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


# desktop_app.compare resolves analyze_batch from its module namespace. Replace that
# binding for the grouped production entry point so confirmations happen before
# the actual Project -> AHU -> Motor calculation starts.
desktop_module.analyze_batch = analyze_with_confirmations


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
    """Mark EBM-Papst motors as intentionally excluded from kW comparison.

    The physical motor is still paired with the corresponding PDF2 motor so the
    user can see the PDF2 side, but no kW difference/MISMATCH is calculated for
    EBM-Papst. Standard motors remain on the normal comparison path.
    """
    if analysis is None:
        return

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
            left = normalize_equipment_id(ahu.match.left_normalized)
            if left == equipment:
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
        if comparison.pdf2_kw is None:
            status = "EBM-PAPST - PDF2 MOTOR YOK"
        else:
            status = "EBM-PAPST - kW KONTROLÜ YOK"

        updated.append(
            replace(
                comparison,
                component_label=f"{comparison.component_label} [EBM]",
                difference_kw=None,
                status=status,
            )
        )

    analysis.motor_comparisons = tuple(updated) if hasattr(analysis, "motor_comparisons") else analysis.motor_comparisons
    info("EBM-Papst motor kuralları uygulandı", ebm_motor_count=ebm_count)


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
            _apply_ebm_rules(self.analysis)
            # Re-render rows after EBM statuses/labels are applied.
            for item_id in self.tree.get_children():
                self.tree.delete(item_id)
            self._render_results()

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
