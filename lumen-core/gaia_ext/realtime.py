"""Future realtime transport contract with explicit owner/device fields."""
from dataclasses import dataclass
from typing import Any
@dataclass(frozen=True)
class RealtimeEnvelope:
    kind:str; owner_id:str; device_id:str; session_id:str; payload:dict[str,Any]
    def as_dict(self): return {"kind":self.kind,"owner_id":self.owner_id,"device_id":self.device_id,"session_id":self.session_id,"payload":self.payload}
