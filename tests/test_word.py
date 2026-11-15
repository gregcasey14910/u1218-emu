from u1218.word import MASK, add, is_zero, sub, to_int, to_word


def test_18_bit_ones_complement_round_trip():
    assert MASK == 0o777777
    assert to_word(-1) == 0o777776
    assert to_int(0o777776) == -1
    assert to_int(0o377777) == 131071


def test_subtractive_adder_avoids_minus_zero():
    assert sub(5, 5) == 0
    assert add(5, to_word(-5)) == 0
    assert is_zero(MASK)


def test_36_bit_a_register_values():
    assert to_word(-1, 36) == (1 << 36) - 2
    assert to_int(to_word(-123456789, 36), 36) == -123456789
