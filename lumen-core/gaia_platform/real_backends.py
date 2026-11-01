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
    """Pipecat adapter. GAIA's production Desktop voice path is Core `/api/chat/voice`.

    This adapter no longer fabricates six empty processors. A caller must provide real
    Pipecat processors/transports, or build a pass-through contract pipeline explicitly
    for integration tests. This prevents a non-functional graph from being reported as
    realtime voice.
    """
    def __init__(self, vad: SileroVADBackend | None = None):
        self.vad=vad or SileroVADBackend(); self.pipeline=None; self.task=None; self.runner=None; self.pipeline_processors=[]; self.interrupted=False; self.production_configured=False
    def health(self):
        try:
            import pipecat
            return {"status":"AVAILABLE" if self.production_configured else "CONFIG_REQUIRED","backend":"pipecat","version":"1.12.0","vad":self.vad.health(),"production_configured":self.production_configured,"desktop_voice_path":"/api/chat/voice"}
        except Exception as exc:return {"status":"DEPENDENCY_MISSING","backend":"pipecat","error":type(exc).__name__}
    def build_pipeline(self, processors: list[Any] | None = None, *, test_passthrough: bool = False):
        try:
            from pipecat.pipeline.pipeline import Pipeline
            from pipecat.pipeline.task import PipelineParams, PipelineTask
            from pipecat.pipeline.runner import PipelineRunner
            if processors:
                self.pipeline_processors=list(processors); self.production_configured=True
            elif test_passthrough:
                from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
                class ForwardingStage(FrameProcessor):
                    def __init__(self, stage_name: str): super().__init__(name=stage_name); self.stage_name=stage_name; self.frames_seen=0
                    async def process_frame(self, frame, direction: FrameDirection):
                        await super().process_frame(frame,direction); self.frames_seen+=1; await self.push_frame(frame,direction)
                self.pipeline_processors=[ForwardingStage('gaia-contract-input'),ForwardingStage('gaia-contract-output')]
                self.production_configured=False
            else:
                raise BackendUnavailable('Real Pipecat processors/transports must be provided; empty placeholder pipeline is forbidden')
            self.pipeline=Pipeline(self.pipeline_processors); self.task=PipelineTask(self.pipeline,params=PipelineParams(enable_metrics=True)); self.runner_cls=PipelineRunner; self.runner=None; return self.task
        except BackendUnavailable: raise
        except Exception as exc: raise BackendUnavailable(f'Pipecat pipeline creation failed: {exc}') from exc
    async def start(self):
        if self.task is None or not self.production_configured: raise BackendUnavailable('Pipecat production pipeline is not configured')
        if self.runner is None:self.runner=self.runner_cls()
        self._runner_task=asyncio.create_task(asyncio.to_thread(self.runner.run,self.task,auto_end=False),name='gaia-pipecat-runner')
        return {"status":"RUNNING","pipeline":type(self.pipeline).__name__,"task":type(self.task).__name__,"processors":[type(p).__name__ for p in self.pipeline_processors]}
    async def interrupt(self,reason='barge_in'):
        self.interrupted=True
        if self.task is not None:
            try:
                from pipecat.frames.frames import InterruptionFrame
                await self.task.queue_frame(InterruptionFrame())
            except Exception:
                try: await self.task.cancel(reason=reason)
                except Exception: pass
        return {"status":"INTERRUPTED","event":"INTERRUPTED","reason":reason}
    async def stop(self):
        if self.task is not None:
            try: await self.task.stop()
            except Exception: pass
        runner_task=getattr(self,'_runner_task',None)
        if runner_task and not runner_task.done(): runner_task.cancel()
        self.pipeline=None; self.task=None; self.runner=None; self.production_configured=False; return {"status":"STOPPED"}

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
    """Mem0 provider executed in an isolated Python 3.11 sidecar.

    Browser Use pins posthog==7.7.0 while Mem0 2.2.1 requires posthog>=7.14.0,
    therefore importing both into GAIA's main venv is intentionally forbidden.
    """
    def __init__(self, config: dict[str, Any] | None = None):
        self.config=config or {}
        root=Path(__file__).resolve().parents[2]
        default=root/'.venv-memory'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        self.python=Path(os.getenv('GAIA_MEM0_PYTHON',str(default))).expanduser()
        self.worker=root/'tools'/'sidecars'/'mem0_worker.py'
    def _call(self,payload:dict[str,Any],*,timeout:int=120):
        if not self.python.is_file() or not self.worker.is_file(): raise BackendUnavailable('Mem0 sidecar is not installed')
        if self.config: payload={**payload,'config':self.config}
        try:
            proc=subprocess.run([str(self.python),str(self.worker)],input=json.dumps(payload),capture_output=True,text=True,timeout=timeout)
        except Exception as exc: raise BackendUnavailable(f'Mem0 sidecar failed: {exc}') from exc
        raw=(proc.stdout or '').strip().splitlines()
        try: data=json.loads(raw[-1] if raw else '{}')
        except Exception as exc: raise BackendUnavailable(f'Mem0 sidecar returned invalid JSON: {proc.stderr[-500:]}') from exc
        if proc.returncode!=0 or data.get('status') in {'ERROR'}: raise BackendUnavailable(data.get('detail') or data.get('reason') or data.get('error') or 'Mem0 sidecar failed')
        return data
    def health(self):
        try:
            data=self._call({'action':'health'},timeout=20)
            data['configured']=bool(self.config or os.getenv('MEM0_CONFIG_JSON'))
            return data
        except Exception as exc:return {'status':'DEPENDENCY_MISSING','backend':'mem0ai-sidecar','error':type(exc).__name__,'python':str(self.python)}
    def _scope(self,owner:str,namespace:str,project:str=''): return {'owner':owner,'namespace':namespace,'project':project}
    def add(self,content:str,*,owner:str,namespace:str,session:str,project:str=''):
        return self._call({'action':'add','content':content,'session':session,**self._scope(owner,namespace,project)}).get('result')
    def search(self,query:str,*,owner:str,namespace:str,project:str='',limit:int=8):
        return self._call({'action':'search','query':query,'limit':limit,**self._scope(owner,namespace,project)}).get('result')
    def _get_record(self,memory_id:str): return self._call({'action':'get','memory_id':memory_id}).get('result')
    def _verify_owned(self,memory_id:str,*,owner:str,namespace:str,project:str)->None:
        record=self._get_record(memory_id)
        metadata=record.get('metadata') if isinstance(record,dict) and isinstance(record.get('metadata'),dict) else (record if isinstance(record,dict) else {})
        expected={'gaia_owner':owner,'gaia_namespace':namespace,'gaia_project':project}
        if any(str(metadata.get(k,''))!=str(v) for k,v in expected.items()): raise PermissionError('Mem0 owner/namespace/project mismatch; mutation denied')
    def update(self,memory_id:str,text:str,*,owner:str,namespace:str,project:str=''):
        self._verify_owned(memory_id,owner=owner,namespace=namespace,project=project)
        return self._call({'action':'update','memory_id':memory_id,'text':text,**self._scope(owner,namespace,project)}).get('result')
    def delete(self,memory_id:str,*,owner:str,namespace:str='',project:str=''):
        self._verify_owned(memory_id,owner=owner,namespace=namespace,project=project)
        return self._call({'action':'delete','memory_id':memory_id,**self._scope(owner,namespace,project)}).get('result')
    def cleanup(self,*,owner:str,namespace:str,project:str=''):
        rows=self._call({'action':'get_all','limit':1000,**self._scope(owner,namespace,project)}).get('result') or []
        seq=rows if isinstance(rows,list) else rows.get('results',[]) if isinstance(rows,dict) else []
        count=0
        for row in seq:
            mid=row.get('id') or row.get('memory_id') if isinstance(row,dict) else None
            if mid:self.delete(mid,owner=owner,namespace=namespace,project=project);count+=1
        return {'status':'CLEANED','count':count}

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
    """OpenHands SDK adapter through an isolated Python 3.12 sidecar."""
    def __init__(self, workspace_root: Path):
        self.workspace_root=Path(workspace_root).resolve(); self.workspace_root.mkdir(parents=True,exist_ok=True)
        root=Path(__file__).resolve().parents[2]
        default=root/'.venv-coding'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        self.python=Path(os.getenv('GAIA_OPENHANDS_PYTHON',str(default))).expanduser()
        self.worker=root/'tools'/'sidecars'/'openhands_worker.py'
    def _call(self,payload:dict[str,Any],*,timeout:int=900):
        if not self.python.is_file() or not self.worker.is_file(): raise BackendUnavailable('OpenHands Python 3.12 sidecar is not installed')
        try:
            proc=subprocess.run([str(self.python),str(self.worker)],input=json.dumps(payload),capture_output=True,text=True,timeout=timeout)
        except Exception as exc: raise BackendUnavailable(f'OpenHands sidecar failed: {exc}') from exc
        raw=(proc.stdout or '').strip().splitlines()
        try:data=json.loads(raw[-1] if raw else '{}')
        except Exception as exc: raise BackendUnavailable(f'OpenHands sidecar returned invalid JSON: {proc.stderr[-500:]}') from exc
        if proc.returncode not in (0,3) or data.get('status')=='ERROR': raise BackendUnavailable(data.get('detail') or data.get('error') or 'OpenHands sidecar failed')
        return data
    def health(self):
        try:return self._call({'action':'health'},timeout=20)
        except Exception as exc:return {'status':'DEPENDENCY_MISSING','backend':'openhands-sdk-sidecar','error':type(exc).__name__,'python':str(self.python)}
    async def run(self,task:str,source:Path,*,max_steps:int=20,approved:bool=False)->dict[str,Any]:
        if not approved:return {'status':'WAITING_PERMISSION','approval_required':True}
        target=Path(tempfile.mkdtemp(prefix='gaia-openhands-',dir=self.workspace_root)); repo=target/'repo'; shutil.copytree(source,repo,ignore=shutil.ignore_patterns('.git','.venv','data','secrets','tokens'))
        result={'workspace':str(repo),'backend':'openhands-sdk-sidecar','task':task,'max_steps':max_steps,'approval_required_before_apply':True}
        model=os.getenv('OPENHANDS_MODEL',''); api_key=os.getenv('OPENHANDS_API_KEY','') or os.getenv('OPENAI_API_KEY',''); base_url=os.getenv('OPENHANDS_BASE_URL','')
        if not model:return {**result,'status':'CONFIG_REQUIRED','reason':'OPENHANDS_MODEL is required'}
        try:
            await asyncio.to_thread(subprocess.run,['git','init','-q'],cwd=repo,check=True)
            await asyncio.to_thread(subprocess.run,['git','add','-A'],cwd=repo,check=True)
            await asyncio.to_thread(subprocess.run,['git','-c','user.email=gaia@localhost','-c','user.name=GAIA','commit','-qm','baseline'],cwd=repo,check=True)
            side=await asyncio.to_thread(self._call,{'action':'run','repo':str(repo),'task':task,'max_steps':max_steps,'model':model,'api_key':api_key,'base_url':base_url},timeout=900)
            if side.get('status')!='COMPLETED':return {**result,**side}
            tests=[]
            for command in ((sys.executable,'-m','pytest','-q'),(sys.executable,'-m','compileall','-q','.')):
                try:
                    proc=await asyncio.to_thread(subprocess.run,command,cwd=repo,capture_output=True,text=True,timeout=120)
                    tests.append({'command':' '.join(command),'returncode':proc.returncode,'output':(proc.stdout+proc.stderr)[-4000:]})
                except Exception as exc:tests.append({'command':' '.join(command),'error':type(exc).__name__})
            diff=await asyncio.to_thread(subprocess.run,['git','diff','--no-ext-diff'],cwd=repo,capture_output=True,text=True)
            return {**result,**side,'tests':tests,'diff':diff.stdout[:50000],'changed':bool(diff.stdout)}
        except Exception as exc:return {**result,'status':'BLOCKED_BY_EXTERNAL_REQUIREMENT','reason':f'OpenHands execution failed: {type(exc).__name__}: {exc}'}

