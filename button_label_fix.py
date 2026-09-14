"""Rename the main analysis button label before the UI is built."""
from __future__ import annotations

import tkinter.ttk as ttk

_original_button_init = ttk.Button.__init__

def _button_init(self, *args, **kwargs):
    if kwargs.get("text") == "TOPLU ANALİZ":
        kwargs["text"] = "ANALİZ"
    _original_button_init(self, *args, **kwargs)

ttk.Button.__init__ = _button_init
