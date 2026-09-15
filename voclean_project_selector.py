"""Select the PDF1 project group for PDF2 files whose coordinate Project Name says VOCLEAN."""
from __future__ import annotations

import threading
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox

import batch_analysis as batch
import pdf_master_scan
from app_logger import info, warning

_PROJECT_OVERRIDES: dict[str, object] = {}
_ORIGINAL_SCAN_PDF = pdf_master_scan.scan_pdf


def _scan_pdf_with_project_override(path, side):
    scan = _ORIGINAL_SCAN_PDF(path, side)
    if str(side).upper().strip() != "PDF2":
        return scan
    override = _PROJECT_OVERRIDES.get(str(scan.path).casefold())
    return replace(scan, project=override) if override is not None else scan


pdf_master_scan.scan_pdf = _scan_pdf_with_project_override
batch.scan_pdf = _scan_pdf_with_project_override


def set_pdf2_project_override(path: str, project) -> None:
    _PROJECT_OVERRIDES[str(path).casefold()] = project


def clear_pdf2_project_overrides(paths) -> None:
    for path in paths:
        _PROJECT_OVERRIDES.pop(str(path).casefold(), None)


def _run_on_ui(callback):
    root = tk._default_root
    if root is None:
        raise RuntimeError("Tk ana penceresi bulunamadı; VOCLEAN proje seçimi açılamıyor.")
    done = threading.Event()
    result = {}

    def invoke():
        try:
            result["value"] = callback(root)
        except Exception as exc:
            result["error"] = exc
        finally:
            done.set()

    root.after(0, invoke)
    done.wait()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _select_group(root, pdf_path: str, groups):
    dialog = tk.Toplevel(root)
    dialog.title("VOCLEAN Proje Grubu Seçimi")
    dialog.transient(root)
    dialog.grab_set()
    dialog.resizable(False, False)
    frame = tk.Frame(dialog, padx=16, pady=14)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text="PDF2 Proje Name koordinatında VOCLEAN bulundu.", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
    tk.Label(frame, text=f"{pdf_path}\n\nBu PDF hangi PDF1 proje grubuna ait?", justify="left", anchor="w").pack(fill="x", pady=(6, 10))
    listbox = tk.Listbox(frame, width=72, height=min(max(len(groups), 3), 12), exportselection=False)
    for key, docs in groups:
        name = docs[0].project.project_name or key
        variants = sorted({d.project.project_name for d in docs if d.project.project_name})
        suffix = f"  [{len(variants)} adlandırma]" if len(variants) > 1 else ""
        listbox.insert("end", f"{name}{suffix}")
    listbox.pack(fill="both", expand=True)
    if groups:
        listbox.selection_set(0)
        listbox.activate(0)
    choice = {"index": None}

    def accept():
        selected = listbox.curselection()
        if not selected:
            messagebox.showwarning("VOCLEAN", "Önce bir proje grubu seçin.", parent=dialog)
            return
        choice["index"] = int(selected[0])
        dialog.destroy()

    def cancel():
        choice["index"] = -1
        dialog.destroy()

    buttons = tk.Frame(frame)
    buttons.pack(fill="x", pady=(12, 0))
    tk.Button(buttons, text="SEÇ", width=12, command=accept).pack(side="right", padx=(6, 0))
    tk.Button(buttons, text="İPTAL", width=12, command=cancel).pack(side="right")
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    root.wait_window(dialog)
    index = choice["index"]
    if index is None or index < 0:
        return None
    return groups[index][0]


def prepare_voclean_project_assignments(pdf1_paths, pdf2_paths):
    """Pre-scan PDF2 coordinate Project Name and assign VOCLEAN files to PDF1 groups."""
    clear_pdf2_project_overrides(pdf2_paths)
    pdf1_documents = batch._discover_documents(list(pdf1_paths), "PDF1")
    left_groups = batch._group_documents(pdf1_documents)
    groups = [(key, docs) for key, docs in left_groups.items() if not key.startswith("__UNRESOLVED__:") and docs]
    if not groups:
        return {}
    voclean_paths = []
    for path in pdf2_paths:
        scan = _ORIGINAL_SCAN_PDF(path, "PDF2")
        project = scan.project
        # VOCLEAN detection is coordinate-only; normal PDF2 project discovery is unchanged.
        if project.project_source == "project_coordinates" and "voclean" in (project.project_name or "").casefold():
            voclean_paths.append(str(scan.path))
    assignments = {}
    for path in voclean_paths:
        selected_key = _run_on_ui(lambda root, p=path: _select_group(root, p, groups))
        if selected_key is None:
            warning("VOCLEAN proje grubu seçimi iptal edildi", path=path)
            raise RuntimeError(f"VOCLEAN proje grubu seçimi iptal edildi: {path}")
        selected_project = left_groups[selected_key][0].project
        set_pdf2_project_override(path, selected_project)
        assignments[path] = selected_key
        info("VOCLEAN PDF2 proje grubu kullanıcı tarafından seçildi", path=path, selected_group=selected_key, selected_project=selected_project.project_name)
    return assignments


def install():
    import confirmation_workflow
    original = confirmation_workflow.analyze_with_confirmations
    if getattr(original, "_voclean_selector_installed", False):
        return

    def wrapped(pdf1_paths, pdf2_paths, progress_callback=None):
        prepare_voclean_project_assignments(pdf1_paths, pdf2_paths)
        return original(pdf1_paths, pdf2_paths, progress_callback=progress_callback)

    wrapped._voclean_selector_installed = True
    confirmation_workflow.analyze_with_confirmations = wrapped


install()
