"""Grouped desktop entry point for PDF kW Selector."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
import sys

import desktop_app as desktop_module
from ahu_matching import normalize_equipment_id
from app_logger import exception, info, startup, warning
from desktop_app import App as BaseApp, VERSION
from drag_drop import install_pdf_drop_targets
from result_grouping import group_result_rows
from updater import apply_update
from confirmation_workflow import analyze_with_confirmations
from pdf_master_scan import scan_pdf


def _path_strings(items):
    result = []
    for item in items or []:
        value = getattr(item, "path", item)
        result.append(str(value))
    return result


def _confirmed_analyze(pdf1_inputs, pdf2_inputs):
    pdf1_paths = _path_strings(pdf1_inputs)
    pdf2_paths = _path_strings(pdf2_inputs)
    info("Onaylı analiz girişleri normalize edildi", pdf1_count=len(pdf1_paths), pdf2_count=len(pdf2_paths))
    return analyze_with_confirmations(pdf1_paths, pdf2_paths)


desktop_module.analyze_batch = _confirmed_analyze


def _page_is_ebm(path: str, page_number: int) -> bool:
    try:
        scan = scan_pdf(path, "PDF1")
        if page_number < 1 or page_number > len(scan.page_texts):
            return False
        text = scan.page_texts[page_number - 1]
        match = re.search(r"\bmodel\s+brand\b\s*[:=\-]?\s*(EBM\s*[- ]?\s*Papst)\b", re.sub(r"\s+", " ", text), re.I)
        if match:
            info("PDF1 EBM-Papst motor tespit edildi", path=path, page=page_number, brand=match.group(1))
            return True
        return False
    except Exception as exc:
        warning("PDF1 Model Brand okunamadı", path=path, page=page_number, error=str(exc))
        return False


def _apply_ebm_rules(analysis):
    if analysis is None:
        return None
    # Motor comparison is already skipped for document-level EBM PDFs in batch_analysis.
    # Keep this function for compatibility with any legacy comparison rows.
    page_cache: dict[tuple[str, int], bool] = {}
    updated = []
    ebm_count = 0
    for comparison in analysis.motor_comparisons:
        if not comparison.pdf1_page:
            updated.append(comparison)
            continue
        equipment = normalize_equipment_id(comparison.equipment_id)
        candidate_paths = []
        for ahu in analysis.ahu_matches:
            if normalize_equipment_id(ahu.match.left_normalized) == equipment:
                candidate_paths.extend(ahu.pdf1_files)
        is_ebm = False
        for path in dict.fromkeys(candidate_paths):
            key = (path, comparison.pdf1_page)
            if key not in page_cache:
                page_cache[key] = _page_is_ebm(path, comparison.pdf1_page)
            if page_cache[key]:
                is_ebm = True
                break
        if not is_ebm:
            updated.append(comparison)
            continue
        ebm_count += 1
        status = "EBM-PAPST - PDF2 MOTOR YOK" if comparison.pdf2_kw is None else "EBM-PAPST - kW KONTROLÜ YOK"
        updated.append(replace(comparison, component_label=f"{comparison.component_label} [EBM]", difference_kw=None, status=status))
    info("EBM-Papst legacy sonuç kuralları uygulandı", ebm_motor_count=ebm_count)
    return replace(analysis, motor_comparisons=tuple(updated))


def _rerender_modified_rows(app, original_analysis):
    comparisons = list(original_analysis.motor_comparisons)
    comparisons.sort(key=lambda item: (
        next((normalize_equipment_id(ahu.match.left_normalized) for ahu in original_analysis.ahu_matches if normalize_equipment_id(ahu.match.left_normalized) == normalize_equipment_id(item.equipment_id)), "-").casefold(),
        normalize_equipment_id(item.equipment_id).casefold(), item.component_type.casefold(), item.component_index,
    ))
    item_ids = list(app.tree.get_children())
    if len(item_ids) != len(comparisons):
        return
    for item_id, comparison in zip(item_ids, comparisons):
        values = list(app.tree.item(item_id, "values"))
        if comparison.status.startswith("EBM-PAPST"):
            values[2] = comparison.component_label
            values[7] = comparison.status
            values[6] = "-"
            app.tree.item(item_id, values=values)


class GroupedApp(BaseApp):
    """Base GUI with Project -> AHU grouping and dedicated EBM-Papst view."""
    def __init__(self):
        super().__init__()
        self._build_ebm_tab()
        install_pdf_drop_targets(self, self.pdf1_label.master, self.pdf2_label.master)

    def _build_ebm_tab(self):
        tab = __import__("tkinter").ttk.Frame(self.tabs)
        self.tabs.add(tab, text="EBM-PAPST (0)")
        cols = ("PDF1", "Proje", "AHU", "EBM Sayfaları", "PDF2", "Durum")
        self.ebm_tree = __import__("tkinter").ttk.Treeview(tab, columns=cols, show="headings")
        widths = {"PDF1": 300, "Proje": 300, "AHU": 120, "EBM Sayfaları": 130, "PDF2": 420, "Durum": 220}
        for col in cols:
            self.ebm_tree.heading(col, text=col)
            self.ebm_tree.column(col, width=widths[col], anchor="w")
        scroll = __import__("tkinter").ttk.Scrollbar(tab, orient="vertical", command=self.ebm_tree.yview)
        self.ebm_tree.configure(yscrollcommand=scroll.set)
        self.ebm_tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        scroll.pack(side="right", fill="y", padx=(0, 5), pady=5)
        self.ebm_tab = tab

    def _render_ebm(self):
        for item in self.ebm_tree.get_children():
            self.ebm_tree.delete(item)
        rows = []
        for document in self.analysis.pdf1_documents:
            scan = scan_pdf(document.path, "PDF1")
            if not scan.pdf1_ebm_pages:
                continue
            ahu_ids = tuple(document.equipment) or ("-",)
            matching_pdf2 = []
            matched_ahu = []
            for ahu in self.analysis.ahu_matches:
                if str(document.path).casefold() in {str(path).casefold() for path in ahu.pdf1_files}:
                    matching_pdf2.extend(ahu.pdf2_files)
                    matched_ahu.append(normalize_equipment_id(ahu.match.right_normalized) or normalize_equipment_id(ahu.match.left_normalized) or "-")
            pdf2_text = ", ".join(Path(path).name for path in dict.fromkeys(matching_pdf2)) or "-"
            status = "PDF2 AHU eşleşti; motor kW karşılaştırması yapılmadı" if matching_pdf2 else "PDF2 AHU eşleşmesi yok"
            for ahu_id in ahu_ids:
                rows.append((Path(document.path).name, document.project.project_name or "-", normalize_equipment_id(ahu_id) or "-", ", ".join(map(str, scan.pdf1_ebm_pages)), pdf2_text, status))
        rows.sort(key=lambda row: (row[1].casefold(), row[2].casefold(), row[0].casefold()))
        for row in rows:
            self.ebm_tree.insert("", "end", values=row)
        self.tabs.tab(self.ebm_tab, text=f"EBM-PAPST ({len(rows)})")
        info("EBM-Papst sekmesi oluşturuldu", ebm_pdf_count=len(rows), rows=rows)

    def _post_analysis(self):
        try:
            original = self.analysis
            self.analysis = _apply_ebm_rules(original)
            _rerender_modified_rows(self, self.analysis)
            self._render_ebm()
            rows = [self.tree.item(item_id, "values") for item_id in self.tree.get_children()]
            grouped = group_result_rows(rows)
            for item_id in self.tree.get_children():
                self.tree.delete(item_id)
            for row in grouped:
                self.tree.insert("", "end", values=row)
            exception_count = sum(1 for row in grouped if not any(str(value).strip() for value in row))
            info("GUI sonuçları Project/AHU gruplandı", source_rows=len(rows), displayed_rows=len(grouped), group_separators=exception_count)
            self.refresh_logs()
        except Exception as exc:
            exception("Project/AHU sonuç gruplama hatası", exc)
            self.refresh_logs()

    def compare(self):
        super().compare()


if __name__ == "__main__":
    startup(VERSION)
    if len(sys.argv) >= 2 and sys.argv[1] == "--apply-update":
        try:
            apply_update(sys.argv[2], sys.argv[3], int(sys.argv[4]))
        except Exception as exc:
            exception("Updater modu başarısız", exc, argv=sys.argv)
            raise
    else:
        try:
            GroupedApp().mainloop()
        except Exception as exc:
            exception("GUI ana döngüsü beklenmedik hata ile kapandı", exc)
            raise
