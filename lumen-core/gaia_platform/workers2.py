from __future__ import annotations
import asyncio,shutil,tempfile,time,subprocess
from pathlib import Path
from dataclasses import dataclass
@dataclass(frozen=True)
class Budget: max_steps:int=20; max_seconds:float=300; max_tool_calls:int=50
class CodingWorkspaceManager:
 def __init__(self,base:Path): self.base=Path(base); self.base.mkdir(parents=True,exist_ok=True)
 def create(self,source:Path):
  target=Path(tempfile.mkdtemp(prefix='gaia-code-',dir=self.base)); shutil.copytree(source,target/'repo',dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git','.venv','data','logs','secrets','tokens')); return target/'repo'
 def diff(self,workspace:Path):
  p=subprocess.run(['git','-C',str(workspace),'diff','--no-ext-diff'],capture_output=True,text=True,timeout=30); return p.stdout if p.returncode==0 else ''
class WorkerManager:
 def __init__(self): self.workers={}
 def register(self,name,worker): self.workers[name]=worker
 async def run(self,name,task,*,budget=Budget()):
  if name not in self.workers: raise KeyError(name)
  started=time.monotonic(); result=await asyncio.wait_for(self.workers[name](task,budget),budget.max_seconds); return {'worker':name,'elapsed':time.monotonic()-started,'result':result}
