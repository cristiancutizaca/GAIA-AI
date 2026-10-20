from __future__ import annotations
import asyncio,json
from .security import redact
class VisualizerStream:
 def __init__(self): self.clients=[]
 def publish(self,event):
  payload=json.dumps(redact(event),ensure_ascii=False);
  for q in tuple(self.clients):
   try:q.put_nowait(payload)
   except asyncio.QueueFull: pass
 async def subscribe(self):
  q=asyncio.Queue(maxsize=64); self.clients.append(q)
  try:
   while True: yield await q.get()
  finally:
   if q in self.clients:self.clients.remove(q)
