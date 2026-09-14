"""Visual polish for the desktop GUI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

_ORIGINAL_TK_INIT = tk.Tk.__init__


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


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
        style.configure("Horizontal.TProgressbar", troughcolor="#d7eaf3", background="#39a7d8")

        app.configure(background="#eef7fc")

        # Give the top/header and PDF selection boxes a cleaner card-like look.
        children = app.winfo_children()
        if children:
            children[0].configure(style="TFrame")

        # Move the technical JSON/detail area into the error/log tab.
        detail_frame = getattr(app, "detail", None)
        log_tab = None
        for child in app.tabs.winfo_children():
            if child is not app.tree.master and child is not app.unmatched_tree.master:
                log_tab = child
                break
        if detail_frame is not None and log_tab is not None:
            detail_frame = detail_frame.master
            log_text = getattr(app, "log_text", None)
            log_buttons = None
            if log_text is not None:
                log_buttons = log_text.master
                log_text.pack_forget()
                log_buttons.pack_forget()
            detail_frame.pack_forget()
            detail_frame.configure(text="JSON / TEKNİK DETAY")
            detail_frame.pack(in_=log_tab, fill="both", expand=False, padx=8, pady=(6, 4), before=log_text if log_text else None)
            if log_text is not None:
                log_text.pack(in_=log_tab, fill="both", expand=True, padx=8, pady=4)
            if log_buttons is not None:
                log_buttons.pack(in_=log_tab, fill="x", padx=3, pady=(2, 5))

            # Replace the old bottom JSON button with one in the log tab.
            for widget in list(_walk(app)):
                if isinstance(widget, ttk.Button) and widget.cget("text") == "JSON KAYDET":
                    widget.destroy()
            ttk.Button(log_buttons, text="JSON KAYDET", command=app.save_json).pack(side="left", padx=3)

        # Make the main action visually prominent.
        for widget in _walk(app):
            if isinstance(widget, ttk.Button) and widget.cget("text") == "ANALİZ":
                widget.configure(style="Accent.TButton")
        style.configure("Accent.TButton", background="#62b8df", foreground="#ffffff", padding=(16, 7), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#3da2d2"), ("pressed", "#258dbd")])
    except Exception:
        # UI polish must never prevent the application from starting.
        pass


def _tk_init(self, *args, **kwargs):
    _ORIGINAL_TK_INIT(self, *args, **kwargs)
    self.after_idle(lambda: _polish(self))


tk.Tk.__init__ = _tk_init
