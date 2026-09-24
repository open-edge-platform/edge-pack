# tui/screens/step4.py — Step 4: apt installation with live progress and log
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import datetime
import itertools
import logging
import os
import shutil
import stat
import subprocess  # nosec B404 - reviewed: only used with list-form args (no shell=True), fixed apt/pkexec/xdg-open commands, no untrusted input passed to a shell
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen

from .base import BaseWizardScreen, _ButtonNavMixin
from textual.widgets import Button, Footer, Header, Input, ProgressBar, RichLog, Rule, Static

from ..package_logic import collect_selected_packages, required_prerequisites
from edgepack_shared.install_logic import run_install
from edgepack_shared.log import rotate_logs

LOG_DIR = "/var/log/edgepack"


def _candidate_log_paths(filename: str) -> list[str]:
    """Return the ordered [/var/log/edgepack/, XDG data dir] paths to try for *filename*."""
    return [
        os.path.join(LOG_DIR, filename),
        os.path.join(
            os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
            "edgepack", filename,
        ),
    ]


def _classify_origin(origin: str | None) -> str:
    """Classify a repository origin (URL) as Intel, Ubuntu, or Unknown."""
    if not origin:
        return "Unknown"
    origin_lower = origin.lower()
    if "intel" in origin_lower:
        return "Intel"
    host = (urlparse(origin).hostname or "").lower()
    if host == "ubuntu.com" or host.endswith(".ubuntu.com"):
        return "Ubuntu"
    return "Unknown"


def _parse_get_line(line: str) -> tuple[str, str, str] | None:
    """Parse an apt "Get:N <url> <dist/comp> <arch> <pkg> <arch> <version> [<size>]" line.

    Returns (pkg_name, version, url) or None if *line* isn't a package fetch
    line (apt also prints "Get:" lines for index files during apt-get update, which are not packages).

    Packages already present in apt's local archive cache produce no "Get:"
    line at all (apt skips the download), so this only ever reports packages
    actually fetched over the network this run — cached packages are simply
    not tracked, by design.
    """
    if not line.startswith("Get:"):
        return None
    tokens = line.split()
    if len(tokens) < 7:
        return None
    url, pkg, version = tokens[1], tokens[4], tokens[6]
    if pkg.startswith("["):  # index-file fetch line, not a package
        return None
    return pkg, version, url


def _parse_resolved_line(line: str) -> set[str]:
    """Parse "Resolved: name[=version] ..." into a set of bare package names."""
    payload = line[len("Resolved:"):].strip()
    return {entry.partition("=")[0] for entry in payload.split() if entry}


