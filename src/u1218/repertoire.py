"""The UNIVAC 1218 instruction catalog.

One entry per instruction, transcribed from the 2-page Repertoire of Instructions
card (docs/UNIVAC_1218_Repertoire_of_Instructions_2pages.pdf) with details from
PX 2910 section I-B. The disassembler, the CPU dispatch cross-check and the
Excel export (tools/export_repertoire.py) all read from here.

Notation in ``pseudo``:
  Y      operand address: y (+B for the B-modified "B" instructions);
         y = u_P or u_SR (bank bits from P, or from SR when SR is active)
  (Y)    contents of Y;  K = u sign-extended to 18 bits (constant instructions)
  A      AU:AL, 36 bits;  B = active index register (core 001-010, chosen by ICR)
  '      ones' complement;  & | ^  logical AND / OR / XOR
  CD     comparison designator (compare, less-than, equals stages)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    f: int                  # function code (Format I), 0o50 for Format II
    m: int | None           # minor function code (Format II only)
    mnemonic: str
    name: str               # as printed on the card
    card: str               # description as printed on the card
    pseudo: str             # this emulator's operation
    category: str
    time: str               # execution time, microseconds, as printed
    sr: bool = False        # "#": SR sensitive (y = u_SR when SR is active)
    b_mod: bool = False     # a "B" instruction: y + B (odd f below 50)
    notes: str = ""

    @property
    def code(self) -> str:
        return f"{self.f:02o}" if self.m is None else f"{self.f:02o} {self.m:02o}"

    @property
    def format(self) -> str:
        return "I" if self.m is None else "II"


LOG, SHIFT, SKIP, IO, MISC = "Logical", "Shift", "Skip", "Input/Output", "Misc"
ENTER, STORE, ARITH, MOD, JUMP, FAULT = "Enter", "Store", "Arithmetic", "Modifying", "Jump", "Fault"

_E = Entry


def _pair(f: int, mnemonic: str, name: str, card: str, pseudo: str, category: str,
          time: int, sr: bool = True, notes: str = "") -> list[Entry]:
    """The card's "*" instructions: f uses y, f+1 (suffix B) uses y + B, 4 usec more."""
    return [
        _E(f, None, mnemonic, name, card, pseudo, category, str(time), sr, False, notes),
        _E(f + 1, None, mnemonic + "B", name + " (Y+B)", card.replace("(Y)", "(Y+B)"),
           pseudo, category, str(time + 4), sr, True, notes),
    ]


