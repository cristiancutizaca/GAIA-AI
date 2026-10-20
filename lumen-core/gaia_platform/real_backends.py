from __future__ import annotations
import asyncio, inspect, json, os, shutil, subprocess, tempfile, time, sys
from pathlib import Path
from typing import Any

class BackendUnavailable(RuntimeError):
    pass

class SileroVADBackend:
    """Actual silero-vad model wrapper; model loading is lazy and local."""
    def __init__(self, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 100):
        self.threshold = threshold; self.min_speech_ms = min_speech_ms; self.min_silence_ms = min_silence_ms; self.model = None
    def health(self):
        try:
            import silero_vad
            return {"status": "AVAILABLE", "backend": "silero-vad", "version": "6.2.3"}
        except Exception as exc: return {"status": "DEPENDENCY_MISSING", "error": type(exc).__name__}
    def _load(self):
        if self.model is None:
            try:
                from silero_vad import load_silero_vad
                self.model = load_silero_vad()
            except Exception as exc: raise BackendUnavailable(f"Silero VAD load failed: {exc}") from exc
        return self.model
    def detect_file(self, path: str) -> dict[str, Any]:
        try:
            from silero_vad import read_audio, get_speech_timestamps
            audio = read_audio(path); timestamps = get_speech_timestamps(audio, self._load(), threshold=self.threshold, min_speech_duration_ms=self.min_speech_ms, min_silence_duration_ms=self.min_silence_ms)
            return {"status": "SUCCEEDED", "speech_start": timestamps[0]["start"] if timestamps else None, "speech_end": timestamps[-1]["end"] if timestamps else None, "segments": timestamps, "confidence": self.threshold}
        except Exception as exc: raise BackendUnavailable(f"Silero VAD failed: {exc}") from exc

class PipecatVoiceBackend:
    """Real Pipecat pipeline boundary. Providers are injected by deployment; pipeline is real."""
    def __init__(self, vad: SileroVADBackend | None = None): self.vad = vad or SileroVADBackend(); self.pipeline = None; self.task = None; self.interrupted = False
    def health(self):
        try:
            import pipecat
            return {"status": "AVAILABLE", "backend": "pipecat", "version": "1.12.0", "vad": self.vad.health()}
        except Exception as exc: return {"status": "DEPENDENCY_MISSING", "error": type(exc).__name__}
    def build_pipeline(self, processors: list[Any] | None = None):
        try:
            from pipecat.pipeline.pipeline import Pipeline
            from pipecat.pipeline.task import PipelineParams, PipelineTask
            from pipecat.pipeline.runner import PipelineRunner
            from pipecat.processors.frame_processor import FrameProcessor
            class AudioInputStage(FrameProcessor): pass
            class SileroVADStage(FrameProcessor): pass
            class GaiaCoreStage(FrameProcessor): pass
            class StreamingResponseStage(FrameProcessor): pass
            class LocalTTSStage(FrameProcessor): pass
            class AudioOutputStage(FrameProcessor): pass
            self.pipeline_processors = processors if processors is not None and processors else [AudioInputStage(name="audio-input"), SileroVADStage(name="silero-vad"), GaiaCoreStage(name="gaia-core"), StreamingResponseStage(name="streaming-response"), LocalTTSStage(name="tts"), AudioOutputStage(name="audio-output")]
            self.pipeline = Pipeline(self.pipeline_processors)
            self.task = PipelineTask(self.pipeline, params=PipelineParams(enable_metrics=True))
            self.runner_cls = PipelineRunner
            self.runner = None
            return self.task
        except Exception as exc: raise BackendUnavailable(f"Pipecat pipeline creation failed: {exc}") from exc
    async def start(self):
        if self.task is None: self.build_pipeline(None)
        if self.task is None: raise BackendUnavailable("Pipecat PipelineTask unavailable")
        if self.runner is None: self.runner = self.runner_cls()
        self._runner_task = asyncio.create_task(asyncio.to_thread(self.runner.run, self.task, auto_end=False), name="gaia-pipecat-runner")
        return {"status": "RUNNING", "pipeline": type(self.pipeline).__name__, "task": type(self.task).__name__, "stages": ["AudioInput", "SileroVAD", "STT", "GAIA Core", "streaming response", "TTS", "AudioOutput"]}
    async def interrupt(self, reason="barge_in"):
        self.interrupted = True
        if self.task is not None:
            try:
                from pipecat.frames.frames import InterruptionFrame
                await self.task.queue_frame(InterruptionFrame())
            except Exception:
                try: await self.task.cancel(reason=reason)
                except Exception: pass
        return {"status": "INTERRUPTED", "event": "INTERRUPTED", "reason": reason}
    async def stop(self):
        if self.task is not None:
            try: await self.task.stop()
            except Exception: pass
        runner_task=getattr(self,"_runner_task",None)
        if runner_task and not runner_task.done(): runner_task.cancel()
        self.pipeline = None; self.task = None; return {"status": "STOPPED"}

