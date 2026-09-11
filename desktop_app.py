"""Desktop GUI for PDF kW Selector."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app_logger import exception, info, read_log, clear_log, log_file, log_directory, startup
from batch_analysis import analyze_batch
from desktop_inputs import PdfInput, discover_pdfs
from pdf_master_scan import scan_pdfs
from updater import check_for_update, download_update, restart_with_update
from ahu_matching import normalize_equipment_id

VERSION = "v0.5.4"


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"PDF kW Selector {VERSION} — Batch Motor Analysis"); self.geometry("1300x820"); self.minsize(1100, 700)
        self.pdf1_inputs: list[PdfInput] = []; self.pdf2_inputs: list[PdfInput] = []; self.analysis = None; self._analysis_running = False; self._build_ui()

    def _build_ui(self):
        top=ttk.Frame(self,padding=8); top.pack(fill="x"); ttk.Label(top,text="PDF kW SELECTOR",font=("Segoe UI",18,"bold")).pack(side="left"); ttk.Label(top,text=f"{VERSION} • Project → AHU → Motor").pack(side="right",pady=8)
        boxes=ttk.Frame(self,padding=(8,0)); boxes.pack(fill="x"); self.pdf1_label,self.pdf1_box=self._file_box(boxes,"PDF 1 — Seçim / Referans","PDF1"); self.pdf2_label,self.pdf2_box=self._file_box(boxes,"PDF 2 — Elektrik / Üretim","PDF2"); self.pdf1_box.pack(side="left",fill="x",expand=True,padx=(0,5)); self.pdf2_box.pack(side="left",fill="x",expand=True,padx=(5,0))
        tabs=ttk.Notebook(self); tabs.pack(fill="both",expand=True,padx=8,pady=(6,0)); self.tabs=tabs; result_tab=ttk.Frame(tabs); unmatched_tab=ttk.Frame(tabs); log_tab=ttk.Frame(tabs); tabs.add(result_tab,text="SONUÇLAR"); tabs.add(unmatched_tab,text="EŞLEŞMEYEN PDF'LER (0)"); tabs.add(log_tab,text="HATA / İŞLEM LOGLARI")
        cols=("Proje","AHU","Motor","Tip","PDF1 kW","PDF2 kW","Fark","Durum","PDF1","PDF2"); self.tree=ttk.Treeview(result_tab,columns=cols,show="headings")
        for col in cols: self.tree.heading(col,text=col); self.tree.column(col,width=100,anchor="center")
        self.tree.pack(fill="both",expand=True,padx=5,pady=5)
        unmatched_cols=("Taraf","PDF","Proje","AHU","Neden"); self.unmatched_tree=ttk.Treeview(unmatched_tab,columns=unmatched_cols,show="headings")
        widths={"Taraf":90,"PDF":420,"Proje":300,"AHU":260,"Neden":260}
        for col in unmatched_cols: self.unmatched_tree.heading(col,text=col); self.unmatched_tree.column(col,width=widths[col],anchor="w")
        unmatched_scroll=ttk.Scrollbar(unmatched_tab,orient="vertical",command=self.unmatched_tree.yview); self.unmatched_tree.configure(yscrollcommand=unmatched_scroll.set); self.unmatched_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5); unmatched_scroll.pack(side="right",fill="y",padx=(0,5),pady=5)
        detail_frame=ttk.LabelFrame(result_tab,text="Sonuç JSON / teknik detay",padding=5); detail_frame.pack(fill="both",expand=False,padx=8,pady=4); self.detail=tk.Text(detail_frame,height=6,wrap="none"); self.detail.pack(fill="both",expand=True); self.detail.configure(state="disabled")
        self.update_progress=tk.DoubleVar(value=0); self.update_detail=tk.StringVar(value="Güncelleme hazır"); style=ttk.Style(self); style.configure("Update.Horizontal.TProgressbar",troughcolor="#d9d9d9",background="#20a050",lightcolor="#20a050",darkcolor="#16803d")
        progress=ttk.Frame(self,padding=(5,0)); progress.pack(fill="x"); ttk.Label(progress,textvariable=self.update_detail,anchor="e").pack(side="right"); self.update_bar=ttk.Progressbar(progress,style="Update.Horizontal.TProgressbar",variable=self.update_progress,maximum=100,length=360); self.update_bar.pack(side="right",padx=8)
        buttons=ttk.Frame(self,padding=5); buttons.pack(fill="x"); ttk.Button(buttons,text="TOPLU ANALİZ",command=self.compare).pack(side="left",padx=3); ttk.Button(buttons,text="SEÇİMLERİ TEMİZLE",command=self.clear_inputs).pack(side="left",padx=3); ttk.Button(buttons,text="JSON KAYDET",command=self.save_json).pack(side="left",padx=3); ttk.Button(buttons,text="GÜNCELLEME KONTROL ET",command=self.check_updates).pack(side="left",padx=3); self.status=ttk.Label(buttons,text="Hazır",anchor="e"); self.status.pack(side="right")
        self.log_text=tk.Text(log_tab,wrap="none"); self.log_text.pack(fill="both",expand=True,padx=5,pady=5); log_buttons=ttk.Frame(log_tab,padding=5); log_buttons.pack(fill="x"); ttk.Button(log_buttons,text="LOGLARI YENİLE",command=self.refresh_logs).pack(side="left",padx=3); ttk.Button(log_buttons,text="LOG DOSYASINI AÇ",command=self.open_log_file).pack(side="left",padx=3); ttk.Button(log_buttons,text="LOG KLASÖRÜNÜ AÇ",command=self.open_log_directory).pack(side="left",padx=3); ttk.Button(log_buttons,text="LOGLARI TEMİZLE",command=self.clear_logs).pack(side="left",padx=3); self.refresh_logs()

    def _file_box(self,parent,title,side):
        frame=ttk.LabelFrame(parent,text=title,padding=6); label=ttk.Label(frame,text="0 PDF seçildi"); label.pack(side="left",fill="x",expand=True); ttk.Button(frame,text="PDF EKLE",command=lambda:self.add_files(side)).pack(side="right",padx=2); ttk.Button(frame,text="KLASÖR EKLE",command=lambda:self.add_folder(side)).pack(side="right",padx=2); return label,frame
    def add_files(self,side): self._merge_inputs(side,list(filedialog.askopenfilenames(title=f"{side} PDF seç",filetypes=[("PDF","*.pdf")])) )
    def add_folder(self,side):
        path=filedialog.askdirectory(title=f"{side} PDF klasörü seç")
        if path:self._merge_inputs(side,[path])
    def _merge_inputs(self,side,paths):
        discovered=discover_pdfs(paths,recursive=True); target=self.pdf1_inputs if side=="PDF1" else self.pdf2_inputs; known={str(x.path).casefold() for x in target}
        for path in discovered:
            if str(path).casefold() not in known: target.append(path)
        label=self.pdf1_label if side=="PDF1" else self.pdf2_label; names=", ".join(Path(x.path).name for x in target[:3]); label.configure(text=f"{len(target)} PDF: {names}{' ...' if len(target)>3 else ''}"); info("PDF girişleri güncellendi",side=side,count=len(target),paths=[str(x.path) for x in target])
    def clear_inputs(self):
        if self._analysis_running:return
        self.pdf1_inputs.clear(); self.pdf2_inputs.clear(); self.pdf1_label.configure(text="0 PDF seçildi"); self.pdf2_label.configure(text="0 PDF seçildi"); self._clear_unmatched(); info("PDF seçimleri temizlendi")

    def compare(self):
        if self._analysis_running:return
        if not self.pdf1_inputs or not self.pdf2_inputs: messagebox.showwarning("Eksik seçim","PDF1 ve PDF2 tarafına en az birer PDF/klasör ekleyin."); return
        self._analysis_running=True; self.status.configure(text="PDF'ler taranıyor... Arayüz çalışmaya devam edecek."); self.update_idletasks(); pdf1=[str(x.path) for x in self.pdf1_inputs]; pdf2=[str(x.path) for x in self.pdf2_inputs]; threading.Thread(target=self._prepare_analysis,args=(pdf1,pdf2),daemon=True).start()
    def _prepare_analysis(self,pdf1_paths,pdf2_paths):
        try:
            scan_pdfs([(p,"PDF1") for p in pdf1_paths]+[(p,"PDF2") for p in pdf2_paths]); self.after(0,self._run_analysis_after_scan,pdf1_paths,pdf2_paths)
        except Exception as exc:self.after(0,self._analysis_failed,exc)
    def _run_analysis_after_scan(self,pdf1_paths,pdf2_paths):
        try:
            self.status.configure(text="Eşleştirme ve motor analizi yapılıyor..."); self.update_idletasks(); self.analysis=analyze_batch(pdf1_paths,pdf2_paths); self._render_analysis(); self._render_unmatched(); self._post_analysis(); self._analysis_running=False
        except Exception as exc:self._analysis_failed(exc)
    def _post_analysis(self):pass
    def _render_analysis(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        counts={"MATCH":0,"MISMATCH":0,"ONLY_IN_PDF1":0,"ONLY_IN_PDF2":0}; ahu_context={}
        for batch_ahu in self.analysis.ahu_matches:
            left=normalize_equipment_id(batch_ahu.match.left_normalized); right=normalize_equipment_id(batch_ahu.match.right_normalized)
            if left:ahu_context[left]=batch_ahu.project_name or "-"
            if right:ahu_context[right]=batch_ahu.project_name or "-"
        comparisons=list(self.analysis.motor_comparisons); comparisons.sort(key=lambda item:(ahu_context.get(normalize_equipment_id(item.equipment_id),"-").casefold(),normalize_equipment_id(item.equipment_id).casefold(),item.component_type.casefold(),item.component_index)); previous_group=None; group_number=0
        for comparison in comparisons:
            counts[comparison.status]=counts.get(comparison.status,0)+1; ahu=normalize_equipment_id(comparison.equipment_id); project=ahu_context.get(ahu,"-"); group_key=(project.casefold(),ahu.casefold())
            if group_key!=previous_group: group_number+=1; previous_group=group_key
            tag="group_a" if group_number%2 else "group_b"; self.tree.insert("","end",tags=(tag,),values=(project,ahu,comparison.component_label,comparison.component_type,self._fmt(comparison.pdf1_kw),self._fmt(comparison.pdf2_kw),self._fmt(comparison.difference_kw),comparison.status,comparison.pdf1_page or "-",comparison.pdf2_page or "-"))
        info("GUI sonuç tablosu oluşturuldu",comparisons=len(comparisons),counts=counts,grouped_ahu_count=group_number); self.status.configure(text=f"✓ Proje {len(self.analysis.project_matches)} | AHU {len(self.analysis.ahu_matches)} | Motor {len(self.analysis.motor_comparisons)} | MATCH {counts['MATCH']} | MISMATCH {counts['MISMATCH']} | PDF1 {counts['ONLY_IN_PDF1']} | PDF2 {counts['ONLY_IN_PDF2']}"); self._set_detail(json.dumps(self.analysis.to_dict(),ensure_ascii=False,indent=2)); self.refresh_logs()
    def _render_unmatched(self):
        for item in self.unmatched_tree.get_children(): self.unmatched_tree.delete(item)
        matched_paths=set()
        for ahu in self.analysis.ahu_matches:
            matched_paths.update(str(path).casefold() for path in ahu.pdf1_files); matched_paths.update(str(path).casefold() for path in ahu.pdf2_files)
        rows=[]
        for side,documents in (("PDF1",self.analysis.pdf1_documents),("PDF2",self.analysis.pdf2_documents)):
            for document in documents:
                if str(document.path).casefold() in matched_paths: continue
                project=document.project.project_name or "-"; ahus=", ".join(document.equipment) if document.equipment else "-"; reason="AHU eşleşmesine giremedi" if document.equipment else "Ekipman/AHU tespit edilemedi"; rows.append((side,Path(document.path).name,project,ahus,reason,str(document.path)))
        rows.sort(key=lambda row:(row[0],row[1].casefold()))
        for side,pdf,project,ahus,reason,path in rows:self.unmatched_tree.insert("","end",values=(side,pdf,project,ahus,reason),tags=(path,))
        self.tabs.tab(1,text=f"EŞLEŞMEYEN PDF'LER ({len(rows)})")
        info("Eşleşmeyen PDF listesi oluşturuldu",unmatched_count=len(rows),matched_ahu_pdf_count=len(matched_paths),unmatched=[{"side":r[0],"path":r[5],"project":r[2],"ahu":r[3],"reason":r[4]} for r in rows])
    def _clear_unmatched(self):
        if not hasattr(self,"unmatched_tree"): return
        for item in self.unmatched_tree.get_children(): self.unmatched_tree.delete(item)
        if hasattr(self,"tabs"): self.tabs.tab(1,text="EŞLEŞMEYEN PDF'LER (0)")
    def _analysis_failed(self,exc):
        self._analysis_running=False; exception("GUI sonuç tablosu oluşturma hatası",exc); messagebox.showerror("Sonuç gösterme hatası",f"{type(exc).__name__}: {exc}"); self.status.configure(text="Analiz başarısız"); self.refresh_logs()

    def check_updates(self):
        try: info("Güncelleme butonuna basıldı",current_exe=str(Path(sys.executable).resolve()),version=VERSION); info_data=check_for_update(Path(sys.executable), VERSION)
        except Exception as exc: exception("GUI güncelleme kontrolü hatası",exc); messagebox.showerror("Güncelleme kontrolü",f"Güncelleme kontrol edilemedi:\n{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde."); self.refresh_logs(); return
        if not info_data["available"]: info("Program güncel",version=VERSION,current_sha256=info_data.get("current_digest")); messagebox.showinfo("Güncelleme",f"Programınız güncel.\nSürüm: {VERSION}"); self.refresh_logs(); return
        info("Yeni sürüm bulundu",version=info_data["version"],remote_sha256=info_data.get("digest"),current_sha256=info_data.get("current_digest"),asset_id=info_data.get("asset_id"),asset_size=info_data.get("asset_size"),asset_name=info_data.get("asset_name"),download_url=info_data.get("download_url"),browser_download_url=info_data.get("browser_download_url")); answer=messagebox.askyesno("Yeni sürüm bulundu",f"Yeni sürüm mevcut: {info_data['version']}\nMevcut sürüm: {VERSION}\n\nŞimdi güncellensin mi?")
        if not answer: info("Kullanıcı güncellemeyi iptal etti"); self.refresh_logs(); return
        try:
            self.status.configure(text="Yeni sürüm indiriliyor..."); self.update_progress.set(0); self.update_detail.set("İndirme başlıyor..."); self.update_idletasks(); threading.Thread(target=self._download_update_background,args=(info_data,),daemon=True).start()
        except SystemExit: raise
        except Exception as exc: exception("GUI güncelleme uygulama hatası",exc,version=info_data.get("version"),asset_id=info_data.get("asset_id"),expected_sha256=info_data.get("digest"),asset_name=info_data.get("asset_name")); messagebox.showerror("Güncelleme",f"Güncelleme başarısız:\n{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde."); self.status.configure(text="Güncelleme başarısız"); self.refresh_logs()
    def _download_update_background(self, info_data):
        try:
            temp_exe=download_update(info_data["download_url"],expected_digest=info_data.get("digest"),asset_id=info_data.get("asset_id"),browser_download_url=info_data.get("browser_download_url"),expected_size=info_data.get("asset_size"),asset_name=info_data.get("asset_name"),progress_callback=lambda stage,done,total,speed:self.after(0,self._update_progress,stage,done,total,speed))
            self.after(0,self._update_install, temp_exe, info_data)
        except Exception as exc:
            self.after(0,self._update_failed, exc, info_data)
    def _update_progress(self, stage, done, total, speed):
        percent=(done / total * 100) if total else 0
        self.update_progress.set(percent); total_mb=f"{total / 1048576:.1f}" if total else "?"; done_mb=f"{done / 1048576:.1f}"; speed_mb=speed / 1048576
        text=f"İndirme %{percent:.1f} • {done_mb}/{total_mb} MB • {speed_mb:.2f} MB/sn"; self.update_detail.set(text); info("Güncelleme indirme ilerlemesi",percent=round(percent,1),downloaded_mb=round(done/1048576,2),total_mb=round(total/1048576,2) if total else None,speed_mb_s=round(speed_mb,2)); self.refresh_logs()
    def _update_install(self, temp_exe, info_data):
        self.update_progress.set(100); self.update_detail.set("Kurulum hazırlanıyor..."); self.status.configure(text="Güncelleme kuruluyor..."); info("Güncelleme kurulumu başlıyor",temp=str(temp_exe)); self.refresh_logs(); restart_with_update(temp_exe,Path(sys.executable))
    def _update_failed(self, exc, info_data):
        exception("GUI güncelleme uygulama hatası",exc,version=info_data.get("version"),asset_id=info_data.get("asset_id"),asset_name=info_data.get("asset_name")); messagebox.showerror("Güncelleme",f"Güncelleme başarısız:\n{type(exc).__name__}: {exc}\n\nDetay HATA / İŞLEM LOGLARI sekmesinde."); self.status.configure(text="Güncelleme başarısız"); self.update_detail.set("Güncelleme başarısız"); self.refresh_logs()
    @staticmethod
    def _fmt(value): return "-" if value is None else f"{value:g}"
    def _set_detail(self,text):
        self.detail.configure(state="normal"); self.detail.delete("1.0","end");
        if text:self.detail.insert("1.0",text)
        self.detail.configure(state="disabled")
    def refresh_logs(self):
        try:
            if not hasattr(self,"log_text"): return
            text=read_log(); self.log_text.delete("1.0","end"); self.log_text.insert("1.0",text); self.log_text.see("end")
        except Exception as exc: exception("GUI log ekranı yenilenemedi",exc)
    def open_log_file(self):
        path=log_file(); path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_text("",encoding="utf-8")
        os.startfile(str(path)) if os.name=="nt" else subprocess.Popen(["xdg-open",str(path)])
    def open_log_directory(self):
        directory=log_directory(); directory.mkdir(parents=True,exist_ok=True); os.startfile(str(directory)) if os.name=="nt" else subprocess.Popen(["xdg-open",str(directory)])
    def clear_logs(self):
        if messagebox.askyesno("Logları temizle","Tüm mevcut uygulama logları temizlensin mi?"):clear_log(); self.refresh_logs()
    def save_json(self):
        if self.analysis is None:messagebox.showwarning("Sonuç yok","Önce TOPLU ANALİZ çalıştırın."); return
        path=filedialog.asksaveasfilename(title="Toplu analizi kaydet",defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path:return
        Path(path).write_text(json.dumps(self.analysis.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8"); info("Analiz JSON kaydedildi",path=path); self.refresh_logs()
