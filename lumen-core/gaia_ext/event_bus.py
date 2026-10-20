"""Observable internal Event Bus; it never executes actions or stores secrets."""
from __future__ import annotations
import asyncio, hashlib, json, time, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

STATES=frozenset({"IDLE","LISTENING","TRANSCRIBING","THINKING","PLANNING","SEARCHING_MEMORY","USING_TOOL","WAITING_PERMISSION","EXECUTING","BROWSING","CODING","SPEAKING","INTERRUPTED","ERROR","SAFE_MODE"})
_SEVERITIES=frozenset({"info","warning","error","critical"})
_SENSITIVE=("password","secret","token","api_key","apikey","cookie","authorization")

def _safe(value: Any) -> Any:
    if isinstance(value,dict): return {str(k):("[REDACTED]" if any(x in str(k).lower() for x in _SENSITIVE) else _safe(v)) for k,v in value.items()}
    if isinstance(value,list): return [_safe(v) for v in value[:100]]
    if isinstance(value,(str,int,float,bool)) or value is None: return value if not (isinstance(value,str) and len(value)>4096) else value[:4096]
    return str(value)[:4096]

@dataclass(frozen=True)
class GaiaEvent:
    state: str
    source: str
    correlation_id: str
    session_id: str
    timestamp: str
    device_id: str = ""
    severity: str = "info"
    metadata: dict[str,Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: "gev_"+uuid.uuid4().hex)
    @classmethod
    def create(cls,state: str,*,source: str,session_id: str,correlation_id: str="",device_id: str="",severity: str="info",metadata: dict[str,Any]|None=None)->"GaiaEvent":
        state=str(state).upper(); severity=str(severity).lower()
        if state not in STATES: raise ValueError("state not allowed")
        if severity not in _SEVERITIES: raise ValueError("severity not allowed")
        if not source or not session_id: raise ValueError("source and session_id required")
        return cls(state,str(source)[:80],correlation_id[:100] or uuid.uuid4().hex,session_id[:100],datetime.now(timezone.utc).isoformat(),device_id[:100],severity,_safe(metadata or {}))
    def as_dict(self)->dict[str,Any]: return {"event_id":self.event_id,"state":self.state,"source":self.source,"correlation_id":self.correlation_id,"session_id":self.session_id,"timestamp":self.timestamp,"device_id":self.device_id,"severity":self.severity,"metadata":self.metadata}

Subscriber=Callable[[GaiaEvent],Any|Awaitable[Any]]
class EventBus:
    def __init__(self,max_queue:int=256)->None:
        self._queue:asyncio.Queue[GaiaEvent]=asyncio.Queue(maxsize=max(32,min(1024,max_queue))); self._subs:dict[str,Subscriber]={}; self._task:asyncio.Task|None=None; self._stop=False; self.metrics={"published":0,"processed":0,"dropped":0,"subscriber_errors":0}
    def subscribe(self,name:str,callback:Subscriber)->None:
        if not name or not callable(callback): raise ValueError("invalid subscriber")
        self._subs[name[:80]]=callback
    def publish(self,event:GaiaEvent|dict[str,Any])->bool:
        if self._stop: return False
        if isinstance(event,dict): event=GaiaEvent.create(**event)
        try:self._queue.put_nowait(event)
        except asyncio.QueueFull:self.metrics["dropped"]+=1; return False
        self.metrics["published"]+=1; return True
    async def start(self)->None:
        if not self._task or self._task.done(): self._stop=False; self._task=asyncio.create_task(self._run(),name="gaia-event-bus")
    async def stop(self)->None:
        self._stop=True; task=self._task; self._task=None
        if task: task.cancel(); await asyncio.gather(task,return_exceptions=True)
    async def _run(self)->None:
        while not self._stop:
            event=await self._queue.get()
            try:
                for callback in tuple(self._subs.values()):
                    try:
                        result=callback(event)
                        if hasattr(result,"__await__"): await result
                    except asyncio.CancelledError: raise
                    except Exception:self.metrics["subscriber_errors"]+=1
                self.metrics["processed"]+=1
            finally:self._queue.task_done()
    def status(self)->dict[str,Any]: return {"running":bool(self._task and not self._task.done()),"queue_depth":self._queue.qsize(),"queue_max":self._queue.maxsize,"subscribers":sorted(self._subs),**self.metrics}
