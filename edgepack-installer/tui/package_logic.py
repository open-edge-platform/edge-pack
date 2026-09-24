# tui/package_logic.py — pure data functions for package tree management
#
# All functions operate on plain Python dicts (no Gtk, no Textual widgets).
# These are extracted from the GUI's step2/step3/step4 mixin methods so that
# both the GUI and TUI can share the same business logic.
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgepack_shared.processor import Processor


# ---------------------------------------------------------------------------
# Entry dict schema
# ---------------------------------------------------------------------------
# {
#   name               : str
#   version            : str
#   size               : str          raw string from YAML, e.g. "1.5 GB"
#   level              : int          0=root, 1=section header, 2=leaf package
#   checked            : bool | None  None means "no checkbox shown" (section headers)
#   locked             : bool         cannot be changed by user
#   preselected        : bool         was on by default (from usage-feature mapping)
#   parent             : dict | None
#   children           : list[dict]
#   category           : str | None   'dkms' | 'kernel' | None
#   disabled_by_kvariant: bool        DKMS rows disabled when intel_kernel selected
#   bold               : bool         display name in bold
# }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_size(raw: object) -> float:
    """Convert a size string (e.g. '1.5 GB', '512 MB') to MiB float."""
    if raw is None:
        return 0.0
    s = str(raw).strip().upper()
    for unit, mult in (
        ("GB", 1024.0),
        ("MB", 1.0),
        ("KB", 1.0 / 1024.0),
        ("B", 1.0 / (1024.0 * 1024.0)),
    ):
        if s.endswith(unit):
            try:
                return float(s[: -len(unit)].strip()) * mult
            except ValueError:
                return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _make_entry(
    name: str,
    version: str,
    size: str,
    *,
    checked: bool | None,
    level: int,
    locked: bool = False,
    bold: bool = False,
    parent: dict | None = None,
    category: str | None = None,
) -> dict:
    """Allocate one entry dict and wire it to its parent's children list."""
    resolved_category = category or (
        parent.get("category") if isinstance(parent, dict) else None
    )
    entry: dict = {
        "name": name,
        "version": version or "",
        "size": size or "",
        "level": level,
        "checked": checked,
        "locked": locked,
        "preselected": bool(checked) if checked is not None else False,
        "parent": parent,
        "children": [],
        "category": resolved_category,
        "disabled_by_kvariant": False,
        "bold": bold,
    }
    if parent is not None:
        parent["children"].append(entry)
    return entry


# ---------------------------------------------------------------------------
# Public: build tree
# ---------------------------------------------------------------------------

def build_pkg_entries(
    processor: "Processor",
    profile_key: str,
    addon_profile_keys: list[str] | None = None,
    platform_key: str | None = None,
    os_key: str | None = None,
) -> list[dict]:
    """Build the flat package entry list from the selected base-profile plus any add-ons.

    Returns a *flat* list of entry dicts representing the tree; parent/children
    links allow traversal.

    Example:
        Input:  processor, 'base-standard', ['sriov'], 'ptl'
        Output: [root_entry, packages_header, intel-edge-base-standard,
                 addons_header, intel-edge-graphics-sriov-ptl]
    """
    entries: list[dict] = []

    meta_packages = processor.profile_packages(profile_key, platform_key, os_key) if profile_key else []

    # Level 0 — root
    root = _make_entry(
        "intel-edge-pack",
        "1.0",
        "",
        checked=True,
        locked=True,
        level=0,
        bold=True,
    )
    entries.append(root)

    # Level 1 — Base packages section
    pkg_header = _make_entry(
        "Packages",
        "",
        "",
        checked=None,
        level=1,
        bold=True,
        parent=root,
    )
    entries.append(pkg_header)

    for pkg_name in meta_packages:
        e = _make_entry(
            pkg_name,
            "",
            "",
            checked=True,
            locked=True,
            level=2,
            bold=False,
            parent=pkg_header,
        )
        entries.append(e)

    # Level 1 — Add-on packages section (one per selected optional profile)
    addon_packages: list[str] = []
    for addon_key in (addon_profile_keys or []):
        addon_packages.extend(processor.addon_packages(addon_key, platform_key, os_key))

    if addon_packages:
        addon_header = _make_entry(
            "Add-on packages",
            "",
            "",
            checked=None,
            level=1,
            bold=True,
            parent=root,
        )
        entries.append(addon_header)
        for pkg_name in addon_packages:
            e = _make_entry(
                pkg_name,
                "",
                "",
                checked=True,
                locked=True,
                level=2,
                bold=False,
                parent=addon_header,
            )
            entries.append(e)

    return entries


