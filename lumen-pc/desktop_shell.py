"""GAIA resident Desktop Shell. The UI is a client; GAIA Core remains authority."""
from __future__ import annotations
import ctypes, json, os, platform, sys, tempfile, threading, time, wave, webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from PySide6.QtCore import QObject, Qt, Signal
    from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QDialog, QFormLayout, QLabel, QLineEdit, QMenu, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False
    class QObject: pass
    class Signal:
        def __init__(self,*a,**k): pass
    QAction=QColor=QIcon=QPainter=QPixmap=QApplication=QDialog=QFormLayout=QLabel=QLineEdit=QMenu=QPushButton=QSystemTrayIcon=QVBoxLayout=QWidget=None

try:
    import httpx
except ImportError:
    httpx = None
try:
    import sounddevice as sd
except ImportError:
    sd = None
try:
    import numpy as np
except ImportError:
    np = None
try:
    import soundfile as sf
except ImportError:
    sf = None

CORE_DEFAULT = os.getenv("LUMEN_CORE_URL", "http://127.0.0.1:8090").rstrip("/")
RESTART_EXIT_CODE = 75

@dataclass
class ShellConfig:
    core_url: str = CORE_DEFAULT
    secret: str = os.getenv("LUMEN_SECRET", "")
    orb_size: int = int(os.getenv("GAIA_ORB_SIZE", "72"))
    corner: str = os.getenv("GAIA_ORB_CORNER", "bottom-right")
    orb_mode: str = os.getenv("GAIA_ORB_MODE", "wake_only").lower()
    wake_word: bool = os.getenv("GAIA_WAKEWORD_ENABLED", "false").lower() in {"1","true","yes"}
    microphone: bool = os.getenv("GAIA_MICROPHONE_ENABLED", "true").lower() in {"1","true","yes"}
    ptt_hotkey: str = os.getenv("GAIA_PUSH_TO_TALK", "Ctrl+Space")
    quick_hotkey: str = os.getenv("GAIA_QUICK_COMMAND_HOTKEY", "Win+Shift+G")

class DesktopEventClient:
    """Bounded SSE client. It never touches Qt widgets directly."""
    def __init__(self, url: str, secret: str, on_event: Callable[[dict],None], *, backoff_max: float=30.0):
        self.url=url.rstrip("/")+"/api/visualizer/events"; self.secret=secret; self.on_event=on_event; self.backoff_max=backoff_max
        self._stop=threading.Event(); self.thread=None; self.connected=False
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self._stop.clear(); self.thread=threading.Thread(target=self._run,name="gaia-event-client",daemon=True); self.thread.start()
    def _run(self):
        delay=1.0
        while not self._stop.is_set():
            try:
                if httpx is None: raise RuntimeError("httpx unavailable")
                timeout=httpx.Timeout(connect=5.0,read=None,write=5.0,pool=5.0)
                headers={"Authorization":f"Bearer {self.secret}"} if self.secret else {}
                with httpx.stream("GET",self.url,headers=headers,timeout=timeout) as response:
                    response.raise_for_status(); self.connected=True; delay=1.0; event_name="message"
                    self.on_event({"state":"IDLE","source":"event_client","connected":True})
                    for line in response.iter_lines():
                        if self._stop.is_set(): break
                        if not line: continue
                        if line.startswith("event:"): event_name=line.split(":",1)[1].strip()
                        elif line.startswith("data:"):
                            try: payload=json.loads(line.split(":",1)[1].strip())
                            except Exception: continue
                            if isinstance(payload,dict): payload.setdefault("event",event_name); self.on_event(payload)
            except Exception as exc:
                self.connected=False; self.on_event({"state":"OFFLINE","source":"event_client","error":type(exc).__name__})
                self._stop.wait(delay); delay=min(self.backoff_max,delay*2)
    def stop(self):
        self._stop.set()
        if self.thread and self.thread is not threading.current_thread(): self.thread.join(timeout=2)
        self.thread=None; self.connected=False