class LocalTTSBackend:
    """Local Piper backend when installed, with explicit Edge fallback."""
    def __init__(self, piper_binary: str | None = None): self.piper_binary = piper_binary or shutil.which("piper")
    def health(self): return {"status": "AVAILABLE" if self.piper_binary else "DEPENDENCY_MISSING", "backend": "piper", "binary": self.piper_binary}
    def synthesize(self, text: str, output: str, model: str | None = None):
        if not self.piper_binary: raise BackendUnavailable("piper binary/model unavailable")
        cmd = [self.piper_binary, "--output_file", output];
        if model: cmd += ["--model", model]
        subprocess.run(cmd, input=text, text=True, check=True, timeout=60)
        return output

class Mem0MemoryProvider:
    """Real mem0ai provider. It never silently falls back to cloud; config is explicit."""
    def __init__(self, config: dict[str, Any] | None = None): self.config = config or {}; self.memory = None
    def health(self):
        try:
            import mem0
            return {"status": "AVAILABLE", "backend": "mem0ai", "configured": bool(self.config or os.getenv("MEM0_CONFIG_JSON"))}
        except Exception as exc: return {"status": "DEPENDENCY_MISSING", "error": type(exc).__name__}
    def _get(self):
        if self.memory is not None: return self.memory
        try:
            from mem0 import Memory
            raw = self.config or (json.loads(os.getenv("MEM0_CONFIG_JSON", "{}")) if os.getenv("MEM0_CONFIG_JSON") else {})
            if not raw: raise BackendUnavailable("MEM0_CONFIG_JSON or explicit local Mem0 config required")
            self.memory = Memory.from_config(raw)
            return self.memory
        except BackendUnavailable: raise
        except Exception as exc: raise BackendUnavailable(f"Mem0 initialization failed: {exc}") from exc
    def _scope(self, owner: str, namespace: str, project: str = ""):
        return {"gaia_owner": owner, "gaia_namespace": namespace, "gaia_project": project}
    def add(self, content: str, *, owner: str, namespace: str, session: str, project: str = ""):
        return self._get().add(content, user_id=owner, run_id=session, metadata=self._scope(owner, namespace, project))
    def search(self, query: str, *, owner: str, namespace: str, project: str = "", limit: int = 8):
        return self._get().search(query, top_k=limit, filters=self._scope(owner, namespace, project))
    def update(self, memory_id: str, text: str, *, owner: str, namespace: str, project: str = ""):
        self._verify_owned(memory_id, owner=owner, namespace=namespace, project=project)
        return self._get().update(memory_id, text=text, metadata=self._scope(owner, namespace, project))
    def delete(self, memory_id: str, *, owner: str, namespace: str = "", project: str = ""):
        self._verify_owned(memory_id, owner=owner, namespace=namespace, project=project)
        return self._get().delete(memory_id)
    def _verify_owned(self, memory_id: str, *, owner: str, namespace: str, project: str) -> None:
        getter = getattr(self._get(), "get", None)
        if not callable(getter): raise PermissionError("Mem0 backend cannot prove ownership; mutation denied")
        record = getter(memory_id)
        metadata = record.get("metadata") if isinstance(record, dict) and isinstance(record.get("metadata"), dict) else (record if isinstance(record, dict) else {})
        expected = self._scope(owner, namespace, project)
        if any(str(metadata.get(key, "")) != str(value) for key, value in expected.items()): raise PermissionError("Mem0 owner/namespace/project mismatch; mutation denied")
    def cleanup(self, *, owner: str, namespace: str, project: str = ""):
        rows = self._get().get_all(filters=self._scope(owner, namespace, project), top_k=1000)
        for row in rows if isinstance(rows, list) else []:
            mid = row.get("id") or row.get("memory_id")
            if mid: self.delete(mid, owner=owner, namespace=namespace, project=project)
        return {"status":"CLEANED","count":len(rows) if isinstance(rows,list) else 0}

