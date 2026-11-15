"""UNIVAC 1218 instruction words: encode, decode, disassemble, and a small assembler.

    Format I   | 17 - f - 12 | 11 ------ u ------ 0 |
    Format II  | 17 - f - 12 | 11 - m - 6 | 5 - k - 0 |     (f = 50)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .repertoire import ALIASES, BY_MNEMONIC, FAULT_CODES, lookup
from .word import MASK

U_MASK = 0o7777
ADDRESS_MASK = 0o77777          # 15-bit addresses (32K words)
CONSTANT_CODES = (0o36, 0o37, 0o70, 0o71)   # u is a sign-extended constant


def encode_i(f: int, u: int) -> int:
    return ((f & 0o77) << 12) | (u & U_MASK)


def encode_ii(m: int, k: int = 0) -> int:
    return (0o50 << 12) | ((m & 0o77) << 6) | (k & 0o77)


def fields(word: int) -> tuple[int, int, int, int]:
    """(f, u, m, k) of an instruction word."""
    return (word >> 12) & 0o77, word & U_MASK, (word >> 6) & 0o77, word & 0o77


def sign_extend_u(u: int) -> int:
    """A 12-bit ones' complement constant extended to 18 bits."""
    u &= U_MASK
    return u | 0o770000 if u & 0o4000 else u


def disassemble(word: int) -> str:
    word &= MASK
    f, u, m, k = fields(word)
    entry = lookup(word)
    if entry is None:
        if f in FAULT_CODES or (f == 0o50 and m in FAULT_CODES):
            return "FAULT"
        return "(not used)" if f == 0o50 else "FAULT"
    if entry.m is None:
        return f"{entry.mnemonic} {u:04o}"
    if entry.mnemonic in ("CPAL", "CPAU", "CPA", "RND", "SKPNBO", "SKPOV", "SKPNOV", "SKPODD",
                          "SKPEVN", "RIL", "RXL", "SIL", "SXL", "WTFI"):
        return entry.mnemonic
    return f"{entry.mnemonic} {k:02o}"


def encode(mnemonic: str, operand: int = 0) -> int:
    """Encode one instruction by mnemonic: Format I operand = u, Format II operand = k."""
    name = ALIASES.get(mnemonic.upper(), mnemonic.upper())
    entry = BY_MNEMONIC.get(name)
    if entry is None:
        raise ValueError(f"unknown mnemonic {mnemonic!r}")
    if entry.m is None:
        return encode_i(entry.f, operand)
    return encode_ii(entry.m, operand)


@dataclass
class Assembler:
    """Two-pass assembler for generated code.

    ``op(mnemonic, operand)`` where operand is an int or a label name (with an
    optional ``+n`` offset given as ``(label, n)``); ``word(value)`` emits data;
    ``label(name)`` defines a label at the current address. ``assemble()``
    resolves labels and returns the words starting at ``origin``.
    """

    origin: int = 0
    items: list = field(default_factory=list)       # (kind, a, b, comment)
    labels: dict[str, int] = field(default_factory=dict)

    @property
    def address(self) -> int:
        return self.origin + len(self.items)

    def label(self, name: str) -> int:
        if name in self.labels:
            raise ValueError(f"duplicate label {name}")
        self.labels[name] = self.address
        return self.address

    def op(self, mnemonic: str, operand: int | str | tuple[str, int] = 0,
           comment: str = "") -> int:
        address = self.address
        self.items.append(("op", mnemonic, operand, comment))
        return address

    def word(self, value: int | str | tuple[str, int], comment: str = "") -> int:
        address = self.address
        self.items.append(("word", None, value, comment))
        return address

    def resolve(self, operand: int | str | tuple[str, int]) -> int:
        if isinstance(operand, int):
            return operand
        name, offset = (operand, 0) if isinstance(operand, str) else operand
        if name not in self.labels:
            raise ValueError(f"undefined label {name}")
        return self.labels[name] + offset

    def assemble(self) -> list[int]:
        words = []
        for kind, mnemonic, operand, _ in self.items:
            value = self.resolve(operand)
            if kind == "op":
                entry = BY_MNEMONIC[ALIASES.get(mnemonic, mnemonic)]
                if entry.m is None:
                    if entry.f in CONSTANT_CODES:
                        value &= U_MASK
                    elif value > U_MASK and isinstance(operand, (str, tuple)):
                        value &= U_MASK          # label in a higher bank: u = low 12 bits
                    words.append(encode_i(entry.f, value))
                else:
                    words.append(encode_ii(entry.m, value))
            else:
                words.append(value & MASK)
        return words

    def comments(self) -> list[str]:
        return [item[3] for item in self.items]
