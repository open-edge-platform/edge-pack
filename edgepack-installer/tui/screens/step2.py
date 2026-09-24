# tui/screens/step2.py — Step 2: profile review and optional add-on selection
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.content import Content
from textual.message import Message
from textual.style import Style

from .base import BaseWizardScreen, _ButtonNavMixin
from textual.widgets import Button, Checkbox, Footer, Header, Rule, Static

from ..package_logic import build_pkg_entries, collect_selected_packages


# ---------------------------------------------------------------------------
# AddonCheckbox — posts Focused message so the Screen updates the About panel
# ---------------------------------------------------------------------------

class AddonCheckbox(Checkbox):
    """Checkbox for an optional add-on profile.

    Posts ``AddonCheckbox.Focused`` when it receives focus so the parent
    Screen can update the About description panel without polling.
    """

    BUTTON_INNER = " ✔ "
    BUTTON_LEFT  = "["
    BUTTON_RIGHT = "]"

    # Register a separate component class for the bracket characters so their
    # colour can be controlled independently from the inner tick via CSS.
    COMPONENT_CLASSES = Checkbox.COMPONENT_CLASSES | {"toggle--bracket"}

    @property
    def _button(self) -> Content:
        """Render [ ✔ ] with brackets and inner tick styled independently.

        The default ToggleButton renderer derives the bracket foreground from
        `toggle--button`'s *background*, which forces both the bracket colour
        and the inner fill to share the same value.  This override reads the
        bracket colour from the separate ``toggle--bracket`` component class so
        the brackets stay visible while the inner area remains transparent.
        """
        inner_style   = self.get_visual_style("toggle--button")
        bracket_style = self.get_visual_style("toggle--bracket")
        outer_bg      = self.background_colors[1]

        # Brackets: always use toggle--bracket foreground on the widget background.
        br    = Style(foreground=bracket_style.foreground, background=outer_bg)
        # Inner tick: toggle--button foreground (invisible or $success) on the
        # same dark widget background — no coloured fill behind the character.
        inner = Style(foreground=inner_style.foreground, background=outer_bg,
                      bold=inner_style.bold)

        return Content.assemble(
            (self.BUTTON_LEFT,  br),
            (self.BUTTON_INNER, inner),
            (self.BUTTON_RIGHT, br),
        )

    class Focused(Message):
        """Posted when this checkbox gains keyboard or mouse focus."""

        def __init__(self, profile_key: str, description: str) -> None:
            super().__init__()
            self.profile_key = profile_key
            self.description = description

    def __init__(
        self,
        label: str,
        *,
        profile_key: str,
        description: str,
        value: bool = False,
        id: str | None = None,
    ) -> None:
        super().__init__(label, value=value, id=id)
        self._profile_key = profile_key
        self._description = description

    def on_focus(self) -> None:
        self.post_message(self.Focused(self._profile_key, self._description))


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------

