"""Visual polish and layout helpers for the desktop GUI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

_ORIGINAL_TK_INIT = tk.Tk.__init__


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _find_action_bar(app):
    for child in app.winfo_children():
        if not isinstance(child, ttk.Frame):
            continue
        for nested in child.winfo_children():
            if isinstance(nested, ttk.Button) and nested.cget("text") == "▶ ANALİZ BAŞLA":
                return child
    return None


def _pin_bottom_bars(app):
    """Keep the action bar permanently at the bottom, below the resizable area."""
    buttons = getattr(app, "_fixed_action_bar", None) or _find_action_bar(app)
    update_panel = getattr(app, "update_panel", None)
    if buttons is not None:
        app._fixed_action_bar = buttons
        if buttons.winfo_manager() == "pack":
            buttons.pack_forget()
        buttons.pack(side="bottom", fill="x", padx=0, pady=0)

    # The update-progress row is optional. If it is shown later by the update
    # checker, force it to remain immediately above the fixed action bar.
    if update_panel is not None and update_panel.winfo_manager() == "pack":
        update_panel.pack_forget()
        update_panel.pack(side="bottom", fill="x", padx=0, pady=0)


def _make_vertical_tab_resizer(app):
    """Put the notebook in a vertical-only splitter; footer controls stay fixed."""
    tabs = getattr(app, "tabs", None)
    if tabs is None or getattr(app, "_tab_resizer", None) is not None:
        return

    _pin_bottom_bars(app)
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
    splitter.pack(fill="both", expand=True, padx=10, pady=(8, 0))
    splitter.add(tabs, minsize=220, stretch="always")
    splitter.add(spacer, minsize=4, height=4, stretch="never")
    app._tab_resizer = splitter
    app._tab_resizer_spacer = spacer

    # _manual_update_check() may call update_panel.pack() later. Re-assert the
    # footer order shortly afterwards so that row can never push the buttons out.
    def keep_footer():
        try:
            _pin_bottom_bars(app)
            app.after(250, keep_footer)
        except tk.TclError:
            return

    app.after(250, keep_footer)


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

        _make_vertical_tab_resizer(app)

        style.configure("Accent.TButton", background="#62b8df", foreground="#ffffff", padding=(16, 7), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#3da2d2"), ("pressed", "#258dbd")])
        for widget in _walk(app):
            if isinstance(widget, ttk.Button) and widget.cget("text") == "ANALİZ":
                widget.configure(style="Accent.TButton")
    except Exception:
        pass


def _tk_init(self, *args, **kwargs):
    _ORIGINAL_TK_INIT(self, *args, **kwargs)
    self.after_idle(lambda: _polish(self))


tk.Tk.__init__ = _tk_init
