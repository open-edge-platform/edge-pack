# tui/screens/step1.py — Step 1: profile selection and system information
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import textwrap

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen

from .base import BaseWizardScreen
from textual.widgets import Button, Footer, Header, RadioButton, RadioSet, Rule, Static


# ---------------------------------------------------------------------------
# Unsupported platform modal
# ---------------------------------------------------------------------------

class UnsupportedPlatformScreen(ModalScreen):
    """Modal shown when the host platform and/or OS is not supported.

    Dynamically composes the title and body depending on which check(s) failed:
      - platform only        → "Unsupported Platform"
      - OS only              → "Unsupported OS"
      - both                 → "Unsupported Platform and OS"
      - os_version_warning   → "OS Version Not Supported" (dot-release too old)
    """

    BINDINGS = [Binding("space", "exit_app", "", show=False)]

    def __init__(
        self,
        platform_supported: bool,
        os_supported: bool,
        cpu_model: str,
        os_name: str,
        platform_details: list[tuple[str, list[str]]],
        os_labels: list[str],
        os_version_warning: str = "",
        kernel_version_warning: str = "",
        kernel_version: str = "",
    ) -> None:
        super().__init__()
        self._platform_supported = platform_supported
        self._os_supported = os_supported
        self._cpu_model = cpu_model
        self._os_name = os_name
        self._platform_details = platform_details
        self._os_labels = os_labels
        self._os_version_warning = os_version_warning
        self._kernel_version_warning = kernel_version_warning
        self._kernel_version = kernel_version

    def _build_title(self) -> str:
        if not self._platform_supported and not self._os_supported:
            return "✗  Unsupported Platform and OS"
        if not self._platform_supported:
            return "✗  Unsupported Platform"
        if self._os_version_warning:
            return "✗  OS Version Not Supported"
        if self._kernel_version_warning:
            return "✗  Kernel Version Not Supported"
        return "✗  Unsupported OS"

    def _wrap_models(self, label: str, models: list[str], width: int = 54) -> str:
        """Bullet line for a platform; overflowing SKUs align under the first one."""
        if not models:
            return f"  \u2022 {label}"
        prefix = f"  \u2022 {label}: "
        return textwrap.fill(
            ", ".join(models),
            width=width,
            initial_indent=prefix,
            subsequent_indent=" " * len(prefix),
            break_on_hyphens=False,
        )

    def _build_message(self) -> str:
        parts: list[str] = []
        if self._os_version_warning:
            parts.append(
                f"Detected OS:   {self._os_name}\n\n"
                f"{self._os_version_warning}"
            )
        elif self._kernel_version_warning:
            parts.append(
                f"Detected Kernel:   {self._kernel_version}\n\n"
                f"{self._kernel_version_warning}"
            )
        else:
            if not self._platform_supported:
                platform_rows = []
                for label, models in self._platform_details:
                    platform_rows.append(self._wrap_models(label, models))
                platform_lines = "\n".join(platform_rows)
                parts.append(
                    f"Detected CPU:  {self._cpu_model}\n\n"
                    f"Supported platforms:\n{platform_lines}"
                )
            if not self._os_supported:
                os_lines = "\n".join(f"  \u2022 {lbl}" for lbl in self._os_labels)
                parts.append(
                    f"Detected OS:   {self._os_name}\n\n"
                    f"Supported operating systems:\n{os_lines}"
                )
        return "\n\n".join(parts) + "\n\nInstallation cannot proceed on this system."

    def compose(self) -> ComposeResult:
        with Vertical(id="error-dialog"):
            yield Static(self._build_title(), id="error-title", markup=False)
            yield Rule()
            yield Static(self._build_message(), id="error-msg")
            with Horizontal(id="error-actions"):
                yield Button("Exit Installer", variant="error", id="btn-exit-unsupported")

    def on_mount(self) -> None:
        self.set_timer(0.05, lambda: self.query_one("#btn-exit-unsupported", Button).focus())

    def action_exit_app(self) -> None:
        self.app.exit()

    @on(Button.Pressed, "#btn-exit-unsupported")
    def on_exit(self) -> None:
        self.app.exit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _radio_id(group: str, idx: int) -> str:
    """Return a safe widget ID for a RadioButton using a numeric index.

    Textual IDs must match [a-zA-Z][a-zA-Z0-9_-]* — using the raw YAML key
    (e.g. '1.0') would produce invalid IDs like 'rb_version_1.0'.
    The YAML key is stored in the widget's .name attribute instead.
    """
    return f"rb-{group}-{idx}"


def _radiset_id(group: str) -> str:
    return f"rs-{group}"


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------

