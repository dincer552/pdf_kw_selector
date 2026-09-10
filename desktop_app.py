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
        self._build()
        self.refresh_logs()
        self._schedule_log_refresh()
        info("GUI hazır", pdf1_count=0, pdf2_count=0)

    def _report_callback_exception(self, exc, value, tb):
        """Tkinter callback errors do not reliably reach sys.excepthook."""
        try:
            import traceback
            exception("YAKALANMAMIŞ GUI CALLBACK HATASI", value, callback_exception_type=getattr(exc, "__name__", str(exc)), traceback_text="".join(traceback.format_exception(exc, value, tb)))
            self.refresh_logs()
        except Exception as log_exc:
            exception("GUI callback hatası loglanırken ikinci hata oluştu", log_exc)

    def _schedule_log_refresh(self):
        try:
            if self.winfo_exists():
                self._log_refresh_job = self.after(1000, self._scheduled_log_refresh)
        except Exception as exc:
            exception("Otomatik log yenileme zamanlayıcısı başlatılamadı", exc)

    def _scheduled_log_refresh(self):
        try:
            self.refresh_logs()
        except Exception as exc:
            exception("Otomatik log yenileme hatası", exc)
        finally:
            self._schedule_log_refresh()

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
        self.pdf1_inputs,self.pdf2_inputs=[],[]; self.analysis=None; self._update_label(self.pdf1_label,[]); self._update_label(self.pdf2_label,[]); [self.tree.delete(i) for i in self.tree.get_children()]; self._set_detail(""); self.status.configure(text="Seçimler temizlendi."); info("PDF seçimleri temizlendi"); self.refresh_logs()

    def compare(self):
        if not self.pdf1_inputs or not self.pdf2_inputs:
            messagebox.showwarning("PDF eksik","PDF 1 ve PDF 2 tarafına en az bir PDF veya klasör ekleyin."); return
        try:
            info("GUI toplu analiz isteği",pdf1_count=len(self.pdf1_inputs),pdf2_count=len(self.pdf2_inputs)); self.status.configure(text="Project → AHU → Motor toplu analizi yapılıyor..."); self.update_idletasks(); self.analysis=analyze_batch(self.pdf1_inputs,self.pdf2_inputs)
            self._render_results()
        except Exception as exc:
            exception("GUI toplu analiz hatası",exc); messagebox.showerror("Analiz hatası",f"{type(exc).__name__}: {exc}"); self.refresh_logs()

    def _render_results(self):
        try:
            for item in self.tree.get_children(): self.tree.delete(item)
            counts={"MATCH":0,"MISMATCH":0,"ONLY_IN_PDF1":0,"ONLY_IN_PDF2":0}; ahu_context={}
            for batch_ahu in self.analysis.ahu_matches:
                left=normalize_equipment_id(batch_ahu.match.left_normalized); right=normalize_equipment_id(batch_ahu.match.right_normalized)
                if left: ahu_context[left]=batch_ahu.project_name or "-"
                if right: ahu_context[right]=batch_ahu.project_name or "-"
            comparisons=list(self.analysis.motor_comparisons); comparisons.sort(key=lambda item:(ahu_context.get(normalize_equipment_id(item.equipment_id),"-").casefold(),normalize_equipment_id(item.equipment_id).casefold(),item.component_type.casefold(),item.component_index))
            previous_group=None; group_number=0
            for comparison in comparisons:
                counts[comparison.status]=counts.get(comparison.status,0)+1; ahu=normalize_equipment_id(comparison.equipment_id); project=ahu_context.get(ahu,"-"); group_key=(project.casefold(),ahu.casefold())
                if group_key!=previous_group: group_number+=1; previous_group=group_key
                tag="group_a" if group_number%2 else "group_b"
                self.tree.insert("","end",tags=(tag,),values=(project,ahu,comparison.component_label,comparison.component_type,self._fmt(comparison.pdf1_kw),self._fmt(comparison.pdf2_kw),self._fmt(comparison.difference_kw),comparison.status,comparison.pdf1_page or "-",comparison.pdf2_page or "-"))
            info("GUI sonuç tablosu oluşturuldu",comparisons=len(comparisons),counts=counts,grouped_ahu_count=group_number); self.status.configure(text=f"✓ Proje {len(self.analysis.project_matches)} | AHU {len(self.analysis.ahu_matches)} | Motor {len(self.analysis.motor_comparisons)} | MATCH {counts['MATCH']} | MISMATCH {counts['MISMATCH']} | PDF1 {counts['ONLY_IN_PDF1']} | PDF2 {counts['ONLY_IN_PDF2']}"); self._set_detail(json.dumps(self.analysis.to_dict(),ensure_ascii=False,indent=2)); self.refresh_logs()
        except Exception as exc: exception("GUI sonuç tablosu oluşturma hatası",exc); messagebox.showerror("Sonuç gösterme hatası",f"{type(exc).__name__}: {exc}"); self.refresh_logs()

    def check_updates(self):
        try: info("Güncelleme butonuna basıldı",current_exe=str(Path(sys.executable).resolve()),version=VERSION); info_data=check_for_update(Path(sys.executable))
        except Exception as exc: exception("GUI güncelleme kontrolü hatası",exc); messagebox.showerror("Güncelleme kontrolü",f"Güncelleme kontrol edilemedi:\n{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde."); self.refresh_logs(); return
        if not info_data["available"]: info("Program güncel",version=VERSION,current_sha256=info_data.get("current_digest")); messagebox.showinfo("Güncelleme",f"Programınız güncel.\nSürüm: {VERSION}"); self.refresh_logs(); return
        info("Yeni sürüm bulundu",version=info_data["version"],remote_sha256=info_data.get("digest"),current_sha256=info_data.get("current_digest"),asset_id=info_data.get("asset_id"),asset_size=info_data.get("asset_size"),download_url=info_data.get("download_url"),browser_download_url=info_data.get("browser_download_url")); answer=messagebox.askyesno("Yeni sürüm bulundu",f"Yeni sürüm mevcut: {info_data['version']}\nMevcut sürüm: {VERSION}\n\nŞimdi güncellensin mi?")
        if not answer: info("Kullanıcı güncellemeyi iptal etti"); self.refresh_logs(); return
        try:
            self.status.configure(text="Yeni sürüm indiriliyor..."); self.update_idletasks(); temp_exe=download_update(info_data["download_url"],expected_digest=info_data.get("digest"),asset_id=info_data.get("asset_id"),browser_download_url=info_data.get("browser_download_url"),expected_size=info_data.get("asset_size")); downloaded_digest=hashlib.sha256(temp_exe.read_bytes()).hexdigest().lower(); info("İndirilen EXE son SHA-256 hesaplandı",sha256=downloaded_digest,expected=info_data.get("digest"),temp=str(temp_exe)); restart_with_update(temp_exe,Path(sys.executable))
        except SystemExit: raise
        except Exception as exc: exception("GUI güncelleme uygulama hatası",exc,version=info_data.get("version"),asset_id=info_data.get("asset_id"),expected_sha256=info_data.get("digest")); messagebox.showerror("Güncelleme",f"Güncelleme başarısız:\n{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde."); self.status.configure(text="Güncelleme başarısız"); self.refresh_logs()

    @staticmethod
    def _fmt(value): return "-" if value is None else f"{value:g}"
    def _set_detail(self,text):
        self.detail.configure(state="normal"); self.detail.delete("1.0","end");
        if text: self.detail.insert("1.0",text)
        self.detail.configure(state="disabled")
    def refresh_logs(self):
        try:
            if not hasattr(self,"log_text"): return
            text=read_log(); self.log_text.delete("1.0","end"); self.log_text.insert("1.0",text); self.log_text.see("end")
        except Exception as exc: exception("GUI log ekranı yenilenemedi",exc)
    def open_log_file(self):
        path=log_file(); path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists(): path.write_text("",encoding="utf-8")
        os.startfile(str(path)) if os.name=="nt" else subprocess.Popen(["xdg-open",str(path)])
    def open_log_directory(self):
        directory=log_directory(); directory.mkdir(parents=True,exist_ok=True); os.startfile(str(directory)) if os.name=="nt" else subprocess.Popen(["xdg-open",str(directory)])
    def clear_logs(self):
        if messagebox.askyesno("Logları temizle","Tüm mevcut uygulama logları temizlensin mi?"): clear_log(); self.refresh_logs()
    def save_json(self):
        if self.analysis is None: messagebox.showwarning("Sonuç yok","Önce TOPLU ANALİZ çalıştırın."); return
        path=filedialog.asksaveasfilename(title="Toplu analizi kaydet",defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path:return
        Path(path).write_text(json.dumps(self.analysis.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8"); messagebox.showinfo("Kaydedildi",f"Sonuç kaydedildi:\n{path}")

if __name__ == "__main__":
    startup(VERSION)
    if len(sys.argv)>=2 and sys.argv[1]=="--apply-update": apply_update(sys.argv[2],sys.argv[3],int(sys.argv[4]))
    else: App().mainloop()