CATALOG: list[Entry] = [
    # ------------------------------------------------------------------ logical
    *_pair(0o02, "CMAL", "COMPARE SET DESIGNATOR", "(AL):(Y); (AL)f = (AL)i",
           "CD <- compare (AL) with (Y) algebraically", LOG, 8),
    *_pair(0o04, "SLSU", "SELECTIVE SUBSTITUTE", "L(AU)'(AL)+L(AU)(Y) -> AL; (AU)f=(AU)i",
           "AL <- (AL & AU') | ((Y) & AU)", LOG, 8),
    *_pair(0o06, "CMSK", "COMPARE WITH MASK SET DES.", "L(AL)(AU):L(Y)(AU); (A)f=(A)i",
           "CD <- compare (AL & AU) with ((Y) & AU) algebraically", LOG, 8),
    _E(0o51, None, "SLSET", "SELECTIVE SET (INCLUSIVE OR)", "(AL)v(Y) -> AL",
       "AL <- AL | (Y)", LOG, "8"),
    _E(0o52, None, "SLCL", "SELECTIVE CLEAR (LOGICAL PROD)", "L(AL)(Y) -> AL",
       "AL <- AL & (Y)", LOG, "8"),
    _E(0o53, None, "SLCP", "SELECTIVE COMPLEMENT (EXCL. OR)", "(AL)(+)(Y) -> AL",
       "AL <- AL ^ (Y)", LOG, "8"),
    _E(0o50, 0o61, "CPAL", "COMPLEMENT AL", "(AL)' -> AL  IGNORE k", "AL <- AL' (+0 stays +0)",
       LOG, "5.33"),
    _E(0o50, 0o62, "CPAU", "COMPLEMENT AU", "(AU)' -> AU  IGNORE k", "AU <- AU' (+0 stays +0)",
       LOG, "5.33"),
    _E(0o50, 0o63, "CPA", "COMPLEMENT A", "(A)' -> A  IGNORE k", "A <- A' (+0 stays +0)",
       LOG, "5.33"),
    # ------------------------------------------------------------------ shift
    _E(0o50, 0o41, "RSHAU", "RIGHT SHIFT AU", "SHIFT RIGHT k, END OFF, FILL WITH SIGN",
       "AU <- AU >> k (arithmetic)", SHIFT, "5.33+2k/3"),
    _E(0o50, 0o42, "RSHAL", "RIGHT SHIFT AL", "SHIFT RIGHT k, END OFF, FILL WITH SIGN",
       "AL <- AL >> k (arithmetic)", SHIFT, "5.33+2k/3"),
    _E(0o50, 0o43, "RSHA", "RIGHT SHIFT A", "SHIFT RIGHT k, END OFF, FILL WITH SIGN",
       "A <- A >> k (arithmetic)", SHIFT, "5.33+2k/3"),
    _E(0o50, 0o44, "SF", "SCALE FACTOR SHIFT",
       "LEFT CIRCULAR SHIFT A UNTIL A35 != A34 OR k - SHIFTCOUNT = 0; k - SHIFTCOUNT -> 00017",
       "normalize A left (at most k places); k - shifts -> (00017)", SHIFT, "9.33+2k/3"),
    _E(0o50, 0o45, "LSHAU", "LEFT SHIFT AU", "SHIFT LEFT k CIRCULARLY", "AU <- AU rotl k",
       SHIFT, "5.33+2k/3"),
    _E(0o50, 0o46, "LSHAL", "LEFT SHIFT AL", "SHIFT LEFT k CIRCULARLY", "AL <- AL rotl k",
       SHIFT, "5.33+2k/3"),
    _E(0o50, 0o47, "LSHA", "LEFT SHIFT A", "SHIFT LEFT k CIRCULARLY", "A <- A rotl k",
       SHIFT, "5.33+2k/3"),
    # ------------------------------------------------------------------ skip
    _E(0o50, 0o51, "SKPNBO", "SKIP ON NO BORROW", "SKIP NI IF BORROW DESIGNATOR NOT SET",
       "skip if not borrow", SKIP, "6/4.67"),
    _E(0o50, 0o52, "SKPOV", "SKIP ON OVERFLOW", "SKIP NI IF OVERFLOW DESIGNATOR SET",
       "skip if overflow; clear overflow", SKIP, "6/4.67"),
    _E(0o50, 0o53, "SKPNOV", "SKIP ON NO OVERFLOW", "SKIP NI IF OVERFLOW DESIGNATOR NOT SET",
       "skip if not overflow; clear overflow", SKIP, "6/4.67"),
    _E(0o50, 0o54, "SKPODD", "SKIP ON ODD PARITY", "SKIP NI IF SUM OF ONES IN L(AU)(AL) IS ODD",
       "skip if popcount(AU & AL) odd", SKIP, "6/4.67"),
    _E(0o50, 0o55, "SKPEVN", "SKIP ON EVEN PARITY",
       "SKIP NI IF SUM OF ONES IN L(AU)(AL) IS EVEN", "skip if popcount(AU & AL) even", SKIP,
       "6/4.67"),
    _E(0o50, 0o21, "SKPIIN", "SKIP ON INPUT INACTIVE", "SKIP NI IF CHAN. k INPUT IS INACTIVE",
       "skip if input channel k inactive", SKIP, "6/4.67"),
    _E(0o50, 0o22, "SKPOIN", "SKIP ON OUTPUT INACTIVE", "SKIP NI IF CHAN. k OUTPUT IS INACTIVE",
       "skip if output channel k inactive", SKIP, "6/4.67"),
    _E(0o50, 0o23, "SKPFIN", "SKIP ON EXT. FUNCT. INACTIVE",
       "SKIP NI IF CHAN. k EXT. FUNCT. IS INACTIVE", "skip if ext. function channel k inactive",
       SKIP, "6/4.67"),
    _E(0o50, 0o50, "SKP", "SKIP ON KEY SETTING k", "SKIP NI IF k = CONSOLE KEY SETTING",
       "skip if (k4-0 & skip keys) or k5", SKIP, "6/4.67"),
    _E(0o50, 0o57, "SKPNR", "SKIP ON NO RESUME", "SKIP NI IF RESUME DESIGNATOR NOT SET",
       "skip if resume designator of channel k not set", SKIP, "6/4.67"),
    # ------------------------------------------------------------------ input / output
    _E(0o50, 0o11, "IN", "INPUT TRANSFER", "(P+1) -> 60+2k; (P+2) -> 61+2k; SET IN. ACTIVE",
       "load input buffer control words, activate input on channel k", IO, "20"),
    _E(0o50, 0o12, "OUT", "OUTPUT TRANSFER", "(P+1) -> 40+2k; (P+2) -> 41+2k; SET OUT. ACTIVE",
       "load output buffer control words, activate output on channel k", IO, "20"),
    _E(0o50, 0o13, "EXF", "EXT. FUNCT. TRANSFER",
       "(P+1) -> 20+2k; (P+2) -> 21+2k; SET EXT. F. ACTIVE",
       "load ext. function buffer control words, activate on channel k", IO, "20"),
    _E(0o50, 0o15, "INSTP", "TERMINATE INPUT", "CLEAR INPUT ACTIVE CHAN. k",
       "input channel k inactive", IO, "4"),
    _E(0o50, 0o16, "OUTSTP", "TERMINATE OUTPUT", "CLEAR OUTPUT ACTIVE CHAN. k",
       "output channel k inactive", IO, "4"),
    _E(0o50, 0o17, "EXFSTP", "TERMINATE EXT. FUNCT.", "CLEAR FUNCTION ACTIVE CHAN. k",
       "ext. function channel k inactive", IO, "4"),
    _E(0o50, 0o20, "SRSM", "SET RESUME", "SET THE RESUME DESIGNATOR (INTERCOMPUTER)",
       "resume designator of channel k set", IO, "4"),
    _E(0o50, 0o26, "OUTOV", "OUTPUT OVERRIDE", "FORCE ONE WORD OUT CHAN. k WITH OUTPUT ACK.",
       "send the word at the output buffer address of channel k", IO, "4.67"),
    _E(0o50, 0o27, "EXFOV", "FUNCTION OVERRIDE", "FORCE ONE WORD OUT CHAN. k WITH EXT. FUNCT.",
       "send the word at the ext. function buffer address of channel k", IO, "4.67"),
    _E(0o50, 0o30, "RIL", "REMOVE INTERRUPT LOCKOUT", "ENABLE ALL INTERRUPTS",
       "interrupt lockout off", IO, "4"),
    _E(0o50, 0o32, "RXL", "REMOVE EXT. INT. LOCKOUT", "ENABLE EXTERNAL INTERRUPTS",
       "external interrupt lockout off", IO, "4"),
    _E(0o50, 0o34, "SIL", "SET INTERRUPT LOCKOUT", "DISABLE ALL INTERRUPTS",
       "interrupt lockout on", IO, "4"),
    _E(0o50, 0o36, "SXL", "SET EXT. INT. LOCKOUT", "DISABLE EXTERNAL INTERRUPTS",
       "external interrupt lockout on", IO, "4"),
    # ------------------------------------------------------------------ misc
    _E(0o50, 0o24, "WTFI", "WAIT FOR INTERRUPT",
       "STOP; THEN INTERRUPT ENTRANCE REG. FOR NI", "stop until an interrupt", MISC, "4"),
    _E(0o50, 0o56, "STOP", "STOP ON KEY SETTING", "STOP IF k = KEY SETTING",
       "stop if (k4-0 & stop keys) or k5", MISC, "4.67"),
    # ------------------------------------------------------------------ enter
    *_pair(0o10, "ENTAU", "ENTER AU WITH (Y)", "(Y) -> AU", "AU <- (Y)", ENTER, 8),
    *_pair(0o12, "ENTAL", "ENTER AL WITH (Y)", "(Y) -> AL", "AL <- (Y)", ENTER, 8),
    *_pair(0o32, "ENTB", "ENTER B REGISTER WITH (Y)", "(Y) -> B REGISTER", "B <- (Y)", ENTER,
           12),
    _E(0o36, None, "ENTBK", "ENTER B REGISTER WITH CONSTANT", "Y -> B REGISTER (Note 1)",
       "B <- K", ENTER, "8", notes="u sign-extended to 18 bits"),
    _E(0o70, None, "ENTALK", "ENTER AL WITH CONSTANT", "Y -> AL (Note 1)", "AL <- K", ENTER,
       "4.67", notes="u sign-extended to 18 bits"),
    _E(0o50, 0o72, "ENTICR", "ENTER INDEX CONTROL REGISTER", "k2-0 -> ICR", "ICR <- k & 7",
       ENTER, "4"),
    _E(0o50, 0o73, "ENTSR", "ENTER SR", "k3-0 -> SR", "SR <- k & 17 (SR3 = 1 activates SR)",
       ENTER, "4"),
    # ------------------------------------------------------------------ store
    *_pair(0o40, "CL", "STORE ZERO (CLEAR Y)", "0 -> Y", "(Y) <- 0", STORE, 8),
    *_pair(0o42, "STRB", "STORE B IN Y", "B -> Y", "(Y) <- B", STORE, 12),
    *_pair(0o44, "STRAL", "STORE (AL) IN Y", "(AL) -> Y", "(Y) <- AL", STORE, 8),
    *_pair(0o46, "STRAU", "STORE (AU) IN Y", "(AU) -> Y", "(Y) <- AU", STORE, 8),
    _E(0o72, None, "STRICR", "STORE (ICR) IN YL", "(ICR) -> Y5-0; (Y)17-6 UNCHANGED",
       "(Y)5-0 <- address of the active index register (ICR 0 -> 10)", STORE, "8"),
    _E(0o74, None, "STRADR", "STORE ADDRESS IN YL", "(AL)11-0 -> Y11-0; (Y)17-12 UNCHANGED",
       "(Y)11-0 <- AL11-0", STORE, "8"),
    _E(0o75, None, "STRSR", "STORE (SR) IN YL", "(SR) -> Y5-0; (Y)17-6 UNCHGD. 0 -> SR3",
       "(Y)5-0 <- SR; SR <- 0 (deactivated)", STORE, "8"),
    # ------------------------------------------------------------------ arithmetic
    *_pair(0o14, "ADDAL", "ADD (Y) TO AL", "(AL) + (Y) -> AL", "AL <- AL + (Y); overflow",
           ARITH, 8),
    *_pair(0o16, "SUBAL", "SUBTRACT (Y) FROM AL", "(AL) - (Y) -> AL", "AL <- AL - (Y); overflow",
           ARITH, 8),
    *_pair(0o20, "ADDA", "ADD (Y+1,Y) TO A", "(A)+(Y+1,Y) -> A",
           "A <- A + (Y+1,Y); end-around borrow blocked -> borrow designator", ARITH, 12),
    *_pair(0o22, "SUBA", "SUBTRACT (Y+1,Y) FROM A", "(A)-(Y+1,Y) -> A",
           "A <- A - (Y+1,Y); end-around borrow blocked -> borrow designator", ARITH, 12),
    *_pair(0o24, "MULAL", "MULTIPLY AL BY (Y)", "(AL).(Y) -> A", "A <- AL * (Y)", ARITH, 26,
           notes="26-48.67 usec"),
    *_pair(0o26, "DIVA", "DIVIDE A BY (Y)", "(A)/(Y) -> AL; Remainder -> AU",
           "AL <- A / (Y), AU <- remainder (sign of dividend); overflow -> AL = 0", ARITH, 48),
    _E(0o71, None, "ADDALK", "ADD CONSTANT TO AL", "(AL)+Y -> AL, Note 1", "AL <- AL + K",
       ARITH, "4.67", notes="u sign-extended to 18 bits"),
    _E(0o50, 0o60, "RND", "ROUND AU", "+(AU)+AL17 -> AL; OR -(AU)-AL17' -> AL; AUf = AUi",
       "AL <- AU + AL17 (AU positive) or AU - AL17' (AU negative)", ARITH, "5.33"),
    # ------------------------------------------------------------------ modifying
    _E(0o37, None, "ENTBKB", "MODIFY B WITH CONSTANT", "B+Y -> B REGISTER", "B <- B + K", MOD,
       "12", notes="u sign-extended to 18 bits"),
    _E(0o56, None, "BSK", "B SKIP", "IF B = (Y), SKIP NI; IF B != (Y), B+1 -> B & DO NI",
       "if B == (Y) skip else B <- B + 1", MOD, "16"),
    _E(0o57, None, "ISK", "INDEX SKIP", "IF (Y)=0, SKIP NI; IF (Y) != 0, (Y)-1 -> Y & DO NI",
       "if (Y) == +0 skip else (Y) <- (Y) - 1", MOD, "12"),
    _E(0o73, None, "BJP", "B JUMP", "IF B!=0, B-1 -> B AND Y -> P; IF B=0, DO NI",
       "if B != +0: B <- B - 1, P <- Y", MOD, "12"),
    # ------------------------------------------------------------------ jump
    *_pair(0o30, "IRJP", "INDIRECT RETURN JUMP", "(P)+1 -> (Y); (Y)+1 -> P (Note 2)",
           "(Y)14-0 = R: (R) <- P+1, P <- R + 1", JUMP, 12, sr=False),
    *_pair(0o34, "JP", "UNCONDITIONAL JUMP", "Y -> P", "P <- Y", JUMP, 4, sr=False),
    _E(0o54, None, "IJPEI", "IND JUMP & ENABLE INT.", "(Y) -> P & ENABLE INTERRUPTS",
       "interrupt lockout off; P <- (Y)14-0", JUMP, "8"),
    _E(0o55, None, "IJP", "INDIRECT JUMP", "(Y) -> P", "P <- (Y)14-0", JUMP, "8"),
    _E(0o76, None, "RJP", "DIRECT RETURN JUMP", "(P)+1 -> Y; Y+1 -> P (Note 2)",
       "(Y) <- P+1, P <- Y + 1", JUMP, "8"),
    _E(0o60, None, "JPAUZ", "JUMP (AU) = 0", "CD NOT SET: (AU) = 0; SET: JPEQ M = (AL)",
       "jump if (no CD and AU == +0) or (CD and equal)", JUMP, "4"),
    _E(0o61, None, "JPALZ", "JUMP (AL) = 0 / JPEQ", "CD NOT SET: (AL) = 0; SET: M = (AL)",
       "jump if (no CD and AL == +0) or (CD and equal)", JUMP, "4", notes="also JPEQ"),
    _E(0o62, None, "JPAUNZ", "JUMP (AU) != 0", "CD NOT SET: (AU) != 0; SET: M != (AL)",
       "jump if (no CD and AU != +0) or (CD and not equal)", JUMP, "4"),
    _E(0o63, None, "JPALNZ", "JUMP (AL) != 0 / JPNOT", "CD NOT SET: (AL) != 0; SET: M != (AL)",
       "jump if (no CD and AL != +0) or (CD and not equal)", JUMP, "4", notes="also JPNOT"),
    _E(0o64, None, "JPAUP", "JUMP (AU) POSITIVE", "CD NOT SET: (AU) POS.; SET: M <= (AL)",
       "jump if (no CD and AU17 = 0) or (CD and not less)", JUMP, "4"),
    _E(0o65, None, "JPALP", "JUMP (AL) POSITIVE / JPMLEQ", "CD NOT SET: (AL) POS.; SET: M <= (AL)",
       "jump if (no CD and AL17 = 0) or (CD and not less)", JUMP, "4", notes="also JPMLEQ"),
    _E(0o66, None, "JPAUNG", "JUMP (AU) NEGATIVE", "CD NOT SET: (AU) NEG.; SET: M > (AL)",
       "jump if (no CD and AU17 = 1) or (CD and less)", JUMP, "4"),
    _E(0o67, None, "JPALNG", "JUMP (AL) NEGATIVE / JPMGR", "CD NOT SET: (AL) NEG.; SET: M > (AL)",
       "jump if (no CD and AL17 = 1) or (CD and less)", JUMP, "4", notes="also JPMGR"),
]

