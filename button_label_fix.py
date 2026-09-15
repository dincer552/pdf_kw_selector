"""Small UI fixes applied before/after the desktop UI is built."""
from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk

_original_button_init = ttk.Button.__init__
_original_tk_init = tk.Tk.__init__


def _button_init(self, *args, **kwargs):
    if kwargs.get("text") == "TOPLU ANALİZ":
        kwargs["text"] = "ANALİZ"
    _original_button_init(self, *args, **kwargs)


def _walk_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk_widgets(child)


def _move_json_and_detail_to_errors(app):
    if getattr(app, "_ui_relocated", False):
        return
    tabs = getattr(app, "tabs", None)
    if tabs is None or len(tabs.tabs()) < 3:
        return

    log_tab = tabs.nametowidget(tabs.tabs()[2])
    if getattr(app, "detail", None) is not None and app.detail.master is log_tab:
        app._ui_relocated = True
        return
    widgets = list(_walk_widgets(app))

    # Hide the original JSON button and recreate it inside the HATA / İŞLEM LOGLARI tab.
    for widget in widgets:
        if isinstance(widget, ttk.Button) and widget.cget("text") == "JSON KAYDET":
            try:
                widget.pack_forget()
            except tk.TclError:
                pass
            break

    # Hide the original technical-detail box and redirect self.detail to the new one.
    old_detail_frame = None
    for widget in widgets:
        if isinstance(widget, ttk.LabelFrame) and widget.cget("text") == "Sonuç JSON / teknik detay":
            old_detail_frame = widget
            try:
                widget.pack_forget()
            except tk.TclError:
                pass
            break

    if getattr(app, "detail", None) is not None:
        detail_frame = ttk.LabelFrame(log_tab, text="Sonuç JSON / teknik detay", padding=5)
        detail_frame.pack(fill="both", expand=False, padx=5, pady=(5, 0), side="top")
        detail = tk.Text(detail_frame, height=8, wrap="none")
        detail.pack(fill="both", expand=True)
        detail.configure(state="disabled")
        app.detail = detail

    json_button_frame = ttk.Frame(log_tab, padding=(5, 5, 5, 0))
    json_button_frame.pack(fill="x", side="top")
    ttk.Button(json_button_frame, text="JSON KAYDET", command=app.save_json).pack(side="left", padx=3)

    # Keep the actual logs below the technical JSON box.
    log_text = next((w for w in widgets if w is getattr(app, "log_text", None)), None)
    if log_text is not None:
        log_text.pack_forget()
        log_text.pack(fill="both", expand=True, padx=5, pady=5, side="top")

    app._ui_relocated = True


def _tk_init(self, *args, **kwargs):
    _original_tk_init(self, *args, **kwargs)
    self.after_idle(lambda: _move_json_and_detail_to_errors(self))


ttk.Button.__init__ = _button_init
tk.Tk.__init__ = _tk_init
