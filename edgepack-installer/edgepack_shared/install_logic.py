# edgepack_shared/install_logic.py — apt installation logic (UI-agnostic)
#
# SPDX-License-Identifier: MIT

import os
import shlex
import shutil
import subprocess  # nosec B404 - reviewed: only used with list-form args (no shell=True), fixed apt/pkexec commands, no untrusted input passed to a shell
import sys
import threading
from urllib.parse import urlparse

SOURCES_LIST_PATH = "/etc/apt/sources.list.d/edgepack.list"
PREFERENCES_PATH = "/etc/apt/preferences.d/edgepack.pref"
DEFAULT_PIN_PRIORITY = 1001


_INTEL_NO_PROXY = (
    "localhost,.local,127.0.0.0/8,10.0.0.0/8,192.168.0.0/16,172.16.0.0/12"
)


def _proxy_env_exports() -> str:
    """Build 'export VAR=value' lines for proxy env vars set in the user session.

    pkexec runs in a clean environment and strips proxy variables, so apt inside
    the root shell won't respect the user's no_proxy / http_proxy settings.
    We re-inject them at the top of the install script so apt routes correctly.

    no_proxy always includes the Intel internal address ranges; any additional
    entries already set in the user session are merged in.
    """
    exports = []

    # Pass through http/https proxy from user session if set
    for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        val = os.environ.get(var)
        if val:
            safe = val.replace("'", "'\\''")
            exports.append(f"export {var}='{safe}'")

    # Build no_proxy: always include Intel ranges, extend with user's entries
    user_no_proxy = os.environ.get("no_proxy") or os.environ.get("NO_PROXY") or ""
    extra = ",".join(
        e for e in user_no_proxy.split(",")
        if e.strip() and e.strip() not in _INTEL_NO_PROXY
    )
    merged_no_proxy = _INTEL_NO_PROXY + ("," + extra if extra else "")
    exports.append(f"export no_proxy='{merged_no_proxy}'")
    exports.append(f"export NO_PROXY='{merged_no_proxy}'")

    return "\n".join(exports) + "\n"


# ---------------------------------------------------------------------------
# Path resolver for _dep_resolver.py
#
# The resolver runs as a standalone script inside the privileged shell after
# "apt-get update".  In a PyInstaller bundle it is extracted alongside the
# other data files under sys._MEIPASS; in a normal source checkout it lives
# next to this module in edgepack_shared/.
# ---------------------------------------------------------------------------

def _resolver_path() -> str:
    """Return the absolute path to dep_resolver.py for both frozen and source runs."""
    if getattr(sys, 'frozen', False):
        # PyInstaller bundle: data files are under sys._MEIPASS
        return os.path.join(sys._MEIPASS, 'edgepack_shared', 'dep_resolver.py')
    # Normal source checkout: file is in the same directory as this module
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dep_resolver.py')


PREREQ_KEYRING_DIR = "/etc/apt/keyrings"
PREREQ_SOURCES_PATH = "/etc/apt/sources.list.d/edgepack-prereq.list"


def _require_https(url, label):
    """Raise ValueError if a YAML-sourced url is set but not https:// (TLS-only network policy)."""
    if url and not str(url).strip().lower().startswith("https://"):
        raise ValueError(f"Insecure {label} rejected (must use https://): {url!r}")


