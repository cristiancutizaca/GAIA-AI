from __future__ import annotations
import json,time,uuid
from pathlib import Path
from .security import redact
class Observability:
 def __init__(self,path:Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
 def event(self,event,*,component='core',severity='info',correlation_id='',session_id='',duration_ms=None,**metadata):
  record={'timestamp':time.time(),'correlation_id':correlation_id or 'corr_'+uuid.uuid4().hex,'session_id':session_id,'component':component,'severity':severity,'event':event,'duration_ms':duration_ms,'metadata':redact(metadata)}
  with self.path.open('a',encoding='utf-8') as f: f.write(json.dumps(record,ensure_ascii=False)+'\n')
  return record
 def read(self,limit=100):
  if not self.path.exists(): return []
  return [json.loads(x) for x in self.path.read_text(encoding='utf-8').splitlines()[-limit:] if x.strip()]
