from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import logging
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, UploadFile, File, Header, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

import llm
import memory
import brain_backup
from action_intent import ActionIntent, ActionPlan, describe_action, detect_action, parse_action_plan, parse_structured_intent
from config import (
    ACTION_ENGINE_ENABLED,
    ACTION_CONFIRM_POLICY,
    ACTION_MAX_LEVEL,
    ACTION_PLAN_MAX,
    ASSISTANT_NAME,
    AUTO_FACTS_ENABLED,
    BACKUP_ENABLED,
    DATA_DIR,
    DEVICE_TOKEN_TTL_DAYS,
    DEVICE_TOKENS_ENABLED,
    ENVIRONMENT,
    VAULT_STATUS,
    MAX_AUDIO_UPLOAD_MB,
    MEMORY_CONTEXT_MAX_CHARS,
    PRIVACY_MODE,
    PROACTIVE_ENABLED_DEFAULT,
    STT_ENABLED,
    TTS_ENABLED,
    VERSION,
)
from personality import build_system_prompt
from voice import get_available_voices, speech_to_text, text_to_speech
from authz import (
    CAP_ACTIONS_REQUEST, CAP_BACKUP_CREATE, CAP_CHAT, CAP_DIAGNOSTICS,
    CAP_MEMORY_READ, CAP_MEMORY_WRITE, CAP_PROACTIVE_CONTROL, CAP_PROACTIVE_READ,
    CAP_VOICE, Principal, authenticate, effective_device, can_request_actions,
    require_capability, require_master,
)

require_chat = require_capability(CAP_CHAT)
require_diagnostics = require_capability(CAP_DIAGNOSTICS)
require_memory_read = require_capability(CAP_MEMORY_READ)
require_memory_write = require_capability(CAP_MEMORY_WRITE)
require_voice = require_capability(CAP_VOICE)
require_backup_create = require_capability(CAP_BACKUP_CREATE)
require_proactive_read = require_capability(CAP_PROACTIVE_READ)
require_proactive_control = require_capability(CAP_PROACTIVE_CONTROL)

logger = logging.getLogger("lumen.api")
router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str = Field(default="", max_length=64, pattern=r"^[\w-]*$")
    device: str = Field(default="pc", min_length=1, max_length=40)
    profile: str = Field(default="", max_length=20)
    context: int | None = Field(default=None, ge=512, le=32768)
    intent: dict | None = None
    pc_context: dict | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: str
    kind: str = "chat"
    action_id: str | None = None
    request_id: str | None = None
    confirmation_required: bool = False
    preview: str | list[str] | None = None
    action: dict | None = None
    plan: dict | None = None


class CancelRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[\w-]+$")


class ActionCompleteRequest(BaseModel):
    action_id: str = Field(min_length=8, max_length=80, pattern=r"^[\w-]+$")
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[\w-]+$")
    device: str = Field(default="pc", min_length=1, max_length=40)
    success: bool
    message: str = Field(min_length=1, max_length=12000)
    data: dict = Field(default_factory=dict)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class FactRequest(BaseModel):
    category: str = Field(min_length=1, max_length=60)
    fact: str = Field(min_length=1, max_length=1000)