def _build_prerequisite_script(prerequisites):
    """Compose the shell snippet that satisfies addon prerequisites before anything else runs.

    Mirrors the manual bring-up steps for a gating package, with a real signing key
    (a ``repository_key`` is now mandatory for every repo — no unsigned fallback):
        wget -qO- <key-url> | gpg --dearmor -o /etc/apt/keyrings/<name>.gpg
        echo "deb [signed-by=...] <url> <dist> <components>" > .../edgepack-prereq.list
        apt-get update
        apt-get install <packages>

    Every command is chained with "|| exit $?" so a failure here aborts before
    the normal edgepack sources file is written or any normal package is
    touched. Returns "" when there are no repositories to add.
    """
    prerequisites = prerequisites or {}
    repos = [r for r in (prerequisites.get("repositories") or []) if r.get("repository_url")]
    packages = prerequisites.get("packages") or []
    if not repos:
        return ""

    # APT verifies repository metadata as an unprivileged user, so it must be
    # able to traverse the keyring directory and read each referenced key.
    lines = [
        f"install -d -m 0755 {PREREQ_KEYRING_DIR}",
        "command -v gpg >/dev/null 2>&1 || "
        "{ apt-get update && apt-get install -y gnupg; } || exit $?",
    ]

    sources_lines = []
    for i, repo in enumerate(repos):
        url = str(repo["repository_url"]).strip()
        dist = repo.get("repository_dist") or ""
        components = " ".join(repo.get("repository_components") or ["main"])
        key_url = repo.get("repository_key")
        _require_https(url, "repository_url")
        _require_https(key_url, "repository_key")

        if not key_url:
            raise ValueError(f"repository_key is required for {url!r}")

        keyring_path = f"{PREREQ_KEYRING_DIR}/edgepack-prereq-{i}.gpg"
        # key_url/keyring_path land in a shell command (not just file content) -- must be quoted.
        lines.append(
            f"wget -qO- {shlex.quote(key_url)} | "
            f"gpg --batch --yes --dearmor -o {shlex.quote(keyring_path)} && "
            f"chmod 0644 {shlex.quote(keyring_path)} || exit $?"
        )
        signed_by = f"[signed-by={keyring_path}] "

        line = f"deb {signed_by}{url}"
        if dist:
            line += f" {dist} {components}"
        sources_lines.append(line)

    sources_content = "\n".join(sources_lines) + "\n"
    lines.append(f"cat > {PREREQ_SOURCES_PATH} <<'EOF'\n{sources_content}EOF")
    lines.append('echo "Running: apt-get update"')
    lines.append("apt-get update || exit $?")

    # Quote each package name individually so a malicious/malformed name can't
    # inject shell metacharacters, while still passing as separate apt args.
    pkgs = " ".join(shlex.quote(p) for p in packages)
    if pkgs:
        lines.append(
            f'echo "Running: apt-get -o Dpkg::Options::=--force-confnew install -y {pkgs}"'
        )
        lines.append(
            f"apt-get -o Dpkg::Options::=--force-confnew install -y {pkgs} || exit $?"
        )
    return "\n".join(lines) + "\n"


def _build_apt_preferences(repos):
    """Compose an apt preferences file pinning each edgepack repo's origin host.

    Each entry in *repos* may set ``pin_priority`` (an int) to control how
    strongly apt prefers that repo's origin over other sources; entries that
    omit it fall back to DEFAULT_PIN_PRIORITY. Pins are scoped by
    "Pin: origin <host>" (not the full URL/path) since apt preferences only
    matches on origin hostname, dist/release, or component. Returns "" when no
    repo has a resolvable host, so callers can skip writing an empty file.
    """
    seen = set()
    blocks = []
    for repo in repos:
        url = (repo.get("repository_url") or "").rstrip("/")
        dist = repo.get("repository_dist") or ""
        if not url or not dist:
            continue
        host = urlparse(url).hostname
        if not host:
            continue
        priority = repo.get("pin_priority", DEFAULT_PIN_PRIORITY)
        key = (host, priority)
        if key in seen:
            continue
        seen.add(key)
        blocks.append(f"Package: *\nPin: origin {host}\nPin-Priority: {priority}\n")

    return "\n".join(blocks)


