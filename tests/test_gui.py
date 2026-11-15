import tkinter as tk

import pytest

from u1218.gui import CPUWindow


@pytest.fixture
def window(tk_root):
    top = tk.Toplevel(tk_root)
    win = CPUWindow(top)
    yield win
    win._end_run()
    top.destroy()


def test_compile_load_and_basic_step(window):
    window.basic_load()
    assert window.program is not None and window.cpu.p == 0
    window.basic_step()                       # JP 0240, prologue, then line 20 starts
    row = window.program.rows[window.cpu.p]
    assert window.program.line_numbers[row] == 20


def test_run_to_end_and_master_clear(window):
    window.basic_load()
    window.cpu.run(100_000)
    window.refresh()
    assert window.cpu.console.text.splitlines()[-1].split() == ["25", "46368"]
    window.master_clear()
    assert window.cpu.p == 0 and window.cpu.console.text == ""


def test_keys_and_deposit(window):
    window.set_key("SKIP", 0, True)
    window.set_key("STOP", 3, True)
    assert window.cpu.skip_keys == 1 and window.cpu.stop_keys == 0o10
    window.deposit_where.insert(0, "AL")
    window.deposit_value.insert(0, "777776")
    window.deposit()
    assert window.cpu.al == 0o777776


def test_compile_error_is_reported(window):
    window.basic_text.delete("1.0", tk.END)
    window.basic_text.insert("1.0", "10 GOTO 50\n")
    window.basic_load()
    assert "does not exist" in window.basic_status.cget("text")


def test_panel_opens_on_the_same_cpu(window):
    window.open_panel()
    window.cpu.al = 0o5
    window.panel.refresh()
    assert window.panel.reg_lamps["AL"][0].lit and window.panel.reg_lamps["AL"][2].lit
    window.panel.close()
