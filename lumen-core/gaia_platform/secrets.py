from __future__ import annotations
import os
class SecretManager:
 def __init__(self,service='gaia'): self.service=service; self._keyring=None
 def _backend(self):
  if self._keyring is None:
   try: import keyring; self._keyring=keyring
   except ImportError: self._keyring=False
  return self._keyring
 def resolve(self,ref:str)->str:
  if not ref.startswith('secret://'): raise ValueError('only secret:// references accepted')
  name=ref[9:]; env=os.getenv('GAIA_SECRET_'+name.upper().replace('/','_'))
  if env: return env
  b=self._backend()
  if b: return b.get_password(self.service,name) or ''
  return ''
 def set(self,ref,value:str):
  if not ref.startswith('secret://') or not value: raise ValueError('invalid secret reference/value')
  b=self._backend()
  if not b: raise RuntimeError('keyring/Secret Service unavailable; plaintext fallback disabled')
  b.set_password(self.service,ref[9:],value); return True
 def redact(self,text):
  return str(text).replace(self.resolve('secret://dummy'),'[REDACTED]') if self.resolve('secret://dummy') else str(text)
