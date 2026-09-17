"""Single source of truth for comparison statuses and desktop presentation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import tkinter as tk
from tkinter import ttk

STATUS_MATCH = "MATCH"
STATUS_MISMATCH = "MISMATCH"
STATUS_EBM_PAPST = "EBM_PAPST"
STATUS_ONLY_IN_PDF1 = "ONLY_IN_PDF1"
STATUS_ONLY_IN_PDF2 = "ONLY_IN_PDF2"
STATUS_MATCH_TAG = "status_match"
STATUS_ERROR_TAG = "status_error"

ALL_STATUSES = frozenset({STATUS_MATCH, STATUS_MISMATCH, STATUS_EBM_PAPST, STATUS_ONLY_IN_PDF1, STATUS_ONLY_IN_PDF2})

def normalize_status(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().upper()

def is_match_status(value: Any) -> bool:
    """Only the literal MATCH status counts toward the motor MATCH total."""
    return normalize_status(value) == STATUS_MATCH

def _is_ebm_papst(record: Any) -> bool:
    if record is None: return False
    brand = str(getattr(record, "model_brand", "") or "").casefold().replace(" ", "")
    return "ebm-papst" in brand or "ebmpapst" in brand

def _is_legacy_1_1_equivalent(pdf1_kw: float | None, pdf2_kw: float | None) -> bool:
    return pdf1_kw is not None and pdf2_kw is not None and abs(pdf1_kw - 1.1) <= 0.001 and abs(pdf2_kw - 1.5) <= 0.001

@dataclass(frozen=True)
class StatusDecision:
    status: str
    difference_kw: float | None
    explanation: str

def decide_motor_status(pdf1_record: Any, pdf2_record: Any, tolerance_kw: float = 0.01) -> StatusDecision:
    """Decide the motor comparison result in exactly one place."""
    if tolerance_kw < 0: raise ValueError("tolerance_kw must be >= 0")
    pdf1_kw = getattr(pdf1_record, "power_kw", None) if pdf1_record is not None else None
    pdf2_kw = getattr(pdf2_record, "power_kw", None) if pdf2_record is not None else None
    if pdf1_record is None: return StatusDecision(STATUS_ONLY_IN_PDF2, None, "PDF1 tarafında karşılığı bulunamadı.")
    if pdf2_record is None: return StatusDecision(STATUS_ONLY_IN_PDF1, None, "PDF2 tarafında karşılığı bulunamadı.")
    if _is_ebm_papst(pdf1_record):
        return StatusDecision(STATUS_EBM_PAPST, None, "PDF1 Model Brand = EBM-Papst; normal kW karşılaştırması yapılmadı. PDF2 motoru eşleştirildi.")
    difference = abs((pdf1_kw or 0.0) - (pdf2_kw or 0.0))
    if _is_legacy_1_1_equivalent(pdf1_kw, pdf2_kw):
        return StatusDecision(STATUS_MATCH, difference, "Özel eşdeğerlik: PDF1 1.1 kW, PDF2 1.5 kW kabul edildi. Bu istisna yalnızca 1.1→1.5 için geçerlidir.")
    if difference <= tolerance_kw: return StatusDecision(STATUS_MATCH, difference, "Normal kW karşılaştırması yapıldı.")
    return StatusDecision(STATUS_MISMATCH, difference, "Normal kW karşılaştırması yapıldı.")

def _is_ba_code_match_status(value: Any) -> bool:
    """BA code matches are visually successful, but are not motor MATCH totals."""
    status = normalize_status(value)
    return status.startswith("BA KODU EŞLEŞTİ")

def status_display_text(value: Any) -> str:
    """Return the compact status text shown in a status cell."""
    status = normalize_status(value)
    if not status: return ""
    if status == "✓ MATCH" or status.startswith("✓ BA KODU EŞLEŞTİ") or status.startswith("✕ "): return status
    if is_match_status(status): return "✓ MATCH"
    if _is_ba_code_match_status(status): return f"✓ {status}"
    return f"✕ {status}"

def status_tag_name(value: Any) -> str | None:
    """Return the Treeview tag for the central visual status rule."""
    status = normalize_status(value)
    if not status: return None
    if status == "✓ MATCH" or status.startswith("✓ BA KODU EŞLEŞTİ"): return STATUS_MATCH_TAG
    if status.startswith("✕ "): status = status[2:].strip()
    if is_match_status(status) or _is_ba_code_match_status(status): return STATUS_MATCH_TAG
    return STATUS_ERROR_TAG

def configure_status_tags(tree: ttk.Treeview) -> None:
    """Configure native, scroll-safe status colours on a Treeview."""
    tree.tag_configure(STATUS_MATCH_TAG, background="#dcfce7", foreground="#065f46")
    tree.tag_configure(STATUS_ERROR_TAG, background="#fee2e2", foreground="#991b1b")

def apply_status_tag(tree: ttk.Treeview, item_id: str, value: Any) -> None:
    """Append the correct native Treeview status tag without dropping others."""
    tag = status_tag_name(value)
    if not tag: return
    tags = [existing for existing in tree.item(item_id, "tags") if existing not in {STATUS_MATCH_TAG, STATUS_ERROR_TAG}]
    tree.item(item_id, tags=(*tags, tag))

def install_status_display(root: tk.Misc) -> None:
    """Configure native status styles for every existing status table."""
    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)
    for widget in walk(root):
        if not isinstance(widget, ttk.Treeview): continue
        headings = {" ".join(str(widget.heading(column, "text") or "").split()).casefold() for column in widget["columns"]}
        if headings & {"durum", "status", "sonuç", "result"}: configure_status_tags(widget)
