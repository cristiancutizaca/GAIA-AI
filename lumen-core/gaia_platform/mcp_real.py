from __future__ import annotations
import asyncio,json,urllib.request,urllib.error
from dataclasses import dataclass,field
from typing import Any
from .security import redact
@dataclass(frozen=True)
class MCPServerConfig:
    name:str; transport:str="stdio"; command:tuple[str,...]=(); url:str=""; enabled:bool=False; allow_tools:frozenset[str]=frozenset(); deny_tools:frozenset[str]=frozenset(); timeout:float=15.0; max_result_bytes:int=262144
@dataclass
class MCPConnection:
    config:MCPServerConfig; process:Any=None; request_id:int=0; initialized:bool=False; capabilities:dict[str,Any]=field(default_factory=dict)
    async def connect(self):
        if self.config.transport=="stdio":
            if not self.config.command: raise ValueError("stdio command required")
            self.process=await asyncio.create_subprocess_exec(*self.config.command,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        elif self.config.transport not in {"streamable_http","http"}: raise ValueError("unsupported MCP transport")
        result=await self.request("initialize",{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"gaia","version":"1.2"}})
        self.initialized=True; self.capabilities=result.get("capabilities",{}) if isinstance(result,dict) else {}; return result
    async def request(self,method:str,params:dict[str,Any]|None=None):
        self.request_id+=1; rid=self.request_id; payload={"jsonrpc":"2.0","id":rid,"method":method,"params":params or {}}
        if self.config.transport=="stdio":
            if not self.process or not self.process.stdin or not self.process.stdout: raise ConnectionError("MCP not connected")
            self.process.stdin.write((json.dumps(payload,separators=(",",":"))+"\n").encode()); await self.process.stdin.drain()
            raw=await asyncio.wait_for(self.process.stdout.readline(),timeout=self.config.timeout)
            if not raw: raise ConnectionError("MCP server closed stdio")
            response=json.loads(raw.decode());
        else:
            def call():
                req=urllib.request.Request(self.config.url,data=(json.dumps(payload)+"\n").encode(),headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"},method="POST")
                with urllib.request.urlopen(req,timeout=self.config.timeout) as r: return json.loads(r.read(self.config.max_result_bytes+1).decode())
            response=await asyncio.to_thread(call)
        if "error" in response: raise RuntimeError(str(redact(response["error"])))
        return response.get("result",{})
    async def list_tools(self): return (await self.request("tools/list")).get("tools",[])
    async def list_resources(self): return (await self.request("resources/list")).get("resources",[])
    async def list_prompts(self): return (await self.request("prompts/list")).get("prompts",[])
    async def call_tool(self,name:str,arguments:dict[str,Any]|None=None,*,confirmed=False):
        if name in self.config.deny_tools or (self.config.allow_tools and name not in self.config.allow_tools): raise PermissionError("MCP tool not allowlisted")
        if not confirmed: raise PermissionError("explicit GAIA confirmation required")
        result=await self.request("tools/call",{"name":name,"arguments":arguments or {}}); return redact(result)
    async def close(self):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try: await asyncio.wait_for(self.process.wait(),2)
            except asyncio.TimeoutError: self.process.kill(); await self.process.wait()
        self.process=None; self.initialized=False
class MCPManager:
    def __init__(self): self.configs={}; self.connections={}; self.audit=[]
    def register(self,config:MCPServerConfig): self.configs[config.name]=config
    def tool_risk(self, server: str, tool: str) -> str:
        """Conservative fallback: only explicitly read-shaped tools are read-only."""
        name = str(tool).casefold()
        if any(token in name for token in ("read", "list", "get", "search", "inspect", "health", "status")):
            return "READ_ONLY"
        return "EXTERNAL_SIDE_EFFECT"
    async def connect(self,name):
        cfg=self.configs[name]
        if not cfg.enabled: raise PermissionError("MCP server disabled")
        conn=MCPConnection(cfg); await conn.connect(); self.connections[name]=conn; self.audit.append({"event":"connected","server":name}); return conn
    async def discover(self,name):
        c=self.connections.get(name) or await self.connect(name); return {"tools":await c.list_tools(),"resources":await c.list_resources(),"prompts":await c.list_prompts()}
    async def call(self,server,tool,args=None,*,principal=None,authority=None,confirmed=False):
        risk=self.tool_risk(server, tool)
        if risk != "READ_ONLY":
            if principal is None or authority is None:
                raise PermissionError("MCP side effects require the GAIA authority gate")
            decision=authority(principal, capability="mcp.tool", permission="actions_request", risk=risk, resource_scope=f"mcp:{server}/{tool}", confirmed=confirmed)
            if not decision.allowed:
                raise PermissionError(decision.reason)
        c=self.connections.get(server) or await self.connect(server); result=await c.call_tool(tool,args,confirmed=True if risk == "READ_ONLY" else confirmed); self.audit.append({"event":"tool_call","server":server,"tool":tool,"risk":risk}); return result
    async def close(self):
        for c in tuple(self.connections.values()): await c.close()
        self.connections.clear()