class PyAutoGUIComputerUseBackend:
    """Deterministic coordinate-level fallback for Windows Computer Use.

    This is intentionally NOT called UI-TARS. Visual reasoning providers may be added
    separately; GAIA Authority/Action Host remain the only execution gate.
    """
    def health(self):
        try:
            import pyautogui
            return {"status":"AVAILABLE" if sys.platform=='win32' else "PHYSICAL_WINDOWS_VALIDATION_PENDING","backend":"pyautogui","interactive_session":sys.platform=='win32' or bool(os.getenv('DISPLAY'))}
        except Exception as exc:return {"status":"DEPENDENCY_MISSING","backend":"pyautogui","error":type(exc).__name__}
    async def observe(self):
        try:
            import pyautogui
            target=Path(tempfile.mkstemp(prefix='gaia-screen-',suffix='.png')[1]); pyautogui.screenshot(str(target)); return {"status":"SUCCEEDED","backend":"pyautogui","screenshot":str(target)}
        except Exception as exc:return {"status":"BLOCKED_BY_ENVIRONMENT","reason":f'GUI observation unavailable: {type(exc).__name__}'}
    async def click(self,x:int,y:int):
        import pyautogui; pyautogui.click(int(x),int(y)); return {"status":"SUCCEEDED","action":"click"}
    async def double_click(self,x:int,y:int):
        import pyautogui; pyautogui.doubleClick(int(x),int(y)); return {"status":"SUCCEEDED","action":"double_click"}
    async def right_click(self,x:int,y:int):
        import pyautogui; pyautogui.rightClick(int(x),int(y)); return {"status":"SUCCEEDED","action":"right_click"}
    async def type(self,text:str,interval:float=0.01):
        import pyautogui; pyautogui.write(str(text),interval=max(0.0,float(interval))); return {"status":"SUCCEEDED","action":"type"}
    async def hotkey(self,*keys:str):
        import pyautogui; pyautogui.hotkey(*[str(k) for k in keys]); return {"status":"SUCCEEDED","action":"hotkey","keys":list(keys)}
    async def scroll(self,clicks:int,x:int|None=None,y:int|None=None):
        import pyautogui; pyautogui.scroll(int(clicks),x=x,y=y); return {"status":"SUCCEEDED","action":"scroll"}
    async def drag(self,x1:int,y1:int,x2:int,y2:int,duration:float=.3):
        import pyautogui; pyautogui.moveTo(int(x1),int(y1)); pyautogui.dragTo(int(x2),int(y2),duration=max(.05,float(duration)),button='left'); return {"status":"SUCCEEDED","action":"drag"}
    async def wait(self,seconds:float): await asyncio.sleep(min(30,max(0,float(seconds)))); return {"status":"SUCCEEDED","action":"wait"}
    async def abort(self): return {"status":"ABORTED"}

