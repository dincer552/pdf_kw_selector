"""Grouped desktop entry point for PDF kW Selector."""
from __future__ import annotations

import sys

from app_logger import exception, startup
from desktop_app import App as BaseApp, VERSION
from drag_drop import install_pdf_drop_targets
from result_grouping import group_result_rows
from updater import apply_update


class GroupedApp(BaseApp):
    """Base GUI with Project -> AHU visual grouping in the results table."""

    def __init__(self):
        super().__init__()
        # Keep the existing PDF EKLE / KLASÖR EKLE buttons and add drag-and-drop
        # to the same two input boxes.
        install_pdf_drop_targets(self, self.pdf1_label.master, self.pdf2_label.master)

    def compare(self):
        super().compare()
        try:
            if self.analysis is None:
                return

            rows = [self.tree.item(item_id, "values") for item_id in self.tree.get_children()]
            grouped = group_result_rows(rows)

            for item_id in self.tree.get_children():
                self.tree.delete(item_id)

            for row in grouped:
                self.tree.insert("", "end", values=row)

            exception_count = sum(1 for row in grouped if not any(str(value).strip() for value in row))
            from app_logger import info
            info(
                "GUI sonuçları Project/AHU gruplandı",
                source_rows=len(rows),
                displayed_rows=len(grouped),
                group_separators=exception_count,
            )
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
