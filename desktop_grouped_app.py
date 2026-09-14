"""Grouped desktop entry point for PDF kW Selector."""
from __future__ import annotations
from pathlib import Path
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
        super().__init__(); self._analysis_started_at=None; self._build_ebm_tab(); self.tabs.tab(0,text="DANFOS"); self.tabs.insert(1,self.ebm_tab); self.unmatched_tab_index=lambda:2; self.tree.tag_configure("mismatch",background="#ffb3b3",foreground="#000000"); install_pdf_drop_targets(self,self.pdf1_label.master,self.pdf2_label.master)
    def _build_ebm_tab(self):
        tab=ttk.Frame(self.tabs); self.tabs.add(tab,text="EBM-PAPST (0)"); cols=("Proje","AHU","Seçim çıktısı","Elektrik p.","Durum"); self.ebm_tree=ttk.Treeview(tab,columns=cols,show="headings"); widths={"Proje":300,"AHU":120,"Seçim çıktısı":300,"Elektrik p.":420,"Durum":260}
        for col in cols:self.ebm_tree.heading(col,text=col);self.ebm_tree.column(col,width=widths[col],anchor="w")
        scroll=ttk.Scrollbar(tab,orient="vertical",command=self.ebm_tree.yview);self.ebm_tree.configure(yscrollcommand=scroll.set);self.ebm_tree.pack(side="left",fill="both",expand=True,padx=(5,0),pady=5);scroll.pack(side="right",fill="y",padx=(0,5),pady=5);self.ebm_tab=tab
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
        super()._render_unmatched(); self.tabs.tab(self.unmatched_tab_index(),text=f"EŞLEŞMEYEN PDF'LER ({len(self.unmatched_tree.get_children())})")
    def _clear_grouped_results(self):
        for item in self.ebm_tree.get_children(): self.ebm_tree.delete(item)
        self.tabs.tab(0,text="DANFOS (0)")
        self.tabs.tab(self.ebm_tab,text="EBM-PAPST (0)")
    def _post_analysis(self):
        try:
            self._render_ebm(); rows=[self.tree.item(i,"values") for i in self.tree.get_children()]; grouped=group_result_rows(rows)
            for i in self.tree.get_children():self.tree.delete(i)
            for row in grouped:self.tree.insert("","end",values=row,tags=("mismatch",) if len(row)>5 and str(row[5]).strip()=="MISMATCH" else ())
            matched=set()
            for ahu in self.analysis.ahu_matches:
                if getattr(ahu.match,"status","") in {"EXACT","NORMALIZED_MATCH","USER_APPROVED"}:
                    for value in (ahu.match.left_normalized,ahu.match.right_normalized):
                        if value:matched.add(value)
            elapsed=time.perf_counter()-self._analysis_started_at if self._analysis_started_at is not None else None
            self.tabs.tab(0,text=f"DANFOS ({len(matched)})")
            if elapsed is not None:
                self.status.configure(text=f"Analiz süresi: {elapsed:.2f} sn | AHU {len(self.analysis.ahu_matches)} | Motor {len(self.analysis.motor_comparisons)} | MATCH/MISMATCH sonuçları hazır")
                info("Toplu analiz tamamlandı",elapsed_seconds=round(elapsed,3),ahu_count=len(self.analysis.ahu_matches),motor_count=len(self.analysis.motor_comparisons))
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
