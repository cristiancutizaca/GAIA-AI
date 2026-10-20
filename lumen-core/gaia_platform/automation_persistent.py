from __future__ import annotations
import datetime as dt, json, sqlite3, uuid
from pathlib import Path

class PersistentAutomationStore:
    """Durable metadata store; execution is delegated to GAIA Planner/Permission/Action Host."""
    def __init__(self, path: Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path); self.db.row_factory=sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS automations (
          automation_id TEXT PRIMARY KEY, owner TEXT NOT NULL, trigger_json TEXT NOT NULL,
          task_json TEXT NOT NULL, permissions_json TEXT NOT NULL, scope_json TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, last_run TEXT,
          next_run TEXT, result_json TEXT, failure_count INTEGER NOT NULL DEFAULT 0)''')
        self.db.commit()
    def add(self, owner, trigger, task, permissions=(), scope=None, next_run=None):
        if not owner: raise ValueError('owner required')
        aid='auto_'+uuid.uuid4().hex
        now=dt.datetime.now(dt.timezone.utc).isoformat()
        self.db.execute('INSERT INTO automations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(aid,owner,json.dumps(trigger),json.dumps(task),json.dumps(list(permissions)),json.dumps(scope or {}),0,now,None,next_run,None,0)); self.db.commit(); return self.get(aid,owner)
    def get(self, aid, owner):
        row=self.db.execute('SELECT * FROM automations WHERE automation_id=? AND owner=?',(aid,owner)).fetchone(); return self._decode(row) if row else None
    def list(self, owner): return [self._decode(r) for r in self.db.execute('SELECT * FROM automations WHERE owner=? ORDER BY created_at',(owner,)).fetchall()]
    def set_enabled(self, aid, owner, enabled):
        if not self.get(aid,owner): raise PermissionError('automation ownership denied')
        self.db.execute('UPDATE automations SET enabled=? WHERE automation_id=? AND owner=?',(int(enabled),aid,owner)); self.db.commit(); return self.get(aid,owner)
    def due(self, now=None):
        now=now or dt.datetime.now(dt.timezone.utc).isoformat()
        return [self._decode(r) for r in self.db.execute('SELECT * FROM automations WHERE enabled=1 AND next_run IS NOT NULL AND next_run<=?',(now,)).fetchall()]
    def record(self, aid, owner, *, result, next_run=None, failed=False):
        if not self.get(aid,owner): raise PermissionError('automation ownership denied')
        now=dt.datetime.now(dt.timezone.utc).isoformat(); self.db.execute('UPDATE automations SET last_run=?,next_run=?,result_json=?,failure_count=failure_count+? WHERE automation_id=? AND owner=?',(now,next_run,json.dumps(result),int(failed),aid,owner)); self.db.commit(); return self.get(aid,owner)
    def recover_orphans(self, running_ids=()):
        ids=tuple(running_ids); rows=self.db.execute('SELECT automation_id FROM automations WHERE result_json IS NULL AND enabled=1').fetchall(); recovered=[]
        for row in rows:
            if row['automation_id'] not in ids:
                self.db.execute('UPDATE automations SET result_json=? WHERE automation_id=?', (json.dumps({'status':'INTERRUPTED','reason':'process recovery; no automatic rerun'}),row['automation_id'])); recovered.append(row['automation_id'])
        self.db.commit(); return recovered
    def _decode(self,row):
        if not row:return None
        d=dict(row)
        for key in ('trigger_json','task_json','permissions_json','scope_json','result_json'):
            value=d.pop(key); d[key[:-5]]=json.loads(value) if value else None
        d['enabled']=bool(d['enabled']); return d
    def close(self): self.db.close()
