#!/usr/bin/env python3
"""Validate generated selector data and its static asset references."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "docs" / "edgepack-installer-files"


def main() -> int:
    config = json.loads((WEB_DIR / "config.json").read_text(encoding="utf-8"))
    methods = {method["value"] for method in config["methods"]}
    if methods != {"tui", "installer-cli", "apt"}:
        raise ValueError(f"Unexpected installation methods: {sorted(methods)}")
    apt_method = next(method for method in config["methods"] if method["value"] == "apt")
    if apt_method["label"] != "APT":
        raise ValueError("APT method must use the concise 'APT' label")
    if "platforms" in config:
        raise ValueError("Platform choices must not be exposed by the web selector")
    if any("description" in operating_system for operating_system in config["operatingSystems"]):
        raise ValueError("Operating system choices must not include subtitles")

    headless = config.get("headlessSupport") or {}
    if headless.get("guideUrl") != "ubuntu-desktop-remove-display.html":
        raise ValueError("Headless guide URL must be relative to the embedding documentation page")
    headless_commands = [step["command"] for step in headless.get("steps", [])]
    headless_commands.append((headless.get("verification") or {}).get("command", ""))
    if any(not command.strip() for command in headless_commands):
        raise ValueError("Headless support must provide commands for every step and verification")
    guide = (ROOT / "docs" / "user-guide" / "ubuntu-desktop-remove-display.md").read_text(
        encoding="utf-8"
    )
    guide_command_lines = {
        line.strip()
        for block in re.findall(r"```bash\n(.*?)\n```", guide, flags=re.DOTALL)
        for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    for command in headless_commands:
        for line in command.splitlines():
            executable_line = line.strip()
            if (
                executable_line
                and not executable_line.startswith("#")
                and executable_line not in guide_command_lines
            ):
                raise ValueError(f"Headless selector command is missing from the guide: {executable_line}")

    seen = set()
    for installation in config["installations"]:
        selection = installation["selection"]
        if "platform" in selection:
            raise ValueError("Generated selections must not require a platform choice")
        identity = (
            selection["os"],
            selection["baseProfile"],
            tuple(sorted(selection["addons"])),
        )
        if identity in seen:
            raise ValueError(f"Duplicate installation selection: {identity}")
        seen.add(identity)

        commands = installation["commands"]
        if set(commands) != methods or any(not commands[method].strip() for method in methods):
            raise ValueError(f"Incomplete commands for selection: {identity}")
        apt_commands = commands["apt"]
        if "signed-by=/etc/apt/keyrings/" not in apt_commands:
            raise ValueError(f"APT repositories are not bound to a keyring: {identity}")
        if "apt-key" in apt_commands or "trusted=yes" in apt_commands:
            raise ValueError(f"Unsafe legacy APT configuration found: {identity}")
        if "edgepack-prerequisite" in apt_commands:
            raise ValueError(f"Conflicting prerequisite repository naming found: {identity}")
        if "intel-edge-npu" in installation["packages"]:
            for prerequisite_path in (
                "/etc/apt/keyrings/edgepack-prereq-0.gpg",
                "/etc/apt/sources.list.d/edgepack-prereq.list",
            ):
                if prerequisite_path not in apt_commands:
                    raise ValueError(
                        f"NPU selection does not reuse installer prerequisite paths: {identity}"
                    )
        if not installation["packages"]:
            raise ValueError(f"No packages resolved for selection: {identity}")
        for method in ("tui", "installer-cli"):
            installer_commands = commands[method]
            for required_gate in (
                "sha256sum -c edgepack-installer.sha256 &&\n",
                "chmod +x edgepack-installer &&\n",
            ):
                if required_gate not in installer_commands:
                    raise ValueError(
                        f"{method} does not gate installer execution for selection: {identity}"
                    )

    html = (WEB_DIR / "selector.html").read_text(encoding="utf-8")
    if "platform-options" in html:
        raise ValueError("Platform selection must not be shown in the web selector")
    for marker in ("toggle-headless", "headless-panel", "headless-steps"):
        if marker not in html:
            raise ValueError(f"Missing headless support UI marker: {marker}")
    for asset in ("style.css", "selector.js"):
        if asset not in html or not (WEB_DIR / asset).is_file():
            raise ValueError(f"Missing selector asset: {asset}")
    for class_name in ("app-wrap", "st-responsive-container", "st-section", "spark-button"):
        if class_name not in html:
            raise ValueError(f"Missing OEP selector class: {class_name}")

    embed = (ROOT / "docs" / "user-guide" / "index.md").read_text(encoding="utf-8")
    for marker in (
        "../../_static/edgepack-installer-files/iframe-resizer.js",
        "../../_static/edgepack-installer-files/selector.html",
        'id="installerFrame"',
    ):
        if marker not in embed:
            raise ValueError(f"Missing OEP iframe integration marker: {marker}")
    for fallback_link in (
        "[hosted installation selector](https://docs.openedgeplatform.intel.com/dev/OEP-articles/edge-pack/index.html)",
        "[Installation overview](get-started/index.md)",
        "[Install with the TUI](get-started/install-tui.md)",
        "[Install with the installer CLI](get-started/install-cli.md)",
        "[Install with APT](get-started/install-apt.md)",
        "[Convert Ubuntu Desktop to a headless system](ubuntu-desktop-remove-display.md)",
    ):
        if fallback_link not in embed:
            raise ValueError(f"Missing GitHub-visible installation fallback: {fallback_link}")
    if not (WEB_DIR / "iframe-resizer.js").is_file():
        raise ValueError("Missing same-origin iframe resizer")
    selector_script = (WEB_DIR / "selector.js").read_text(encoding="utf-8")
    if "new URL(support.guideUrl, window.parent.location.href)" not in selector_script:
        raise ValueError("Headless guide URL must resolve against the embedding page")

    print(f"Validated {len(seen)} installation selections.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())