class WindowsUIAutomationBackend:
    """Windows-native UI Automation inspection/invocation via pywinauto."""
    def health(self):
        if sys.platform!='win32': return {"status":"PHYSICAL_WINDOWS_VALIDATION_PENDING","backend":"windows-uia"}
        try:
            import pywinauto
            return {"status":"AVAILABLE","backend":"windows-uia"}
        except Exception as exc:return {"status":"DEPENDENCY_MISSING","backend":"windows-uia","error":type(exc).__name__}
    def _desktop(self):
        from pywinauto import Desktop
        return Desktop(backend='uia')
    async def active_window(self):
        if sys.platform!='win32': return {"status":"BLOCKED_BY_ENVIRONMENT"}
        import win32gui
        handle=win32gui.GetForegroundWindow(); win=self._desktop().window(handle=handle)
        return {"status":"SUCCEEDED","backend":"windows-uia","handle":int(handle),"title":win.window_text(),"control_type":win.element_info.control_type}
    async def invoke(self,*,title:str='',auto_id:str='',control_type:str='Button'):
        if sys.platform!='win32': return {"status":"BLOCKED_BY_ENVIRONMENT"}
        root=self._desktop().window(handle=__import__('win32gui').GetForegroundWindow())
        kwargs={"control_type":control_type}
        if title: kwargs['title']=title
        if auto_id: kwargs['auto_id']=auto_id
        control=root.child_window(**kwargs).wrapper_object()
        if hasattr(control,'invoke'): control.invoke()
        else: control.click_input()
        return {"status":"SUCCEEDED","backend":"windows-uia","action":"invoke","title":title,"auto_id":auto_id}
    async def set_value(self,text:str,*,title:str='',auto_id:str='',control_type:str='Edit'):
        if sys.platform!='win32': return {"status":"BLOCKED_BY_ENVIRONMENT"}
        root=self._desktop().window(handle=__import__('win32gui').GetForegroundWindow()); kwargs={"control_type":control_type}
        if title: kwargs['title']=title
        if auto_id: kwargs['auto_id']=auto_id
        control=root.child_window(**kwargs).wrapper_object(); control.set_edit_text(str(text)); return {"status":"SUCCEEDED","backend":"windows-uia","action":"set_value"}