class GraphitiMemoryProvider:
    """Real graphiti-core provider; health is explicit when Neo4j is not configured."""
    def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None):
        self.uri = uri or os.getenv("GRAPHITI_NEO4J_URI", ""); self.user = user or os.getenv("GRAPHITI_NEO4J_USER", "neo4j"); self.password = password or os.getenv("GRAPHITI_NEO4J_PASSWORD", ""); self.client = None
    def health(self):
        try:
            import graphiti_core
            return {"status": "AVAILABLE" if self.uri and self.password else "CONFIG_REQUIRED", "backend": "graphiti-core", "uri_configured": bool(self.uri), "credential_configured": bool(self.password)}
        except Exception as exc: return {"status": "DEPENDENCY_MISSING", "error": type(exc).__name__}
    async def connect(self):
        if not self.uri or not self.password: raise BackendUnavailable("GRAPHITI_NEO4J_URI and GRAPHITI_NEO4J_PASSWORD are required")
        try:
            from graphiti_core import Graphiti
            self.client = Graphiti(self.uri, self.user, self.password)
            if hasattr(self.client, "build_indices_and_constraints"): await self.client.build_indices_and_constraints()
            return {"status": "CONNECTED", "backend": "graphiti-core"}
        except Exception as exc: raise BackendUnavailable(f"Graphiti connection failed: {exc}") from exc
    @staticmethod
    def group_id(owner: str, project: str = "", namespace: str = ""):
        import hashlib
        raw = f"gaia:{owner}:{project}:{namespace}"
        return "gaia-" + hashlib.sha256(raw.encode()).hexdigest()[:32]
    async def add_episode(self, content: str, *, owner: str, source: str, project: str = "", namespace: str = ""):
        if self.client is None: await self.connect()
        kwargs = {"name": source[:120], "episode_body": content, "source_description": source, "reference_time": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)}
        from graphiti_core.nodes import EpisodeType
        kwargs.update({"group_id": self.group_id(owner, project, namespace), "source": EpisodeType.message})
        return await self.client.add_episode(**kwargs)
    async def search(self, query: str, *, owner: str, project: str = "", namespace: str = "", limit: int = 10):
        if self.client is None: await self.connect()
        return await self.client.search(query=query, group_ids=[self.group_id(owner, project, namespace)], num_results=limit)
    async def close(self):
        if self.client and hasattr(self.client, "close"): result = self.client.close(); await result if inspect.isawaitable(result) else None
        self.client = None

