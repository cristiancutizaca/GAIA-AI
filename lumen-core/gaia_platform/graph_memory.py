from __future__ import annotations
import sqlite3,uuid,datetime
from pathlib import Path
class TemporalGraphStore:
 def __init__(self,path:Path): self.db=sqlite3.connect(path); self.db.execute('CREATE TABLE IF NOT EXISTS nodes(id TEXT PRIMARY KEY,type TEXT,name TEXT,owner TEXT)'); self.db.execute('CREATE TABLE IF NOT EXISTS edges(id TEXT PRIMARY KEY,src TEXT,dst TEXT,relation TEXT,valid_from TEXT,valid_until TEXT,source TEXT,owner TEXT)'); self.db.commit()
 def node(self,type,name,owner):
  nid='node_'+uuid.uuid4().hex; self.db.execute('INSERT INTO nodes VALUES(?,?,?,?)',(nid,type,name,owner)); self.db.commit(); return nid
 def edge(self,src,dst,relation,owner,source='user',valid_from='',valid_until=''):
  eid='edge_'+uuid.uuid4().hex; self.db.execute('INSERT INTO edges VALUES(?,?,?,?,?,?,?,?)',(eid,src,dst,relation,valid_from,valid_until,source,owner)); self.db.commit(); return eid
 def related(self,node_id,owner): return [dict(zip(('id','src','dst','relation','valid_from','valid_until','source','owner'),r)) for r in self.db.execute('SELECT * FROM edges WHERE owner=? AND (src=? OR dst=?)',(owner,node_id,node_id)).fetchall()]