class Step2Screen(_ButtonNavMixin, BaseWizardScreen):
    """Step 2 — base profile summary and optional add-on selection."""

    DEFAULT_ABOUT = "Use arrow keys to navigate, Space to toggle add-ons."

    CATEGORY_ORDER = ["Intel Technologies", "Application/Tools"]

    BINDINGS = [
        Binding("f1",        "app.show_about",     "About", show=True),
        Binding("tab",       "focus_next_smart",   "Next", show=True),
        Binding("shift+tab", "app.focus_previous", "Prev", show=True),
        Binding("space",     "press_focused",      "Select", show=True,  priority=True),
        Binding("left",      "focus_prev_button",  "",     show=False),
        Binding("right",     "focus_next_button",  "",     show=False),
        Binding("ctrl+q",    "app.quit",            "Quit", show=True),
    ]

    # ------------------------------------------------------------------
    # Compose — static skeleton; dynamic content filled in on_mount
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical(id="step2-outer"):
            yield Static("Step 2 of 4 — Review Packages", id="step2-title")
            yield Rule()

            # Locked base-profile packages
            with Vertical(id="s2-base-box"):
                pass  # populated in on_mount

            # Optional add-ons scroll list
            yield Static("Optional add-ons", id="s2-addons-label")
            with ScrollableContainer(id="s2-addons-scroll"):
                yield Vertical(id="s2-addons-rows")

            # Description panel — updates as add-on checkboxes receive focus
            with Vertical(id="s2-about-box"):
                yield Static(self.DEFAULT_ABOUT, id="s2-about-text")

            # Running package summary
            yield Static("", id="s2-selected-summary", markup=True)

            yield Rule()

            with Horizontal(id="step2-actions"):
                yield Button("← Back", id="btn-back")
                yield Button("Continue →", variant="primary", id="btn-continue")

        yield Footer()

    # ------------------------------------------------------------------
    # Mount — populate dynamic sections
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        app = self.app  # type: ignore[attr-defined]
        proc = app.processor
        profile_key = app.selected_profile or ""
        platform_key = app.detected_platform_key
        os_key = app.detected_os_key

        # Filter add-ons that are compatible with the selected base profile, platform, and OS.
        compatible_keys = {k for k, _ in proc.compatible_profiles(profile_key, platform_key, os_key)}

        # Drop any previously-selected add-ons that no longer apply
        # (e.g. user went back and changed base profile).
        app.selected_addon_profiles = [
            k for k in app.selected_addon_profiles if k in compatible_keys
        ]

        # Build pkg_entries (preserving any surviving add-ons from a previous visit)
        app.pkg_entries = build_pkg_entries(
            proc, profile_key, app.selected_addon_profiles, platform_key, os_key
        )

        # ── Base profile box ──
        base_entry = proc.entry("base-profiles", profile_key)
        base_display = base_entry.get("display_name") or profile_key
        base_description = base_entry.get("description") or ""
        base_pkgs = proc.profile_packages(profile_key, platform_key, os_key)
        base_box = self.query_one("#s2-base-box", Vertical)
        base_box.border_title = f"Base Profile: {base_display}"
        for pkg in base_pkgs:
            base_box.mount(Static(f"  ✓  {pkg}", classes="base-pkg-row"))
        if base_description:
            base_box.mount(Static(f"     {base_description}", id="s2-base-description"))

        # ── Optional add-on cards, grouped by category ──
        rows = self.query_one("#s2-addons-rows", Vertical)
        all_profiles = proc.compatible_profiles(profile_key, platform_key, os_key)
        if not all_profiles:
            rows.mount(Static(
                "  No optional add-ons available for this profile.",
                classes="addon-none",
            ))
        else:
            # Group profiles by category, preserving first-seen order for any
            # category not already in CATEGORY_ORDER.
            grouped: dict[str, list[tuple[str, dict]]] = {}
            for key, entry in all_profiles:
                category = (entry or {}).get("category") or "Other"
                grouped.setdefault(category, []).append((key, entry))

            ordered_categories = [c for c in self.CATEGORY_ORDER if c in grouped]
            ordered_categories += [c for c in grouped if c not in ordered_categories]

            first_header = True
            for category in ordered_categories:
                header_classes = "addon-category-header"
                if first_header:
                    header_classes += " addon-category-header-first"
                rows.mount(Static(category, classes=header_classes))
                first_header = False

                for key, entry in grouped[category]:
                    entry = entry or {}
                    display = entry.get("display_name") or key
                    description = entry.get("description") or ""
                    packages = proc.addon_packages(key, platform_key, os_key)
                    pkg_str = "  ".join(packages) if packages else "(none)"
                    pre_checked = key in app.selected_addon_profiles

                    card = Vertical(classes="addon-card", id=f"addon-card-{key}")
                    rows.mount(card)
                    card.mount(AddonCheckbox(
                        display,
                        profile_key=key,
                        description=description,
                        value=pre_checked,
                        id=f"addon-cb-{key}",
                    ))
                    card.mount(Static(f"  Packages: {pkg_str}", classes="addon-packages"))

        # ── Description box border title ──
        self.query_one("#s2-about-box", Vertical).border_title = "Description"

        self._refresh_summary()

        # Prevent the ScrollableContainer from grabbing an extra Tab stop.
        self.query_one("#s2-addons-scroll", ScrollableContainer).can_focus = False

        # Default focus: first add-on checkbox, or Continue if none available
        def _set_initial_focus() -> None:
            checkboxes = list(self.query(AddonCheckbox))
            if checkboxes:
                checkboxes[0].focus()
            else:
                self.query_one("#btn-continue", Button).focus()

        self.set_timer(0.05, _set_initial_focus)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_press_focused(self) -> None:
        """Activate the focused widget: press Buttons, toggle Checkboxes."""
        focused = self.focused
        if focused is None or focused.disabled:
            return
        if isinstance(focused, Button):
            focused.press()
        elif isinstance(focused, Checkbox):
            focused.toggle()
            # After toggling, advance to the next add-on checkbox so the user
            # can quickly scan and tick items.  At the end of the list jump
            # straight to the Continue button — the natural next action.
            checkboxes = list(self.query(AddonCheckbox))
            idx = next((i for i, c in enumerate(checkboxes) if c is focused), -1)
            if 0 <= idx + 1 < len(checkboxes):
                checkboxes[idx + 1].focus()
            else:
                self.query_one("#btn-continue", Button).focus()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(AddonCheckbox.Focused)
    def on_addon_focused(self, event: AddonCheckbox.Focused) -> None:
        """Update the About panel when an add-on checkbox gains focus."""
        self.query_one("#s2-about-text", Static).update(
            event.description or self.DEFAULT_ABOUT
        )

    @on(Checkbox.Changed)
    def on_addon_toggled(self, event: Checkbox.Changed) -> None:
        """Add/remove an optional profile and rebuild pkg_entries."""
        cb_id = event.checkbox.id or ""
        if not cb_id.startswith("addon-cb-"):
            return

        profile_key = cb_id[len("addon-cb-"):]
        app = self.app  # type: ignore[attr-defined]
        addons: list[str] = list(app.selected_addon_profiles)
        if event.value and profile_key not in addons:
            addons.append(profile_key)
        elif not event.value and profile_key in addons:
            addons.remove(profile_key)

        app.selected_addon_profiles = addons
        app.pkg_entries = build_pkg_entries(
            app.processor, app.selected_profile, addons, app.detected_platform_key, app.detected_os_key
        )
        self._refresh_summary()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-continue")
    def on_continue(self) -> None:
        from .step3 import Step3Screen
        self.app.push_screen(Step3Screen())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_summary(self) -> None:
        packages = collect_selected_packages(self.app.pkg_entries)  # type: ignore[attr-defined]
        pkg_str = "  ".join(packages.keys()) if packages else "(none)"
        self.query_one("#s2-selected-summary", Static).update(
            f"[bold]Selected:[/bold]  {pkg_str}"
        )

