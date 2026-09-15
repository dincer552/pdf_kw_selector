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
        colors = {
            "surface": "#0d1117",
            "panel": "#161b22",
            "panel_alt": "#21262d",
            "border": "#30363d",
            "text": "#e6edf3",
            "muted": "#8b949e",
            "accent": "#2f81f7",
            "accent_hover": "#58a6ff",
            "selection": "#1f6feb",
        }
        style = ttk.Style(app)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=colors["surface"])
        style.configure("TLabelframe", background=colors["panel"], bordercolor=colors["border"], borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=colors["panel"], foreground=colors["accent_hover"], font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background=colors["surface"], foreground=colors["text"], font=("Segoe UI", 9))
        style.configure("Muted.TLabel", background=colors["surface"], foreground=colors["muted"], font=("Segoe UI", 9))
        style.configure("TNotebook", background=colors["surface"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("TNotebook.Tab", background=colors["panel"], foreground=colors["muted"], padding=(16, 9), font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", colors["panel_alt"]), ("active", colors["border"])], foreground=[("selected", colors["text"]), ("active", colors["text"])])
        style.configure("TButton", background=colors["panel_alt"], foreground=colors["text"], padding=(11, 7), font=("Segoe UI", 9, "bold"), bordercolor=colors["border"], borderwidth=1, relief="solid")
        style.map("TButton", background=[("active", colors["border"]), ("pressed", colors["accent"]), ("disabled", colors["panel"])], foreground=[("disabled", colors["muted"])])
        style.configure("Accent.TButton", background=colors["accent"], foreground="#ffffff", padding=(16, 8), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Accent.TButton", background=[("active", colors["accent_hover"]), ("pressed", "#1f6feb"), ("disabled", colors["panel"])])
        style.configure("Treeview", background=colors["panel"], fieldbackground=colors["panel"], foreground=colors["text"], rowheight=30, font=("Segoe UI", 9), bordercolor=colors["border"], lightcolor=colors["border"], darkcolor=colors["border"])
        style.configure("Treeview.Heading", background=colors["panel_alt"], foreground=colors["muted"], font=("Segoe UI", 9, "bold"), padding=8, relief="flat")
        style.map("Treeview", background=[("selected", colors["selection"])], foreground=[("selected", "#ffffff")])
        style.configure("Horizontal.TProgressbar", troughcolor=colors["panel_alt"], background=colors["accent"], lightcolor=colors["accent"], darkcolor=colors["accent"], bordercolor=colors["border"])
        style.configure("Update.Horizontal.TProgressbar", troughcolor=colors["panel_alt"], background="#3fb950", lightcolor="#3fb950", darkcolor="#238636", bordercolor=colors["border"])

        app.configure(background=colors["surface"])
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

        for widget in _walk(app):
            if isinstance(widget, tk.Text):
                widget.configure(
                    background=colors["panel"],
                    foreground=colors["text"],
                    insertbackground=colors["text"],
                    selectbackground=colors["selection"],
                    selectforeground="#ffffff",
                    highlightthickness=1,
                    highlightbackground=colors["border"],
                    highlightcolor=colors["accent"],
                    relief="flat",
                    padx=8,
                    pady=8,
                )
            if isinstance(widget, ttk.Button) and widget.cget("text") in ("ANALİZ", "ANALİZ BAŞLA"):
                widget.configure(style="Accent.TButton")
    except Exception:
        # Visual polish must never prevent the application from starting.
        pass


def _tk_init(self, *args, **kwargs):
    _ORIGINAL_TK_INIT(self, *args, **kwargs)
    self.after_idle(lambda: _polish(self))


tk.Tk.__init__ = _tk_init
