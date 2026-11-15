from u1218.cpu import CPU
from u1218.isa import Assembler, disassemble, encode
from u1218.repertoire import BY_MNEMONIC, CATALOG, lookup


def test_catalog_is_unique_and_complete():
    codes = [(e.f, e.m) for e in CATALOG]
    assert len(codes) == len(set(codes))
    assert len(CATALOG) == 98            # PX 2910: "a repertoire of 98 instructions"


def test_every_instruction_executes_and_disassembles():
    for entry in CATALOG:
        cpu = CPU()
        operand = 0o2000 if entry.m is None else 1
        word = encode(entry.mnemonic, operand)
        assert lookup(word) is entry
        assert disassemble(word).startswith(entry.mnemonic)
        cpu.mem.load([word, 0o2000, 0o2000], 0o1000)
        cpu.p = 0o1000
        cpu.step()                        # must not raise


def test_b_instructions_are_odd_and_four_microseconds_slower():
    for entry in CATALOG:
        if entry.b_mod:
            plain = BY_MNEMONIC[entry.mnemonic[:-1]]
            assert entry.f == plain.f + 1
            assert float(entry.time) == float(plain.time) + 4


def test_assembler_labels():
    asm = Assembler(origin=0o240)
    asm.op("JP", "next")
    asm.word(0o123)
    asm.label("next")
    asm.op("ENTAL", ("next", -1))
    assert asm.assemble() == [encode("JP", 0o242), 0o123, encode("ENTAL", 0o241)]
