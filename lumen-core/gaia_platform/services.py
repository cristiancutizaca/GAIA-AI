from __future__ import annotations
import datetime as dt, json, os, shutil, sqlite3, time, uuid, zipfile
from pathlib import Path
from dataclasses import dataclass
from .security import redact

class ProjectRegistry:
    def __init__(self,path:Path):
        self.db=sqlite3.connect(path); self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, owner TEXT, name TEXT, path TEXT, namespace TEXT, vault_path TEXT, models_json TEXT, tools_json TEXT, skills_json TEXT, config_json TEXT, created_at TEXT)'); self.db.commit()
    def add(self,owner,name,path,**kwargs):
        pid='project_'+uuid.uuid4().hex; self.db.execute('INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?)',(pid,owner,name,str(Path(path).resolve()),kwargs.get('namespace',pid),kwargs.get('vault_path',''),json.dumps(kwargs.get('models',[])),json.dumps(kwargs.get('tools',[])),json.dumps(kwargs.get('skills',[])),json.dumps(kwargs.get('config',{})),dt.datetime.now(dt.timezone.utc).isoformat())); self.db.commit(); return self.get(pid,owner)
    def get(self,pid,owner):
        row=self.db.execute('SELECT * FROM projects WHERE id=? AND owner=?',(pid,owner)).fetchone(); return self._decode(row) if row else None
    def list(self,owner): return [self._decode(r) for r in self.db.execute('SELECT * FROM projects WHERE owner=? ORDER BY created_at',(owner,)).fetchall()]
    def _decode(self,row):
        d=dict(row)
        for k in ('models_json','tools_json','skills_json','config_json'):
            v=d.pop(k); d[k[:-5]]=json.loads(v)
        return d
    def close(self): self.db.close()

class JobStore:
    def __init__(self,path:Path):
        self.db=sqlite3.connect(path); self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, owner TEXT, goal TEXT, procedure_json TEXT, state TEXT, created_at TEXT, updated_at TEXT, result_json TEXT)'); self.db.commit()
    def create(self,owner,goal,procedure):
        jid='job_'+uuid.uuid4().hex; now=dt.datetime.now(dt.timezone.utc).isoformat(); self.db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)',(jid,owner,goal,json.dumps(procedure), 'PENDING',now,now,None)); self.db.commit(); return self.get(jid,owner)
    def get(self,jid,owner):
        r=self.db.execute('SELECT * FROM jobs WHERE id=? AND owner=?',(jid,owner)).fetchone(); return self._decode(r) if r else None
    def update(self,jid,owner,state,result=None):
        if not self.get(jid,owner): raise PermissionError('job ownership denied')
        self.db.execute('UPDATE jobs SET state=?,result_json=?,updated_at=? WHERE id=? AND owner=?',(state,json.dumps(result) if result is not None else None,dt.datetime.now(dt.timezone.utc).isoformat(),jid,owner)); self.db.commit(); return self.get(jid,owner)
    def list(self,owner): return [self._decode(r) for r in self.db.execute('SELECT * FROM jobs WHERE owner=? ORDER BY created_at',(owner,)).fetchall()]
    def _decode(self,row):
        if not row:return None
        d=dict(row); d['procedure']=json.loads(d.pop('procedure_json')); d['result']=json.loads(d.pop('result_json')) if d.get('result_json') else None; d.pop('result_json',None); return d
    def close(self): self.db.close()

class FilesystemSandbox:
    def __init__(self,root:Path): self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
    def resolve(self,relative:str)->Path:
        p=(self.root/relative).resolve()
        if self.root not in p.parents and p != self.root: raise PermissionError('filesystem path outside allowed root')
        if p.exists() and p.is_symlink(): raise PermissionError('symlink targets are not allowed')
        return p
    def read(self,relative,max_bytes=2_000_000): return self.resolve(relative).read_bytes()[:max_bytes]
    def metadata(self,relative):
        p=self.resolve(relative); s=p.stat(); return {'path':relative,'size':s.st_size,'mtime':s.st_mtime,'is_file':p.is_file(),'is_dir':p.is_dir()}
    def list(self,relative=''):
        p=self.resolve(relative); return [{'name':x.name,'is_dir':x.is_dir(),'size':x.stat().st_size if x.is_file() else 0} for x in sorted(p.iterdir())]

@dataclass
class CircuitBreaker:
    threshold:int=3; cooldown:float=30.0; failures:int=0; opened_at:float=0.0
    @property
    def state(self):
        if self.opened_at and time.monotonic()-self.opened_at < self.cooldown:return 'OPEN'
        if self.opened_at:return 'HALF_OPEN'
        return 'CLOSED'
    def allow(self): return self.state != 'OPEN'
    def success(self): self.failures=0; self.opened_at=0.0
    def failure(self):
        self.failures+=1
        if self.failures>=self.threshold:self.opened_at=time.monotonic()

class DiagnosticsExporter:
    def __init__(self,root:Path): self.root=Path(root)
    def export(self,output:Path,*,status:dict,events:list[dict],errors:list[dict]=()):
        output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
        manifest={'format':1,'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'secret_values_emitted':False,'files':['status.json','events.jsonl','errors.jsonl']}
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json',json.dumps(manifest,indent=2)); z.writestr('status.json',json.dumps(redact(status),indent=2)); z.writestr('events.jsonl',''.join(json.dumps(redact(e),ensure_ascii=False)+'\n' for e in events)); z.writestr('errors.jsonl',''.join(json.dumps(redact(e),ensure_ascii=False)+'\n' for e in errors))
        return manifest
