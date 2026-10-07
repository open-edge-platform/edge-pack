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

from dataclasses import asdict
import json
import os
import sys
import threading
from typing import TextIO

from edgepack_shared.host import (
    host_cpu_model, read_os_release, host_os_dot_version,
    host_kernel_release, host_kernel_dot_version, host_kernel_is_ubuntu,
)
from edgepack_shared.install_logic import run_install
from edgepack_shared.processor import Processor
from edgepack_shared.user_config import ConfigError, load_selection, normalize_selection

from .__version__ import __version__
from .package_logic import required_prerequisites


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

def list_command(processor: Processor, json_output: bool = False) -> None:
    """Print every base profile and add-on profile key defined in the template."""
    if json_output:
        result = command_result("list")
        result["profiles"] = {
            "base_profiles": processor.section("base-profiles"),
            "addons": processor.section("profiles"),
        }
        print(json.dumps(result))
        return
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

def command_result(command: str, dry_run: bool = False) -> dict:
    return {
        "schema_version": 1, "command": command, "status": "ok",
        "dry_run": dry_run, "exit_code": 0, "selection": None,
        "host": None, "plan": None, "errors": [], "restart_recommended": False,
    }


def report_error(result: dict, json_output: bool, code: int, error_code: str,
                 message: str, field: str | None = None) -> int:
    error = {"code": error_code, "message": message}
    if field is not None:
        error["field"] = field
    result.update(status="error", exit_code=code, errors=[error])
    if json_output:
        print(json.dumps(result))
    else:
        print(f"error: {message}", file=sys.stderr)
    return code


def _print_plan(result: dict) -> None:
    selection, host, plan = result["selection"], result["host"], result["plan"]
    print(f"Base profile : {selection['base_profile']}")
    print(f"EdgePack     : {selection['edgepack_version']}")
    print(f"Add-ons      : {', '.join(selection['addons']) or '(none)'}")
    print(f"Platform     : {host['platform_key']}")
    print(f"OS           : {host['os_key']}")
    for label, packages in (
        ("Packages", plan["packages"]),
        ("Additional OS packages", plan["additional_os_packages"]),
        ("Prerequisite packages", plan["prerequisites"]["packages"]),
    ):
        print(f"{label}:")
        for name in packages:
            print(f"  - {name}")
        if not packages:
            print("  (none)")
    for label, repos in (
        ("Prerequisite repositories", plan["prerequisites"]["repositories"]),
        ("Repositories", plan["repositories"]),
    ):
        print(f"{label}:")
        for repo in repos:
            print(f"  - {repo.get('repository_url', '')} {repo.get('repository_dist', '')}")
        if not repos:
            print("  (none)")


def install_command(args) -> int:
    """Validate a YAML or positional selection, preview it, or install unattended."""
    dry_run = getattr(args, "dry_run", False)
    json_output = getattr(args, "json", False)
    result = command_result("install", dry_run)

    def fail(code, error_code, message, field=None):
        return report_error(result, json_output, code, error_code, message, field)

    try:
        config = getattr(args, "config", None)
        if config is not None:
            if args.base_profile is not None or args.addons:
                raise ConfigError("Use either --config or positional profiles, not both")
            selection = load_selection(config, __version__)
        else:
            selection = normalize_selection(
                {"base_profile": args.base_profile, "addons": args.addons}, __version__
            )
    except ConfigError as error:
        return fail(2, "invalid_selection", str(error), error.field)

    result["selection"] = asdict(selection)
    processor = Processor.load()
    base_profiles = processor.section("base-profiles")
    addon_profiles = processor.section("profiles")
    if selection.base_profile not in base_profiles:
        return fail(2, "unknown_profile",
                    f"Unknown base profile '{selection.base_profile}'; "
                    f"valid profiles: {', '.join(sorted(base_profiles))}", "base_profile")
    unknown = [key for key in selection.addons if key not in addon_profiles]
    if unknown:
        return fail(2, "unknown_addon",
                    f"Unknown add-ons: {', '.join(unknown)}; "
                    f"valid add-ons: {', '.join(sorted(addon_profiles))}", "addons")

    host = _check_host_requirements(processor)
    result["host"] = {key: host[key] for key in ("platform_key", "os_key", "issues")}
    if host["issues"]:
        return fail(4, "unsupported_host", "; ".join(host["issues"]))
    platform_key, os_key = host["platform_key"], host["os_key"]
    supported_bases = {
        key for key, _, supported in processor.base_profiles_for_platform(platform_key, os_key)
        if supported
    }
    if selection.base_profile not in supported_bases:
        return fail(3, "incompatible_profile",
                    f"Base profile '{selection.base_profile}' is not supported on "
                    f"{platform_key} / {os_key}", "base_profile")
    compatible = {
        key for key, _ in processor.compatible_profiles(selection.base_profile, platform_key, os_key)
    }
    reasons = []
    for key in selection.addons:
        if key not in compatible:
            issues = processor.addon_compatibility_issues(key, platform_key, os_key)
            allowed_bases = (addon_profiles[key] or {}).get("base-profiles") or []
            if allowed_bases and selection.base_profile not in allowed_bases:
                issues.append(f"requires base profile: {', '.join(allowed_bases)}")
            reasons.append(f"{key}: {'; '.join(issues) or 'incompatible with selection'}")
    if reasons:
        return fail(3, "incompatible_addon", "; ".join(reasons), "addons")

    packages = list(processor.profile_packages(selection.base_profile, platform_key, os_key))
    for key in selection.addons:
        packages.extend(processor.addon_packages(key, platform_key, os_key))
    packages = _dedupe(packages)
    if not packages:
        return fail(3, "empty_selection", "Resolved package list is empty; nothing to install")
    profiles = [selection.base_profile, *selection.addons]
    hidden_packages = _dedupe([
        name for key in profiles
        for name in processor.hidden_os_packages(key, platform_key, os_key)
        if name not in packages
    ])
    prerequisites = required_prerequisites(processor, profiles, os_key)
    repos = list((host["os_entry"] or {}).get("repositories", {}).values())
    result["plan"] = {
        "packages": packages, "additional_os_packages": hidden_packages,
        "prerequisites": prerequisites, "repositories": repos,
    }
    if not json_output:
        _print_plan(result)
    if dry_run:
        if json_output:
            print(json.dumps(result))
        else:
            print("\nDry run: no changes made. Profile preview only; APT dependencies and versions are not verified.")
        return 0
    if os.geteuid() != 0:
        return fail(1, "root_required", "Installing packages requires root; re-run with sudo")

    if not json_output:
        print("\nRequirements met; proceeding with installation...\n")
    code = _run_install_blocking(
        packages, repos, prerequisites, hidden_packages,
        output_stream=sys.stderr if json_output else sys.stdout,
    )
    if code != 0:
        return fail(code, "installation_failed", f"Installation failed (exit code {code}); see installation output")
    result["restart_recommended"] = True
    if json_output:
        print(json.dumps(result))
    else:
        print("\nInstallation completed successfully. A manual system restart is recommended.")
    return 0


def _run_install_blocking(packages: list[str], repos: list[dict], prerequisites: dict,
                          force_packages: list[str] | None = None,
                          output_stream: TextIO | None = None) -> int:
    """Run edgepack_shared.install_logic.run_install synchronously and stream its output."""
    done = threading.Event()
    result = {"code": 1}
    stream = output_stream if output_stream is not None else sys.stdout

    def _on_output(line: str) -> None:
        stream.write(line if line.endswith("\n") else line + "\n")
        stream.flush()

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
