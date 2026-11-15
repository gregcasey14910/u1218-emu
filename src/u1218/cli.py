"""Command-line entry point (placeholder until the CPU is built)."""

from __future__ import annotations

import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="u1218", description="UNIVAC 1218 emulator")
    parser.add_argument("--version", action="version", version=f"u1218 {__version__}")
    parser.add_argument("--panel", action="store_true", help="open the CPU drawer panel")
    args = parser.parse_args(argv)
    if args.panel:
        from .panel import main as panel_main
        panel_main()
        return 0
    print("UNIVAC 1218 emulator: CPU and BASIC to come; try --panel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
