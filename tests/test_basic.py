import pytest

from u1218.basic import BasicError, compile_basic
from u1218.cpu import CPU
from u1218.word import to_int


def run(source: str, skip_keys: int = 0, stop_keys: int = 0, steps: int = 200_000):
    program = compile_basic(source)
    cpu = CPU()
    cpu.skip_keys, cpu.stop_keys = skip_keys, stop_keys
    program.load(cpu.mem)
    cpu.run(steps)
    return cpu, program


def value(cpu, program, name):
    return to_int(cpu.mem.read(program.variables[name]))


def test_arithmetic_and_print():
    cpu, program = run('10 A = 7 * 6 - 50 / 4\n20 B = -(A + 3) * 2\n'
                       '30 PRINT "A="; A; " B="; B\n40 C = 100000 + 31071\n')
    assert value(cpu, program, "A") == 30
    assert value(cpu, program, "B") == -66
    assert value(cpu, program, "C") == 131071
    assert cpu.console.text == "A=30 B=-66\n"
    assert cpu.stop_reason == "STOP"


def test_division_truncates_toward_zero_and_zero_prints():
    cpu, _ = run("10 PRINT -7 / 2; \" \"; 7 / -2; \" \"; 0 * -5; \" \"; 1 / 3\n")
    assert cpu.console.text == "-3 -3 0 0\n"


def test_all_comparisons():
    lines = []
    for i, relop in enumerate(("=", "<>", "<", "<=", ">", ">=")):
        n = 10 * (i + 1)
        lines.append(f'{n} IF 3 {relop} 5 THEN PRINT "{relop}";')
    cpu, _ = run("\n".join(lines))
    assert cpu.console.text == "<><<="


def test_if_then_line_and_negative_values():
    cpu, _ = run('10 A = -4\n20 IF A < -3 THEN 50\n30 PRINT "NO"\n40 END\n'
                 '50 PRINT "YES"\n')
    assert cpu.console.text == "YES\n"


def test_gosub_return_nested():
    cpu, _ = run('10 GOSUB 100\n20 PRINT "BACK"\n30 END\n100 PRINT "A";\n110 GOSUB 200\n'
                 '120 RETURN\n200 PRINT "B";\n210 RETURN\n')
    assert cpu.console.text == "ABBACK\n"


def test_for_next_steps():
    cpu, _ = run("10 FOR I = 10 TO 1 STEP -3\n20 PRINT I;\n30 NEXT I\n"
                 "40 FOR J = 1 TO 0\n50 PRINT J\n60 NEXT\n")
    assert cpu.console.text == "10741"


def test_console_keys_and_stop_key():
    source = ('10 IF KEY2 THEN PRINT "K";\n20 IF NOT KEY2 THEN PRINT "N";\n'
              '30 STOP 1\n40 PRINT "END"\n')
    cpu, _ = run(source)
    assert cpu.console.text == "NEND\n"
    cpu, _ = run(source, skip_keys=0o04, stop_keys=0o02)
    assert cpu.console.text == "K" and cpu.stop_reason == "STOP KEY"
    cpu.restart()
    cpu.run(1000)
    assert cpu.console.text == "KEND\n"


def test_end_stays_stopped():
    cpu, _ = run("10 END\n")
    cpu.restart()
    cpu.run(10)
    assert cpu.halted and cpu.stop_reason == "STOP"


def test_fibonacci_program():
    with open("programs/fibonacci.bas") as handle:
        cpu, _ = run(handle.read())
    lines = cpu.console.text.splitlines()
    assert len(lines) == 25 and lines[-1].split() == ["25", "46368"]


def test_line_map_for_colours():
    program = compile_basic("10 A = 1\n\n30 PRINT A\n")
    assert program.line_numbers == {1: 10, 3: 30}
    assert program.rows[program.row_starts[3]] == 3


@pytest.mark.parametrize("source, message", [
    ("10 GOTO 99\n", "does not exist"),
    ("20 A = 1\n10 B = 2\n", "increase"),
    ("10 FOR I = 1 TO 3\n", "without NEXT"),
    ("10 A = 200000\n", "too big"),
    ("10 STOP 7\n", "0-4"),
])
def test_errors(source, message):
    with pytest.raises(BasicError, match=message):
        compile_basic(source)
