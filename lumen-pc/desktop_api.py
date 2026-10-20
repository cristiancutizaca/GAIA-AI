"""Cliente HTTP y utilidades de audio compartidas por la GUI de GAIA."""
from __future__ import annotations
import atexit
import json
import logging
import math
import os
import platform
import uuid
from urllib.parse import urlencode

import re
import subprocess
import tempfile
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx
from dotenv import load_dotenv
from action_engine import ActionEngine
from action_host import ActionHost

from action_response import parse_action_response, response_for_display
from context_providers import collect_desktop_context
from request_envelope import build_request_envelope

PROJECT_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger("lumen.desktop_api")

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

DEFAULT_URL = os.getenv("LUMEN_CORE_URL", "http://127.0.0.1:8090").rstrip("/")
DEFAULT_SECRET = os.getenv("LUMEN_SECRET", "lumen-dev-key")
DEVICE = os.getenv("GAIA_PC_DEVICE_ID", "pc-main").strip() or "pc-main"

POLL_SECONDS = max(5, int(os.getenv("LUMEN_PROACTIVE_POLL_SECONDS", "15")))
LLM_CLIENT_TIMEOUT = max(30.0, float(os.getenv("LUMEN_LLM_TIMEOUT_SECONDS", "600")))
ACTION_CONFIRM_POLICY = os.getenv("GAIA_ACTION_CONFIRM_POLICY", "CONFIRM_EXECUTION").upper()

def _positive_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning("Configuración %s inválida; se usa %.1f.", name, default)
        return default
    if not math.isfinite(value) or value <= 0:
        logger.warning("Configuración %s fuera de rango; se usa %.1f.", name, default)
        return default
    return value

# Una sola regla efectiva para el cliente: margen sobre post-action y mínimo seguro.
POST_ACTION_TIMEOUT = _positive_float_env("GAIA_POST_ACTION_LLM_TIMEOUT", 30.0)
REQUESTED_CLIENT_TIMEOUT = _positive_float_env("GAIA_CLIENT_ACTION_TIMEOUT", 60.0)
ACTION_COMPLETION_TIMEOUT = max(60.0, REQUESTED_CLIENT_TIMEOUT, POST_ACTION_TIMEOUT + 15.0)
CAPTURE_DOWNLOAD_TIMEOUT = _positive_float_env("GAIA_CAPTURE_DOWNLOAD_TIMEOUT", 30.0)

_TEMP_FILES: list[Path] = []
MIC_PREFERENCE_FILE = Path(os.getenv("GAIA_MIC_PREFERENCE_FILE", str(Path.home() / ".gaia_mic.json"))).expanduser()


