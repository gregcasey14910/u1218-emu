import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def tk_root():
    """One Tk root for the whole session (creating many roots is flaky on Windows)."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    yield root
    root.destroy()
