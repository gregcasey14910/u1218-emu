"""UNIVAC 1218 emulator main window: registers, console keys, memory and BASIC.

Left: registers, designators and the console (skip / stop keys, AUTO RECOVERY).
Centre: memory, following P, with the BASIC line of each word and its colour.
Right: BASIC editor, compile / step / run, console printer output and the
generated code. The CPU drawer panel opens beside it (Panel button or --panel).

A run executes in time slices so the windows stay live; Stop ends it after the
current instruction (or, for Run BASIC, at the end of the current line).
"""

from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from .basic import BasicError, CompiledProgram, compile_basic
from .cpu import CPU
from .isa import disassemble
from .widgets import Led, ToggleSwitch
from .word import to_int

MEMORY_ROWS = 32
BASIC_STEP_LIMIT = 100_000
RUN_SLICE_MS = 30
LINE_COLORS = ("#ffd6d6", "#ffe7c2", "#fff6a8", "#d6f5c6",
               "#c9ecf5", "#d9dcff", "#f0d6f5", "#e6e6e6")
FONT = ("Consolas", 10)
SAMPLE_BASIC = """10 REM Fibonacci numbers, 25 terms
20 A = 0
30 B = 1
40 FOR I = 1 TO 25
50 PRINT I, A
60 C = A + B
70 A = B
80 B = C
90 NEXT I
100 IF KEY0 THEN 20
110 END
"""


