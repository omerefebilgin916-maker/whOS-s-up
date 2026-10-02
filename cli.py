"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __app_name__, __tagline__, __version__
from .privacy import safe_error_message

MIN_INTERVAL = 0.2


def _interval(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid number: {value!r}")
    if number < MIN_INTERVAL:
        raise argparse.ArgumentTypeError(f"interval must be at least {MIN_INTERVAL} seconds")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whosup",
        description=f"{__app_name__} {__tagline__}: what is my computer doing right now?",
    )
    parser.add_argument("--version", action="version", version=f"{__app_name__} {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="{watch,version,export}")

    watch = sub.add_parser("watch", help="live system monitor (Ctrl+C to quit)")
    watch.add_argument("--interval", type=_interval, default=1.0, metavar="SECONDS",
                       help="refresh interval in seconds (default: 1)")

    sub.add_parser("version", help="show version information")

    export = sub.add_parser("export", help="save a one-time snapshot to a file")
    fmt = export.add_mutually_exclusive_group(required=True)
    fmt.add_argument("--md", action="store_true", help="export as Markdown")
    fmt.add_argument("--txt", action="store_true", help="export as plain text")
    export.add_argument("--output", "-o", metavar="FILE",
                        help="output file (default: whosup-YYYY-MM-DD-HHMMSS.<ext>)")
    return parser


def _run_export(args: argparse.Namespace) -> int:
    from .export import write_export
    from .system import take_snapshot

    snapshot = take_snapshot()
    path = write_export(snapshot, "md" if args.md else "txt", args.output)
    print(f"Snapshot saved: {path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "version":
            print(f"{__app_name__} v{__version__}\n{__tagline__}")
            return 0
        if args.command == "export":
            return _run_export(args)
        if args.command == "watch":
            from .ui import run_watch
            return run_watch(args.interval)
        from .ui import show_once
        show_once()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as error:  # last line of defence: no traceback, no paths
        print(f"whosup: {safe_error_message(error)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
