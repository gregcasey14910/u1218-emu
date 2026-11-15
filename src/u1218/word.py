"""18-bit word helpers for the UNIVAC 1218.

From the repertoire card (docs/UNIVAC_1218_Repertoire_of_Instructions_2pages.pdf):
words are 18 bits, arithmetic is ones' complement, and the A register is
36 bits made of AU (upper) and AL (lower). Words are stored as unsigned
Python ints in the range 0..MASK.

The adder type (subtractive, as assumed for the AN/UYK-7, or additive) is
not yet confirmed for the 1218; check PX 2910 before relying on -0 results.
"""

WORD_BITS = 18
MASK = (1 << WORD_BITS) - 1
SIGN = 1 << (WORD_BITS - 1)
DOUBLE_BITS = 36
DOUBLE_MASK = (1 << DOUBLE_BITS) - 1


def to_word(value: int, bits: int = WORD_BITS) -> int:
    """Encode a signed Python int as a ones' complement word of `bits` bits."""
    mask = (1 << bits) - 1
    if value < 0:
        return (~(-value)) & mask
    return value & mask


def to_int(word: int, bits: int = WORD_BITS) -> int:
    """Decode a ones' complement word to a signed Python int (-0 becomes 0)."""
    mask = (1 << bits) - 1
    word &= mask
    if word >> (bits - 1):
        return -((~word) & mask)
    return word


def is_negative(word: int, bits: int = WORD_BITS) -> bool:
    return bool((word >> (bits - 1)) & 1)


def is_zero(word: int, bits: int = WORD_BITS) -> bool:
    """True for both +0 and -0."""
    mask = (1 << bits) - 1
    word &= mask
    return word in (0, mask)


def subtract_bits(a: int, b: int, bits: int) -> int:
    """Ones' complement subtractive adder: a - b with end-around borrow."""
    mask = (1 << bits) - 1
    result = (a & mask) - (b & mask)
    if result < 0:
        result = (result - 1) & mask
    return result


def add(a: int, b: int, bits: int = WORD_BITS) -> int:
    """Ones' complement add, done as a - (-b) on a subtractive adder."""
    return subtract_bits(a, ~b, bits)


def sub(a: int, b: int, bits: int = WORD_BITS) -> int:
    return subtract_bits(a, b, bits)


def negate(word: int, bits: int = WORD_BITS) -> int:
    return (~word) & ((1 << bits) - 1)


def field(word: int, hi: int, lo: int) -> int:
    """Extract bit field [hi..lo], with bit 17 as the most significant bit."""
    return (word >> lo) & ((1 << (hi - lo + 1)) - 1)
