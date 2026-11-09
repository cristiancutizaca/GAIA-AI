"""GAIA local wake-word + conversation endpointing.

Sleeping mode evaluates only the local openWakeWord model using low-latency
80 ms PCM frames. After detection, Silero VAD endpoints the utterance and the
listener remains in a conversation session until the Desktop ends it or the
next-turn timeout expires. No Jarvis model is ever substituted for Gaia.
"""
from __future__ import annotations

from collections import deque
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
import wave
from typing import Callable

import numpy as np

WAKE_WORD="gaia"
SAMPLE_RATE=16000
WAKE_CHUNK_SAMPLES=1280  # 80 ms at 16 kHz; openWakeWord's low-latency native step.
VAD_CHUNK_SAMPLES=512    # 32 ms; Silero streaming step at 16 kHz.
MAX_UTTERANCE_SECONDS=float(os.getenv("GAIA_MAX_UTTERANCE_SECONDS","20"))
START_TIMEOUT_SECONDS=float(os.getenv("GAIA_CONVERSATION_START_TIMEOUT","10"))


class WakeWordListener:
    def __init__(self,on_wake:Callable[[str],None]|None=None,on_session_end:Callable[[],None]|None=None,
                 on_error:Callable[[str],None]|None=None):
        self.on_wake=on_wake; self.on_session_end=on_session_end; self.on_error=on_error
        self.running=False; self._thread=None; self._wake_model=None; self._vad_model=None
        self.sensitivity=float(os.getenv("GAIA_WAKEWORD_SENSITIVITY","0.5"))
        self.session_active=False; self.last_wake=0.0
        self._session_lock=threading.Lock(); self._capture_lock=threading.Lock(); self._next_turn_thread=None

    def health(self)->dict:
        model_path = self._model_path()
        if not model_path or not os.path.isfile(model_path):
            return {"status":"CUSTOM_MODEL_MISSING","engine":"openwakeword","local":True,"required":"GAIA_WAKEWORD_MODEL or assets/wakeword/gaia.onnx"}
        path = Path(model_path)
        if path.name.casefold() != "gaia.onnx":
            return {"status": "CUSTOM_MODEL_INVALID", "engine": "openwakeword", "local": True,
                    "required": "Un modelo entrenado para GAIA con el nombre gaia.onnx."}
        try:
            import openwakeword  # noqa:F401
            return {"status":"GAIA_MODEL_READY","engine":"openwakeword","local":True,"model":model_path,"sensitivity":self.sensitivity}
        except Exception as exc:
            return {"status":"ERROR","engine":"openwakeword","local":True,"error":type(exc).__name__}

    def _model_path(self)->str:
        raw=os.getenv("GAIA_WAKEWORD_MODEL","").strip()
        if raw:return str(Path(raw).expanduser())
        default=Path(__file__).resolve().parents[1]/"assets"/"wakeword"/"gaia.onnx"
        return str(default) if default.is_file() else ""

    def _load_wakeword(self):
        if self._wake_model is None:
            from openwakeword.model import Model
            model_path=self._model_path()
            if not model_path or not os.path.isfile(model_path) or Path(model_path).name.casefold() != "gaia.onnx":
                raise RuntimeError("GAIA requiere su modelo gaia.onnx.")
            self._wake_model=Model(wakeword_models=[model_path],inference_framework="onnx")
        return self._wake_model

    def _load_vad(self):
        if self._vad_model is None:
            from silero_vad import load_silero_vad
            self._vad_model=load_silero_vad()
        return self._vad_model

    @staticmethod
    def _save_wav(audio:np.ndarray,path:str)->None:
        with wave.open(path,"wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE); wf.writeframes(audio.astype(np.int16,copy=False).tobytes())

    def _detect_wake_word(self,audio:np.ndarray)->bool:
        if audio.size<WAKE_CHUNK_SAMPLES:return False
        model=self._load_wakeword()
        scores=model.predict(audio.astype(np.int16,copy=False))
        model_name = Path(self._model_path()).stem.casefold()
        detected = any(float(value) >= self.sensitivity for name, value in scores.items()
                       if Path(str(name)).stem.casefold() == model_name)
        if detected:
            try:model.reset()
            except Exception:pass
        return detected

    def _record_utterance(self,start_timeout:float=START_TIMEOUT_SECONDS)->str|None:
        """Capture one utterance with Silero VAD; returns a temporary 16k mono WAV."""
        import sounddevice as sd
        try:
            import torch
            from silero_vad import VADIterator
            vad=VADIterator(self._load_vad(),sampling_rate=SAMPLE_RATE)
        except Exception as exc:
            raise RuntimeError(f"Silero VAD unavailable: {exc}") from exc

        q:queue.Queue[np.ndarray]=queue.Queue(maxsize=256)
        pre=deque(maxlen=12)  # ~384 ms pre-roll
        captured=[]; started=False; start_deadline=time.monotonic()+max(1.0,start_timeout); speech_started_at=0.0

        def callback(indata,frames,time_info,status):
            if not self.running:return
            try:q.put_nowait(indata[:,0].astype(np.int16,copy=True))
            except queue.Full:
                try:q.get_nowait(); q.put_nowait(indata[:,0].astype(np.int16,copy=True))
                except Exception:pass

        from audio_input import input_settings
        from desktop_api import get_preferred_microphone
        options, _ = input_settings(sd, get_preferred_microphone(), SAMPLE_RATE)
        with self._capture_lock:
            if not self.running:
                return None
            with sd.InputStream(**options, blocksize=VAD_CHUNK_SAMPLES, callback=callback):
                while self.running:
                    if not started and time.monotonic()>=start_deadline:return None
                    if started and time.monotonic()-speech_started_at>=MAX_UTTERANCE_SECONDS:break
                    try:chunk=q.get(timeout=.2)
                    except queue.Empty:continue
                    if len(chunk)!=VAD_CHUNK_SAMPLES:continue
                    pre.append(chunk)
                    tensor=torch.from_numpy(chunk.astype(np.float32)/32768.0)
                    event=vad(tensor,return_seconds=True)
                    if not started:
                        if event and "start" in event:
                            started=True; speech_started_at=time.monotonic(); captured.extend(list(pre)); pre.clear()
                    else:
                        captured.append(chunk)
                        if event and "end" in event:break
        try:vad.reset_states()
        except Exception:pass
        if not captured or not self.running:return None
        audio=np.concatenate(captured)
        with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as tmp:path=tmp.name
        self._save_wav(audio,path); return path

    def _dispatch_utterance(self, start_timeout: float) -> None:
        path = None
        try:
            path = self._record_utterance(start_timeout)
            if path and self.running and self.on_wake:
                self.on_wake(path)
                path = None  # ownership passed to the desktop
            else:
                self.end_session()
        except Exception as exc:
            self._report_error("Escucha de conversación", exc)
        finally:
            if path:
                Path(path).unlink(missing_ok=True)

    def _report_error(self, stage: str, exc: Exception) -> None:
        was_running = self.running
        self.running = False
        self.end_session()
        if was_running and self.on_error:
            self.on_error(f"{stage}: {exc}. Push To Talk sigue disponible.")

    def begin_session(self)->None:
        with self._session_lock:
            self.session_active=True; self.last_wake=time.time()

    def request_next_turn(self,timeout:float=START_TIMEOUT_SECONDS)->bool:
        with self._session_lock:
            if not self.running or not self.session_active:return False
            if self._next_turn_thread and self._next_turn_thread.is_alive():return False
            self._next_turn_thread=threading.Thread(target=self._dispatch_utterance,args=(timeout,),name="gaia-conversation-turn",daemon=True); self._next_turn_thread.start(); return True

    def end_session(self)->None:
        callback=None
        with self._session_lock:
            if self.session_active:
                self.session_active=False; callback=self.on_session_end
        if callback:
            try:callback()
            except Exception:pass

    def _listen_loop(self) -> None:
        try:
            import sounddevice as sd
            from audio_input import input_settings
            from desktop_api import get_preferred_microphone
            self._load_wakeword()
            options, _ = input_settings(sd, get_preferred_microphone(), SAMPLE_RATE)
            while self.running:
                if self.session_active:
                    time.sleep(.05)
                    continue
                frames: queue.Queue[np.ndarray] = queue.Queue(maxsize=8)

                def capture(indata, frame_count, time_info, status):
                    try:
                        frames.put_nowait(indata[:, 0].copy())
                    except queue.Full:
                        pass

                activated = False
                with self._capture_lock:
                    if not self.running:
                        break
                    with sd.InputStream(**options, blocksize=WAKE_CHUNK_SAMPLES, callback=capture):
                        while self.running and not self.session_active:
                            try:
                                frame = frames.get(timeout=.15)
                            except queue.Empty:
                                continue
                            if self.running and self._detect_wake_word(frame):
                                self.begin_session()
                                activated = True
                                break
                if self.running and activated:
                    self._dispatch_utterance(START_TIMEOUT_SECONDS)
        except Exception as exc:
            self._report_error("Activación por palabra", exc)

    def start(self) -> None:
        if self.running or any(t and t.is_alive() for t in (self._thread, self._next_turn_thread)):
            return
        if self.health().get("status") != "GAIA_MODEL_READY":
            raise RuntimeError("GAIA wake model is not ready")
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, name="gaia-wakeword", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        self.end_session()
        for attr in ("_thread", "_next_turn_thread"):
            worker = getattr(self, attr)
            if worker and worker is not threading.current_thread():
                worker.join(timeout=.75)
            if not worker or not worker.is_alive():
                setattr(self, attr, None)



async def wake_word_client(core_url:str,secret:str,device:str="pc"):
    """Legacy terminal client retained for diagnostics; DesktopShell is the normal surface."""
    import asyncio, httpx
    def on_wake(audio_path:str):
        async def send():
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    with open(audio_path,"rb") as f:
                        r=await client.post(f"{core_url}/api/chat/voice",headers={"Authorization":f"Bearer {secret}"},params={"device":device},files={"audio":("message.wav",f,"audio/wav")})
                    print(r.json())
            finally:Path(audio_path).unlink(missing_ok=True)
        asyncio.run(send())
    listener=WakeWordListener(on_wake=on_wake); listener.start()
    try:
        while True:await asyncio.sleep(1)
    except KeyboardInterrupt:listener.stop()
