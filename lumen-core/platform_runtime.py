from __future__ import annotations
import asyncio, json, os, re, time, uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gaia_ext.event_bus import EventBus, GaiaEvent
from gaia_ext.feature_flags import feature_flags
from gaia_platform.browser_real import BrowserProfile, HttpBrowserBackend, BrowserUseBackend
from gaia_platform.memory_v2 import MemoryV2Store
from gaia_platform.mcp_real import MCPManager, MCPServerConfig
from gaia_platform.security import guard_web_content
from gaia_platform.automation_persistent import PersistentAutomationStore
from authority import authorize, READ_ONLY, LOW_RISK
from gaia_platform.planner import Planner
from gaia_platform.skills2 import SkillRegistryV2
from gaia_platform.services import ProjectRegistry, JobStore, FilesystemSandbox, DiagnosticsExporter, CircuitBreaker
from gaia_platform.real_backends import Mem0MemoryProvider, GraphitiMemoryProvider, PipecatVoiceBackend, SileroVADBackend, OpenHandsCodingWorker, UITARSComputerUseBackend
from gaia_platform.visualizer_http import VisualizerStream

@dataclass(frozen=True)
class Capability:
    name: str
    provider: str
    risk: str
    enabled: bool
    permission: str

class CapabilityRouter:
    def __init__(self):
        self._items: dict[str, Capability] = {}
    def register(self, name: str, provider: str, *, risk="READ_ONLY", enabled=True, permission="chat"):
        self._items[name] = Capability(name, provider, risk, bool(enabled), permission)
    def resolve(self, name: str) -> Capability:
        item = self._items.get(name)
        if not item or not item.enabled:
            raise LookupError(f"capability unavailable: {name}")
        return item
    def status(self):
        return {k: vars(v) for k, v in sorted(self._items.items())}

