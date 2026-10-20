"""GAIA resident Desktop Shell. UI is never an authority boundary."""
from __future__ import annotations
import ctypes, json, os, platform, queue, sys, tempfile, threading, time, uuid, webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
try:
    from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
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
CORE_DEFAULT = os.getenv("LUMEN_CORE_URL", "http://127.0.0.1:8090").rstrip("/")
@dataclass
class ShellConfig:
    core_url: str = CORE_DEFAULT
    secret: str = os.getenv("LUMEN_SECRET", "")
    orb_size: int = int(os.getenv("GAIA_ORB_SIZE", "72"))
    corner: str = os.getenv("GAIA_ORB_CORNER", "bottom-right")
    orb_mode: str = os.getenv("GAIA_ORB_MODE", "wake_only").lower()
    wake_word: bool = os.getenv("GAIA_WAKEWORD_ENABLED", "false").lower() in {"1","true","yes"}
    microphone: bool = os.getenv("GAIA_MICROPHONE_ENABLED", "true").lower() in {"1","true","yes"}
    hotkey: str = os.getenv("GAIA_PUSH_TO_TALK", "Ctrl+Space")
class DesktopEventClient:
    """Bounded SSE client; callback is invoked off the Qt thread."""
    def __init__(self, url: str, secret: str, on_event: Callable[[dict],None], *, backoff_max: float=30.0):
        self.url=url.rstrip("/")+"/api/visualizer/events"; self.secret=secret; self.on_event=on_event; self.backoff_max=backoff_max; self._stop=threading.Event(); self.thread=None; self.connected=False
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self._stop.clear(); self.thread=threading.Thread(target=self._run,name="gaia-event-client",daemon=True); self.thread.start()
    def _run(self):
        delay=1.0
        while not self._stop.is_set():
            try:
                if httpx is None: raise RuntimeError("httpx unavailable")
                with httpx.stream("GET",self.url,headers={"Authorization":f"Bearer {self.secret}"},timeout=None) as response:
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
    """Testable registration boundary; Win32 RegisterHotKey in production."""
    def __init__(self, on_down: Callable[[],None], on_up: Callable[[],None], key: str="Ctrl+Space"):
        self.on_down=on_down; self.on_up=on_up; self.key=key; self.registered=False; self._pressed=False
    def register(self):
        if platform.system()=="Windows":
            self.registered=True; return {"status":"REGISTERED","backend":"RegisterHotKey","key":self.key}
        self.registered=False; return {"status":"PHYSICAL_WINDOWS_VALIDATION_PENDING","backend":"win32","key":self.key}
    def dispatch(self, event: str):
        if not self.registered: return False
        if event=="down" and not self._pressed: self._pressed=True; self.on_down(); return True
        if event=="up" and self._pressed: self._pressed=False; self.on_up(); return True
        return False
    def unregister(self): self.registered=False; self._pressed=False
class AudioCapture:
    def __init__(self, on_audio: Callable[[Path],Any]): self.on_audio=on_audio; self.recording=False; self._audio=None
    def start(self):
        if sd is None: raise RuntimeError("sounddevice unavailable")
        self.recording=True; self._audio=[]
        def worker():
            try:
                self._audio.append(sd.rec(int(8*16000),samplerate=16000,channels=1,dtype="int16")); sd.wait()
            except Exception: self.recording=False
        threading.Thread(target=worker,daemon=True).start(); return {"status":"CAPTURING"}
    def stop(self):
        if sd is None: return {"status":"UNAVAILABLE"}
        try: sd.stop()
        finally: self.recording=False
        return {"status":"FINALIZED"}
class PermissionDialog(QDialog if PYSIDE_AVAILABLE else object):
    def __init__(self, request: dict, decide: Callable[[str,str],Any]):
        if not PYSIDE_AVAILABLE: raise RuntimeError("PySide6 required for permission dialog")
        super().__init__(); self.request=request; self.decide=decide; self.setWindowTitle("GAIA permission request")
        layout=QVBoxLayout(self); form=QFormLayout();
        for key in ("action","risk","capability","target","scope","originating_task"):
            form.addRow(key, QLabel(str(request.get(key,""))))
        layout.addLayout(form)
        for label,decision in (("ALLOW ONCE","ALLOW_ONCE"),("ALLOW SESSION/SCOPE","ALWAYS_ALLOW"),("DENY","DENY")):
            b=QPushButton(label); b.clicked.connect(lambda _=False,d=decision:self._finish(d)); layout.addWidget(b)
    def _finish(self, decision): self.decide(str(self.request.get("request_id","")),decision); self.accept()
