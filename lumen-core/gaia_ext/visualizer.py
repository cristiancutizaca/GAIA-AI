"""Read-only visualizer consumer schema; it has no action authority."""
from dataclasses import dataclass
from typing import Any
@dataclass(frozen=True)
class VisualizerEventConsumer:
    name:str="gaia-local-visualizer"
    async def consume(self,event:dict[str,Any])->None: return None
    def normalize(self,event:dict[str,Any])->dict[str,Any]: return {"state":str(event.get("state","IDLE")).lower(),"timestamp":event.get("timestamp",""),"source":str(event.get("source","core"))[:80],"metadata":event.get("metadata",{}) if isinstance(event.get("metadata"),dict) else {}}
