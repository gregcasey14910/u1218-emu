"""CPU tests, mostly the worked examples printed in PX 2910 section I-B."""

from u1218.cpu import CPU
from u1218.isa import encode, encode_i
from u1218.word import to_word

ORG = 0o1000


def machine(*program, **cells) -> CPU:
    """A CPU with the program at ORG; cells given as c<octal address>=value."""
    cpu = CPU()
    cpu.mem.load([encode(*op) if isinstance(op, tuple) else op for op in program], ORG)
    for name, value in cells.items():
        cpu.mem.write(int(name[1:], 8), value)
    cpu.p = ORG
    return cpu


def run(cpu: CPU, steps: int) -> CPU:
    for _ in range(steps):
        cpu.step()
    return cpu


def test_enter_store_and_constants():
    cpu = run(machine(("ENTAL", 0o2000), ("STRAL", 0o2001), ("ENTALK", 0o7776),
                      ("ENTAU", 0o2000), c2000=0o123456), 4)
    assert cpu.mem.read(0o2001) == 0o123456
    assert cpu.al == 0o777776            # ENTALK 7776 = -1 sign-extended
    assert cpu.au == 0o123456


def test_add_constant_examples():
    cpu = machine(("ADDALK", 0o0002))
    cpu.al = 0o057777
    assert run(cpu, 1).al == 0o060001
    cpu = machine(("ADDALK", 0o7775))
    cpu.al = 0o067055
    assert run(cpu, 1).al == 0o067053


def test_subtractive_adder_and_overflow():
    cpu = machine(("ADDAL", 0o2000), ("SUBAL", 0o2000), c2000=5)
    cpu.al = to_word(-5)
    run(cpu, 1)
    assert cpu.al == 0                       # -5 + 5 = +0
    cpu = machine(("ADDAL", 0o2000), ("SKPOV", 0), ("ENTALK", 1), ("ENTALK", 2), c2000=1)
    cpu.al = 0o377777
    run(cpu, 3)
    assert cpu.al == 2 and not cpu.overflow  # overflow skipped ENTALK 1 and was cleared


def test_double_add_example_with_borrow():
    # PX 2910 ADDA example: unadjusted sum, borrow recorded
    cpu = machine(("ADDA", 0o2006), c2006=0o351123, c2007=0o077430)
    cpu.a = 0o201007430145
    run(cpu, 1)
    assert cpu.a == 0o300440001271
    assert cpu.borrow


def test_multiply_and_divide_signs():
    cpu = machine(("MULAL", 0o2000), c2000=to_word(-300))
    cpu.al = 1000
    run(cpu, 1)
    assert cpu.a == to_word(-300000, 36)
    for dividend, divisor, quotient, remainder in ((5, 4, 1, 1), (5, -4, -1, 1),
                                                   (-5, 4, -1, -1), (-5, -4, 1, -1)):
        cpu = machine(("DIVA", 0o2000), c2000=to_word(divisor))
        cpu.a = to_word(dividend, 36)
        run(cpu, 1)
        assert (cpu.al, cpu.au) == (to_word(quotient), to_word(remainder))


def test_shift_examples():
    cpu = machine(encode_i(0o50, (0o41 << 6) | 2))      # RSHAU 2
    cpu.au = 0o400000
    assert run(cpu, 1).au == 0o700000
    cpu = machine(("LSHAU", 2))
    cpu.au = 0o300000
    assert run(cpu, 1).au == 0o400001
    cpu = machine(("SF", 3))
    cpu.a = 0o600000000000
    run(cpu, 1)
    assert cpu.a == 0o400000000001 and cpu.mem.read(0o17) == 2
    cpu = machine(("SF", 7))
    cpu.a = 0o170000000000
    run(cpu, 1)
    assert cpu.a == 0o360000000000 and cpu.mem.read(0o17) == 6