# ---------------------------------------------------------------------------
# Public: cascade / ancestor update (called from Step 2 toggle handlers)
# ---------------------------------------------------------------------------

def cascade_to_descendants(entry: dict, active: bool) -> list[dict]:
    """Set every unlocked, kvariant-enabled descendant to *active*.

    Returns the list of entries that were actually changed (for widget sync).

    Example:
        Input:  (dkms_header_entry, True)
        Output: [xe_dkms_entry, ...] — each now has checked=True
    """
    changed: list[dict] = []
    for child in entry["children"]:
        if (
            child["checked"] is not None
            and not child["locked"]
            and not child.get("disabled_by_kvariant")
        ):
            if child["checked"] != active:
                child["checked"] = active
                changed.append(child)
        changed.extend(cascade_to_descendants(child, active))
    return changed


def update_ancestors(entry: dict) -> list[dict]:
    """Walk up parents: mark each parent checked iff any descendant is active.

    Returns the list of ancestor entries that were actually changed.

    Example:
        Input:  xe_dkms leaf entry (just toggled off)
        Output: [dkms_header_entry] — now unchecked because no child active
    """
    changed: list[dict] = []
    parent = entry["parent"]
    while parent is not None:
        if parent["checked"] is not None and not parent["locked"]:
            should_be = _any_descendant_active(parent)
            if parent["checked"] != should_be:
                parent["checked"] = should_be
                changed.append(parent)
        parent = parent["parent"]
    return changed


def _any_descendant_active(entry: dict) -> bool:
    for child in entry["children"]:
        if child.get("checked"):
            return True
        if _any_descendant_active(child):
            return True
    return False


# ---------------------------------------------------------------------------
# Public: prerequisites (repo + gating package, checked before the normal install)
# ---------------------------------------------------------------------------

def required_prerequisites(
    processor: "Processor",
    profile_keys: list[str],
    os_key: str | None,
) -> dict:
    """Collect and merge prerequisite repos/packages for the given selected profile keys and OS variant.

    Looks up ``processor.profile_prerequisites(key, os_key)`` for every key
    (base profile and/or add-ons), each of which may declare multiple
    ``repositories`` plus a ``packages`` list. Repos are deduped by
    ``repository_url`` and packages by exact string, across all selected
    profiles, into a single merged block.

    """
    seen_urls: set[str] = set()
    seen_packages: set[str] = set()
    repositories: list[dict] = []
    packages: list[str] = []
    for key in profile_keys or []:
        prereq = processor.profile_prerequisites(key, os_key)
        if not prereq:
            continue
        for repo in prereq.get("repositories") or []:
            url = repo.get("repository_url")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            repositories.append(repo)
        for pkg in prereq.get("packages") or []:
            if pkg in seen_packages:
                continue
            seen_packages.add(pkg)
            packages.append(pkg)
    return {"repositories": repositories, "packages": packages}


# ---------------------------------------------------------------------------
# Public: collect packages for install
# ---------------------------------------------------------------------------

def collect_selected_packages(pkg_entries: list[dict]) -> dict[str, str]:
    """Return {package_name: version} for every checked level-2 package entry.

    Example:
        Input:  [root, packages_hdr, intel-edge-base-standard(checked=True)]
        Output: {'intel-edge-base-standard': ''}
    """
    return {
        entry["name"]: entry.get("version") or ""
        for entry in pkg_entries
        if entry["level"] == 2 and entry.get("checked") and entry.get("name")
    }


def compute_total_size(pkg_entries: list[dict]) -> float:
    """Sum sizes (in MiB) of all checked level-2 entries."""
    total = 0.0
    for entry in pkg_entries:
        if entry["level"] == 2 and entry.get("checked"):
            total += _parse_size(entry.get("size"))
    return total


def _selected_leaves(entry: dict) -> list[dict]:
    """Return all checked leaves beneath *entry* (any depth)."""
    leaves: list[dict] = []

    def walk(e: dict) -> None:
        if not e["children"]:
            if e.get("checked"):
                leaves.append(e)
            return
        for child in e["children"]:
            walk(child)

    walk(entry)
    return leaves