class WindowsComputerUseRouter:
    """Deterministic Windows router: UI Automation first, coordinate fallback second.

    This provider contains no policy authority; callers must pass GAIA authorization
    before invoking side effects. Visual Agent-S/UI-TARS providers remain optional.
    """
    def __init__(self):
        self.uia=WindowsUIAutomationBackend(); self.coordinates=PyAutoGUIComputerUseBackend()
    def health(self):
        return {"status":"AVAILABLE" if sys.platform=='win32' else "PHYSICAL_WINDOWS_VALIDATION_PENDING","backend":"windows-deterministic-router","priority":["windows-uia","pyautogui"],"uia":self.uia.health(),"coordinates":self.coordinates.health()}
    async def observe(self):
        active=await self.uia.active_window() if sys.platform=='win32' else {"status":"BLOCKED_BY_ENVIRONMENT"}
        screen=await self.coordinates.observe()
        return {"status":"SUCCEEDED" if active.get("status")=="SUCCEEDED" or screen.get("status")=="SUCCEEDED" else "BLOCKED_BY_ENVIRONMENT","backend":"windows-deterministic-router","active_window":active,"screen":screen}
    async def invoke(self,**selector): return await self.uia.invoke(**selector)
    async def set_value(self,text:str,**selector): return await self.uia.set_value(text,**selector)
    async def click(self,x:int,y:int): return await self.coordinates.click(x,y)
    async def double_click(self,x:int,y:int): return await self.coordinates.double_click(x,y)
    async def right_click(self,x:int,y:int): return await self.coordinates.right_click(x,y)
    async def type(self,text:str,interval:float=.01): return await self.coordinates.type(text,interval)
    async def hotkey(self,*keys:str): return await self.coordinates.hotkey(*keys)
    async def scroll(self,clicks:int,x:int|None=None,y:int|None=None): return await self.coordinates.scroll(clicks,x,y)
    async def drag(self,x1:int,y1:int,x2:int,y2:int,duration:float=.3): return await self.coordinates.drag(x1,y1,x2,y2,duration)
    async def wait(self,seconds:float): return await self.coordinates.wait(seconds)
    async def abort(self): return await self.coordinates.abort()

# Backward-compatible symbol only. Health/reporting remains honest: backend=pyautogui.
UITARSComputerUseBackend = PyAutoGUIComputerUseBackend

