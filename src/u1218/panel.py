"""The UNIVAC 1218 control panel: CPU drawer, in its own Tk window.

Laid out after docs/1218_panel.jpg (right-hand drawer, "T.S. 746"); the test
point blocks at the drawer edges are left out. Live now:

    register lamps   pressing a lamp flips that bit (manual alteration of registers)
    white buttons    clear the register / function code / phase beside them
    MODE lamps       select the mode (one lit at a time)
    knob             clock speed, 0-100 %

The SEQUENCE lamps are indicators; the toggle switches are mock-ups until the
CPU runs. A panel is a FrontPanel subclass registered in PANELS so other
drawers can be added later.

Run standalone with:  python -m u1218.panel   (or  u1218 --panel)
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .cpu import CPU, FUNCTION_BITS, MODES, PHASES, SEQUENCES, WIDTH
from .widgets import Bracket, CapButton, DomeLamp, Knob, ThreeWaySwitch, ToggleSwitch

CABINET = "#8e938b"      # cabinet paint around the drawer
FRAME = "#d6d6d0"        # aluminium drawer frame
LIGHT = "#b4bccb"        # light blue-grey panel areas
DARK = "#3e4452"         # dark slate panel areas
RULE = "#c9ced8"         # rules between boxes
INK = "#f4f4f4"          # legends on the dark areas
LIGHT_INK = "#1f2633"    # legends on the light areas (white in the photo, darkened to read)
TAG = "#a3262a"          # the red "T.S. 746" tag
FONT = ("Arial", 7)
LAMP = 17
PITCH = 22               # lamp-to-lamp distance inside a register
REFRESH_MS = 100

CpuProvider = Callable[[], CPU]


class PanelToggle(ToggleSwitch):
    HEIGHT = 48            # no ON/OFF text under the lever


class PanelThreeWay(ThreeWaySwitch):
    HEIGHT = 48


class FrontPanel(tk.Toplevel):
    """Base class for a panel window bound to a CPU (via a provider)."""

    title_text = "UNIVAC 1218 Panel"

    def __init__(self, master: tk.Misc, cpu_provider: CpuProvider,
                 on_change: Callable[[], None] | None = None) -> None:
        super().__init__(master, background=CABINET)
        self.cpu_provider = cpu_provider
        self.on_change = on_change
        self.all_lamps: list[DomeLamp] = []
        self.title(self.title_text)
        self.resizable(False, False)
        self._alive = True
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.build()
        self.refresh()
        self.after(REFRESH_MS, self._tick)

    @property
    def cpu(self) -> CPU:
        return self.cpu_provider()

    def build(self) -> None:
        raise NotImplementedError

    def refresh(self) -> None:
        pass

    def _tick(self) -> None:
        if not self._alive:
            return
        try:
            self.refresh()
        finally:
            self.after(REFRESH_MS, self._tick)

    def close(self) -> None:
        self._alive = False
        self.destroy()

    def changed(self) -> None:
        """The panel altered machine state: redraw and tell the owner."""
        self.refresh()
        if self.on_change:
            self.on_change()

    def lamp_test(self, on: bool) -> None:
        for lamp in self.all_lamps:
            lamp.set_test(on)


class CpuDrawerPanel(FrontPanel):
    """The CPU drawer of the 1218 control panel."""

    title_text = "UNIVAC 1218 - CPU drawer"

    def build(self) -> None:
        self.reg_lamps: dict[str, list[DomeLamp]] = {}      # name -> lamp per bit (index = bit)
        self.function_lamps: list[DomeLamp] = []           # index = bit of f
        self.sequence_lamps: dict[str, DomeLamp] = {}
        self.mode_lamps: dict[str, DomeLamp] = {}
        self.phase_lamps: list[DomeLamp] = []
        self.switches: dict[str, tk.Widget] = {}

        drawer = tk.Frame(self, background=FRAME, padx=7, pady=7)
        drawer.pack(padx=14, pady=14)
        self.face = tk.Frame(drawer, background=RULE)
        self.face.pack()

        self.build_tag()
        self.register_pair(("AU", "AL"), LIGHT)
        self.register_pair(("Q", "X"), DARK)
        self.build_sequence()
        self.build_latch()
        self.register_pair(("S", "P"), DARK)
        self.build_function()
        self.build_mode()
        self.build_phase()
        self.build_switches()

    # ------------------------------------------------------------ layout helpers

    def section(self, background: str, pady: int = 1) -> tk.Frame:
        frame = tk.Frame(self.face, background=background)
        frame.pack(fill=tk.X, padx=1, pady=(0, pady))
        return frame

    def text(self, parent: tk.Misc, text: str, background: str, size: int = 6) -> tk.Label:
        return tk.Label(parent, text=text, font=("Arial", size),
                        foreground=LIGHT_INK if background == LIGHT else INK,
                        background=background, padx=0, pady=0, justify=tk.CENTER)

    def lamp(self, parent: tk.Misc, background: str,
             command: Callable[[], None] | None = None) -> DomeLamp:
        widget = DomeLamp(parent, size=LAMP, background=background, command=command)
        self.all_lamps.append(widget)
        return widget

    # ------------------------------------------------------------ sections

    def build_tag(self) -> None:
        row = self.section(LIGHT, pady=0)
        tk.Label(row, text="T.S.746", font=("Arial", 11), foreground="#f3e6dc",
                 background=TAG, padx=8, pady=0).pack(side=tk.LEFT, padx=8, pady=(5, 1))

    def register_pair(self, names: tuple[str, str], background: str) -> None:
        row = self.section(background)
        for i, name in enumerate(names):
            if i:
                tk.Frame(row, background=RULE, width=2).pack(side=tk.LEFT, fill=tk.Y)
            box = tk.Frame(row, background=background, padx=8, pady=1)
            box.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
            self.build_register(box, name, background)

    def build_register(self, box: tk.Frame, name: str, background: str) -> None:
        """Lamps three to a row (one octal digit), MSB top left; CLEAR button top right."""
        width = WIDTH[name]
        lamps: list[DomeLamp | None] = [None] * width
        Bracket(box, width=3 * PITCH, text=name, background=background, height=13,
                ink=LIGHT_INK if background == LIGHT else INK).grid(
            row=0, column=0, columnspan=3, pady=(1, 0))
        for r in range(width // 3):
            for c in range(3):
                bit = width - 1 - 3 * r - c
                lamp = self.lamp(box, background,
                                 command=lambda n=name, b=bit: self.flip(n, b))
                lamp.grid(row=1 + 2 * r, column=c, padx=(PITCH - LAMP) // 2)
                lamps[bit] = lamp
                self.text(box, str(bit), background).grid(row=2 + 2 * r, column=c)
        CapButton(box, size=LAMP, background=background,
                  command=lambda n=name: self.clear(n)).grid(row=1, column=3, padx=(4, 0))
        self.reg_lamps[name] = lamps  # type: ignore[assignment]

    def build_sequence(self) -> None:
        box = tk.Frame(self.section(DARK), background=DARK, pady=1)
        box.pack()
        Bracket(box, width=len(SEQUENCES) * PITCH, text="SEQUENCE", background=DARK).grid(
            row=0, column=0, columnspan=len(SEQUENCES))
        for c, name in enumerate(SEQUENCES):
            lamp = self.lamp(box, DARK)
            lamp.grid(row=1, column=c, padx=(PITCH - LAMP) // 2 + 2)
            self.text(box, name, DARK).grid(row=2, column=c)
            self.sequence_lamps[name] = lamp

    def build_latch(self) -> None:
        """The drawer pull: a plain strip with a screw and the square-socket latch."""
        row = self.section(LIGHT)
        canvas = tk.Canvas(row, height=30, background=LIGHT, highlightthickness=0)
        canvas.pack(fill=tk.X)
        canvas.bind("<Configure>", lambda e: self._draw_latch(canvas, e.width))

    @staticmethod
    def _draw_latch(canvas: tk.Canvas, width: int) -> None:
        canvas.delete("all")
        x, y = width - 70, 15
        canvas.create_oval(x - 14, y - 14, x + 14, y + 14, fill="#e8e8e4", outline="#7d7d7d",
                           width=2)
        canvas.create_oval(x - 10, y - 10, x + 10, y + 10, fill="#2a2a2a", outline="")
        canvas.create_polygon(x, y - 6, x + 6, y, x, y + 6, x - 6, y, fill="#9a9a9a",
                              outline="#555555")
        sx = 40
        canvas.create_oval(sx - 6, y - 6, sx + 6, y + 6, fill="#d0d0d0", outline="#777777")
        canvas.create_line(sx - 4, y, sx + 4, y, fill="#777777")

    def build_function(self) -> None:
        box = tk.Frame(self.section(DARK), background=DARK, pady=1)
        box.pack()
        columns = 1 + FUNCTION_BITS + 1
        Bracket(box, width=(columns - 1) * PITCH + 10, text="U", background=DARK).grid(
            row=0, column=0, columnspan=columns - 1, sticky=tk.W)
        self.text(box, "FORMAT II", DARK).grid(row=1, column=0)
        Bracket(box, width=FUNCTION_BITS * PITCH, text="FUNCTION CODE", background=DARK).grid(
            row=1, column=1, columnspan=FUNCTION_BITS)
        self.format2_lamp = self.lamp(box, DARK, command=self.flip_format2)
        self.format2_lamp.grid(row=2, column=0, padx=6)
        lamps: list[DomeLamp | None] = [None] * FUNCTION_BITS
        for i in range(FUNCTION_BITS):
            bit = FUNCTION_BITS - 1 - i
            lamp = self.lamp(box, DARK, command=lambda b=bit: self.flip_function(b))
            lamp.grid(row=2, column=1 + i, padx=(PITCH - LAMP) // 2)
            lamps[bit] = lamp
        self.function_lamps = lamps  # type: ignore[assignment]
        CapButton(box, size=LAMP, background=DARK, command=self.clear_function).grid(
            row=2, column=columns - 1, padx=(8, 0))

    def build_mode(self) -> None:
        box = tk.Frame(self.section(DARK), background=DARK, pady=1)
        box.pack(fill=tk.X)
        Bracket(box, width=4 * 54, text="MODE", background=DARK).grid(
            row=0, column=0, columnspan=4, padx=(14, 0))
        for c, name in enumerate(MODES):
            lamp = self.lamp(box, DARK, command=lambda m=name: self.select_mode(m))
            lamp.grid(row=1, column=c, padx=(30 if c == 0 else 17, 17))
            self.text(box, name.replace(" ", "\n"), DARK).grid(row=2, column=c,
                                                                padx=(14 if c == 0 else 0, 0))
            self.mode_lamps[name] = lamp

    def build_phase(self) -> None:
        box = tk.Frame(self.section(DARK), background=DARK, pady=1)
        box.pack(fill=tk.X)
        Bracket(box, width=PHASES * PITCH + 20, text="PHASE", background=DARK).grid(
            row=0, column=0, columnspan=PHASES, sticky=tk.W, padx=(14, 0))
        for c in range(PHASES):
            lamp = self.lamp(box, DARK, command=lambda b=c: self.flip_phase(b))
            lamp.grid(row=1, column=c, padx=(20 if c == 0 else 4, 4), pady=(0, 4))
            self.phase_lamps.append(lamp)
        CapButton(box, size=LAMP, background=DARK, command=self.clear_phase).grid(
            row=1, column=PHASES, padx=(6, 0), pady=(0, 4))

    # (kind, label above, label below); kinds: switch (two-position), switch3m
    # (momentary down, rest in the middle), knob. Not functional yet.
    SWITCH_ROWS = (
        (("switch3m", "I/O\nCLEAR", "CLEAR"), ("switch", "", "PHASE\nREPEAT"),
         ("switch", "SEQ\nSTOP", ""), ("switch3m", "RESTART", "STEP")),
        (("switch", "", "FUNCTION\nREPEAT"), ("switch", "", "AUTO\nRECOVERY"),
         ("switch3m", "", "ADV P"), ("knob", "", "SPEED")),
    )

    def build_switches(self) -> None:
        """Each switch row is three grid rows (label above, switch, label below); empty
        labels are not created, so a row with no labels above takes no space."""
        area = tk.Frame(self.section(LIGHT, pady=0), background=LIGHT, pady=3)
        area.pack()
        for r, row in enumerate(self.SWITCH_ROWS):
            for c, (kind, above, below) in enumerate(row):
                if above:
                    self.text(area, above, LIGHT).grid(row=3 * r, column=c, sticky=tk.S)
                if kind == "switch":
                    widget: tk.Widget = PanelToggle(area, background=LIGHT,
                                                    show_text=False, plate="#cfcfcf")
                elif kind == "switch3m":
                    widget = PanelThreeWay(area, background=LIGHT, plate="#cfcfcf",
                                           latching=False)
                else:
                    widget = Knob(area, size=46, value=self.cpu.clock_speed,
                                  command=self.set_speed, background=LIGHT)
                widget.grid(row=3 * r + 1, column=c, padx=12)
                if below:
                    self.text(area, below, LIGHT).grid(row=3 * r + 2, column=c, sticky=tk.N)
                self.switches[(above or below).replace("\n", " ")] = widget

    # ------------------------------------------------------------ actions

    def flip(self, name: str, bit: int) -> None:
        self.cpu.flip_bit(name, bit)
        self.changed()

    def clear(self, name: str) -> None:
        self.cpu.clear(name)
        self.changed()

    def flip_function(self, bit: int) -> None:
        self.cpu.function_code ^= 1 << bit
        self.changed()

    def flip_format2(self) -> None:
        self.cpu.format2 = not self.cpu.format2
        self.changed()

    def clear_function(self) -> None:
        self.cpu.function_code = 0
        self.cpu.format2 = False
        self.changed()

    def select_mode(self, mode: str) -> None:
        self.cpu.mode = mode
        self.changed()

    def flip_phase(self, bit: int) -> None:
        self.cpu.phase ^= 1 << bit
        self.changed()

    def clear_phase(self) -> None:
        self.cpu.phase = 0
        self.changed()

    def set_speed(self, percent: int) -> None:
        self.cpu.clock_speed = percent

    # ------------------------------------------------------------ display

    def refresh(self) -> None:
        cpu = self.cpu
        for name, lamps in self.reg_lamps.items():
            value = cpu.get(name)
            for bit, lamp in enumerate(lamps):
                lamp.set(bool(value >> bit & 1))
        for bit, lamp in enumerate(self.function_lamps):
            lamp.set(bool(cpu.function_code >> bit & 1))
        self.format2_lamp.set(cpu.format2)
        for name, lamp in self.sequence_lamps.items():
            lamp.set(name == cpu.sequence)
        for name, lamp in self.mode_lamps.items():
            lamp.set(name == cpu.mode)
        for bit, lamp in enumerate(self.phase_lamps):
            lamp.set(bool(cpu.phase >> bit & 1))


PANELS: dict[str, type[FrontPanel]] = {"cpu": CpuDrawerPanel}


def main(cpu: CPU | None = None) -> None:
    cpu = cpu or CPU()
    root = tk.Tk()
    root.withdraw()
    panel = CpuDrawerPanel(root, lambda: cpu)
    panel.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