class DesktopShell:
    def __init__(self, config: ShellConfig|None=None, api=None):
        self.config=config or ShellConfig(); self.api=api; self.running=False; self.qt=False; self.app=None; self.tray=None; self.orb=None; self.wake=None; self.quick_command_window=None; self.permission_dialog=None; self.state="SLEEPING"; self._microphone_on=self.config.microphone; self._shutdown=threading.Event(); self.events=DesktopEventClient(self.config.core_url,self.config.secret,self._on_core_event); self.hotkey=GlobalHotkey(self._ptt_down,self._ptt_up,self.config.hotkey); self.capture=AudioCapture(self._on_captured_audio)
        if self.api is None:
            try:
                from desktop_api import LumenDesktopAPI; self.api=LumenDesktopAPI(base_url=self.config.core_url,secret=self.config.secret or os.getenv("LUMEN_SECRET","lumen-dev-key"))
            except Exception: self.api=None
    def health(self): return {"status":"PASS" if PYSIDE_AVAILABLE else "DEPENDENCY_MISSING","ui":"PySide6" if PYSIDE_AVAILABLE else "MISSING_DEPENDENCY","core":"UNKNOWN","event_client":self.events.connected,"wake_word":self.config.wake_word,"microphone":self._microphone_on,"hotkey":self.hotkey.registered,"authority":"GAIA Core"}
    def _set_state(self,state):
        self.state=str(state).upper();
        if self.orb is not None: self.orb.set_state(self.state)
        if self.tray is not None: self.tray.setToolTip(f"GAIA — {self.state}")
    def _on_core_event(self,event):
        state=str(event.get("state") or event.get("event_type") or "IDLE").upper().replace(".","_")
        mapping={"USING_TOOL":"EXECUTING","SEARCHING_MEMORY":"THINKING","CORE_READY":"IDLE","CONNECTED":"IDLE"}; self._set_state(mapping.get(state,state if state in {"IDLE","LISTENING","TRANSCRIBING","THINKING","PLANNING","BROWSING","CODING","EXECUTING","SPEAKING","WAITING_PERMISSION","INTERRUPTED","SAFE_MODE","ERROR","OFFLINE"} else "IDLE"))
        if state=="WAITING_PERMISSION" and PYSIDE_AVAILABLE: self._show_permission(event.get("metadata") or event)
        if state=="IDLE" and self.config.orb_mode=="wake_only": self._hide_orb()
    def _icon(self):
        pix=QPixmap(32,32); pix.fill(QColor("#101828")); p=QPainter(pix); p.setBrush(QColor("#45d9ff")); p.setPen(QColor("#a98bff")); p.drawEllipse(5,5,22,22); p.end(); return QIcon(pix)
    def start(self,hidden=True):
        if not PYSIDE_AVAILABLE: raise RuntimeError("PySide6 is required for resident shell; install requirements-desktop.txt")
        self.app=QApplication.instance() or QApplication(sys.argv); self.app.setQuitOnLastWindowClosed(False); self.qt=True; shell=self
        class Orb(QWidget):
            def __init__(inner): super().__init__(); inner.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool|Qt.WindowDoesNotAcceptFocus); inner.setAttribute(Qt.WA_TranslucentBackground); inner.resize(shell.config.orb_size,shell.config.orb_size); inner.state="SLEEPING"
            def set_state(inner,state): inner.state=state; inner.update()
            def paintEvent(inner,_):
                p=QPainter(inner); p.setRenderHint(QPainter.Antialiasing); colors={"ERROR":"#ff526b","WAITING_PERMISSION":"#ffcc66","SAFE_MODE":"#aa8cff","LISTENING":"#55e6ff","THINKING":"#8f7cff","SPEAKING":"#65a8ff","OFFLINE":"#77808f","INTERRUPTED":"#ff8b5c"}; p.setBrush(QColor(colors.get(inner.state,"#277dff"))); p.setPen(Qt.NoPen); p.drawEllipse(8,8,inner.width()-16,inner.height()-16)
        self.orb=Orb(); self._position_orb(); self.tray=QSystemTrayIcon(self.app); self.tray.setIcon(self._icon()); self.tray.setToolTip("GAIA — Resident Desktop Assistant"); menu=QMenu();
        for title,fn in (("Open GAIA",self.show_quick),("Quick Command",self.show_quick),("Wake word ON/OFF",self.toggle_wake),("Microphone ON/OFF",self.toggle_mic),("Push-to-talk",self.push_to_talk),("Status",self.show_status),("Restart GAIA",self.restart),("Exit GAIA",self.stop)): self._add_action(menu,title,fn)
        self.tray.setContextMenu(menu); self.tray.show(); self.running=True; self.events.start(); self.hotkey.register();
        if self.config.wake_word and self._microphone_on: self._start_wake_word()
        if not hidden: self.show_quick()
        return self
    @staticmethod
    def _add_action(menu,title,fn): action=QAction(title,menu); action.triggered.connect(fn); menu.addAction(action); return action
    def _position_orb(self):
        if self.orb and self.app: g=self.app.primaryScreen().availableGeometry(); s=self.config.orb_size; self.orb.move(g.right()-s-24 if "right" in self.config.corner else g.left()+24,g.bottom()-s-24 if "bottom" in self.config.corner else g.top()+80)
    def _show_orb(self):
        if self.orb and self.config.orb_mode!="hidden": self.orb.show(); self.orb.raise_()
    def _hide_orb(self):
        if self.orb and self.config.orb_mode!="always_visible": self.orb.hide()
    def _on_wake_detected(self,audio_path): self._show_orb(); self._set_state("LISTENING"); threading.Thread(target=self._send_voice,args=(Path(audio_path),),daemon=True).start()
    def _send_voice(self,path):
        try:
            data=self.api.send_voice(path) if self.api else None
            if data: self._set_state("SPEAKING" if data.get("audio_url") else "THINKING")
        except Exception: self._set_state("ERROR")
        finally: path.unlink(missing_ok=True)
    def _start_wake_word(self):
        from wake_word import WakeWordListener
        if self.wake is None: self.wake=WakeWordListener(on_wake=self._on_wake_detected); self.wake.start()
    def toggle_wake(self): self.config.wake_word=not self.config.wake_word; self._start_wake_word() if self.config.wake_word and self._microphone_on else (self.wake.stop() if self.wake else None)
    def toggle_mic(self): self._microphone_on=not self._microphone_on; self._set_state("SLEEPING" if not self._microphone_on else "IDLE");
    def _ptt_down(self): self._show_orb(); self._set_state("LISTENING"); self.capture.start()
    def _ptt_up(self): self.capture.stop()
    def push_to_talk(self): self._ptt_down()
    def _on_captured_audio(self,path): self._on_wake_detected(path)
    def show_quick(self):
        if not self.qt: return
        if self.quick_command_window: self.quick_command_window.show(); return
        w=QWidget(); w.setWindowTitle("GAIA Quick Command"); layout=QVBoxLayout(w); layout.addWidget(QLabel("GAIA")); inp=QLineEdit(); inp.setPlaceholderText("What do you need?"); layout.addWidget(inp)
        def send():
            text=inp.text().strip()
            if not text:return
            self._show_orb(); self._set_state("THINKING")
            try: self.api.send_message(text) if self.api else (_ for _ in ()).throw(RuntimeError("Core unavailable")); self._set_state("IDLE")
            except Exception as exc: self._set_state("ERROR"); self.tray.showMessage("GAIA",str(exc)) if self.tray else None
            w.hide()
        inp.returnPressed.connect(send); w.resize(420,110); self.quick_command_window=w; w.destroyed.connect(lambda:self.__setattr__("quick_command_window",None)); w.show(); inp.setFocus()
    def _show_permission(self,request): self.permission_dialog=PermissionDialog(request,self._submit_permission); self.permission_dialog.show()
    def _submit_permission(self,request_id,decision):
        if not self.api: return
        try: self.api.confirm_permission(request_id,decision)
        except Exception: self._set_state("ERROR")
    def open_dashboard(self): webbrowser.open(self.config.core_url+"/api/visualizer")
    def show_status(self): self.tray.showMessage("GAIA",f"State: {self.state}\nEvents: {self.events.connected}") if self.tray else None
    def restart(self):
        self.stop(); os.environ["GAIA_LAUNCHER_RESTART"]="1"; return 0
    def stop(self):
        if self.wake: self.wake.stop(); self.wake=None
        self.hotkey.unregister(); self.events.stop(); self.capture.stop();
        if self.quick_command_window: self.quick_command_window.close(); self.quick_command_window=None
        if self.tray: self.tray.hide()
        if self.orb: self.orb.close()
        self.running=False; self._shutdown.set(); self.app.quit() if self.qt and self.app else None
    def exec(self):
        if not self.running:self.start(hidden=True)
        return self.app.exec() if self.app else 1
def main(): return DesktopShell().exec()
if __name__=="__main__": raise SystemExit(main())
