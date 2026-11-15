# u1218 — UNIVAC 1218 emulator

A Python emulator of the US Navy **UNIVAC 1218** (CP-789) computer, following the
same plan as the AN/UYK-7 project (`../UYK7`, github.com/gregcasey14910/uyk7-emu):

1. instruction-level emulation of the full repertoire,
2. a Tkinter front panel with live lamps, switches and register display,
3. a small BASIC compiler that generates 1218 machine code.

## Status

Environment set up; research started. See [docs/1218_research.md](docs/1218_research.md)
for what is known so far and [docs/sources.md](docs/sources.md) for the archived manuals.

## Layout

```
src/u1218/
  word.py      18-bit / 36-bit ones' complement helpers
  widgets.py   drawn panel widgets (lamps, toggles, knob...) carried over from UYK7
  cli.py       command-line entry point
tests/         pytest suite
docs/          manuals, repertoire cards, research notes
```

## Setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```
