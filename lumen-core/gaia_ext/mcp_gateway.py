"""MCP-shaped gateway with GAIA risk/allowlist enforcement; no direct privileged authority."""
from __future__ import annotations
import asyncio, json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

RISK_LEVELS=("READ_ONLY","LOW_RISK","INTERACTIVE","EXTERNAL_SIDE_EFFECT","PRIVILEGED")
@dataclass(frozen=True)
class MCPToolAdapter:
    name: str
    description: str
    risk: str
    handler: Callable[[dict[str,Any]],Any|Awaitable[Any]]
    namespace: str = "default"
    def __post_init__(self):
        if self.risk not in RISK_LEVELS: raise ValueError("invalid MCP risk")
        if not self.name or not callable(self.handler): raise ValueError("invalid MCP tool")
    def schema(self)->dict[str,Any]: return {"name":self.name,"description":self.description[:500],"risk":self.risk,"namespace":self.namespace[:80]}

class MCPGateway:
    def __init__(self,*,allowlist: set[str]|None=None,denylist: set[str]|None=None,permission_check:Callable[...,bool]|None=None):
        self.allowlist=allowlist; self.denylist=denylist or set(); self.permission_check=permission_check or (lambda **_:False); self._tools:dict[str,MCPToolAdapter]={}; self.connected=False; self.metrics={"calls":0,"denied":0,"errors":0}
    def register(self,tool:MCPToolAdapter)->None:
        key=f"{tool.namespace}:{tool.name}"
        if key in self._tools: raise ValueError("duplicate MCP tool")
        self._tools[key]=tool
    def connect(self)->dict[str,Any]: self.connected=True; return {"status":"connected","tools":len(self._tools)}
    async def disconnect(self)->None: self.connected=False
    def health(self)->dict[str,Any]: return {"status":"OK" if self.connected else "DISABLED","connected":self.connected,"tools":len(self._tools),"metrics":dict(self.metrics)}
    def list_tools(self)->list[dict[str,Any]]: return [t.schema() for key,t in sorted(self._tools.items()) if key not in self.denylist and (self.allowlist is None or key in self.allowlist)]
    async def call(self,qualified_name:str,arguments:dict[str,Any]|None=None,*,principal:Any=None,confirmed:bool=False)->dict[str,Any]:
        self.metrics["calls"]+=1; tool=self._tools.get(qualified_name)
        if not self.connected or tool is None or qualified_name in self.denylist or (self.allowlist is not None and qualified_name not in self.allowlist): self.metrics["denied"]+=1; raise PermissionError("MCP tool not allowed or gateway disconnected")
        if tool.risk in {"INTERACTIVE","EXTERNAL_SIDE_EFFECT","PRIVILEGED"} and not confirmed: self.metrics["denied"]+=1; raise PermissionError("explicit GAIA confirmation required")
        if tool.risk in {"EXTERNAL_SIDE_EFFECT","PRIVILEGED"} and not self.permission_check(tool=tool,principal=principal): self.metrics["denied"]+=1; raise PermissionError("GAIA Permission Layer denied MCP tool")
        try:
            result=tool.handler(arguments or {}); result=await result if hasattr(result,"__await__") else result; return {"ok":True,"tool":qualified_name,"result":result}
        except Exception as exc:self.metrics["errors"]+=1; raise RuntimeError(f"MCP adapter failed: {type(exc).__name__}: {exc}") from exc
    async def handle_jsonrpc(self,line:str,*,principal:Any=None)->dict[str,Any]:
        request=json.loads(line); method=request.get("method"); rid=request.get("id")
        try:
            if method=="initialize": result={"protocolVersion":"2025-03-26","capabilities":{"tools":{}}}
            elif method=="tools/list": result={"tools":self.list_tools()}
            elif method=="tools/call":
                params=request.get("params",{}); result=await self.call(str(params.get("name","")),params.get("arguments",{}),principal=principal,confirmed=bool(params.get("confirmed",False)))
            else: raise ValueError("method not supported")
            return {"jsonrpc":"2.0","id":rid,"result":result}
        except Exception as exc:return {"jsonrpc":"2.0","id":rid,"error":{"code":-32000,"message":str(exc)[:300]}}
