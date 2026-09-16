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
    """Render status badges directly inside each visible Durum cell.

    This deliberately avoids a single canvas overlay for the whole column.
    Grouped Treeviews contain parent AHU rows and child motor rows; a column-wide
    overlay can stay at stale coordinates and cover unrelated MATCH text while
    scrolling. Each badge below belongs to exactly one Treeview item and is
    repositioned from that item's bbox on every refresh.
    """
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
            self.status_col = None
            self.refresh_job = None
            self.poll_job = None
            self.badges = {}
            tree.after_idle(self.install)

        def find_status_column(self):
            for column in self.tree["columns"]:
                heading = str(self.tree.heading(column, "text") or "").strip().casefold()
                if heading in {"durum", "status", "sonuç", "result"}:
                    return column
            return None

        def iter_items(self, parent=""):
            for item_id in self.tree.get_children(parent):
                yield item_id
                yield from self.iter_items(item_id)

        def row_background(self, item_id):
            try:
                for tag in self.tree.item(item_id, "tags") or ():
                    bg = str(self.tree.tag_configure(tag, "background") or "")
                    if bg:
                        return bg
            except tk.TclError:
                pass
            return "#ffffff"

        def install(self):
            try:
                if not self.tree.winfo_exists():
                    return
                self.status_col = self.find_status_column()
                if not self.status_col:
                    return
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
            for badge in list(self.badges.values()):
                try:
                    badge.destroy()
                except tk.TclError:
                    pass
            self.badges.clear()

        def schedule_refresh(self, _event=None):
            if self.refresh_job is not None:
                return
            try:
                self.refresh_job = self.tree.after_idle(self.refresh)
            except tk.TclError:
                self.refresh_job = None

        def destroy_badge(self, item_id):
            badge = self.badges.pop(item_id, None)
            if badge is not None:
                try:
                    badge.destroy()
                except tk.TclError:
                    pass

        def refresh(self):
            self.refresh_job = None
            try:
                if not self.tree.winfo_exists() or not self.status_col:
                    return

                columns = list(self.tree["columns"])
                col_index = columns.index(self.status_col)
                badge_font = tkfont.Font(family="Segoe UI", size=8, weight="bold")
                visible_ids = set()

                for item_id in self.iter_items(""):
                    bbox = self.tree.bbox(item_id, self.status_col)
                    values = self.tree.item(item_id, "values")
                    status = str(values[col_index]).strip() if col_index < len(values) else ""

                    if not bbox or bbox[2] <= 0 or bbox[3] <= 0 or not status:
                        self.destroy_badge(item_id)
                        continue

                    visible_ids.add(item_id)
                    green = is_match_status(status)
                    label = "✓ MATCH" if green else f"✕ {status}"
                    outline = "#10b981" if green else "#ef4444"
                    fill = "#dcfce7" if green else "#fee2e2"
                    foreground = "#064e3b" if green else "#7f1d1d"

                    col_width = max(1, int(self.tree.column(self.status_col, "width")))
                    max_badge_width = max(68, col_width - 10)
                    badge_w = min(max(badge_font.measure(label) + 20, 68), max_badge_width)
                    cell_h = max(18, int(bbox[3]))
                    badge_h = min(22, max(18, cell_h - 4))
                    row_bg = self.row_background(item_id)

                    badge = self.badges.get(item_id)
                    if badge is None or not badge.winfo_exists():
                        badge = tk.Canvas(
                            self.tree,
                            width=badge_w,
                            height=badge_h,
                            highlightthickness=0,
                            bd=0,
                            bg=row_bg,
                        )
                        badge.bind("<Button-1>", lambda event, iid=item_id: self.on_badge_click(event, iid))
                        self.badges[item_id] = badge

                    badge.configure(width=badge_w, height=badge_h, bg=row_bg)
                    x = bbox[0] + max(2, (bbox[2] - badge_w) / 2)
                    y = bbox[1] + max(1, (bbox[3] - badge_h) / 2)
                    badge.place(x=x, y=y, anchor="nw")
                    badge.lift()
                    badge.delete("all")

                    radius = badge_h / 2.0
                    points = [
                        1 + radius, 1, badge_w - 1 - radius, 1,
                        badge_w - 1, 1, badge_w - 1, 1 + radius,
                        badge_w - 1, badge_h - 1 - radius, badge_w - 1, badge_h - 1,
                        badge_w - 1 - radius, badge_h - 1, 1 + radius, badge_h - 1,
                        1, badge_h - 1, 1, badge_h - 1 - radius,
                        1, 1 + radius, 1, 1,
                    ]
                    badge.create_polygon(points, smooth=True, fill=fill, outline=outline, width=1.5)
                    badge.create_text(
                        badge_w / 2,
                        badge_h / 2,
                        text=label,
                        fill=foreground,
                        font=badge_font,
                        width=max(1, badge_w - 12),
                        justify="center",
                    )

                for item_id in list(self.badges):
                    if item_id not in visible_ids:
                        self.destroy_badge(item_id)
            except (tk.TclError, ValueError, IndexError):
                return

        def on_badge_click(self, _event, item_id):
            try:
                if self.tree.exists(item_id):
                    self.tree.selection_set(item_id)
                    self.tree.focus(item_id)
            except tk.TclError:
                pass

    trees = [widget for widget in walk(root) if isinstance(widget, ttk.Treeview)]
    for tree in trees:
        if getattr(tree, "_central_status_overlay", None) is None:
            tree._central_status_overlay = StatusOverlay(tree)