class SentenceTTSBuffer:
    """Acumula tokens y sintetiza frases completas en segundo plano."""
    def __init__(self, api: "LumenDesktopAPI") -> None:
        self.api = api
        self.buffer = ""
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gaia-tts")
        self.processes: list[object] = []

    def feed(self, text: str) -> None:
        with self.lock:
            if self.stopped.is_set():
                return
            self.buffer += text
            while True:
                match = re.search(r"^(.+?[.!?])($| )", self.buffer, flags=re.S)
                if not match:
                    break
                sentence = match.group(1).strip()
                self.buffer = self.buffer[match.end():]
                if sentence:
                    self._submit(sentence)

    def finish(self) -> None:
        with self.lock:
            tail = self.buffer.strip()
            self.buffer = ""
            if tail and not self.stopped.is_set():
                self._submit(tail)
        self.executor.shutdown(wait=False, cancel_futures=False)

    def stop(self) -> None:
        self.stopped.set()
        with self.lock:
            self.buffer = ""
        for process in list(self.processes):
            try:
                process.terminate()  # type: ignore[attr-defined]
            except (AttributeError, OSError):
                pass
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _submit(self, sentence: str) -> None:
        self.executor.submit(self._synthesize_and_play, sentence)

    def _synthesize_and_play(self, sentence: str) -> None:
        if self.stopped.is_set():
            return
        try:
            path = self.api.request_tts(sentence)
            if self.stopped.is_set():
                return
            play_audio(path, process_registry=self.processes)
        except Exception:
            # Streaming text remains useful when local TTS is unavailable.
            return


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
        self.request_id = ""
        self._active_tts: SentenceTTSBuffer | None = None
        self._plan_cancel_requested = threading.Event()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret}"}

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            with httpx.Client(timeout=kwargs.pop("timeout", LLM_CLIENT_TIMEOUT)) as client:
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

    def desktop_context(self, *, level: str = "FOREGROUND", force_refresh: bool = False) -> dict:
        try:
            return collect_desktop_context(base_dir=PROJECT_DIR, projects_file=PROJECT_DIR / "projects.json", level=level, force_refresh=force_refresh)
        except Exception:
            return {"active_window": None, "ollama": {"status": "unavailable"}, "project": {"active_project": None, "status": "unavailable"}, "system": {}, "desktop_snapshot": {"desktop_available": False, "context_level": level}}

    def request_envelope(self, text: str = "", *, channel: str = "desktop_text", target_host: str = "", context: dict | None = None) -> dict:
        context_data = context if isinstance(context, dict) else self.desktop_context()
        snapshot = context_data.get("desktop_snapshot") if isinstance(context_data.get("desktop_snapshot"), dict) else context_data
        return build_request_envelope(session_id=self.session_id, channel=channel, requesting_device=DEVICE, target_host=target_host, message=text, desktop_snapshot=snapshot)

    def action_host_status(self) -> dict:
        """Return local host metadata; capability discovery does not execute anything."""
        return ActionHost(PROJECT_DIR, policy=ACTION_CONFIRM_POLICY).public_capabilities()

    def start_pairing(self, device_id: str | None = None, capabilities: list[str] | None = None) -> dict:
        identifier = device_id or f"android-{uuid.uuid4().hex[:8]}"
        data = self._request("POST", "/api/pairing/start", json={"device_id": identifier, "capabilities": capabilities or ["chat", "actions_request", "streaming", "voice"]}, timeout=10.0).json()
        pairing_uri = str(data.get("pairing_uri") or data.get("qr_payload") or "").strip()
        if not pairing_uri and data.get("pairing_id") and data.get("code"):
            pairing_uri = "gaia://pair?" + urlencode({
                "id": str(data["pairing_id"]),
                "code": str(data["code"]),
                "url": self.base_url.rstrip("/"),
            })
        if pairing_uri:
            data["pairing_uri"] = pairing_uri
            data["qr_payload"] = pairing_uri
        return data

    def kill_switch(self) -> dict:
        return self._request("POST", "/api/actions/kill-switch", timeout=10.0).json()

    def enable_actions(self) -> dict:
        return self._request("POST", "/api/actions/enable", timeout=10.0).json()

    def send_message(self, text: str) -> dict:
        context = self.desktop_context(level="FOREGROUND")
        data = self._request("POST", "/api/chat", json={"message": text, "session_id": self.session_id, "device": DEVICE, "channel": "desktop_text", "pc_context": context, "desktop_snapshot": context.get("desktop_snapshot"), "request_envelope": self.request_envelope(text, channel="desktop_text", context=context)}).json()
        self.session_id = data.get("session_id", self.session_id)
        return data

    def send_voice(self, audio_path: Path) -> dict:
        context = self.desktop_context(level="FOREGROUND")
        envelope = self.request_envelope(channel="desktop_voice", context=context)
        form = {"channel": "desktop_voice", "request_envelope": json.dumps(envelope, ensure_ascii=False), "desktop_snapshot": json.dumps(context.get("desktop_snapshot") or {}, ensure_ascii=False)}
        with audio_path.open("rb") as handle:
            data = self._request("POST", "/api/chat/voice", params={"session_id": self.session_id, "device": DEVICE}, data=form,
                                 files={"audio": (audio_path.name, handle, "audio/wav")}, timeout=LLM_CLIENT_TIMEOUT).json()
        self.session_id = data.get("session_id", self.session_id)
        parsed = parse_action_response(data)
        if parsed:
            if parsed.confirmation_required and ACTION_CONFIRM_POLICY == "CONFIRM_EXECUTION":
                return {**data, "response": response_for_display(parsed), "confirmation_required": True}
            return self.confirm_action(data)
        return data

    def send_assistant(self, text: str, engine: ActionEngine | None = None, profile: str = "", speak: bool = False) -> dict:
        """Consume SSE and optionally synthesize complete sentences in the background."""
        self._plan_cancel_requested.clear()
        event_name = ""
        final: dict = {}
        action_data: dict | None = None
        tts_buffer = SentenceTTSBuffer(self) if speak else None
        self._active_tts = tts_buffer
        try:
            with httpx.Client(timeout=LLM_CLIENT_TIMEOUT) as client:
                context = self.desktop_context(level="FOREGROUND")
                with client.stream("POST", f"{self.base_url}/api/assistant/stream", headers=self.headers, json={"message": text, "session_id": self.session_id, "device": DEVICE, "profile": profile, "channel": "desktop_text", "pc_context": context, "desktop_snapshot": context.get("desktop_snapshot"), "request_envelope": self.request_envelope(text, channel="desktop_text", context=context)}) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if isinstance(line, bytes):
                            line = line.decode("utf-8")
                        if line.startswith("event: "):
                            event_name = line[7:].strip()
                        elif line.startswith("data: "):
                            payload = json.loads(line[6:])
                            if event_name == "meta":
                                self.session_id = payload.get("session_id", self.session_id)
                                self.request_id = payload.get("request_id", self.request_id)
                            elif event_name == "action":
                                action_data = payload
                            elif event_name == "token":
                                if tts_buffer:
                                    tts_buffer.feed(str(payload.get("text", "")))
                            elif event_name == "done":
                                final = payload
                            elif event_name == "cancelled":
                                final = {"kind": "cancelled", "response": payload.get("detail", "Generación cancelada."), "session_id": self.session_id, "request_id": self.request_id}
                            elif event_name == "error":
                                raise LumenAPIError(payload.get("detail", "El Core informó un error."))
        except httpx.RequestError as exc:
            if tts_buffer:
                tts_buffer.stop()
            raise LumenAPIError(f"No se pudo conectar con el Core: {exc}") from exc
        if tts_buffer:
            tts_buffer.finish()
        self._active_tts = None
        if action_data:
            parsed = parse_action_response(action_data)
            if not parsed:
                raise LumenAPIError("El Core devolvió una respuesta de acción inválida.")
            if parsed.confirmation_required and ACTION_CONFIRM_POLICY == "CONFIRM_EXECUTION":
                return {**action_data, "response": response_for_display(parsed), "confirmation_required": True, "tts_streamed": bool(speak)}
            result = self.confirm_action(action_data, engine=engine)
            result["tts_streamed"] = bool(speak)
            return result
        self.session_id = final.get("session_id", self.session_id)
        final["tts_streamed"] = bool(speak)
        return final

    def cancel_action(self, action_data: dict) -> dict:
        """Close a pending action/plan as cancelled without invoking ActionEngine."""
        parsed = parse_action_response(action_data)
        if not parsed:
            raise LumenAPIError("Respuesta de acción inválida o incompleta.")
        total = len(parsed.steps)
        result = {"success": False, "action": parsed.kind, "message": "Ejecución cancelada antes de comenzar.", "data": {"actions": [], "completed": 0, "total": total, "cancelled": True, "plan_id": parsed.action_id if parsed.is_plan else None}, "cancelled": True}
        completed = self._request("POST", "/api/actions/complete", json={
            "action_id": action_data["action_id"], "session_id": action_data["session_id"], "device": DEVICE,
            "success": False, "message": result["message"], "data": result["data"],
        }, timeout=ACTION_COMPLETION_TIMEOUT).json()
        completed.update({"kind": "chat", "response": result["message"], "local_result": result, "plan": parsed.plan})
        return completed

    def download_capture(self, capture_id: str) -> Path:
        candidate = str(capture_id or "").strip()
        if not re.fullmatch(r"cap_[A-Za-z0-9_-]{20,80}", candidate):
            raise LumenAPIError("capture_id inválido.")
        response = self._request("GET", f"/api/captures/{candidate}", timeout=CAPTURE_DOWNLOAD_TIMEOUT)
        path = Path(tempfile.gettempdir()) / f"gaia_{candidate}.png"
        path.write_bytes(response.content)
        _TEMP_FILES.append(path)
        return path

    def list_permissions(self) -> list[dict]:
        return self._request("GET", "/api/permissions", timeout=10.0).json().get("permissions", [])

    def discovered_apps(self, *, force_refresh: bool = False) -> list[dict]:
        return self._request("GET", "/api/apps/discovered", params={"force_refresh": bool(force_refresh)}, timeout=15.0).json().get("apps", [])

    def set_app_trust(self, app_id: str, decision: str) -> dict:
        return self._request("POST", "/api/apps/trust", json={"app_id": str(app_id), "decision": str(decision).upper()}, timeout=10.0).json()

    def revoke_app_trust(self, app_id: str) -> dict:
        return self._request("DELETE", "/api/apps/trust", json={"app_id": str(app_id)}, timeout=10.0).json()

    def trusted_folders(self) -> list[dict]:
        return self._request("GET", "/api/trusted-folders", timeout=10.0).json().get("folders", [])

    def grant_trusted_folder(self, path: str, *, label: str = "", rights: list[str] | None = None) -> dict:
        return self._request("POST", "/api/trusted-folders", json={"path": str(path), "label": str(label), "rights": rights}, timeout=10.0).json()

    def update_trusted_folder(self, folder_id: str, *, rights: list[str] | None = None, trusted: bool | None = None, label: str | None = None) -> dict:
        payload = {"folder_id": str(folder_id), "rights": rights}
        if trusted is not None:
            payload["trusted"] = bool(trusted)
        if label is not None:
            payload["label"] = str(label)
        return self._request("PATCH", "/api/trusted-folders", json=payload, timeout=10.0).json()

    def revoke_trusted_folder(self, folder_id: str) -> dict:
        return self._request("DELETE", "/api/trusted-folders", json={"folder_id": str(folder_id)}, timeout=10.0).json()

    def grant_permission(self, capability: str, resource_scope: str, decision: str, risk_level: int, device_id: str = DEVICE) -> dict:
        return self._request("POST", "/api/permissions", json={
            "capability": capability, "resource_scope": resource_scope, "decision": decision,
            "risk_level": int(risk_level), "device_id": device_id,
        }, timeout=10.0).json()

    def revoke_permission(self, capability: str, resource_scope: str = "", device_id: str = DEVICE) -> dict:
        return self._request("DELETE", "/api/permissions", params={"capability": capability, "resource_scope": resource_scope, "device_id": device_id}, timeout=10.0).json()

    def confirm_permission(self, request_id: str, decision: str, *, session_id: str = "") -> dict:
        """Send a Core-owned allow/reject request; DENY must never approve."""
        action_id = str(request_id or "").strip()
        target_session = str(session_id or self.session_id or "").strip()
        normalized = str(decision or "").strip().upper()
        if not action_id or not target_session:
            raise LumenAPIError("Se requiere action_id y session_id de la solicitud original.")
        if normalized in {"DENY", "REJECT", "CANCEL", "ALWAYS_DENY"}:
            path, normalized = "/api/actions/reject", "DENY"
        elif normalized in {"CONFIRM_ONCE", "ALLOW_ONCE", "ALWAYS_ALLOW"}:
            path = "/api/actions/approve"
            if normalized == "CONFIRM_ONCE":
                normalized = ""  # Core treats the absence of a grant as one-time confirmation.
        else:
            raise LumenAPIError("Decisión de permiso no reconocida.")
        return self._request("POST", path, json={
            "action_id": action_id, "session_id": target_session,
            "decision": normalized,
        }, timeout=10.0).json()

    def remote_action_host_status(self) -> dict:
        """Authenticated heartbeat state, not just local capability discovery."""
        return self._request("GET", "/api/action-host/status", timeout=8.0).json()

    def actions_control_status(self) -> dict:
        return self._request("GET", "/api/actions/control", timeout=8.0).json()

    def confirm_action(self, action_data: dict, engine: ActionEngine | None = None, permission_decision: str | None = None) -> dict:
        """Execute a previously previewed action/plan through the separated PC Action Host."""
        parsed = parse_action_response(action_data)
        if not parsed:
            raise LumenAPIError("Respuesta de acción inválida o incompleta.")
        permission_ids: list[int] = []
        if permission_decision:
            entries = action_data.get("permission_entries")
            if not isinstance(entries, list) or not entries:
                raise LumenAPIError("El Core no entregó permission_entries autoritativas; no se crea ningún grant.")
            if permission_decision == "ALWAYS_ALLOW" and not all(bool(entry.get("allow_always")) for entry in entries if isinstance(entry, dict)):
                raise LumenAPIError("El scope solicitado no admite un grant persistente para esta acción.")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise LumenAPIError("permission_entries inválidas; no se crea ningún grant.")
                capability = str(entry.get("capability") or "")
                scope = str(entry.get("resource_scope") or "")[:500]
                if not capability or not scope or "unresolved" in scope:
                    raise LumenAPIError("Scope de permiso vacío o no resuelto; se requiere autorización puntual.")
                grant = self.grant_permission(capability, scope, permission_decision, int(entry.get("risk_level", 0)), DEVICE)
                if grant.get("permission_id") is not None:
                    permission_ids.append(int(grant["permission_id"]))
        host = ActionHost(PROJECT_DIR, policy=ACTION_CONFIRM_POLICY)
        if engine is not None:
            host.engine = engine
            host.coordinator.engine = engine
        verified = host.execute({**action_data, "device": DEVICE}, confirmed=True)
        local_result = verified.as_dict()
        if local_result.get("blocked"):
            return {**action_data, "response": local_result["message"], "local_result": local_result}
        completion_data = dict(local_result.get("data") or {})
        completion_data["cancelled"] = bool(local_result.get("cancelled"))
        completion_data["execution_verified"] = bool(local_result.get("execution_verified"))
        completion_data["resource_scope_version"] = action_data.get("resource_scope_version")
        completion_data["permission_entries"] = action_data.get("permission_entries") or []
        completion_data["host_version"] = local_result.get("host_version")
        completion_data["audit_digest"] = local_result.get("audit_digest")
        completion_data["permission_ids"] = permission_ids
        completed = self._request("POST", "/api/actions/complete", json={
            "action_id": action_data["action_id"], "session_id": action_data["session_id"], "device": DEVICE,
            "success": local_result["success"], "message": local_result["message"], "data": completion_data,
            "status": local_result.get("status", "FAILED"),
            "request_validated": local_result.get("request_validated"),
            "execution_attempted": local_result.get("execution_attempted"),
            "capability_available": local_result.get("capability_available"),
            "side_effect_performed": local_result.get("side_effect_performed"),
            "effect_verified": local_result.get("effect_verified"),
            "observation_completed": local_result.get("observation_completed"),
            "execution_verified": local_result.get("execution_verified"),
        }, timeout=ACTION_COMPLETION_TIMEOUT).json()
        execution_action = parsed.plan if parsed.is_plan else parsed.action
        completed.update({"kind": "chat", "response": completed.get("response") or local_result["message"], "session_id": action_data["session_id"], "action": execution_action, "plan": parsed.plan, "local_result": local_result})
        return completed

    def cancel_generation(self) -> dict:
        self._plan_cancel_requested.set()
        if self._active_tts:
            self._active_tts.stop()
            self._active_tts = None
        if not self.request_id:
            return {"status": "no_active_request"}
        return self._request("POST", "/api/assistant/cancel", json={"request_id": self.request_id}, timeout=10.0).json()

    def request_tts(self, text: str) -> Path:
        response = self._request("POST", "/api/voice/tts", json={"text": text}, timeout=90.0)
        return _save_temp(response.content, ".mp3")

    def download_audio(self, url: str) -> Path:
        path = url if url.startswith("/") else f"/{url}"
        return _save_temp(self._request("GET", path, timeout=60.0).content, ".mp3")

    def backup(self) -> dict:
        return self._request("POST", "/api/backup", timeout=30.0).json()

    def automation_status(self) -> dict:
        return self._request("GET", "/api/automation/status", timeout=10.0).json()

    def automations(self) -> dict:
        return self._request("GET", "/api/automations", timeout=10.0).json()

    def notifications(self) -> dict:
        return self._request("GET", "/api/notifications", timeout=10.0).json()

    def set_automation_mode(self, mode: str) -> dict:
        return self._request("POST", "/api/automation/mode", json={"mode": str(mode).upper()}, timeout=10.0).json()

    def pause_automation(self, paused: bool) -> dict:
        return self._request("POST", "/api/automation/pause", params={"paused": bool(paused)}, timeout=10.0).json()

    def set_rule_enabled(self, rule_id: str, enabled: bool) -> dict:
        return self._request("POST", f"/api/automations/{rule_id}/enabled", params={"enabled": bool(enabled)}, timeout=10.0).json()

    def dismiss_notification(self, notification_id: str) -> dict:
        return self._request("PATCH", f"/api/notifications/{notification_id}", json={"read": True, "dismissed": True}, timeout=10.0).json()

    def diagnostics(self) -> dict:
        return self._request("GET", "/api/diagnostics", timeout=20.0).json()

    def facts(self) -> list[dict]:
        return self._request("GET", "/api/memory/facts", timeout=10.0).json()

    def search_memories(self, query: str) -> list[dict]:
        return self._request("GET", "/api/memory/search", params={"query": query}, timeout=10.0).json()

    def open_tasks(self) -> list[dict]:
        return self._request("GET", "/api/memory/tasks", timeout=10.0).json()

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