class CPUWindow:
    def __init__(self, root: tk.Tk, cpu: CPU | None = None, basic_file: str | None = None,
                 panel: bool = False) -> None:
        self.root = root
        self.cpu = cpu or CPU()
        self.program: CompiledProgram | None = None
        self.loaded_source: str | None = None
        self.row_colors: dict[int, int] = {}
        self.running = False
        self.run_basic = False
        self.stop_requested = False
        self._run_job: str | None = None
        self.memory_top = 0
        self.panel = None
        root.title("UNIVAC 1218 Emulator")
        root.minsize(1400, 760)
        self._build()
        self.cpu.reset()
        self.refresh()
        if basic_file:
            self.basic_open(basic_file)
        if panel:
            self.root.after(300, self.open_panel)

    # ------------------------------------------------------------ layout

    def _build(self) -> None:
        panes = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        left = ttk.Frame(panes)
        centre = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=0)
        panes.add(centre, weight=1)
        panes.add(right, weight=1)
        self._build_registers(left)
        self._build_console(left)
        self._build_controls(left)
        self._build_memory(centre)
        self._build_basic(right)

    def _build_registers(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Registers", padding=8)
        box.pack(fill=tk.X)
        self.reg_labels: dict[str, ttk.Label] = {}
        rows = (("AU", "upper accumulator"), ("AL", "lower accumulator"), ("A", "AU:AL, 36 bits"),
                ("B", "active index register"), ("ICR", "index control"),
                ("SR", "special (bank) register"), ("P", "program address"),
                ("F", "function register"), ("X", "exchange: operand"),
                ("D", "arithmetic exchange: result"), ("S", "memory address"),
                ("Z", "memory buffer"))
        for row, (name, hint) in enumerate(rows):
            ttk.Label(box, text=name, font=("Consolas", 10, "bold"), width=4).grid(
                row=row, column=0, sticky=tk.W)
            label = ttk.Label(box, text="", font=FONT, width=26)
            label.grid(row=row, column=1, sticky=tk.W)
            ttk.Label(box, text=hint, foreground="#666666").grid(row=row, column=2, sticky=tk.W)
            self.reg_labels[name] = label
        self.designators = ttk.Label(box, text="", font=FONT)
        self.designators.grid(row=len(rows), column=0, columnspan=3, sticky=tk.W, pady=(6, 0))
        deposit = ttk.Frame(box)
        deposit.grid(row=len(rows) + 1, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))
        ttk.Label(deposit, text="Set").pack(side=tk.LEFT)
        self.deposit_where = ttk.Entry(deposit, width=8)
        self.deposit_where.pack(side=tk.LEFT, padx=3)
        ttk.Label(deposit, text="=").pack(side=tk.LEFT)
        self.deposit_value = ttk.Entry(deposit, width=14)
        self.deposit_value.pack(side=tk.LEFT, padx=3)
        ttk.Button(deposit, text="Deposit", command=self.deposit).pack(side=tk.LEFT)
        ttk.Label(box, text="Address or register (AU AL A B ICR SR P), octal value",
                  foreground="#666666").grid(row=len(rows) + 2, column=0, columnspan=3,
                                            sticky=tk.W)

    def _build_console(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Console", padding=8)
        box.pack(fill=tk.X, pady=(6, 0))
        self.key_switches: dict[tuple[str, int], ToggleSwitch] = {}
        self.key_lamps: dict[tuple[str, int], Led] = {}
        for row, (kind, color, hint) in enumerate((("SKIP", "white", "SKP k, IF KEYn"),
                                                  ("STOP", "red", "STOP k, STOP n"))):
            ttk.Label(box, text=f"{kind} KEYS", width=10).grid(row=2 * row, column=0, rowspan=2,
                                                              sticky=tk.W)
            for key in range(5):
                column = 5 - key
                switch = ToggleSwitch(box, command=lambda on, k=kind, n=key:
                                      self.set_key(k, n, on), show_text=False)
                switch.grid(row=2 * row, column=column, padx=2)
                lamp = Led(box, color=color, size=16)
                lamp.grid(row=2 * row + 1, column=column)
                ttk.Label(box, text=str(key)).grid(row=2 * row + 1, column=column, sticky=tk.E)
                self.key_switches[(kind, key)] = switch
                self.key_lamps[(kind, key)] = lamp
            ttk.Label(box, text=hint, foreground="#666666").grid(row=2 * row, column=6,
                                                                rowspan=2, padx=6)
        extra = ttk.Frame(box)
        extra.grid(row=4, column=0, columnspan=7, sticky=tk.W, pady=(6, 0))
        self.auto_recovery = tk.BooleanVar(value=self.cpu.auto_recovery)
        ttk.Checkbutton(extra, text="AUTO RECOVERY (fault -> bootstrap 00200)",
                        variable=self.auto_recovery,
                        command=self._set_auto_recovery).pack(side=tk.LEFT)
        ttk.Label(extra, text="  FAULT").pack(side=tk.LEFT)
        self.fault_lamp = Led(extra, color="red", size=16)
        self.fault_lamp.pack(side=tk.LEFT, padx=3)
        ttk.Label(extra, text=" RUN").pack(side=tk.LEFT)
        self.run_lamp = Led(extra, color="green", size=16)
        self.run_lamp.pack(side=tk.LEFT, padx=3)

    def _build_controls(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Control", padding=8)
        box.pack(fill=tk.X, pady=(6, 0))
        buttons = ttk.Frame(box)
        buttons.pack(fill=tk.X)
        for text, command in (("Step", self.step), ("Run", self.run), ("Stop", self.request_stop),
                              ("Master Clear", self.master_clear), ("Panel", self.open_panel)):
            ttk.Button(buttons, text=text, command=command).pack(side=tk.LEFT, padx=(0, 4))
        self.status = ttk.Label(box, text="Ready", font=FONT)
        self.status.pack(anchor=tk.W, pady=(6, 0))
        self.counts = ttk.Label(box, text="", foreground="#444444")
        self.counts.pack(anchor=tk.W)

    def _build_memory(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Memory", padding=6)
        box.pack(fill=tk.BOTH, expand=True)
        top = ttk.Frame(box)
        top.pack(fill=tk.X)
        self.follow_p = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Follow P", variable=self.follow_p,
                        command=self._refresh_memory).pack(side=tk.LEFT)
        ttk.Label(top, text="   Go to (octal)").pack(side=tk.LEFT)
        self.goto_address = ttk.Entry(top, width=8)
        self.goto_address.pack(side=tk.LEFT, padx=4)
        self.goto_address.bind("<Return>", lambda _e: self._memory_goto())
        ttk.Button(top, text="Go", command=self._memory_goto).pack(side=tk.LEFT)
        frame = ttk.Frame(box)
        frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        columns = ("p", "address", "octal", "instruction", "line")
        self.memory = ttk.Treeview(frame, columns=columns, show="headings", height=MEMORY_ROWS)
        for name, title, width in (("p", "", 24), ("address", "Address", 70),
                                   ("octal", "Word", 70), ("instruction", "Instruction", 170),
                                   ("line", "BASIC", 60)):
            self.memory.heading(name, text=title)
            self.memory.column(name, width=width, anchor=tk.W, stretch=name == "instruction")
        for index, color in enumerate(LINE_COLORS):
            self.memory.tag_configure(f"c{index}", background=color)
        self.memory.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.memory_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                           command=self._memory_scrolled)
        self.memory_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.memory.bind("<MouseWheel>", self._memory_wheel)

    def _build_basic(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="BASIC", padding=8)
        box.pack(fill=tk.BOTH, expand=True)
        ttk.Label(box, text="00000 jumps to the program at 00240.  IF [NOT] KEYn uses skip key n; "
                  "STOP n uses stop key n (0-4).", wraplength=430).pack(anchor=tk.W)
        self.basic_text = tk.Text(box, width=50, height=16, font=FONT, undo=True, wrap=tk.NONE)
        self.basic_text.insert("1.0", SAMPLE_BASIC)
        self.basic_text.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        for index, color in enumerate(LINE_COLORS):
            self.basic_text.tag_configure(f"bc{index}", background=color)
        self.basic_text.tag_configure("current", font=("Consolas", 10, "bold"),
                                      relief=tk.RAISED, borderwidth=1)
        self.basic_text.bind("<<Modified>>", self._basic_modified)
        row = ttk.Frame(box)
        row.pack(fill=tk.X)
        ttk.Button(row, text="Compile & Load", command=self.basic_load).pack(side=tk.LEFT)
        ttk.Button(row, text="Compile, Load & Run",
                   command=lambda: self.basic_load(run=True)).pack(side=tk.LEFT, padx=6)
        ttk.Button(row, text="Save...", command=self.basic_save).pack(side=tk.RIGHT)
        ttk.Button(row, text="Open...", command=self.basic_open).pack(side=tk.RIGHT, padx=6)
        row = ttk.Frame(box)
        row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(row, text="Step BASIC line", command=self.basic_step).pack(side=tk.LEFT)
        ttk.Button(row, text="Run BASIC", command=self.basic_run).pack(side=tk.LEFT, padx=6)
        self.basic_status = ttk.Label(box, text="", wraplength=430, foreground="#1a5e1a")
        self.basic_status.pack(anchor=tk.W, pady=4)
        tabs = ttk.Notebook(box)
        tabs.pack(fill=tk.BOTH, expand=True)
        self.output = tk.Text(tabs, width=50, height=14, font=("Consolas", 9), wrap=tk.NONE,
                              state=tk.DISABLED)
        self.listing = tk.Text(tabs, width=50, height=14, font=("Consolas", 9), wrap=tk.NONE,
                               state=tk.DISABLED)
        tabs.add(self.output, text="Printer / Variables")
        tabs.add(self.listing, text="Generated code")

    # ------------------------------------------------------------ panel

    def open_panel(self) -> None:
        from .panel import CpuDrawerPanel

        if self.panel is not None and self.panel.winfo_exists():
            self.panel.lift()
            return
        self.panel = CpuDrawerPanel(self.root, lambda: self.cpu, on_change=self.refresh)
        recovery = self.panel.switches.get("AUTO RECOVERY")
        if recovery is not None:
            recovery.set(self.cpu.auto_recovery)
            recovery._command = self._panel_auto_recovery
        self.panel.lift()
        self.panel.attributes("-topmost", True)
        self.root.after(300, lambda: self.panel.attributes("-topmost", False))

    def _panel_auto_recovery(self, on: bool) -> None:
        self.cpu.auto_recovery = on
        self.auto_recovery.set(on)

    def _set_auto_recovery(self) -> None:
        self.cpu.auto_recovery = self.auto_recovery.get()
        if self.panel is not None and self.panel.winfo_exists():
            switch = self.panel.switches.get("AUTO RECOVERY")
            if switch is not None:
                switch.set(self.cpu.auto_recovery)

    # ------------------------------------------------------------ console keys

    def set_key(self, kind: str, key: int, on: bool) -> None:
        attribute = "skip_keys" if kind == "SKIP" else "stop_keys"
        value = getattr(self.cpu, attribute)
        setattr(self.cpu, attribute, value | (1 << key) if on else value & ~(1 << key))

    # ------------------------------------------------------------ refresh

    def refresh(self) -> None:
        cpu = self.cpu
        regs = cpu.regs

        def word(value: int) -> str:
            return f"{value:06o}  ({to_int(value):+d})"

        labels = self.reg_labels
        labels["AU"].configure(text=word(cpu.au))
        labels["AL"].configure(text=word(cpu.al))
        labels["A"].configure(text=f"{cpu.a:012o}  ({to_int(cpu.a, 36):+d})")
        labels["B"].configure(text=f"{word(cpu.b)}  @{cpu.index_address():02o}")
        labels["ICR"].configure(text=f"{cpu.icr}")
        labels["SR"].configure(text=f"{cpu.sr:02o}  ({'active, bank ' + str(cpu.sr & 7) if cpu.sr_active else 'inactive'})")
        labels["P"].configure(text=f"{cpu.p:05o}")
        labels["F"].configure(text=f"{'50 ' if cpu.format2 else ''}{cpu.function_code:02o}")
        for name in ("X", "D", "Z"):
            labels[name].configure(text=f"{regs[name]:06o}")
        labels["S"].configure(text=f"{regs['S']:05o}")
        cd = "-" if cpu.cd is None else ("LESS " if cpu.cd[0] else "") + ("EQUAL" if cpu.cd[1] else "")
        self.designators.configure(
            text=f"Overflow {int(cpu.overflow)}   Borrow {int(cpu.borrow)}   Compare {cd or 'set'}")
        for (kind, key), lamp in self.key_lamps.items():
            light = cpu.skip_light if kind == "SKIP" else cpu.stop_light
            lamp.set(bool(light >> key & 1))
        self.fault_lamp.set(cpu.fault)
        self.run_lamp.set(self.running)
        if not self.running:
            state = f"Stopped: {cpu.stop_reason}" if cpu.halted else "Ready"
            self.status.configure(text=state)
        self.counts.configure(text=f"{cpu.cycles} instructions, "
                                   f"{cpu.micros / 1000:.3f} ms machine time")
        self._refresh_memory()
        self._refresh_output()
        self._refresh_current_line()

    def _source_current(self) -> bool:
        return (self.program is not None
                and self.loaded_source == self.basic_text.get("1.0", "end-1c"))

    def _refresh_memory(self) -> None:
        p = self.cpu.p
        size = self.cpu.mem.size
        if self.follow_p.get() and not (self.memory_top + 2 <= p < self.memory_top + MEMORY_ROWS - 2):
            self.memory_top = max(0, min(p - MEMORY_ROWS // 3, size - MEMORY_ROWS))
        self.memory.delete(*self.memory.get_children())
        program = self.program if self._source_current() else None
        first, last = self.memory_top, min(size, self.memory_top + MEMORY_ROWS)
        for address in range(first, last):
            value = self.cpu.mem.read(address)
            tags, line = (), ""
            if program is not None and address in program.rows:
                row = program.rows[address]
                tags = (f"c{self.row_colors.get(row, 7)}",)
                if program.row_starts.get(row) == address:
                    line = str(program.line_numbers.get(row, ""))
            item = self.memory.insert("", tk.END, tags=tags, values=(
                ">" if address == p else "", f"{address:05o}", f"{value:06o}",
                disassemble(value), line))
            if address == p:
                self.memory.selection_set(item)
        self.memory_scroll.set(first / size, last / size)

    def _memory_scrolled(self, *args) -> None:
        size = self.cpu.mem.size
        if args[0] == "moveto":
            top = int(float(args[1]) * size)
        else:
            top = self.memory_top + int(args[1]) * (MEMORY_ROWS - 2 if args[2] == "pages" else 1)
        self.follow_p.set(False)
        self.memory_top = max(0, min(top, size - MEMORY_ROWS))
        self._refresh_memory()

    def _memory_wheel(self, event) -> str:
        self._memory_scrolled("scroll", -3 * (event.delta // 120), "units")
        return "break"

    def _memory_goto(self) -> None:
        try:
            address = int(self.goto_address.get(), 8)
        except ValueError:
            self.status.configure(text="Go to: enter an octal address")
            return
        self.follow_p.set(False)
        self.memory_top = max(0, min(address - 2, self.cpu.mem.size - MEMORY_ROWS))
        self._refresh_memory()

    def _refresh_output(self) -> None:
        text = self.cpu.console.text
        if self.program is not None:
            values = "  ".join(f"{name}={to_int(self.cpu.mem.read(address))}"
                               for name, address in sorted(self.program.variables.items()))
            text += f"\n---- variables ----\n{values}\n"
        self._set_text(self.output, text)
        self.output.see(tk.END)

    @staticmethod
    def _set_text(widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state=tk.DISABLED)

    def _refresh_current_line(self) -> None:
        self.basic_text.tag_remove("current", "1.0", tk.END)
        if not self._source_current():
            return
        row = self.program.rows.get(self.cpu.p)
        if row is not None:
            self.basic_text.tag_add("current", f"{row}.0", f"{row}.0 lineend")
            self.basic_text.see(f"{row}.0")

    # ------------------------------------------------------------ deposit

    def deposit(self) -> None:
        where = self.deposit_where.get().strip().upper()
        try:
            value = int(self.deposit_value.get().strip(), 8)
        except ValueError:
            self.status.configure(text="Deposit: value must be octal")
            return
        cpu = self.cpu
        if where in ("AU", "AL", "P"):
            cpu.set(where, value)
        elif where == "A":
            cpu.a = value
        elif where == "B":
            cpu.b = value
        elif where == "ICR":
            cpu.icr = value & 7
        elif where == "SR":
            cpu.sr = value & 0o17
        else:
            try:
                cpu.mem.write(int(where, 8), value, force=True)
            except ValueError:
                self.status.configure(text="Deposit: octal address or register name")
                return
        self.refresh()

    # ------------------------------------------------------------ BASIC

    def _basic_modified(self, _event=None) -> None:
        self.basic_text.edit_modified(False)
        if self.program is not None and not self._source_current():
            for tag in [f"bc{i}" for i in range(len(LINE_COLORS))] + ["current"]:
                self.basic_text.tag_remove(tag, "1.0", tk.END)
            self.basic_status.configure(text="Source changed: Compile & Load again.",
                                        foreground="#8a5a00")
            self._refresh_memory()

    def basic_load(self, run: bool = False) -> None:
        source = self.basic_text.get("1.0", "end-1c")
        try:
            program = compile_basic(source)
        except BasicError as error:
            self.basic_status.configure(text=f"Error: {error}", foreground="#b00020")
            return
        self._end_run()
        self.program, self.loaded_source = program, source
        self.cpu.mem.clear()
        self.cpu.reset()
        self.cpu.console.clear()
        program.load(self.cpu.mem)
        self.row_colors = {}
        for tag in [f"bc{i}" for i in range(len(LINE_COLORS))]:
            self.basic_text.tag_remove(tag, "1.0", tk.END)
        for index, row in enumerate(sorted(program.row_starts)):
            color = index % len(LINE_COLORS)
            self.row_colors[row] = color
            self.basic_text.tag_add(f"bc{color}", f"{row}.0", f"{row}.0 lineend +1c")
        self._set_text(self.listing, program.listing)
        size = program.end_address - 0o240 + 1
        self.basic_status.configure(
            text=f"Loaded: {len(program.line_numbers)} lines, {size} words "
                 f"(00240-{program.end_address - 1:05o})", foreground="#1a5e1a")
        self.follow_p.set(True)
        self.refresh()
        if run:
            self.basic_run()

    def _basic_ready(self) -> bool:
        if not self._source_current():
            self.basic_status.configure(text="Compile & Load the BASIC program first.",
                                        foreground="#8a5a00")
            return False
        return True

    def basic_step(self) -> None:
        """Run machine instructions until the next BASIC line starts."""
        if self.running or not self._basic_ready():
            return
        program = self.program
        self.cpu.restart()
        steps = 0
        while steps < BASIC_STEP_LIMIT and not self.cpu.halted:
            self.cpu.step()
            steps += 1
            row = program.rows.get(self.cpu.p)
            if row is not None and program.row_starts.get(row) == self.cpu.p:
                break
        row = program.rows.get(self.cpu.p)
        number = program.line_numbers.get(row) if row is not None else None
        if self.cpu.halted:
            message = f"Stopped after {steps} instructions: {self.cpu.stop_reason}"
        else:
            message = f"Next: line {number}  ({steps} machine instructions)"
        self.basic_status.configure(text=message, foreground="#1a5e1a")
        self.refresh()

    def basic_run(self) -> None:
        if self.running or not self._basic_ready():
            return
        self._start_run(basic=True)

    def basic_open(self, path: str | None = None) -> None:
        path = path or filedialog.askopenfilename(
            filetypes=[("BASIC", "*.bas"), ("All files", "*.*")],
            initialdir=Path.cwd() / "programs")
        if not path:
            return
        self.basic_text.delete("1.0", tk.END)
        self.basic_text.insert("1.0", Path(path).read_text())
        self.basic_status.configure(text=f"Opened {Path(path).name}", foreground="#1a5e1a")

    def basic_save(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".bas",
                                            filetypes=[("BASIC", "*.bas")],
                                            initialdir=Path.cwd() / "programs")
        if path:
            Path(path).write_text(self.basic_text.get("1.0", "end-1c") + "\n")
            self.basic_status.configure(text=f"Saved {Path(path).name}", foreground="#1a5e1a")

    # ------------------------------------------------------------ running

    def step(self) -> None:
        if self.running:
            return
        self.cpu.restart()
        self.cpu.step()
        self.refresh()

    def run(self) -> None:
        if not self.running:
            self._start_run(basic=False)

    def _start_run(self, basic: bool) -> None:
        self.cpu.restart()
        if self.cpu.halted:
            self.refresh()
            return
        self.running, self.run_basic, self.stop_requested = True, basic, False
        self.status.configure(text="Running")
        self._run_job = self.root.after(1, self._run_slice)

    def _at_line_start(self) -> bool:
        program = self.program
        if program is None:
            return True
        row = program.rows.get(self.cpu.p)
        return row is not None and program.row_starts.get(row) == self.cpu.p

    def _run_slice(self) -> None:
        self._run_job = None
        if not self.running:
            return
        deadline = time.perf_counter() + RUN_SLICE_MS / 1000
        cpu = self.cpu
        while time.perf_counter() < deadline:
            for _ in range(500):
                if cpu.halted:
                    self._finish(f"Stopped: {cpu.stop_reason}")
                    return
                if self.stop_requested and (not self.run_basic or self._at_line_start()):
                    cpu.stop("PANEL STOP")
                    self._finish("Stopped by Stop")
                    return
                cpu.step()
        self.refresh()
        self._run_job = self.root.after(1, self._run_slice)

    def _finish(self, message: str) -> None:
        self.running = False
        self.stop_requested = False
        self.status.configure(text=message)
        if self.run_basic:
            self.basic_status.configure(text=f"Run: {message} after {self.cpu.cycles} "
                                             "instructions", foreground="#1a5e1a")
        self.refresh()

    def _end_run(self) -> None:
        if self._run_job is not None:
            self.root.after_cancel(self._run_job)
            self._run_job = None
        self.running = False
        self.stop_requested = False

    def request_stop(self) -> None:
        if self.running:
            self.stop_requested = True

    def master_clear(self) -> None:
        """MASTER CLEAR: stop, clear registers and designators, P = 0, and reload the
        BASIC program so the next start begins it again."""
        self._end_run()
        self.cpu.reset()
        self.cpu.console.clear()
        if self._source_current():
            self.program.load(self.cpu.mem)          # fresh variables and data
        self.status.configure(text="MASTER CLEAR")
        self.follow_p.set(True)
        self.refresh()


def main(basic_file: str | None = None, panel: bool = False) -> None:
    root = tk.Tk()
    CPUWindow(root, basic_file=basic_file, panel=panel)
    root.mainloop()


if __name__ == "__main__":
    main()
