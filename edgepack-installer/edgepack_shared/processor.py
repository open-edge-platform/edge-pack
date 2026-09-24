# edgepack_shared/processor.py — YAML template processor (UI-agnostic)
#
# SPDX-License-Identifier: MIT

import os
import sys
import yaml

from .host import host_cpu_model, read_os_release


def _resolve_platform_packages(pkgs, platform_key: str | None) -> list[str]:
    """Resolve meta_packages to a flat list for the given platform.

    Accepts either the legacy flat-list form or the new map form::

        # flat list (all platforms get the same packages)
        meta_packages:
          - intel-edge-ipu

        # platform map (per-platform override with 'default' fallback)
        meta_packages:
          default: [intel-edge-ipu]
          ptl:     [intel-edge-ipu, intel-edge-ipu-ptl-sample]
          wcl:     [intel-edge-ipu, intel-edge-ipu-wcl-sample]

    Resolution order for the map form:
      1. Exact platform_key match.
      2. 'default' or '_default' fallback.
    """
    if isinstance(pkgs, list):
        return list(pkgs)
    if isinstance(pkgs, dict):
        if platform_key and platform_key in pkgs:
            value = pkgs[platform_key]
        else:
            value = pkgs.get('default') or pkgs.get('_default') or []
        return list(value) if isinstance(value, list) else []
    return []


