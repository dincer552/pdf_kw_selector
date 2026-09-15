"""Show a crisp lime green border box over clickable PDF cells while the mouse is over them."""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk

_ORIGINAL_TREEVIEW_INIT = ttk.Treeview.__init__

_PDF_COLUMNS = {
    "pdf", "pdf1", "pdf2", "pdf dosyası", "pdf dosyasi",
    "seçim çıktısı", "secim ciktisi", "seçim ciktisi", "secim çıktısı",
    "seçim kw", "secim kw", "seçim", "secim",
    "elektrik p.", "elektrik p", "elektrik p. kw", "elektrik p kw",
}


def _is_pdf(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower().endswith(".pdf")


def _basename(value: str) -> str:
    return os.path.basename(value.replace("\\", "/")).casefold()


class CellHoverBox:
    """Draws a crisp lime green border box around a clickable PDF cell on hover without obscuring cell text."""

    def __init__(self, color: str = "#84cc16", line_width: int = 2):
        self.color = color
        self.line_width = line_width
        self.current_tree: ttk.Treeview | None = None
        self.current_cell: tuple[ttk.Treeview, str, str] | None = None
        self._lines: list[tk.Frame] = []

    def _ensure_lines(self, tree: ttk.Treeview) -> None:
        if self._lines and self.current_tree is tree:
            return
        self.hide()
        self.current_tree = tree
        self._lines = [
            tk.Frame(tree, bg=self.color, cursor="hand2"),  # top
            tk.Frame(tree, bg=self.color, cursor="hand2"),  # bottom
            tk.Frame(tree, bg=self.color, cursor="hand2"),  # left
            tk.Frame(tree, bg=self.color, cursor="hand2"),  # right
        ]
        for line in self._lines:
            line.bind("<Button-1>", self._on_border_click)
            line.bind("<Double-1>", self._on_border_double_click)

    def _on_border_click(self, event) -> None:
        if self.current_tree and self.current_tree.winfo_exists():
            x = event.x_root - self.current_tree.winfo_rootx()
            y = event.y_root - self.current_tree.winfo_rooty()
            self.current_tree.event_generate("<Button-1>", x=x, y=y)

    def _on_border_double_click(self, event) -> None:
        if self.current_tree and self.current_tree.winfo_exists():
            x = event.x_root - self.current_tree.winfo_rootx()
            y = event.y_root - self.current_tree.winfo_rooty()
            self.current_tree.event_generate("<Double-1>", x=x, y=y)

    def show(self, tree: ttk.Treeview, row_id: str, col: str) -> None:
        try:
            bbox = tree.bbox(row_id, col)
        except Exception:
            bbox = None
        if not bbox or len(bbox) != 4 or bbox[2] <= 0 or bbox[3] <= 0:
            self.hide()
            return

        if self.current_cell == (tree, row_id, col):
            return

        self.current_cell = (tree, row_id, col)
        self._ensure_lines(tree)
        x, y, w, h = bbox
        lw = self.line_width

        # Place the 4 border lines along the perimeter of the cell
        self._lines[0].place(x=x, y=y, width=w, height=lw)
        self._lines[1].place(x=x, y=y + h - lw, width=w, height=lw)
        self._lines[2].place(x=x, y=y, width=lw, height=h)
        self._lines[3].place(x=x + w - lw, y=y, width=lw, height=h)

        for line in self._lines:
            line.lift()

    def hide(self) -> None:
        self.current_cell = None
        for line in self._lines:
            try:
                line.place_forget()
            except Exception:
                pass


_shared_hover_box = CellHoverBox(color="#84cc16", line_width=2)


def get_cell_hover_box() -> CellHoverBox:
    return _shared_hover_box


def _candidate_from_cell_data(tree: ttk.Treeview, item: str, column_id: str) -> str | None:
    """Use the exact PDF path stored by the result renderer when available."""
    app = tree.winfo_toplevel()
    data_maps = (
        ("_tree_cell_data", {"#4": "pdf1_path", "#5": "pdf2_path"}),
        ("_ebm_cell_data", {"#3": "pdf1_path", "#4": "pdf2_path"}),
        ("_voclean_cell_data", {"#2": "pdf1_path", "#5": "pdf2_path"}),
        ("_sysreco_cell_data", {"#3": "pdf_path"}),
        ("_unmatched_cell_data", {"#2": "path"}),
    )
    for attr, mapping in data_maps:
        data_map = getattr(app, attr, None)
        if not isinstance(data_map, dict):
            continue
        data = data_map.get(item)
        if not isinstance(data, dict):
            continue
        key = mapping.get(column_id)
        if not key:
            continue
        path = data.get(key)
        if path:
            return str(path)

    # Also check direct item values for hidden file paths (e.g. DANFOSS table row[6]=pdf1, row[8]=pdf2)
    values = tree.item(item, "values") or ()
    if column_id == "#4" and len(values) > 6 and values[6]:
        return str(values[6])
    if column_id == "#5" and len(values) > 8 and values[8]:
        return str(values[8])

    return None


def _resolve_pdf(tree: ttk.Treeview, item: str, column_id: str) -> str | None:
    try:
        heading = str(tree.heading(column_id, "text") or "").strip().casefold()
    except tk.TclError:
        return None
    if heading not in _PDF_COLUMNS:
        return None

    # Verify that cell is not an empty or dash placeholder
    values = tree.item(item, "values") or ()
    try:
        column_index = list(tree["columns"]).index(column_id)
    except (ValueError, tk.TclError):
        column_index = -1

    if column_index >= 0 and column_index < len(values):
        val_str = str(values[column_index]).strip()
        if not val_str or val_str == "-":
            return None

    # Result renderers already know the exact source path
    exact = _candidate_from_cell_data(tree, item, column_id)
    if exact:
        return exact

    if column_index >= len(values):
        return None
    displayed = str(values[column_index]).strip()
    if _is_pdf(displayed):
        # A full PDF path may also be supplied as a Treeview tag
        for tag in tree.item(item, "tags") or ():
            if _is_pdf(tag) and os.path.isfile(os.path.expanduser(str(tag))):
                return os.path.expanduser(str(tag))

        # Fall back to the source-document lists on the application
        app = tree.winfo_toplevel()
        wanted = _basename(displayed)
        for attr in ("pdf1_documents", "pdf2_documents"):
            documents = getattr(app, attr, None)
            if documents is None:
                continue
            for doc in documents:
                path = doc.get("path") if isinstance(doc, dict) else getattr(doc, "path", None)
                if path and _basename(str(path)) == wanted and os.path.isfile(str(path)):
                    return str(path)

        analysis = getattr(app, "analysis", None)
        for attr in ("pdf1_documents", "pdf2_documents"):
            documents = getattr(analysis, attr, None) if analysis is not None else None
            for doc in documents or ():
                path = getattr(doc, "path", None)
                if path and _basename(str(path)) == wanted and os.path.isfile(str(path)):
                    return str(path)

    # For kW columns (DANFOSS #4 and #5), non-empty values are valid openable cells
    if heading in ("seçim kw", "secim kw", "elektrik p. kw", "elektrik p kw"):
        return displayed or "pdf"

    return None


def _motion(tree: ttk.Treeview, event) -> None:
    try:
        region = tree.identify_region(event.x, event.y)
        if region != "cell":
            if _shared_hover_box.current_tree is tree:
                _shared_hover_box.hide()
            tree.configure(cursor="")
            return

        item = tree.identify_row(event.y)
        column_id = tree.identify_column(event.x)
        if not item or not column_id:
            if _shared_hover_box.current_tree is tree:
                _shared_hover_box.hide()
            tree.configure(cursor="")
            return

        path = _resolve_pdf(tree, item, column_id)
        if path:
            tree.configure(cursor="hand2")
            _shared_hover_box.show(tree, item, column_id)
        else:
            if _shared_hover_box.current_tree is tree:
                _shared_hover_box.hide()
            tree.configure(cursor="")
    except Exception:
        if _shared_hover_box.current_tree is tree:
            _shared_hover_box.hide()


def _hide(tree: ttk.Treeview) -> None:
    try:
        tree.configure(cursor="")
    except Exception:
        pass
    if _shared_hover_box.current_tree is tree:
        _shared_hover_box.hide()


def _treeview_init(self, *args, **kwargs):
    _ORIGINAL_TREEVIEW_INIT(self, *args, **kwargs)
    self.bind("<Motion>", lambda event, tree=self: _motion(tree, event), add="+")
    self.bind("<Leave>", lambda _event, tree=self: _hide(tree), add="+")
    self.bind("<MouseWheel>", lambda _event, tree=self: _hide(tree), add="+")
    self.bind("<Button-4>", lambda _event, tree=self: _hide(tree), add="+")
    self.bind("<Button-5>", lambda _event, tree=self: _hide(tree), add="+")


ttk.Treeview.__init__ = _treeview_init