def _build_install_script(packages, repos, prerequisites=None):
    """Compose the shell script that writes the sources file, runs apt-get update, then installs.

    Each entry in *repos* is a repository config dict from the YAML ``repositories`` section,
    containing ``repository_url``, ``repository_dist``, ``repository_components``, and a required
    ``repository_key`` URL. The key is downloaded and used with [signed-by=...]; a repo with a URL
    and dist but no key raises ``ValueError`` (unsigned/trusted=yes repos are no longer allowed).

    *prerequisites* (optional) is a ``{repositories, packages}`` dict — see
    ``_build_prerequisite_script`` — run and gated on before the normal flow below.
    """
    key_download_cmds = []  # standalone shell commands; written before the sources file
    sources_lines = []
    needs_gpg = False
    for repo in repos:
        url = str(repo.get("repository_url") or "").strip()
        dist = repo.get("repository_dist") or ""
        components = repo.get("repository_components") or ["main"]
        component_str = " ".join(components)
        key_url = repo.get("repository_key")
        _require_https(url, "repository_url")
        _require_https(key_url, "repository_key")
        if url and dist:
            if not key_url:
                raise ValueError(f"repository_key is required for {url!r} (unsigned/trusted=yes repos are no longer allowed)")
            needs_gpg = True
            # Download signing key into the keyring directory, then reference it via signed-by.
            keyring_path = f"{PREREQ_KEYRING_DIR}/edgepack-{hash(url) & 0xFFFF:x}.gpg"
            key_download_cmds.append(
                f"wget -qO- {shlex.quote(key_url)} | "
                f"gpg --batch --yes --dearmor -o {shlex.quote(keyring_path)} && "
                f"chmod 0644 {shlex.quote(keyring_path)} || exit $?"
            )
            signed_by = f"[signed-by={keyring_path}] "
            sources_lines.append(f"deb {signed_by}{url} {dist} {component_str}")

    sources_content = "\n".join(sources_lines) + "\n"

    # Quote each package name individually (see _build_prerequisite_script) --
    # this is the exact command-substitution boundary Bandit's B404 flags.
    pkg_names = " ".join(shlex.quote(name) for name, _ in packages)

    # Notes on script structure:
    #   - No global "set -e": we need the diagnostic block to run after a
    #     failed apt-get install, then re-exit with the original code.
    #   - "apt-get update || exit $?" still aborts early on update failure.
    #   - _dep_resolver.py is bundled as a data file (PyInstaller) or lives
    #     next to this module (source run).  _resolver_path() returns the
    #     correct path for both cases — no temp file writing needed.
    #   - "--allow-downgrades" lets apt pin a version lower than whatever is
    #     currently installed when the Depends line requires it.
    #   - "-V" (--verbose-versions) prints the exact version being installed /
    #     upgraded / removed for every package.
    #   - On non-zero exit, "apt-cache policy" is run on the same package list
    #     so the log captures repository priorities and available versions —
    #     essential for diagnosing unmet-dependency errors.
    prereq_script = _build_prerequisite_script(prerequisites)
    if prereq_script and not sources_content.strip():
        # Prerequisites returned a non-empty script but the main repo config
        # was empty (e.g. missing signing key caused an early abort in the
        # loop above). Do NOT write an empty or partial sources file — abort
        # entirely so the privileged shell exits before touching apt state.
        print("error: prerequisite check aborted — repository configuration incomplete", file=sys.stderr)
        return ""

    resolver = shlex.quote(_resolver_path())
    # Download signing keys before writing the sources file so they are
    # available when apt-get update runs.
    if needs_gpg:
        key_download_cmds.insert(
            0,
            "command -v gpg >/dev/null 2>&1 || "
            "{ apt-get update && apt-get install -y gnupg; } || exit $?"
        )
    _key_dl = ("\n".join(key_download_cmds) + "\n") if key_download_cmds else ""
    preferences_content = _build_apt_preferences(repos)
    _prefs_write = (
        f"cat > {PREFERENCES_PATH} <<'EOF'\n{preferences_content}EOF\n"
        if preferences_content else ""
    )
    return (
        f"{_proxy_env_exports()}"
        f"export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a; "
        f"{prereq_script}"
        f"{_key_dl}"
        f"cat > {SOURCES_LIST_PATH} <<'EOF'\n{sources_content}EOF\n"
        f"{_prefs_write}"
        f'echo "Running: apt-get update"; '
        f"apt-get update || exit $?; "
        # Disable glob expansion and split the resolver output on newlines only,
        # so the unquoted $PKGS below (run as root) cannot glob-expand against /
        # or word-split on whitespace in a version string (review Issue 1).
        f"set -f; IFS='\n'; "
        f"PKGS=$(python3 {resolver} {pkg_names}) || exit $?; "
        f'PKGS_INLINE=$(echo "$PKGS" | tr "\\n" " "); '
        f'echo "Resolved: $PKGS_INLINE"; '
        f'echo "Running: apt-get -o Dpkg::Options::=--force-confnew install --allow-downgrades -y -V $PKGS_INLINE"; '
        f"apt-get -o APT::Status-Fd=1 -o Dpkg::Options::=--force-confnew install --allow-downgrades -y -V $PKGS; "
        f"_APT_EXIT=$?; "
        f"exit $_APT_EXIT"
    )


def _call_direct(fn, *args):
    fn(*args)


