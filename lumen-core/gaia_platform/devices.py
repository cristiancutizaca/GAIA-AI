from __future__ import annotations
import hashlib,secrets,time
class DeviceRegistry:
 def __init__(self): self.items={}
 def create_pairing(self,owner,device_id,capabilities):
  code=f'{secrets.randbelow(1000000):06d}'; digest=hashlib.sha256(code.encode()).hexdigest(); self.items[device_id]={'owner':owner,'capabilities':list(capabilities),'trusted':False,'code_hash':digest,'expires':time.time()+300}; return code
 def approve(self,owner,device_id,code):
  d=self.items.get(device_id);
  if not d or d['owner']!=owner or d['expires']<time.time() or not secrets.compare_digest(d['code_hash'],hashlib.sha256(code.encode()).hexdigest()): raise PermissionError('pairing denied')
  d['trusted']=True; d.pop('code_hash',None); return True
 def revoke(self,owner,device_id):
  if self.items.get(device_id,{}).get('owner')!=owner: raise PermissionError('ownership denied')
  self.items[device_id]['trusted']=False
