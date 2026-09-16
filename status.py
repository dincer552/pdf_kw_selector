"""Single source of truth for comparison statuses and their desktop presentation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    return str(value or "").strip().upper()


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
        return StatusDecision(
            STATUS_ONLY_IN_PDF2,
            None,
            "PDF1 tarafında karşılığı bulunamadı.",
        )

    if pdf2_record is None:
        return StatusDecision(
            STATUS_ONLY_IN_PDF1,
            None,
            "PDF2 tarafında karşılığı bulunamadı.",
        )

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
        return StatusDecision(
            STATUS_MATCH,
            difference,
            "Normal kW karşılaştırması yapıldı.",
        )

    return StatusDecision(
        STATUS_MISMATCH,
        difference,
        "Normal kW karşılaştırması yapıldı.",
    )


# ----------------------------- Desktop presentation -----------------------------


def install_status_display(root) -> None:
    """Install the single status renderer on every Treeview containing a Durum column."""
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    class StatusOverlay:
        def __init__(self, tree):
            self.tree = tree
            self.canvas = None
            self.status_col = None
            self.refresh_job = None
            self.poll_job = None
            tree.after_idle(self.install)

        def find_status_column(self):
            for column in self.tree["columns"]:
                heading = str(self.tree.heading(column, "text") or "").strip().casefold()
                if heading in {"durum", "status", "sonuç", "result"}:
                    return column
            return None

        def install(self):
            try:
                if not self.tree.winfo_exists():
                    return
                self.status_col = self.find_status_column()
                if not self.status_col:
                    return
                self.canvas = tk.Canvas(self.tree.master, highlightthickness=0, bd=0, bg="#ffffff")
                self.canvas.place_forget()
                for sequence in ("<Configure>", "<Expose>", "<Visibility>", "<<TreeviewSelect>>", "<MouseWheel>", "<Button-4>", "<Button-5>"):
                    self.tree.bind(sequence, self.schedule_refresh, add="+")
                self.tree.bind("<Destroy>", self.on_destroy, add="+")
                self.schedule_refresh()
                self.poll()
            except tk.TclError:
                return

        def poll(self):
            try:
                if not self.tree.winfo_exists():
                    return
                self.schedule_refresh()
                self.poll_job = self.tree.after(150, self.poll)
            except tk.TclError:
                self.poll_job = None

        def on_destroy(self, _event=None):
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

        def schedule_refresh(self, _event=None):
            if self.refresh_job is not None:
                return
            try:
                self.refresh_job = self.tree.after_idle(self.refresh)
            except tk.TclError:
                self.refresh_job = None

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
                    green = is_match_status(status)
                    label = "✓ MATCH" if green else f"✕ {status}"
                    outline = "#10b981" if green else "#ef4444"
                    fill = "#dcfce7" if green else "#fee2e2"
                    foreground = "#064e3b" if green else "#7f1d1d"
                    badge_w = min(max(badge_font.measure(label) + 20, 68), max(68, col_width - 10))
                    badge_h = min(22, max(18, cell_h - 4))
                    x1 = 5
                    y1 = local_y + max(2, (cell_h - badge_h) / 2)
                    x2 = min(col_width - 5, x1 + badge_w)
                    y2 = y1 + badge_h
                    radius = badge_h / 2.0
                    points = [
                        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
                        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
                        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
                    ]
                    self.canvas.create_polygon(points, smooth=True, fill=fill, outline=outline, width=1.5)
                    self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=label, fill=foreground, font=badge_font)
            except (tk.TclError, ValueError, IndexError):
                return

    trees = [widget for widget in walk(root) if isinstance(widget, ttk.Treeview)]
    for tree in trees:
        if getattr(tree, "_central_status_overlay", None) is None:
            tree._central_status_overlay = StatusOverlay(tree)
