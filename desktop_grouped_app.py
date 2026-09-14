"""Grouped desktop entry point for PDF kW Selector."""
from __future__ import annotations
from pathlib import Path
import re
import sys
import time
from tkinter import ttk
import desktop_app as desktop_module
from app_logger import exception, info, startup
from desktop_app import App as BaseApp, VERSION
from drag_drop import install_pdf_drop_targets
from result_grouping import group_result_rows
from updater import apply_update
from confirmation_workflow import analyze_with_confirmations
from pdf_master_scan import scan_pdf

def _path_strings(items): return [str(getattr(item,"path",item)) for item in (items or [])]
def _confirmed_analyze(pdf1_inputs,pdf2_inputs,progress_callback=None):
    p1,p2=_path_strings(pdf1_inputs),_path_strings(pdf2_inputs); info("Onaylı analiz girişleri normalize edildi",pdf1_count=len(p1),pdf2_count=len(p2)); return analyze_with_confirmations(p1,p2,progress_callback=progress_callback)
desktop_module.analyze_batch=_confirmed_analyze

class GroupedApp(BaseApp):
    def __init__(self):
        super().__init__(); self._analysis_started_at=None; self._build_ebm_tab(); self._build_voclean_tab(); self._build_sysreco_tab(); self.tabs.tab(0,text="DANFOS"); self.tabs.insert(1,self.ebm_tab); self.tabs.insert(2,self.voclean_tab); self.tabs.insert(3,self.sysreco_tab); self.unmatched_tab_index=lambda:4; self.tree.tag_configure("mismatch",background="#ffb3b3",foreground="#000000"); install_pdf_drop_targets(self,self.pdf1_label.master,self.pdf2_label.master)
    def _build_ebm_tab(self):
        tab=ttk.Frame(self.tabs); self.tabs.add(tab,text="EBM-PAPST (0)"); cols=("Proje","AHU","Seçim çıktısı","Elektrik p.","Durum"); self.ebm_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":300,"AHU":120,"Seçim çıktısı":300,"Elektrik p.":420,"Durum":260}
        for col in cols:self.ebm_tree.heading(col,text=col);self.ebm_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=self.ebm_tree.yview);self.ebm_tree.configure(yscrollcommand=scroll.set);self.ebm_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.ebm_tab=tab
    def _build_voclean_tab(self):
        tab=ttk.Frame(self.tabs); self.tabs.add(tab,text="VOCLEAN (0)"); cols=("Proje","PDF1","VOClean kW","PDF1 Sayfa","PDF2","AHU","Durum"); self.voclean_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":260,"PDF1":300,"VOClean kW":100,"PDF1 Sayfa":90,"PDF2":300,"AHU":180,"Durum":280}
        for col in cols:self.voclean_tree.heading(col,text=col);self.voclean_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=self.voclean_tree.yview);self.voclean_tree.configure(yscrollcommand=scroll.set);self.voclean_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.voclean_tab=tab
    def _build_sysreco_tab(self):
        tab=ttk.Frame(self.tabs); self.tabs.add(tab,text="SYSRECO (0)"); cols=("Proje","AHU","PDF","SysReco Model"); self.sysreco_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":320,"AHU":180,"PDF":420,"SysReco Model":180}
        for col in cols:self.sysreco_tree.heading(col,text=col);self.sysreco_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=self.sysreco_tree.yview);self.sysreco_tree.configure(yscrollcommand=scroll.set);self.sysreco_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.sysreco_tab=tab
    @staticmethod
    def _voclean_power_prefix(value_kw): return f"BA{int(round(float(value_kw)*100)):03d}-"
    @staticmethod
    def _is_voclean_text(text): return bool(re.search(r"\bVOC\s*LEAN\b",text or "",re.I))
    def _is_voclean_document(self,document,side=None):
        # PDF1 VOCLEAN must be identified from the actual PDF content.
        # PDF2 keeps the project-name fallback for known VOCLEAN records.
        if side == "PDF2": return "voclean" in str(getattr(getattr(document,"project",None),"project_name","") or "").casefold()
        scan=scan_pdf(document.path,"PDF1")
        return any(self._is_voclean_text(text) for text in scan.page_texts)
    @staticmethod
    def _is_sysreco_text(text): return bool(re.search(r"\bSysReco\b",text or "",re.I))
    @staticmethod
    def _sysreco_models(text): return list(dict.fromkeys(m.group(0).strip() for m in re.finditer(r"\bSysReco\s+FX\d+\b",text or "",re.I)))
    def _sysreco_documents(self):
        result=[]
        for document in self.analysis.pdf1_documents:
            scan=scan_pdf(document.path,"PDF1")
            full_text="\n".join(scan.page_texts)
            if self._is_sysreco_text(full_text): result.append((document,full_text))
        return result
    def _render_voclean(self):
        for item in self.voclean_tree.get_children(): self.voclean_tree.delete(item)
        rows=[]
        for document in self.analysis.pdf1_documents:
            scan=scan_pdf(document.path,"PDF1"); voc_pages=[n for n,text in enumerate(scan.page_texts,1) if self._is_voclean_text(text)]
            if not voc_pages: continue
            motor_results=list(scan.pdf1_motors)
            if not motor_results:
                rows.append((document.project.project_name or "-",Path(document.path).name,"-","-","-","-","VOClean bulundu; Plug fan kW bulunamadı")); continue
            for motor in motor_results:
                if motor.value_kw is None: continue
                prefix=self._voclean_power_prefix(motor.value_kw).upper(); matches=[]
                for pdf2_document in self.analysis.pdf2_documents:
                    for ahu in pdf2_document.equipment:
                        ahu_text=str(ahu).strip()
                        if ahu_text.upper().startswith(prefix): matches.append((pdf2_document,ahu_text))
                if matches:
                    for pdf2_document,ahu_text in matches: rows.append((document.project.project_name or "-",Path(document.path).name,f"{motor.value_kw:g}",str(motor.page_number),Path(pdf2_document.path).name,ahu_text,f"BA kodu eşleşti ({prefix[:-1]})"))
                else:
                    rows.append((document.project.project_name or "-",Path(document.path).name,f"{motor.value_kw:g}",str(motor.page_number),"-","-",f"PDF2 AHU eşleşmesi yok; beklenen {prefix[:-1]}-xxxxx"))
        rows.sort(key=lambda r:(str(r[0]).casefold(),str(r[1]).casefold(),str(r[3]),str(r[5]).casefold()))
        for row in rows:self.voclean_tree.insert("","end",values=row)
        self.tabs.tab(self.voclean_tab,text=f"VOCLEAN ({len(rows)})"); info("VOClean sonuçları oluşturuldu",row_count=len(rows))
    def _render_sysreco(self):
        for item in self.sysreco_tree.get_children(): self.sysreco_tree.delete(item)
        rows=[]
        for document,full_text in self._sysreco_documents():
            models=self._sysreco_models(full_text) or ["SysReco modeli bulunamadı"]
            for model in models:
                rows.append((document.project.project_name or "-", ", ".join(str(value) for value in document.equipment) if document.equipment else "-", Path(document.path).name, model))
        rows.sort(key=lambda r:(str(r[0]).casefold(),str(r[1]).casefold(),str(r[2]).casefold(),str(r[3]).casefold()))
        for row in rows:self.sysreco_tree.insert("","end",values=row)
        self.tabs.tab(self.sysreco_tab,text=f"SYSRECO ({len(rows)})"); info("SysReco sonuçları oluşturuldu",row_count=len(rows))
    def _render_ebm(self):
        for item in self.ebm_tree.get_children():self.ebm_tree.delete(item)
        rows=[]
        for document in self.analysis.pdf1_documents:
            scan=scan_pdf(document.path,"PDF1")
            if not scan.pdf1_ebm_pages:continue
            matching=[]
            for ahu in self.analysis.ahu_matches:
                if str(document.path).casefold() in {str(p).casefold() for p in ahu.pdf1_files}:matching.extend(ahu.pdf2_files)
            pdf2=", ".join(Path(p).name for p in dict.fromkeys(matching)) or "-"; status="PDF2 AHU eşleşti; motor kW karşılaştırması yapılmadı" if matching else "PDF2 AHU eşleşmesi yok"
            for ahu_id in tuple(document.equipment) or ("-",):rows.append((document.project.project_name or "-",ahu_id or "-",Path(document.path).name,pdf2,status))
        rows.sort(key=lambda r:(str(r[1]).casefold(),str(r[2]).casefold(),str(r[0]).casefold()))
        for row in rows:self.ebm_tree.insert("","end",values=row)
        self.tabs.tab(self.ebm_tab,text=f"EBM-PAPST ({len(rows)})")
    def _render_unmatched(self):
        for item in self.unmatched_tree.get_children():self.unmatched_tree.delete(item)
        matched_paths=set(); accepted_statuses={"EXACT","NORMALIZED_MATCH","USER_APPROVED"}; sysreco_paths={str(document.path).casefold() for document,_ in self._sysreco_documents()}; vocclean_paths={str(document.path).casefold() for document in self.analysis.pdf1_documents if self._is_voclean_document(document,"PDF1")}
        for ahu in self.analysis.ahu_matches:
            if getattr(ahu.match,"status","") not in accepted_statuses:continue
            matched_paths.update(str(path).casefold() for path in ahu.pdf1_files); matched_paths.update(str(path).casefold() for path in ahu.pdf2_files)
        rows=[]
        for side,documents in (("PDF1",self.analysis.pdf1_documents),("PDF2",self.analysis.pdf2_documents)):
            for document in documents:
                document_path=str(document.path).casefold()
                if document_path in matched_paths or document_path in sysreco_paths:continue
                if side == "PDF1" and document_path in vocclean_paths:continue
                if side == "PDF2" and self._is_voclean_document(document,"PDF2"):continue
                project=document.project.project_name or "-"; ahus=", ".join(str(value) for value in document.equipment if str(value).strip()) if document.equipment else "-"; reason="AHU eşleşmesine giremedi" if document.equipment else "Ekipman/AHU tespit edilemedi"; rows.append((side,Path(document.path).name,project,ahus,reason,str(document.path)))
        rows.sort(key=lambda row:(row[0],row[1].casefold()))
        for side,pdf,project,ahus,reason,path in rows:self.unmatched_tree.insert("","end",values=(side,pdf,project,ahus,reason),tags=(path,))
        self.tabs.tab(self.unmatched_tab_index(),text=f"EŞLEŞMEYEN PDF'LER ({len(rows)})")
    def _clear_grouped_results(self):
        for item in self.ebm_tree.get_children():self.ebm_tree.delete(item)
        for item in self.voclean_tree.get_children():self.voclean_tree.delete(item)
        for item in self.sysreco_tree.get_children():self.sysreco_tree.delete(item)
        self.tabs.tab(0,text="DANFOS (0)"); self.tabs.tab(self.ebm_tab,text="EBM-PAPST (0)"); self.tabs.tab(self.voclean_tab,text="VOCLEAN (0)"); self.tabs.tab(self.sysreco_tab,text="SYSRECO (0)")
    def _post_analysis(self):
        try:
            self._render_ebm(); self._render_voclean(); self._render_sysreco(); rows=[self.tree.item(i,"values") for i in self.tree.get_children()]; grouped=group_result_rows(rows)
            for i in self.tree.get_children():self.tree.delete(i)
            for row in grouped:self.tree.insert("","end",values=row,tags=("mismatch",) if len(row)>5 and str(row[5]).strip()=="MISMATCH" else ())
            elapsed=time.perf_counter()-self._analysis_started_at if self._analysis_started_at is not None else None
            danfos_count=len(self.tree.get_children()); self.tabs.tab(0,text=f"DANFOS ({danfos_count})")
            if elapsed is not None:self.status.configure(text=f"Analiz süresi: {elapsed:.2f} sn | AHU {len(self.analysis.ahu_matches)} | Motor {len(self.analysis.motor_comparisons)} | MATCH/MISMATCH sonuçları hazır"); info("Toplu analiz tamamlandı",elapsed_seconds=round(elapsed,3),ahu_count=len(self.analysis.ahu_matches),motor_count=len(self.analysis.motor_comparisons),danfos_row_count=danfos_count)
            self.refresh_logs()
        except Exception as exc:exception("Project/AHU sonuç gruplama hatası",exc);self.refresh_logs()
    def compare(self):
        self._analysis_started_at=time.perf_counter(); super().compare()

if __name__=="__main__":
    startup(VERSION)
    if len(sys.argv)>=2 and sys.argv[1]=="--apply-update":
        try:apply_update(sys.argv[2],sys.argv[3],int(sys.argv[4]))
        except Exception as exc:exception("Updater modu başarısız",exc,argv=sys.argv);raise
    else:
        try:GroupedApp().mainloop()
        except Exception as exc:exception("GUI ana döngüsü beklenmedik hata ile kapandı",exc);raise
