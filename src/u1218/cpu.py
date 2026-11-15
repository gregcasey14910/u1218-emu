"""UNIVAC 1218 machine state.

For now this holds only what the CPU drawer of the control panel displays and
alters; the fetch/execute loop comes with the repertoire.

Register names follow the panel photo (docs/1218_panel_labels.md). The middle
pair (Q, X) is a provisional reading of the photo and may be renamed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# (name, width in bits), in panel order: top pair, middle pair, lower pair.
REGISTERS: tuple[tuple[str, int], ...] = (
    ("AU", 18), ("AL", 18),
    ("Q", 18), ("X", 18),
    ("S", 15), ("P", 15),
)
WIDTH = dict(REGISTERS)

SEQUENCES = ("I", "B", "R", "W", "SQ", "HC", "RW", "WAIT")
MODES = ("OPER STEP", "PHASE STEP", "SEQ STEP", "RUN")
PHASES = 4
FUNCTION_BITS = 6          # f, bits 17-12 of the instruction


@dataclass
class CPU:
    regs: dict[str, int] = field(default_factory=lambda: {name: 0 for name, _ in REGISTERS})
    function_code: int = 0     # U register function code f (6 bits)
    format2: bool = False      # FORMAT II lamp: the current instruction is Format II (f = 50)
    sequence: str | None = None
    mode: str = "RUN"
    phase: int = 0             # bit mask of the PHASE lamps
    clock_speed: int = 50      # % of full speed, from the panel knob

    def get(self, name: str) -> int:
        return self.regs[name]

    def set(self, name: str, value: int) -> None:
        self.regs[name] = value & ((1 << WIDTH[name]) - 1)

    def flip_bit(self, name: str, bit: int) -> None:
        self.set(name, self.regs[name] ^ (1 << bit))

    def clear(self, name: str) -> None:
        self.regs[name] = 0

    @property
    def a(self) -> int:
        """The 36-bit accumulator A = AU:AL."""
        return (self.regs["AU"] << 18) | self.regs["AL"]

    @a.setter
    def a(self, value: int) -> None:
        self.set("AU", value >> 18)
        self.set("AL", value)
