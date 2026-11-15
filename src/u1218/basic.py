"""A small BASIC compiler that generates UNIVAC 1218 machine code.

Memory layout: address 00000 (where P starts after MASTER CLEAR) holds JP 00240,
because 00001-00237 are assigned (index registers, I/O control words, interrupt
entrances, bootstrap). The program starts at 00240: a short prologue, the code
for each line, the run-time routines, then the data area. Everything lives in
bank 0 (00000-07777) so 12-bit u addresses reach it all.

Language
    [line] statement [: statement ...]
    LET v = expr          (LET optional)    v: A-Z, optionally followed by a digit
    PRINT item [; item | , item ...] [; | ,]
                          items: "text" or a numeric expression; ; joins, , tabs;
                          a newline ends the PRINT unless it finishes with ; or ,
    IF expr relop expr THEN line | statement      relop: = <> < <= > >=
    IF [NOT] KEYn THEN line | statement          console SKIP key n (0-4), via SKP
    GOTO line   GOSUB line   RETURN
    FOR v = expr TO expr [STEP constant]  ...  NEXT [v]
    STOP n                stop if console STOP key n (0-4) is set (STOP k); the next
                          start continues with the next statement
    END   STOP            stop for good (STOP 40)
    REM ...
Numbers are 18-bit ones' complement integers (-131071..131071); / truncates.

Machine use: AL is the accumulator, AU the high half for multiply/divide; index
register 1 (core 00001, ICR = 1) is the GOSUB stack pointer and index register 2
the digit pointer of the number printer. PRINT sends ASCII characters to the
console printer on channel 7 with OUT buffers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .cpu import CONSOLE_CHANNEL, Memory
from .isa import Assembler, disassemble
from .word import MASK, to_word

START = 0o240
BANK_END = 0o10000
STACK_WORDS = 16
MAX_NUMBER = 0o377777
K_MAX = 0o3777                 # largest constant that fits u (12-bit ones' complement)

RELOPS = ("<>", "<=", ">=", "=", "<", ">")
INVERSE = {"=": "<>", "<>": "=", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}
SWAPPED = {">": "<", "<=": ">="}                         # a > b  is  b < a
JUMP_FOR = {"=": "JPEQ", "<>": "JPNOT", "<": "JPMGR", ">=": "JPMLEQ"}


class BasicError(Exception):
    def __init__(self, line: str, message: str):
        super().__init__(f"{line}: {message}" if line else message)
        self.line = line
        self.message = message


@dataclass
class CompiledProgram:
    words: list[int]                     # from address 0 (00001-00237 left as zeros)
    rows: dict[int, int]                 # address -> source row (1-based)
    row_starts: dict[int, int]           # row -> first address
    line_numbers: dict[int, int]         # row -> BASIC line number
    variables: dict[str, int]            # name -> address
    listing: str
    end_address: int

    def load(self, mem: Memory) -> None:
        """Put the program in memory, leaving 00001-00237 (index registers,
        I/O control words, bootstrap) untouched apart from the cleared indexes."""
        mem.write(0, self.words[0], force=True)
        mem.load(self.words[START:], START)
        for address in (1, 2):
            mem.write(address, 0)


TOKEN = re.compile(r'\s*(?:(\d+)|("(?:[^"]|"")*")|([A-Za-z][A-Za-z0-9]*\$?)|(<>|<=|>=|.))')


def tokenize(text: str, line: str) -> list[str]:
    tokens, pos = [], 0
    text = text.rstrip()
    while pos < len(text):
        match = TOKEN.match(text, pos)
        if not match or match.end() == pos:
            raise BasicError(line, f"cannot read {text[pos:]!r}")
        number, string, word, symbol = match.groups()
        if number is not None:
            tokens.append(number)
        elif string is not None:
            tokens.append(string)
        elif word is not None:
            tokens.append(word.upper())
        elif symbol and symbol.strip():
            tokens.append(symbol)
        pos = match.end()
    return tokens


class Compiler:
    def __init__(self) -> None:
        self.asm = Assembler(origin=START)
        self.variables: dict[str, str] = {}      # name -> label
        self.constants: dict[int, str] = {}      # value -> label
        self.strings: list[tuple[str, str]] = []  # (label, text)
        self.temps = 0
        self.max_temps = 0
        self.labels = 0
        self.for_stack: list[tuple[str, str, str, int]] = []   # (var, top, exit, step)
        self.line_labels: set[int] = set()
        self.jump_targets: list[tuple[int, str]] = []
        self.used = set()
        self.line = ""

    # ------------------------------------------------------------ helpers

    def new_label(self, stem: str) -> str:
        self.labels += 1
        return f"{stem}{self.labels}"

    def var(self, name: str) -> str:
        if not re.fullmatch(r"[A-Z][0-9]?", name):
            raise BasicError(self.line, f"bad variable name {name}")
        return self.variables.setdefault(name, f"V_{name}")

    def const(self, value: int) -> str:
        return self.constants.setdefault(value, f"K_{value}".replace("-", "M"))

    def temp(self) -> str:
        label = f"T_{self.temps}"
        self.temps += 1
        self.max_temps = max(self.max_temps, self.temps)
        return label

    def op(self, mnemonic: str, operand=0, comment: str = "") -> None:
        self.asm.op(mnemonic, operand, comment)

    @staticmethod
    def k(value: int) -> int:
        """A small constant as a 12-bit ones' complement u field."""
        return to_word(value, 12)

    # ------------------------------------------------------------ expressions

    def parse_expression(self, tokens: list[str]):
        node = self.parse_term(tokens)
        while tokens and tokens[0] in "+-":
            node = (tokens.pop(0), node, self.parse_term(tokens))
        return node

    def parse_term(self, tokens: list[str]):
        node = self.parse_factor(tokens)
        while tokens and tokens[0] in ("*", "/"):
            node = (tokens.pop(0), node, self.parse_factor(tokens))
        return node

    def parse_factor(self, tokens: list[str]):
        if not tokens:
            raise BasicError(self.line, "expression expected")
        token = tokens.pop(0)
        if token == "-":
            node = self.parse_factor(tokens)
            return ("num", -node[1]) if node[0] == "num" else ("neg", node)
        if token == "+":
            return self.parse_factor(tokens)
        if token == "(":
            node = self.parse_expression(tokens)
            self.expect(tokens, ")")
            return node
        if token.isdigit():
            value = int(token)
            if value > MAX_NUMBER:
                raise BasicError(self.line, f"{value} is too big for an 18-bit word")
            return ("num", value)
        if re.fullmatch(r"[A-Z][0-9]?", token):
            return ("var", token)
        raise BasicError(self.line, f"unexpected {token!r}")

    @staticmethod
    def simple(node) -> bool:
        return node[0] in ("num", "var")

    def address_of(self, node) -> str:
        return self.const(node[1]) if node[0] == "num" else self.var(node[1])

    def load(self, node) -> None:
        """Code that leaves the value of node in AL."""
        kind = node[0]
        if kind == "num":
            value = node[1]
            if abs(value) <= K_MAX:
                self.op("ENTALK", self.k(value))
            else:
                self.op("ENTAL", self.const(value))
            return
        if kind == "var":
            self.op("ENTAL", self.var(node[1]))
            return
        if kind == "neg":
            self.load(node[1])
            self.op("CPAL")
            return
        operator, left, right = node
        if self.simple(right):
            self.load(left)
            self.apply(operator, right)
            return
        spill = self.temp()
        self.load(right)
        self.op("STRAL", spill)
        self.load(left)
        self.apply(operator, ("tmp", spill))
        self.temps -= 1

    def apply(self, operator: str, right) -> None:
        """AL <- AL operator right (right is a constant, a variable or a temp)."""
        if right[0] == "num" and operator in "+-" and abs(right[1]) <= K_MAX:
            self.op("ADDALK", self.k(right[1] if operator == "+" else -right[1]))
            return
        address = right[1] if right[0] == "tmp" else self.address_of(right)
        if operator == "+":
            self.op("ADDAL", address)
        elif operator == "-":
            self.op("SUBAL", address)
        elif operator == "*":
            self.op("MULAL", address)
            self.op("ADDALK", 0, "-0 -> +0")
        else:
            self.op("STRAL", "DIVTMP")
            self.op("ENTAU", "DIVTMP")
            self.op("RSHA", 18, "A = dividend, sign extended")
            self.op("DIVA", address)
            self.op("ADDALK", 0, "-0 -> +0")
            self.used.add("DIVTMP")

    # ------------------------------------------------------------ statements

    def expect(self, tokens: list[str], token: str) -> None:
        if not tokens or tokens.pop(0) != token:
            raise BasicError(self.line, f"{token!r} expected")

    def line_label(self, number: int) -> str:
        return f"L{number}"

    def jump_to_line(self, number: int) -> None:
        self.jump_targets.append((number, self.line))
        self.op("JP", self.line_label(number))

    def statement(self, tokens: list[str]) -> None:
        if not tokens:
            return
        keyword = tokens[0]
        if keyword == "REM":
            tokens.clear()
            return
        if keyword in ("LET", "PRINT", "IF", "GOTO", "GOSUB", "RETURN", "FOR", "NEXT",
                       "END", "STOP"):
            tokens.pop(0)
        else:
            keyword = "LET"
        getattr(self, f"st_{keyword.lower()}")(tokens)

    def st_let(self, tokens: list[str]) -> None:
        if not tokens:
            raise BasicError(self.line, "variable expected")
        target = self.var(tokens.pop(0))
        self.expect(tokens, "=")
        self.load(self.parse_expression(tokens))
        self.op("STRAL", target)

    def st_print(self, tokens: list[str]) -> None:
        newline = True
        while tokens and tokens[0] != ":":
            token = tokens[0]
            if token in (";", ","):
                tokens.pop(0)
                if token == ",":
                    self.out_cell("TAB")
                newline = False
                continue
            newline = True
            if token.startswith('"'):
                tokens.pop(0)
                text = token[1:-1].replace('""', '"')
                if text:
                    label = self.new_label("S_")
                    self.strings.append((label, text))
                    self.op("OUT", CONSOLE_CHANNEL, f'PRINT "{text}"')
                    self.asm.word((f"{label}", len(text)), "terminal address")
                    self.asm.word(label, "initial address")
            else:
                self.load(self.parse_expression(tokens))
                self.op("RJP", "PRNUM")
                self.used.add("PRNUM")
        if newline:
            self.out_cell("NL")

    def out_cell(self, label: str) -> None:
        self.used.add(label)
        self.op("OUT", CONSOLE_CHANNEL, "newline" if label == "NL" else "tab")
        self.asm.word((label, 1), "terminal address")
        self.asm.word(label, "initial address")

    def condition(self, tokens: list[str]) -> tuple:
        if tokens and tokens[0] == "NOT":
            tokens.pop(0)
            negate = True
        else:
            negate = False
        if tokens and re.fullmatch(r"KEY[0-4]", tokens[0]):
            return ("key", int(tokens.pop(0)[3]), negate)
        if negate:
            raise BasicError(self.line, "NOT is only allowed with KEYn")
        left = self.parse_expression(tokens)
        if not tokens or tokens[0] not in RELOPS:
            raise BasicError(self.line, "comparison operator expected")
        relop = tokens.pop(0)
        return ("cmp", relop, left, self.parse_expression(tokens))

    def jump_if(self, cond: tuple, target: str, when: bool = True) -> None:
        """Jump to target if the condition is `when`."""
        if cond[0] == "key":
            _, key, negate = cond
            taken_when_set = when != negate
            self.op("SKP", 1 << key, f"skip if KEY{key} set")
            if taken_when_set:
                over = self.new_label("X_")
                self.op("JP", over)
                self.op("JP", target)
                self.asm.label(over)
            else:
                self.op("JP", target)
            return
        _, relop, left, right = cond
        if not when:
            relop = INVERSE[relop]
        if relop in SWAPPED:
            relop, left, right = SWAPPED[relop], right, left
        if self.simple(right):
            address = self.address_of(right)
        else:
            address = self.temp()
            self.load(right)
            self.op("STRAL", address)
            self.temps -= 1
        self.load(left)
        self.op("CMAL", address)
        self.op(JUMP_FOR[relop], target)

    def st_if(self, tokens: list[str]) -> None:
        cond = self.condition(tokens)
        self.expect(tokens, "THEN")
        if tokens and tokens[0].isdigit():
            number = int(tokens.pop(0))
            self.jump_targets.append((number, self.line))
            self.jump_if(cond, self.line_label(number))
            return
        skip = self.new_label("F_")
        self.jump_if(cond, skip, when=False)
        self.statement(tokens)
        while tokens and tokens[0] == ":":
            tokens.pop(0)
            self.statement(tokens)
        self.asm.label(skip)

    def st_goto(self, tokens: list[str]) -> None:
        self.jump_to_line(self.line_number(tokens))

    def line_number(self, tokens: list[str]) -> int:
        if not tokens or not tokens[0].isdigit():
            raise BasicError(self.line, "line number expected")
        return int(tokens.pop(0))

    def st_gosub(self, tokens: list[str]) -> None:
        number = self.line_number(tokens)
        back = self.new_label("R_")
        self.op("ENTAL", self.address_const(back), "return address")
        self.op("STRALB", "STACK", "push (B = index register 1)")
        self.op("ENTBKB", 1)
        self.jump_to_line(number)
        self.asm.label(back)
        self.used.add("STACK")

    def address_const(self, label: str) -> str:
        name = f"A_{label}"
        self.constants.setdefault(name, name)       # resolved to the label's address
        return name

    def st_return(self, tokens: list[str]) -> None:
        self.op("ENTBKB", self.k(-1), "pop")
        self.op("ENTALB", "STACK")
        self.op("STRAL", "RETTMP")
        self.op("IJP", "RETTMP")
        self.used.update(("STACK", "RETTMP"))

    def st_for(self, tokens: list[str]) -> None:
        name = tokens.pop(0) if tokens else ""
        variable = self.var(name)
        self.expect(tokens, "=")
        self.load(self.parse_expression(tokens))
        self.op("STRAL", variable)
        self.expect(tokens, "TO")
        limit = f"FL_{name}"
        self.constants.setdefault(limit, limit)
        self.load(self.parse_expression(tokens))
        self.op("STRAL", limit)
        step = 1
        if tokens and tokens[0] == "STEP":
            tokens.pop(0)
            node = self.parse_factor(tokens)
            if node[0] != "num":
                raise BasicError(self.line, "STEP must be a constant")
            step = node[1]
            if step == 0:
                raise BasicError(self.line, "STEP 0 never ends")
        top, done = self.new_label("FOR_"), self.new_label("NEXT_")
        self.asm.label(top)
        if step > 0:                                     # exit when limit < v
            self.op("ENTAL", limit)
            self.op("CMAL", variable)
        else:                                            # exit when v < limit
            self.op("ENTAL", variable)
            self.op("CMAL", limit)
        self.op("JPMGR", done)
        self.for_stack.append((name, top, done, step))

    def st_next(self, tokens: list[str]) -> None:
        if not self.for_stack:
            raise BasicError(self.line, "NEXT without FOR")
        name, top, done, step = self.for_stack.pop()
        if tokens and tokens[0] not in (":",):
            given = tokens.pop(0)
            if given != name:
                raise BasicError(self.line, f"NEXT {given} does not match FOR {name}")
        variable = self.var(name)
        self.op("ENTAL", variable)
        self.apply("+", ("num", step))
        self.op("STRAL", variable)
        self.op("JP", top)
        self.asm.label(done)

    def st_stop(self, tokens: list[str]) -> None:
        if tokens and tokens[0].isdigit():
            key = int(tokens.pop(0))
            if not 0 <= key <= 4:
                raise BasicError(self.line, "STOP key must be 0-4")
            self.op("STOP", 1 << key, f"stop if STOP key {key} set")
            return
        self.st_end(tokens)

    def st_end(self, _tokens: list[str]) -> None:
        here = self.asm.address
        self.op("STOP", 0o40, "END")
        self.op("JP", here)

    # ------------------------------------------------------------ run-time library

    def library(self) -> None:
        asm = self.asm
        if "PRNUM" in self.used:
            self.used.update(("NL", "MINUS"))
            asm.label("PRNUM")
            asm.word(0, "PRNUM: print AL in decimal (return address)")
            self.op("ADDALK", 0, "-0 -> +0")
            self.op("JPALP", "PN_POS")
            self.op("STRAL", "PN_V")
            self.op("OUT", CONSOLE_CHANNEL, "print '-'")
            asm.word(("MINUS", 1))
            asm.word("MINUS")
            self.op("ENTAL", "PN_V")
            self.op("CPAL", 0, "magnitude")
            asm.label("PN_POS")
            self.op("ENTICR", 2, "index register 2 = digit pointer")
            self.op("ENTBK", 6)
            asm.label("PN_LOOP")
            self.op("STRAL", "PN_V")
            self.op("ENTAU", "PN_ZERO")
            self.op("DIVA", "PN_TEN", "AL = v / 10, AU = v mod 10")
            self.op("STRAL", "PN_V")
            self.op("STRAU", "PN_D")
            self.op("ENTAL", "PN_D")
            self.op("ADDALK", 0o60, "digit -> ASCII")
            self.op("STRALB", ("PN_BUF", -1))
            self.op("ENTBKB", self.k(-1))
            self.op("ENTAL", "PN_V")
            self.op("JPALNZ", "PN_LOOP")
            self.op("STRB", "PN_D", "first digit is at PN_BUF + B")
            self.op("ENTAL", "PN_D")
            self.op("ADDAL", "A_PN_BUF")
            self.op("STRADR", "PN_INIT", "initial address of the OUT buffer")
            self.op("ENTICR", 1, "back to the GOSUB stack pointer")
            self.op("OUT", CONSOLE_CHANNEL, "print the digits")
            asm.word(("PN_BUF", 6), "terminal address")
            asm.label("PN_INIT")
            asm.word("PN_BUF", "initial address (set above)")
            self.op("IJP", "PRNUM")
            self.constants.setdefault("A_PN_BUF", "A_PN_BUF")

    def data(self) -> None:
        asm = self.asm
        asm.label("DATA")
        cells = {"NL": 0o12, "TAB": 0o11, "MINUS": ord("-")}
        for name, value in cells.items():
            if name in self.used:
                asm.label(name)
                asm.word(value, name)
        if "PRNUM" in self.used:
            for name, value in (("PN_V", 0), ("PN_D", 0), ("PN_ZERO", 0), ("PN_TEN", 10)):
                asm.label(name)
                asm.word(value, name)
            asm.label("PN_BUF")
            for _ in range(6):
                asm.word(0, "digits")
        for name in ("DIVTMP", "RETTMP"):
            if name in self.used:
                asm.label(name)
                asm.word(0, name)
        for key, label in self.constants.items():
            asm.label(label)
            if isinstance(key, int):
                asm.word(to_word(key), f"constant {key}")
            elif key.startswith("A_"):
                asm.word(key[2:], f"address of {key[2:]}")
            else:
                asm.word(0, f"FOR limit {key[3:]}")
        for name, label in sorted(self.variables.items()):
            asm.label(label)
            asm.word(0, f"variable {name}")
        for i in range(self.max_temps):
            asm.label(f"T_{i}")
            asm.word(0, "temporary")
        for label, text in self.strings:
            asm.label(label)
            for ch in text:
                asm.word(ord(ch) & 0x7F, repr(ch))
        if "STACK" in self.used:
            asm.label("STACK")
            for _ in range(STACK_WORDS):
                asm.word(0, "GOSUB stack")

    # ------------------------------------------------------------ driver

    def compile(self, source: str) -> CompiledProgram:
        asm = self.asm
        asm.op("ENTICR", 1, "index register 1: GOSUB stack pointer")
        asm.op("ENTBK", 0)
        rows: dict[int, int] = {}
        row_starts: dict[int, int] = {}
        line_numbers: dict[int, int] = {}
        previous = None
        for row, text in enumerate(source.splitlines(), start=1):
            stripped = text.strip()
            if not stripped:
                continue
            match = re.match(r"(\d+)\s*(.*)", stripped)
            if not match:
                raise BasicError(stripped[:20], "line number expected")
            number, body = int(match.group(1)), match.group(2)
            self.line = str(number)
            if previous is not None and number <= previous:
                raise BasicError(self.line, "line numbers must increase")
            previous = number
            start = asm.address
            asm.label(self.line_label(number))
            self.line_labels.add(number)
            line_numbers[row] = number
            row_starts[row] = start
            tokens = tokenize(body, self.line)
            while tokens:
                self.statement(tokens)
                if tokens:
                    if tokens[0] != ":":
                        raise BasicError(self.line, f"unexpected {tokens[0]!r}")
                    tokens.pop(0)
            for address in range(start, asm.address):
                rows[address] = row
        if self.for_stack:
            raise BasicError(self.line, f"FOR {self.for_stack[-1][0]} without NEXT")
        for number, line in self.jump_targets:
            if number not in self.line_labels:
                raise BasicError(line, f"line {number} does not exist")
        end_label = asm.address
        self.st_end([])
        rows[end_label] = rows[end_label + 1] = max(rows.values(), default=0)
        self.library()
        self.data()
        end_address = asm.address
        if end_address > BANK_END:
            raise BasicError("", f"program needs {end_address:o} words; bank 0 ends at 10000")
        words = asm.assemble()
        listing = self.make_listing(words, row_starts, line_numbers)
        program_words = [0] * START + words
        program_words[0] = 0o340000 | START          # JP 00240
        return CompiledProgram(
            words=[w & MASK for w in program_words], rows=rows, row_starts=row_starts,
            line_numbers=line_numbers,
            variables={name: asm.labels[label] for name, label in self.variables.items()},
            listing=listing, end_address=end_address)

    def make_listing(self, words: list[int], row_starts: dict[int, int],
                     line_numbers: dict[int, int]) -> str:
        starts = {address: line_numbers[row] for row, address in row_starts.items()}
        names = {address: name for name, address in self.asm.labels.items()}
        out = ["00000  340240  JP 0240       start"]
        for offset, (word, item) in enumerate(zip(words, self.asm.items, strict=True)):
            address = START + offset
            kind, _, _, note = item
            label = names.get(address, "")
            number = starts.get(address)
            code = f"({word:06o})" if kind == "word" else disassemble(word)
            line = f"{address:05o}  {word:06o}  {code:<13} {label:<9} {note}"
            if number is not None:
                line += f"   [{number}]"
            out.append(line.rstrip())
        return "\n".join(out)


def compile_basic(source: str) -> CompiledProgram:
    return Compiler().compile(source)
