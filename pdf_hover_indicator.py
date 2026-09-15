"""Show a green outline over PDF cells while the mouse is over them."""
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


def _candidate_from_cell_data(tree: ttk.Treeview, item: str, column_id: str) -> str | None:
    """Use the exact PDF path stored by the result renderer when available."""
    app = tree.winfo_toplevel()
    data_maps = (
        ("_tree_cell_data", {"#3": "pdf1_path", "#4": "pdf2_path"}),
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
        path = data.get(mapping.get(column_id, ""))
        if path and os.path.isfile(str(path)):
            return str(path)
    return None


def _resolve_pdf(tree: ttk.Treeview, item: str, column_id: str) -> str | None:
    try:
        heading = str(tree.heading(column_id, "text") or "").strip().casefold()
    except tk.TclError:
        return None
    if heading not in _PDF_COLUMNS:
        return None

    # Result renderers already know the exact source path. Prefer that over
    # filename matching so duplicate PDF names cannot highlight the wrong file.
    exact = _candidate_from_cell_data(tree, item, column_id)
    if exact:
        return exact

    values = tree.item(item, "values") or ()
    try:
        column_index = list(tree["columns"]).index(column_id)
    except (ValueError, tk.TclError):
        return None
    if column_index >= len(values):
        return None
    displayed = str(values[column_index]).strip()
    if not _is_pdf(displayed):
        return None

    # A full PDF path may also be supplied as a Treeview tag.
    for tag in tree.item(item, "tags") or ():
        if _is_pdf(tag) and os.path.isfile(os.path.expanduser(str(tag))):
            return os.path.expanduser(str(tag))

    # Fall back to the source-document lists on the application.
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

    # Last fallback: inspect common analysis document containers. Dataclass
    # objects are handled explicitly; this avoids the previous recursive scan
    # silently ignoring Path/document objects.
    analysis = getattr(app, "analysis", None)
    for attr in ("pdf1_documents", "pdf2_documents"):
        documents = getattr(analysis, attr, None) if analysis is not None else None
        for doc in documents or ():
            path = getattr(doc, "path", None)
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
    if not bbox or len(bbox) < 4:
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

        def click(_event=None, t=tree):
            selected = getattr(t, "_pdf_hover_path", None)
            if selected:
                _open_pdf(selected)

        overlay.bind("<Button-1>", click)
        overlay.bind("<Leave>", lambda _event, t=tree: _hide(t))
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
    except tk.TclError:
        _hide(tree)
    except Exception:
        _hide(tree)


def _treeview_init(self, *args, **kwargs):
    _ORIGINAL_TREEVIEW_INIT(self, *args, **kwargs)
    self.bind("<Motion>", lambda event, tree=self: _motion(tree, event), add="+")
    self.bind("<Leave>", lambda _event, tree=self: _hide(tree), add="+")


ttk.Treeview.__init__ = _treeview_init
