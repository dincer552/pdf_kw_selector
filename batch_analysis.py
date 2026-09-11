"""Project -> AHU -> motor batch analysis orchestration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from ahu_matching import AHUMatch, discover_equipment, match_ahu_lists, normalize_equipment_id
from app_logger import debug, exception, info, warning
from motor_compare import MotorComparison, compare_motor_records
from motor_database import build_comparison_key
from pdf_master_scan import build_physical_motor_records, scan_pdf, scan_pdfs
from project_discovery import ProjectDiscovery, normalize_project_name
from project_matching import ProjectMatch, match_discoveries

@dataclass(frozen=True)
class BatchDocument:
    path: str; side: str; project: ProjectDiscovery; equipment: tuple[str, ...]
    def to_dict(self) -> dict:
        data=asdict(self); data["project"]=self.project.to_dict(); return data

@dataclass(frozen=True)
class BatchAHU:
    project_name: str | None; match: AHUMatch; pdf1_files: tuple[str, ...]; pdf2_files: tuple[str, ...]
    def to_dict(self) -> dict: return {"project_name":self.project_name,"match":self.match.to_dict(),"pdf1_files":list(self.pdf1_files),"pdf2_files":list(self.pdf2_files)}

@dataclass(frozen=True)
class BatchAnalysis:
    pdf1_documents: tuple[BatchDocument,...]; pdf2_documents: tuple[BatchDocument,...]; project_matches: tuple[ProjectMatch,...]; ahu_matches: tuple[BatchAHU,...]; motor_comparisons: tuple[MotorComparison,...]
    def to_dict(self)->dict: return {"pdf1_documents":[x.to_dict() for x in self.pdf1_documents],"pdf2_documents":[x.to_dict() for x in self.pdf2_documents],"project_matches":[x.to_dict() for x in self.project_matches],"ahu_matches":[x.to_dict() for x in self.ahu_matches],"motor_comparisons":[x.to_dict() for x in self.motor_comparisons]}

def _discover_documents(paths:list[str|Path],side:str)->list[BatchDocument]:
    documents=[]; seen_paths=set(); valid_paths=[]; info("PDF master keşfi başladı",side=side,input_count=len(paths))
    for raw in paths:
        path=Path(raw).expanduser().resolve(); key=str(path).casefold()
        if key in seen_paths: continue
        seen_paths.add(key)
        if not path.is_file(): warning("PDF dosyası bulunamadı veya dosya değil",side=side,path=str(path)); continue
        valid_paths.append(str(path))
    if valid_paths:
        try: scan_pdfs([(path,side) for path in valid_paths])
        except Exception as exc: exception("Paralel master scan başarısız; cache taraması seri olarak devam edecek",exc,side=side)
    for path in valid_paths:
        try:
            scan=scan_pdf(path,side); document=BatchDocument(path,side,scan.project,scan.equipment.unique_ids()); documents.append(document)
            info("PDF master keşfi tamamlandı",side=side,path=path,pages=scan.page_count,project=scan.project.project_name,equipment=list(document.equipment),motor_count=len(scan.pdf1_motors if side=="PDF1" else scan.pdf2_motors),ebm_pages=list(scan.pdf1_ebm_pages))
        except Exception as exc: exception("PDF keşfi başarısız; dosya analizin dışında bırakıldı",exc,side=side,path=path)
    return documents

def _group_documents(documents):
    grouped={}
    for document in documents:
        key=document.project.project_name_normalized or f"__UNRESOLVED__:{document.path}"; grouped.setdefault(key,[]).append(document)
    return grouped

def _files_for_ahu(documents,normalized_ahu):
    if not normalized_ahu:return ()
    target=normalize_equipment_id(normalized_ahu); return tuple(document.path for document in documents if target in {normalize_equipment_id(x) for x in document.equipment})

def _dedupe_motor_records(records):
    unique={}
    for record in records:unique.setdefault(build_comparison_key(record),record)
    return list(unique.values())

def _extract_side_motors(paths,side,target_ahu):
    target=normalize_equipment_id(target_ahu) if target_ahu else None; records=[]
    for path in paths:
        try:records.extend(build_physical_motor_records(scan_pdf(path,side)))
        except Exception as exc:exception("Motor keşfi başarısız",exc,side=side,path=path,ahu=target)
    records=_dedupe_motor_records(records); return records if target is None else [r for r in records if normalize_equipment_id(r.equipment_id)==target]

def _pair_project_groups(left_groups,right_groups):
    """Use exact project names/AHU overlap first; fuzzy scoring is last resort."""
    candidates=[]; used_l=set(); used_r=set(); right_ahu_index={}
    info("PROJECT MATCH DEBUG: gruplar hazır",left_groups={k:sorted(_ahu_set(v)) for k,v in left_groups.items()},right_groups={k:sorted(_ahu_set(v)) for k,v in right_groups.items()})
    for right_key,right_docs in right_groups.items():
        for ahu in _ahu_set(right_docs): right_ahu_index.setdefault(ahu,[]).append(right_key)
    info("PROJECT MATCH DEBUG: PDF2 AHU index",ahu_index=right_ahu_index)
    for left_key,left_docs in left_groups.items():
        if not left_key or left_key.startswith("__UNRESOLVED__:"): continue
        right=right_groups.get(left_key)
        if right is None: continue
        match=match_discoveries(left_docs[0].project,right[0].project); info("PROJECT MATCH DEBUG: exact aday",left=left_key,right=left_key,score=match.score,status=match.status,reason=match.reason); candidates.append((match.score,left_key,left_key,match))
    for left_key,left_docs in left_groups.items():
        if left_key.startswith("__UNRESOLVED__:"): continue
        matches=set()
        for ahu in _ahu_set(left_docs): matches.update(right_ahu_index.get(ahu,()))
        matches -= used_r
        info("PROJECT MATCH DEBUG: AHU overlap adayı",left=left_key,left_ahus=sorted(_ahu_set(left_docs)),candidate_right_groups=sorted(matches),overlap={k:sorted(_ahu_set(left_docs)&_ahu_set(right_groups[k])) for k in matches})
        if len(matches)!=1: continue
        right_key=next(iter(matches)); match=match_discoveries(left_docs[0].project,right_groups[right_key][0].project); info("PROJECT MATCH DEBUG: AHU ile proje çifti",left=left_key,right=right_key,score=match.score,status=match.status,reason=match.reason); candidates.append((match.score,left_key,right_key,match))
    for left_key,left_docs in left_groups.items():
        if left_key.startswith("__UNRESOLVED__:") or not left_key: continue
        for right_key,right_docs in right_groups.items():
            if right_key in used_r or right_key.startswith("__UNRESOLVED__:") or not right_key: continue
            try:
                match=match_discoveries(left_docs[0].project,right_docs[0].project); info("PROJECT MATCH DEBUG: fuzzy aday",left=left_key,right=right_key,score=match.score,status=match.status,reason=match.reason); candidates.append((match.score,left_key,right_key,match))
            except Exception as exc: exception("Proje eşleşme adayı hesaplanamadı",exc,left=left_docs[0].project.project_name,right=right_docs[0].project.project_name)
    output=[]
    for _,lk,rk,m in sorted(candidates,reverse=True,key=lambda x:x[0]):
        if lk in used_l or rk in used_r or m.status=="NO_MATCH": info("PROJECT MATCH DEBUG: aday elendi",left=lk,right=rk,score=m.score,status=m.status,reason=m.reason); continue
        used_l.add(lk);used_r.add(rk);output.append((lk,rk,m)); info("PROJECT MATCH DEBUG: FINAL EŞLEŞME",left=lk,right=rk,score=m.score,status=m.status,reason=m.reason)
    info("PROJECT MATCH DEBUG: sonuç",match_count=len(output),unmatched_left=[k for k in left_groups if k not in used_l],unmatched_right=[k for k in right_groups if k not in used_r])
    return output

def _ahu_set(documents): return {normalize_equipment_id(e) for d in documents for e in d.equipment if normalize_equipment_id(e)}

def _best_project_for_document(document,left_groups):
    right_ahus=_ahu_set([document]); candidates=[]
    if not right_ahus:return None
    for key,docs in left_groups.items():
        project=docs[0].project
        if not project.project_name_normalized:continue
        overlap=right_ahus&_ahu_set(docs)
        if overlap:candidates.append((len(overlap)/len(right_ahus),len(overlap),key,overlap))
    if not candidates:return None
    candidates.sort(key=lambda x:(x[0],x[1]),reverse=True);best=candidates[0]
    if len(candidates)>1 and best[:2]==candidates[1][:2]:return None
    return best if best[0]>=.50 else None

def _infer_unresolved_right_documents(left_groups,right_documents,already_matched_paths):
    assignments={}
    for document in right_documents:
        if document.project.project_name_normalized or document.path in already_matched_paths:continue
        best=_best_project_for_document(document,left_groups)
        if best:assignments.setdefault(best[2],[]).append(document)
    return assignments

def _is_ebm_pdf1(paths):
    for path in paths:
        scan=scan_pdf(path,"PDF1")
        if scan.pdf1_ebm_pages:
            return True
    return False

def analyze_batch(pdf1_paths,pdf2_paths,progress_callback=None):
    def progress(stage, current, total, detail):
        if progress_callback:
            progress_callback(stage, current, total, detail)
    left_docs=_discover_documents(pdf1_paths,"PDF1");right_docs=_discover_documents(pdf2_paths,"PDF2");left_groups=_group_documents(left_docs);right_groups=_group_documents(right_docs)
    progress("matching",1,5,"PDF belgeleri gruplandı")
    named_pairs=_pair_project_groups(left_groups,right_groups);used_right_paths=set();project_pair_docs={}
    progress("matching",2,5,"Projeler eşleştiriliyor")
    for lk,rk,m in named_pairs:
        rg=right_groups[rk];used_right_paths.update(d.path for d in rg);project_pair_docs[lk]=(m,list(left_groups[lk]),list(rg))
    for lk,docs in _infer_unresolved_right_documents(left_groups,right_docs,used_right_paths).items():
        if lk in project_pair_docs:
            m,lg,rg=project_pair_docs[lk];rg.extend(docs);project_pair_docs[lk]=(m,lg,rg);continue
        lg=left_groups[lk];p=lg[0].project;right_name=docs[0].project.project_name if docs[0].project.project_name else None;overlap_total=sum(len(_ahu_set([d])&_ahu_set(lg)) for d in docs)
        project_pair_docs[lk]=(ProjectMatch(p.project_name,right_name,p.project_name_normalized,normalize_project_name(right_name or "") or None,round(overlap_total/max(1,sum(len(_ahu_set([d])) for d in docs)),4),"INFERRED_FROM_AHU","PDF2 project name is unavailable; project was inferred from AHU references",p.project_source,None),list(lg),list(docs))
    project_matches=[];ahu_batches=[];motor_comparisons=[]
    progress("matching",3,5,"AHU ekipmanları eşleştiriliyor")
    for pm,lg,rg in project_pair_docs.values():
        project_matches.append(pm);left_equipment=[];right_equipment=[]
        for d in lg:left_equipment.extend(scan_pdf(d.path,d.side).equipment.equipment_ids)
        for d in rg:right_equipment.extend(scan_pdf(d.path,d.side).equipment.equipment_ids)
        info("AHU MATCH DEBUG: proje grubu",project=pm.left_name,pdf1_files=[d.path for d in lg],pdf2_files=[d.path for d in rg],pdf1_ahus=sorted({item.normalized for item in left_equipment}),pdf2_ahus=sorted({item.normalized for item in right_equipment}))
        for am in match_ahu_lists(left_equipment,right_equipment):
            lf=_files_for_ahu(lg,am.left_normalized);rf=_files_for_ahu(rg,am.right_normalized); info("AHU MATCH DEBUG: aday",project=pm.left_name,left=am.left_normalized,right=am.right_normalized,score=am.score,status=am.status,reason=getattr(am,"reason",None),pdf1_files=list(lf),pdf2_files=list(rf)); ahu_batches.append(BatchAHU(pm.left_name,am,lf,rf))
            if am.status not in {"EXACT","NORMALIZED_MATCH","USER_APPROVED"}:continue
            if _is_ebm_pdf1(lf):
                info("EBM-Papst PDF1 motor karşılaştırması atlandı; AHU eşleşmesi korunuyor",project=pm.left_name,ahu=am.left_normalized,pdf1_files=list(lf),pdf2_files=list(rf))
                continue
            try:motor_comparisons.extend(compare_motor_records(_extract_side_motors(lf,"PDF1",am.left_normalized),_extract_side_motors(rf,"PDF2",am.right_normalized)))
            except Exception as exc:exception("Motor karşılaştırması başarısız",exc,project=pm.left_name,ahu=am.left_normalized)
    progress("matching",4,5,"Motor sonuçları oluşturuluyor")
    info("AHU MATCH DEBUG: final",project_matches=len(project_matches),ahu_matches=len(ahu_batches),motor_comparisons=len(motor_comparisons))
    progress("matching",5,5,"Analiz tamamlandı")
    return BatchAnalysis(tuple(left_docs),tuple(right_docs),tuple(project_matches),tuple(ahu_batches),tuple(motor_comparisons))