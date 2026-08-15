"""Cliente HTTP y utilidades de audio compartidas por la GUI de LUMEN."""
from __future__ import annotations
import atexit
import os
import platform
import subprocess
import tempfile
import wave
from pathlib import Path
import httpx
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

DEFAULT_URL = os.getenv("LUMEN_CORE_URL", "http://localhost:8090").rstrip("/")
DEFAULT_SECRET = os.getenv("LUMEN_SECRET", "lumen-dev-key")
DEVICE = f"pc-gui-{platform.system().lower()}"
POLL_SECONDS = max(5, int(os.getenv("LUMEN_PROACTIVE_POLL_SECONDS", "15")))
_TEMP_FILES: list[Path] = []


def _cleanup() -> None:
    for path in _TEMP_FILES:
        path.unlink(missing_ok=True)

atexit.register(_cleanup)


class LumenAPIError(RuntimeError):
    pass


class LumenDesktopAPI:
    def __init__(self, base_url: str = DEFAULT_URL, secret: str = DEFAULT_SECRET) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.session_id = ""

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret}"}

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            with httpx.Client(timeout=kwargs.pop("timeout", 120.0)) as client:
                response = client.request(method, f"{self.base_url}{path}", headers=self.headers, **kwargs)
            if response.is_error:
                try:
                    message = response.json().get("detail", response.text)
                except ValueError:
                    message = response.text
                raise LumenAPIError(f"HTTP {response.status_code}: {message}")
            return response
        except httpx.RequestError as exc:
            raise LumenAPIError(f"No se pudo conectar con el Core: {exc}") from exc

    def health(self) -> dict:
        try:
            with httpx.Client(timeout=4.0) as client:
                response = client.get(f"{self.base_url}/api/health")
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise LumenAPIError("Core desconectado") from exc

    def status(self) -> dict:
        return self._request("GET", "/api/status", timeout=6.0).json()

    def send_message(self, text: str) -> dict:
        data = self._request("POST", "/api/chat", json={"message": text, "session_id": self.session_id, "device": DEVICE}).json()
        self.session_id = data.get("session_id", self.session_id)
        return data

    def send_voice(self, audio_path: Path) -> dict:
        with audio_path.open("rb") as handle:
            data = self._request("POST", "/api/chat/voice", params={"session_id": self.session_id, "device": DEVICE},
                                 files={"audio": (audio_path.name, handle, "audio/wav")}, timeout=240.0).json()
        self.session_id = data.get("session_id", self.session_id)
        return data

    def request_tts(self, text: str) -> Path:
        response = self._request("POST", "/api/voice/tts", json={"text": text}, timeout=90.0)
        return _save_temp(response.content, ".mp3")

    def download_audio(self, url: str) -> Path:
        path = url if url.startswith("/") else f"/{url}"
        return _save_temp(self._request("GET", path, timeout=60.0).content, ".mp3")

    def backup(self) -> dict:
        return self._request("POST", "/api/backup", timeout=30.0).json()

    def facts(self) -> list[dict]:
        return self._request("GET", "/api/memory/facts", timeout=10.0).json()

    def add_fact(self, category: str, fact: str) -> None:
        self._request("POST", "/api/memory/fact", json={"category": category, "fact": fact}, timeout=10.0)

    def delete_fact(self, fact_id: int) -> None:
        self._request("DELETE", f"/api/memory/fact/{fact_id}", timeout=10.0)

    def enqueue_test_message(self) -> dict:
        return self._request("POST", "/api/proactive/test", json={"message": "La cola proactiva funciona. No fue magia, fue polling."}, timeout=10.0).json()

    def poll_proactive(self) -> dict:
        return self._request("GET", "/api/proactive/check", timeout=10.0).json()


def _save_temp(content: bytes, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp.write(content)
        path = Path(temp.name)
    _TEMP_FILES.append(path)
    return path


def record_microphone(duration: int = 5) -> Path:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise LumenAPIError("Falta sounddevice. Instala dependencias del cliente PC.") from exc
    sample_rate = 16000
    try:
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
    except Exception as exc:
        raise LumenAPIError(f"No se pudo grabar desde el micrófono: {exc}") from exc
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
        path = Path(temp.name)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio.tobytes())
    _TEMP_FILES.append(path)
    return path


def play_audio(path: Path) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return
        commands = [["afplay", str(path)]] if system == "Darwin" else [["mpv", "--no-video", str(path)], ["ffplay", "-nodisp", "-autoexit", str(path)], ["xdg-open", str(path)]]
        for command in commands:
            try:
                subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                continue
        raise LumenAPIError("No hay reproductor disponible. En Linux instala mpv o ffmpeg.")
    except OSError as exc:
        raise LumenAPIError(f"No se pudo reproducir audio: {exc}") from exc
