"""Drawn console widgets shared by the CPU window and the front panels."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk


def default_background(widget: tk.Misc) -> str:
    try:
        return widget.cget("background")
    except tk.TclError:
        return ttk.Style(widget).lookup("TLabelframe", "background") or "#f0f0f0"


class ToggleSwitch(tk.Canvas):
    """A bat-handle toggle switch: lever down = OFF (default), click to flip."""

    WIDTH, HEIGHT = 40, 58

    def __init__(self, parent: tk.Misc, command: Callable[[bool], None] | None = None,
                 background: str | None = None, show_text: bool = True,
                 plate: str = "#2b2b2b") -> None:
        super().__init__(parent, width=self.WIDTH, height=self.HEIGHT,
                         highlightthickness=0, cursor="hand2",
                         background=background or default_background(parent))
        self.on = False
        self._command = command
        self._show_text = show_text
        self._plate = plate
        self.bind("<Button-1>", self._click)
        self._draw()

    def _click(self, _event=None) -> None:
        self.set(not self.on)
        if self._command:
            self._command(self.on)

    def set(self, on: bool) -> None:
        self.on = on
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        cx, cy = self.WIDTH // 2, 26
        self.create_rectangle(cx - 12, cy - 18, cx + 12, cy + 18, fill=self._plate,
                              outline="#111111", width=2)
        self.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill="#9a9a9a", outline="#555555")
        tip_y = cy - 16 if self.on else cy + 16
        self.create_line(cx, cy, cx, tip_y, width=5, fill="#d8d8d8", capstyle=tk.ROUND)
        self.create_oval(cx - 4, tip_y - 4, cx + 4, tip_y + 4, fill="#f2f2f2", outline="#777777")
        if self._show_text:
            self.create_text(cx, self.HEIGHT - 5, text="ON" if self.on else "OFF",
                             font=("TkDefaultFont", 7, "bold"),
                             fill="#0a7a0a" if self.on else "#555555")


LED_COLORS = {          # (lit, unlit)
    "red": ("#ff2020", "#4a1414"),
    "green": ("#30e040", "#123a16"),
    "white": ("#fffbe6", "#8c8c8c"),
    "amber": ("#ffb020", "#4a3210"),
}


class Led(tk.Canvas):
    """An indicator lamp (no button).

    ``set(lit)`` shows the real state; ``set_test(True)`` (lamp test) lights it
    regardless, without changing the real state.
    """

    SIZE = 20

    def __init__(self, parent: tk.Misc, color: str = "red", size: int | None = None,
                 background: str | None = None) -> None:
        self.size = size or self.SIZE
        super().__init__(parent, width=self.size, height=self.size, highlightthickness=0,
                         background=background or default_background(parent))
        self.lit_color, self.dark_color = LED_COLORS[color]
        self.lit = False
        self.test = False
        self._shown: bool | None = None
        self._draw()

    def set(self, lit: bool) -> None:
        self.lit = lit
        self._draw()

    def set_test(self, on: bool) -> None:
        self.test = on
        self._draw()

    def _draw(self) -> None:
        shown = self.lit or self.test
        if shown == self._shown:
            return
        self._shown = shown
        self.delete("all")
        s = self.size
        self.create_oval(2, 2, s - 2, s - 2, fill=self.lit_color if shown else self.dark_color,
                         outline="#220000", width=2)
        if shown:
            self.create_oval(s * 0.3, s * 0.25, s * 0.5, s * 0.45, fill="#ffffff", outline="")


# Lamp-button lens colours: lit (glow, lens) and unlit lens.
LENS_COLORS = {
    "amber": ("#ff9a00", "#ffbe3c", "#e9e9e6"),
    "white": ("#fffdf0", "#ffffff", "#e9e9e6"),
}


class LampButton(tk.Canvas):
    """An illuminated push-button: chrome bezel, lens lit (amber) when its bit is set.

    command      called on click (release); without it the button is a dummy
    on_press / on_release   momentary actions (e.g. IND TEST)
    set_test()   lamp test: show lit without changing the real state
    """

    SIZE = 30

    def __init__(self, parent: tk.Misc, command: Callable[[], None] | None = None,
                 size: int | None = None, background: str = "#111111", lens: str = "amber",
                 on_press: Callable[[], None] | None = None,
                 on_release: Callable[[], None] | None = None) -> None:
        self.size = size or self.SIZE
        live = command or on_press or on_release
        super().__init__(parent, width=self.size, height=self.size, highlightthickness=0,
                         background=background, cursor="hand2" if live else "arrow")
        self.command = command
        self.on_press = on_press
        self.on_release = on_release
        self.glow, self.lens_lit, self.lens_dark = LENS_COLORS[lens]
        self.lit = False
        self.test = False
        self._pressed = False
        self._shown: tuple[bool, bool] | None = None
        if live:
            self.bind("<ButtonPress-1>", self._press)
            self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _press(self, _event=None) -> None:
        self._pressed = True
        self._draw()
        if self.on_press:
            self.on_press()

    def _release(self, _event=None) -> None:
        self._pressed = False
        self._draw()
        if self.on_release:
            self.on_release()
        if self.command:
            self.command()

    def set(self, lit: bool) -> None:
        self.lit = lit
        self._draw()

    def set_test(self, on: bool) -> None:
        self.test = on
        self._draw()

    def _draw(self) -> None:
        shown = self.lit or self.test
        if (shown, self._pressed) == self._shown:
            return
        self._shown = (shown, self._pressed)
        self.delete("all")
        s = self.size
        inset = 3 if self._pressed else 2
        self.create_oval(1, 1, s - 1, s - 1, fill="#6e6e6e", outline="#2a2a2a")     # bezel
        self.create_oval(inset + 2, inset + 2, s - inset - 2, s - inset - 2,
                         fill="#cfcfcf", outline="#8a8a8a")                          # chrome
        if shown:
            self.create_oval(5, 5, s - 5, s - 5, fill=self.glow, outline="")        # glow
        self.create_oval(inset + 6, inset + 6, s - inset - 6, s - inset - 6,
                         fill=self.lens_lit if shown else self.lens_dark, outline="#b5b5b0")
        self.create_arc(inset + 7, inset + 7, s - inset - 9, s - inset - 9, start=100,
                        extent=80, style=tk.ARC, outline="#ffffff", width=2)


class Jack(tk.Canvas):
    """A blank panel hole / unused jack."""

    def __init__(self, parent: tk.Misc, size: int = 22, background: str = "#111111") -> None:
        super().__init__(parent, width=size, height=size, highlightthickness=0,
                         background=background)
        self.create_oval(3, 3, size - 3, size - 3, fill="#000000", outline="#3a3a3a", width=2)


class Knob(tk.Canvas):
    """A speed-control knob: knurled creamy-white rim, dark face, white pointer.

    The value is a percentage, 0-100 in steps of 10. Clicking the top half of the
    knob raises it 10 %, the bottom half lowers it 10 %; 0 % means stopped. The
    pointer sweeps 300 degrees through 12:00, from 7:00 (100 %, MAX) to 5:00 (0 %, MIN).
    """

    MAX_CLOCK, SWEEP = 210.0, 300.0     # 7:00, measured clockwise from 12:00
    STEP = 10

    def __init__(self, parent: tk.Misc, size: int = 66, value: int = 50,
                 command: Callable[[int], None] | None = None,
                 background: str = "#111111") -> None:
        super().__init__(parent, width=size, height=size, highlightthickness=0,
                         cursor="hand2", background=background)
        self.size = size
        self.value = value
        self.command = command
        self.bind("<Button-1>", self._click)
        self._draw()

    def angle(self) -> float:
        """Pointer position in clock degrees (clockwise from 12:00)."""
        return (self.MAX_CLOCK + (1 - self.value / 100) * self.SWEEP) % 360

    def set(self, value: int) -> None:
        self.value = max(0, min(100, int(value)))
        self._draw()
        if self.command:
            self.command(self.value)

    def step(self, up: bool) -> None:
        self.set(self.value + (self.STEP if up else -self.STEP))

    def _click(self, event: tk.Event) -> None:
        self.step(up=event.y < self.size / 2)

    def _point(self, clock_deg: float, radius: float) -> tuple[float, float]:
        import math
        c = self.size / 2
        a = math.radians(clock_deg)
        return c + radius * math.sin(a), c - radius * math.cos(a)

    def _draw(self) -> None:
        self.delete("all")
        c = self.size / 2
        rim = c - 2                       # outer radius
        face = rim * 0.80                 # dark face radius
        self.create_oval(c - rim, c - rim, c + rim, c + rim, fill="#f1e7cc",
                         outline="#cbbf9e", width=1)
        for tooth in range(72):           # knurling: fine radial grooves on the rim
            angle = tooth * 5
            self.create_line(*self._point(angle, face + 1), *self._point(angle, rim - 1),
                             fill="#b3a582", width=1)
        self.create_oval(c - face, c - face, c + face, c + face, fill="#1d1d1d",
                         outline="#f1e7cc", width=2)
        self.create_oval(c - face * 0.9, c - face * 0.9, c + face * 0.9, c + face * 0.9,
                         outline="#2c2c2c", width=1)
        angle = self.angle()
        self.create_line(*self._point(angle, rim * 0.25), *self._point(angle, rim),
                         fill="#ffffff", width=3, capstyle=tk.ROUND)


class ThreeWaySwitch(tk.Canvas):
    """A three-position bat-handle toggle: UP (latching), CENTER (rest), DOWN (momentary).

    Click the top half: latch UP, or from UP go back to CENTER. Click the bottom
    half: the lever snaps DOWN, on_momentary() fires, and it springs back to
    CENTER by itself (from UP too: pushing it down releases the latch). In
    CENTER the lever points straight out at the viewer, drawn as a short arm to
    the left so it reads differently from UP and DOWN.
    """

    WIDTH, HEIGHT = ToggleSwitch.WIDTH, ToggleSwitch.HEIGHT
    UP, CENTER, DOWN = "up", "center", "down"
    SPRING_MS = 250             # how long the momentary DOWN is shown

    def __init__(self, parent: tk.Misc, background: str | None = None,
                 plate: str = "#2b2b2b",
                 on_momentary: Callable[[], None] | None = None,
                 on_latch: Callable[[bool], None] | None = None,
                 latching: bool = True) -> None:
        super().__init__(parent, width=self.WIDTH, height=self.HEIGHT,
                         highlightthickness=0, cursor="hand2",
                         background=background or default_background(parent))
        self.position = self.CENTER
        self.on_momentary = on_momentary
        self.on_latch = on_latch
        self.latching = latching      # False: momentary-down only, the top does nothing
        self._plate = plate
        self._spring_job: str | None = None
        self.bind("<Button-1>", self._click)
        self._draw()

    def _click(self, event: tk.Event) -> None:
        if event.y < 26:
            self.push_up()
        else:
            self.push_down()

    def push_up(self) -> None:
        """Top half: latch UP, or release an UP latch back to CENTER."""
        if self.position == self.DOWN or not self.latching:
            return
        latched = self.position != self.UP
        self.position = self.UP if latched else self.CENTER
        self._draw()
        if self.on_latch:
            self.on_latch(latched)

    def push_down(self) -> None:
        """Bottom half: momentary DOWN, fire, then spring back to CENTER."""
        if self.position == self.DOWN:
            return
        if self.position == self.UP and self.on_latch:
            self.on_latch(False)
        self.position = self.DOWN
        self._draw()
        self.update_idletasks()            # show the lever down while the action runs
        if self.on_momentary:
            self.on_momentary()
        self._spring_job = self.after(self.SPRING_MS, self._spring_back)

    def _spring_back(self) -> None:
        self._spring_job = None
        self.position = self.CENTER
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        cx, cy = self.WIDTH // 2, 26
        self.create_rectangle(cx - 12, cy - 18, cx + 12, cy + 18, fill=self._plate,
                              outline="#111111", width=2)
        self.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill="#9a9a9a", outline="#555555")
        tip_x, tip_y = {self.UP: (cx, cy - 16), self.DOWN: (cx, cy + 16),
                        self.CENTER: (cx - 9, cy)}[self.position]
        self.create_line(cx, cy, tip_x, tip_y, width=5, fill="#d8d8d8", capstyle=tk.ROUND)
        self.create_oval(tip_x - 4, tip_y - 4, tip_x + 4, tip_y + 4, fill="#f2f2f2",
                         outline="#777777")


class DomeLamp(tk.Canvas):
    """A 1218-style indicator: an amber glass dome, dark brown when off.

    With ``command`` it is also a push-button (the 1218 panel allows manual
    alteration of every register by pressing its bit lamps).
    """

    LIT = ("#ffb22e", "#ffe2a0")       # body, highlight
    DARK = ("#6b3a12", "#a8662e")

    def __init__(self, parent: tk.Misc, size: int = 22, background: str = "#3e4452",
                 command: Callable[[], None] | None = None) -> None:
        super().__init__(parent, width=size, height=size, highlightthickness=0,
                         background=background, cursor="hand2" if command else "arrow")
        self.size = size
        self.command = command
        self.lit = False
        self.test = False
        self._shown: bool | None = None
        if command:
            self.bind("<Button-1>", lambda _e: command())
        self._draw()

    def set(self, lit: bool) -> None:
        self.lit = lit
        self._draw()

    def set_test(self, on: bool) -> None:
        self.test = on
        self._draw()

    def _draw(self) -> None:
        shown = self.lit or self.test
        if shown == self._shown:
            return
        self._shown = shown
        self.delete("all")
        s = self.size
        body, shine = self.LIT if shown else self.DARK
        self.create_oval(1, 1, s - 1, s - 1, fill="#111111", outline="#000000")      # bezel
        self.create_oval(3, 3, s - 3, s - 3, fill=body, outline="")                  # dome
        self.create_oval(s * 0.30, s * 0.22, s * 0.52, s * 0.42, fill=shine, outline="")


class CapButton(tk.Canvas):
    """A momentary push-button with a round cream-white cap (register CLEAR etc.)."""

    def __init__(self, parent: tk.Misc, size: int = 22, background: str = "#3e4452",
                 command: Callable[[], None] | None = None) -> None:
        super().__init__(parent, width=size, height=size, highlightthickness=0,
                         background=background, cursor="hand2" if command else "arrow")
        self.size = size
        self.command = command
        self._pressed = False
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _press(self, _event=None) -> None:
        self._pressed = True
        self._draw()

    def _release(self, _event=None) -> None:
        self._pressed = False
        self._draw()
        if self.command:
            self.command()

    def _draw(self) -> None:
        self.delete("all")
        s = self.size
        inset = 4 if self._pressed else 3
        self.create_oval(1, 1, s - 1, s - 1, fill="#111111", outline="#000000")
        self.create_oval(inset, inset, s - inset, s - inset,
                         fill="#e9dfb8" if self._pressed else "#fbf3d0", outline="#c9bf98")


class Bracket(tk.Canvas):
    """A panel legend drawn as a bracket: |‾‾‾‾ TEXT ‾‾‾‾| spanning a group of controls."""

    def __init__(self, parent: tk.Misc, width: int, text: str = "", background: str = "#3e4452",
                 ink: str = "#f2f2f2", height: int = 16, font=("Arial", 8, "bold")) -> None:
        super().__init__(parent, width=width, height=height, highlightthickness=0,
                         background=background)
        y = height // 2 + 1
        left, right = 3, width - 3
        if text:
            label = self.create_text(width / 2, y, text=text, fill=ink, font=font)
            x0, _, x1, _ = self.bbox(label)
            self.create_line(left, y, x0 - 4, y, fill=ink)
            self.create_line(x1 + 4, y, right, y, fill=ink)
        else:
            self.create_line(left, y, right, y, fill=ink)
        self.create_line(left, y, left, height, fill=ink)
        self.create_line(right, y, right, height, fill=ink)
