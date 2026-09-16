"""Single source of truth for desktop status classification and badge rendering."""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

MATCH_STATUS = "MATCH"


def normalize_status(value) -> str:
    return " ".join(str(value or "").split())


def is_match_status(value) -> bool:
    return normalize_status(value).casefold() == MATCH_STATUS.casefold()


def badge_text(value) -> str:
    status = normalize_status(value)
    if not status:
        return ""
    return "✓ MATCH" if is_match_status(status) else f"✕ {status}"


def badge_colors(value) -> tuple[str, str, str]:
    if is_match_status(value):
        return "#dcfce7", "#10b981", "#064e3b"
    return "#fee2e2", "#ef4444", "#7f1d1d"


def _rounded_box(canvas: tk.Canvas, x1, y1, x2, y2, radius, **kwargs):
    radius = max(2.0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
              x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
              x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class _StatusBadgeOverlay:
    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self.canvas = None
        self.status_col = None
        self._refresh_job = None
        self._poll_job = None
        tree.after_idle(self._install)

    def _find_status_column(self):
        for column in self.tree["columns"]:
            if str(self.tree.heading(column, "text") or "").strip().casefold() == "durum":
                return column
        return None

    def _install(self):
        try:
            if not self.tree.winfo_exists():
                return
            self.status_col = self._find_status_column()
            if not self.status_col:
                return
            self.canvas = tk.Canvas(self.tree.master, highlightthickness=0, bd=0, bg="#ffffff")
            self.canvas.place_forget()
            self.canvas.bind("<Button-1>", self._on_canvas_click)
            for sequence in ("<Configure>", "<Expose>", "<Visibility>", "<<TreeviewSelect>>", "<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.tree.bind(sequence, self._schedule_refresh, add="+")
            self.tree.bind("<Destroy>", self._on_destroy, add="+")
            self._schedule_refresh()
            self._poll()
        except tk.TclError:
            return

    def _poll(self):
        try:
            if not self.tree.winfo_exists():
                return
            self._schedule_refresh()
            self._poll_job = self.tree.after(150, self._poll)
        except tk.TclError:
            self._poll_job = None

    def _on_destroy(self, _event=None):
        for job in (self._refresh_job, self._poll_job):
            if job is not None:
                try:
                    self.tree.after_cancel(job)
                except Exception:
                    pass
        self._refresh_job = self._poll_job = None
        if self.canvas is not None:
            try:
                self.canvas.destroy()
            except Exception:
                pass

    def _schedule_refresh(self, _event=None):
        if self._refresh_job is not None:
            return
        try:
            self._refresh_job = self.tree.after_idle(self._refresh)
        except tk.TclError:
            self._refresh_job = None

    def _refresh(self):
        self._refresh_job = None
        try:
            if not self.tree.winfo_exists() or self.canvas is None or not self.status_col:
                return
            visible = []
            for item_id in self.tree.get_children(""):
                bbox = self.tree.bbox(item_id, self.status_col)
                if bbox and bbox[2] > 0 and bbox[3] > 0:
                    visible.append((item_id, bbox))
            if not visible:
                self.canvas.place_forget()
                return
            first_bbox = visible[0][1]
            col_x = first_bbox[0]
            col_width = max(1, int(self.tree.column(self.status_col, "width")))
            body_top = first_bbox[1]
            height = max(1, self.tree.winfo_height() - body_top)
            self.canvas.configure(width=col_width, height=height)
            self.canvas.place(x=self.tree.winfo_x() + col_x, y=self.tree.winfo_y() + body_top, anchor="nw")
            self.canvas.lift()
            self.canvas.delete("all")
            badge_font = tkfont.Font(family="Segoe UI", size=8, weight="bold")
            col_index = list(self.tree["columns"]).index(self.status_col)
            for item_id, bbox in visible:
                values = self.tree.item(item_id, "values")
                status = str(values[col_index]).strip() if col_index < len(values) else ""
                if not status:
                    continue
                _, cell_y, _, cell_h = bbox
                local_y = cell_y - body_top
                label = badge_text(status)
                fill, outline, foreground = badge_colors(status)
                badge_w = min(max(badge_font.measure(label) + 20, 68), max(68, col_width - 10))
                badge_h = min(22, max(18, cell_h - 4))
                x1 = 5
                y1 = local_y + max(2, (cell_h - badge_h) / 2)
                x2 = min(col_width - 5, x1 + badge_w)
                y2 = y1 + badge_h
                _rounded_box(self.canvas, x1, y1, x2, y2, badge_h / 2.0, fill=fill, outline=outline, width=1.5)
                self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=label, fill=foreground, font=badge_font)
        except (tk.TclError, ValueError, IndexError):
            return

    def _on_canvas_click(self, event):
        try:
            tree_y = event.y + self.tree.winfo_y()
            row_id = self.tree.identify_row(tree_y)
            if row_id:
                self.tree.selection_set(row_id)
                self.tree.focus(row_id)
        except tk.TclError:
            pass


def install_status_badges(app) -> None:
    """Attach the canonical badge overlay to every Treeview in the desktop app."""
    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)
    for widget in walk(app):
        if isinstance(widget, ttk.Treeview):
            _StatusBadgeOverlay(widget)
