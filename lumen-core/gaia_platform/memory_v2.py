from __future__ import annotations
import hashlib,sqlite3,datetime,json,re
from pathlib import Path
from typing import Any
PRIVACY={"PUBLIC","PRIVATE","SECRET","DEVICE_SECRET"}
class MemoryV2Store:
    def __init__(self,path:Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.db=sqlite3.connect(self.path); self.db.row_factory=sqlite3.Row; self.db.execute("CREATE TABLE IF NOT EXISTS memories (memory_id TEXT PRIMARY KEY, owner_id TEXT, namespace TEXT, session TEXT, device TEXT, project TEXT, kind TEXT, content TEXT, source TEXT, confidence REAL, importance REAL, privacy_level TEXT, created_at TEXT, updated_at TEXT, valid_from TEXT, valid_until TEXT)"); self.db.commit()
    def add(self,content:str,*,owner_id:str,namespace:str="default",session:str="",device:str="",project:str="",kind:str="semantic",source:str="user",confidence:float=1.0,importance:float=0.5,privacy_level:str="PRIVATE",valid_from:str="",valid_until:str=""):
        if privacy_level not in PRIVACY: raise ValueError("invalid privacy level")
        if not owner_id or not content.strip(): raise ValueError("owner/content required")
        now=datetime.datetime.now(datetime.timezone.utc).isoformat(); mid="mem_"+hashlib.sha256((owner_id+namespace+content+now).encode()).hexdigest()[:24]
        self.db.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(mid,owner_id,namespace,session,device,project,kind,content[:20000],source,max(0,min(1,confidence)),max(0,min(1,importance)),privacy_level,now,now,valid_from,valid_until)); self.db.commit(); return mid
    def search(self,query:str,*,owner_id:str,namespace:str="default",limit:int=8,include_secrets:bool=False):
        rows=self.db.execute("SELECT * FROM memories WHERE owner_id=? AND namespace=? ORDER BY updated_at DESC",(owner_id,namespace)).fetchall(); q=set(re.findall(r"\w+",query.lower())); scored=[]
        for r in rows:
            if r['privacy_level'] in {'SECRET','DEVICE_SECRET'} and not include_secrets: continue
            words=set(re.findall(r"\w+",r['content'].lower())); exact=len(q&words); score=exact*2+float(r['importance'])+float(r['confidence'])
            if exact or not q: scored.append((score,dict(r)))
        return [x[1] for x in sorted(scored,key=lambda x:(x[0],x[1]['updated_at']),reverse=True)[:max(1,min(50,limit))]]
    def delete(self,memory_id:str,*,owner_id:str)->bool:
        cur=self.db.execute("DELETE FROM memories WHERE memory_id=? AND owner_id=?",(memory_id,owner_id)); self.db.commit(); return cur.rowcount>0
    def export(self,*,owner_id:str): return [dict(r) for r in self.db.execute("SELECT * FROM memories WHERE owner_id=?",(owner_id,)).fetchall()]
    def close(self): self.db.close()