class Step1Screen(BaseWizardScreen):
    """Step 1 — user selects platform, usage features, kernel variant, type and version."""

    BINDINGS = [
        Binding("f1",        "app.show_about",     "About",      show=True),
        Binding("tab",       "app.focus_next",     "Next field", show=True),
        Binding("shift+tab", "app.focus_previous", "Prev field", show=True),
        Binding("space",     "press_focused",      "Select",      show=True,  priority=True),
        Binding("left",      "focus_prev_button",  "",           show=False),
        Binding("right",     "focus_next_button",  "",           show=False),
        Binding("ctrl+q",    "app.quit",            "Quit",       show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        # Guard against re-entrant constraint updates triggered by programmatic
        # radio-button changes inside _apply_constraints().
        self._applying_constraints = False
        # Platform/OS warnings captured at mount; persisted so that the later
        # installed-package check can merge its results into the same panel.
        self._system_warnings: list[str] = []

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        app = self.app  # type: ignore[attr-defined]
        proc = app.processor

        yield Header()

        with Horizontal(id="step1-main"):
            # ── Left panel: system information ────────────────────────
            with Vertical(id="step1-left") as left:
                left.border_title = " ℹ  System Info "
                yield Static("Detected OS", classes="info-label")
                yield Static("—", id="info-os-value", classes="info-value")
                yield Rule()
                yield Static("Detected Platform", classes="info-label")
                yield Static("—", id="info-platform-value", classes="info-value")
                yield Static("—", id="info-cpu-sku-value", classes="info-cpu-sku")
                yield Rule()
                yield Static("Detected Kernel", classes="info-label")
                yield Static("—", id="info-kernel-value", classes="info-value")
                yield Rule()
                yield Static("⚠  Warnings", classes="info-label")
                yield Static("None", id="info-warnings-value", classes="info-value info-ok")

            # ── Right column ──────────────────────────────────────────
            with Vertical(id="step1-right"):
                # Top right: selection groups
                with ScrollableContainer(id="step1-scroll") as scroll:
                    scroll.border_title = " ◈  Configure Your Installation "

                    # ── Profile (single-select) ───────────────────────
                    with Vertical(classes="group-box", id="box-profile") as box:
                        box.border_title = " ○  Profile "
                        with RadioSet(id=_radiset_id("profile")):
                            for idx, (key, label, is_supported) in enumerate(proc.base_profiles_for_platform(app.detected_platform_key, app.detected_os_key)):
                                pre_selected = key == (app.selected_profile or "")
                                display = label if is_supported else f"[strike]{label}[/strike]"
                                yield RadioButton(display, name=key, id=_radio_id("profile", idx), value=pre_selected, disabled=not is_supported)

                    # ── EdgePack Version (hardcoded until YAML carries a version section) ──
                    with Vertical(classes="group-box", id="box-version") as box:
                        box.border_title = " ○  EdgePack Version "
                        with RadioSet(id=_radiset_id("version")):
                            yield RadioButton("v2026.2", name="2026.2", id=_radio_id("version", 0), value=True)

                # Bottom right: hardcoded notes
                with Vertical(id="step1-notes-box") as notes:
                    notes.border_title = " ✎  Notes "
                    yield Static(
                        "• Requires [bold]sudo / root[/bold] privileges to install packages.",
                        markup=True, classes="note-line",
                    )
                    yield Static(
                        "• An active [bold]internet connection[/bold] is required.",
                        markup=True, classes="note-line",
                    )
                    yield Static(
                        "• Packages are fetched from [bold]Intel Edge[/bold] repositories.",
                        markup=True, classes="note-line",
                    )
                    yield Static(
                        "• The complete list of installed packages will be recorded in the [bold]log file[/bold] at the end of installation.",
                        markup=True, classes="note-line",
                    )

                with Horizontal(id="step1-actions"):
                    yield Button("Continue →", variant="primary", id="btn-continue")

        yield Footer()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_press_focused(self) -> None:
        """Activate the focused widget: press Buttons, toggle RadioSet cursor, toggle RadioButtons."""
        focused = self.focused
        if focused is None or focused.disabled:
            return
        if isinstance(focused, Button):
            focused.press()
        elif isinstance(focused, RadioSet):
            focused.action_toggle_button()
        elif isinstance(focused, RadioButton):
            focused.toggle()

    def action_focus_prev_button(self) -> None:
        """Move focus to the previous enabled Button (left arrow)."""
        self._move_button_focus(-1)

    def action_focus_next_button(self) -> None:
        """Move focus to the next enabled Button (right arrow)."""
        self._move_button_focus(1)

    def _move_button_focus(self, delta: int) -> None:
        focused = self.focused
        if not isinstance(focused, Button):
            return
        buttons = [b for b in self.query(Button) if not b.disabled]
        idx = next((i for i, b in enumerate(buttons) if b is focused), -1)
        target = idx + delta
        if 0 <= target < len(buttons):
            buttons[target].focus()

    # ------------------------------------------------------------------
    # Mount — apply auto-detections and initial constraints
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        app = self.app  # type: ignore[attr-defined]

        # Populate left panel — Detected OS
        os_entry = app.detected_os_entry or {}
        os_name = os_entry.get("display_name") or app.detected_os_name
        self.query_one("#info-os-value", Static).update(os_name)

        # Populate left panel — Detected Platform + CPU SKU
        platform_entry = app.detected_platform_entry or {}
        platform_display = platform_entry.get("display_name")
        platform_widget = self.query_one("#info-platform-value", Static)
        if platform_display:
            platform_widget.update(platform_display)
            platform_widget.remove_class("info-unrecognized")
        else:
            platform_widget.update("Unrecognized Platform")
            platform_widget.add_class("info-unrecognized")
        cpu_sku_widget = self.query_one("#info-cpu-sku-value", Static)
        cpu_sku_widget.update(app.detected_cpu_model or "—")

        # Populate left panel — Detected Kernel
        self.query_one("#info-kernel-value", Static).update(app.detected_kernel_release or "—")

        # Populate left panel — Warnings (platform / OS checks)
        if not app.os_supported:
            os_names = ", ".join(app.processor.supported_os_labels())
            self._system_warnings.append(f"Unsupported OS — installer requires {os_names}")
        if not app.platform_supported:
            platform_names = ", ".join(app.processor.supported_platform_labels())
            self._system_warnings.append(f"Unsupported platform — requires {platform_names}")
        if not app.os_version_met and app.os_version_warning:
            self._system_warnings.append(app.os_version_warning)
        if not app.kernel_version_met and app.kernel_version_warning:
            self._system_warnings.append(app.kernel_version_warning)
        self._refresh_warnings_panel([])

        self._apply_constraints()
        self._save_to_app()
        # The ScrollableContainer is focusable by default in Textual, which inserts
        # an unwanted extra Tab stop between the buttons and the first RadioSet.
        # Disable it so the cycle is: section1 → section2 → button → section1.
        self.query_one("#step1-scroll", ScrollableContainer).can_focus = False
        # Set keyboard focus to the profile group so Tab works without a mouse click.
        self.set_timer(0.05, lambda: self.query_one("#rs-profile", RadioSet).focus())
        # Show warnings for any base-profile packages that are already installed.
        # (May be a no-op if the background scan hasn't finished yet; the scan
        #  completion handler will call this again when results arrive.)
        self._update_installed_warnings()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(RadioSet.Changed)
    def on_radio_changed(self, event: RadioSet.Changed) -> None:
        if self._applying_constraints:
            return
        self._apply_constraints()
        self._save_to_app()

    @on(Button.Pressed, "#btn-continue")
    def on_continue(self) -> None:
        app = self.app  # type: ignore[attr-defined]
        if not app.platform_supported or not app.os_supported:
            self.app.push_screen(UnsupportedPlatformScreen(
                platform_supported=app.platform_supported,
                os_supported=app.os_supported,
                cpu_model=app.detected_cpu_model,
                os_name=app.detected_os_name,
                platform_details=app.processor.supported_platform_details(),
                os_labels=app.processor.supported_os_labels(),
            ))
            return
        if not app.os_version_met:
            self.app.push_screen(UnsupportedPlatformScreen(
                platform_supported=True,
                os_supported=True,
                cpu_model=app.detected_cpu_model,
                os_name=app.detected_os_name,
                platform_details=app.processor.supported_platform_details(),
                os_labels=app.processor.supported_os_labels(),
                os_version_warning=app.os_version_warning,
            ))
            return
        if not app.kernel_version_met:
            self.app.push_screen(UnsupportedPlatformScreen(
                platform_supported=True,
                os_supported=True,
                cpu_model=app.detected_cpu_model,
                os_name=app.detected_os_name,
                platform_details=app.processor.supported_platform_details(),
                os_labels=app.processor.supported_os_labels(),
                kernel_version_warning=app.kernel_version_warning,
                kernel_version=app.detected_kernel_version,
            ))
            return
        self._save_to_app()
        from .step2 import Step2Screen
        self.app.push_screen(Step2Screen())

    # ------------------------------------------------------------------
    # Constraint logic  (mirrors GUI's _do_apply_constraints)
    # ------------------------------------------------------------------

    def _apply_constraints(self) -> None:
        """Re-evaluate which buttons are enabled given current selections."""
        if self._applying_constraints:
            return
        self._applying_constraints = True
        try:
            self._do_apply_constraints()
        finally:
            self._applying_constraints = False

    def _do_apply_constraints(self) -> None:
        app = self.app  # type: ignore[attr-defined]
        proc = app.processor

        # Profile — only allow profiles supported on the detected platform and OS.
        # Unsupported ones are already rendered as disabled/struck-out in compose.
        self._set_radio_allowed("profile", {k for k, _, supported in proc.base_profiles_for_platform(app.detected_platform_key, app.detected_os_key) if supported})

    # ------------------------------------------------------------------
    # Widget helpers
    # ------------------------------------------------------------------

    def _set_radio_allowed(self, group: str, allowed_keys: set[str]) -> None:
        """Mirror GTK's _set_group_allowed: disable first, then migrate selection.

        GTK order (the correct one):
          1. set_sensitive() on ALL buttons (including the currently active one)
          2. if no active+sensitive button remains → deactivate the stale one, activate first sensitive

        Textual equivalent:
          1. btn.disabled on all buttons
          2. if pressed button is now disabled (or None) → silently deselect it via
             disable_messages so RadioSet's force-back-to-True guard never fires,
             then select the first enabled button
        """
        rs = self.query_one(f"#{_radiset_id(group)}", RadioSet)

        # Step 1 — set disabled on every button (mirrors GTK set_sensitive).
        for btn in rs.query(RadioButton):
            btn.disabled = (btn.name or "") not in allowed_keys

        # Step 2 — check if the current selection is still valid.
        pressed = rs.pressed_button
        if pressed is None or pressed.disabled:
            # Silently deselect the stale button.  We block RadioButton.Changed
            # while setting value=False so RadioSet's else-branch ("force back to
            # True") never fires and there is no bounce cycle.
            if pressed is not None:
                pressed.disable_messages(RadioButton.Changed)
                pressed.value = False
                rs._pressed_button = None
                pressed.enable_messages(RadioButton.Changed)

            # Activate the first still-enabled button.
            for btn in rs.query(RadioButton):
                if not btn.disabled:
                    btn.value = True
                    break

    def _activate_radio(self, group: str, key: str) -> None:
        """Programmatically select a specific radio button by YAML key."""
        rs = self.query_one(f"#{_radiset_id(group)}", RadioSet)
        for btn in rs.query(RadioButton):
            if btn.name == key:
                btn.value = True
                return

    def _selected_radio(self, group: str) -> str | None:
        """Return the YAML key of the pressed button in *group*, or None."""
        rs = self.query_one(f"#{_radiset_id(group)}", RadioSet)
        pressed = rs.pressed_button
        if pressed is None:
            return None
        return pressed.name

    # ------------------------------------------------------------------
    # Persist selections to App state
    # ------------------------------------------------------------------

    def _save_to_app(self) -> None:
        """Write current UI selections into app-level shared state."""
        app = self.app  # type: ignore[attr-defined]
        app.selected_profile = self._selected_radio("profile")
        app.selected_version = self._selected_radio("version") or "1.0"

    # ------------------------------------------------------------------
    # Warnings panel helpers
    # ------------------------------------------------------------------

    def _refresh_warnings_panel(self, extra: list[str]) -> None:
        """Rebuild the left-panel Warnings section from system + extra warnings."""
        all_warnings = self._system_warnings + extra
        warn_widget = self.query_one("#info-warnings-value", Static)
        if all_warnings:
            warn_widget.update("\n".join(f"• {w}" for w in all_warnings))
            warn_widget.remove_class("info-ok")
            warn_widget.add_class("info-warn")
        else:
            warn_widget.update("None")
            warn_widget.remove_class("info-warn")
            warn_widget.add_class("info-ok")

    def _update_installed_warnings(self) -> None:
        """Merge already-installed profile warnings into the left-panel Warnings box.

        Called once on mount (scan may not be done yet) and again when the
        background package scan completes via app._refresh_installed_warnings().
        """
        app = self.app  # type: ignore[attr-defined]
        proc = app.processor
        installed = getattr(app, "installed_versions", {})

        installed_warnings: list[str] = []
        for key, entry in proc.section("base-profiles").items():
            entry = entry or {}
            meta_pkgs = proc.profile_packages(key, app.detected_platform_key, app.detected_os_key)
            installed_pkgs = [p for p in meta_pkgs if p in installed]
            if installed_pkgs:
                pkg_name = installed_pkgs[0]
                ver = installed[pkg_name]
                display_name = entry.get("display_name") or key
                installed_warnings.append(
                    f"{display_name} is already installed (v{ver})"
                )

        self._refresh_warnings_panel(installed_warnings)
