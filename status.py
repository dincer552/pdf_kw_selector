"""Single source of truth for comparison statuses and desktop presentation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import tkinter as tk
from tkinter import ttk, font as tkfont

STATUS_MATCH = "MATCH"
STATUS_MISMATCH = "MISMATCH"
STATUS_EBM_PAPST = "EBM_PAPST"
STATUS_ONLY_IN_PDF1 = "ONLY_IN_PDF1"
STATUS_ONLY_IN_PDF2 = "ONLY_IN_PDF2"

ALL_STATUSES = frozenset({
    STATUS_MATCH,
    STATUS_MISMATCH,
    STATUS_EBM_PAPST,
    STATUS_ONLY_IN_PDF1,
    STATUS_ONLY_IN_PDF2,
})


def normalize_status(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().upper()


def is_match_status(value: Any) -> bool:
    """Only the literal MATCH status is a successful result."""
    return normalize_status(value) == STATUS_MATCH


def _is_ebm_papst(record: Any) -> bool:
    if record is None:
        return False
    brand = str(getattr(record, "model_brand", "") or "").casefold().replace(" ", "")
    return "ebm-papst" in brand or "ebmpapst" in brand


def _is_legacy_1_1_equivalent(pdf1_kw: float | None, pdf2_kw: float | None) -> bool:
    return (
        pdf1_kw is not None
        and pdf2_kw is not None
        and abs(pdf1_kw - 1.1) <= 0.001
        and abs(pdf2_kw - 1.5) <= 0.001
    )


@dataclass(frozen=True)
class StatusDecision:
    status: str
    difference_kw: float | None
    explanation: str


def decide_motor_status(
    pdf1_record: Any,
    pdf2_record: Any,
    tolerance_kw: float = 0.01,
) -> StatusDecision:
    """Decide the motor comparison result in exactly one place."""
    if tolerance_kw < 0:
        raise ValueError("tolerance_kw must be >= 0")

    pdf1_kw = getattr(pdf1_record, "power_kw", None) if pdf1_record is not None else None
    pdf2_kw = getattr(pdf2_record, "power_kw", None) if pdf2_record is not None else None

    if pdf1_record is None:
        return StatusDecision(STATUS_ONLY_IN_PDF2, None, "PDF1 tarafında karşılığı bulunamadı.")
    if pdf2_record is None:
        return StatusDecision(STATUS_ONLY_IN_PDF1, None, "PDF2 tarafında karşılığı bulunamadı.")
    if _is_ebm_papst(pdf1_record):
        return StatusDecision(
            STATUS_EBM_PAPST,
            None,
            "PDF1 Model Brand = EBM-Papst; normal kW karşılaştırması yapılmadı. PDF2 motoru eşleştirildi.",
        )

    difference = abs((pdf1_kw or 0.0) - (pdf2_kw or 0.0))
    if _is_legacy_1_1_equivalent(pdf1_kw, pdf2_kw):
        return StatusDecision(
            STATUS_MATCH,
            difference,
            "Özel eşdeğerlik: PDF1 1.1 kW, PDF2 1.5 kW kabul edildi. Bu istisna yalnızca 1.1→1.5 için geçerlidir.",
        )
    if difference <= tolerance_kw:
        return StatusDecision(STATUS_MATCH, difference, "Normal kW karşılaştırması yapıldı.")
    return StatusDecision(STATUS_MISMATCH, difference, "Normal kW karşılaştırması yapıldı.")


class _StatusOverlay:
    """Draw status badges above a Treeview without changing its data."""

    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self.status_col: str | None = None
        self.canvas: tk.Canvas | None = None
        self.refresh_job = None
        self.poll_job = None
        tree.after_idle(self.install)

    def install(self):
        try:
            if not self.tree.winfo_exists():
                return
            self.status_col = self._find_status_column()
            if not self.status_col:
                return

            # The overlay belongs to the Treeview's parent, not to the Treeview
            # itself. This guarantees it is above the themed Treeview renderer.
            parent = self.tree.master
            self.canvas = tk.Canvas(parent, highlightthickness=0, bd=0, bg="#ffffff")
            self.canvas.place_forget()
            self.canvas.bind("<Button-1>", self._on_click)
            for sequence in ("<Configure>", "<Expose>", "<Visibility>", "<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.tree.bind(sequence, self.schedule_refresh, add="+")
            self.tree.bind("<Destroy>", self.destroy, add="+")
            self.schedule_refresh()
            self.poll()
        except tk.TclError:
            return

    def _find_status_column(self) -> str | None:
        for column in self.tree["columns"]:
            heading = " ".join(str(self.tree.heading(column, "text") or "").split()).casefold()
            if heading in {"durum", "status", "sonuç", "result"}:
                return column
        return None

    def poll(self):
        try:
            if not self.tree.winfo_exists():
                return
            self.schedule_refresh()
            self.poll_job = self.tree.after(100, self.poll)
        except tk.TclError:
            self.poll_job = None

    def schedule_refresh(self, _event=None):
        if self.refresh_job is not None:
            return
        try:
            self.refresh_job = self.tree.after_idle(self.refresh)
        except tk.TclError:
            self.refresh_job = None

    def destroy(self, _event=None):
        for job in (self.refresh_job, self.poll_job):
            if job is not None:
                try:
                    self.tree.after_cancel(job)
                except Exception:
                    pass
        self.refresh_job = self.poll_job = None
        if self.canvas is not None:
            try:
                self.canvas.destroy()
            except tk.TclError:
                pass
        self.canvas = None

    def refresh(self):
        self.refresh_job = None
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
            column_x = int(first_bbox[0])
            column_width = max(1, int(self.tree.column(self.status_col, "width")))
            body_top = int(first_bbox[1])
            canvas_height = max(1, int(self.tree.winfo_height()) - body_top)

            self.canvas.configure(width=column_width, height=canvas_height)
            self.canvas.place(
                x=int(self.tree.winfo_x()) + column_x,
                y=int(self.tree.winfo_y()) + body_top,
                anchor="nw",
            )
            self.canvas.lift()
            self.canvas.delete("all")

            columns = list(self.tree["columns"])
            col_index = columns.index(self.status_col)
            badge_font = tkfont.Font(self.canvas, family="Segoe UI", size=8, weight="bold")

            for item_id, bbox in visible:
                values = self.tree.item(item_id, "values")
                status = str(values[col_index]).strip() if col_index < len(values) else ""
                if not status:
                    continue

                green = is_match_status(status)
                label = "✓ MATCH" if green else f"✕ {status}"
                outline = "#10b981" if green else "#ef4444"
                fill = "#dcfce7" if green else "#fee2e2"
                foreground = "#064e3b" if green else "#7f1d1d"

                _, cell_y, _, cell_h = bbox
                local_y = int(cell_y) - body_top
                badge_h = min(22, max(18, int(cell_h) - 4))
                measured = badge_font.measure(label) + 20
                badge_w = min(max(measured, 68), max(68, column_width - 10))
                x1 = max(4, int((column_width - badge_w) / 2))
                y1 = local_y + max(1, int((cell_h - badge_h) / 2))
                x2 = min(column_width - 4, x1 + badge_w)
                y2 = y1 + badge_h
                radius = badge_h / 2.0
                points = [
                    x1 + radius, y1,
                    x2 - radius, y1,
                    x2, y1,
                    x2, y1 + radius,
                    x2, y2 - radius,
                    x2, y2,
                    x2 - radius, y2,
                    x1 + radius, y2,
                    x1, y2,
                    x1, y2 - radius,
                    x1, y1 + radius,
                    x1, y1,
                ]
                self.canvas.create_polygon(points, smooth=True, fill=fill, outline=outline, width=1.5)
                self.canvas.create_text(
                    (x1 + x2) / 2,
                    (y1 + y2) / 2,
                    text=label,
                    fill=foreground,
                    font=badge_font,
                )

        except (tk.TclError, ValueError, IndexError):
            return

    def _on_click(self, event):
        try:
            tree_y = event.y + int(self.tree.winfo_y())
            item_id = self.tree.identify_row(tree_y)
            if item_id:
                self.tree.selection_set(item_id)
                self.tree.focus(item_id)
        except tk.TclError:
            pass


def install_status_display(root: tk.Misc) -> None:
    """Install the single status renderer on every Treeview with a Durum column."""
    controllers = getattr(root, "_status_overlays", None)
    if controllers is None:
        controllers = []
        root._status_overlays = controllers

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    for widget in walk(root):
        if not isinstance(widget, ttk.Treeview):
            continue
        if getattr(widget, "_central_status_overlay", None) is not None:
            continue
        controller = _StatusOverlay(widget)
        widget._central_status_overlay = controller
        controllers.append(controller)
