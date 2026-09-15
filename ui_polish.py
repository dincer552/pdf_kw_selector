"""Visual polish and layout helpers for the desktop GUI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

_ORIGINAL_TK_INIT = tk.Tk.__init__


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _make_vertical_tab_resizer(app):
    """Put the notebook in a vertical-only splitter so the action bar stays visible."""
    tabs = getattr(app, "tabs", None)
    if tabs is None or getattr(app, "_tab_resizer", None) is not None:
        return

    update_panel = getattr(app, "update_panel", None)
    splitter = tk.PanedWindow(
        app,
        orient="vertical",
        sashwidth=8,
        sashrelief="flat",
        bd=0,
        relief="flat",
        bg="#c9e8f5",
        opaqueresize=True,
    )
    spacer = ttk.Frame(splitter, height=4)

    tabs.pack_forget()
    if update_panel is not None:
        splitter.pack(fill="both", expand=True, padx=10, pady=(8, 0), before=update_panel)
    else:
        splitter.pack(fill="both", expand=True, padx=10, pady=(8, 0))
    splitter.add(tabs, minsize=220, stretch="always")
    splitter.add(spacer, minsize=4, height=4, stretch="never")
    app._tab_resizer = splitter
    app._tab_resizer_spacer = spacer


def _polish(app):
    try:
        style = ttk.Style(app)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background="#eef7fc")
        style.configure("TLabelframe", background="#eef7fc", borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background="#dff2fb", foreground="#16445c", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#eef7fc", foreground="#17384a", font=("Segoe UI", 9))
        style.configure("TNotebook", background="#dceff8", borderwidth=0)
        style.configure("TNotebook.Tab", background="#cfeaf7", foreground="#16445c", padding=(14, 7), font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#0877a8")])
        style.configure("TButton", background="#d8eef9", foreground="#16445c", padding=(10, 6), font=("Segoe UI", 9, "bold"), borderwidth=1, relief="solid")
        style.map("TButton", background=[("active", "#bde3f4"), ("pressed", "#a9d8ec")])
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground="#183b4c", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#c9e8f5", foreground="#16445c", font=("Segoe UI", 9, "bold"), padding=7)
        style.map("Treeview", background=[("selected", "#c8eafa")], foreground=[("selected", "#10384b")])

        app.configure(background="#eef7fc")
        children = app.winfo_children()
        if children:
            children[0].configure(style="TFrame")

        # Move JSON/technical detail from SONUÇLAR to HATA / İŞLEM LOGLARI.
        detail = getattr(app, "detail", None)
        result_tab = app.tree.master
        unmatched_tab = app.unmatched_tree.master
        log_tab = next((child for child in app.tabs.winfo_children() if child not in (result_tab, unmatched_tab)), None)
        if detail is not None and log_tab is not None:
            detail_frame = detail.master
            log_text = getattr(app, "log_text", None)
            log_buttons = next((child for child in log_tab.winfo_children() if isinstance(child, ttk.Frame) and child is not log_text), None)
            if log_text is not None:
                log_text.pack_forget()
            if log_buttons is not None:
                log_buttons.pack_forget()
            detail_frame.pack_forget()
            detail_frame.configure(text="JSON / TEKNİK DETAY")
            detail_frame.pack(in_=log_tab, fill="both", expand=False, padx=8, pady=(6, 4))
            if log_text is not None:
                log_text.pack(in_=log_tab, fill="both", expand=True, padx=8, pady=4)
            if log_buttons is not None:
                log_buttons.pack(in_=log_tab, fill="x", padx=3, pady=(2, 5))
                for widget in list(log_buttons.winfo_children()):
                    if isinstance(widget, ttk.Button) and widget.cget("text") == "JSON KAYDET":
                        widget.destroy()
                ttk.Button(log_buttons, text="JSON KAYDET", command=app.save_json).pack(side="left", padx=3)

        # The notebook is the only vertically resizable area. The action bar
        # remains outside the splitter, so ANALİZ BAŞLA can never be hidden.
        _make_vertical_tab_resizer(app)

        style.configure("Accent.TButton", background="#62b8df", foreground="#ffffff", padding=(16, 7), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#3da2d2"), ("pressed", "#258dbd")])
        for widget in _walk(app):
            if isinstance(widget, ttk.Button) and widget.cget("text") == "ANALİZ":
                widget.configure(style="Accent.TButton")
    except Exception:
        # Visual/layout polish must never prevent the application from starting.
        pass


def _tk_init(self, *args, **kwargs):
    _ORIGINAL_TK_INIT(self, *args, **kwargs)
    self.after_idle(lambda: _polish(self))


tk.Tk.__init__ = _tk_init