def _resolve_os_extra_packages(entry, platform_key: str | None, os_key: str | None) -> list[str]:
    """Resolve a profile entry's ``meta_packages_by_os.<os_key>`` extras.

    These are installed but never shown in the UI, so they are resolved
    separately from the visible ``meta_packages``. Platform-resolved (so the
    map form is still supported), order preserved, duplicates dropped.
    """
    entry = entry or {}
    by_os = entry.get('meta_packages_by_os') or {}
    if not (os_key and isinstance(by_os, dict)):
        return []
    pkgs = _resolve_platform_packages(by_os.get(os_key) or [], platform_key)
    seen: set[str] = set()
    result: list[str] = []
    for pkg in pkgs:
        if pkg not in seen:
            seen.add(pkg)
            result.append(pkg)
    return result


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a dotted version string into a tuple of ints for comparison.

    Examples::

        _parse_version('24.04.2') -> (24, 4, 2)
        _parse_version('24.04')   -> (24, 4)
        _parse_version('26.04.1') -> (26, 4, 1)
    """
    parts: list[int] = []
    for part in str(version_str).strip().split('.'):
        try:
            parts.append(int(part))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def _as_dict(value):
    """Coerce an arbitrary (possibly adversarial YAML) value to a dict."""
    return value if isinstance(value, dict) else {}


class Processor:
    """Wrapper around the parsed edgepacks-template.yml.

    Loads from a Gio gresource when available (GUI path), otherwise falls back
    to the file on disk so TUI callers work without GTK/Gio.
    """

    _RESOURCE_PATH = '/org/gnome/EdgePack/edgepacks-template.yml'
    _LOCAL_FILENAME = '../data/edgepacks-template.yml'

    def __init__(self, data):
        self._data = data if isinstance(data, dict) else {}

    @classmethod
    def load(cls):
        """Load from gresource if available, else from disk next to this file."""
        # Try Gio gresource (only present in the GTK build).
        try:
            from gi.repository import Gio
            gbytes = Gio.resources_lookup_data(
                cls._RESOURCE_PATH, Gio.ResourceLookupFlags.NONE,
            )
            data = yaml.safe_load(gbytes.get_data().decode('utf-8'))
            return cls(data)
        except Exception:
            pass

        # Fall back to the YAML file on disk. Search order:
        #   1. PyInstaller bundle: _MEIPASS/data/edgepacks-template.yml
        #   2. Installed alongside the edgepack package
        #   3. In-tree location relative to edgepack_shared/
        here = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(getattr(sys, '_MEIPASS', ''), 'data', 'edgepacks-template.yml'),
            os.path.join(here, '..', 'edgepack', cls._LOCAL_FILENAME),
            os.path.join(here, '..', 'src', cls._LOCAL_FILENAME),
            os.path.join(here, cls._LOCAL_FILENAME),
        ]
        for path in candidates:
            path = os.path.normpath(path)
            if os.path.isfile(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return cls(yaml.safe_load(f))

        raise FileNotFoundError(f'{cls._LOCAL_FILENAME} not found')

    def section(self, name):
        """Return a top-level YAML section as a dict (empty dict if missing or non-mapping)."""
        value = self._data.get(name)
        return value if isinstance(value, dict) else {}

    def entry(self, section, key):
        """Return a single keyed entry inside a top-level section."""
        return _as_dict(self.section(section).get(key))

    def display_pairs(self, section):
        """List (key, display_name) for every entry in a section, in YAML order."""
        return [
            (key, _as_dict(entry).get('display_name') or key)
            for key, entry in self.section(section).items()
        ]

    def manifest_version(self):
        """Return the top-level 'version:' string from the template (e.g. '0.1-0001')."""
        return str(self._data.get('version') or '').strip()

    def supported_platform_labels(self):
        """Display-name strings for every platform in the template, YAML order."""
        return [
            _as_dict(entry).get('display_name') or key
            for key, entry in self.section('platforms').items()
        ]

    def supported_platform_details(self):
        """(display_name, [model_names]) for every platform, YAML order."""
        details = []
        for key, entry in self.section('platforms').items():
            entry = _as_dict(entry)
            label = entry.get('display_name') or key
            models = [str(m) for m in (entry.get('model_names') or []) if str(m).strip()]
            details.append((label, models))
        return details

    def supported_os_labels(self):
        """Display-name strings for every os_variant in the template, YAML order."""
        return [
            _as_dict(entry).get('display_name') or key
            for key, entry in self.section('os_variant').items()
        ]

    def detect_platform(self, cpu_model: str | None = None):
        """Match the host CPU model name against platforms[].model_names keywords.

        Pass *cpu_model* (from a prior ``host_cpu_model()`` call) to avoid
        reading /proc/cpuinfo a second time.  When omitted the file is read here.

        Returns (platform_key, entry) or (None, {}) if unrecognised.
        """
        platforms = self.section('platforms')
        if not platforms:
            return None, {}

        if cpu_model is None:
            cpu_model = host_cpu_model()
        if not cpu_model:
            return None, {}

        for key, entry in platforms.items():
            entry = _as_dict(entry)
            for keyword in entry.get('model_names') or []:
                if str(keyword) and str(keyword) in cpu_model:
                    return key, entry

        return None, {}

    def detect_os(self, os_info: dict | None = None):
        """Match the host's /etc/os-release against os_variant entries.

        Matching priority:
          1. Explicit 'version_id' field on the entry (e.g. "24.04") matched
             against VERSION_ID from /etc/os-release.  This covers all dot
             releases (24.04.1, 24.04.5, …) because Ubuntu always reports the
             major.minor in VERSION_ID.
          2. VERSION_CODENAME matched against the entry key or description
             (legacy fallback for entries without a version_id field).

        Returns (os_key, entry) on a match, or (None, {}) if no os_variant
        matches — Step 1 renders a "not compatible" warning in that case.
        """
        os_variants = self.section('os_variant')
        if not os_variants:
            return None, {}

        info = os_info if os_info is not None else read_os_release()
        version_id = info.get('VERSION_ID', '').strip()
        version_codename = (info.get('VERSION_CODENAME') or '').lower().strip()

        for key, entry in os_variants.items():
            entry = _as_dict(entry)
            # Priority 1: explicit version_id field
            entry_version_id = str(entry.get('version_id') or '').strip()
            if entry_version_id and version_id and entry_version_id == version_id:
                return key, entry

        # Priority 2: codename fallback (covers entries without version_id)
        for key, entry in os_variants.items():
            entry = _as_dict(entry)
            if not entry.get('version_id') and version_codename:
                desc = (entry.get('description') or '').lower()
                if version_codename in key.lower() or version_codename in desc:
                    return key, entry

        return None, {}

    def os_version_issues(self, os_key: str, host_dot_version: str) -> list[str]:
        """Return warning strings when the host OS dot release is below the minimum.

        Checks the optional 'min_version' field on the os_variant entry.
        Returns an empty list when:
          - the entry has no 'min_version' field, or
          - host_dot_version is empty (version undetectable), or
          - the host version meets or exceeds the minimum.

        Examples::

            # template: min_version: "24.04.2", host: "24.04"
            -> ["Ubuntu 24.04 requires version 24.04.2 or later (detected: 24.04)"]

            # template: min_version: "24.04.2", host: "24.04.5"
            -> []
        """
        entry = self.entry('os_variant', os_key) or {}
        min_version = str(entry.get('min_version') or '').strip()
        if not min_version or not host_dot_version:
            return []
        host_tuple = _parse_version(host_dot_version)
        min_tuple = _parse_version(min_version)
        # Pad both tuples to the same length so (24, 4) == (24, 4, 0).
        # Python tuple comparison treats (24, 4) < (24, 4, 0) as True without padding.
        pad = max(len(host_tuple), len(min_tuple))
        host_padded = host_tuple + (0,) * (pad - len(host_tuple))
        min_padded = min_tuple + (0,) * (pad - len(min_tuple))
        if host_padded < min_padded:
            display = entry.get('display_name') or os_key
            return [
                f"{display} requires version {min_version} or later "
                f"(detected: {host_dot_version})"
            ]
        return []

    def kernel_version_issues(
        self,
        host_kernel_dot_version: str,
        os_key: str | None = None,
        host_kernel_is_ubuntu: bool | None = None,
    ) -> list[str]:
        """Return warning strings when the host kernel doesn't meet the OS variant's requirements.

        Checks two independent, optional fields on the os_variant entry for os_key:
          - 'min_kernel_version': host kernel dot-version must be >= this value.
          - 'require_ubuntu_kernel': if true (the default when the field is absent),
            the kernel must be confirmed Ubuntu-built (see host_kernel_is_ubuntu()).

        Examples::

            # os_variant.ubuntu_noble: min_kernel_version: "7.0"
            # host: version="6.8.0"
            -> ["Ubuntu 24.04 requires kernel version 7.0 or later (detected: 6.8.0)"]

            # os_variant.ubuntu_noble: min_kernel_version: "7.0", require_ubuntu_kernel: true
            # host: version="7.0.0", is_ubuntu=False
            -> ["Ubuntu 24.04 requires an Ubuntu-built kernel, version 7.0 or later"]

            # host: version="7.0.0", is_ubuntu=True
            -> []
        """
        issues: list[str] = []
        if not os_key:
            return issues
        os_entry = self.entry('os_variant', os_key) or {}
        if not os_entry:
            return issues
        display = os_entry.get('display_name') or os_key

        min_version = str(os_entry.get('min_kernel_version') or '').strip()
        if min_version and host_kernel_dot_version:
            host_tuple = _parse_version(host_kernel_dot_version)
            min_tuple = _parse_version(min_version)
            pad = max(len(host_tuple), len(min_tuple))
            host_padded = host_tuple + (0,) * (pad - len(host_tuple))
            min_padded = min_tuple + (0,) * (pad - len(min_tuple))
            if host_padded < min_padded:
                issues.append(
                    f"{display} requires kernel version {min_version} or later "
                    f"(detected: {host_kernel_dot_version})"
                )

        require_ubuntu = os_entry.get('require_ubuntu_kernel', True)
        if require_ubuntu and host_kernel_is_ubuntu is False:
            issues.append(
                f"{display} requires an Ubuntu-built kernel, version {min_version or '7.0'} or later"
            )

        return issues

    def profile_packages(self, profile_key: str, platform_key: str | None = None,
                         os_key: str | None = None) -> list[str]:
        """Visible meta-package names for a base-profile (excludes meta_packages_by_os)."""
        entry = self.entry('base-profiles', profile_key) or {}
        return _resolve_platform_packages(entry.get('meta_packages') or [], platform_key)

    def base_profiles_for_platform(
        self,
        platform_key: str | None = None,
        os_key: str | None = None,
    ) -> list[tuple[str, str, bool]]:
        """(key, display_name, is_supported) for every base-profile in YAML order.

        All profiles are always returned so the UI can show unsupported ones as
        crossed-out rather than hiding them entirely.  is_supported is True when:
          - no 'supported_platforms' list, or platform_key is in that list, AND
          - no 'supported_os_variants' list, or os_key is in that list.
        """
        result = []
        for key, entry in self.section('base-profiles').items():
            entry = entry or {}
            supported_platforms = entry.get('supported_platforms')
            platform_ok = not supported_platforms or not platform_key or platform_key in supported_platforms
            supported_os = entry.get('supported_os_variants')
            os_ok = not supported_os or not os_key or os_key in supported_os
            result.append((key, entry.get('display_name') or key, platform_ok and os_ok))
        return result

    def addon_packages(self, addon_key: str, platform_key: str | None = None,
                       os_key: str | None = None) -> list[str]:
        """Visible meta-package names for an add-on profile (excludes meta_packages_by_os)."""
        entry = self.entry('profiles', addon_key) or {}
        return _resolve_platform_packages(entry.get('meta_packages') or [], platform_key)

    def hidden_os_packages(self, profile_key: str, platform_key: str | None = None,
                           os_key: str | None = None) -> list[str]:
        """``meta_packages_by_os`` extras for a base or add-on profile.

        Installed for the matching OS variant but never shown in the package
        tree, summary, or size total — merged into the apt command only at the
        final install hand-off.
        """
        entry = self.entry('profiles', profile_key) or self.entry('base-profiles', profile_key)
        return _resolve_os_extra_packages(entry, platform_key, os_key)

    def profile_prerequisites(self, profile_key: str, os_key: str | None = None) -> dict | None:
        """Return the 'prerequisites' block for a base-profile or add-on profile key.

        Checks 'profiles' (add-ons) first, then 'base-profiles' — a given key
        only ever exists in one of the two sections. The YAML 'prerequisites'
        block is keyed by os_variant (e.g. 'ubuntu_noble', 'ubuntu_resolute'),
        mirroring os_variant.<key>.repositories, since the repo URL/dist and
        package version can differ per OS variant. Returns None when the
        profile has no prerequisites declared for the given os_key.
        """
        entry = self.entry('profiles', profile_key) or self.entry('base-profiles', profile_key)
        prereqs_by_os = entry.get('prerequisites') or {}
        if not os_key:
            return None
        return prereqs_by_os.get(os_key) or None

    def compatible_profiles(
        self,
        base_profile_key: str,
        platform_key: str | None = None,
        os_key: str | None = None,
    ) -> list[tuple[str, dict]]:
        """(key, entry) pairs for profiles compatible with the given base-profile, platform, and OS.

        A profile is included when:
          - its 'base-profiles' list contains base_profile_key, AND
          - it has no 'supported_platforms' list, or platform_key is in that list, AND
          - it has no 'supported_os_variants' list, or os_key is in that list.
        """
        result = []
        for key, entry in self.section('profiles').items():
            entry = entry or {}
            if base_profile_key not in (entry.get('base-profiles') or []):
                continue
            supported_platforms = entry.get('supported_platforms')
            if supported_platforms and platform_key and platform_key not in supported_platforms:
                continue
            supported_os = entry.get('supported_os_variants')
            if supported_os and os_key and os_key not in supported_os:
                continue
            result.append((key, entry))
        return result

    def addon_compatibility_issues(
        self,
        addon_key: str,
        detected_platform_key: str | None,
        detected_os_key: str | None = None,
    ) -> list[str]:
        """Return warning strings for compatibility issues with an add-on profile.

        Checks both the 'supported_platforms' and 'supported_os_variants' lists on
        the profile entry, mirroring the checks performed by compatible_profiles().
        """
        issues: list[str] = []
        addon_entry = self.entry('profiles', addon_key) or {}
        addon_display = addon_entry.get('display_name') or addon_key

        supported_platforms = addon_entry.get('supported_platforms') or []
        if supported_platforms and detected_platform_key and detected_platform_key not in supported_platforms:
            supported_names = [
                (self.entry('platforms', k) or {}).get('display_name') or k
                for k in supported_platforms
            ]
            issues.append(
                f"{addon_display} is not supported on this platform "
                f"(supported: {', '.join(supported_names)})"
            )

        supported_os = addon_entry.get('supported_os_variants') or []
        if supported_os and detected_os_key and detected_os_key not in supported_os:
            supported_os_names = [
                (self.entry('os_variant', k) or {}).get('display_name') or k
                for k in supported_os
            ]
            issues.append(
                f"{addon_display} is not supported on this OS "
                f"(supported: {', '.join(supported_os_names)})"
            )
        return issues

    def os_repositories(self, os_key: str) -> dict:
        """Repositories dict for an OS variant, keyed by repo name."""
        return self.entry('os_variant', os_key).get('repositories') or {}

    def versions(self):
        """List (key, label) pairs for every Edge Pack version in the YAML."""
        return [(str(v), f'V{v}') for v in self.section('edgepack_version').keys()]

    def os_edgepack_versions(self, os_key: str | None) -> list[tuple[str, str]]:
        """Return (version_key, label) pairs from the detected OS variant's edgepack_versions list."""
        if not os_key:
            return []
        versions = self.entry('os_variant', os_key).get('edgepack_versions') or []
        return [(str(v), f'V{v}') for v in versions]

    def version_entry(self, key):
        """Return the edgepack_version block for a given version key."""
        return self.entry('edgepack_version', key) or self.entry('edgepack_version', str(key))

    def meta_packages(self, version_key):
        """Meta-packages defined for a given Edge Pack version."""
        return self.version_entry(version_key).get('meta_packages') or {}

    def dkms_packages(self, version_key):
        """DKMS packages defined for a given Edge Pack version."""
        ev = self.version_entry(version_key)
        return ev.get('dkms-packages') or ev.get('dkms_packages') or {}

    def kernel_image(self, version_key, kvariant, flavour, os_key):
        """Resolve the kernel image package for the current selection.

        Returns (package_name, version) or None if no matching entry.
        """
        ev_kernel = self.version_entry(version_key).get('kernel_packages') or {}
        variant_entry = next(
            (v for k, v in ev_kernel.items() if k.lower() == kvariant.lower()),
            None,
        ) or {}
        sub_key = flavour if kvariant == 'intel_kernel' else os_key
        leaf = variant_entry.get(sub_key) or {}
        name = leaf.get('package_name')
        if not name:
            return None
        return name, leaf.get('version', '')

    def required_meta_packages(self, usage_key):
        """Meta-packages a usage feature pulls in (incl. nested sub-features)."""
        if not usage_key:
            return set()
        feature = self.entry('features', usage_key)
        required = set()
        for key in ('meta_packages', 'meta_package'):
            required.update(feature.get(key) or [])
        for sub in feature.values():
            if isinstance(sub, dict):
                for key in ('meta_packages', 'meta_package'):
                    required.update(sub.get(key) or [])
        return required

    def required_dkms_packages(self, usage_key):
        """DKMS packages a usage feature requires (incl. nested sub-features)."""
        if not usage_key:
            return set()
        feature = self.entry('features', usage_key)
        required = set()
        for key in ('dkms_packages', 'dkms_package'):
            required.update(feature.get(key) or [])
        for sub in feature.values():
            if isinstance(sub, dict):
                for key in ('dkms_packages', 'dkms_package'):
                    required.update(sub.get(key) or [])
        return required

    def platform_features(self, platform_key):
        """Features supported by a given platform."""
        return set(self.entry('platforms', platform_key).get('features') or [])

    def platform_kernel_variants(self, platform_key):
        """Kernel variants the platform's YAML entry advertises support for."""
        return set(self.entry('platforms', platform_key).get('supported_kernel_version') or [])

    def kernel_type_flavours_for(self, kvariant_key):
        """Flavours (kernel_type_variant) compatible with the given kernel variant."""
        return {
            type_key
            for type_key, type_entry in self.section('kernel_type_variant').items()
            if kvariant_key in (type_entry.get('kernel_variant') or [])
        }

    def all_package_names(self):
        """Every Intel Edge package name referenced anywhere in the template."""
        names = set()
        for version_key in self.section('edgepack_version'):
            ev = self.version_entry(version_key)
            names.update((ev.get('meta_packages') or {}).keys())
            names.update((ev.get('dkms-packages') or ev.get('dkms_packages') or {}).keys())
            kernel_packages = ev.get('kernel_packages') or {}
            for variant_entry in kernel_packages.values():
                if not isinstance(variant_entry, dict):
                    continue
                for leaf in variant_entry.values():
                    if isinstance(leaf, dict) and leaf.get('package_name'):
                        names.add(leaf['package_name'])
        # Include base-profile and add-on profile meta_packages
        for entry in self.section('base-profiles').values():
            names.update((entry or {}).get('meta_packages') or [])
        for entry in self.section('profiles').values():
            names.update((entry or {}).get('meta_packages') or [])
        return names

    def kernel_variant_uses_dkms(self, kvariant_key):
        """Whether DKMS modules are applicable to the given kernel variant."""
        entry = self.entry('kernel_variant', kvariant_key)
        return str(entry.get('dkms', '')).lower() == 'yes'
