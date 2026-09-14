"""Make PDF cells in analysis Treeviews open their source PDF."""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from tkinter import ttk

_PATCHED = False
_ORIGINAL_TREEVIEW_INIT = None


def _open_path(path: str) -> None:
    if not path or not os.path.isfile(path):
        return
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def _document_paths(app):
    analysis = getattr(app, "analysis", None)
    if analysis is None:
        return []
    result = []
    for side in ("pdf1_documents", "pdf2_documents"):
        for document in getattr(analysis, side, ()) or ():
            path = str(getattr(document, "path", ""))
            if path:
                result.append(path)
    return result


def _clicked_pdf_path(tree, item, column):
    tags = tree.item(item, "tags") or ()
    for tag in tags:
        if isinstance(tag, str) and tag.lower().endswith(".pdf") and os.path.isfile(tag):
            return tag

    value = str(tree.set(item, column) or "").strip()
    if not value or value == "-":
        return None
    wanted = {part.strip().casefold() for part in value.split(",") if part.strip()}
    for path in _document_paths(tree.winfo_toplevel()):
        if Path(path).name.casefold() in wanted:
            return path
    return None


def _on_tree_click(event):
    tree = event.widget
    if not isinstance(tree, ttk.Treeview):
        return
    row = tree.identify_row(event.y)
    col = tree.identify_column(event.x)
    if not row or not col.startswith("#"):
        return
    try:
        index = int(col[1:]) - 1
        columns = tree["columns"]
        if index < 0 or index >= len(columns):
            return
        column = columns[index]
        heading = str(tree.heading(column, "text") or "").casefold()
    except Exception:
        return
    pdf_columns = {"pdf", "pdf1", "pdf2", "seçim çıktısı", "elektrik p."}
    if heading not in pdf_columns:
        return
    path = _clicked_pdf_path(tree, row, column)
    if path:
        _open_path(path)


def install() -> None:
    global _PATCHED, _ORIGINAL_TREEVIEW_INIT
    if _PATCHED:
        return
    _ORIGINAL_TREEVIEW_INIT = ttk.Treeview.__init__

    def patched_init(self, *args, **kwargs):
        _ORIGINAL_TREEVIEW_INIT(self, *args, **kwargs)
        self.bind("<Button-1>", _on_tree_click, add="+")

    ttk.Treeview.__init__ = patched_init
    _PATCHED = True


install()
