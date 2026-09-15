"""Show a green outline over PDF cells while the mouse is over them.

The outline is deliberately drawn in a tiny transparent Windows overlay so the
Treeview text remains visible. Only cells that resolve to a real PDF path are
highlighted; clicking the highlighted cell opens that PDF.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk

_ORIGINAL_TREEVIEW_INIT = ttk.Treeview.__init__
_PDF_COLUMNS = {
    "pdf", "pdf1", "pdf2", "seçim çıktısı", "secim cikti", "secim çıktısı",
    "elektrik p.", "elektrik p",
}


def _is_pdf(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower().endswith(".pdf")


def _basename(value: str) -> str:
    return os.path.basename(value.replace("\\", "/")).casefold()


def _walk_pdf_paths(value: object, seen: set[int] | None = None):
    if seen is None:
        seen = set()
    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        if _is_pdf(value):
            yield value
        return
    marker = id(value)
    if marker in seen:
        return
    seen.add(marker)
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_pdf_paths(item, seen)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _walk_pdf_paths(item, seen)


def _resolve_pdf(tree: ttk.Treeview, item: str, column_id: str) -> str | None:
    try:
        heading = str(tree.heading(column_id, "text") or "").strip().casefold()
    except tk.TclError:
        return None
    if heading not in _PDF_COLUMNS:
        return None
    values = tree.item(item, "values") or ()
    try:
        index = list(tree["columns"]).index(column_id)
    except (ValueError, tk.TclError):
        return None
    if index >= len(values):
        return None
    displayed = str(values[index]).strip()
    if not _is_pdf(displayed):
        return None

    for tag in tree.item(item, "tags") or ():
        if _is_pdf(tag):
            candidate = os.path.expanduser(str(tag))
            if os.path.isfile(candidate):
                return candidate

    app = tree.winfo_toplevel()
    analysis = getattr(app, "analysis", None)
    if analysis is not None:
        wanted = _basename(displayed)
        for candidate in _walk_pdf_paths(analysis):
            candidate = str(candidate)
            if _basename(candidate) == wanted and os.path.isfile(candidate):
                return candidate

    for attr in ("pdf1_documents", "pdf2_documents"):
        documents = getattr(app, attr, None)
        if documents is not None:
            wanted = _basename(displayed)
            for doc in documents:
                path = doc.get("path") if isinstance(doc, dict) else getattr(doc, "path", None)
                if path and _basename(str(path)) == wanted and os.path.isfile(str(path)):
                    return str(path)
    return None


def _open_pdf(path: str) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass


def _hide(tree: ttk.Treeview) -> None:
    overlay = getattr(tree, "_pdf_hover_overlay", None)
    if overlay is not None:
        try:
            overlay.destroy()
        except tk.TclError:
            pass
    tree._pdf_hover_overlay = None
    tree._pdf_hover_path = None


def _show(tree: ttk.Treeview, item: str, column_id: str, path: str) -> None:
    bbox = tree.bbox(item, column_id)
    if not bbox:
        _hide(tree)
        return
    x, y, width, height = map(int, bbox)
    root = tree.winfo_toplevel()
    screen_x = tree.winfo_rootx() + x
    screen_y = tree.winfo_rooty() + y
    overlay = getattr(tree, "_pdf_hover_overlay", None)
    if overlay is None or not overlay.winfo_exists():
        overlay = tk.Toplevel(root)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        try:
            overlay.attributes("-transparentcolor", "#ff00ff")
        except tk.TclError:
            overlay.destroy()
            _hide(tree)
            return
        canvas = tk.Canvas(overlay, bg="#ff00ff", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        overlay.bind("<Button-1>", lambda _e, t=tree: _open_pdf(getattr(t, "_pdf_hover_path", "")))
        tree._pdf_hover_overlay = overlay
    else:
        canvas = overlay.winfo_children()[0]
    canvas.delete("all")
    canvas.create_rectangle(2, 2, max(2, width - 2), max(2, height - 2), outline="#7CFC00", width=2)
    overlay.geometry(f"{width}x{height}+{screen_x}+{screen_y}")
    tree._pdf_hover_path = path


def _motion(tree: ttk.Treeview, event) -> None:
    try:
        item = tree.identify_row(event.y)
        column_id = tree.identify_column(event.x)
        if not item or not column_id:
            _hide(tree)
            return
        path = _resolve_pdf(tree, item, column_id)
        if path:
            _show(tree, item, column_id, path)
        else:
            _hide(tree)
    except Exception:
        _hide(tree)


def _treeview_init(self, *args, **kwargs):
    _ORIGINAL_TREEVIEW_INIT(self, *args, **kwargs)
    self.bind("<Motion>", lambda event, tree=self: _motion(tree, event), add="+")
    self.bind("<Leave>", lambda _event, tree=self: _hide(tree), add="+")


ttk.Treeview.__init__ = _treeview_init
