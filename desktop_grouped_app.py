"""Grouped desktop entry point for PDF kW Selector."""
from __future__ import annotations

from dataclasses import replace
import re
import sys

from pypdf import PdfReader

import desktop_app as desktop_module
from ahu_matching import normalize_equipment_id
from app_logger import exception, info, startup, warning
from desktop_app import App as BaseApp, VERSION
from drag_drop import install_pdf_drop_targets
from result_grouping import group_result_rows
from updater import apply_update
from confirmation_workflow import analyze_with_confirmations


def _path_strings(items):
    """Accept both GUI PdfInput objects and plain filesystem paths."""
    result = []
    for item in items or []:
        value = getattr(item, "path", item)
        result.append(str(value))
    return result


def _confirmed_analyze(pdf1_inputs, pdf2_inputs):
    """Normalize GUI inputs before entering the confirmation workflow."""
    pdf1_paths = _path_strings(pdf1_inputs)
    pdf2_paths = _path_strings(pdf2_inputs)
    info("Onaylı analiz girişleri normalize edildi", pdf1_count=len(pdf1_paths), pdf2_count=len(pdf2_paths))
    return analyze_with_confirmations(pdf1_paths, pdf2_paths)


# desktop_app.compare resolves analyze_batch from its module namespace. Replace that
# binding for the grouped production entry point so confirmations happen before
# the actual Project -> AHU -> Motor calculation starts.
desktop_module.analyze_batch = _confirmed_analyze


EBM_BRAND_RE = re.compile(r"\bmodel\s+brand\b\s*[:=\-]?\s*(EBM\s*[- ]?\s*Papst)\b", re.I)


def _page_is_ebm(path: str, page_number: int) -> bool:
    """Check the exact PDF1 motor page for Model Brand = EBM-Papst."""
    try:
        pages = PdfReader(path).pages
        if page_number < 1 or page_number > len(pages):
            return False
        text = pages[page_number - 1].extract_text() or ""
        match = EBM_BRAND_RE.search(re.sub(r"\s+", " ", text))
        if match:
            info("PDF1 EBM-Papst motor tespit edildi", path=path, page=page_number, brand=match.group(1))
            return True
        return False
    except Exception as exc:
        warning("PDF1 Model Brand okunamadı", path=path, page=page_number, error=str(exc))
        return False


def _apply_ebm_rules(analysis):
    """Mark EBM-Papst motors as intentionally excluded from kW comparison."""
    if analysis is None:
        return None

    page_cache: dict[tuple[str, int], bool] = {}
    ebm_count = 0
    updated = []

    for comparison in analysis.motor_comparisons:
        if not comparison.pdf1_page:
            updated.append(comparison)
            continue

        equipment = normalize_equipment_id(comparison.equipment_id)
        candidate_paths: list[str] = []
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
        updated.append(
            replace(
                comparison,
                component_label=f"{comparison.component_label} [EBM]",
                difference_kw=None,
                status=status,
            )
        )

    info("EBM-Papst motor kuralları uygulandı", ebm_motor_count=ebm_count)
    return replace(analysis, motor_comparisons=tuple(updated))


def _rerender_modified_rows(app, original_analysis):
    """Update the already-rendered Treeview rows without running the analysis again."""
    comparisons = list(original_analysis.motor_comparisons)
    comparisons.sort(key=lambda item: (
        next((
            normalize_equipment_id(ahu.match.left_normalized)
            for ahu in original_analysis.ahu_matches
            if normalize_equipment_id(ahu.match.left_normalized) == normalize_equipment_id(item.equipment_id)
        ), "-").casefold(),
        normalize_equipment_id(item.equipment_id).casefold(),
        item.component_type.casefold(),
        item.component_index,
    ))

    item_ids = list(app.tree.get_children())
    if len(item_ids) != len(comparisons):
        warning("EBM sonuç satırları yeniden işlenemedi: Treeview satır sayısı farklı", tree_rows=len(item_ids), comparisons=len(comparisons))
        return

    for item_id, comparison in zip(item_ids, comparisons):
        values = list(app.tree.item(item_id, "values"))
        if comparison.status.startswith("EBM-PAPST"):
            values[2] = comparison.component_label
            values[7] = comparison.status
            values[6] = "-"
            app.tree.item(item_id, values=values)


class GroupedApp(BaseApp):
    """Base GUI with Project -> AHU visual grouping in the results table."""
    def __init__(self):
        super().__init__()
        install_pdf_drop_targets(self, self.pdf1_label.master, self.pdf2_label.master)

    def compare(self):
        super().compare()
        try:
            if self.analysis is None:
                return
            original = self.analysis
            self.analysis = _apply_ebm_rules(original)
            _rerender_modified_rows(self, self.analysis)

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
