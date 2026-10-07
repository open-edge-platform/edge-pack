from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import yaml


MAX_CONFIG_BYTES = 64 * 1024


class ConfigError(ValueError):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class InstallationSelection:
    base_profile: str
    addons: tuple[str, ...]
    edgepack_version: str
    schema_version: int = 1


class _SelectionLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        event = self.peek_event()
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None):
            raise ConfigError("YAML anchors and aliases are not supported")
        depth = getattr(self, "_selection_depth", 0)
        if depth >= 4:
            raise ConfigError("Configuration nesting is too deep")
        self._selection_depth = depth + 1
        try:
            return super().compose_node(parent, index)
        finally:
            self._selection_depth = depth

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise ConfigError("Configuration field names must be strings")
            if key in mapping:
                raise ConfigError(f"Duplicate field '{key}'", key)
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def validate_profile_key(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{field} must be a nonempty string", field)
    if len(value) > 128 or re.fullmatch(r"[a-zA-Z0-9_-]+", value) is None:
        raise ConfigError(
            f"{field} must contain 1-128 letters, digits, underscores or hyphens", field
        )
    return value


def normalize_selection(data: object, supported_version: str) -> InstallationSelection:
    if not isinstance(data, dict):
        raise ConfigError("Configuration must be a YAML mapping")
    allowed = {"schema_version", "base_profile", "edgepack_version", "addons"}
    for field in data:
        if field not in allowed:
            raise ConfigError(f"Unknown configuration field '{field}'", str(field))
    schema_version = data.get("schema_version", 1)
    if type(schema_version) is not int or schema_version != 1:
        raise ConfigError("schema_version must be the integer 1", "schema_version")
    base_profile = validate_profile_key(data.get("base_profile"), "base_profile")
    addons = data.get("addons", [])
    if not isinstance(addons, list):
        raise ConfigError("addons must be a list of profile keys", "addons")
    keys = [validate_profile_key(value, f"addons[{index}]") for index, value in enumerate(addons)]
    version = data.get("edgepack_version", supported_version)
    if not isinstance(version, str) or version != supported_version:
        raise ConfigError(
            f'edgepack_version must be the quoted string "{supported_version}"',
            "edgepack_version",
        )
    return InstallationSelection(base_profile, tuple(dict.fromkeys(keys)), version)


def load_selection(path: str, supported_version: str) -> InstallationSelection:
    try:
        with Path(path).open("rb") as stream:
            content = stream.read(MAX_CONFIG_BYTES + 1)
    except OSError as error:
        raise ConfigError("Cannot read configuration file; check the path and permissions") from error
    if len(content) > MAX_CONFIG_BYTES:
        raise ConfigError("Configuration file exceeds the 64 KiB limit")
    try:
        data = yaml.load(content.decode("utf-8"), Loader=_SelectionLoader)
    except UnicodeError as error:
        raise ConfigError("Configuration file must use UTF-8 encoding") from error
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ConfigError(f"Invalid YAML configuration{location}; use one plain YAML document") from error
    return normalize_selection(data, supported_version)