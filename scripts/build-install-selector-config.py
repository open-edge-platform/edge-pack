#!/usr/bin/env python3
"""Generate the installation selector config from the Edge Pack manifest."""

from __future__ import annotations

import argparse
import itertools
import json
import shlex
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "edgepack-installer" / "data" / "edgepacks-template.yml"
WEB_DIR = ROOT / "docs" / "edgepack-installer-files"
BASE_PATH = WEB_DIR / "config.base.json"
OUTPUT_PATH = WEB_DIR / "config.json"


def _load_mapping(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream) if path.suffix in {".yml", ".yaml"} else json.load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a mapping")
    return data


def _resolve_packages(value: object, platform_key: str) -> list[str]:
    if isinstance(value, list):
        return [str(package) for package in value]
    if isinstance(value, dict):
        selected = value.get(platform_key, value.get("default", value.get("_default", [])))
        if isinstance(selected, list):
            return [str(package) for package in selected]
    return []


def _supported(entry: dict, platform_key: str, os_key: str) -> bool:
    platforms = entry.get("supported_platforms") or []
    os_variants = entry.get("supported_os_variants") or []
    return (not platforms or platform_key in platforms) and (not os_variants or os_key in os_variants)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _profile_packages(entry: dict, platform_key: str, os_key: str) -> list[str]:
    packages = _resolve_packages(entry.get("meta_packages") or [], platform_key)
    by_os = entry.get("meta_packages_by_os") or {}
    if isinstance(by_os, dict):
        packages.extend(_resolve_packages(by_os.get(os_key) or [], platform_key))
    return _dedupe(packages)


def _compatible_addons(manifest: dict, base_key: str, platform_key: str, os_key: str) -> list[tuple[str, dict]]:
    result = []
    for addon_key, raw_entry in (manifest.get("profiles") or {}).items():
        entry = raw_entry if isinstance(raw_entry, dict) else {}
        if base_key in (entry.get("base-profiles") or []) and _supported(entry, platform_key, os_key):
            result.append((addon_key, entry))
    return result


def _addon_combinations(addons: list[tuple[str, dict]]):
    for count in range(len(addons) + 1):
        yield from itertools.combinations(addons, count)


def _download_commands(base: dict) -> list[str]:
    binary_url = shlex.quote(base["installerBinaryUrl"])
    checksum_url = shlex.quote(base["installerChecksumUrl"])
    return [
        f"curl -fL {binary_url} -o edgepack-installer &&",
        f"curl -fL {checksum_url} -o edgepack-installer.sha256 &&",
        "sha256sum -c edgepack-installer.sha256 &&",
        "chmod +x edgepack-installer &&",
    ]


def _repository_commands(repositories: list[dict], prefix: str, source_name: str) -> list[str]:
    if not repositories:
        return []

    commands = ["sudo install -d -m 0755 /etc/apt/keyrings"]
    source_lines = []
    for index, repository in enumerate(repositories):
        url = str(repository.get("repository_url") or "").strip()
        key_url = str(repository.get("repository_key") or "").strip()
        distribution = str(repository.get("repository_dist") or "").strip()
        components = " ".join(repository.get("repository_components") or ["main"])
        if not (url.startswith("https://") and key_url.startswith("https://") and distribution):
            raise ValueError(f"Incomplete or insecure repository configuration for {url or '<missing URL>'}")
        keyring = f"/etc/apt/keyrings/{prefix}-{index}.gpg"
        commands.append(
            f"curl -fsSL {shlex.quote(key_url)} | "
            f"sudo gpg --batch --yes --dearmor -o {shlex.quote(keyring)}"
        )
        source_lines.append(f"deb [signed-by={keyring}] {url} {distribution} {components}")

    quoted_lines = " ".join(shlex.quote(line) for line in source_lines)
    commands.append(
        f"printf '%s\\n' {quoted_lines} | "
        f"sudo tee /etc/apt/sources.list.d/{source_name}.list >/dev/null"
    )
    return commands


def _prerequisites(selected: list[tuple[str, dict]], os_key: str) -> tuple[list[dict], list[str]]:
    repositories = []
    packages = []
    seen_urls = set()
    for _, entry in selected:
        by_os = entry.get("prerequisites") or {}
        prerequisites = by_os.get(os_key) or {} if isinstance(by_os, dict) else {}
        for repository in prerequisites.get("repositories") or []:
            url = repository.get("repository_url")
            if url not in seen_urls:
                repositories.append(repository)
                seen_urls.add(url)
        packages.extend(str(package) for package in prerequisites.get("packages") or [])
    return repositories, _dedupe(packages)


