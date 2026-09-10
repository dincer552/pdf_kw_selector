"""Desktop GUI for PDF kW Selector - Project -> AHU -> Motor batch analysis."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ahu_matching import normalize_equipment_id
from app_logger import clear_log, exception, info, log_directory, log_file, read_log, startup, warning
from batch_analysis import analyze_batch
from batch_input import discover_pdfs
from project_discovery import discover_project, normalize_project_name
from project_matching import match_project_names
from updater import apply_update, check_for_update, download_update, restart_with_update

VERSION = "v0.5.3"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"PDF kW Selector {VERSION} — Batch Motor Analysis")
        self.geometry("1320x800")
        self.minsize(1120, 700)
        self.pdf1_inputs = []
        self.pdf2_inputs = []
        self.analysis = None
        self._log_refresh_job = None
        self.report_callback_exception = self._report_callback_exception
        self._project_approved_variants: set[tuple[str, str]] = set()
        self._ahu_approved_variants: set[tuple[str, str]] = set()
        self._build()
        self.refresh_logs(); self._schedule_log_refresh()
        info("GUI hazır", pdf1_count=0, pdf2_count=0)

    def _report_callback_exception(self, exc, value, tb):
        try:
            import traceback
            exception("YAKALANMAMIŞ GUI CALLBACK HATASI", value, callback_exception_type=getattr(exc, "__name__", str(exc)), traceback_text="".join(traceback.format_exception(exc, value, tb)))
            self.refresh_logs()
        except Exception as log_exc: exception("GUI callback hatası loglanırken ikinci hata oluştu", log_exc)

    def _schedule_log_refresh(self):
        try:
            if self.winfo_exists(): self._log_refresh_job = self.after(1000, self._scheduled_log_refresh)
        except Exception as exc: exception("Otomatik log yenileme zamanlayıcısı başlatılamadı", exc)

    def _scheduled_log_refresh(self):
        try: self.refresh_logs()
        except Exception as exc: exception("Otomatik log yenileme hatası", exc)
        finally: self._schedule_log_refresh()

    def _build(self):
        outer = ttk.Frame(self, padding=12); outer.pack(fill="both", expand=True); outer.columnconfigure(0, weight=1); outer.rowconfigure(2, weight=1)
        header = ttk.Frame(outer); header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="PDF kW SELECTOR", font=("Segoe UI", 19, "bold")).pack(side="left")
        ttk.Label(header, text=f"{VERSION} • Project → AHU → Motor", font=("Segoe UI", 10)).pack(side="right")
        top = ttk.Frame(outer); top.grid(row=1, column=0, sticky="ew", pady=(10, 8)); top.columnconfigure(0, weight=1); top.columnconfigure(1, weight=1)
        self.pdf1_label = self._file_box(top, "PDF 1 — Seçim / Referans", 0, self.add_pdf1_files, self.add_pdf1_folder)
        self.pdf2_label = self._file_box(top, "PDF 2 — Elektrik / Üretim", 1, self.add_pdf2_files, self.add_pdf2_folder)
        notebook = ttk.Notebook(outer); notebook.grid(row=2, column=0, sticky="nsew")
        result = ttk.Frame(notebook, padding=8); result.columnconfigure(0, weight=1); result.rowconfigure(0, weight=1); notebook.add(result, text="SONUÇLAR")
        cols=("project","ahu","motor","type","pdf1","pdf2","diff","status","page1","page2"); headings={"project":"Proje","ahu":"AHU","motor":"Motor","type":"Tip","pdf1":"PDF1 kW","pdf2":"PDF2 kW","diff":"Fark","status":"Durum","page1":"PDF1","page2":"PDF2"}; widths={"project":220,"ahu":105,"motor":80,"type":110,"pdf1":80,"pdf2":80,"diff":70,"status":125,"page1":60,"page2":60}
        self.tree=ttk.Treeview(result, columns=cols, show="headings")
        for col in cols: self.tree.heading(col,text=headings[col]); self.tree.column(col,width=widths[col],anchor="center")
        self.tree.tag_configure("group_a",background="#f7f7f7"); self.tree.tag_configure("group_b",background="#ffffff"); self.tree.grid(row=0,column=0,sticky="nsew")
        scroll=ttk.Scrollbar(result,orient="vertical",command=self.tree.yview); scroll.grid(row=0,column=1,sticky="ns"); self.tree.configure(yscrollcommand=scroll.set)
        detail_frame=ttk.Frame(result); detail_frame.grid(row=1,column=0,columnspan=2,sticky="ew",pady=(8,0)); detail_frame.columnconfigure(0,weight=1); ttk.Label(detail_frame,text="Sonuç JSON / teknik detay").grid(row=0,column=0,sticky="w")
        self.detail=tk.Text(detail_frame,height=7,wrap="word",font=("Consolas",9)); self.detail.grid(row=1,column=0,sticky="ew"); self.detail.configure(state="disabled")
        log_tab=ttk.Frame(notebook,padding=8); log_tab.columnconfigure(0,weight=1); log_tab.rowconfigure(1,weight=1); notebook.add(log_tab,text="HATA / İŞLEM LOGLARI")
        ttk.Label(log_tab,text=f"Log dosyası: {log_file()}").grid(row=0,column=0,sticky="w",pady=(0,6)); self.log_text=tk.Text(log_tab,wrap="none",font=("Consolas",9)); self.log_text.grid(row=1,column=0,sticky="nsew")
        log_scroll_y=ttk.Scrollbar(log_tab,orient="vertical",command=self.log_text.yview); log_scroll_y.grid(row=1,column=1,sticky="ns"); log_scroll_x=ttk.Scrollbar(log_tab,orient="horizontal",command=self.log_text.xview); log_scroll_x.grid(row=2,column=0,sticky="ew"); self.log_text.configure(yscrollcommand=log_scroll_y.set,xscrollcommand=log_scroll_x.set)
        log_actions=ttk.Frame(log_tab); log_actions.grid(row=3,column=0,sticky="ew",pady=(6,0)); ttk.Button(log_actions,text="LOGLARI YENİLE",command=self.refresh_logs).pack(side="left"); ttk.Button(log_actions,text="LOG DOSYASINI AÇ",command=self.open_log_file).pack(side="left",padx=6); ttk.Button(log_actions,text="LOG KLASÖRÜ",command=self.open_log_directory).pack(side="left"); ttk.Button(log_actions,text="LOGLARI TEMİZLE",command=self.clear_logs).pack(side="left",padx=6)
        actions=ttk.Frame(outer); actions.grid(row=3,column=0,sticky="ew",pady=8); ttk.Button(actions,text="TOPLU ANALİZ",command=self.compare).pack(side="left"); ttk.Button(actions,text="SEÇİMLERİ TEMİZLE",command=self.clear_inputs).pack(side="left",padx=8); ttk.Button(actions,text="JSON KAYDET",command=self.save_json).pack(side="left"); ttk.Button(actions,text="GÜNCELLEME KONTROL ET",command=self.check_updates).pack(side="left",padx=8); self.status=ttk.Label(actions,text="PDF 1 ve PDF 2 tarafına dosya veya klasör ekleyin."); self.status.pack(side="right")

    def _file_box(self,parent,title,column,file_command,folder_command):
        box=ttk.LabelFrame(parent,text=title,padding=8); box.grid(row=0,column=column,sticky="nsew",padx=(0,5) if column==0 else (5,0)); label=ttk.Label(box,text="0 PDF seçildi",width=75); label.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,6)); ttk.Button(box,text="PDF EKLE",command=file_command).grid(row=1,column=0,sticky="w"); ttk.Button(box,text="KLASÖR EKLE",command=folder_command).grid(row=1,column=1,sticky="w",padx=6); box.columnconfigure(0,weight=1); return label

    def _add_inputs(self,target):
        try:
            info("Dosya seçici açılıyor",target=target); paths=filedialog.askopenfilenames(title=f"{target} PDF dosyalarını seç",filetypes=[("PDF files","*.pdf"),("All files","*.*")]); info("Dosya seçici kapandı",target=target,selected_count=len(paths))
            if paths: self._merge_inputs(target,list(paths))
        except Exception as exc: exception("PDF dosya seçme hatası",exc,target=target); messagebox.showerror("Dosya seçme hatası",f"{type(exc).__name__}: {exc}")
    def _add_folder(self,target):
        try:
            info("Klasör seçici açılıyor",target=target); path=filedialog.askdirectory(title=f"{target} PDF klasörünü seç"); info("Klasör seçici kapandı",target=target,selected=path or None)
            if path: self._merge_inputs(target,[path])
        except Exception as exc: exception("PDF klasör seçme hatası",exc,target=target); messagebox.showerror("Klasör seçme hatası",f"{type(exc).__name__}: {exc}")
    def _merge_inputs(self,target,paths):
        try:
            current=self.pdf1_inputs if target=="PDF1" else self.pdf2_inputs; merged=discover_pdfs([item.path for item in current]+list(paths),recursive=True)
            if target=="PDF1": self.pdf1_inputs=merged; self._update_label(self.pdf1_label,merged)
            else: self.pdf2_inputs=merged; self._update_label(self.pdf2_label,merged)
            info("PDF giriş listesi güncellendi",target=target,count=len(merged),paths=[item.path for item in merged]); self.status.configure(text=f"{target}: {len(merged)} PDF hazır"); self.refresh_logs()
        except Exception as exc: exception("PDF girişleri hazırlanamadı",exc,target=target,paths=list(paths)); messagebox.showerror("PDF hazırlama hatası",f"{type(exc).__name__}: {exc}"); self.refresh_logs()
    def _update_label(self,label,items):
        if not items: label.configure(text="0 PDF seçildi"); return
        names=[Path(item.path).name for item in items[:3]]; suffix=" ..." if len(items)>3 else ""; label.configure(text=f"{len(items)} PDF: "+", ".join(names)+suffix)
    def add_pdf1_files(self): self._add_inputs("PDF1")
    def add_pdf1_folder(self): self._add_folder("PDF1")
    def add_pdf2_files(self): self._add_inputs("PDF2")
    def add_pdf2_folder(self): self._add_folder("PDF2")
    def clear_inputs(self):
        self.pdf1_inputs,self.pdf2_inputs=[],[]; self.analysis=None; self._project_approved_variants.clear(); self._ahu_approved_variants.clear(); self._update_label(self.pdf1_label,[]); self._update_label(self.pdf2_label,[]); [self.tree.delete(i) for i in self.tree.get_children()]; self._set_detail(""); self.status.configure(text="Seçimler temizlendi."); info("PDF seçimleri temizlendi"); self.refresh_logs()

    def _read_project_text(self,path):
        try:
            reader=discover_project(path)
            return reader.project_name
        except Exception: return None

    def _project_confirmation_candidates(self):
        pdf1_projects={}; pdf2_projects={}
        for item in self.pdf1_inputs:
            p=self._read_project_text(item.path)
            if p: pdf1_projects.setdefault(normalize_project_name(p),p)
        for item in self.pdf2_inputs:
            p=self._read_project_text(item.path)
            if p: pdf2_projects.setdefault(normalize_project_name(p),p)
        candidates=[]
        for ln,lv in pdf1_projects.items():
            for rn,rv in pdf2_projects.items():
                if ln==rn: continue
                m=match_project_names(lv,rv)
                if m.status=="REVIEW_REQUIRED" or 0.30 <= m.score < 0.85:
                    candidates.append((m.score,lv,rv,ln,rn))
        return sorted(candidates,key=lambda x:x[0],reverse=True)

    def _confirm_projects(self):
        for score,left,right,ln,rn in self._project_confirmation_candidates():
            key=(ln,rn)
            if key in self._project_approved_variants: continue
            answer=messagebox.askyesno("Proje eşleşmesi için onay",f"PDF1 Projesi:\n\n{left}\n\nPDF2 Projesi:\n\n{right}\n\nBunlar aynı proje mi?\n\nBenzerlik: {score:.0%}")
            if not answer:
                warning("Kullanıcı proje eşleşmesini reddetti",left=left,right=right,score=score); return False
            info("Kullanıcı proje eşleşmesini onayladı",left=left,right=right,score=score); self._project_approved_variants.add(key)
        return True

    def _confirm_ahus(self, analysis):
        # Once a variant is approved, reuse the mapping for every AHU with that normalized variant family.
        left_ids=sorted({m.match.left_normalized for m in analysis.ahu_matches if m.match.left_normalized}); right_ids=sorted({m.match.right_normalized for m in analysis.ahu_matches if m.match.right_normalized})
        for lid in left_ids:
            for rid in right_ids:
                if (lid,rid) in self._ahu_approved_variants: continue
                m = __import__('ahu_matching').match_ahu_ids(lid,rid)
                if m.status != "REVIEW_REQUIRED": continue
                answer=messagebox.askyesno("AHU eşleşmesi için onay",f"PDF1 AHU:\n\n{lid}\n\nPDF2 AHU:\n\n{rid}\n\nBunlar aynı AHU mu?\n\nBenzerlik: {m.score:.0%}")
                if not answer:
                    warning("Kullanıcı AHU eşleşmesini reddetti",left=lid,right=rid,score=m.score); return False
                info("Kullanıcı AHU eşleşmesini onayladı",left=lid,right=rid,score=m.score); self._ahu_approved_variants.add((lid,rid))
        return True

    def compare(self):
        if not self.pdf1_inputs or not self.pdf2_inputs:
            messagebox.showwarning("PDF eksik","PDF 1 ve PDF 2 tarafına en az bir PDF veya klasör ekleyin."); return
        try:
            if not self._confirm_projects():
                self.status.configure(text="Proje eşleşmesi kullanıcı tarafından reddedildi."); return
            info("GUI toplu analiz isteği",pdf1_count=len(self.pdf1_inputs),pdf2_count=len(self.pdf2_inputs)); self.status.configure(text="Project → AHU → Motor toplu analizi yapılıyor..."); self.update_idletasks()
            # Analysis is executed after project confirmations. The current engine handles confirmed variants below by retrying AHU matching with approved aliases.
            self.analysis=analyze_batch(self.pdf1_inputs,self.pdf2_inputs)
            if not self._confirm_ahus(self.analysis):
                self.status.configure(text="AHU eşleşmesi kullanıcı tarafından reddedildi."); return
            if self._ahu_approved_variants:
                from batch_analysis import _pair_project_groups
                # Re-run through the engine once with the approved mappings supplied by a compatibility wrapper.
                original_match = __import__('batch_analysis').match_ahu_lists
                try:
                    __import__('batch_analysis').match_ahu_lists=lambda left,right: __import__('ahu_matching').match_ahu_lists(left,right,approved_variants=self._ahu_approved_variants)
                    self.analysis=analyze_batch(self.pdf1_inputs,self.pdf2_inputs)
                finally:
                    __import__('batch_analysis').match_ahu_lists=original_match
            self._render_results()
        except Exception as exc:
            exception("GUI toplu analiz hatası",exc); messagebox.showerror("Analiz hatası",f"{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde."); self.refresh_logs()

    def _render_results(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        comparisons=self.analysis.motor_comparisons; counts={k:0 for k in ["MATCH","MISMATCH","ONLY_IN_PDF1","ONLY_IN_PDF2"]}; group_number=0; current_group=None
        for comparison in comparisons:
            project=comparison.project_name; ahu=normalize_equipment_id(comparison.equipment_id); key=(project,ahu)
            if key != current_group: group_number += 1; current_group=key
            tag="group_a" if group_number%2 else "group_b"
            counts[comparison.status]=counts.get(comparison.status,0)+1
            self.tree.insert("", "end", tags=(tag,), values=(project,ahu,comparison.component_label,comparison.component_type,self._fmt(comparison.pdf1_kw),self._fmt(comparison.pdf2_kw),self._fmt(comparison.difference_kw),comparison.status,comparison.pdf1_page or "-",comparison.pdf2_page or "-"))
        info("GUI sonuç tablosu oluşturuldu",comparisons=len(comparisons),counts=counts,grouped_ahu_count=group_number); self.status.configure(text=f"✓ Proje {len(self.analysis.project_matches)} | AHU {len(self.analysis.ahu_matches)} | Motor {len(self.analysis.motor_comparisons)} | MATCH {counts['MATCH']} | MISMATCH {counts['MISMATCH']} | PDF1 {counts['ONLY_IN_PDF1']} | PDF2 {counts['ONLY_IN_PDF2']}"); self._set_detail(json.dumps(self.analysis.to_dict(),ensure_ascii=False,indent=2)); self.refresh_logs()

    def check_updates(self):
        try: info("Güncelleme butonuna basıldı",current_exe=str(Path(sys.executable).resolve()),version=VERSION); info_data=check_for_update(Path(sys.executable))
        except Exception as exc: exception("GUI güncelleme kontrolü hatası",exc); messagebox.showerror("Güncelleme kontrolü",f"Güncelleme kontrol edilemedi:\n{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde."); self.refresh_logs(); return
        if not info_data["available"]: messagebox.showinfo("Güncelleme",f"Programınız güncel.\nSürüm: {VERSION}"); return
        answer=messagebox.askyesno("Yeni sürüm bulundu",f"Yeni sürüm mevcut: {info_data['version']}\nMevcut sürüm: {VERSION}\n\nŞimdi güncellensin mi?")
        if not answer: return
        try:
            self.status.configure(text="Yeni sürüm indiriliyor..."); self.update_idletasks()
            temp_exe=__import__('updater').download_update(info_data["download_url"],expected_digest=info_data.get("digest"),asset_id=info_data.get("asset_id"),browser_download_url=info_data.get("browser_download_url"),expected_size=info_data.get("asset_size"))
            downloaded_digest=hashlib.sha256(temp_exe.read_bytes()).hexdigest().lower(); info("İndirilen EXE son SHA-256 hesaplandı",sha256=downloaded_digest,expected=info_data.get("digest"),temp=str(temp_exe)); restart_with_update(temp_exe,Path(sys.executable))
        except SystemExit: raise
        except Exception as exc: exception("GUI güncelleme uygulama hatası",exc,version=info_data.get("version"),asset_id=info_data.get("asset_id"),expected_sha256=info_data.get("digest")); messagebox.showerror("Güncelleme",f"Güncelleme başarısız:\n{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde."); self.refresh_logs()
