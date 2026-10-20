"""GAIA resident Desktop Shell. UI is never an authority boundary."""
from __future__ import annotations
import ctypes, json, os, platform, sys, tempfile, threading, time, wave, webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
try:
    from PySide6.QtCore import QObject, Qt, QTimer, Signal, QAbstractNativeEventFilter
    from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QDialog, QFormLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False
    class QObject: pass
    class QAbstractNativeEventFilter: pass
    class Signal:
        def __init__(self,*a,**k): pass
    QAction=QColor=QIcon=QPainter=QPixmap=QApplication=QDialog=QFormLayout=QLabel=QLineEdit=QMenu=QMessageBox=QPushButton=QSystemTrayIcon=QVBoxLayout=QWidget=None
try:
    import httpx
except ImportError:
    httpx = None
try:
    import sounddevice as sd
except ImportError:
    sd = None
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
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
    """Real Win32 global hotkey; press once to record, again to send.

    This is deliberately a *toggle*, not fake key-up notifications. The
    Windows RegisterHotKey API only delivers WM_HOTKEY, not key-release.
    """
    MODIFIERS = {"CTRL": 0x2, "CONTROL": 0x2, "ALT": 0x1, "SHIFT": 0x4, "WIN": 0x8}

    def __init__(self, on_down: Callable[[], None], on_up: Callable[[], None], key: str = "Ctrl+Space"):
        self.on_down, self.on_up, self.key = on_down, on_up, key
        self.registered = False
        self._pressed = False
        self._filter = None
        self._app = None
        self._id = 0x4741

    @classmethod
    def _parse(cls, key: str) -> tuple[int, int]:
        parts = [x.strip().upper() for x in key.split("+") if x.strip()]
        if len(parts) < 2:
            raise ValueError("Se requiere al menos un modificador y una tecla")
        mods = 0
        for p in parts[:-1]:
            if p not in cls.MODIFIERS:
                raise ValueError("Modificador no compatible: " + p)
            mods |= cls.MODIFIERS[p]
        last = parts[-1]
        if last == "SPACE":
            vk = 0x20
        elif len(last) == 1 and last.isascii() and last.isalnum():
            vk = ord(last)
        elif last.startswith("F") and last[1:].isdigit() and 1 <= int(last[1:]) <= 12:
            vk = 0x70 + int(last[1:]) - 1
        else:
            raise ValueError("Tecla no compatible: " + last)
        return mods | 0x4000, vk  # MOD_NOREPEAT

    def register(self, app=None):
        if platform.system() != "Windows" or not PYSIDE_AVAILABLE or app is None:
            return {"status": "UNAVAILABLE", "reason": "requires Windows and Qt"}
        mods, vk = self._parse(self.key)
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, self._id, mods, vk):
            return {"status": "UNAVAILABLE", "reason": "shortcut in use"}
        owner = self

        class NativeFilter(QAbstractNativeEventFilter):
            def nativeEventFilter(self, event_type, message):
                if bytes(event_type) == b"windows_generic_MSG":
                    from ctypes import wintypes

                    class POINT(ctypes.Structure):
                        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

                    class MSG(ctypes.Structure):
                        _fields_ = [
                            ("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                            ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                            ("time", wintypes.DWORD), ("pt", POINT),
                        ]
                    msg = MSG.from_address(int(message))
                    if msg.message == 0x0312 and msg.wParam == owner._id:
                        owner.dispatch("up" if owner._pressed else "down")
                        return True, 0
                return False, 0

        try:
            self._filter = NativeFilter()
            self._app = app
            app.installNativeEventFilter(self._filter)
            self.registered = True
            return {"status": "REGISTERED", "backend": "RegisterHotKey", "key": self.key}
        except Exception:
            user32.UnregisterHotKey(None, self._id)
            self._filter = None
            raise

    def dispatch(self, event: str):
        if not self.registered:
            return False
        if event == "down" and not self._pressed:
            self._pressed = True
            self.on_down()
            return True
        if event == "up" and self._pressed:
            self._pressed = False
            self.on_up()
            return True
        return False

    def unregister(self):
        if self.registered and platform.system() == "Windows":
            ctypes.windll.user32.UnregisterHotKey(None, self._id)
        if self._filter is not None and self._app is not None:
            self._app.removeNativeEventFilter(self._filter)
        self._filter = None
        self._app = None
        self.registered = False
        self._pressed = False


class AudioCapture:
    """Record 16 kHz mono PCM and hand a finalized WAV to the voice API."""
    def __init__(self, on_audio: Callable[[Path], Any]):
        self.on_audio = on_audio
        self.recording = False
        self._stream = None
        self._chunks: list[bytes] = []
        self._frames = 0
        self._lock = threading.Lock()

    def start(self):
        if sd is None:
            raise RuntimeError("sounddevice unavailable")
        if self.recording:
            return {"status": "ALREADY_CAPTURING"}
        with self._lock:
            self._chunks.clear()
            self._frames = 0

        def callback(indata, frames, _time, status):
            with self._lock:
                if self.recording and self._frames < 16000 * 20:
                    self._chunks.append(indata.tobytes())
                    self._frames += frames

        stream = sd.InputStream(samplerate=16000, channels=1, dtype="int16",
                                blocksize=1600, callback=callback)
        self.recording = True
        try:
            stream.start()
        except Exception:
            self.recording = False
            stream.close()
            raise
        self._stream = stream
        return {"status": "CAPTURING"}

    def stop(self, *, deliver: bool = True):
        if not self.recording and self._stream is None:
            return {"status": "IDLE"}
        self.recording = False
        stream, self._stream = self._stream, None
        try:
            if stream is not None:
                stream.stop()
                stream.close()
        finally:
            with self._lock:
                pcm = b"".join(self._chunks)
                self._chunks.clear()
                self._frames = 0
        if not deliver or len(pcm) < 16000 // 4 * 2:
            return {"status": "DISCARDED"}
        handle = tempfile.NamedTemporaryFile(prefix="gaia_voice_", suffix=".wav", delete=False)
        path = Path(handle.name)
        handle.close()
        try:
            with wave.open(str(path), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(16000)
                out.writeframes(pcm)
            self.on_audio(path)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return {"status": "FINALIZED", "path": str(path)}


class ShellSignals(QObject if PYSIDE_AVAILABLE else object):
    if PYSIDE_AVAILABLE:
        event = Signal(object)
        voice_captured = Signal(str)
        state = Signal(str)
        response = Signal(object)

class PermissionDialog(QDialog if PYSIDE_AVAILABLE else object):
    """Shows the exact Core action, scope and risk, without approving on close."""
    def __init__(self, request: dict, decide: Callable[[dict, str], Any]):
        if not PYSIDE_AVAILABLE:
            raise RuntimeError("PySide6 required for permission dialog")
        super().__init__()
        self.request, self.decide = request, decide
        self._answered = False
        self.setWindowTitle("GAIA | Autorizar acción")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("GAIA solicita autorización para una acción en tu PC."))
        form = QFormLayout()
        raw = request.get("plan") or request.get("action") or {}
        items = raw.get("actions", []) if isinstance(raw, dict) and "actions" in raw else [raw]
        risk = max((int(x.get("risk_level", 0)) for x in items if isinstance(x, dict)), default=0)
        options = request.get("confirmation_options") or {}
        details = ", ".join(str(x.get("name") or x.get("action") or "desconocida")
                            for x in items if isinstance(x, dict))[:300]
        entries = request.get("permission_entries") or []
        scopes = ", ".join(str(x.get("human_scope_description") or x.get("resource_scope") or "")
                           for x in entries if isinstance(x, dict))[:400]
        form.addRow("Acción:", QLabel(details or "Revisar la solicitud"))
        form.addRow("Riesgo:", QLabel(str(risk)))
        form.addRow("Alcance:", QLabel(scopes or "Sin alcance descriptivo: autorización puntual"))
        form.addRow("ID:", QLabel(str(request.get("action_id") or "")[:50]))
        layout.addLayout(form)
        once = QPushButton("Autorizar esta ejecución")
        once.clicked.connect(lambda: self._finish("CONFIRM_ONCE"))
        layout.addWidget(once)
        if options.get("allow_always", False) and risk <= 2 and entries:
            persistent = QPushButton("Guardar permiso para este alcance")
            persistent.clicked.connect(lambda: self._finish("ALWAYS_ALLOW"))
            layout.addWidget(persistent)
        deny = QPushButton("Rechazar")
        deny.clicked.connect(lambda: self._finish("DENY"))
        layout.addWidget(deny)

    def _finish(self, decision):
        if self._answered:
            return
        self._answered = True
        self.decide(self.request, decision)
        self.accept()

    def reject(self):
        if not self._answered:
            self._answered = True
            self.decide(self.request, "DENY")
        super().reject()


class DesktopShell:
    def __init__(self, config: ShellConfig|None=None, api=None):
        self.config=config or ShellConfig(); self.api=api; self.running=False; self.qt=False; self.app=None; self.tray=None; self.orb=None; self.wake=None; self.quick_command_window=None; self.quick_result_label=None; self.permission_dialog=None; self._permission_ids=set(); self._request_lock=threading.Lock(); self._capture_session=0; self.state="SLEEPING"; self._microphone_on=self.config.microphone; self._shutdown=threading.Event(); self.signals=None; self._exit_code=0
        self.events=DesktopEventClient(self.config.core_url,self.config.secret,self._on_core_event)
        self.hotkey=GlobalHotkey(self._ptt_down,self._ptt_up,self.config.hotkey)
        self.capture=AudioCapture(self._on_captured_audio)
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
        if self.signals is not None:
            self.signals.event.emit(event)
            return
        self._render_core_event(event)

    def _render_core_event(self,event):
        state=str(event.get("state") or event.get("event_type") or "IDLE").upper().replace(".","_")
        mapping={"USING_TOOL":"EXECUTING","SEARCHING_MEMORY":"THINKING","CORE_READY":"IDLE","CONNECTED":"IDLE"}; self._set_state(mapping.get(state,state if state in {"IDLE","LISTENING","TRANSCRIBING","THINKING","PLANNING","BROWSING","CODING","EXECUTING","SPEAKING","WAITING_PERMISSION","INTERRUPTED","SAFE_MODE","ERROR","OFFLINE"} else "IDLE"))
        if state=="WAITING_PERMISSION" and PYSIDE_AVAILABLE:
            request = event.get("metadata") or event
            if isinstance(request, dict) and request.get("action_id") and request.get("session_id"):
                self._show_permission(request)
        if state=="IDLE" and self.config.orb_mode=="wake_only": self._hide_orb()
    def _icon(self):
        pix=QPixmap(32,32); pix.fill(QColor("#101828")); p=QPainter(pix); p.setBrush(QColor("#45d9ff")); p.setPen(QColor("#a98bff")); p.drawEllipse(5,5,22,22); p.end(); return QIcon(pix)
    def start(self,hidden=True):
        if not PYSIDE_AVAILABLE: raise RuntimeError("PySide6 is required for resident shell; install requirements-desktop.txt")
        self.app=QApplication.instance() or QApplication(sys.argv); self.app.setQuitOnLastWindowClosed(False); self.qt=True; shell=self
        self.signals=ShellSignals()
        self.signals.event.connect(self._render_core_event)
        self.signals.voice_captured.connect(self._handle_voice)
        self.signals.state.connect(self._set_state)
        self.signals.response.connect(self._show_response)
        class Orb(QWidget):
            def __init__(inner): super().__init__(); inner.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool|Qt.WindowDoesNotAcceptFocus); inner.setAttribute(Qt.WA_TranslucentBackground); inner.resize(shell.config.orb_size,shell.config.orb_size); inner.state="SLEEPING"
            def set_state(inner,state): inner.state=state; inner.update()
            def paintEvent(inner,_):
                p=QPainter(inner); p.setRenderHint(QPainter.Antialiasing); colors={"ERROR":"#ff526b","WAITING_PERMISSION":"#ffcc66","SAFE_MODE":"#aa8cff","LISTENING":"#55e6ff","THINKING":"#8f7cff","SPEAKING":"#65a8ff","OFFLINE":"#77808f","INTERRUPTED":"#ff8b5c"}; p.setBrush(QColor(colors.get(inner.state,"#277dff"))); p.setPen(Qt.NoPen); p.drawEllipse(8,8,inner.width()-16,inner.height()-16)
        self.orb=Orb(); self._position_orb(); self.tray=QSystemTrayIcon(self.app); self.tray.setIcon(self._icon()); self.tray.setToolTip("GAIA — Resident Desktop Assistant"); menu=QMenu();
        for title,fn in (("Open GAIA",self.show_quick),("Quick Command",self.show_quick),("Wake word ON/OFF",self.toggle_wake),("Microphone ON/OFF",self.toggle_mic),("Grabar / finalizar voz",self.push_to_talk),("Estado Core / Acción",self.show_status),("PARAR ACCIONES",self.emergency_stop),("Reactivar acciones",self.resume_actions),("Restart GAIA",self.restart),("Exit GAIA",self.stop)): self._add_action(menu,title,fn)
        self.tray.setContextMenu(menu); self.tray.show(); self.running=True; self.events.start(); self.hotkey.register(self.app);
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
    def _on_wake_detected(self, audio_path):
        if not self._microphone_on or self._shutdown.is_set():
            Path(audio_path).unlink(missing_ok=True)
            return
        if self.signals is not None:
            self.signals.voice_captured.emit(str(audio_path))

    def _handle_voice(self, audio_path):
        if not self._microphone_on or self._shutdown.is_set():
            Path(audio_path).unlink(missing_ok=True)
            return
        self._show_orb()
        self._set_state("TRANSCRIBING")
        threading.Thread(target=self._send_voice, args=(Path(audio_path),), daemon=True).start()

    def _send_voice(self, path):
        acquired = self._request_lock.acquire(blocking=False)
        try:
            if not acquired:
                raise RuntimeError("GAIA ya procesa otra solicitud. Inténtalo al terminar.")
            if not self.api:
                raise RuntimeError("Core unavailable")
            data = self.api.send_voice(path)
            if self.signals is not None:
                self.signals.response.emit(data)
            answer = str(data.get("response") or data.get("message") or "").strip()
            if os.getenv("GAIA_SPEAK_RESPONSES", "true").lower() in {"true", "1", "yes"}:
                from desktop_api import play_audio
                audio_url = str(data.get("audio_url") or "").strip()
                if audio_url or answer:
                    if self.signals is not None:
                        self.signals.state.emit("SPEAKING")
                    try:
                        path_to_play = (self.api.download_audio(audio_url) if audio_url
                                        else self.api.request_tts(answer[:1500]))
                        play_audio(path_to_play)
                    except Exception:
                        # A speaker/network failure must not discard a successful chat response.
                        pass
            if self.signals is not None:
                self.signals.state.emit("IDLE")
        except Exception as exc:
            if self.signals is not None:
                self.signals.response.emit({"response": f"Error de voz: {type(exc).__name__}"})
                self.signals.state.emit("ERROR")
        finally:
            if acquired:
                self._request_lock.release()
            path.unlink(missing_ok=True)

    def _start_wake_word(self):
        from wake_word import WakeWordListener
        listener = self.wake or WakeWordListener(on_wake=self._on_wake_detected)
        readiness = listener.health()
        if readiness.get("status") not in {"GAIA_MODEL_READY", "WHISPER_FALLBACK"}:
            self.config.wake_word = False
            if self.tray is not None:
                self.tray.showMessage("GAIA | Voz", "Falta el modelo de activación 'GAIA'. Usa Ctrl+Espacio para grabar.")
            return
        try:
            if not listener.running:
                listener.start()
            self.wake = listener
        except Exception as exc:
            self.config.wake_word = False
            if self.tray is not None:
                self.tray.showMessage("GAIA | Voz", str(exc)[:200])

    def _stop_wake_word(self):
        if self.wake is not None:
            self.wake.stop()
            self.wake = None

    def toggle_wake(self):
        self.config.wake_word = not self.config.wake_word
        if self.config.wake_word and self._microphone_on:
            self._start_wake_word()
        else:
            self._stop_wake_word()

    def toggle_mic(self):
        self._microphone_on = not self._microphone_on
        if not self._microphone_on:
            self.capture.stop(deliver=False)
            self._stop_wake_word()
        elif self.config.wake_word and self.qt:
            self._start_wake_word()
        self._set_state("SLEEPING" if not self._microphone_on else "IDLE")

    def _ptt_down(self):
        if not self._microphone_on:
            return
        self._stop_wake_word()  # Avoid simultaneous ownership of the microphone.
        self._show_orb()
        try:
            result = self.capture.start()
            self._capture_session += 1
            capture_session = self._capture_session
            self._set_state("LISTENING")
            if self.qt and self.app:
                QTimer.singleShot(20000, lambda: (
                    self.hotkey.dispatch("up") if self.hotkey._pressed else self._ptt_up()
                ) if self.capture.recording and capture_session == self._capture_session else None)
        except Exception as exc:
            self._set_state("ERROR")
            if self.config.wake_word and self._microphone_on:
                self._start_wake_word()
            if self.tray:
                self.tray.showMessage("GAIA", str(exc))

    def _ptt_up(self):
        if self.capture.recording:
            self.capture.stop()
        if self.config.wake_word and self._microphone_on:
            self._start_wake_word()

    def push_to_talk(self):
        if self.capture.recording:
            self._ptt_up()
        else:
            self._ptt_down()

    def _on_captured_audio(self,path):
        self._on_wake_detected(path)

    def show_quick(self):
        if not self.qt:
            return
        if self.quick_command_window:
            self.quick_command_window.show()
            self.quick_command_window.raise_()
            return
        w = QWidget()
        w.setWindowTitle("GAIA - Comandos")
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("GAIA | Asistente personal"))
        inp = QLineEdit()
        inp.setPlaceholderText("¿Qué necesitas que haga?")
        layout.addWidget(inp)
        label = QLabel("")
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        layout.addWidget(label)
        self.quick_result_label = label

        def send():
            message = inp.text().strip()
            if not message:
                return
            inp.clear()
            label.setText("Procesando...")
            self._show_orb()
            self._set_state("THINKING")

            def worker():
                acquired = self._request_lock.acquire(blocking=False)
                try:
                    if not acquired:
                        raise RuntimeError("GAIA está procesando otra solicitud.")
                    if self.api is None:
                        raise RuntimeError("Core no disponible")
                    answer = self.api.send_assistant(message)
                    if self.signals is not None:
                        self.signals.response.emit(answer)
                        self.signals.state.emit("IDLE")
                except Exception as exc:
                    if self.signals is not None:
                        self.signals.response.emit({"response": f"Error: {type(exc).__name__}: {exc}"})
                        self.signals.state.emit("ERROR")
                finally:
                    if acquired:
                        self._request_lock.release()
            threading.Thread(target=worker, daemon=True).start()

        inp.returnPressed.connect(send)
        w.resize(510, 180)
        self.quick_command_window = w
        w.destroyed.connect(lambda: self.__setattr__("quick_command_window", None))
        w.show()
        inp.setFocus()

    def _show_response(self, data):
        if not isinstance(data, dict):
            return
        message = str(data.get("response") or data.get("message") or data.get("detail") or "Sin respuesta.")
        if data.get("confirmation_required"):
            message += "\nAcción pendiente. Debes autorizarla o rechazarla."
            if data.get("action_id") and data.get("session_id"):
                self._show_permission(data)
            else:
                message += "\nFaltan los identificadores de autorización del Core."
        elif data.get("status") in {"approved", "rejected"}:
            message = ("Acción autorizada. El ejecutor de PC procesará la solicitud."
                       if data.get("status") == "approved" else "Acción rechazada.")
        if self.quick_result_label is not None:
            self.quick_result_label.setText(message[:3000])
        if self.tray is not None and (
            self.quick_command_window is None or not self.quick_command_window.isVisible()
        ):
            self.tray.showMessage("GAIA", message[:180])

    def _show_permission(self, request):
        if not isinstance(request, dict):
            return
        action_id = str(request.get("action_id") or "")
        session_id = str(request.get("session_id") or "")
        if not action_id or not session_id or action_id in self._permission_ids:
            return
        # A notification without the actual action plan is not enough to
        # request informed consent; wait for the Core's complete response.
        if not isinstance(request.get("action") or request.get("plan"), dict):
            return
        self._permission_ids.add(action_id)
        dlg = PermissionDialog(request, self._submit_permission)
        self.permission_dialog = dlg
        dlg.finished.connect(lambda _, aid=action_id: self._permission_ids.discard(aid))
        dlg.show()
        dlg.raise_()

    def _submit_permission(self, request, decision):
        if not self.api:
            return
        action_id = str(request.get("action_id") or "")
        session_id = str(request.get("session_id") or "")
        if not action_id or not session_id:
            return
        self._set_state("EXECUTING" if decision != "DENY" else "IDLE")

        def worker():
            try:
                result = self.api.confirm_permission(action_id, decision, session_id=session_id)
                if self.signals is not None:
                    self.signals.response.emit(result)
                    self.signals.state.emit("IDLE")
            except Exception as exc:
                if self.signals is not None:
                    self.signals.response.emit({"response": f"No se pudo registrar la autorización: {exc}"})
                    self.signals.state.emit("ERROR")
        threading.Thread(target=worker, daemon=True).start()

    def open_dashboard(self):
        webbrowser.open(self.config.core_url + "/api/visualizer")

    def show_status(self):
        if not self.api:
            self._show_response({"response": "Core no disponible"})
            return

        def worker():
            try:
                host = self.api.remote_action_host_status()
                actions = self.api.actions_control_status()
                message = (
                    f"Core: conectado. Action Host: {'conectado' if host.get('online') else 'DESCONECTADO'}. "
                    f"Acciones: {'ACTIVAS' if actions.get('enabled') else 'DESACTIVADAS'}. "
                    f"Voz: {'activada' if self._microphone_on else 'desactivada'}."
                )
                if self.signals is not None:
                    self.signals.response.emit({"response": message})
            except Exception as exc:
                if self.signals is not None:
                    self.signals.response.emit({"response": f"Estado de GAIA no disponible: {exc}"})
        threading.Thread(target=worker, daemon=True).start()

    def emergency_stop(self):
        if not self.api:
            return
        answer = QMessageBox.question(
            None, "GAIA | Detener acciones",
            "¿Desactivar las acciones y cancelar las solicitudes pendientes? "
            "No detiene acciones que ya estén ejecutándose.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return

        def worker():
            try:
                result = self.api.kill_switch()
                if self.signals is not None:
                    self.signals.response.emit({"response": f"Acciones bloqueadas. Solicitudes canceladas: {result.get('pending_cancelled', 0)}."})
                    self.signals.state.emit("SAFE_MODE")
            except Exception as exc:
                if self.signals is not None:
                    self.signals.response.emit({"response": f"Error al detener acciones: {exc}"})
        threading.Thread(target=worker, daemon=True).start()

    def resume_actions(self):
        if not self.api:
            return
        answer = QMessageBox.question(
            None, "GAIA | Reactivar acciones",
            "¿Permitir nuevamente que GAIA ejecute acciones autorizadas?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return

        def worker():
            try:
                result = self.api.enable_actions()
                if self.signals is not None:
                    self.signals.response.emit({"response": "Acciones reactivadas." if result.get("enabled") else "El Core mantiene las acciones desactivadas."})
                    self.signals.state.emit("IDLE")
            except Exception as exc:
                if self.signals is not None:
                    self.signals.response.emit({"response": f"No se pudieron reactivar las acciones: {exc}"})
        threading.Thread(target=worker, daemon=True).start()

    def restart(self):
        self._exit_code = 75
        self.stop()
        return self._exit_code
    def stop(self):
        self._stop_wake_word()
        self.hotkey.unregister(); self.events.stop(); self.capture.stop(deliver=False);
        if self.quick_command_window: self.quick_command_window.close(); self.quick_command_window=None
        if self.tray: self.tray.hide()
        if self.orb: self.orb.close()
        self.running=False; self._shutdown.set(); self.app.exit(self._exit_code) if self.qt and self.app else None
    def exec(self):
        if not self.running:self.start(hidden=True)
        return self.app.exec() if self.app else 1
def main(): return DesktopShell().exec()
if __name__=="__main__": raise SystemExit(main())