# Alternate mnemonics accepted by the assembler (the card's "or" names).
ALIASES = {"JPEQ": "JPALZ", "JPNOT": "JPALNZ", "JPMLEQ": "JPALP", "JPMGR": "JPALNG"}

# Format II minor codes that mean the same as their even neighbour (PX 2910 I-B-8).
FORMAT_II_DUPLICATES = {0o25: 0o24, 0o31: 0o30, 0o33: 0o32, 0o35: 0o34, 0o37: 0o36}

FAULT_CODES = (0o00, 0o01, 0o77)            # Format I, and 50 00 / 50 01 / 50 77
NOT_USED_II = (*range(0o02, 0o11), 0o14, 0o40, *range(0o64, 0o72), 0o74, 0o75, 0o76)

BY_CODE: dict[tuple[int, int | None], Entry] = {(e.f, e.m): e for e in CATALOG}
BY_MNEMONIC: dict[str, Entry] = {e.mnemonic: e for e in CATALOG}


def lookup(word: int) -> Entry | None:
    """The catalog entry for an instruction word (None for fault / not-used codes)."""
    f = (word >> 12) & 0o77
    if f != 0o50:
        return BY_CODE.get((f, None))
    m = (word >> 6) & 0o77
    return BY_CODE.get((0o50, FORMAT_II_DUPLICATES.get(m, m)))
