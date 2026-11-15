"""UNIVAC 1218 central processor.

Behaviour from PX 2910 section I-B (docs/PX2910_RevC_Ch2_1218_Programmers_Reference_Manual_Nov1969.pdf)
and the repertoire card. Summary of the machine as modelled:

* 18-bit words, ones' complement, subtractive adder (x - x = +0); A = AU:AL, 36 bits.
* Memory up to 32K words; 00200-00237 is the bootstrap NDRO, not writable by stores.
* Operand address y = u with bank bits from P (u_P), or from SR when SR is active
  (SR3 = 1) for the SR-sensitive instructions; the odd "B" instructions below 50
  add B (18-bit ones' complement) and keep the low 15 bits.
* B is the active index register, a core cell: ICR = 0 selects 00010, ICR = 1-7
  select 00001-00007.
* Designators: overflow (cleared only by SKPOV / SKPNOV), borrow (ADDA / SUBA),
  comparison designator (compare / less-than / equals; cleared by every
  instruction except the conditional jumps 60-67).
* Console: skip keys 0-4 (SKP), stop keys 0-4 (STOP), AUTO RECOVERY switch.
* I/O: eight channels with buffer control words in core (IN 60+2k, OUT 40+2k,
  EXF 20+2k). A device on a channel transfers the whole buffer at once. The
  console printer is on CONSOLE_CHANNEL and prints the low 7 bits of each word
  as ASCII (the real 1232 console used Fieldata).
* Interrupts are not modelled yet: WTFI stops the computer; the lockout
  instructions only set their designators.
* An illegal function code (00, 01, 77, 50 00, 50 01, 50 77) sets P to the
  fault entrance 00000 (or the bootstrap 00200 with AUTO RECOVERY up), lights
  FAULT and stops, so the fault can be seen.

Internal registers shown on the panel follow PX 2910 3.5.2: X (exchange: the
operand), D (arithmetic exchange: the result), S (memory address), Z (memory
buffer), F (function register: Format II bit + 6-bit code).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .isa import ADDRESS_MASK, CONSTANT_CODES, fields, sign_extend_u
from .repertoire import FAULT_CODES, FORMAT_II_DUPLICATES, NOT_USED_II, lookup
from .word import DOUBLE_MASK, MASK, SIGN, add, negate, sub, to_int

MEMORY_WORDS = 1 << 15
BOOTSTRAP = range(0o200, 0o240)
SCALE_FACTOR_CELL = 0o17
CONSOLE_CHANNEL = 7

# (name, width in bits), in panel order: top pair, middle pair, lower pair.
REGISTERS: tuple[tuple[str, int], ...] = (
    ("AU", 18), ("AL", 18),
    ("D", 18), ("X", 18),
    ("S", 15), ("P", 15),
)
WIDTH = dict(REGISTERS) | {"Z": 18}

SEQUENCES = ("I", "B", "R", "W", "SQ", "HC", "RW", "WAIT")
MODES = ("OPER STEP", "PHASE STEP", "SEQ STEP", "RUN")
PHASES = 4
FUNCTION_BITS = 6
RESTARTABLE = ("STOP", "STOP KEY", "WAIT FOR INTERRUPT", "FAULT", "PANEL STOP")


class Memory:
    def __init__(self, size: int = MEMORY_WORDS) -> None:
        self.size = size
        self.words = [0] * size

    def read(self, address: int) -> int:
        return self.words[address % self.size]

    def write(self, address: int, value: int, force: bool = False) -> None:
        """Store a word; stores into the bootstrap NDRO are ignored unless forced."""
        address %= self.size
        if address in BOOTSTRAP and not force:
            return
        self.words[address] = value & MASK

    def load(self, words: list[int], start: int = 0) -> None:
        for offset, word in enumerate(words):
            self.write(start + offset, word, force=True)

    def clear(self) -> None:
        self.words = [0] * self.size


class ConsolePrinter:
    """Output device: each word is one ASCII character (low 7 bits)."""

    def __init__(self) -> None:
        self.text = ""

    def output(self, word: int) -> None:
        code = word & 0x7F
        if code == 0:
            return
        self.text += "\n" if code in (0x0A, 0x0D) else chr(code)

    def clear(self) -> None:
        self.text = ""


@dataclass
class Channel:
    input_active: bool = False
    output_active: bool = False
    function_active: bool = False
    resume: bool = False
    device: ConsolePrinter | None = None


@dataclass
class CPU:
    mem: Memory = field(default_factory=Memory)
    regs: dict[str, int] = field(default_factory=lambda: {name: 0 for name in WIDTH})
    icr: int = 0
    sr: int = 0
    overflow: bool = False
    borrow: bool = False
    cd: tuple[bool, bool] | None = None   # comparison designator set: (less, equal)
    function_code: int = 0                # F register, low 6 bits
    format2: bool = False                 # F register, Format II bit
    skip_keys: int = 0                    # console skip keys 0-4 (bit mask)
    stop_keys: int = 0                    # console stop keys 0-4 (bit mask)
    auto_recovery: bool = False
    interrupt_lockout: bool = False
    external_lockout: bool = False
    halted: bool = False
    stop_reason: str = ""
    fault: bool = False
    skip_light: int = 0                   # keys that caused the last skip / stop
    stop_light: int = 0
    cycles: int = 0                       # instructions executed
    micros: float = 0.0                   # execution time, microseconds
    sequence: str | None = None
    sequences: list[str] = field(default_factory=list)
    mode: str = "RUN"
    phase: int = 0
    clock_speed: int = 50
    channels: list[Channel] = field(default_factory=lambda: [Channel() for _ in range(8)])
    console: ConsolePrinter = field(default_factory=ConsolePrinter)

    def __post_init__(self) -> None:
        self.channels[CONSOLE_CHANNEL].device = self.console

    # ------------------------------------------------------------ registers

    def get(self, name: str) -> int:
        return self.regs[name]

    def set(self, name: str, value: int) -> None:
        self.regs[name] = value & ((1 << WIDTH[name]) - 1)

    def flip_bit(self, name: str, bit: int) -> None:
        self.set(name, self.regs[name] ^ (1 << bit))

    def clear(self, name: str) -> None:
        self.regs[name] = 0

    @property
    def p(self) -> int:
        return self.regs["P"]

    @p.setter
    def p(self, value: int) -> None:
        self.regs["P"] = value & ADDRESS_MASK

    @property
    def au(self) -> int:
        return self.regs["AU"]

    @au.setter
    def au(self, value: int) -> None:
        self.regs["AU"] = value & MASK

    @property
    def al(self) -> int:
        return self.regs["AL"]

    @al.setter
    def al(self, value: int) -> None:
        self.regs["AL"] = value & MASK

    @property
    def a(self) -> int:
        """The 36-bit accumulator A = AU:AL."""
        return (self.regs["AU"] << 18) | self.regs["AL"]

    @a.setter
    def a(self, value: int) -> None:
        value &= DOUBLE_MASK
        self.au, self.al = value >> 18, value

    def index_address(self, icr: int | None = None) -> int:
        """Core address of an index register: ICR 0 -> 00010, 1-7 -> 00001-00007."""
        icr = self.icr if icr is None else icr
        return 0o10 if icr == 0 else icr

    @property
    def b(self) -> int:
        return self.mem.read(self.index_address())

    @b.setter
    def b(self, value: int) -> None:
        self.mem.write(self.index_address(), value)

    @property
    def sr_active(self) -> bool:
        return bool(self.sr & 0o10)

    # ------------------------------------------------------------ control

    def reset(self, start: int = 0) -> None:
        """MASTER CLEAR: registers and designators cleared, P = start."""
        for name in self.regs:
            self.regs[name] = 0
        self.p = start
        self.icr = self.sr = 0
        self.overflow = self.borrow = False
        self.cd = None
        self.function_code, self.format2 = 0, False
        self.interrupt_lockout = self.external_lockout = False
        self.halted, self.stop_reason, self.fault = False, "", False
        self.skip_light = self.stop_light = 0
        self.cycles, self.micros = 0, 0.0
        self.sequence, self.sequences, self.phase = None, [], 0
        for channel in self.channels:
            channel.input_active = channel.output_active = channel.function_active = False
            channel.resume = False

    def stop(self, reason: str) -> None:
        self.halted = True
        self.stop_reason = reason

    def restart(self) -> None:
        """Continue after a stop, a stop key, WTFI or a fault."""
        if self.halted and self.stop_reason in RESTARTABLE:
            self.halted = False
            self.stop_reason = ""
            self.stop_light = 0
            self.fault = False

    def run(self, max_steps: int | None = None) -> int:
        steps = 0
        while not self.halted and (max_steps is None or steps < max_steps):
            self.step()
            steps += 1
        return steps

    # ------------------------------------------------------------ memory helpers

    def read(self, address: int) -> int:
        address &= ADDRESS_MASK
        word = self.mem.read(address)
        self.regs["S"], self.regs["Z"] = address, word
        return word

    def write(self, address: int, value: int) -> None:
        address &= ADDRESS_MASK
        self.regs["S"], self.regs["Z"] = address, value & MASK
        self.mem.write(address, value)

    def operand_address(self, entry, u: int, here: int) -> int:
        """y = u_P or u_SR, plus B for the B-modified instructions."""
        bank = (self.sr & 0o7) if (entry.sr and self.sr_active) else (here >> 12) & 0o7
        y = (bank << 12) | u
        if entry.b_mod:
            self.sequences.append("B")
            y = add(y, self.b)
        return y & ADDRESS_MASK

    # ------------------------------------------------------------ execution

    def step(self) -> None:
        if self.halted:
            return
        here = self.p
        self.sequences = ["I"]
        word = self.read(here)
        self.p = here + 1
        f, u, m, k = fields(word)
        self.format2 = f == 0o50
        self.function_code = m if self.format2 else f
        compare_before = self.cd
        self.skip_light = 0
        entry = lookup(word)
        time = 4.0
        if entry is None:
            if f in FAULT_CODES or (f == 0o50 and m in FAULT_CODES):
                self._fault(here)
            # else a not-used Format II code: 4 usec, no operation
            self.cd = None
        elif f == 0o50:
            time = self._format_ii(FORMAT_II_DUPLICATES.get(m, m), k, entry)
            self.cd = None
        else:
            time = self._format_i(f, u, entry, here, compare_before)
        self.cycles += 1
        self.micros += time
        self.phase = 1 << (self.cycles % PHASES)
        if self.halted and self.stop_reason == "WAIT FOR INTERRUPT":
            self.sequences.append("WAIT")
        self.sequence = self.sequences[-1]

    def _fault(self, _here: int) -> None:
        self.fault = True
        self.p = 0o200 if self.auto_recovery else 0
        self.stop("FAULT")

    def _skip(self, condition: bool) -> float:
        if condition:
            self.p = self.p + 1
            return 6.0
        return 4.67

    @staticmethod
    def _base_time(entry) -> float:
        try:
            return float(entry.time.split("/")[0].split("+")[0].split("-")[0])
        except ValueError:
            return 4.0

    # ------------------------------------------------------------ Format I

    def _format_i(self, f: int, u: int, entry, here: int,
                  compare_before: tuple[bool, bool] | None) -> float:
        time = self._base_time(entry)
        if f in CONSTANT_CODES:
            constant = sign_extend_u(u)
            if f == 0o36:                               # ENTBK
                self.b = constant
            elif f == 0o37:                             # ENTBKB
                self.b = add(self.b, constant)
            elif f == 0o70:                             # ENTALK
                self.al = constant
            else:                                       # ADDALK
                self.al = self._add18(self.al, constant)
            self.regs["X"] = constant
            self.cd = None
            return time
        y = self.operand_address(entry, u, here)
        base = f & ~1 if f < 0o50 else f                # the plain form of a "B" instruction
        if 0o60 <= f <= 0o67:
            if self._jump_condition(f, compare_before):
                self.p = y
            return time
        self.cd = None
        handler = getattr(self, f"_op_{base:02o}", None)
        if handler is None:
            raise NotImplementedError(f"function {f:02o}")
        handler(y)
        return time

    def _operand(self, y: int) -> int:
        self.sequences.append("R")
        value = self.read(y)
        self.regs["X"] = value
        return value

    def _store(self, y: int, value: int) -> None:
        self.sequences.append("W")
        self.write(y, value)

    def _result(self, value: int) -> int:
        self.regs["D"] = value & MASK
        return value

    def _add18(self, a: int, b: int) -> int:
        result = add(a, b)
        if not ((a ^ b) & SIGN) and ((a ^ result) & SIGN):
            self.overflow = True
        return self._result(result)

    def _sub18(self, a: int, b: int) -> int:
        result = sub(a, b)
        if ((a ^ b) & SIGN) and ((a ^ result) & SIGN):
            self.overflow = True
        return self._result(result)

    def _compare(self, left: int, right: int) -> None:
        a, b = to_int(left), to_int(right)
        self.cd = (a < b, a == b)

    # logical / compare
    def _op_02(self, y):                                # CMAL
        self._compare(self.al, self._operand(y))

    def _op_04(self, y):                                # SLSU
        self.al = self._result((self.al & ~self.au) | (self._operand(y) & self.au))

    def _op_06(self, y):                                # CMSK
        self._compare(self.al & self.au, self._operand(y) & self.au)

    def _op_51(self, y):                                # SLSET
        self.al = self._result(self.al | self._operand(y))

    def _op_52(self, y):                                # SLCL
        self.al = self._result(self.al & self._operand(y))

    def _op_53(self, y):                                # SLCP
        self.al = self._result(self.al ^ self._operand(y))

    # enter / store
    def _op_10(self, y):                                # ENTAU
        self.au = self._operand(y)

    def _op_12(self, y):                                # ENTAL
        self.al = self._operand(y)

    def _op_32(self, y):                                # ENTB
        self.b = self._operand(y)

    def _op_40(self, y):                                # CL
        self._store(y, 0)

    def _op_42(self, y):                                # STRB
        self._store(y, self.b)

    def _op_44(self, y):                                # STRAL
        self._store(y, self.al)

    def _op_46(self, y):                                # STRAU
        self._store(y, self.au)

    def _op_72(self, y):                                # STRICR
        self.sequences.append("RW")
        self.write(y, (self.read(y) & ~0o77) | self.index_address())

    def _op_74(self, y):                                # STRADR
        self.sequences.append("RW")
        self.write(y, (self.read(y) & ~0o7777) | (self.al & 0o7777))

    def _op_75(self, y):                                # STRSR
        self.sequences.append("RW")
        self.write(y, (self.read(y) & ~0o77) | (self.sr & 0o17))
        self.sr = 0

    # arithmetic
    def _op_14(self, y):                                # ADDAL
        self.al = self._add18(self.al, self._operand(y))

    def _op_16(self, y):                                # SUBAL
        self.al = self._sub18(self.al, self._operand(y))

    def _double(self, y: int) -> int:
        low = self._operand(y)
        high = self._operand(y + 1)
        return (high << 18) | low

    def _add36(self, a: int, b: int, subtract: bool) -> None:
        """36-bit add / subtract: any end-around borrow is blocked and recorded in
        the borrow designator, leaving A uncorrected (PX 2910, ADDA note)."""
        operand = b if subtract else negate(b, 36)
        result = a - operand
        self.borrow = result < 0
        if self.borrow:
            result += 1 << 36
        sa, sb, sr = a >> 35, (b >> 35) ^ subtract, result >> 35
        if sa == sb and sr != sa:
            self.overflow = True
        self.a = result
        self.regs["D"] = self.al

    def _op_20(self, y):                                # ADDA
        self._add36(self.a, self._double(y), subtract=False)

    def _op_22(self, y):                                # SUBA
        self._add36(self.a, self._double(y), subtract=True)

    def _op_24(self, y):                                # MULAL
        multiplier = self._operand(y)
        negative = bool((self.al ^ multiplier) & SIGN)
        product = abs(to_int(self.al)) * abs(to_int(multiplier))
        self.a = negate(product, 36) if negative else product
        self.regs["D"] = self.al

    def _op_26(self, y):                                # DIVA
        divisor_word = self._operand(y)
        dividend_negative = bool(self.a >> 35)
        divisor, dividend = to_int(divisor_word), to_int(self.a, 36)
        if divisor == 0 or abs(dividend) // abs(divisor) > 0o377777:
            self.overflow = True
            self.al = 0
            return
        quotient, remainder = divmod(abs(dividend), abs(divisor))
        negative_q = dividend_negative != bool(divisor_word & SIGN)
        self.al = negate(quotient) if negative_q else quotient
        self.au = negate(remainder) if dividend_negative else remainder
        self.regs["D"] = self.al

    # jumps and modifying
    def _op_30(self, y):                                # IRJP
        target = self.read(y) & ADDRESS_MASK
        self._store(target, self.p)
        self.p = target + 1

    def _op_34(self, y):                                # JP
        self.p = y

    def _op_54(self, y):                                # IJPEI
        self.interrupt_lockout = False
        self.p = self._operand(y) & ADDRESS_MASK

    def _op_55(self, y):                                # IJP
        self.p = self._operand(y) & ADDRESS_MASK

    def _op_76(self, y):                                # RJP
        self._store(y, self.p)
        self.p = y + 1

    def _op_56(self, y):                                # BSK
        if self.b == self._operand(y):
            self.p = self.p + 1
        else:
            self.b = add(self.b, 1)

    def _op_57(self, y):                                # ISK
        value = self._operand(y)
        if value == 0:
            self.p = self.p + 1
        else:
            self.sequences.append("RW")
            self.write(y, sub(value, 1))

    def _op_73(self, y):                                # BJP
        if self.b != 0:
            self.b = sub(self.b, 1)
            self.p = y

    def _jump_condition(self, f: int, cd: tuple[bool, bool] | None) -> bool:
        register = self.au if f % 2 == 0 else self.al
        group = (f - 0o60) // 2         # 0 zero/equal, 1 not zero, 2 positive, 3 negative
        if cd is not None:
            less, equal = cd
            return (equal, not equal, not less, less)[group]
        return (register == 0, register != 0, not register & SIGN,
                bool(register & SIGN))[group]

    # ------------------------------------------------------------ Format II

    def _format_ii(self, m: int, k: int, entry) -> float:
        time = self._base_time(entry)
        channel = self.channels[k & 7]
        if 0o41 <= m <= 0o47:
            self.sequences.append("SQ")
            self._shift(m, k)
            return (8.0 if m == 0o44 else 4.0) if k == 0 else time + 2 * k / 3
        if m == 0o50:                                    # SKP
            hit = self.skip_keys & k & 0o37
            self.skip_light = hit
            return self._skip(bool(hit) or bool(k & 0o40))
        if m == 0o51:                                    # SKPNBO
            return self._skip(not self.borrow)
        if m in (0o52, 0o53):                            # SKPOV / SKPNOV
            overflow, self.overflow = self.overflow, False
            return self._skip(overflow if m == 0o52 else not overflow)
        if m in (0o54, 0o55):                            # SKPODD / SKPEVN
            odd = (self.au & self.al).bit_count() % 2 == 1
            return self._skip(odd if m == 0o54 else not odd)
        if m == 0o21:
            return self._skip(not channel.input_active)
        if m == 0o22:
            return self._skip(not channel.output_active)
        if m == 0o23:
            return self._skip(not channel.function_active)
        if m == 0o57:                                    # SKPNR
            return self._skip(not channel.resume)
        if m == 0o56:                                    # STOP
            hit = self.stop_keys & k & 0o37
            if hit or k & 0o40:
                self.stop_light = hit
                self.stop("STOP KEY" if hit else "STOP")
            return time
        if m in (0o11, 0o12, 0o13):
            self._buffer(m, k & 7)
            return time
        if m == 0o15:
            channel.input_active = False
        elif m == 0o16:
            channel.output_active = False
        elif m == 0o17:
            channel.function_active = False
        elif m == 0o20:
            channel.resume = True
        elif m in (0o26, 0o27):                          # OUTOV / EXFOV
            control = (0o41 if m == 0o26 else 0o21) + 2 * (k & 7)
            address = self.mem.read(control) & ADDRESS_MASK
            if channel.device is not None:
                channel.device.output(self._operand(address))
        elif m == 0o30:
            self.interrupt_lockout = False
        elif m == 0o32:
            self.external_lockout = False
        elif m == 0o34:
            self.interrupt_lockout = True
        elif m == 0o36:
            self.external_lockout = True
        elif m == 0o24:
            self.stop("WAIT FOR INTERRUPT")
        elif m == 0o60:                                  # RND
            bit17 = (self.al >> 17) & 1
            self.al = (add(self.au, bit17) if not self.au & SIGN
                       else sub(self.au, 1 - bit17))
        elif m == 0o61:
            self.al = 0 if self.al == 0 else negate(self.al)
        elif m == 0o62:
            self.au = 0 if self.au == 0 else negate(self.au)
        elif m == 0o63:
            self.a = 0 if self.a == 0 else negate(self.a, 36)
        elif m == 0o72:
            self.icr = k & 0o7
        elif m == 0o73:
            self.sr = k & 0o17
        elif m not in NOT_USED_II:
            raise NotImplementedError(f"50 {m:02o}")
        return time

    def _shift(self, m: int, k: int) -> None:
        if m in (0o41, 0o42, 0o45, 0o46):
            name = "AU" if m in (0o41, 0o45) else "AL"
            value, bits = self.regs[name], 18
        else:
            value, bits = self.a, 36
        mask = (1 << bits) - 1
        if m in (0o41, 0o42, 0o43):                     # right, end off, sign fill
            negative = value >> (bits - 1)
            count = min(k, bits)
            value >>= count
            if negative:
                value |= (mask << (bits - count)) & mask
        elif m == 0o44:                                  # SF
            count = 0
            while count < k and ((value >> 35) & 1) == ((value >> 34) & 1):
                value = ((value << 1) | (value >> 35)) & mask
                count += 1
            self._store(SCALE_FACTOR_CELL, k - count)
        else:                                            # left circular
            count = k % bits
            value = ((value << count) | (value >> (bits - count))) & mask
        if bits == 18:
            self.regs[name] = value
        else:
            self.a = value

    def _buffer(self, m: int, k: int) -> None:
        """IN / OUT / EXF: the next two words go to the buffer control registers;
        a device on the channel then transfers the buffer."""
        base = {0o11: 0o60, 0o12: 0o40, 0o13: 0o20}[m] + 2 * k
        terminal, initial = self.read(self.p), self.read(self.p + 1)
        self.mem.write(base, terminal, force=True)
        self.mem.write(base + 1, initial, force=True)
        self.p = self.p + 2
        channel = self.channels[k]
        if m == 0o11:
            channel.input_active = True
            return
        if m == 0o13:
            channel.function_active = True
        else:
            channel.output_active = True
        if channel.device is None:
            return
        address, end = initial & ADDRESS_MASK, terminal & ADDRESS_MASK
        step = -1 if initial >> 17 else 1
        guard = 0
        while address != end and guard < MEMORY_WORDS:
            channel.device.output(self.read(address))
            address = (address + step) & ADDRESS_MASK
            guard += 1
        self.mem.write(base + 1, (initial & ~ADDRESS_MASK) | address, force=True)
        if m == 0o13:
            channel.function_active = False
        else:
            channel.output_active = False