class FactUpdateRequest(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    fact: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    pinned: bool = False


class OpenTaskRequest(BaseModel):
    task: str = Field(min_length=1, max_length=500)
    session_id: str = Field(default="", max_length=64)


class ProjectNoteRequest(BaseModel):
    project: str = Field(min_length=1, max_length=120)
    note: str = Field(min_length=1, max_length=1000)
    note_key: str = Field(default="general", max_length=120)


class DeviceRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[\w.-]+$")
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    permission_level: int = Field(default=0, ge=0, le=2)
    name: str = Field(default="", max_length=120)
    device_type: str = Field(default="unknown", max_length=40)


class DeviceTokenRequest(BaseModel):
    ttl_days: int = Field(default=DEVICE_TOKEN_TTL_DAYS, ge=1, le=3650)


class DevicePermissionRequest(BaseModel):
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    permission_level: int = Field(default=0, ge=0, le=2)


class PreferenceRequest(BaseModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[\w.-]+$")
    value: str = Field(max_length=300)


class ProactiveTestRequest(BaseModel):
    message: str = Field(default="Mensaje proactivo de prueba: la cola y el polling funcionan.", min_length=1, max_length=500)


def require_auth(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
    """Compatibility dependency: authentication only, no implied permissions."""
    return principal


def require_master_auth(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
    return require_master(principal)


def require_action_execution(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
    if principal.is_master or (principal.allows("actions_execute") and principal.allows("action_host")):
        return principal
    raise HTTPException(status_code=403, detail="Este dispositivo no es un Action Host autorizado.")


def require_voice_chat(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
    if not principal.allows(CAP_VOICE) or not principal.allows(CAP_CHAT):
        raise HTTPException(status_code=403, detail="El chat por voz requiere las capabilities voice y chat.")
    return principal


def _session_id(request: ChatRequest) -> str:
    return request.session_id.strip() or uuid.uuid4().hex[:12]


def _compact_pc_context(raw: dict | None) -> dict:
    """Whitelist read-only PC telemetry before it reaches the model prompt."""
    if not isinstance(raw, dict):
        return {}
    window = raw.get("active_window") if isinstance(raw.get("active_window"), dict) else {}
    ollama_context = raw.get("ollama") if isinstance(raw.get("ollama"), dict) else {}
    project_context = raw.get("project") if isinstance(raw.get("project"), dict) else {}
    project = project_context.get("active_project") if isinstance(project_context.get("active_project"), dict) else {}
    system = raw.get("system") if isinstance(raw.get("system"), dict) else {}
    if PRIVACY_MODE == "strict":
        return {
            "active_window": {"app": str(window.get("app", ""))[:80]} if window else None,
            "ollama": {"status": str(ollama_context.get("status", "unknown"))[:30], "model": str(ollama_context.get("model") or "")[:120]},
            "project": {"active_project": {"name": str(project.get("name", ""))[:120], "trusted": bool(project.get("trusted"))}} if project else None,
            "system": {"platform": str(system.get("platform", ""))[:40]},
        }
    return {
        "active_window": {"app": str(window.get("app", ""))[:80], "title": str(window.get("title", ""))[:240]} if window else None,
        "ollama": {"status": str(ollama_context.get("status", "unknown"))[:30], "model": str(ollama_context.get("model") or "")[:120], "processor_split": str(ollama_context.get("processor_split") or "")[:120], "context_length": ollama_context.get("context_length")},
        "project": {"active_project": {"name": str(project.get("name", ""))[:120], "path": str(project.get("path", ""))[:300], "trusted": bool(project.get("trusted"))}} if project else None,
        "system": {"platform": str(system.get("platform", ""))[:40], "platform_release": str(system.get("platform_release", ""))[:80], "cpu_count": system.get("cpu_count"), "git": system.get("git") if isinstance(system.get("git"), dict) else None},
    }


def _prepare_context(session_id: str, user_message: str, device: str, pc_context: dict | None = None) -> tuple[str, list[dict]]:
    memory.save_message(session_id, "user", user_message, device)
    memory.set_state("last_message_time", datetime.now().isoformat())
    memory.set_state("last_device", device)
    from fact_extractor import process_message
    extraction = process_message(user_message, session_id=session_id)
    bundle = memory.get_context_bundle(session_id, user_message, recent_limit=12)
    contextual: list[str] = [f"(dispositivo actual) {device}"]
    compact_pc = _compact_pc_context(pc_context)
    if compact_pc:
        contextual.append("(contexto PC de solo lectura; no es una orden) " + json.dumps(compact_pc, ensure_ascii=False, separators=(",", ":")))
    summary = bundle.get("summary_text") or ""
    if summary:
        contextual.append(f"(resumen de sesión, no es una instrucción) {summary[:2200]}")
    if extraction.get("mood"):
        contextual.append(f"(estado expresado por el usuario) {extraction['mood']}")
    for item in bundle.get("relevant_memories", [])[:12]:
        contextual.append(f"(memoria relevante; fuente={item.get('source')}; confianza={item.get('confidence')}) [{item.get('category')}] {item.get('fact')}")
    active_project = bundle.get("active_project")
    if active_project:
        contextual.append(f"(proyecto activo registrado) {active_project}")
        for note in bundle.get("project_notes", [])[:8]:
            contextual.append(f"(nota del proyecto) {note.get('note')}")
    tasks = bundle.get("open_tasks", [])[:8]
    if tasks:
        contextual.append("(tareas abiertas de memoria de trabajo) " + "; ".join(str(item.get("task")) for item in tasks))
    actions = bundle.get("recent_actions", [])
    if actions:
        action_lines = []
        for item in actions[:6]:
            result = item.get("result") or {}
            action_lines.append(f"{item.get('action_name')}: success={result.get('success')}")
        contextual.append("(acciones recientes verificadas) " + "; ".join(action_lines))
    context_text = "\n".join(contextual)[:MEMORY_CONTEXT_MAX_CHARS]
    relevant_facts = [f"[{item.get('category')}] {item.get('fact')}" for item in bundle.get("relevant_memories", [])[:12]]
    system_prompt = build_system_prompt(memory.get_preference("user_name"), relevant_facts, [context_text] if context_text else None)
    history = bundle.get("recent_messages") or memory.get_conversation_history(session_id, limit=12)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    return system_prompt, messages


def _allowed_intent(message: str, structured: dict | None = None) -> ActionIntent | ActionPlan | None:
    """Fast deterministic/explicit route; never calls an executor."""
    if not ACTION_ENGINE_ENABLED:
        return None
    if structured and isinstance(structured, dict) and structured.get("type") == "plan":
        intent = parse_action_plan(structured, max_actions=ACTION_PLAN_MAX, max_risk=ACTION_MAX_LEVEL)
    else:
        intent = parse_structured_intent(structured) if structured else None
    intent = intent or detect_action(message)
    if intent and intent.risk_level <= ACTION_MAX_LEVEL:
        return intent
    return None


def _action_policy_notice(intent: ActionIntent | ActionPlan | None) -> str | None:
    if not intent:
        return None
    if ACTION_CONFIRM_POLICY == "BLOCKED":
        return "Acciones deshabilitadas por configuración; no se ejecutó nada."
    if ACTION_CONFIRM_POLICY == "AUTO_SAFE" and intent.risk_level > 1:
        return "La acción requiere ejecución controlada y AUTO_SAFE solo permite acciones de nivel 1; no se ejecutó nada."
    return None


def _apply_action_policy(intent: ActionIntent | ActionPlan | None) -> ActionIntent | ActionPlan | None:
    if not intent or ACTION_CONFIRM_POLICY == "BLOCKED":
        return None
    if ACTION_CONFIRM_POLICY == "AUTO_SAFE" and intent.risk_level > 1:
        return None
    if ACTION_CONFIRM_POLICY == "CONFIRM_EXECUTION":
        return replace(intent, confirmation_required=True)
    return intent


def _action_contract(intent: ActionIntent | ActionPlan, action_id: str, session_id: str, request_id: str = "") -> dict:
    """Build the one response schema consumed by Core, PC GUI and terminal."""
    confirmation_required = bool(intent.confirmation_required)
    if isinstance(intent, ActionPlan):
        actions = []
        previews = []
        for item in intent.actions:
            action = item.as_dict()
            action.pop("confirmation_required", None)
            action["type"] = "action"
            actions.append(action)
            previews.append(describe_action(item))
        plan = {"type": "plan", "plan_id": action_id, "actions": actions, "risk_level": intent.risk_level, "confidence": intent.confidence, "source": intent.source}
        response = "GAIA quiere ejecutar:\n" + "\n".join(f"{index}. {text}" for index, text in enumerate(previews, 1))
        return {"kind": "plan", "response": response, "action_id": action_id, "session_id": session_id, "request_id": request_id, "confirmation_required": confirmation_required, "preview": previews, "plan": plan}
    action = intent.as_dict()
    action.pop("confirmation_required", None)
    action["type"] = "action"
    preview = describe_action(intent)
    return {"kind": "action", "response": preview, "action_id": action_id, "session_id": session_id, "request_id": request_id, "confirmation_required": confirmation_required, "preview": preview, "action": action}


async def _allowed_intent_with_llm(message: str, structured: dict | None = None) -> ActionIntent | ActionPlan | None:
    intent = _allowed_intent(message, structured)
    if intent:
        return intent
    if not ACTION_ENGINE_ENABLED:
        return None
    from intent_classifier import classify_intent
    proposed = await classify_intent(message)
    if proposed and proposed.risk_level <= ACTION_MAX_LEVEL:
        return proposed
    return None


@router.get("/health")
async def health():
    return {"name": ASSISTANT_NAME, "version": VERSION, "status": "online"}


@router.get("/status", dependencies=[Depends(require_diagnostics)])
async def status():
    from proactive import is_enabled
    return {
        "name": ASSISTANT_NAME, "version": VERSION, "environment": ENVIRONMENT, "status": "online",
        "llm": await llm.check_backend(), "memory": memory.get_stats(), "backup_enabled": BACKUP_ENABLED,
        "vault": brain_backup.vault_status(), "devices": len(memory.get_devices()),
        "voice": {"tts_enabled": TTS_ENABLED, "stt_enabled": STT_ENABLED},
        "features": {"auto_facts": AUTO_FACTS_ENABLED, "proactive_auto": is_enabled(), "proactive_muted": __import__("proactive").is_muted(), "proactive_default": PROACTIVE_ENABLED_DEFAULT,
                     "streaming": True, "action_engine": ACTION_ENGINE_ENABLED, "action_max_level": ACTION_MAX_LEVEL},
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/diagnostics", dependencies=[Depends(require_diagnostics)])
async def diagnostics():
    stats = memory.get_stats()
    vault = brain_backup.vault_status()
    from backup_scheduler import backup_runtime_status
    return {
        "core": {"name": ASSISTANT_NAME, "version": VERSION, "environment": ENVIRONMENT, "status": "online", "timestamp": datetime.now().isoformat()},
        "lan": {"enabled": __import__("config").LAN_ENABLED, "host": __import__("config").HOST, "tls": False, "warning": "LAN requiere opt-in explícito y TLS externo." if __import__("config").LAN_ENABLED else "Solo localhost por defecto."},
        "database": {"status": "ok", "schema_version": stats.get("schema_version"), "fts5": stats.get("fts5"), "size_mb": stats.get("db_size_mb"), "messages": stats.get("total_messages")},
        "vault": {"status": vault.get("status"), "configured": bool(vault.get("root")), "fallback_warning": vault.get("fallback_warning", "")},
        "ollama": await llm.check_backend(),
        "voice": {"tts_enabled": TTS_ENABLED, "stt_enabled": STT_ENABLED, "audio_retention": __import__("config").AUDIO_RETENTION},
        "action_engine": {"enabled": ACTION_ENGINE_ENABLED, "max_level": ACTION_MAX_LEVEL, "confirm_policy": ACTION_CONFIRM_POLICY},
        "auth": {"model": "master_or_device_capabilities", "rbac_enabled": True, "brain_restore": "master_only"},
        "backup_scheduler": backup_runtime_status(),
        "devices": {"registered": len(memory.get_devices()), "tokens_enabled": DEVICE_TOKENS_ENABLED},
        "version": VERSION,
    }


async def _chat_service(req: ChatRequest, principal: Principal) -> ChatResponse:
    session_id = _session_id(req)
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío.")
    device_id = effective_device(principal, req.device)
    memory.touch_device(device_id)
    candidate = await _allowed_intent_with_llm(user_message, req.intent) if can_request_actions(principal) else None
    notice = _action_policy_notice(candidate)
    if notice:
        memory.save_message(session_id, "user", user_message, device_id)
        memory.save_message(session_id, "assistant", notice, device_id)
        return ChatResponse(response=notice, session_id=session_id, timestamp=datetime.now().isoformat())
    intent = _apply_action_policy(candidate)
    if intent:
        action_id = uuid.uuid4().hex
        memory.save_message(session_id, "user", user_message, device_id)
        memory.set_state("last_message_time", datetime.now().isoformat())
        memory.set_state("last_device", device_id)
        memory.set_state(f"pending_action:{action_id}", json.dumps({"session_id": session_id, "device": device_id, "principal_type": principal.type, "device_id": principal.device_id, "token_id": principal.token_id, "intent": intent.as_dict()}))
        contract = _action_contract(intent, action_id, session_id)
        return ChatResponse(timestamp=datetime.now().isoformat(), **contract)
    system_prompt, messages = _prepare_context(session_id, user_message, device_id, req.pc_context)
    try:
        response_text = await llm.chat_completion(system_prompt, messages, profile=req.profile or None, context_override=req.context)
    except llm.LLMError as exc:
        logger.warning("Fallo de chat: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    memory.save_message(session_id, "assistant", response_text, device_id)
    return ChatResponse(response=response_text, session_id=session_id, timestamp=datetime.now().isoformat())


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, principal: Annotated[Principal, Depends(require_chat)]):
    return await _chat_service(req, principal)


async def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _assistant_stream(req: ChatRequest, principal: Principal) -> AsyncIterator[str]:
    session_id = _session_id(req)
    user_message = req.message.strip()
    if not user_message:
        yield await _sse_event("error", {"detail": "El mensaje no puede estar vacío."})
        return
    device_id = effective_device(principal, req.device)
    memory.touch_device(device_id)
    request_id = uuid.uuid4().hex
    cancel_key = f"cancel:{request_id}"
    owner_key = f"request_owner:{request_id}"
    memory.set_state(cancel_key, "0")
    memory.set_state(owner_key, json.dumps({"request_id": request_id, "principal_type": principal.type, "device_id": principal.device_id, "token_id": principal.token_id, "session_id": session_id, "created_at": datetime.now().isoformat()}))
    yield await _sse_event("meta", {"session_id": session_id, "request_id": request_id})
    candidate = await _allowed_intent_with_llm(user_message, req.intent) if can_request_actions(principal) else None
    notice = _action_policy_notice(candidate)
    if notice:
        memory.save_message(session_id, "user", user_message, device_id)
        memory.save_message(session_id, "assistant", notice, device_id)
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        yield await _sse_event("done", {"kind": "chat", "response": notice, "session_id": session_id, "request_id": request_id, "timestamp": datetime.now().isoformat()})
        return
    intent = _apply_action_policy(candidate)
    if intent:
        action_id = uuid.uuid4().hex
        memory.save_message(session_id, "user", user_message, device_id)
        memory.set_state(f"pending_action:{action_id}", json.dumps({"session_id": session_id, "device": device_id, "principal_type": principal.type, "device_id": principal.device_id, "token_id": principal.token_id, "intent": intent.as_dict(), "request_id": request_id}))
        payload = _action_contract(intent, action_id, session_id, request_id)
        yield await _sse_event("action", payload)
        yield await _sse_event("done", {**payload, "timestamp": datetime.now().isoformat()})
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        return

    system_prompt, messages = _prepare_context(session_id, user_message, device_id, req.pc_context)
    chunks: list[str] = []
    try:
        async for chunk in llm.chat_completion_stream(system_prompt, messages, profile=req.profile or None, context_override=req.context):
            if memory.get_state(cancel_key, "0") == "1":
                yield await _sse_event("cancelled", {"session_id": session_id, "request_id": request_id, "detail": "Generación cancelada por el usuario."})
                memory.delete_state(owner_key)
                memory.delete_state(cancel_key)
                return
            if chunk:
                chunks.append(chunk)
                yield await _sse_event("token", {"text": chunk})
    except llm.LLMError as exc:
        logger.warning("Fallo de streaming: %s", exc)
        yield await _sse_event("error", {"detail": str(exc), "session_id": session_id, "request_id": request_id})
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        return
    response_text = "".join(chunks).strip()
    if not response_text:
        yield await _sse_event("error", {"detail": "El backend no devolvió texto visible.", "session_id": session_id, "request_id": request_id})
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        return
    memory.save_message(session_id, "assistant", response_text, device_id)
    memory.set_state(cancel_key, "done")
    yield await _sse_event("done", {"kind": "chat", "response": response_text, "session_id": session_id, "request_id": request_id, "timestamp": datetime.now().isoformat()})
    memory.delete_state(owner_key)
    memory.delete_state(cancel_key)


@router.post("/assistant/stream")
async def assistant_stream(req: ChatRequest, principal: Annotated[Principal, Depends(require_chat)]):
    return StreamingResponse(_assistant_stream(req, principal), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, principal: Annotated[Principal, Depends(require_chat)]):
    return StreamingResponse(_assistant_stream(req, principal), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@router.post("/assistant/cancel")
async def cancel_assistant(req: CancelRequest, principal: Annotated[Principal, Depends(require_chat)]):
    owner_key = f"request_owner:{req.request_id}"
    raw_owner = memory.get_state(owner_key)
    if not raw_owner:
        raise HTTPException(status_code=404, detail="La generación no existe, terminó o expiró.")
    try:
        owner = json.loads(raw_owner)
        created_at = datetime.fromisoformat(str(owner.get("created_at", "")))
        if (datetime.now() - created_at).total_seconds() > 900:
            memory.delete_state(owner_key)
            memory.delete_state(f"cancel:{req.request_id}")
            raise HTTPException(status_code=404, detail="La generación expiró y su ownership fue limpiado.")
    except (json.JSONDecodeError, ValueError):
        memory.delete_state(owner_key)
        memory.delete_state(f"cancel:{req.request_id}")
        raise HTTPException(status_code=404, detail="La generación no tiene ownership válido.")
    if not principal.is_master:
        same_device = owner.get("principal_type") == "device" and owner.get("device_id") == principal.device_id and owner.get("token_id") == principal.token_id
        if not same_device:
            raise HTTPException(status_code=403, detail="Solo el Principal propietario puede cancelar esta generación.")
    memory.set_state(f"cancel:{req.request_id}", "1")
    return {"status": "cancel_requested", "request_id": req.request_id}


@router.post("/actions/complete")
async def complete_action(req: ActionCompleteRequest, principal: Annotated[Principal, Depends(require_action_execution)]):
    state_key = f"pending_action:{req.action_id}"
    raw = memory.get_state(state_key)
    if not raw:
        raise HTTPException(status_code=404, detail="La acción ya no está pendiente o expiró.")
    try:
        pending = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Estado de acción inválido.") from exc
    if pending.get("completed"):
        raise HTTPException(status_code=409, detail="La acción ya fue completada.")
    if pending.get("session_id") != req.session_id:
        raise HTTPException(status_code=409, detail="La sesión no coincide con la acción pendiente.")
    if not principal.is_master:
        same_device = pending.get("principal_type") == "device" and pending.get("device_id") == principal.device_id and pending.get("token_id") == principal.token_id
        if not same_device:
            raise HTTPException(status_code=403, detail="La acción pertenece a otro Principal.")
    pending_intent = pending.get("intent", {}) if isinstance(pending.get("intent"), dict) else {}
    if pending_intent.get("type") == "plan" and req.data.get("plan_id") != req.action_id:
        raise HTTPException(status_code=409, detail="El resultado no referencia el plan pendiente correcto.")
    deterministic_result = req.message.strip()
    validated_payload = json.dumps({"action": pending.get("intent", {}), "success": req.success, "result": req.data}, ensure_ascii=False)[:12000]
    natural_response = deterministic_result
    generated_by_llm = False
    try:
        safe_prompt = build_system_prompt(memory.get_preference("user_name"), memory.get_facts_summary(), None) + "\n\nREGLA DE POST-ACCIÓN: solo verbaliza el resultado validado que sigue. No propongas ni ejecutes acciones. No inventes datos. Responde en español y conserva tu personalidad."
        natural_response = await asyncio.wait_for(llm.chat_completion(safe_prompt, [{"role": "user", "content": f"Resultado validado del cliente local:\n{validated_payload}"}], profile="fast"), timeout=30.0)
        generated_by_llm = True
    except (asyncio.TimeoutError, llm.LLMError) as exc:
        logger.info("Post-action natural fallback: %s", exc)
    result_payload = {"success": req.success, "cancelled": bool(req.data.get("cancelled")), "message": deterministic_result, "data": req.data, "natural_response": natural_response}
    device_id = effective_device(principal, req.device)
    memory.save_action(req.action_id, req.session_id, device_id, pending_intent, result_payload)
    memory.save_message(req.session_id, "assistant", natural_response, device_id)
    memory.set_state(state_key, json.dumps({"completed": True, **result_payload}))
    return {"status": "completed", "action_id": req.action_id, "session_id": req.session_id, "response": natural_response, "deterministic_response": deterministic_result, "success": req.success, "data": req.data, "generated_by_llm": generated_by_llm, "timestamp": datetime.now().isoformat()}


@router.post("/chat/voice")
async def chat_voice(principal: Annotated[Principal, Depends(require_voice_chat)], audio: UploadFile = File(...), session_id: str = "", device: str = "pc"):
    suffix = Path(audio.filename or "audio.wav").suffix.lower() or ".wav"
    if suffix not in {".wav", ".mp3", ".m4a", ".ogg", ".webm"}:
        raise HTTPException(status_code=415, detail="Formato de audio no admitido.")
    content = await audio.read((MAX_AUDIO_UPLOAD_MB * 1024 * 1024) + 1)
    if len(content) > MAX_AUDIO_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Archivo de audio demasiado grande.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        try:
            user_text = await asyncio.to_thread(speech_to_text, tmp_path)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Falló la transcripción: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if not user_text.strip():
        raise HTTPException(status_code=400, detail="No se detectó voz en el audio.")
    chat_resp = await _chat_service(ChatRequest(message=user_text, session_id=session_id, device=device), principal)
    audio_url: str | None = None
    tts_error: str | None = None
    if TTS_ENABLED and chat_resp.kind == "chat":
        try:
            audio_path = await text_to_speech(chat_resp.response)
            audio_url = f"/api/voice/audio/{Path(audio_path).name}"
        except Exception as exc:
            tts_error = str(exc)
            logger.warning("Respuesta generada, pero TTS falló: %s", exc)
    return {"user_text": user_text, "response": chat_resp.response, "session_id": chat_resp.session_id, "timestamp": chat_resp.timestamp, "kind": chat_resp.kind, "action_id": chat_resp.action_id, "request_id": chat_resp.request_id, "confirmation_required": chat_resp.confirmation_required, "preview": chat_resp.preview, "action": chat_resp.action, "plan": chat_resp.plan, "audio_url": audio_url, "tts_error": tts_error}


@router.get("/voice/audio/{filename}", dependencies=[Depends(require_voice)])
async def get_audio(filename: str):
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Nombre de audio inválido.")
    audio_path = DATA_DIR / "audio" / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio no encontrado.")
    return FileResponse(str(audio_path), media_type="audio/mpeg", filename=filename)


@router.post("/voice/tts", dependencies=[Depends(require_voice)])
async def tts_only(req: TTSRequest):
    try:
        audio_path = await text_to_speech(req.text)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return FileResponse(str(audio_path), media_type="audio/mpeg")


@router.get("/voice/voices", dependencies=[Depends(require_voice)])
async def list_voices():
    return await get_available_voices()


@router.post("/memory/fact", dependencies=[Depends(require_memory_write)])
async def add_fact(req: FactRequest):
    memory.save_fact(req.category.strip(), req.fact.strip(), source="manual", confidence=1.0)
    return {"status": "saved"}


@router.delete("/memory/fact/{fact_id}", dependencies=[Depends(require_memory_write)])
async def remove_fact(fact_id: int):
    if not memory.delete_fact(fact_id):
        raise HTTPException(status_code=404, detail="Fact no encontrado.")
    return {"status": "deleted"}


@router.post("/memory/fact/{fact_id}", dependencies=[Depends(require_memory_write)])
async def edit_fact(fact_id: int, req: FactUpdateRequest):
    if not memory.update_fact(fact_id, req.category.strip(), req.fact.strip(), req.confidence, req.pinned):
        raise HTTPException(status_code=404, detail="Recuerdo no encontrado.")
    return {"status": "updated", "id": fact_id}


@router.get("/memory/fact/{fact_id}/history", dependencies=[Depends(require_memory_read)])
async def fact_history(fact_id: int):
    return memory.get_fact_history(fact_id)


@router.get("/memory/search", dependencies=[Depends(require_memory_read)])
async def memory_search(query: str = Query(default="", max_length=500), category: str | None = Query(default=None, max_length=80), limit: int = Query(default=12, ge=1, le=50)):
    return memory.search_memories(query, category, limit)


@router.get("/memory/tasks", dependencies=[Depends(require_memory_read)])
async def memory_tasks(limit: int = Query(default=30, ge=1, le=100)):
    return memory.get_open_tasks(limit)


@router.post("/memory/tasks", dependencies=[Depends(require_memory_write)])
async def add_memory_task(req: OpenTaskRequest):
    return {"status": "saved", "id": memory.save_open_task(req.task, req.session_id)}


@router.post("/memory/tasks/{task_id}/close", dependencies=[Depends(require_memory_write)])
async def close_memory_task(task_id: int):
    if not memory.close_open_task(task_id):
        raise HTTPException(status_code=404, detail="Tarea abierta no encontrada.")
    return {"status": "closed", "id": task_id}


@router.post("/memory/project-note", dependencies=[Depends(require_memory_write)])
async def add_project_note(req: ProjectNoteRequest):
    memory.save_project_note(req.project, req.note, req.note_key)
    return {"status": "saved", "project": req.project}


@router.get("/memory/project-notes", dependencies=[Depends(require_memory_read)])
async def project_notes(project: str = Query(min_length=1, max_length=120)):
    return memory.get_project_notes(project)


@router.get("/memory/sessions/{session_id}/summary", dependencies=[Depends(require_memory_read)])
async def session_summary(session_id: str, refresh: bool = False):
    summary = memory.maybe_update_session_summary(session_id, force=refresh)
    return {"session_id": session_id, "summary": summary, **memory.get_session_summary_record(session_id)}


@router.get("/memory/context/{session_id}", dependencies=[Depends(require_memory_read)])
async def memory_context(session_id: str, query: str = Query(default="", max_length=500)):
    return memory.get_context_bundle(session_id, query)


@router.get("/memory/facts", dependencies=[Depends(require_memory_read)])
async def get_facts(category: str | None = None):
    return memory.get_facts(category)


@router.post("/devices/register", dependencies=[Depends(require_master_auth)])
async def register_device(req: DeviceRequest):
    memory.register_device(req.device_id, req.capabilities, req.permission_level, req.name, req.device_type)
    memory.record_admin_audit("master", None, "device_register", req.device_id, "success", {"capabilities": sorted(set(req.capabilities)), "permission_level": min(2, req.permission_level)})
    return {"status": "registered", "device_id": req.device_id, "permission_level": min(2, req.permission_level)}


@router.get("/devices", dependencies=[Depends(require_master_auth)])
async def list_devices():
    return memory.get_devices()


@router.get("/admin/audit", dependencies=[Depends(require_master_auth)])
async def admin_audit(limit: int = Query(default=100, ge=1, le=500)):
    return memory.get_admin_audit(limit)


@router.put("/devices/{device_id}/permissions", dependencies=[Depends(require_master_auth)])
async def update_device_permissions(device_id: str, req: DevicePermissionRequest):
    if not memory.update_device_permissions(device_id, req.capabilities, req.permission_level):
        memory.record_admin_audit("master", None, "device_permissions", device_id, "not_found")
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado.")
    memory.record_admin_audit("master", None, "device_permissions", device_id, "success", {"capabilities": sorted(set(req.capabilities)), "permission_level": req.permission_level})
    return {"status": "updated", "device_id": device_id, "permission_level": req.permission_level, "capabilities": sorted(set(req.capabilities))}


@router.get("/devices/{device_id}/self", dependencies=[Depends(require_capability("device_self"))])
async def device_self(device_id: str, principal: Annotated[Principal, Depends(authenticate)]):
    if not principal.is_master and principal.device_id != device_id:
        raise HTTPException(status_code=403, detail="Solo puedes consultar tu propio dispositivo.")
    devices = [item for item in memory.get_devices() if item.get("device_id") == device_id]
    if not devices:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado.")
    return devices[0]


@router.post("/devices/{device_id}/token", dependencies=[Depends(require_master_auth)])
async def create_device_token(device_id: str, req: DeviceTokenRequest):
    if not DEVICE_TOKENS_ENABLED:
        raise HTTPException(status_code=409, detail="Los tokens de dispositivo están desactivados.")
    try:
        created = memory.create_device_token(device_id, ttl_days=req.ttl_days)
        memory.record_admin_audit("master", None, "device_token_create", device_id, "success", {"token_id": created.get("token_id"), "ttl_days": req.ttl_days})
        return {"status": "created", **created}
    except ValueError as exc:
        memory.record_admin_audit("master", None, "device_token_create", device_id, "failed")
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/devices/{device_id}/tokens", dependencies=[Depends(require_master_auth)])
async def list_device_tokens(device_id: str):
    return memory.get_device_tokens(device_id)


@router.post("/devices/{device_id}/revoke", dependencies=[Depends(require_master_auth)])
async def revoke_device(device_id: str):
    if not memory.revoke_device(device_id):
        memory.record_admin_audit("master", None, "device_revoke", device_id, "not_found")
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado.")
    memory.record_admin_audit("master", None, "device_revoke", device_id, "success")
    return {"status": "revoked", "device_id": device_id}


@router.post("/device-tokens/{token_id}/revoke", dependencies=[Depends(require_master_auth)])
async def revoke_device_token(token_id: str):
    if not memory.revoke_device_token(token_id):
        memory.record_admin_audit("master", None, "device_token_revoke", token_id, "not_found")
        raise HTTPException(status_code=404, detail="Token no encontrado.")
    memory.record_admin_audit("master", None, "device_token_revoke", token_id, "success")
    return {"status": "revoked", "token_id": token_id}


@router.post("/memory/preference", dependencies=[Depends(require_memory_write)])
async def set_pref(req: PreferenceRequest):
    memory.set_preference(req.key, req.value)
    return {"status": "saved"}


@router.get("/memory/preferences", dependencies=[Depends(require_memory_read)])
async def get_prefs():
    return memory.get_all_preferences()


@router.get("/memory/sessions", dependencies=[Depends(require_memory_read)])
async def list_sessions():
    return memory.get_all_sessions()


@router.get("/memory/history/{session_id}", dependencies=[Depends(require_memory_read)])
async def get_history(session_id: str, limit: int = Query(default=50, ge=1, le=200)):
    return memory.get_conversation_history(session_id, limit)


@router.post("/backup", dependencies=[Depends(require_backup_create)])
async def backup():
    return {"status": "backup_created", "path": memory.create_backup()}


@router.post("/backup/brain")
async def brain_backup_create(principal: Annotated[Principal, Depends(require_backup_create)]):
    try:
        path = await asyncio.to_thread(brain_backup.create_brain_backup)
        memory.record_admin_audit(principal.type, principal.device_id, "brain_backup_create", Path(path).name, "success")
        return {"status": "brain_backup_created", "path": path}
    except Exception as exc:
        memory.record_admin_audit(principal.type, principal.device_id, "brain_backup_create", None, "failed", {"error_type": type(exc).__name__})
        raise HTTPException(status_code=503, detail="No se pudo crear el Brain Backup.") from exc


@router.post("/backup/brain/restore", dependencies=[Depends(require_master_auth)])
async def brain_backup_restore(archive: UploadFile = File(...)):
    suffix = Path(archive.filename or "backup.zip").suffix.lower()
    if suffix != ".zip":
        raise HTTPException(status_code=415, detail="El Brain Backup debe ser un ZIP.")
    content = await archive.read(100 * 1024 * 1024 + 1)
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El Brain Backup supera el límite de 100 MB.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp:
        temp.write(content)
        temp_path = Path(temp.name)
    try:
        result = await asyncio.to_thread(brain_backup.restore_brain_backup, temp_path)
        memory.record_admin_audit("master", None, "brain_restore", Path(archive.filename or "backup.zip").name, "success", {"manifest_verified": bool(result.get("manifest_verified")), "integrity": result.get("integrity")})
        return result
    except RuntimeError as exc:
        memory.record_admin_audit("master", None, "brain_restore", Path(archive.filename or "backup.zip").name, "failed", {"error_type": type(exc).__name__})
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/vault/status", dependencies=[Depends(require_diagnostics)])
async def get_vault_status():
    return brain_backup.vault_status()


@router.get("/actions/history", dependencies=[Depends(require_memory_read)])
async def action_history(session_id: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
    return memory.get_action_history(session_id, limit)


@router.get("/proactive/check", dependencies=[Depends(require_proactive_read)])
async def proactive_check():
    pending = memory.pop_proactive_message()
    return {"has_message": bool(pending), **(pending or {})}


@router.post("/proactive/test", dependencies=[Depends(require_proactive_control)])
async def proactive_test(req: ProactiveTestRequest):
    message_id = memory.enqueue_proactive_message("manual_test", req.message)
    return {"status": "queued", "id": message_id, "message": req.message}


@router.post("/proactive/toggle", dependencies=[Depends(require_proactive_control)])
async def proactive_toggle(enabled: bool = True):
    from proactive import set_enabled
    set_enabled(enabled)
    return {"status": "ok", "enabled": enabled}


@router.post("/proactive/mute", dependencies=[Depends(require_proactive_control)])
async def proactive_mute(muted: bool = True):
    from proactive import set_muted
    set_muted(muted)
    return {"status": "ok", "muted": muted}


@router.get("/profile", dependencies=[Depends(require_memory_read)])
async def user_profile():
    from fact_extractor import get_user_profile
    return get_user_profile()