class PlatformRuntime:
    """Owner of v1.3 production-path capabilities; Core remains permission authority."""
    def __init__(self, root: Path, *, event_bus: EventBus | None = None):
        self.root = Path(root).resolve()
        self.data = self.root / "data"
        self.data.mkdir(parents=True, exist_ok=True)
        self.events = event_bus or EventBus()
        self.visualizer_stream = VisualizerStream()
        self.events.subscribe("visualizer", self.visualizer_stream.publish)
        self.capabilities = CapabilityRouter()
        self.memory = MemoryV2Store(self.data / "platform_memory_v13.db")
        browser_profile = BrowserProfile(name="temporary", allowed_domains=set(), allow_private=os.getenv("GAIA_BROWSER_ALLOW_PRIVATE", "false").lower() in {"1", "true", "yes"})
        self.browser = BrowserUseBackend(browser_profile) if feature_flags.browser else HttpBrowserBackend(browser_profile)
        self.mcp = MCPManager()
        self.automations = PersistentAutomationStore(self.data / "automations_v13.db")
        self.projects = ProjectRegistry(self.data / "projects_v14.db")
        self.jobs = JobStore(self.data / "jobs_v14.db")
        self.filesystem = FilesystemSandbox(self.data / "workspace")
        self.diagnostics_exporter = DiagnosticsExporter(self.data)
        self.breakers = {name: CircuitBreaker() for name in ("mcp", "browser", "voice", "coding", "graph")}
        self.vad = SileroVADBackend()
        self.voice_provider = PipecatVoiceBackend(self.vad)
        self.mem0 = Mem0MemoryProvider()
        self.graphiti = GraphitiMemoryProvider()
        self.coding_worker = OpenHandsCodingWorker(self.data / "coding-workspaces")
        self.computer_use = UITARSComputerUseBackend()
        self.planner = Planner()
        self.skills = SkillRegistryV2()
        for skill_id in ("research", "browser_research", "coding", "debugging", "code_review", "project_analysis", "file_management", "system_diagnostics", "documentation", "memory_management", "data_analysis"):
            self.skills.enable(skill_id)
        self._started = False
        self._register_capabilities()
        self._load_mcp_registry()

    def _register_capabilities(self):
        entries = [
            ("memory.read", "MemoryV2Store", READ_ONLY, True, "memory_read"),
            ("memory.write", "MemoryV2Store", LOW_RISK, True, "memory_write"),
            ("memory.semantic_search", "MemoryV2Store", READ_ONLY, True, "memory_read"),
            ("graph.query", "TemporalGraphStore", READ_ONLY, bool(feature_flags.graph_memory), "memory_read"),
            ("browser.read", "HttpBrowserBackend", READ_ONLY, True, "chat"),
            ("browser.search", "HttpBrowserBackend", READ_ONLY, True, "chat"),
            ("browser.interact", "BrowserUseBackend", "INTERACTIVE", bool(feature_flags.browser), "actions_request"),
            ("browser.submit", "BrowserUseBackend", "EXTERNAL_SIDE_EFFECT", bool(feature_flags.browser), "actions_request"),
            ("browser.download", "BrowserUseBackend", "LOW_RISK", bool(feature_flags.browser), "actions_request"),
            ("mcp.tool", "MCPManager", "INTERACTIVE", bool(feature_flags.mcp), "actions_request"),
            ("filesystem.read", "FileWorker", READ_ONLY, True, "chat"),
            ("filesystem.write", "FileWorker", "EXTERNAL_SIDE_EFFECT", True, "actions_request"),
            ("process.execute", "ActionHost", "PRIVILEGED", False, "actions_execute"),
            ("voice.listen", "VoiceRouter", READ_ONLY, bool(feature_flags.voice_v2), "voice"),
            ("voice.speak", "VoiceRouter", LOW_RISK, bool(feature_flags.voice_v2), "voice"),
            ("coding.inspect", "CodingWorker", READ_ONLY, bool(feature_flags.coding_worker), "chat"),
            ("coding.modify", "CodingWorker", LOW_RISK, bool(feature_flags.coding_worker), "actions_request"),
            ("coding.apply", "ActionHost", "EXTERNAL_SIDE_EFFECT", bool(feature_flags.coding_worker), "actions_execute"),
            ("research.web", "BrowserWorker", READ_ONLY, True, "chat"),
            ("computer.observe", "ComputerUse", READ_ONLY, bool(feature_flags.computer_use), "chat"),
            ("computer.interact", "ComputerUse", "EXTERNAL_SIDE_EFFECT", bool(feature_flags.computer_use), "actions_request"),
            ("automation.manage", "AutomationEngine", "LOW_RISK", True, "actions_request"),
            ("device.remote_action", "ActionHost", "EXTERNAL_SIDE_EFFECT", bool(feature_flags.realtime_transport), "actions_request"),
        ]
        for name, provider, risk, enabled, permission in entries:
            self.capabilities.register(name, provider, risk=risk, enabled=enabled, permission=permission)

    def _registry_path(self): return self.data / "mcp_servers_v13.json"
    def _load_mcp_registry(self):
        path = self._registry_path()
        if not path.exists(): return
        try: items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError): return
        for item in items if isinstance(items, list) else []:
            try: self.register_mcp(item, persist=False)
            except (TypeError, ValueError): continue

    def register_mcp(self, item: dict[str, Any], *, persist=True):
        command = tuple(str(x) for x in item.get("command", []))
        cfg = MCPServerConfig(name=str(item["name"]), transport=str(item.get("transport", "stdio")), command=command, url=str(item.get("url", "")), enabled=bool(item.get("enabled", False)), allow_tools=frozenset(str(x) for x in item.get("allow_tools", [])), deny_tools=frozenset(str(x) for x in item.get("deny_tools", [])), timeout=float(item.get("timeout", 15)))
        self.mcp.register(cfg)
        if persist:
            rows=[]
            for c in self.mcp.configs.values(): rows.append({"name":c.name,"transport":c.transport,"command":list(c.command),"url":c.url,"enabled":c.enabled,"allow_tools":sorted(c.allow_tools),"deny_tools":sorted(c.deny_tools),"timeout":c.timeout})
            self._registry_path().write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return cfg

    async def start(self):
        if not self._started:
            await self.events.start(); self._started=True
            self._emit("IDLE", "platform_runtime", {"event":"started"})
        return self

    async def stop(self):
        if self._started:
            await self.mcp.close(); await self.browser.close(); await self.voice_provider.stop(); await self.graphiti.close(); await self.events.stop(); self._started=False
        self.memory.close()
        self.automations.close()
        self.projects.close()
        self.jobs.close()

    def _emit(self, state, source, metadata=None, *, session_id="", correlation_id=""):
        try:
            self.events.publish(GaiaEvent.create(state, source=source, session_id=session_id or "platform", correlation_id=correlation_id, metadata=metadata or {}))
        except (ValueError, RuntimeError):
            pass

    @staticmethod
    def _owner(principal): return "master" if getattr(principal, "is_master", False) else str(getattr(principal, "device_id", "unknown"))
    @staticmethod
    def _allows(principal, capability): return bool(getattr(principal, "allows", lambda _: False)(capability))

    @staticmethod
    def _authority_result(decision, *, response_prefix="Capability blocked"):
        if decision.allowed:
            return None
        return {"response":f"{response_prefix}: {decision.reason}","capability":decision.capability,"risk":decision.risk,"status":decision.status,"authority":decision.as_dict()}

    async def handle_chat(self, message: str, *, principal, session_id: str, device_id: str, request_id: str = "") -> dict[str, Any] | None:
        """Return a handled response only for capabilities this runtime owns; otherwise None delegates to legacy GAIA chat."""
        text = message.strip(); low = text.lower(); correlation = request_id or uuid.uuid4().hex
        owner = self._owner(principal)
        plan = self.planner.plan(text, mcp_configs=self.mcp.configs)
        self._emit("PLANNING", "planner_v2", {"plan_id":plan.id,"state":plan.state,"skill":plan.steps[0].skill}, session_id=session_id, correlation_id=correlation)
        self._emit("THINKING", "platform_runtime", {"message_length":len(text)}, session_id=session_id, correlation_id=correlation)

        if re.search(r"\b(recuerda|recuerdame|remember)\b", low):
            decision = authorize(principal, capability="memory.write", permission="memory_write", risk=LOW_RISK, resource_scope=f"memory:{owner}", confirmed=True)
            blocked = self._authority_result(decision, response_prefix="Memory write blocked")
            if blocked: return blocked
            content = re.split(r"\b(?:que|that)\b", text, maxsplit=1, flags=re.I)[-1].strip(" .:") or text
            mid = self.memory.add(content, owner_id=owner, namespace=f"device:{device_id}", session=session_id, device=device_id, source="chat", kind="episodic", importance=.8)
            semantic = None
            graph = None
            if feature_flags.mem0:
                try: semantic = await asyncio.to_thread(self.mem0.add, content, owner=owner, namespace=f"device:{device_id}", session=session_id)
                except Exception as exc: semantic = {"status": "BACKEND_FAILED", "error": type(exc).__name__}
            if feature_flags.graph_memory:
                try: graph = await self.graphiti.add_episode(content, owner=owner, namespace=f"device:{device_id}", source="gaia.chat.memory")
                except Exception as exc: graph = {"status": "BACKEND_FAILED", "error": type(exc).__name__}
            self._emit("USING_TOOL", "memory_v2", {"capability":"memory.write","memory_id":mid}, session_id=session_id, correlation_id=correlation)
            return {"response":f"Guardé el recuerdo en el espacio privado de {owner}.","capability":"memory.write","memory_id":mid,"semantic_memory":semantic,"graph_memory":graph,"status":"SUCCEEDED","plan":self.planner.serialize(plan)}

        if re.search(r"\b(?:qué|que|what)\b.*\b(?:recuerd|base de datos|database|proyecto)\b", low) or "what do you remember" in low:
            decision = authorize(principal, capability="memory.read", permission="memory_read", risk=READ_ONLY, resource_scope=f"memory:{owner}")
            blocked = self._authority_result(decision, response_prefix="Memory read blocked")
            if blocked: return blocked
            rows = self.memory.search(text, owner_id=owner, namespace=f"device:{device_id}", limit=5)
            semantic = None
            graph = None
            if feature_flags.mem0:
                try: semantic = await asyncio.to_thread(self.mem0.search, text, owner=owner, namespace=f"device:{device_id}", limit=5)
                except Exception as exc: semantic = {"status": "BACKEND_FAILED", "error": type(exc).__name__}
            if feature_flags.graph_memory:
                try: graph = await self.graphiti.search(text, owner=owner, namespace=f"device:{device_id}", limit=5)
                except Exception as exc: graph = {"status": "BACKEND_FAILED", "error": type(exc).__name__}
            response = "No encontré un recuerdo relevante." if not rows else "Recuerdo relevante: " + "; ".join(str(x["content"]) for x in rows)
            self._emit("SEARCHING_MEMORY", "memory_v2", {"count":len(rows)}, session_id=session_id, correlation_id=correlation)
            return {"response":response,"capability":"memory.read","results":rows,"semantic_results":semantic,"graph_results":graph,"status":"SUCCEEDED","plan":self.planner.serialize(plan)}

        interaction = re.search(r"(?i)\b(?:click|haz click|pulsa)\s+(?:en\s+)?([#.]?[\w-]+)|\b(?:escribe|type|rellena)\s+(.+?)\s+(?:en|into)\s+([#.]?[\w-]+)", text)
        if interaction and re.search(r"(?i)\b(?:browser|navegador|página|pagina|click|pulsa|escribe|type|rellena)\b", text):
            decision = authorize(principal, capability="browser.interact", permission="actions_request", risk="INTERACTIVE", resource_scope="browser:interactive", confirmed=False)
            blocked = self._authority_result(decision, response_prefix="Browser interaction blocked")
            if blocked: return blocked
            if not self.breakers["browser"].allow(): return {"response":"Browser backend temporalmente aislado.","capability":"browser.interact","status":"BACKEND_OPEN"}
            try:
                url = re.search(r"\bhttps?://[^\s]+", text, re.I)
                if url and getattr(self.browser, "session", None) is None: await self.browser.launch()
                if url: await self.browser.navigate(url.group(0).rstrip(".,);]"))
                if interaction.group(1): result = await self.browser.click(interaction.group(1))
                else: result = await self.browser.type(interaction.group(3), interaction.group(2))
                self.breakers["browser"].success(); self._emit("BROWSING", "browser_use", result, session_id=session_id, correlation_id=correlation)
                return {"response":"Acción Browser Use completada bajo autorización GAIA.","capability":"browser.interact","status":"SUCCEEDED","result":result,"plan":self.planner.serialize(plan)}
            except Exception as exc:
                self.breakers["browser"].failure(); return {"response":f"Browser Use backend unavailable: {type(exc).__name__}","capability":"browser.interact","status":"BACKEND_FAILED"}

        url_match = re.search(r"\bhttps?://[^\s]+|\b(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s]*)?", text, re.I)
        if url_match and re.search(r"\b(?:abre|abrir|lee|leer|busca|buscar|open|read|search)\b", low):
            decision = authorize(principal, capability="browser.read", permission="chat", risk=READ_ONLY, resource_scope="web:read")
            blocked = self._authority_result(decision, response_prefix="Browser read blocked")
            if blocked: return blocked
            self.capabilities.resolve("browser.read")
            if not self.breakers["browser"].allow():
                return {"response":"Browser backend temporalmente aislado por circuit breaker.","capability":"browser.read","status":"BACKEND_OPEN"}
            url = url_match.group(0).rstrip(".,);]")
            if not url.startswith("http"): url="https://"+url
            self._emit("BROWSING", "browser_router", {"url":url,"trust":"EXTERNAL_UNTRUSTED"}, session_id=session_id, correlation_id=correlation)
            try:
                result = await self.browser.navigate(url); self.breakers["browser"].success()
            except Exception as exc:
                self.breakers["browser"].failure()
                return {"response":f"Browser backend unavailable: {type(exc).__name__}","capability":"browser.read","status":"BACKEND_FAILED"}
            body = str(result.get("content", {}).get("content", ""))
            title = re.search(r"<title[^>]*>(.*?)</title>", body, re.I|re.S)
            heading = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.I|re.S)
            label = (title or heading).group(1).strip() if (title or heading) else result.get("url", url)
            return {"response":f"Título de la página: {re.sub(r'<[^>]+>','',label)}","capability":"browser.read","url":result.get("url",url),"trust":"EXTERNAL_UNTRUSTED","status":"SUCCEEDED","plan":self.planner.serialize(plan)}

        mcp_match = re.search(r"\bmcp\s*[:/]\s*([\w.-]+)\s*[/：:]\s*([\w.-]+)", low)
        planned_mcp = next((s.capability.resource_scope.split(":",1)[1].split("/",1) for s in plan.steps if s.capability and s.capability.capability == "mcp.tool" and ":" in s.capability.resource_scope), None)
        if not mcp_match and planned_mcp:
            mcp_match = re.match(r"mcp[:/]([\w.-]+)[/:]([\w.-]+)", f"mcp:{planned_mcp[0]}/{planned_mcp[1]}")
        if mcp_match:
            server, tool = mcp_match.group(1), mcp_match.group(2)
            self.capabilities.resolve("mcp.tool")
            risk = self.mcp.tool_risk(server, tool)
            decision = authorize(principal, capability="mcp.tool", permission="actions_request", risk=risk, resource_scope=f"mcp:{server}/{tool}", confirmed=False)
            blocked = self._authority_result(decision, response_prefix="MCP blocked")
            if blocked: return blocked
            if not self.breakers["mcp"].allow():
                return {"response":"MCP backend temporalmente aislado por circuit breaker.","capability":"mcp.tool","status":"BACKEND_OPEN"}
            self._emit("USING_TOOL", "mcp_gateway", {"server":server,"tool":tool}, session_id=session_id, correlation_id=correlation)
            try:
                result = await self.mcp.call(server, tool, {}, principal=principal, authority=authorize, confirmed=decision.allowed); self.breakers["mcp"].success()
            except Exception as exc:
                self.breakers["mcp"].failure()
                return {"response":f"MCP backend unavailable: {type(exc).__name__}","capability":"mcp.tool","status":"BACKEND_FAILED"}
            return {"response":f"MCP {server}/{tool}: {json.dumps(result, ensure_ascii=False)}","capability":"mcp.tool","status":"SUCCEEDED","result":result,"plan":self.planner.serialize(plan)}
        return None

    def status(self):
        return {"started":self._started,"capabilities":self.capabilities.status(),"mcp_servers":sorted(self.mcp.configs),"automations":len(self.automations.list("master")),"projects":len(self.projects.list("master")),"jobs":len(self.jobs.list("master")),"skills":self.skills.list(),"visualizer":{"enabled":feature_flags.visualizer,"stream_clients":len(self.visualizer_stream.clients)},"backends":{"browser":self.browser.health() if hasattr(self.browser,"health") else {"status":"FALLBACK_HTTP"},"voice":self.voice_provider.health(),"vad":self.vad.health(),"mem0":self.mem0.health(),"graphiti":self.graphiti.health(),"openhands":self.coding_worker.health(),"computer_use":self.computer_use.health()},"breakers":{k:v.state for k,v in self.breakers.items()},"event_bus":self.events.status()}
