from __future__ import annotations
import datetime,uuid
from dataclasses import dataclass,asdict
@dataclass
class Job: id:str; owner:str; kind:str; run_at:str; interval_seconds:int=0; enabled:bool=True; allowed_tools:tuple[str,...]=(); permissions:tuple[str,...]=(); expires_at:str=""; last_run:str=""
class Scheduler:
 def __init__(self): self.jobs={}
 def add(self,owner,run_at,*,kind='one-shot',interval_seconds=0,allowed_tools=(),permissions=(),expires_at=''):
  if not owner: raise ValueError('owner required')
  j=Job('job_'+uuid.uuid4().hex,owner,kind,run_at,int(interval_seconds),True,tuple(allowed_tools),tuple(permissions),expires_at); self.jobs[j.id]=j; return asdict(j)
 def cancel(self,id,owner):
  j=self.jobs.get(id);
  if not j or j.owner!=owner: raise PermissionError('job ownership denied')
  j.enabled=False; return True
 def due(self,now=None):
  now=now or datetime.datetime.now(datetime.timezone.utc).isoformat(); return [asdict(j) for j in self.jobs.values() if j.enabled and j.run_at<=now and (not j.expires_at or now<j.expires_at)]
 def list(self,owner): return [asdict(j) for j in self.jobs.values() if j.owner==owner]
