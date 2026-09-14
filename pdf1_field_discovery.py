from __future__ import annotations
import inspect,re
from pathlib import Path
import fitz
from ahu_matching import AHUDiscovery,EquipmentOccurrence,normalize_equipment_id
from project_discovery import ProjectCandidate,ProjectDiscovery,normalize_project_name
R=re.compile(r'\b(?:[A-Z0-9]+[_ -]+AHU[_ -]?[A-Z]?\d+(?:\.\d+)?|HKS[_ -]?\d+|KS[_ -]?[A-Z]?\d+(?:\.\d+)?|SS[_ -]?[A-Z]?\d+(?:\.\d+)?|PW[_ -]?\d+(?:\.\d+)?|AHU(?:[_ -]+[A-Z0-9_.-]+|\d[A-Z0-9_.-]*))\b',re.I)
STOP={'creation','revision','designer','model','airflow','rate'}
def _path(path):
 if path:return Path(path)
 f=inspect.currentframe().f_back
 for _ in range(3):
  if f:
   p=f.f_locals.get('resolved') or f.f_locals.get('path')
   if p:return Path(p)
  f=f.f_back
 return None
def _row(words,y,tol=2.0):
 return sorted((w for w in words if abs(((w[1]+w[3])/2)-y)<=tol),key=lambda w:w[0])
def _fields(path):
 projects=[];units=[];d=fitz.open(str(path))
 try:
  for pn,page in enumerate(d,1):
   words=page.get_text('words')
   for w in words:
    t=w[4].strip().casefold(); y=(w[1]+w[3])/2
    if t=='project':
     vals=[]
     for x in _row(words,y):
      if x[0]<=w[2]+1:continue
      xt=x[4].strip()
      if xt.casefold() in {'creation','revision'}:break
      vals.append(xt)
     v=' '.join(vals).strip();n=normalize_project_name(v)
     if v and len(n.split())>=2:projects.append(ProjectCandidate(v,n,'project_coordinates',pn,'HIGH'))
    elif t=='unit':
     row=_row(words,y)
     ref=next((x for x in row if x[0]>w[2] and x[4].strip().casefold()=='reference'),None)
     if not ref:continue
     for x in row:
      if x[0]<=ref[2]+1:continue
      m=R.search(x[4])
      if m:
       raw=m.group(0).strip(' .,:;)]}');n=normalize_equipment_id(raw)
       if n:units.append(EquipmentOccurrence(raw,n,pn,'unit_reference_coordinates'))
       break
 finally:d.close()
 return projects,units
def discover_pdf1_project(pages,path=None):
 path=_path(path)
 if not path:return ProjectDiscovery(None,None,None,None,'REVIEW',())
 a,_=_fields(path);seen=set();q=[]
 for x in a:
  if x.normalized not in seen:seen.add(x.normalized);q.append(x)
 if not q:return ProjectDiscovery(None,None,None,None,'REVIEW',())
 x=q[0];return ProjectDiscovery(x.value,x.normalized,x.source,x.page,x.confidence,tuple(q))
def discover_pdf1_unit_reference(pages,path=None):
 path=_path(path)
 if not path:return AHUDiscovery(())
 _,a=_fields(path);seen=set();q=[]
 for x in a:
  k=(x.normalized,x.page)
  if k not in seen:seen.add(k);q.append(x)
 return AHUDiscovery(tuple(q))
