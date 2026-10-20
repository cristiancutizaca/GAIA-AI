from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Any
@dataclass
class VoiceState: state:str="IDLE"; mode:str="manual"; confidence:float=0.0
class BargeInController:
 def __init__(self): self._cancel=asyncio.Event()
 def interrupt(self): self._cancel.set()
 def reset(self): self._cancel=asyncio.Event()
 async def cancelled(self): return self._cancel.is_set()
class VoiceRouter:
 def __init__(self): self.state=VoiceState(); self.barge_in=BargeInController(); self._tts_task=None
 def transition(self,state,confidence=0.0):
  allowed={"IDLE":{"LISTENING","SPEAKING"},"LISTENING":{"TRANSCRIBING","IDLE"},"TRANSCRIBING":{"THINKING","ERROR"},"THINKING":{"SPEAKING","ERROR"},"SPEAKING":{"INTERRUPTED","IDLE"},"INTERRUPTED":{"LISTENING","IDLE"}}
  if state not in allowed.get(self.state.state,set()): raise ValueError(f"invalid voice transition {self.state.state}->{state}")
  self.state=VoiceState(state,self.state.mode,confidence); return self.state
 async def speak(self,tts, text):
  self.transition("SPEAKING"); self.barge_in.reset()
  try:
   for chunk in tts(text):
    if await self.barge_in.cancelled(): self.transition("INTERRUPTED"); return {"status":"interrupted"}
    if hasattr(chunk,"__await__"): await chunk
   self.transition("IDLE"); return {"status":"complete"}
  finally:
   if self.state.state=="SPEAKING": self.transition("IDLE")
 def interrupt(self):
  if self.state.state=="SPEAKING": self.barge_in.interrupt()
class TurnManager:
 def __init__(self,min_confidence=.5,silence_threshold=.2): self.min_confidence=min_confidence; self.silence_threshold=silence_threshold
 def decide(self,confidence:float,silence_seconds:float)->str: return "speech_start" if confidence>=self.min_confidence else ("speech_end" if silence_seconds>=self.silence_threshold else "silence")
