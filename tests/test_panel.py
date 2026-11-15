import pytest

from u1218.cpu import CPU, REGISTERS
from u1218.panel import CpuDrawerPanel


def test_cpu_register_widths_and_accumulator():
    cpu = CPU()
    cpu.set("P", 0o777777)
    assert cpu.get("P") == 0o77777          # P is 15 bits
    cpu.a = 0o123456_654321
    assert (cpu.get("AU"), cpu.get("AL")) == (0o123456, 0o654321)
    cpu.flip_bit("AL", 0)
    assert cpu.a == 0o123456_654320


@pytest.fixture
def panel(tk_root):
    cpu = CPU()
    p = CpuDrawerPanel(tk_root, lambda: cpu)
    yield p, cpu
    p.close()


def test_every_register_has_a_lamp_per_bit(panel):
    p, _ = panel
    for name, width in REGISTERS:
        assert len(p.reg_lamps[name]) == width


def test_lamp_press_flips_bit_and_lights(panel):
    p, cpu = panel
    p.reg_lamps["AU"][17].command()
    assert cpu.get("AU") == 0o400000 and p.reg_lamps["AU"][17].lit
    p.reg_lamps["AU"][17].command()
    assert cpu.get("AU") == 0


def test_clear_function_mode_phase(panel):
    p, cpu = panel
    cpu.set("X", 0o777777)
    p.clear("X")
    assert cpu.get("X") == 0
    p.flip_function(5)
    p.flip_format2()
    assert cpu.function_code == 0o40 and cpu.format2
    p.clear_function()
    assert cpu.function_code == 0 and not cpu.format2
    p.select_mode("SEQ STEP")
    assert p.mode_lamps["SEQ STEP"].lit and not p.mode_lamps["RUN"].lit
    p.flip_phase(2)
    assert cpu.phase == 0b100 and p.phase_lamps[2].lit
    p.clear_phase()
    assert cpu.phase == 0


def test_sequence_lamp_follows_cpu(panel):
    p, cpu = panel
    cpu.sequence = "WAIT"
    p.refresh()
    assert p.sequence_lamps["WAIT"].lit and not p.sequence_lamps["I"].lit
