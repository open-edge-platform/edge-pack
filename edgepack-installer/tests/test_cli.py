import io
import argparse
import json
import itertools
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import sys
import types
import unittest
from unittest.mock import patch

from edgepack_shared.user_config import (
    ConfigError, InstallationSelection, MAX_CONFIG_BYTES, load_selection,
    normalize_selection,
)
from edgepack_shared.processor import Processor
from tui import cli
from tui.main import main
from tui.package_logic import build_pkg_entries, collect_selected_packages, required_prerequisites


class UserConfigTests(unittest.TestCase):
    def load_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "choices.yml"
            path.write_text(text, encoding="utf-8")
            return load_selection(str(path), "2026.2")

    def test_profile_only_defaults(self):
        self.assertEqual(
            self.load_text("base_profile: base-standard\n"),
            InstallationSelection("base-standard", (), "2026.2"),
        )

    def test_optional_fields_and_deduplication(self):
        self.assertEqual(
            self.load_text('schema_version: 1\nbase_profile: base-standard\n'
                           'edgepack_version: "2026.2"\naddons: [ffmpeg, npu, ffmpeg]\n'),
            InstallationSelection("base-standard", ("ffmpeg", "npu"), "2026.2"),
        )

    def test_all_optional_field_combinations(self):
        optional = {"schema_version": 1, "edgepack_version": "2026.2", "addons": []}
        for count in range(4):
            for fields in itertools.combinations(optional, count):
                with self.subTest(fields=fields):
                    data = {"base_profile": "base-standard", **{key: optional[key] for key in fields}}
                    self.assertEqual(normalize_selection(data, "2026.2"),
                                     InstallationSelection("base-standard", (), "2026.2"))

    def test_invalid_documents(self):
        documents = [
            "", "null", "[]", "base_profile: [", "addons: []",
            "base_profile: null", "base_profile: 123", "base_profile: ''",
            "base_profile: bad/key", "base_profile: " + "a" * 129,
            "base_profile: base-standard\naddons: npu",
            "base_profile: base-standard\naddons: null",
            "base_profile: base-standard\naddons: [true]",
            "base_profile: base-standard\nschema_version: true",
            "base_profile: base-standard\nschema_version: 2",
            "base_profile: base-standard\nschema_version: 1.0",
            "base_profile: base-standard\nedgepack_version: 2026.2",
            'base_profile: base-standard\nedgepack_version: "2025.1"',
            "base_profile: base-standard\nreboot: true",
            "base_profile: base-standard\nbase_profile: base-realtime",
            "base_profile: base-standard\n---\naddons: []",
            "base_profile: &base base-standard\naddons: [*base]",
            "base_profile: !!python/object/apply:os.system ['false']",
            "base_profile: base-standard\n? [bad, key]\n: value",
            "base_profile: base-standard\naddons: " + "[" * 20 + "]" * 20,
        ]
        for text in documents:
            with self.subTest(text=text), self.assertRaises(ConfigError):
                self.load_text(text)

    def test_read_failures(self):
        with patch("pathlib.Path.open", side_effect=PermissionError), self.assertRaises(ConfigError):
            load_selection("choices.yml", "2026.2")
        with patch("pathlib.Path.open", return_value=io.BytesIO(b"\xff")), self.assertRaises(ConfigError):
            load_selection("choices.yml", "2026.2")
        with self.assertRaises(ConfigError):
            self.load_text(" " * (MAX_CONFIG_BYTES + 1))

    def test_positional_normalization_matches_yaml(self):
        self.assertEqual(
            normalize_selection({"base_profile": "base-standard", "addons": ["ffmpeg"]}, "2026.2"),
            self.load_text("base_profile: base-standard\naddons: [ffmpeg]"),
        )


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.processor = Processor.load()
        self.host = {
            "platform_key": "ptl", "platform_entry": self.processor.entry("platforms", "ptl"),
            "os_key": "ubuntu_noble", "os_entry": self.processor.entry("os_variant", "ubuntu_noble"),
            "issues": [],
        }

    def run_install(self, **overrides):
        args = argparse.Namespace(
            base_profile="base-standard", addons=[], config=None, dry_run=True, json=True,
        )
        for key, value in overrides.items():
            setattr(args, key, value)
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(cli, "_check_host_requirements", return_value=self.host), \
             patch.object(cli.os, "geteuid", return_value=1000), \
             patch.object(cli, "run_install") as install, \
             redirect_stdout(output), redirect_stderr(errors):
            code = cli.install_command(args)
        install.assert_not_called()
        return code, json.loads(output.getvalue()), errors.getvalue()

    def test_preview_matches_tui(self):
        for os_key, addons in (("ubuntu_noble", ["npu", "ffmpeg"]),
                               ("ubuntu_resolute", ["gstreamer", "manageability"])):
            for platform_key in ("ptl", "wcl"):
                with self.subTest(os=os_key, platform=platform_key):
                    self.host.update(platform_key=platform_key, os_key=os_key,
                                     os_entry=self.processor.entry("os_variant", os_key))
                    code, result, errors = self.run_install(addons=addons)
                    self.assertEqual(code, 0)
                    self.assertEqual(errors, "")
                    self.assertFalse(result["restart_recommended"])
                    entries = build_pkg_entries(self.processor, "base-standard", addons, platform_key, os_key)
                    self.assertEqual(result["plan"]["packages"], list(collect_selected_packages(entries)))
                    self.assertEqual(result["plan"]["prerequisites"], required_prerequisites(
                        self.processor, ["base-standard", *addons], os_key))
                    expected_hidden = list(dict.fromkeys(
                        name for key in ["base-standard", *addons]
                        for name in self.processor.hidden_os_packages(key, platform_key, os_key)
                    ))
                    self.assertEqual(result["plan"]["additional_os_packages"], expected_hidden)

    def test_yaml_and_positional_plans_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "choices.yml"
            path.write_text("base_profile: base-standard\naddons: [ffmpeg]", encoding="utf-8")
            yaml_result = self.run_install(base_profile=None, config=str(path))[1]
            positional_result = self.run_install(addons=["ffmpeg"])[1]
        self.assertEqual(yaml_result, positional_result)

    def test_validation_errors_do_not_install(self):
        for overrides, expected in (
            ({"base_profile": None}, 2),
            ({"base_profile": "unknown"}, 2),
            ({"addons": ["unknown"]}, 2),
            ({"config": "choices.yml"}, 2),
            ({"base_profile": "base-realtime"}, 3),
            ({"dry_run": False}, 1),
        ):
            with self.subTest(overrides=overrides):
                code, result, _ = self.run_install(**overrides)
                self.assertEqual(code, expected)
                self.assertEqual(result["exit_code"], code)
                self.assertEqual(result["status"], "error")
                self.assertFalse(result["restart_recommended"])

    def test_unsupported_host(self):
        self.host["issues"] = ["Unsupported CPU", "Unsupported kernel"]
        code, result, _ = self.run_install()
        self.assertEqual(code, 4)
        self.assertEqual(result["errors"][0]["code"], "unsupported_host")

    def test_dry_run_has_no_privileged_or_write_operations(self):
        args = argparse.Namespace(base_profile="base-standard", addons=[], dry_run=True, json=True)
        with patch.object(cli, "_check_host_requirements", return_value=self.host), \
             patch.object(cli.Processor, "load", return_value=self.processor), \
             patch.object(cli.os, "geteuid", side_effect=AssertionError("root check")), \
             patch("subprocess.Popen", side_effect=AssertionError("subprocess")), \
             patch("builtins.open", side_effect=AssertionError("file access")), \
             patch.object(cli, "run_install", side_effect=AssertionError("installation")), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(cli.install_command(args), 0)

    def test_host_checks_use_actual_compatibility_rules(self):
        for cpu, os_info, kernel, ubuntu_kernel, valid in (
            ("Intel Core Ultra 338H", {"VERSION_ID": "24.04", "VERSION": "24.04.4"}, "7.0.0-generic", True, True),
            ("Intel Core Ultra 305", {"VERSION_ID": "26.04", "VERSION": "26.04.0"}, "7.0.0-generic", True, True),
            ("Unsupported CPU", {"VERSION_ID": "24.04"}, "7.0.0-generic", True, False),
            ("Intel Core Ultra 338H", {"VERSION_ID": "22.04"}, "7.0.0-generic", True, False),
            ("Intel Core Ultra 338H", {"VERSION_ID": "24.04"}, "6.8.0-generic", True, False),
            ("Intel Core Ultra 338H", {"VERSION_ID": "24.04"}, "7.0.0-custom", False, False),
        ):
            with self.subTest(cpu=cpu, os=os_info, kernel=kernel), \
                 patch.object(cli, "host_cpu_model", return_value=cpu), \
                 patch.object(cli, "read_os_release", return_value=os_info), \
                 patch.object(cli, "host_kernel_release", return_value=kernel), \
                 patch.object(cli, "host_kernel_is_ubuntu", return_value=ubuntu_kernel):
                self.assertEqual(not cli._check_host_requirements(self.processor)["issues"], valid)

    def test_npu_not_supported_on_resolute(self):
        self.host.update(os_key="ubuntu_resolute", os_entry=self.processor.entry("os_variant", "ubuntu_resolute"))
        code, result, _ = self.run_install(addons=["npu"])
        self.assertEqual(code, 3)
        self.assertEqual(result["errors"][0]["code"], "incompatible_addon")

    def test_execution_and_json_streams(self):
        for child_code in (0, 1, 100):
            with self.subTest(child_code=child_code):
                output, errors = io.StringIO(), io.StringIO()
                def execute(packages, repos, **kwargs):
                    kwargs["output_callback"]("apt output")
                    kwargs["finished_callback"](child_code)
                args = argparse.Namespace(base_profile="base-standard", addons=["npu"], dry_run=False, json=True)
                with patch.object(cli, "_check_host_requirements", return_value=self.host), \
                     patch.object(cli.os, "geteuid", return_value=0), \
                     patch.object(cli, "run_install", side_effect=execute) as install, \
                     redirect_stdout(output), redirect_stderr(errors):
                    code = cli.install_command(args)
                result = json.loads(output.getvalue())
                self.assertEqual(code, child_code)
                self.assertEqual(result["exit_code"], child_code)
                self.assertEqual(result["restart_recommended"], child_code == 0)
                self.assertEqual(errors.getvalue(), "apt output\n")
                install.assert_called_once()
                self.assertEqual(install.call_args.args[0], [(name, "") for name in result["plan"]["packages"]])
                self.assertEqual(install.call_args.kwargs["force_packages"], result["plan"]["additional_os_packages"])
                self.assertEqual(install.call_args.kwargs["prerequisites"], result["plan"]["prerequisites"])


