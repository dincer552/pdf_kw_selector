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
from build_info import BUILD_SHA, BUILD_VERSION

VERSION = BUILD_VERSION
UPDATE_CHECK_INTERVAL_MS = 15 * 60 * 1000


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"PDF kW Selector {VERSION} — Batch Motor Analysis"); self.geometry("1300x820"); self.minsize(1100, 700)
        self.pdf1_inputs: list[PdfInput] = []; self.pdf2_inputs: list[PdfInput] = []; self.analysis = None; self._analysis_running = False; self._update_check_running = False; self._available_update = None; self._build_ui(); self.after(5000, self._schedule_update_check)

    def _build_ui(self):
        top=ttk.Frame(self,padding=8); top.pack(fill="x"); ttk.Label(top,text="PDF kW SELECTOR",font=("Segoe UI",18,"bold")).pack(side="left"); ttk.Label(top,text=f"{VERSION} • Project → AHU → Motor").pack(side="right",pady=8); self.update_check_button=ttk.Button(top,text="↻",width=3,command=self._manual_update_check); self.update_check_button.pack(side="right",padx=(0,8))
        boxes=ttk.Frame(self,padding=(8,0)); boxes.pack(fill="x"); self.pdf1_label,self.pdf1_box=self._file_box(boxes,"Seçim çıktısı","PDF1"); self.pdf2_label,self.pdf2_box=self._file_box(boxes,"Elektrik projesi","PDF2"); self.pdf1_box.pack(side="left",fill="x",expand=True,padx=(0,5)); self.pdf2_box.pack(side="left",fill="x",expand=True,padx=(5,0))
        tabs=ttk.Notebook(self); tabs.pack(fill="both",expand=True,padx=8,pady=(6,0)); self.tabs=tabs; result_tab=ttk.Frame(tabs); unmatched_tab=ttk.Frame(tabs); log_tab=ttk.Frame(tabs); tabs.add(result_tab,text="SONUÇLAR"); tabs.add(unmatched_tab,text="EŞLEŞMEYEN PDF'LER (0)"); tabs.add(log_tab,text="HATA / İŞLEM LOGLARI")
        cols=("Proje","AHU","Motor","Seçim kW","Elektrik P. kW","Durum"); self.tree=ttk.Treeview(result_tab,columns=cols,show="headings")
        for col in cols: self.tree.heading(col,text=col); self.tree.column(col,width=100,anchor="center")
        self.tree.pack(fill="both",expand=True,padx=5,pady=5)
        unmatched_cols=("Taraf","PDF","Proje","AHU","Neden"); self.unmatched_tree=ttk.Treeview(unmatched_tab,columns=unmatched_cols,show="headings")
        widths={"Taraf":90,"PDF":420,"Proje":300,"AHU":260,"Neden":260}
        for col in unmatched_cols: self.unmatched_tree.heading(col,text=col); self.unmatched_tree.column(col,width=widths[col],anchor="w")
        unmatched_scroll=ttk.Scrollbar(unmatched_tab,orient="vertical",command=self.unmatched_tree.yview); self.unmatched_tree.configure(yscrollcommand=unmatched_scroll.set); self.unmatched_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5); unmatched_scroll.pack(side="right",fill="y",padx=(0,5),pady=5)
        detail_frame=ttk.LabelFrame(result_tab,text="Sonuç JSON / teknik detay",padding=5); detail_frame.pack(fill="both",expand=False,padx=8,pady=4); self.detail=tk.Text(detail_frame,height=6,wrap="none"); self.detail.pack(fill="both",expand=True); self.detail.configure(state="disabled")
        self.update_progress=tk.DoubleVar(value=0); self.update_detail=tk.StringVar(value="Güncelleme hazır"); style=ttk.Style(self); style.configure("Update.Horizontal.TProgressbar",troughcolor="#d9d9d9",background="#20a050",lightcolor="#20a050",darkcolor="#16803d")
        progress=ttk.Frame(self,padding=(5,0)); self.update_panel=progress; ttk.Label(progress,textvariable=self.update_detail,anchor="e").pack(side="right"); self.update_bar=ttk.Progressbar(progress,style="Update.Horizontal.TProgressbar",variable=self.update_progress,maximum=100,length=360); self.update_bar.pack(side="right",padx=8)
        buttons=ttk.Frame(self,padding=5); buttons.pack(fill="x"); ttk.Button(buttons,text="ANALİZ",command=self.compare).pack(side="left",padx=3); ttk.Button(buttons,text="SEÇİMLERİ TEMİZLE",command=self.clear_inputs).pack(side="left",padx=3); ttk.Button(buttons,text="JSON KAYDET",command=self.save_json).pack(side="left",padx=3)
        self.update_notice=ttk.Frame(buttons); self.update_notice.pack(side="right",padx=8); self.update_notice_label=ttk.Label(self.update_notice,text="Yeni sürüm mevcut",foreground="#16803d"); self.update_notice_label.pack(side="left",padx=(0,6)); ttk.Button(self.update_notice,text="İNDİR",command=self.download_available_update).pack(side="left"); self.update_notice.pack_forget()
        self.status=ttk.Label(buttons,text="Hazır",anchor="e"); self.status.pack(side="right")
        self.log_text=tk.Text(log_tab,wrap="none"); self.log_text.pack(fill="both",expand=True,padx=5,pady=5); log_buttons=ttk.Frame(log_tab,padding=5); log_buttons.pack(fill="x"); ttk.Button(log_buttons,text="LOGLARI YENİLE",command=self.refresh_logs).pack(side="left",padx=3); ttk.Button(log_buttons,text="LOG DOSYASINI AÇ",command=self.open_log_file).pack(side="left",padx=3); ttk.Button(log_buttons,text="LOG KLASÖRÜNÜ AÇ",command=self.open_log_directory).pack(side="left",padx=3); ttk.Button(log_buttons,text="LOGLARI TEMİZLE",command=self.clear_logs).pack(side="left",padx=3); self.refresh_logs()

    def _manual_update_check(self):
        if self._update_check_running or getattr(self, "_download_running", False):
            return
        self._update_check_running = True
        self._manual_check_active = True
        self._update_check_spinner_index = 0
        self._spin_update_check_button()
        self.status.configure(text="Güncellemeler kontrol ediliyor...")
        self.update_detail.set("Güncel sürüm kontrol ediliyor...")
        self.update_panel.pack(fill="x")
        self.update_idletasks()
        threading.Thread(target=self._check_updates_background, daemon=True).start()

    def _spin_update_check_button(self):
        if not getattr(self, "_manual_check_active", False):
            self.update_check_button.configure(text="↻", state="normal")
            return
        symbols = ("↻", "⟳", "↺", "⟲")
        index = self._update_check_spinner_index % len(symbols)
        self.update_check_button.configure(text=symbols[index], state="disabled")
        self._update_check_spinner_index += 1
        self.after(180, self._spin_update_check_button)

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
        self.pdf1_inputs.clear(); self.pdf2_inputs.clear(); self.pdf1_label.configure(text="0 PDF seçildi"); self.pdf2_label.configure(text="0 PDF seçildi")
        self.analysis = None
        for item in self.tree.get_children(): self.tree.delete(item)
        self._clear_unmatched()
        self._clear_analysis_detail()
        self.status.configure(text="Hazır")
        self.update_progress.set(0)
        self.update_detail.set("Güncelleme hazır")
        self.update_panel.pack_forget()
        self._clear_grouped_results()
        info("PDF seçimleri ve analiz sonuçları temizlendi")

    def _clear_analysis_detail(self):
        self._set_detail("")

    def _clear_grouped_results(self):
        """Hook for grouped result tabs; the log tab must remain untouched."""
        return

    def compare(self):
        if self._analysis_running:return
        if not self.pdf1_inputs or not self.pdf2_inputs: messagebox.showwarning("Eksik seçim","PDF1 ve PDF2 tarafına en az birer PDF/klasör ekleyin."); return
        self._analysis_running=True; self.update_progress.set(0); self.update_detail.set("PDF taraması başlıyor..."); self.update_panel.pack(fill="x"); self.status.configure(text="PDF'ler taranıyor..."); self.update_idletasks(); pdf1=[str(x.path) for x in self.pdf1_inputs]; pdf2=[str(x.path) for x in self.pdf2_inputs]; threading.Thread(target=self._prepare_analysis,args=(pdf1,pdf2),daemon=True).start()
    def _prepare_analysis(self,pdf1_paths,pdf2_paths):
        try:
            scan_pdfs([(p,"PDF1") for p in pdf1_paths]+[(p,"PDF2") for p in pdf2_paths],progress_callback=lambda stage,done,total,detail:self.after(0,self._analysis_progress,stage,done,total,detail)); self.after(0,self._run_analysis_after_scan,pdf1_paths,pdf2_paths)
        except Exception as exc:self.after(0,self._analysis_failed,exc)
    def _run_analysis_after_scan(self,pdf1_paths,pdf2_paths):
        try:
            self.status.configure(text="Eşleştirme ve motor analizi yapılıyor..."); self.update_idletasks(); self.analysis=analyze_batch(pdf1_paths,pdf2_paths,progress_callback=lambda stage,done,total,detail:self.after(0,self._analysis_progress,stage,done,total,detail)); self._render_analysis(); self._render_unmatched(); self._post_analysis(); self._analysis_running=False; self.update_detail.set("Analiz tamamlandı • %100"); self.update_progress.set(100)
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
            tag="group_a" if group_number%2 else "group_b"; self.tree.insert("","end",tags=(tag,),values=(project,ahu,comparison.component_label,self._fmt(comparison.pdf1_kw),self._fmt(comparison.pdf2_kw),comparison.status))
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
        info("Eşleşmeyen PDF listesi oluşturuldu",unmatched_count=len(rows),matched_ahu_pdf_count=len(matched_paths),unmatched=[{"side":r[0],"path":r[5],"project":r[2],"ahu":r[3],"reason":r[4]} for r in rows)
    def _clear_unmatched(self):
        if not hasattr(self,"unmatched_tree"): return
        for item in self.unmatched_tree.get_children(): self.unmatched_tree.delete(item)
        if hasattr(self,"tabs"): self.tabs.tab(1,text="EŞLEŞMEYEN PDF'LER (0)")
    def _analysis_failed(self,exc):
        self._analysis_running=False; exception("GUI sonuç tablosu oluşturma hatası",exc); messagebox.showerror("Sonuç gösterme hatası",f"{type(exc).__name__}: {exc}"); self.status.configure(text="Analiz başarısız"); self.update_detail.set("Analiz başarısız"); self.refresh_logs()
    def _analysis_progress(self, stage, done, total, detail):
        if stage == "scan":
            self.update_detail.set(f"PDF taraması: {done}/{total} • {detail}")
        elif stage == "analysis":
            self.update_detail.set(f"Analiz: {done}/{total} • {detail}")
        else:
            self.update_detail.set(detail)
        if total: self.update_progress.set(min(100.0, (done / total) * 100.0))
        self.update_idletasks()
    def _set_detail(self,text):
        self.detail.configure(state="normal"); self.detail.delete("1.0", "end"); self.detail.insert("1.0",text); self.detail.configure(state="disabled")
    def _fmt(self,value):
        return "-" if value is None else f"{value:g}"
    def _schedule_update_check(self):
        if not self._update_check_running: threading.Thread(target=self._check_updates_background,daemon=True).start()
        self.after(UPDATE_CHECK_INTERVAL_MS,self._schedule_update_check)
    def _check_updates_background(self):
        return
    def download_available_update(self):
        return
    def refresh_logs(self):
        return
    def open_log_file(self):
        return
    def open_log_directory(self):
        return
    def clear_logs(self):
        return
    def save_json(self):
        return