class GlobalHotkey:
    """Real Win32 RegisterHotKey implementation with release detection for hold-to-talk."""
    MODS={"ALT":0x0001,"CTRL":0x0002,"CONTROL":0x0002,"SHIFT":0x0004,"WIN":0x0008,"WINDOWS":0x0008}
    KEYS={"SPACE":0x20,"ENTER":0x0D,"ESC":0x1B,"TAB":0x09}
    WM_HOTKEY=0x0312; WM_QUIT=0x0012
    def __init__(self,on_down:Callable[[],None],on_up:Callable[[],None],key:str="Ctrl+Space",hotkey_id:int=0x4741):
        self.on_down=on_down; self.on_up=on_up; self.key=key; self.hotkey_id=hotkey_id
        self.registered=False; self._pressed=False; self._thread=None; self._thread_id=0; self._ready=threading.Event(); self._result={"status":"UNREGISTERED"}
        self.modifiers,self.vk=self._parse(key)
    @classmethod
    def _parse(cls,key:str):
        parts=[p.strip().upper() for p in key.replace("-","+").split("+") if p.strip()]
        if not parts: raise ValueError("empty hotkey")
        mods=0
        for p in parts[:-1]:
            if p not in cls.MODS: raise ValueError(f"unsupported modifier: {p}")
            mods |= cls.MODS[p]
        last=parts[-1]
        if last in cls.KEYS: vk=cls.KEYS[last]
        elif len(last)==1 and last.isalnum(): vk=ord(last)
        elif last.startswith("F") and last[1:].isdigit() and 1<=int(last[1:])<=24: vk=0x70+int(last[1:])-1
        else: raise ValueError(f"unsupported key: {last}")
        return mods,vk
    def register(self):
        if platform.system()!="Windows":
            return {"status":"PHYSICAL_WINDOWS_VALIDATION_PENDING","backend":"win32-registerhotkey","key":self.key}
        if self._thread and self._thread.is_alive(): return self._result
        self._ready.clear(); self._thread=threading.Thread(target=self._message_loop,name=f"gaia-hotkey-{self.hotkey_id}",daemon=True); self._thread.start(); self._ready.wait(3)
        return dict(self._result)
    def _message_loop(self):
        user32=ctypes.windll.user32; kernel32=ctypes.windll.kernel32
        self._thread_id=int(kernel32.GetCurrentThreadId())
        ok=bool(user32.RegisterHotKey(None,self.hotkey_id,self.modifiers,self.vk))
        if not ok:
            self.registered=False; self._result={"status":"HOTKEY_CONFLICT","backend":"RegisterHotKey","key":self.key,"winerror":int(kernel32.GetLastError())}; self._ready.set(); return
        self.registered=True; self._result={"status":"REGISTERED","backend":"RegisterHotKey","key":self.key}; self._ready.set()
        class MSG(ctypes.Structure):
            _fields_=[("hwnd",ctypes.c_void_p),("message",ctypes.c_uint),("wParam",ctypes.c_size_t),("lParam",ctypes.c_ssize_t),("time",ctypes.c_uint),("pt_x",ctypes.c_long),("pt_y",ctypes.c_long),("lPrivate",ctypes.c_uint)]
        msg=MSG()
        while user32.GetMessageW(ctypes.byref(msg),None,0,0)>0:
            if msg.message==self.WM_HOTKEY and int(msg.wParam)==self.hotkey_id:
                if not self._pressed:
                    self._pressed=True
                    try: self.on_down()
                    except Exception: pass
                    threading.Thread(target=self._watch_release,name=f"gaia-hotkey-release-{self.hotkey_id}",daemon=True).start()
        user32.UnregisterHotKey(None,self.hotkey_id); self.registered=False; self._pressed=False
    def _watch_release(self):
        if platform.system()!="Windows": return
        user32=ctypes.windll.user32
        # RegisterHotKey has no key-up event; polling the primary key preserves hold-to-talk semantics.
        while self.registered and (user32.GetAsyncKeyState(self.vk)&0x8000): time.sleep(0.015)
        if self._pressed:
            self._pressed=False
            try: self.on_up()
            except Exception: pass
    def dispatch(self,event:str):
        # deterministic test hook; never pretends to register with the OS.
        if event=="down" and not self._pressed: self._pressed=True; self.on_down(); return True
        if event=="up" and self._pressed: self._pressed=False; self.on_up(); return True
        return False
    def unregister(self):
        if platform.system()=="Windows" and self._thread_id:
            try: ctypes.windll.user32.PostThreadMessageW(self._thread_id,self.WM_QUIT,0,0)
            except Exception: pass
        if self._thread and self._thread is not threading.current_thread(): self._thread.join(timeout=2)
        self._thread=None; self._thread_id=0; self.registered=False; self._pressed=False