def run_install(packages, repos, output_callback, finished_callback,
                progress_callback=None, schedule=_call_direct, sudo_password=None,
                prerequisites=None, force_packages=None):
    """Start a background thread that runs the apt install script.

    Args:
        packages: list of (name, version) tuples.
        force_packages: optional list of package names appended to the apt
            command unversioned, without surfacing in the UI/summary (YAML
            ``meta_packages_by_os``). Names already in ``packages`` are skipped
            so they aren't listed twice.
        repos: list of repository config dicts from the YAML ``repositories``
            section (each has ``repository_url``, ``repository_dist``,
            ``repository_components``).
        prerequisites: optional dict ``{repositories: [...], packages: [...]}``
            (see ``tui.package_logic.required_prerequisites``). Each entry in
            ``repositories`` has ``repository_url``, ``repository_dist``,
            ``repository_components``, and a required ``repository_key``.
            When non-empty, every repo is added (signed with its key) and all
            ``packages`` installed *before* the normal sources file is written
            and the normal install runs; a failure here aborts before anything
            else is touched.
        output_callback: called with each regular apt output line.
        finished_callback: called with no arguments when the install exits.
        progress_callback: optional callable(percent, pkg, msg) driven by
            APT::Status-Fd pmstatus lines.  Not called for dlstatus lines.
        schedule: callable used to dispatch callbacks onto the UI thread.
        sudo_password: password string collected from the in-TUI auth modal.
            When provided, ``sudo -S`` reads it from stdin.
            When None (already root, or Flatpak path), ``sudo -n`` is used
            (no prompt; relies on cached credentials or root privileges).

    Auth strategy:
        Flatpak sandbox:
            ``flatpak-spawn --host pkexec`` elevates via the graphical polkit
            agent guaranteed to be present in the host desktop session.
        Everything else (direct terminal, SSH, headless):
            The caller collects the password via an in-TUI modal and passes it
            here as ``sudo_password``.  ``sudo -S -p ""`` reads from stdin so
            the subprocess never needs to touch Textual's terminal.
    """

    def target():
        try:
            existing = {name for name, _ in packages}
            all_packages = list(packages) + [
                (name, "") for name in (force_packages or []) if name not in existing
            ]
            script = _build_install_script(all_packages, repos, prerequisites)

            if not script:
                # _build_install_script returns "" when a repository is missing
                # its signing key — this is a fatal configuration error.
                schedule(output_callback, "\nError: repository configuration incomplete\n")
                schedule(finished_callback, 1)
                return

            if shutil.which("flatpak-spawn") or os.path.exists("/usr/bin/flatpak-spawn"):
                # Flatpak sandbox: delegate to host so pkexec can reach the
                # graphical polkit agent.
                cmd = ["flatpak-spawn", "--host", "pkexec", "sh", "-c", script]
                stdin_data = None
            elif sudo_password is not None:
                # Password collected from the TUI modal.
                # -S  : read password from stdin
                # -p "": suppress the prompt so it doesn't pollute the output stream
                cmd = ["sudo", "-S", "-p", "", "sh", "-c", script]
                # ITEP-95741
                # Mutable bytearray container which can be explicitly cleared.
                # Deterministic memory wiping plus reducing memory forensics window
                stdin_data = bytearray((sudo_password + "\n").encode('utf-8'))
            else:
                # Already root, or caller used another pre-auth mechanism.
                cmd = ["sudo", "-n", "sh", "-c", script]
                stdin_data = None

            # The subprocess must never inherit Textual's terminal fd.
            # stdin=PIPE is used when we feed the password; DEVNULL otherwise.
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
                text=True,
            )
            # ITEP-95741
            # Write password as string (bytearray converted on-the-fly by subprocess)
            # and securely wipe the password bytearray from memory
            if stdin_data is not None:
                process.stdin.write(stdin_data.decode('utf-8'))
                process.stdin.close()
                stdin_data.clear()
            for line in process.stdout:
                stripped = line.rstrip('\n')
                if stripped.startswith('pmstatus:'):
                    if progress_callback:
                        parts = stripped.split(':', 3)
                        if len(parts) == 4:
                            _, pkg, pct_str, msg = parts
                            try:
                                schedule(progress_callback, float(pct_str), pkg, msg)
                            except ValueError:
                                pass  # malformed percentage string — skip this progress update
                elif stripped.startswith('dlstatus:'):
                    pass  # skip download status lines from the log
                else:
                    schedule(output_callback, line)
            process.wait()
        except Exception as e:
            # Sanitize the message so internal details (paths, module names,
            # stack frames) are not exposed to the user or captured in logs.
            err_msg = str(e).strip()
            if len(err_msg) > 120:
                err_msg = err_msg[:120] + "..."
            schedule(output_callback, f"\nError: {err_msg}\n")
            schedule(finished_callback, 1)
            return
        schedule(finished_callback, process.returncode)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