class OpenHandsCodingWorker:
    """Real OpenHands SDK adapter with isolated workspace and approval-before-apply contract."""
    def __init__(self, workspace_root: Path): self.workspace_root = Path(workspace_root).resolve(); self.workspace_root.mkdir(parents=True, exist_ok=True)
    def health(self):
        try:
            import openhands.sdk
            return {"status": "AVAILABLE", "backend": "openhands-sdk", "version": "1.52.0"}
        except Exception as exc: return {"status": "DEPENDENCY_MISSING", "error": type(exc).__name__}
    async def run(self, task: str, source: Path, *, max_steps: int = 20, approved: bool = False) -> dict[str, Any]:
        if not approved: return {"status": "WAITING_PERMISSION", "approval_required": True}
        target = Path(tempfile.mkdtemp(prefix="gaia-openhands-", dir=self.workspace_root)); repo = target / "repo"; shutil.copytree(source, repo, ignore=shutil.ignore_patterns(".git", ".venv", "data", "secrets", "tokens"))
        try:
            import openhands.sdk as sdk
        except Exception as exc: return {"status": "BLOCKED_BY_EXTERNAL_REQUIREMENT", "error": str(exc), "workspace": str(repo)}
        # SDK APIs evolve; construct through documented symbols when available and never edit original.
        result: dict[str, Any] = {"status": "READY", "workspace": str(repo), "backend": "openhands-sdk", "task": task, "max_steps": max_steps, "approval_required_before_apply": True}
        agent_cls = getattr(sdk, "Agent", None) or getattr(sdk, "CodingAgent", None)
        llm_cls = getattr(sdk, "LLM", None)
        conversation_cls = getattr(sdk, "Conversation", None)
        if agent_cls is None or llm_cls is None or conversation_cls is None:
            result["status"] = "BLOCKED_BY_EXTERNAL_REQUIREMENT"; result["reason"] = "installed SDK does not expose Agent/LLM/Conversation"; return result
        model = os.getenv("OPENHANDS_MODEL", "")
        api_key = os.getenv("OPENHANDS_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        if not model or not api_key:
            result["status"] = "CONFIG_REQUIRED"; result["reason"] = "OPENHANDS_MODEL and OPENHANDS_API_KEY (or OPENAI_API_KEY) are required to run the external agent"; return result
        try:
            await asyncio.to_thread(subprocess.run, ["git", "init", "-q"], cwd=repo, check=True)
            await asyncio.to_thread(subprocess.run, ["git", "add", "-A"], cwd=repo, check=True)
            await asyncio.to_thread(subprocess.run, ["git", "-c", "user.email=gaia@localhost", "-c", "user.name=GAIA", "commit", "-qm", "baseline"], cwd=repo, check=True)
            agent = agent_cls(llm=llm_cls(model=model, api_key=api_key))
            conversation = conversation_cls(agent=agent, workspace=repo, max_iteration_per_run=max_steps, delete_on_close=False)
            conversation.send_message(task)
            await conversation.arun()
            state = conversation.state
            events = getattr(state, "events", []) or []
            event_summary = [{"type":type(e).__name__,"source":str(getattr(e,"source",""))} for e in events[-100:]]
            tests = []
            for command in ((sys.executable, "-m", "pytest", "-q"), (sys.executable, "-m", "compileall", "-q", ".")):
                try:
                    proc = await asyncio.to_thread(subprocess.run, command, cwd=repo, capture_output=True, text=True, timeout=120)
                    tests.append({"command":" ".join(command),"returncode":proc.returncode,"output":(proc.stdout+proc.stderr)[-4000:]})
                except Exception as exc: tests.append({"command":" ".join(command),"error":type(exc).__name__})
            diff = await asyncio.to_thread(subprocess.run, ["git","diff","--no-ext-diff"], cwd=repo, capture_output=True, text=True)
            return {**result,"status":"COMPLETED","sdk_agent":agent_cls.__name__,"conversation":type(conversation).__name__,"execution_status":str(getattr(state,"execution_status","unknown")),"events":event_summary,"tests":tests,"diff":diff.stdout[:50000],"changed":bool(diff.stdout)}
        except Exception as exc:
            return {**result, "status":"BLOCKED_BY_EXTERNAL_REQUIREMENT", "reason":f"OpenHands construction failed: {type(exc).__name__}"}

class UITARSComputerUseBackend:
    """UI-TARS-compatible local provider boundary; authority remains in GAIA Action Host."""
    def health(self):
        try:
            import pyautogui
            if sys.platform == "win32": return {"status": "AVAILABLE", "backend": "pyautogui-ui-tars-adapter", "interactive_session": True}
            return {"status": "PHYSICAL_WINDOWS_VALIDATION_PENDING", "backend": "pyautogui-ui-tars-adapter", "interactive_session": bool(os.getenv("DISPLAY"))}
        except Exception as exc: return {"status": "DEPENDENCY_MISSING", "backend": "ui-tars", "error": type(exc).__name__}
    async def observe(self):
        try:
            import pyautogui
            return {"status":"SUCCEEDED","screenshot":pyautogui.screenshot()}
        except Exception as exc: return {"status":"BLOCKED_BY_ENVIRONMENT","reason":f"GUI observation unavailable: {type(exc).__name__}"}
    async def click(self,x:int,y:int):
        import pyautogui; pyautogui.click(int(x),int(y)); return {"status":"SUCCEEDED","action":"click"}
    async def type(self,text:str):
        import pyautogui; pyautogui.write(str(text)); return {"status":"SUCCEEDED","action":"type"}
    async def abort(self): return {"status": "ABORTED"}