def list_audio_devices() -> list[dict]:
    try:
        import sounddevice as sd
        return [{"index": int(item["index"]), "name": str(item["name"]), "max_input_channels": int(item["max_input_channels"]), "default_samplerate": float(item["default_samplerate"])} for item in sd.query_devices() if int(item.get("max_input_channels", 0)) > 0]
    except ImportError as exc:
        raise LumenAPIError("Falta sounddevice para consultar micrófonos.") from exc
    except Exception as exc:
        raise LumenAPIError(f"No se pudieron consultar los micrófonos: {exc}") from exc


def get_preferred_microphone() -> int | None:
    try:
        payload = json.loads(MIC_PREFERENCE_FILE.read_text(encoding="utf-8"))
        value = payload.get("device") if isinstance(payload, dict) else None
        return int(value) if value is not None else None
    except (OSError, ValueError, TypeError):
        return None


def set_preferred_microphone(device: int | None) -> None:
    if device is not None and int(device) < 0:
        raise LumenAPIError("El índice de micrófono no puede ser negativo.")
    MIC_PREFERENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = MIC_PREFERENCE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps({"device": int(device) if device is not None else None}), encoding="utf-8")
    temp.replace(MIC_PREFERENCE_FILE)


def select_microphone() -> list[dict]:
    """List microphones and mark the persisted preference without selecting by name heuristics."""
    preferred = get_preferred_microphone()
    devices = list_audio_devices()
    for item in devices:
        item["preferred"] = preferred is not None and item["index"] == preferred
    return devices


def record_microphone(duration: int = 5, device: int | None = None) -> Path:
    duration = min(60, max(1, int(duration)))
    if device is None:
        device = get_preferred_microphone()
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise LumenAPIError("Falta sounddevice. Instala dependencias del cliente PC.") from exc
    sample_rate = 16000
    try:
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16", device=device)
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


def play_audio(path: Path, process_registry: list[object] | None = None) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return
        commands = [["afplay", str(path)]] if system == "Darwin" else [["mpv", "--no-video", str(path)], ["ffplay", "-nodisp", "-autoexit", str(path)], ["xdg-open", str(path)]]
        for command in commands:
            try:
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if process_registry is not None:
                    process_registry.append(process)
                return
            except FileNotFoundError:
                continue
        raise LumenAPIError("No hay reproductor disponible. En Linux instala mpv o ffmpeg.")
    except OSError as exc:
        raise LumenAPIError(f"No se pudo reproducir audio: {exc}") from exc
