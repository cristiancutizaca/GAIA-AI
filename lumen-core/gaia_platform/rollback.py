from __future__ import annotations
import json
from pathlib import Path
class ReleaseManager:
 def __init__(self,root:Path): self.root=Path(root); self.state=self.root/'releases.json'
 def record(self,version,archive):
  data=json.loads(self.state.read_text()) if self.state.exists() else {'current':'','previous':'','releases':{}}; data['previous']=data.get('current',''); data['current']=version; data['releases'][version]=str(archive); self.state.write_text(json.dumps(data,indent=2)); return data
 def rollback_target(self):
  if not self.state.exists(): return ''
  return json.loads(self.state.read_text()).get('previous','')
