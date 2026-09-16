"""Single source of truth for result status display in the Windows desktop app.

The analysis engine owns the status value. This module owns only its presentation:
exactly ``MATCH`` is green; every other non-empty status is red.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

_ORIGINAL_TREEVIEW_INIT = ttk.Treeview.__init__


def normalize_status(value: object) -> str:
    return " ".join(str(value or "").split())


def is_match_status(value: object) -> bool:
    return normalize_status(value).casefold() == "match"


def status_badge_text(value: object) -> tuple[str | None, bool]:
    status = normalize_status(value)
    if not status:
        return None, False
    matched = is_match_status(status)
    return (("✓ MATCH" if matched else f"✕ {status}"), matched)


class _StatusOverlay:
    def __init__(self, tree: ttk.Treeview) -> None:
        self.tree = tree
        self.labels: dict[tuple[str, str], tk.Label] = {}
        self.job: str | None = None
        tree.after_idle(self.refresh)
        tree.bind("<Configure>", self._schedule, add="+")
        tree.bind("<Expose>", self._schedule, add="+")
        tree.bind("<MouseWheel>", self._schedule, add="+")
        tree.bind("<Button-4>", self._schedule, add="+")
        tree.bind("<Button-5>", self._schedule, add="+")
        tree.bind("<Destroy>", self._destroy, add="+")

    def _status_columns(self) -> list[str]:
        result: list[str] = []
        for col in self.tree["columns"]:
            heading = str(self.tree.heading(col, "text") or "").strip().casefold()
            if heading in {"durum", "status", "sonuç", "result"}:
                result.append(col)
        return result

    def _schedule(self, _event=None) -> None:
        if self.job is not None:
            return
        try:
            self.job = self.tree.after_idle(self.refresh)
        except tk.TclError:
            self.job = None

    def refresh(self) -> None:
        self.job = None
        try:
            if not self.tree.winfo_exists():
                return
            columns = self._status_columns()
            wanted: dict[tuple[str, str], tuple[int, int, int, int, str, bool]] = {}
            all_items = self.tree.get_children("")
            for item in all_items:
                for col in columns:
                    bbox = self.tree.bbox(item, col)
                    if not bbox or bbox[2] <= 0 or bbox[3] <= 0:
                        continue
                    values = self.tree.item(item, "values")
                    try:
                        index = list(self.tree["columns"]).index(col)
                    except ValueError:
                        continue
                    value = values[index] if index < len(values) else ""
                    text, matched = status_badge_text(value)
                    if text:
                        wanted[(item, col)] = (*bbox, text, matched)

            for key, label in list(self.labels.items()):
                if key not in wanted or not label.winfo_exists():
                    try:
                        label.destroy()
                    except tk.TclError:
                        pass
                    self.labels.pop(key, None)

            for key, (x, y, width, height, text, matched) in wanted.items():
                label = self.labels.get(key)
                bg = "#dcfce7" if matched else "#fee2e2"
                fg = "#166534" if matched else "#991b1b"
                border = "#22c55e" if matched else "#ef4444"
                if label is None or not label.winfo_exists():
                    label = tk.Label(
                        self.tree,
                        text=text,
                        font=("Segoe UI", 8, "bold"),
                        bg=bg,
                        fg=fg,
                        bd=0,
                        relief="flat",
                        highlightthickness=1,
                        highlightbackground=border,
                        highlightcolor=border,
                        padx=8,
                        pady=1,
                        anchor="center",
                    )
                    self.labels[key] = label
                else:
                    label.configure(text=text, bg=bg, fg=fg, highlightbackground=border, highlightcolor=border)
                label.place(x=x + 4, y=y + 2, width=max(58, width - 8), height=max(18, height - 4))
                label.lift()

            self.job = self.tree.after(120, self.refresh)
        except (tk.TclError, ValueError, IndexError):
            self.job = None

    def _destroy(self, _event=None) -> None:
        if self.job is not None:
            try:
                self.tree.after_cancel(self.job)
            except Exception:
                pass
            self.job = None
        for label in list(self.labels.values()):
            try:
                label.destroy()
            except Exception:
                pass
        self.labels.clear()


def _treeview_init(self, *args, **kwargs):
    _ORIGINAL_TREEVIEW_INIT(self, *args, **kwargs)
    self._status_overlay = _StatusOverlay(self)


# Install once, before any Treeview is created.
if not getattr(ttk.Treeview, "_pdf_kw_status_display_installed", False):
    ttk.Treeview.__init__ = _treeview_init
    ttk.Treeview._pdf_kw_status_display_installed = True