class AudioCapture:
    """Hold-to-talk capture. stop() finalizes a WAV and invokes on_audio exactly once."""
    def __init__(self,on_audio:Callable[[Path],Any],sample_rate:int=16000):
        self.on_audio=on_audio; self.sample_rate=sample_rate; self.recording=False; self._stream=None; self._frames=[]; self._lock=threading.Lock()
    def start(self):
        if sd is None or np is None: raise RuntimeError("sounddevice/numpy unavailable")
        if self.recording: return {"status":"ALREADY_CAPTURING"}
        with self._lock: self._frames=[]
        def callback(indata,frames,time_info,status):
            if self.recording:
                with self._lock: self._frames.append(indata.copy())
        self._stream=sd.InputStream(samplerate=self.sample_rate,channels=1,dtype="int16",callback=callback)
        self._stream.start(); self.recording=True; return {"status":"CAPTURING","sample_rate":self.sample_rate}
    def stop(self):
        if not self.recording:
            return {"status":"IDLE"}
        self.recording=False
        stream=self._stream; self._stream=None
        try:
            if stream is not None: stream.stop(); stream.close()
        finally:
            with self._lock:
                frames=list(self._frames); self._frames=[]
        if not frames: return {"status":"EMPTY"}
        audio=np.concatenate(frames,axis=0).astype("int16",copy=False)
        with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as tmp: path=Path(tmp.name)
        with wave.open(str(path),"wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(self.sample_rate); wav.writeframes(audio.tobytes())
        threading.Thread(target=self.on_audio,args=(path,),name="gaia-captured-audio",daemon=True).start()
        return {"status":"FINALIZED","path":str(path),"frames":int(audio.shape[0])}

class AudioPlayer:
    """Single-owner cancellable local player using soundfile + sounddevice."""
    def __init__(self): self._stop=threading.Event(); self._thread=None; self._lock=threading.Lock()
    @property
    def playing(self): return bool(self._thread and self._thread.is_alive())
    def play(self,path:Path,on_done:Callable[[],None]|None=None,on_error:Callable[[str],None]|None=None):
        if sd is None or sf is None: raise RuntimeError("sounddevice/soundfile unavailable")
        self.stop(); self._stop.clear()
        def worker():
            try:
                data,rate=sf.read(str(path),dtype="float32",always_2d=True)
                if self._stop.is_set(): return
                sd.play(data,rate,blocking=False)
                while not self._stop.wait(.03):
                    try:
                        stream=sd.get_stream()
                        if not getattr(stream,"active",False): break
                    except Exception: break
                if self._stop.is_set(): sd.stop()
                elif on_done: on_done()
            except Exception as exc:
                if on_error: on_error(f"{type(exc).__name__}: {exc}")
            finally:
                try: path.unlink(missing_ok=True)
                except Exception: pass
        self._thread=threading.Thread(target=worker,name="gaia-audio-player",daemon=True); self._thread.start()
    def stop(self):
        self._stop.set()
        if sd is not None:
            try: sd.stop()
            except Exception: pass
        t=self._thread
        if t and t is not threading.current_thread(): t.join(timeout=1)
        self._thread=None


class BargeInMonitor:
    """Local Silero monitor active only while GAIA is speaking."""
    def __init__(self,on_barge:Callable[[],None],sample_rate:int=16000):
        self.on_barge=on_barge; self.sample_rate=sample_rate; self._stop=threading.Event(); self._thread=None
    @property
    def running(self): return bool(self._thread and self._thread.is_alive())
    def start(self):
        if self.running or sd is None:return False
        self._stop.clear(); self._thread=threading.Thread(target=self._run,name="gaia-barge-in",daemon=True); self._thread.start(); return True
    def _run(self):
        try:
            import torch
            from silero_vad import load_silero_vad, VADIterator
            vad=VADIterator(load_silero_vad(),sampling_rate=self.sample_rate,threshold=float(os.getenv("GAIA_BARGE_IN_THRESHOLD","0.7")),min_silence_duration_ms=150)
            with sd.InputStream(samplerate=self.sample_rate,channels=1,dtype="int16",blocksize=512) as stream:
                while not self._stop.is_set():
                    data,_overflowed=stream.read(512); chunk=data[:,0]
                    event=vad(torch.from_numpy(chunk.astype(np.float32)/32768.0),return_seconds=True)
                    if event and "start" in event:
                        try:self.on_barge()
                        finally:break
            try:vad.reset_states()
            except Exception:pass
        except Exception:
            return
    def stop(self):
        self._stop.set(); t=self._thread
        if t and t is not threading.current_thread():t.join(timeout=.7)
        self._thread=None

if PYSIDE_AVAILABLE:
    class QtBridge(QObject):
        core_event=Signal(object); wake_audio=Signal(object); voice_result=Signal(object); voice_error=Signal(str)
        quick_result=Signal(object); quick_error=Signal(str); hotkey_action=Signal(str); playback_done=Signal(); playback_error=Signal(str); barge_in=Signal()
else:
    class QtBridge: pass

class PermissionDialog(QDialog if PYSIDE_AVAILABLE else object):
    def __init__(self,request:dict,decide:Callable[[str,str],Any]):
        if not PYSIDE_AVAILABLE: raise RuntimeError("PySide6 required for permission dialog")
        super().__init__(); self.request=request; self.decide=decide; self.setWindowTitle("GAIA permission request")
        layout=QVBoxLayout(self); form=QFormLayout()
        for key in ("action","risk","capability","target","scope","originating_task"):
            form.addRow(key,QLabel(str(request.get(key,""))))
        layout.addLayout(form)
        for label,decision in (("ALLOW ONCE","ALLOW_ONCE"),("ALLOW SESSION/SCOPE","ALWAYS_ALLOW"),("DENY","DENY")):
            b=QPushButton(label); b.clicked.connect(lambda _=False,d=decision:self._finish(d)); layout.addWidget(b)
    def _finish(self,decision): self.decide(str(self.request.get("request_id","")),decision); self.accept()

class DesktopShell:
    def __init__(self,config:ShellConfig|None=None,api=None):
        self.config=config or ShellConfig(); self.api=api; self.running=False; self.qt=False; self.app=None; self.tray=None; self.orb=None; self.wake=None
        self.quick_command_window=None; self.permission_dialog=None; self.state="SLEEPING"; self._microphone_on=self.config.microphone; self._shutdown=threading.Event(); self.bridge=None
        self.events=DesktopEventClient(self.config.core_url,self.config.secret,self._queue_core_event)
        self.ptt_hotkey=GlobalHotkey(lambda:self._queue_hotkey("ptt_down"),lambda:self._queue_hotkey("ptt_up"),self.config.ptt_hotkey,0x4741)
        self.quick_hotkey=GlobalHotkey(lambda:self._queue_hotkey("quick"),lambda:None,self.config.quick_hotkey,0x4742)
        self.capture=AudioCapture(self._on_captured_audio); self.player=AudioPlayer(); self.barge=BargeInMonitor(lambda:self.bridge.barge_in.emit() if self.bridge is not None else None)
        if self.api is None:
            try:
                from desktop_api import LumenDesktopAPI
                self.api=LumenDesktopAPI(base_url=self.config.core_url,secret=self.config.secret or os.getenv("LUMEN_SECRET","lumen-dev-key"))
            except Exception: self.api=None
    def health(self):
        return {"status":"PASS" if PYSIDE_AVAILABLE else "DEPENDENCY_MISSING","ui":"PySide6" if PYSIDE_AVAILABLE else "MISSING_DEPENDENCY","event_client":self.events.connected,"wake_word":self.config.wake_word,"microphone":self._microphone_on,"ptt_hotkey":self.ptt_hotkey.registered,"quick_hotkey":self.quick_hotkey.registered,"authority":"GAIA Core"}
    def _queue_core_event(self,event):
        if self.bridge is not None: self.bridge.core_event.emit(event)
    def _queue_hotkey(self,action):
        if self.bridge is not None: self.bridge.hotkey_action.emit(action)
    def _set_state(self,state):
        self.state=str(state).upper()
        if self.orb is not None: self.orb.set_state(self.state)
        if self.tray is not None: self.tray.setToolTip(f"GAIA — {self.state}")
    def _on_core_event_gui(self,event):
        state=str(event.get("state") or event.get("event_type") or "IDLE").upper().replace(".","_")
        mapping={"USING_TOOL":"EXECUTING","SEARCHING_MEMORY":"THINKING","CORE_READY":"IDLE","CONNECTED":"IDLE"}
        allowed={"IDLE","LISTENING","TRANSCRIBING","THINKING","PLANNING","BROWSING","CODING","EXECUTING","SPEAKING","WAITING_PERMISSION","INTERRUPTED","SAFE_MODE","ERROR","OFFLINE"}
        self._set_state(mapping.get(state,state if state in allowed else "IDLE"))
        if state=="WAITING_PERMISSION": self._show_permission(event.get("metadata") or event)
        if state=="IDLE" and self.config.orb_mode=="wake_only" and not self.capture.recording and not self.player.playing: self._hide_orb()
    def _icon(self):
        pix=QPixmap(32,32); pix.fill(QColor("#101828")); p=QPainter(pix); p.setBrush(QColor("#45d9ff")); p.setPen(QColor("#a98bff")); p.drawEllipse(5,5,22,22); p.end(); return QIcon(pix)
    def start(self,hidden=True):
        if not PYSIDE_AVAILABLE: raise RuntimeError("PySide6 is required for resident shell; install the Desktop/Full profile")
        self.app=QApplication.instance() or QApplication(sys.argv); self.app.setQuitOnLastWindowClosed(False); self.qt=True; shell=self
        self.bridge=QtBridge(); self.bridge.core_event.connect(self._on_core_event_gui); self.bridge.wake_audio.connect(self._handle_wake_audio_gui)
        self.bridge.voice_result.connect(self._handle_voice_result_gui); self.bridge.voice_error.connect(self._handle_error_gui); self.bridge.quick_result.connect(self._handle_quick_result_gui); self.bridge.quick_error.connect(self._handle_error_gui)
        self.bridge.hotkey_action.connect(self._handle_hotkey_gui); self.bridge.playback_done.connect(self._playback_done_gui); self.bridge.playback_error.connect(self._handle_error_gui); self.bridge.barge_in.connect(self._barge_in_gui)
        class Orb(QWidget):
            def __init__(inner):
                super().__init__(); inner.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool|Qt.WindowDoesNotAcceptFocus); inner.setAttribute(Qt.WA_TranslucentBackground); inner.resize(shell.config.orb_size,shell.config.orb_size); inner.state="SLEEPING"
            def set_state(inner,state): inner.state=state; inner.update()
            def paintEvent(inner,_):
                p=QPainter(inner); p.setRenderHint(QPainter.Antialiasing); colors={"ERROR":"#ff526b","WAITING_PERMISSION":"#ffcc66","SAFE_MODE":"#aa8cff","LISTENING":"#55e6ff","THINKING":"#8f7cff","SPEAKING":"#65a8ff","OFFLINE":"#77808f","INTERRUPTED":"#ff8b5c","TRANSCRIBING":"#7ae6c4","CODING":"#b17cff","BROWSING":"#4fc3ff"}; p.setBrush(QColor(colors.get(inner.state,"#277dff"))); p.setPen(Qt.NoPen); p.drawEllipse(8,8,inner.width()-16,inner.height()-16)
        self.orb=Orb(); self._position_orb(); self.tray=QSystemTrayIcon(self.app); self.tray.setIcon(self._icon()); self.tray.setToolTip("GAIA — Resident Desktop Assistant"); menu=QMenu()
        for title,fn in (("Open GAIA",self.show_quick),("Quick Command",self.show_quick),("Open Dashboard",self.open_dashboard),("Wake word ON/OFF",self.toggle_wake),("Microphone ON/OFF",self.toggle_mic),("Push-to-talk",self.push_to_talk),("Status",self.show_status),("Restart GAIA",self.restart),("Exit GAIA",self.stop)): self._add_action(menu,title,fn)
        self.tray.setContextMenu(menu); self.tray.show(); self.running=True; self.events.start(); self.ptt_hotkey.register(); self.quick_hotkey.register()
        if self.config.wake_word and self._microphone_on: self._start_wake_word()
        if not hidden: self.show_quick()
        return self
    @staticmethod
    def _add_action(menu,title,fn): action=QAction(title,menu); action.triggered.connect(fn); menu.addAction(action); return action
    def _position_orb(self):
        if self.orb and self.app:
            g=self.app.primaryScreen().availableGeometry(); s=self.config.orb_size; self.orb.move(g.right()-s-24 if "right" in self.config.corner else g.left()+24,g.bottom()-s-24 if "bottom" in self.config.corner else g.top()+80)
    def _show_orb(self):
        if self.orb and self.config.orb_mode!="hidden": self.orb.show(); self.orb.raise_()
    def _hide_orb(self):
        if self.orb and self.config.orb_mode!="always_visible": self.orb.hide()
    def _on_wake_detected(self,audio_path):
        if self.bridge is not None: self.bridge.wake_audio.emit(Path(audio_path))
    def _handle_wake_audio_gui(self,path): self._show_orb(); self._set_state("LISTENING"); threading.Thread(target=self._send_voice_worker,args=(Path(path),),name="gaia-voice-request",daemon=True).start()
    def _send_voice_worker(self,path):
        try:
            if not self.api: raise RuntimeError("Core unavailable")
            data=self.api.send_voice(path)
            if data and data.get("audio_url"):
                data=dict(data); data["_audio_path"]=self.api.download_audio(data["audio_url"])
            if self.bridge is not None: self.bridge.voice_result.emit(data or {})
        except Exception as exc:
            if self.bridge is not None: self.bridge.voice_error.emit(f"{type(exc).__name__}: {exc}")
        finally:
            try: path.unlink(missing_ok=True)
            except Exception: pass
    def _handle_voice_result_gui(self,data):
        audio_path=data.get("_audio_path") if isinstance(data,dict) else None
        if audio_path:
            self._set_state("SPEAKING")
            try:
                self.player.play(Path(audio_path),lambda:self.bridge.playback_done.emit(),lambda e:self.bridge.playback_error.emit(e))
                self.barge.start()
            except Exception as exc: self._handle_error_gui(str(exc))
        else:
            response=str(data.get("response","")).strip() if isinstance(data,dict) else ""
            if response and self.tray: self.tray.showMessage("GAIA",response[:300])
            self._continue_conversation_gui()
    def _continue_conversation_gui(self):
        if self.wake and self._microphone_on and self.wake.session_active:
            self._show_orb(); self._set_state("LISTENING")
            if self.wake.request_next_turn(): return
        self._set_state("IDLE")
        if self.config.orb_mode=="wake_only": self._hide_orb()
    def _playback_done_gui(self):
        self.barge.stop(); self._continue_conversation_gui()
    def _barge_in_gui(self):
        if not self.player.playing:return
        self.barge.stop(); self.player.stop(); self._set_state("INTERRUPTED")
        try:
            if self.api and hasattr(self.api,"cancel_generation"): threading.Thread(target=self.api.cancel_generation,daemon=True).start()
        except Exception:pass
        if self.wake:
            try:self.wake.begin_session()
            except Exception:pass
        self._continue_conversation_gui()
    def _handle_error_gui(self,message): self._set_state("ERROR"); self.tray.showMessage("GAIA",str(message)[:500]) if self.tray else None
    def _on_wake_session_end(self):
        if self.bridge is not None: self.bridge.core_event.emit({"state":"IDLE","source":"wake_session"})
    def _start_wake_word(self):
        from wake_word import WakeWordListener
        if self.wake is None:
            self.wake=WakeWordListener(on_wake=self._on_wake_detected,on_session_end=self._on_wake_session_end)
            self.wake.start()
    def toggle_wake(self,*_):
        self.config.wake_word=not self.config.wake_word
        if self.config.wake_word and self._microphone_on: self._start_wake_word()
        elif self.wake: self.wake.stop(); self.wake=None
    def toggle_mic(self,*_):
        self._microphone_on=not self._microphone_on
        if not self._microphone_on:
            if self.wake: self.wake.stop(); self.wake=None
            if self.capture.recording: self.capture.stop()
            self.player.stop(); self._set_state("SLEEPING")
        else:
            self._set_state("IDLE")
            if self.config.wake_word: self._start_wake_word()
    def _handle_hotkey_gui(self,action):
        if action=="quick": self.show_quick()
        elif action=="ptt_down": self._ptt_down()
        elif action=="ptt_up": self._ptt_up()
    def _ptt_down(self):
        if not self._microphone_on or self.capture.recording: return
        self.player.stop()
        if self.wake:
            try:self.wake.begin_session()
            except Exception:pass
        try:
            if self.api and hasattr(self.api,"cancel_generation"): threading.Thread(target=self.api.cancel_generation,daemon=True).start()
        except Exception: pass
        self._show_orb(); self._set_state("LISTENING")
        try: self.capture.start()
        except Exception as exc: self._handle_error_gui(str(exc))
    def _ptt_up(self):
        if not self.capture.recording: return
        self._set_state("TRANSCRIBING"); result=self.capture.stop()
        if result.get("status") in {"EMPTY","UNAVAILABLE"}: self._handle_error_gui("No audio captured")
    def push_to_talk(self,*_):
        # Menu action is a toggle; global hotkey remains hold-to-talk.
        self._ptt_up() if self.capture.recording else self._ptt_down()
    def _on_captured_audio(self,path): self._on_wake_detected(path)
    def show_quick(self,*_):
        if not self.qt: return
        if self.quick_command_window: self.quick_command_window.show(); self.quick_command_window.raise_(); return
        w=QWidget(); w.setWindowTitle("GAIA Quick Command"); layout=QVBoxLayout(w); layout.addWidget(QLabel("GAIA")); inp=QLineEdit(); inp.setPlaceholderText("What do you need?"); layout.addWidget(inp)
        def send():
            text=inp.text().strip()
            if not text:return
            inp.setEnabled(False); self._show_orb(); self._set_state("THINKING")
            def worker():
                try:
                    if not self.api: raise RuntimeError("Core unavailable")
                    result=self.api.send_message(text); self.bridge.quick_result.emit(result or {})
                except Exception as exc: self.bridge.quick_error.emit(f"{type(exc).__name__}: {exc}")
            threading.Thread(target=worker,name="gaia-quick-command",daemon=True).start()
        inp.returnPressed.connect(send); w.resize(420,110); self.quick_command_window=w; w.destroyed.connect(lambda:self.__setattr__("quick_command_window",None)); w.show(); inp.setFocus()
    def _handle_quick_result_gui(self,result):
        self._set_state("IDLE")
        if self.quick_command_window: self.quick_command_window.hide()
        text=str(result.get("response","")).strip() if isinstance(result,dict) else ""
        if text and self.tray: self.tray.showMessage("GAIA",text[:300])
    def _show_permission(self,request):
        if self.permission_dialog: self.permission_dialog.close()
        self.permission_dialog=PermissionDialog(request,self._submit_permission); self.permission_dialog.show(); self.permission_dialog.raise_()
    def _submit_permission(self,request_id,decision):
        if not self.api: return
        def worker():
            try: self.api.confirm_permission(request_id,decision)
            except Exception as exc: self.bridge.quick_error.emit(f"Permission error: {exc}")
        threading.Thread(target=worker,name="gaia-permission",daemon=True).start()
    def open_dashboard(self,*_): webbrowser.open(self.config.core_url+"/api/visualizer")
    def show_status(self,*_): self.tray.showMessage("GAIA",f"State: {self.state}\nEvents: {self.events.connected}\nPTT hotkey: {self.ptt_hotkey.registered}\nQuick hotkey: {self.quick_hotkey.registered}") if self.tray else None
    def restart(self,*_): self._shutdown_ui(RESTART_EXIT_CODE)
    def stop(self,*_): self._shutdown_ui(0)
    def _shutdown_ui(self,exit_code:int):
        if self.wake: self.wake.stop(); self.wake=None
        self.ptt_hotkey.unregister(); self.quick_hotkey.unregister(); self.events.stop(); self.capture.stop(); self.barge.stop(); self.player.stop()
        if self.quick_command_window: self.quick_command_window.close(); self.quick_command_window=None
        if self.permission_dialog: self.permission_dialog.close(); self.permission_dialog=None
        if self.tray: self.tray.hide()
        if self.orb: self.orb.close()
        self.running=False; self._shutdown.set()
        if self.qt and self.app: self.app.exit(exit_code)
    def exec(self):
        if not self.running:self.start(hidden=True)
        return self.app.exec() if self.app else 1

def main(): return DesktopShell().exec()
if __name__=="__main__": raise SystemExit(main())