def _apt_commands(
    os_entry: dict,
    packages: list[str],
    selected_profiles: list[tuple[str, dict]],
    os_key: str,
) -> list[str]:
    commands = [
        "sudo apt-get update",
        "sudo apt-get install -y ca-certificates curl gnupg",
    ]

    prerequisite_repositories, prerequisite_packages = _prerequisites(selected_profiles, os_key)
    if prerequisite_repositories:
        commands.extend(_repository_commands(
            prerequisite_repositories, "edgepack-prerequisite", "edgepack-prerequisite"
        ))
        commands.append("sudo apt-get update")
        if prerequisite_packages:
            commands.append(
                "sudo apt-get install -y "
                + " ".join(shlex.quote(package) for package in prerequisite_packages)
            )

    repositories = list((os_entry.get("repositories") or {}).values())
    commands.extend(_repository_commands(repositories, "edgepack", "edgepack"))

    pin_blocks = []
    for repository in repositories:
        host = urlparse(repository.get("repository_url") or "").hostname
        if host:
            priority = int(repository.get("pin_priority", 1001))
            pin_blocks.append((host, priority))
    if pin_blocks:
        pin_lines = []
        for host, priority in dict.fromkeys(pin_blocks):
            pin_lines.extend(["Package: *", f"Pin: origin {host}", f"Pin-Priority: {priority}", ""])
        quoted_lines = " ".join(shlex.quote(line) for line in pin_lines)
        commands.append(
            f"printf '%s\\n' {quoted_lines} | "
            "sudo tee /etc/apt/preferences.d/edgepack.pref >/dev/null"
        )

    commands.extend([
        "sudo apt-get update",
        "sudo apt-get install -y " + " ".join(shlex.quote(package) for package in packages),
    ])
    return commands


def build_config() -> dict:
    manifest = _load_mapping(MANIFEST_PATH)
    base = _load_mapping(BASE_PATH)
    installations_by_selection = {}

    os_variants = manifest.get("os_variant") or {}
    platforms = manifest.get("platforms") or {}
    base_profiles = manifest.get("base-profiles") or {}

    for os_key, os_entry in os_variants.items():
        for platform_key in platforms:
            for base_key, base_entry in base_profiles.items():
                if not _supported(base_entry, platform_key, os_key):
                    continue
                compatible_addons = _compatible_addons(manifest, base_key, platform_key, os_key)
                for addon_combination in _addon_combinations(compatible_addons):
                    addon_keys = [key for key, _ in addon_combination]
                    selected_profiles = [(base_key, base_entry), *addon_combination]
                    packages = []
                    for _, entry in selected_profiles:
                        packages.extend(_profile_packages(entry, platform_key, os_key))
                    packages = _dedupe(packages)
                    cli_args = " ".join([base_key, *addon_keys])
                    downloads = _download_commands(base)
                    installation = {
                        "selection": {
                            "os": os_key,
                            "baseProfile": base_key,
                            "addons": addon_keys,
                        },
                        "packages": packages,
                        "commands": {
                            "tui": "\n".join([*downloads, "sudo ./edgepack-installer"]),
                            "installer-cli": "\n".join([
                                *downloads,
                                f"sudo ./edgepack-installer install {cli_args}",
                            ]),
                            "apt": "\n".join(_apt_commands(
                                os_entry, packages, selected_profiles, os_key
                            )),
                        },
                    }
                    identity = (os_key, base_key, tuple(addon_keys))
                    existing = installations_by_selection.get(identity)
                    if existing and (
                        existing["packages"] != installation["packages"]
                        or existing["commands"] != installation["commands"]
                    ):
                        raise ValueError(
                            "Selector output differs by platform for "
                            f"{os_key}/{base_key}/{','.join(addon_keys) or '<no add-ons>'}"
                        )
                    installations_by_selection[identity] = installation

    return {
        "title": base["title"],
        "manifestVersion": str(manifest.get("version") or ""),
        "defaultMethod": base.get("defaultMethod", "tui"),
        "methods": base["methods"],
        "headlessSupport": base["headlessSupport"],
        "operatingSystems": [
            {
                "value": key,
                "label": entry.get("display_name") or key,
                "minKernelVersion": str(entry.get("min_kernel_version") or ""),
            }
            for key, entry in os_variants.items()
        ],
        "baseProfiles": [
            {
                "value": key,
                "label": entry.get("display_name") or key,
                "description": entry.get("description") or "",
            }
            for key, entry in base_profiles.items()
        ],
        "addons": [
            {
                "value": key,
                "label": entry.get("display_name") or key,
                "description": entry.get("description") or "",
            }
            for key, entry in (manifest.get("profiles") or {}).items()
        ],
        "installations": list(installations_by_selection.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if config.json is stale")
    args = parser.parse_args()
    rendered = json.dumps(build_config(), indent=2, ensure_ascii=False) + "\n"

    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        if current != rendered:
            print("error: docs/edgepack-installer-files/config.json is out of date", file=sys.stderr)
            print("Run: python3 scripts/build-install-selector-config.py", file=sys.stderr)
            return 1
        print("Installation selector config is up to date.")
        return 0

    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())