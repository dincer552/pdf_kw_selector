"""Desktop GUI for PDF kW Selector - multi-PDF, project and AHU discovery."""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ahu_matching import discover_equipment
from batch_input import discover_pdfs
from motor_compare import MotorComparison, compare_motor_records
from project_discovery import discover_project
from stage1_page_discovery import build_stage1_motor_records, find_rated_motor_powers_in_pdf
from stage2_pdf_discovery import build_pdf2_motor_records, find_pdf2_motor_powers

VERSION = "v0.4.2"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"PDF kW Selector {VERSION} — Multi-PDF")
        self.geometry("1180x760")
        self.minsize(1020, 650)
        self.pdf1_inputs = []
        self.pdf2_inputs = []
        self.pdf1 = self.pdf2 = None
        self.pdf1_results = []
        self.pdf2_results = []
        self.pdf1_motors = []
        self.pdf2_motors = []
        self.pdf1_projects = []
        self.pdf2_projects = []
        self.pdf1_ahus = []
        self.pdf2_ahus = []
        self.comparisons: list[MotorComparison] = []
        self._build()

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        ttk.Label(outer, text="PDF kW SELECTOR", font=("Segoe UI", 19, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(outer, text=f"{VERSION}  •  Multi-PDF + Project + AHU Discovery", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="e")

        top = ttk.Frame(outer)
        top.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        self.pdf1_label = self._file_box(top, "PDF 1 — Seçim / ekipman", 0, self.add_pdf1_files, self.add_pdf1_folder)
        self.pdf2_label = self._file_box(top, "PDF 2 — Elektrik / sürücü", 1, self.add_pdf2_files, self.add_pdf2_folder)

        result_frame = ttk.LabelFrame(outer, text="Karşılaştırma", padding=8)
        result_frame.grid(row=2, column=0, sticky="nsew")
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        cols = ("label", "type", "pdf1", "pdf2", "diff", "status", "page1", "page2")
        headings = {"label":"Motor", "type":"Tip", "pdf1":"PDF1 kW", "pdf2":"PDF2 kW", "diff":"Fark", "status":"Durum", "page1":"PDF1 Sayfa", "page2":"PDF2 Sayfa"}
        widths = {"label":100,"type":110,"pdf1":85,"pdf2":85,"diff":75,"status":120,"page1":90,"page2":90}
        self.tree = ttk.Treeview(result_frame, columns=cols, show="headings", height=18)
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew", pady=8)
        ttk.Button(actions, text="KARŞILAŞTIR", command=self.compare).pack(side="left")
        ttk.Button(actions, text="SEÇİLENLERİ TEMİZLE", command=self.clear_inputs).pack(side="left", padx=8)
        ttk.Button(actions, text="JSON KAYDET", command=self.save_json).pack(side="left")
        self.status = ttk.Label(actions, text="PDF 1 ve PDF 2 için dosya veya klasör ekleyin.")
        self.status.pack(side="right")

        self.detail = tk.Text(outer, height=8, wrap="word", font=("Consolas", 9))
        self.detail.grid(row=4, column=0, sticky="ew")
        self.detail.configure(state="disabled")

    def _file_box(self, parent, title, column, file_command, folder_command):
        box = ttk.LabelFrame(parent, text=title, padding=8)
        box.grid(row=0, column=column, sticky="nsew", padx=(0, 5) if column == 0 else (5, 0))
        label = ttk.Label(box, text="0 PDF seçildi", width=62)
        label.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(box, text="PDF EKLE", command=file_command).grid(row=1, column=0, sticky="w")
        ttk.Button(box, text="KLASÖR EKLE", command=folder_command).grid(row=1, column=1, sticky="w", padx=6)
        box.columnconfigure(0, weight=1)
        return label

    def _add_inputs(self, target: str):
        paths = filedialog.askopenfilenames(title=f"{target} PDF dosyalarını seç", filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if paths:
            self._merge_inputs(target, list(paths))

    def _add_folder(self, target: str):
        path = filedialog.askdirectory(title=f"{target} PDF klasörünü seç")
        if path:
            self._merge_inputs(target, [path])

    def _merge_inputs(self, target: str, paths):
        current = self.pdf1_inputs if target == "PDF1" else self.pdf2_inputs
        merged = discover_pdfs([item.path for item in current] + list(paths), recursive=True)
        if target == "PDF1":
            self.pdf1_inputs = merged
            self._update_label(self.pdf1_label, merged)
        else:
            self.pdf2_inputs = merged
            self._update_label(self.pdf2_label, merged)
        self.status.configure(text=f"{target}: {len(merged)} PDF hazır")

    def _update_label(self, label, items):
        if not items:
            label.configure(text="0 PDF seçildi")
            return
        names = [Path(item.path).name for item in items[:3]]
        suffix = " ..." if len(items) > 3 else ""
        label.configure(text=f"{len(items)} PDF: " + ", ".join(names) + suffix)

    def add_pdf1_files(self): self._add_inputs("PDF1")
    def add_pdf1_folder(self): self._add_folder("PDF1")
    def add_pdf2_files(self): self._add_inputs("PDF2")
    def add_pdf2_folder(self): self._add_folder("PDF2")

    def clear_inputs(self):
        self.pdf1_inputs, self.pdf2_inputs = [], []
        self.pdf1 = self.pdf2 = None
        self.pdf1_motors, self.pdf2_motors = [], []
        self.pdf1_projects, self.pdf2_projects = [], []
        self.pdf1_ahus, self.pdf2_ahus, self.comparisons = [], [], []
        self._update_label(self.pdf1_label, [])
        self._update_label(self.pdf2_label, [])
        for item in self.tree.get_children(): self.tree.delete(item)
        self.status.configure(text="Seçimler temizlendi.")

    def _analyze_pdf1_batch(self):
        motors, results, projects, ahus = [], [], [], []
        for item in self.pdf1_inputs:
            path = Path(item.path)
            projects.append(discover_project(path))
            ahus.append(discover_equipment(path))
            found = find_rated_motor_powers_in_pdf(path)
            results.extend(found)
            motors.extend(record for result in found for record in build_stage1_motor_records(result))
        return results, motors, projects, ahus

    def _analyze_pdf2_batch(self):
        motors, results, projects, ahus = [], [], [], []
        counters: dict[tuple[str, str], int] = {}
        for item in self.pdf2_inputs:
            path = Path(item.path)
            projects.append(discover_project(path))
            ahus.append(discover_equipment(path))
            found = find_pdf2_motor_powers(path)
            results.extend(found)
            for result in found:
                key = (result.equipment_id or path.stem, result.component_type)
                current = counters.get(key, 0) + 1
                records = build_pdf2_motor_records(result, start_index=current)
                motors.extend(records)
                counters[key] = current + len(records) - 1
        return results, motors, projects, ahus

    def compare(self):
        if not self.pdf1_inputs or not self.pdf2_inputs:
            messagebox.showwarning("PDF eksik", "PDF 1 ve PDF 2 tarafına en az bir PDF veya klasör ekleyin.")
            return
        try:
            self.status.configure(text="Toplu PDF + Project + AHU Discovery analizi yapılıyor...")
            self.update_idletasks()
            self.pdf1_results, self.pdf1_motors, self.pdf1_projects, self.pdf1_ahus = self._analyze_pdf1_batch()
            self.pdf2_results, self.pdf2_motors, self.pdf2_projects, self.pdf2_ahus = self._analyze_pdf2_batch()
            self.comparisons = compare_motor_records(self.pdf1_motors, self.pdf2_motors)
        except Exception as exc:
            messagebox.showerror("Analiz hatası", str(exc))
            self.status.configure(text="Analiz hatası")
            return

        for item in self.tree.get_children(): self.tree.delete(item)
        counts = {"MATCH":0,"MISMATCH":0,"ONLY_IN_PDF1":0,"ONLY_IN_PDF2":0}
        for result in self.comparisons:
            counts[result.status] = counts.get(result.status, 0) + 1
            self.tree.insert("", "end", values=(result.component_label,result.component_type,self._fmt(result.pdf1_kw),self._fmt(result.pdf2_kw),self._fmt(result.difference_kw),result.status,result.pdf1_page or "-",result.pdf2_page or "-"))
        pdf1_ahu_count = sum(len(x.unique_ids()) for x in self.pdf1_ahus)
        pdf2_ahu_count = sum(len(x.unique_ids()) for x in self.pdf2_ahus)
        self.status.configure(text=f"✓ {len(self.comparisons)} MOTOR | AHU PDF1 {pdf1_ahu_count} | AHU PDF2 {pdf2_ahu_count} | MATCH {counts['MATCH']} | MISMATCH {counts['MISMATCH']}")
        detail = {
            "pdf1_projects": [p.to_dict() for p in self.pdf1_projects],
            "pdf2_projects": [p.to_dict() for p in self.pdf2_projects],
            "pdf1_ahus": [a.to_dict() for a in self.pdf1_ahus],
            "pdf2_ahus": [a.to_dict() for a in self.pdf2_ahus],
            "comparison": [r.to_dict() for r in self.comparisons],
        }
        self._set_detail(json.dumps(detail, ensure_ascii=False, indent=2))

    @staticmethod
    def _fmt(value): return "-" if value is None else f"{value:g}"

    def _set_detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def save_json(self):
        if not self.comparisons:
            messagebox.showwarning("Sonuç yok", "Önce KARŞILAŞTIR çalıştırın.")
            return
        path = filedialog.asksaveasfilename(title="Toplu karşılaştırmayı kaydet", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        payload = {
            "version": VERSION,
            "pdf1_files": [r.to_dict() for r in self.pdf1_inputs],
            "pdf2_files": [r.to_dict() for r in self.pdf2_inputs],
            "pdf1_projects": [r.to_dict() for r in self.pdf1_projects],
            "pdf2_projects": [r.to_dict() for r in self.pdf2_projects],
            "pdf1_ahus": [r.to_dict() for r in self.pdf1_ahus],
            "pdf2_ahus": [r.to_dict() for r in self.pdf2_ahus],
            "pdf1_motors": [r.to_dict() for r in self.pdf1_motors],
            "pdf2_motors": [r.to_dict() for r in self.pdf2_motors],
            "comparison": [r.to_dict() for r in self.comparisons],
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Kaydedildi", f"Sonuç kaydedildi:\n{path}")


if __name__ == "__main__":
    App().mainloop()
