# tui/main.py — entry point for the EdgePack TUI
#
# Run from the ui/ directory:  python -m tui
#
# SPDX-License-Identifier: MIT

import argparse
from contextlib import redirect_stdout
import json
import os
import sys

# Ensure ui/ (the parent of both tui/ and edgepack_shared/) is on sys.path
# when this module is executed directly, so edgepack_shared is importable.
_UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _UI_DIR not in sys.path:
    sys.path.insert(0, _UI_DIR)


def _cli_error(args, code: int, error_code: str, message: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps({
            "schema_version": 1, "command": args.command, "status": "error",
            "dry_run": getattr(args, "dry_run", False), "exit_code": code,
            "selection": None, "host": None, "plan": None,
            "errors": [{"code": error_code, "message": message}],
            "restart_recommended": False,
        }))
    else:
        print(f"error: {message}", file=sys.stderr)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    options = argv[:argv.index("--")] if "--" in argv else argv
    args = argparse.Namespace(
        command=next((value for value in options if value in {"list", "install"}), None),
        json="--json" in options, dry_run="--dry-run" in options,
    )

    class CliParser(argparse.ArgumentParser):
        def __init__(self, *parser_args, **kwargs):
            kwargs["allow_abbrev"] = False
            super().__init__(*parser_args, **kwargs)

        def error(self, message):
            if not args.json:
                self.print_usage(sys.stderr)
            _cli_error(args, 2, "invalid_arguments", message)
            self.exit(2)

    parser = CliParser(description="Intel EdgePack TUI and CLI Installer")
    parser.add_argument(
        "--debug-level",
        type=str,
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "MUTE"],
        default="MUTE",
        help=argparse.SUPPRESS,  # dev-only flag, hidden from customer help output
    )
    # Debug level 0 : show all events
    # Debug level 1 : show debug level and higher level events (correspond to level 10 in )
    # Debug level 2 : show info and higher level level events (20)

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser(
        "list", help="List available base profiles and add-on profiles, then exit",
    )
    list_parser.add_argument("--json", action="store_true", help="Print a JSON result")

    install_parser = subparsers.add_parser(
        "install",
        help="Install a base profile (+ optional add-ons) without the TUI wizard",
    )
    install_parser.add_argument(
        "base_profile", nargs="?", help="Base profile key to install, e.g. base-standard (see 'list')",
    )
    install_parser.add_argument(
        "addons", nargs="*", help="Optional add-on profile keys to install alongside the base profile",
    )

    install_parser.add_argument("--config", metavar="FILE", help="Read wizard selections from a YAML file instead of positional profiles")
    install_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without changing the system (no root required)")
    install_parser.add_argument("--json", action="store_true", help="Print one JSON result to stdout; stream installation output to stderr")

    args = parser.parse_args(argv)
    if args.command == "install":
        if args.config is not None and (args.base_profile is not None or args.addons):
            parser.error("Use either --config or positional profiles, not both")
        if args.config is None and args.base_profile is None:
            parser.error("install requires a base profile or --config FILE")

    # Debug mode is disabled by default (MUTE). To enable it, the caller must
    # explicitly set EDGEPACK_DEBUG=1 — prevents accidental or accidental-by-path
    # information leakage from debug-level log output.
    if args.debug_level != "MUTE" and os.environ.get("EDGEPACK_DEBUG") != "1":
        _cli_error(args, 1, "debug_disabled", "debug mode requires EDGEPACK_DEBUG=1 environment variable")
        sys.exit(1)

    # Global handler: any unhandled exception below is reported as a single
    # generic line (no traceback/paths) instead of a raw Python crash dump.
    try:
        if args.command == "list":
            from edgepack_shared.processor import Processor
            from .cli import list_command
            list_command(Processor.load(), json_output=args.json)
            return

        if args.command == "install":
            from .cli import install_command
            sys.exit(install_command(args))

        # Deferred: textual (and its dependencies) is only required for the TUI itself,
        # not for the 'list'/'install' CLI paths above — keeps those usable under sudo,
        # which drops the invoking user's site-packages (no user-local textual install).
        from .app import EdgePackTUI
        EdgePackTUI(debug_level=args.debug_level).run()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        if args.command:
            _cli_error(args, 130, "interrupted", "Installer interrupted; any started package operation may still need attention")
        sys.exit(130)
    except Exception:
        # Log the full traceback internally (with paths and stack) but show the
        # user a generic message to avoid leaking internal paths or module names.
        import logging
        with redirect_stdout(sys.stderr):
            logging.getLogger("tui_log").exception("Unexpected error during installer run")
        _cli_error(args, 1, "unexpected_error", "edgepack-installer encountered an unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    main()