class EntryPointTests(unittest.TestCase):
    def invoke(self, argv):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            try:
                main(argv)
            except SystemExit as error:
                code = error.code
            else:
                code = 0
        return code, output.getvalue(), errors.getvalue()

    def test_argument_errors_are_json(self):
        for argv in (
            ["install", "--json"],
            ["install", "--config", "choices.yml", "base-standard", "--json"],
            ["install", "--config", "--json"],
            ["install", "--wat", "--json"],
            ["list", "--wat", "--json"],
        ):
            with self.subTest(argv=argv), patch.object(cli, "run_install") as install:
                code, output, errors = self.invoke(argv)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output)["exit_code"], 2)
                self.assertEqual(errors, "")
                install.assert_not_called()

    def test_list_and_help(self):
        code, output, _ = self.invoke(["list", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("base-standard", json.loads(output)["profiles"]["base_profiles"])
        self.assertIn("ffmpeg", self.invoke(["list"])[1])
        code, output, _ = self.invoke(["install", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("--config", output)
        self.assertIn("--dry-run", output)

    def test_unexpected_error_and_interrupt(self):
        for error, expected in ((RuntimeError("internal failure"), 1), (KeyboardInterrupt(), 130)):
            with self.subTest(error=error), patch.object(cli, "install_command", side_effect=error):
                code, output, _ = self.invoke(["install", "base-standard", "--json"])
                self.assertEqual(code, expected)
                self.assertEqual(json.loads(output)["exit_code"], expected)

    def test_debug_errors_are_json(self):
        with patch.dict("os.environ", {"EDGEPACK_DEBUG": "0"}):
            code, output, _ = self.invoke(["--debug-level", "DEBUG", "list", "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["errors"][0]["code"], "debug_disabled")

    def test_no_arguments_still_launches_tui(self):
        from unittest.mock import Mock
        app_module = types.ModuleType("tui.app")
        app_module.EdgePackTUI = Mock()
        with patch.dict(sys.modules, {"tui.app": app_module}):
            code, _, _ = self.invoke([])
        self.assertEqual(code, 0)
        app_module.EdgePackTUI.return_value.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()