def _apt_cache_policy_origins(pkg_names: set[str]) -> dict[str, tuple[str, str]]:
    """Batched, unprivileged "apt-cache policy" lookup for cached packages that had no "Get:" line.

    Returns {name: (candidate_version, origin_url)}. One subprocess call for
    all names (apt-cache re-parses the whole index per invocation, so
    batching keeps this cheap regardless of how many are cached). Reads
    apt's local index/dpkg status only — no network, no root required.
    """
    if not pkg_names:
        return {}
    try:
        result = subprocess.run(
            ["apt-cache", "policy", *sorted(pkg_names)],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return {}

    origins: dict[str, tuple[str, str]] = {}
    name: str | None = None
    version = "unknown"
    origin = "unknown"
    lines = result.stdout.splitlines()
    for i, raw in enumerate(lines):
        if raw and not raw[0].isspace() and raw.endswith(":"):
            if name:
                origins[name] = (version, origin)
            name, version, origin = raw[:-1], "unknown", "unknown"
        elif raw.strip().startswith("Candidate:"):
            version = raw.split(":", 1)[1].strip()
        elif raw.strip().startswith("***") and i + 1 < len(lines):
            parts = lines[i + 1].split()
            if len(parts) >= 2:
                origin = parts[1]
    if name:
        origins[name] = (version, origin)
    return origins


def _apt_dependency_closure(pkg_names: set[str]) -> set[str]:
    """Recursive hard-dependency closure of *pkg_names*, restricted to already-installed packages.

    Top-level packages only cover what THIS run explicitly requested/pinned
    (edgepack_shared.dep_resolver leaves unconstrained deps for apt to
    resolve on its own). Those auto-pulled deps get a "Get:" line on a fresh
    install, but produce no signal at all on a reinstall where they're
    already satisfied — this closure lets the leftover lookup find them too.
    Best-effort: recursing through shared base-OS libraries means this can
    over-approximate vs. the real install transaction, but a one-level-only
    lookup under-approximates real multi-hop edge/media dependency chains,
    so recursion is the accepted tradeoff. "--installed" limits the result
    to packages actually on the system.
    """
    if not pkg_names:
        return set()
    try:
        result = subprocess.run(
            ["apt-cache", "depends", "--recurse", "--no-recommends", "--no-suggests",
             "--no-conflicts", "--no-breaks", "--no-replaces", "--no-enhances",
             "--installed", *sorted(pkg_names)],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return set()

    closure: set[str] = set()
    for raw in result.stdout.splitlines():
        if raw and not raw[0].isspace():
            closure.add(raw.strip())
    return closure


def _ensure_log_dir(sudo_password: str | None) -> bool:
    """Create /var/log/edgepack/ with elevated privileges if it does not exist yet.

    Mirrors the same auth strategy used by run_install: pkexec inside a
    Flatpak sandbox, sudo -S when a password is available, sudo -n otherwise.
    Returns True on success; False if the directory could not be created —
    callers should fall back gracefully but must log the failure so the
    user and operator are aware that persistent logging is unavailable.
    """
    log_dir = LOG_DIR
    if Path(log_dir).is_dir() and os.access(log_dir, os.W_OK):
        return True
    try:
        # Create the directory owned by the invoking user so the TUI process
        # (which runs unprivileged) can write the log file into it.
        # $SUDO_USER is set by sudo; pkexec sets $PKEXEC_UID instead (no
        # world-writable fallback needed for either elevation path).
        script = (
            f"mkdir -p {log_dir} && "
            f"owner=\"${{SUDO_USER:-${{PKEXEC_UID:-}}}}\" && "
            f"{{ [ -n \"$owner\" ] && chown \"$owner\": {log_dir}; }}; "
            # Restrict directory permissions to owner-only (700). Log files may
            # contain sensitive system inventory data. Do not rely on default umask.
            f"chmod 700 {log_dir}"
        )
        if shutil.which("flatpak-spawn") or os.path.exists("/usr/bin/flatpak-spawn"):
            result = subprocess.run(
                ["flatpak-spawn", "--host", "pkexec", "sh", "-c", script],
                capture_output=True, timeout=10,
            )
        elif sudo_password is not None:
            result = subprocess.run(
                ["sudo", "-S", "-p", "", "sh", "-c", script],
                input=sudo_password + "\n",
                capture_output=True, text=True, timeout=10,
            )
        else:
            result = subprocess.run(
                ["sudo", "-n", "sh", "-c", script],
                capture_output=True, timeout=10,
            )
        if result.returncode != 0:
            logging.getLogger("tui_log").warning(
                "_ensure_log_dir: elevated command exited %d — persistent logging unavailable",
                result.returncode,
            )
            return False
        return True
    except Exception as e:
        logging.getLogger("tui_log").warning(
            "_ensure_log_dir: exception during directory creation (%s) — persistent logging unavailable",
            type(e).__name__,
        )
        return False


# ---------------------------------------------------------------------------
# In-TUI sudo authentication modal
# ---------------------------------------------------------------------------

class SudoAuthScreen(_ButtonNavMixin, ModalScreen):
    """Modal password dialog — collects sudo credentials without leaving the TUI.

    The password is pre-validated with ``sudo -S true`` in a background thread
    before the modal dismisses.  Wrong passwords show an inline error and
    re-focus the input for another attempt.  The user may retry as many times
    as needed and must press Cancel to abort.

    Dismissed with the verified password string on success, or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel",            "Cancel", show=False),
        Binding("space",  "press_focused",     "",       show=False),
        Binding("left",   "focus_prev_button", "",       show=False),
        Binding("right",  "focus_next_button", "",       show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="auth-dialog"):
            yield Static("🔒  Authentication Required", id="auth-title", markup=False)
            yield Rule()
            yield Static(
                "A sudo password is required to install packages.",
                id="auth-msg",
            )
            yield Static("", id="auth-error")  # populated on wrong password
            yield Input(
                password=True,
                id="auth-password",
                placeholder="sudo password",
            )
            with Horizontal(id="auth-actions"):
                yield Button("Cancel", id="btn-auth-cancel")
                yield Button("Authenticate →", variant="success", id="btn-auth-confirm")

    def on_mount(self) -> None:
        self.query_one("#auth-password", Input).focus()

    # ------------------------------------------------------------------
    # Password submission & validation
    # ------------------------------------------------------------------

    def _submit(self, password: str) -> None:
        """Validate *password* via ``sudo -S true`` in a background thread."""
        if not password:
            self.query_one("#auth-error", Static).update("Please enter a password.")
            self.query_one("#auth-password", Input).focus()
            return

        # Show a "Verifying…" state so the user knows something is happening.
        confirm = self.query_one("#btn-auth-confirm", Button)
        confirm.disabled = True
        confirm.label = "Verifying…"
        self.query_one("#auth-error", Static).update("")

        def _validate() -> None:
            try:
                result = subprocess.run(
                    ["sudo", "-S", "-p", "", "true"],
                    input=password + "\n",
                    capture_output=True,
                    text=True,
                )
            except Exception as e:
                logging.getLogger("tui_log").warning("sudo validation failed to run: %s", e)
                self.app.call_from_thread(
                    self._on_wrong_password, "Could not run sudo — see log for details."
                )
                return
            if result.returncode == 0:
                self.app.call_from_thread(self.dismiss, password)
            else:
                self.app.call_from_thread(self._on_wrong_password)

        threading.Thread(target=_validate, daemon=True).start()

    def _on_wrong_password(self, message: str = "Incorrect password, please try again.") -> None:
        confirm = self.query_one("#btn-auth-confirm", Button)
        confirm.disabled = False
        confirm.label = "Authenticate →"
        self.query_one("#auth-error", Static).update(message)
        self.query_one("#auth-password", Input).clear()
        self.query_one("#auth-password", Input).focus()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted, "#auth-password")
    def on_submitted(self, event: Input.Submitted) -> None:
        self._submit(event.value)

    @on(Button.Pressed, "#btn-auth-confirm")
    def on_confirm(self) -> None:
        self._submit(self.query_one("#auth-password", Input).value)

    @on(Button.Pressed, "#btn-auth-cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Installation failure modal
# ---------------------------------------------------------------------------

class InstallFailedScreen(ModalScreen):
    """Modal shown when apt exits with a non-zero status code."""

    BINDINGS = [Binding("space", "exit_app", "", show=False)]

    def __init__(self, exit_code: int, log_path: str | None) -> None:
        super().__init__()
        self._exit_code = exit_code
        self._log_path = log_path

    def compose(self) -> ComposeResult:
        with Vertical(id="error-dialog"):
            yield Static("✗  Installation Failed", id="error-title", markup=False)
            yield Rule()
            yield Static(
                f"Installation failed (exit code: {self._exit_code}).\n\n"
                "Possible causes:\n"
                "  \u2022 Network or repository access problem\n"
                "  \u2022 Package not found in the repository\n"
                "  \u2022 Package conflicts on this system\n"
                "  \u2022 Insufficient disk space\n\n"
                + (f"Full log saved to:\n  {self._log_path}" if self._log_path else "No log file was saved."),
                id="error-msg",
            )
            with Horizontal(id="error-actions"):
                yield Button("Exit Installer", variant="error", id="btn-exit-error")

    def on_mount(self) -> None:
        self.set_timer(0.05, lambda: self.query_one("#btn-exit-error", Button).focus())

    def action_exit_app(self) -> None:
        self.app.exit()

    @on(Button.Pressed, "#btn-exit-error")
    def on_exit_error(self) -> None:
        self.app.exit()


# ---------------------------------------------------------------------------
# Post-install restart prompt (modal overlay)
# ---------------------------------------------------------------------------

class RestartPromptScreen(_ButtonNavMixin, ModalScreen):
    """Modal shown after a successful install — offer restart or skip."""

    BINDINGS = [
        Binding("escape", "skip",             "Skip",    show=False),
        Binding("space",  "press_focused",    "",        show=False),
        Binding("left",   "focus_prev_button","",        show=False),
        Binding("right",  "focus_next_button","",        show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="restart-dialog"):
            yield Static("✓  Installation Complete", id="restart-title", markup=False)
            yield Rule()
            yield Static(
                "A system restart is recommended to apply\n"
                "all changes from the installed packages.",
                id="restart-msg",
            )
            with Horizontal(id="restart-actions"):
                yield Button("↺  Restart Now", variant="warning", id="btn-restart")
                yield Button("Skip — Close Installer", id="btn-skip")

    def on_mount(self) -> None:
        self.set_timer(0.05, lambda: self.query_one("#btn-restart", Button).focus())

    def action_skip(self) -> None:
        self.app.exit()

    @on(Button.Pressed, "#btn-skip")
    def on_skip(self) -> None:
        self.app.exit()

    @on(Button.Pressed, "#btn-restart")
    def on_restart(self) -> None:
        # If the sudo cache from the install is still valid we can reboot
        # immediately without asking for a password again.
        try:
            cache_valid = subprocess.run(
                ["sudo", "-n", "true"],
                capture_output=True,
            ).returncode == 0
        except Exception as e:
            logging.getLogger("tui_log").warning("sudo cache check failed to run: %s", e)
            cache_valid = False  # fail closed — fall through to the password prompt

        if cache_valid:
            self._do_reboot(password=None, use_cache=True)
        else:
            self.app.push_screen(SudoAuthScreen(), self._do_reboot)

    def _do_reboot(self, password: str | None, use_cache: bool = False) -> None:
        """Run reboot via sudo. Uses cached credentials or an explicit password."""
        if not use_cache and password is None:
            return  # user cancelled the password dialog

        _REBOOT_DELAY = 4  # seconds between TUI exit and reboot

        def _run() -> None:
            # Close the TUI first so the terminal is restored before we print.
            self.app.call_from_thread(self.app.exit)
            # Give Textual a moment to finish its cleanup / restore the terminal.
            time.sleep(0.5)

            for remaining in range(_REBOOT_DELAY, 0, -1):
                sys.stdout.write(f"\rRebooting in {remaining} second{'s' if remaining != 1 else ''}...  ")
                sys.stdout.flush()
                time.sleep(1)
            sys.stdout.write("\rRebooting now...                \n")
            sys.stdout.flush()

            for base_cmd in (["sudo", "systemctl", "reboot", "-i"], ["sudo", "reboot"]):
                try:
                    if use_cache:
                        cmd = base_cmd
                        inp = None
                    else:
                        cmd = ["sudo", "-S", "-p", ""] + base_cmd[1:]
                        inp = password + "\n"
                    result = subprocess.run(
                        cmd,
                        input=inp,
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    if result.returncode == 0:
                        return
                except Exception:
                    continue
            sys.stdout.write("Reboot failed. Please restart your system manually.\n")
            sys.stdout.flush()

        # Non-daemon so the thread outlives the Textual app and the reboot runs.
        threading.Thread(target=_run, daemon=False).start()


_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _pkg_id(name: str) -> str:
    """Sanitize a package name for use as a Textual widget ID."""
    return "pkg-row-" + name.replace(".", "-").replace("+", "-")


class Step4Screen(_ButtonNavMixin, BaseWizardScreen):
    """Step 4 — runs the apt installation and streams its output."""

    BINDINGS = [
        Binding("f1",     "app.show_about",    "About",   show=True),
        Binding("tab",    "focus_next_smart",  "Next",    show=True),
        Binding("enter",  "press_focused",     "Confirm", show=False),
        Binding("space",  "press_focused",     "Select",   show=True,  priority=True),
        Binding("left",   "focus_prev_button", "",        show=False),
        Binding("right",  "focus_next_button", "",        show=False),
        Binding("ctrl+q", "app.quit",           "Quit",   show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._install_running = False
        self._install_complete = False
        self._install_failed_code: int | None = None
        self._spinner = itertools.cycle(_SPINNER)
        self._active_pkg: str | None = None
        self._pkg_names: list[str] = []
        self._log_file = None         # opened when install starts
        self._actual_log_path: str | None = None
        self._install_ts: str | None = None
        self._pkg_get_origins: dict[str, tuple[str, str]] = {}
        self._in_install_phase = False
        # Full expected package roster (prereq names known upfront + main
        # names learned from the "Resolved:" line) — diffed against
        # _pkg_get_origins at the end to find cached packages with no "Get:".
        self._prereq_pkg_names: set[str] = set()
        self._resolved_pkg_names: set[str] = set()
        # Pre-auth via app.suspend()+sudo -v is needed unless we are already
        # root or running inside a Flatpak (where pkexec is used instead).
        # Deliberately NOT based on $DISPLAY: even with X11 forwarding active
        # there may be no graphical polkit agent, causing pkexec to fall back to
        # a text-mode prompt that writes directly to the TTY and corrupts the TUI.
        _in_flatpak = bool(
            shutil.which("flatpak-spawn") or os.path.exists("/usr/bin/flatpak-spawn")
        )
        self._needs_sudo: bool = not _in_flatpak and os.getuid() != 0

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical(id="step4-outer"):
            yield Static("Step 4 of 4 — Installing", id="step4-title")
            yield Rule()

            # Package status list — populated in on_mount
            yield Static("Packages to be installed:", id="pkg-list-heading")
            yield Vertical(id="pkg-status-list")

            # Progress bar + status label (hidden until install starts)
            yield ProgressBar(total=100, id="install-progress", show_eta=False)
            yield Static("", id="install-status-label")

            yield Rule()

            # Live apt output
            yield RichLog(id="install-log", highlight=True, markup=True, wrap=True)

            yield Rule()

            with Horizontal(id="step4-actions"):
                yield Button("← Back", id="btn-back")
                yield Button("▶ Install Now", variant="success", id="btn-install")

        yield Footer()

    # ------------------------------------------------------------------
    # Mount
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        packages = collect_selected_packages(self.app.pkg_entries)  # type: ignore[attr-defined]
        self._pkg_names = sorted(packages.keys())

        pkg_list = self.query_one("#pkg-status-list", Vertical)
        for name in self._pkg_names:
            pkg_list.mount(Static(
                f"  ○  {name}",
                id=_pkg_id(name),
                classes="pkg-status-row",
            ))

        # Hide progress widgets until install starts
        self.query_one("#install-progress").display = False
        self.query_one("#install-status-label").display = False

        # Spinner timer — updates the active package icon at 10 fps
        self.set_interval(0.1, self._tick_spinner)

        # Default focus: Install Now button
        self.set_timer(0.05, lambda: self.query_one("#btn-install", Button).focus())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_focus_next_smart(self) -> None:
        prev = self.focused
        self.app.action_focus_next()
        if (
            not isinstance(prev, Button)
            and isinstance(self.focused, Button)
            and self.focused.id == "btn-back"
        ):
            self.app.action_focus_next()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        if not self._install_running:
            self.app.pop_screen()

    @on(Button.Pressed, "#btn-install")
    def on_install(self) -> None:
        if self._install_running:
            return

        # After completion the button becomes "Next →" — open restart prompt
        if self._install_complete:
            if self._install_failed_code is not None:
                self.app.push_screen(InstallFailedScreen(self._install_failed_code, self._actual_log_path))
            else:
                self.app.push_screen(RestartPromptScreen())
            return

        app = self.app  # type: ignore[attr-defined]
        packages = collect_selected_packages(app.pkg_entries)

        if not packages:
            self._append_log("[yellow]No packages selected to install.[/yellow]")
            return

        if self._needs_sudo:
            # push_screen with a callback is the correct Textual pattern for
            # receiving a dismissed value without requiring a worker.
            self.app.push_screen(SudoAuthScreen(), self._on_auth_result)
        else:
            self._start_install(sudo_password=None)

    def _on_auth_result(self, password: str | None) -> None:
        """Callback invoked when SudoAuthScreen is dismissed."""
        if password is None:
            return  # user cancelled — do nothing
        self._start_install(sudo_password=password)

    def _start_install(self, sudo_password: str | None) -> None:
        """Lock the UI and launch the background install thread."""
        app = self.app  # type: ignore[attr-defined]
        packages = collect_selected_packages(app.pkg_entries)

        self._install_running = True
        self.query_one("#btn-install", Button).disabled = True
        self.query_one("#btn-back", Button).disabled = True

        # Show progress widgets
        self.query_one("#install-progress").display = True
        self.query_one("#install-status-label").display = True
        self.query_one("#install-status-label", Static).update("Starting installation…")

        self.query_one("#install-log", RichLog).clear()
        self._append_log("Starting installation…\n")

        repos = list((app.detected_os_entry or {}).get("repositories", {}).values())
        selected_profiles = [app.selected_profile, *app.selected_addon_profiles]
        prerequisites = required_prerequisites(
            app.processor,
            selected_profiles,
            app.detected_os_key,
        )
        hidden_packages: list[str] = []
        for _key in selected_profiles:
            if _key:
                hidden_packages.extend(
                    app.processor.hidden_os_packages(_key, app.detected_platform_key, app.detected_os_key)
                )

        # Ensure /var/log/edgepack/ is writable (requires root on first run).
        _log_dir_ok = _ensure_log_dir(sudo_password)
        if not _log_dir_ok:
            self._append_log(
                "[yellow]Warning: could not create persistent log directory; "
                "installation will proceed but logs will not be retained.[/yellow]"
            )
        # Clean up stale log files before creating new ones.
        rotate_logs(LOG_DIR, max_age_days=30, max_count=10)

        # Open log file — fall back to XDG user dir if /var/log/edgepack/ is not yet writable
        _ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._install_ts = _ts
        self._pkg_get_origins = {}
        self._in_install_phase = False
        self._prereq_pkg_names = {p.split("=")[0] for p in (prerequisites.get("packages") or [])}
        self._resolved_pkg_names = set()
        _log_filename = f"edgepack-installer-{_ts}.log"
        for _candidate in _candidate_log_paths(_log_filename):
            try:
                Path(_candidate).parent.mkdir(parents=True, exist_ok=True)
                self._log_file = open(_candidate, "w", encoding="utf-8", buffering=1)
                # Restrict log file permissions to owner-only (0o600). Log files may
                # contain sensitive system inventory data; do not rely on umask.
                os.chmod(_candidate, stat.S_IRUSR | stat.S_IWUSR)
                self._actual_log_path = _candidate
                break
            except Exception:
                continue
        else:
            self._log_file = None
            self._actual_log_path = None

        if self._log_file:
            try:
                self._log_file.write(
                    f"EdgePack Installer log\n"
                    f"Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Packages: {', '.join(self._pkg_names)}\n"
                    f"{'=' * 60}\n"
                )
            except Exception:
                # UI/widget may be gone after install completes — silently ignore
                pass

        kwargs = dict(
            output_callback=self._on_output,
            progress_callback=self._on_progress,
            finished_callback=self._on_finished,
            schedule=app.call_from_thread,
        )
        run_install(sorted(packages.items()), repos, sudo_password=sudo_password,
                    prerequisites=prerequisites, force_packages=hidden_packages, **kwargs)

    # ------------------------------------------------------------------
    # Install callbacks  (invoked on Textual thread via call_from_thread)
    # ------------------------------------------------------------------

    def _on_output(self, line: str) -> None:
        """Append a regular apt output line to the log widget and log file."""
        stripped = line.strip()
        cleaned = line.rstrip("\n")
        self._append_log(cleaned)
        if self._log_file:
            try:
                self._log_file.write(line if line.endswith("\n") else line + "\n")
            except Exception:
                # UI/widget may be gone after install completes — silently ignore
                pass
        # "Running: apt-get update" — echoed once before every apt-get update
        # call (prerequisite stage and main stage). Turns OFF Get:-line
        # tracking so index-file fetches (Packages/Translation-en/etc, which
        # can otherwise look like a real package line) are never captured.
        # "Running: apt-get ... install ..." — echoed once before every
        # apt-get install call (prerequisite stage and main stage). Turns ON
        # tracking so that stage's package fetches are captured.
        if stripped.startswith("Running: apt-get update"):
            self._in_install_phase = False
        elif stripped.startswith("Running: apt-get"):
            self._in_install_phase = True
        elif self._in_install_phase:
            parsed = _parse_get_line(stripped)
            if parsed:
                pkg, version, url = parsed
                self._pkg_get_origins[pkg] = (version, url)
        if stripped.startswith("Resolved:"):
            self._resolved_pkg_names |= _parse_resolved_line(stripped)
        # "Setting up pkg (version) ..." — treat as active package
        if stripped.startswith("Setting up "):
            pkg = stripped[len("Setting up "):].split()[0].split(":")[0]
            self._mark_active(pkg)

    def _on_progress(self, percent: float, pkg: str, msg: str) -> None:
        """Handle a pmstatus progress update from APT::Status-Fd."""
        pkg = pkg.split(":")[0]  # strip :amd64 architecture suffix
        try:
            self.query_one("#install-progress", ProgressBar).update(progress=percent)
            self.query_one("#install-status-label", Static).update(msg)
        except Exception:
            # UI/widget may be gone after install completes — silently ignore
            pass
        if percent >= 99.9:
            self._mark_done(pkg)
        else:
            self._mark_active(pkg)

    def _on_finished(self, exit_code: int = 0) -> None:
        """Called when apt exits. Branches on exit_code for success vs failure."""
        self._install_running = False
        self._install_complete = True
        self._active_pkg = None

        # Close log file
        if self._log_file:
            try:
                self._log_file.write(
                    f"{'=' * 60}\n"
                    f"Finished: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                    f"(exit code: {exit_code})\n"
                )
                self._log_file.close()
            except Exception:
                # UI/widget may be gone after install completes — silently ignore
                pass
            self._log_file = None

        if exit_code != 0:
            # Mark the active/in-progress package as failed; leave others as-is
            for name in self._pkg_names:
                try:
                    widget = self.query_one(f"#{_pkg_id(name)}", Static)
                    text = widget.renderable if hasattr(widget, 'renderable') else ""
                    # Only mark packages that weren't already ticked as done
                    if "\u2713" not in str(text):
                        widget.update(f"  [red]\u2717[/red]  {name}")
                except Exception:
                    # UI/widget may be gone after install completes — silently ignore
                    pass
            try:
                self.query_one("#install-progress", ProgressBar).update(progress=0)
                self.query_one("#install-status-label", Static).update(
                    "[bold red]Installation failed[/bold red]"
                )
            except Exception:
                # UI/widget may be gone after install completes — silently ignore
                pass
            self._append_log(f"\n[bold red]Installation failed (exit code: {exit_code}).[/bold red]")
            self._install_failed_code = exit_code
            try:
                btn = self.query_one("#btn-install", Button)
                btn.label = "Next \u2192"
                btn.variant = "error"
                btn.disabled = False
                self.set_timer(0.1, lambda: btn.focus())
            except Exception:
                # UI/widget may be gone after install completes — silently ignore
                pass
        else:
            for name in self._pkg_names:
                self._mark_done(name)
            try:
                self.query_one("#install-progress", ProgressBar).update(progress=100)
                self.query_one("#install-status-label", Static).update(
                    "[bold green]Checking installed packages\u2026[/bold green]"
                )
            except Exception:
                # UI/widget may be gone after install completes — silently ignore
                pass
            self._append_log("\n[bold green]Installation complete.[/bold green]")
            if self._actual_log_path:
                self._append_log(f"[dim]Full installation log saved to: {self._actual_log_path}[/dim]")
            # Keep the Next button disabled until the package summary log is
            # written — the lookup is a single batched, unprivileged
            # apt-cache call so this only adds a brief delay.
            threading.Thread(target=self._collect_and_write_package_summary, daemon=True).start()

    def _collect_and_write_package_summary(self) -> None:
        """Background-thread step: resolve cached packages' origins, then write the summary.

        Runs off the UI thread since "apt-cache policy"/"apt-cache depends"
        are subprocess calls; _write_package_summary_log() is then scheduled
        back onto the UI thread (it touches the RichLog widget).
        """
        expected = self._prereq_pkg_names | self._resolved_pkg_names
        expected |= _apt_dependency_closure(expected)
        leftover = expected - set(self._pkg_get_origins)
        cached_origins = _apt_cache_policy_origins(leftover)
        self.app.call_from_thread(self._write_package_summary_log, cached_origins)
        self.app.call_from_thread(self._finish_success_ui)

    def _write_package_summary_log(self, cached_origins: dict[str, tuple[str, str]] | None = None) -> None:
        """Write the categorized Intel/Ubuntu/Unknown package summary log.

        Merges packages seen via apt's "Get:" fetch lines (freshly
        downloaded) with *cached_origins* — packages already present in
        apt's local archive cache, resolved via a separate "apt-cache
        policy" lookup since they never produce a "Get:" line. No-op if
        nothing was found either way (e.g. mock installs).
        """
        all_origins = {**(cached_origins or {}), **self._pkg_get_origins}
        if not all_origins:
            return

        buckets: dict[str, list[str]] = {"Intel": [], "Ubuntu": [], "Unknown": []}
        for name in sorted(all_origins):
            version, origin = all_origins[name]
            category = _classify_origin(origin)
            tag = "" if name in self._pkg_get_origins else "  [cached]"
            buckets[category].append(f"  - {name} {version}  ({origin}){tag}")

        _filename = f"edgepack-packages-{self._install_ts or 'unknown'}.log"
        for _candidate in _candidate_log_paths(_filename):
            try:
                Path(_candidate).parent.mkdir(parents=True, exist_ok=True)
                with open(_candidate, "w", encoding="utf-8") as f:
                    f.write(
                        "EdgePack Software BOM\n"
                        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"{'=' * 60}\n\n"
                    )
                    for category in ("Intel", "Ubuntu", "Unknown"):
                        entries = buckets[category]
                        f.write(f"{category} Packages ({len(entries)}):\n")
                        f.write(("\n".join(entries) if entries else "  (none)") + "\n\n")
                # Restrict log file permissions to owner-only (0o600). Do not rely on umask.
                os.chmod(_candidate, stat.S_IRUSR | stat.S_IWUSR)
                self._append_log(f"[dim]Full Software BOM saved to: {_candidate}[/dim]")
                return
            except Exception:
                continue

    def _finish_success_ui(self) -> None:
        """Complete the success UI transition once the package summary log is done."""
        try:
            self.query_one("#install-status-label", Static).update(
                "[bold green]Installation complete[/bold green]"
            )
        except Exception:
            # UI/widget may be gone after install completes — silently ignore
            pass
        try:
            btn = self.query_one("#btn-install", Button)
            btn.label = "Next \u2192"
            btn.variant = "success"
            btn.disabled = False
            self.set_timer(0.1, lambda: btn.focus())
        except Exception:
            # UI/widget may be gone after install completes — silently ignore
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _tick_spinner(self) -> None:
        """Advance the spinner icon on the currently active package row."""
        if self._active_pkg is None or self._install_complete:
            return
        frame = next(self._spinner)
        try:
            self.query_one(f"#{_pkg_id(self._active_pkg)}", Static).update(
                f"  {frame}  {self._active_pkg}"
            )
        except Exception:
            # UI/widget may be gone after install completes — silently ignore
            pass

    def _mark_active(self, pkg_name: str) -> None:
        """Mark a package as currently being installed (spinner)."""
        if pkg_name not in self._pkg_names:
            return
        if self._active_pkg and self._active_pkg != pkg_name:
            self._mark_done(self._active_pkg)
        self._active_pkg = pkg_name

    def _mark_done(self, pkg_name: str) -> None:
        """Mark a package as successfully installed (green ✓)."""
        if pkg_name not in self._pkg_names:
            return
        if self._active_pkg == pkg_name:
            self._active_pkg = None
        try:
            self.query_one(f"#{_pkg_id(pkg_name)}", Static).update(
                f"  [green]✓[/green]  {pkg_name}"
            )
        except Exception:
            # UI/widget may be gone after install completes — silently ignore
            pass

    def _append_log(self, text: str) -> None:
        try:
            self.query_one("#install-log", RichLog).write(text)
        except Exception:
            # UI/widget may be gone after install completes — silently ignore
            pass

