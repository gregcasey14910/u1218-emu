"""Command-line entry point (placeholder until the CPU is built)."""

from __future__ import annotations

import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="u1218", description="UNIVAC 1218 emulator")
    parser.add_argument("--version", action="version", version=f"u1218 {__version__}")
    parser.parse_args(argv)
    print("UNIVAC 1218 emulator: scaffold only (CPU, panel and BASIC to come).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
