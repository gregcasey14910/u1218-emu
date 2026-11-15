"""Command-line entry point: opens the emulator window."""

from __future__ import annotations

import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="u1218", description="UNIVAC 1218 emulator")
    parser.add_argument("--version", action="version", version=f"u1218 {__version__}")
    parser.add_argument("--panel", action="store_true", help="also open the CPU drawer panel")
    parser.add_argument("--panel-only", action="store_true", help="open only the panel")
    parser.add_argument("--basic", metavar="FILE", help="open a BASIC program in the editor")
    args = parser.parse_args(argv)
    if args.panel_only:
        from .panel import main as panel_main
        panel_main()
        return 0
    from .gui import main as gui_main
    gui_main(basic_file=args.basic, panel=args.panel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