def test_logical_examples():
    cpu = machine(("SLSU", 0o2000), c2000=0o123451)
    cpu.au, cpu.al = 0o007777, 0o666666
    assert run(cpu, 1).al == 0o663451
    cpu = machine(("SLCP", 0o2000), c2000=0o070007)
    cpu.al = 0o123456
    assert run(cpu, 1).al == 0o153451
    cpu = machine(("SLCL", 0o2000), c2000=0o707070)
    cpu.al = 0o123456
    assert run(cpu, 1).al == 0o103050
    cpu = machine(("CPAL", 0))
    assert run(cpu, 1).al == 0                    # +0 stays +0


def test_compare_and_conditional_jumps():
    # CMSK example: compare 2351 with 3451 -> less
    cpu = machine(("CMSK", 0o2000), ("JPMGR", 0o1100), c2000=0o123451)
    cpu.au, cpu.al = 0o007777, 0o222351
    run(cpu, 2)
    assert cpu.p == 0o1100
    # without a compare, 61 tests AL = +0 (negative zero is not zero)
    cpu = machine(("JPALZ", 0o1100))
    cpu.al = 0o777777
    assert run(cpu, 1).p == ORG + 1
    # the comparison designator is cleared by any other instruction
    cpu = machine(("CMAL", 0o2000), ("ENTALK", 5), ("JPEQ", 0o1100), c2000=0)
    assert run(cpu, 3).p == ORG + 3


def test_index_registers_and_b_modification():
    cpu = machine(("ENTICR", 3), ("ENTBK", 0o0004), ("ENTALB", 0o2000), ("ENTBKB", 0o7776),
                  ("STRICR", 0o2100), c2004=0o111111)
    run(cpu, 5)
    assert cpu.al == 0o111111                        # (2000 + B=4)
    assert cpu.mem.read(3) == 0o000003               # B = 4 + (-1), held in core 00003
    assert cpu.mem.read(0o2100) & 0o77 == 3
    cpu = machine(("STRICR", 0o2100))
    assert run(cpu, 1).mem.read(0o2100) == 0o10     # ICR 0 -> 00010


def test_sr_banking():
    cpu = machine(("ENTSR", 0o12), ("ENTAL", 0o0005), ("STRSR", 0o2000), ("ENTAL", 0o0005))
    cpu.mem.write(0o20005, 0o222222)
    cpu.mem.write(0o00005, 0o333333)
    run(cpu, 2)
    assert cpu.al == 0o222222                        # SR active, bank 2
    run(cpu, 2)
    assert cpu.mem.read(0o2000) == 0o12 and cpu.sr == 0 and cpu.al == 0o333333


def test_return_jumps_and_loops():
    cpu = machine(("RJP", 0o1100), ("ENTALK", 7))
    cpu.mem.load([encode("IJP", 0o1100)], 0o1101)
    run(cpu, 3)
    assert cpu.al == 7 and cpu.mem.read(0o1100) == ORG + 1
    cpu = machine(("ISK", 0o2000), c2000=0o777777)
    assert run(cpu, 1).mem.read(0o2000) == 0o777776 and cpu.p == ORG + 1
    cpu = machine(("ENTBK", 3), ("BJP", ORG + 1))
    run(cpu, 5)
    assert cpu.b == 0 and cpu.p == ORG + 2


def test_console_keys_stop_and_output():
    cpu = machine(("SKP", 0o04), ("STOP", 0o01), ("STOP", 0o40))
    cpu.skip_keys = 0o04
    run(cpu, 1)
    assert cpu.p == ORG + 2 and cpu.skip_light == 0o04
    run(cpu, 1)
    assert cpu.halted and cpu.stop_reason == "STOP"
    cpu = machine(("OUT", 7), ORG + 5, ORG + 3, ord("H"), ord("I"))
    run(cpu, 1)
    assert cpu.console.text == "HI" and cpu.p == ORG + 3


def test_fault_goes_to_entrance_and_stops():
    cpu = machine(0)
    run(cpu, 1)
    assert cpu.fault and cpu.halted and cpu.p == 0
    cpu = machine(0o770000)
    cpu.auto_recovery = True
    assert run(cpu, 1).p == 0o200


def test_bootstrap_is_read_only():
    cpu = machine(("ENTALK", 1), ("STRAL", 0o0210))
    run(cpu, 2)
    assert cpu.mem.read(0o210) == 0
