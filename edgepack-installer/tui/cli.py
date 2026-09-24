# tui/cli.py — non-interactive CLI install path (no Textual UI)
#
# Lets automated/validation flows install a base profile (+ optional
# add-on profiles) directly from the command line, without stepping through
# the TUI wizard, e.g.:
#
#     sudo ./edgepack-installer install base-standard npu
#     ./edgepack-installer list
#
# Reuses the same Processor/package_logic/install_logic building blocks as
# the TUI so both paths resolve packages and prerequisites identically.
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
import re
import sys
import threading

from edgepack_shared.host import (
    host_cpu_model, read_os_release, host_os_dot_version,
    host_kernel_release, host_kernel_dot_version, host_kernel_is_ubuntu,
)
from edgepack_shared.install_logic import run_install
from edgepack_shared.processor import Processor

from .package_logic import required_prerequisites


def _make_cli_logger() -> logging.Logger:
    """Return a logger that writes to both the TUI log and stdout."""
    from edgepack_shared.log import ep_logger as _ep_log
    _log = _ep_log(name="cli_install", log_file="/var/log/edgepack/edgepack_tui.log")
    return _log.get_logger()


logger: logging.Logger | None = None  # initialised on first call to install_command


def _dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _check_host_requirements(processor: Processor) -> dict:
    """Run the same platform/OS/kernel checks the TUI performs at startup (app.py __init__).

    Returns detected platform/os key+entry plus an 'issues' list of
    human-readable failure reasons — empty when the host qualifies.
    """
    cpu_model = host_cpu_model()
    platform_key, platform_entry = processor.detect_platform(cpu_model)
    os_info = read_os_release()
    os_key, os_entry = processor.detect_os(os_info)

    issues: list[str] = []

    if platform_key is None:
        supported = ", ".join(processor.supported_platform_labels())
        issues.append(f"Unsupported platform — detected CPU '{cpu_model or 'Unknown'}' (supported: {supported})")
    if os_key is None:
        supported = ", ".join(processor.supported_os_labels())
        os_name = (
            os_info.get("PRETTY_NAME")
            or f"{os_info.get('NAME', '')} {os_info.get('VERSION_ID', '')}".strip()
            or "Unknown"
        )
        issues.append(f"Unsupported OS — detected '{os_name}' (supported: {supported})")

    if os_key:
        issues.extend(processor.os_version_issues(os_key, host_os_dot_version(os_info)))

    kernel_dot_version = host_kernel_dot_version(host_kernel_release())
    issues.extend(processor.kernel_version_issues(kernel_dot_version, os_key, host_kernel_is_ubuntu()))

    return {
        "platform_key": platform_key,
        "platform_entry": platform_entry,
        "os_key": os_key,
        "os_entry": os_entry,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# 'list' command
# ---------------------------------------------------------------------------

def list_command(processor: Processor) -> None:
    """Print every base profile and add-on profile key defined in the template."""
    print("Base profiles (choose exactly one):\n")
    base_profiles = processor.section("base-profiles")
    key_width = max((len(k) for k in base_profiles), default=0)
    for key, entry in base_profiles.items():
        entry = entry or {}
        display = entry.get("display_name") or key
        platforms = ", ".join(entry.get("supported_platforms") or []) or "any"
        os_variants = ", ".join(entry.get("supported_os_variants") or []) or "any"
        print(f"  {key.ljust(key_width)}  {display}")
        print(f"  {' ' * key_width}  (platforms: {platforms} | os: {os_variants})")

    print("\nAdd-on profiles (optional, zero or more):\n")
    addon_profiles = processor.section("profiles")
    key_width = max((len(k) for k in addon_profiles), default=0)
    for key, entry in addon_profiles.items():
        entry = entry or {}
        display = entry.get("display_name") or key
        requires = ", ".join(entry.get("base-profiles") or []) or "any base profile"
        print(f"  {key.ljust(key_width)}  {display}")
        print(f"  {' ' * key_width}  (requires base: {requires})")

    print("\nUsage:")
    print("  edgepack-installer install <base-profile> [addon ...]")
    print("  e.g. sudo edgepack-installer install base-standard npu")


# ---------------------------------------------------------------------------
# 'install' command
# ---------------------------------------------------------------------------

# Maximum allowed length for profile keys passed on the CLI. Prevents
# oversized or malformed arguments from reaching downstream processing.
_MAX_PROFILE_KEY_LEN = 128


def _validate_profile_key(key: str, label: str) -> int | None:
    """Return an exit code (non-zero) if *key* is invalid, else None."""
    if not key:
        return 2
    if len(key) > _MAX_PROFILE_KEY_LEN:
        print(
            f"error: {label} exceeds maximum length of {_MAX_PROFILE_KEY_LEN} characters",
            file=sys.stderr,
        )
        logger.warning("Validation failure (%s): argument exceeds maximum length of %d chars", label, _MAX_PROFILE_KEY_LEN)  # type: ignore[reportPossiblyUnboundVariable]
        return 2
    # Reject characters that could be interpreted as shell metacharacters or
    # path separators, since keys are embedded in shell commands.
    if re.search(r'[^a-zA-Z0-9_\-]', key):
        print(
            f"error: {label} contains invalid characters (only a-z, A-Z, 0-9, _, - allowed)",
            file=sys.stderr,
        )
        logger.warning("Validation failure (%s): argument contains disallowed characters", label)  # type: ignore[reportPossiblyUnboundVariable]
        return 2
    return None


def install_command(args) -> int:
    """Resolve, validate, and install *args.base_profile* + *args.addons*.

    Mirrors the checks enforced by the TUI (host requirements at startup,
    then the compatibility rules behind Step 1/2's disabled radios) so the
    CLI can be trusted as a validation gate. Runs unattended — no
    confirmation prompt — since this path exists for scripted validation.
    Returns the process exit code.
    """
    global logger
    logger = _make_cli_logger()

    processor = Processor.load()

    base_profiles = processor.section("base-profiles")
    addon_profiles = processor.section("profiles")

    err = _validate_profile_key(args.base_profile, "base profile key")
    if err:
        return err

    for addon in args.addons:
        err = _validate_profile_key(addon, "add-on profile key")
        if err:
            return err

    if args.base_profile not in base_profiles:
        print(f"error: unknown base profile '{args.base_profile}'", file=sys.stderr)
        print(f"       valid base profiles: {', '.join(sorted(base_profiles)) or '(none)'}", file=sys.stderr)
        print("       run 'edgepack-installer list' to see all options", file=sys.stderr)
        logger.warning("Validation failure: unknown base profile '%s'", args.base_profile)
        return 2

    unknown_addons = [a for a in args.addons if a not in addon_profiles]
    if unknown_addons:
        print(f"error: unknown add-on profile(s): {', '.join(unknown_addons)}", file=sys.stderr)
        print(f"       valid add-on profiles: {', '.join(sorted(addon_profiles)) or '(none)'}", file=sys.stderr)
        print("       run 'edgepack-installer list' to see all options", file=sys.stderr)
        logger.warning("Validation failure: unknown add-on profile(s): %s", ", ".join(unknown_addons))
        return 2

    if os.geteuid() != 0:
        print(
            "error: installing packages requires root privileges — "
            "re-run with sudo, e.g. 'sudo edgepack-installer install ...'",
            file=sys.stderr,
        )
        return 1

    # ---- Host requirements (fatal, mirrors UnsupportedPlatformScreen in the TUI) ----
    print("Checking system requirements...")
    host = _check_host_requirements(processor)
    if host["issues"]:
        print("error: this machine does not meet the installation requirements:", file=sys.stderr)
        for issue in host["issues"]:
            print(f"       - {issue}", file=sys.stderr)
        logger.warning("Host does not meet installation requirements: %s", "; ".join(host["issues"]))
        return 4
    print("System requirements: OK")

    platform_key, platform_entry = host["platform_key"], host["platform_entry"]
    os_key, os_entry = host["os_key"], host["os_entry"]
    platform_display = (platform_entry or {}).get("display_name") or platform_key
    os_display = (os_entry or {}).get("display_name") or os_key

    # ---- Base profile compatibility (fatal, mirrors disabled radio in Step 1) ----
    base_rows = {
        key: (display, supported)
        for key, display, supported in processor.base_profiles_for_platform(platform_key, os_key)
    }
    base_display, base_supported = base_rows.get(args.base_profile, (args.base_profile, False))
    if not base_supported:
        entry = base_profiles.get(args.base_profile) or {}
        supported_platforms = ", ".join(entry.get("supported_platforms") or []) or "any"
        supported_os = ", ".join(entry.get("supported_os_variants") or []) or "any"
        print(
            f"error: base profile '{args.base_profile}' is not supported on this host "
            f"(detected platform: {platform_display}, os: {os_display})",
            file=sys.stderr,
        )
        print(f"       supported platforms: {supported_platforms} | supported os: {supported_os}", file=sys.stderr)
        logger.warning("Base profile '%s' is incompatible with detected host", args.base_profile)
        return 3

    # ---- Add-on compatibility (fatal, mirrors filtered add-on list in Step 2) ----
    compatible_addons = {key for key, _ in processor.compatible_profiles(args.base_profile, platform_key, os_key)}
    incompatible = [a for a in args.addons if a not in compatible_addons]
    if incompatible:
        for addon_key in incompatible:
            entry = addon_profiles.get(addon_key) or {}
            allowed_bases = entry.get("base-profiles") or []
            reasons = processor.addon_compatibility_issues(addon_key, platform_key, os_key)
            if allowed_bases and args.base_profile not in allowed_bases:
                reasons.insert(
                    0,
                    f"'{addon_key}' requires base profile {allowed_bases} "
                    f"(selected: '{args.base_profile}')",
                )
            print(f"error: add-on profile '{addon_key}' is not compatible with this selection:", file=sys.stderr)
            for reason in reasons or ["incompatible with detected host"]:
                print(f"       - {reason}", file=sys.stderr)
            logger.warning("Add-on '%s' is not compatible with the selected profile/host", addon_key)
        return 3

    # ---- Resolve package list ----
    packages = list(processor.profile_packages(args.base_profile, platform_key, os_key))
    for addon_key in args.addons:
        packages.extend(processor.addon_packages(addon_key, platform_key, os_key))
    packages = _dedupe(packages)

    if not packages:
        print("error: resolved package list is empty — nothing to install", file=sys.stderr)
        return 3

    prerequisites = required_prerequisites(processor, [args.base_profile, *args.addons], os_key)
    repos = list((os_entry or {}).get("repositories", {}).values())

    hidden_packages: list[str] = []
    for _key in [args.base_profile, *args.addons]:
        hidden_packages.extend(processor.hidden_os_packages(_key, platform_key, os_key))

    # ---- Summary ----
    print(f"\nBase profile : {base_display} ({args.base_profile})")
    print(f"Add-ons      : {', '.join(args.addons) if args.addons else '(none)'}")
    print(f"Platform     : {platform_display}")
    print(f"OS           : {os_display}")
    print("Packages to install:")
    for name in packages:
        print(f"  - {name}")
    if prerequisites.get("packages"):
        print("Prerequisite packages:")
        for name in prerequisites["packages"]:
            print(f"  - {name}")

    # No confirmation prompt — this path is unattended for scripted validation.
    print("\nRequirements met — proceeding with installation...\n")
    code = _run_install_blocking(packages, repos, prerequisites, hidden_packages)

    if code == 0:
        print("\n\u2714 Installation completed successfully.")
        print("  A system restart is recommended to apply all changes.")
    else:
        print(f"\n\u2718 Installation failed (exit code {code}). See output above for details.", file=sys.stderr)
    return code


def _run_install_blocking(packages: list[str], repos: list[dict], prerequisites: dict,
                          force_packages: list[str] | None = None) -> int:
    """Run edgepack_shared.install_logic.run_install synchronously and stream its output."""
    done = threading.Event()
    result = {"code": 1}

    def _on_output(line: str) -> None:
        sys.stdout.write(line if line.endswith("\n") else line + "\n")
        sys.stdout.flush()

    def _on_finished(code: int = 0) -> None:
        result["code"] = code
        done.set()

    run_install(
        [(name, "") for name in packages],
        repos,
        output_callback=_on_output,
        finished_callback=_on_finished,
        sudo_password=None,
        prerequisites=prerequisites,
        force_packages=force_packages,
    )
    done.wait()
    return result["code"]
