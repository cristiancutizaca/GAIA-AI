from __future__ import annotations
import hashlib,json,re
from dataclasses import dataclass,asdict
from pathlib import Path
@dataclass
class SkillV2:
 id:str; name:str; version:str; author:str; description:str; instructions:str; required_context:list[str]; tools:list[str]; permissions:list[str]; dependencies:list[str]; quality_checks:list[str]; tests:list[str]; enabled:bool=False
class SkillRegistryV2:
 BUILTINS=('research','browser_research','coding','code_review','debugging','project_analysis','file_management','system_diagnostics','memory_management','documentation','data_analysis')
 def __init__(self): self.items={n:SkillV2(n,n.replace('_',' ').title(),'1.0','GAIA','built-in GAIA skill','',[],[],[],[],[],[],False) for n in self.BUILTINS}
 def validate(self,skill:SkillV2):
  if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}",skill.id): raise ValueError('invalid skill id')
  if any(p.lower() in {'admin','root','sudo','process.execute'} for p in skill.permissions): raise PermissionError('skill cannot self-elevate')
  return True
 def register(self,skill:SkillV2): self.validate(skill); self.items[skill.id]=skill
 def enable(self,id): self.items[id].enabled=True
 def disable(self,id): self.items[id].enabled=False
 def list(self): return [asdict(s) for s in self.items.values()]
 def manifest_hash(self,id): return hashlib.sha256(json.dumps(asdict(self.items[id]),sort_keys=True).encode()).hexdigest()
