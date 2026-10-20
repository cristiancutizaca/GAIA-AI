from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import hashlib
import json
import logging
import re
import tempfile
import uuid
import sys
from datetime import datetime
from urllib.parse import urlencode
from pathlib import Path
from typing import Any, Annotated, AsyncIterator

from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException, Depends, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

import llm
import memory
import advanced_memory
import brain_backup
from action_intent import ActionIntent, ActionPlan, describe_action, detect_action, detect_contextual_action, parse_action_plan, parse_structured_intent
from workspace_profiles import detect_workspace_profile, resolve_window_referent
from resource_scope import RESOURCE_SCOPE_VERSION, resolve_resource_scope
import automation_store
from automation_engine import AutomationEngine
from event_engine import Event
from config import (
    ACTION_ENGINE_ENABLED,
    GAIA_ACTIONS_ENABLED,
    GAIA_MODE,
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
    MEMORY_RELEVANCE_LIMIT,
    PRIVACY_MODE,
    SAFE_MODE,
    PROACTIVE_ENABLED_DEFAULT,
    POST_ACTION_LLM_TIMEOUT,
    PERFORMANCE_PROFILE,
    PERMISSION_PERSISTENT_MAX_RISK,
    STT_ENABLED,
    TTS_ENABLED,
    VERSION,
    LAN_ENABLED,
    PC_DEVICE_ID,
    PAIRING_SERVER_URL,
)
from personality import build_system_prompt
from voice import get_available_voices, speech_to_text, text_to_speech

_PROMPT_METRICS: dict[str, int] = {}
_RESOURCE_GOVERNOR = None


def _resource_governor():
    """Return the single runtime governor; fallback only supports import-time tests."""
    global _RESOURCE_GOVERNOR
    try:
        from automation_runtime import runtime
        return runtime.governor
    except (ImportError, AttributeError):
        if _RESOURCE_GOVERNOR is None:
            from resource_governor import ResourceGovernor
            _RESOURCE_GOVERNOR = ResourceGovernor()
        return _RESOURCE_GOVERNOR


def prompt_metrics() -> dict[str, int]:
    """Return size-only prompt metrics; no prompt content is retained."""
    return dict(_PROMPT_METRICS)
from lan_protocol import KNOWN_FEATURES, PAIRING_MANAGER, negotiate_features
from authz import (
    CAP_ACTION_HOST, CAP_ACTIONS_REQUEST, CAP_BACKUP_CREATE, CAP_CHAT, CAP_DIAGNOSTICS,
    CAP_MEMORY_READ, CAP_MEMORY_WRITE, CAP_PROACTIVE_CONTROL, CAP_PROACTIVE_READ,
    CAP_VOICE, Principal, authenticate, effective_device, can_request_actions,
    require_capability, require_master,
)

require_chat = require_capability(CAP_CHAT)
require_action_host = require_capability(CAP_ACTION_HOST)
require_diagnostics = require_capability(CAP_DIAGNOSTICS)
require_memory_read = require_capability(CAP_MEMORY_READ)
require_memory_write = require_capability(CAP_MEMORY_WRITE)
require_voice = require_capability(CAP_VOICE)
require_backup_create = require_capability(CAP_BACKUP_CREATE)
require_proactive_read = require_capability(CAP_PROACTIVE_READ)
require_proactive_control = require_capability(CAP_PROACTIVE_CONTROL)

logger = logging.getLogger("lumen.api")
router = APIRouter()

_EFFECT_CLAIM_RE = re.compile(
    r"\b(?:ya\s+)?(?:abr[ií]|he\s+abierto|abriendo|se\s+abri[oó]|cerr[eé]|he\s+cerrado|cerrando|inici[eé]|he\s+iniciado|iniciando|ejecut[eé]|he\s+ejecutado|ejecutando|elimin[eé]|he\s+eliminado|mov[ií]|he\s+movido|copi[eé]|he\s+copiado|guard[eé]|he\s+guardado|descargu[eé]|he\s+descargado|envi[eé]|he\s+enviado|modifiqu[eé]|he\s+modificado|instal[eé]|he\s+instalado|desinstal[eé]|he\s+desinstalado|reinici[eé]|he\s+reiniciado|apagu[eé]|he\s+apagado|opened|have\s+opened|opening|closed|have\s+closed|started|have\s+started|executed|deleted|moved|copied|saved|downloaded|sent|modified|installed|uninstalled|restarted|shut\s+down)\b",
    re.IGNORECASE,
)
_NON_CLAIM_PREFIX_RE = re.compile(
    r"^(?:no\b|nunca\b|jam[aá]s\b|no\s+(?:puedo|pude|he|hab[ií]a|se\s+ha)\b|podr[ií]a\b|para\b|si\b|si\s+(?:hubiera|hubiese|pudiera|pudiese)\b|if\b|could\b|would\b|to\b)",
    re.IGNORECASE,
)
_EXTERNAL_EFFECT_VERB_RE = re.compile(
    r"\b(?:abr(?:e|ir|es|as|a|an)|open(?:s|ing)?|inici(?:a|ar|as|es|e)|start(?:s|ed|ing)?|lanz(?:a|ar|as|es|e)|ejecut(?:a|ar|as|es|e)|run(?:s|ning)?|cerr(?:a|ar|as|es|e)|close(?:s|d|ing)?|elimin(?:a|ar|as|es|e)|delet(?:e|ed|ing)|muev(?:e|o|a|as|er)|mov(?:e|ed|ing)|copi(?:a|ar|as|es|e)|cop(?:y|ied|ying)|guard(?:a|ar|as|es|e)|sav(?:e|ed|ing)|descarg(?:a|ar|as|es|e)|download(?:s|ed|ing)?|envi(?:a|ar|as|es|e)|send(?:s|ing)?|modific(?:a|ar|as|es|e)|modif(?:y|ied|ying)|instal(?:a|ar|as|es|e)|install(?:s|ed|ing)?|desinstal(?:a|ar|as|es|e)|uninstall(?:s|ed|ing)?|reinici(?:a|ar|as|es|e)|restart(?:s|ed|ing)?|apag(?:a|ar|as|es|e)|shut\s+down)\b",
    re.IGNORECASE,
)
_CAPABILITY_QUESTION_RE = re.compile(
    r"(?:\b(?:tienes|tiene|dispones|dispone|cuentas)\s+(?:capacidad|permiso|una\s+acci[oó]n)|\b(?:qu[eé]|cu[aá]les?)\s+(?:aplicaciones?|apps?|acciones?)\b|\b(?:c[oó]mo)\s+(?:funciona|abres?|abrir|abro|se\s+abre|se\s+puede)\b|\b(?:es\s+seguro|conviene|para\s+qu[eé]|por\s+qu[eé])\b|\b(?:qu[eé]\s+pasar[ií]a|qu[eé]\s+(?:pasa|ocurre))\s+si\b|\bpor\s+qu[eé]\b.*\bno\s+puedes\b|^\s*[¿?]?\s*qu[eé]\s+pasar[ií]a\s+si\b|\bpuedes\s+\w+\b.*\b(?:actualmente|ahora|en\s+este\s+momento)\b)",
    re.IGNORECASE,
)
_REQUEST_FRAME_RE = re.compile(
    r"^\s*(?:(?:me\s+)?(?:puedes|podr[ií]as|ser[ií]as\s+tan\s+amable\s+de|har[ií]as\s+el\s+favor\s+de|can\s+you|could\s+you|would\s+you)\b|(?:quiero|necesito)\s+(?:que\s+)?\b|por\s+favor\b|hazme\s+el\s+favor\s+de\b|te\s+encargo\s+(?:que\s+)?\b|cuando\s+puedas,?\s+|si\s+tienes\s+un\s+momento,?\s+|en\s+cuanto\s+puedas,?\s+|no\s+te\s+olvides\s+de\s+|me\s+(?=abr(?:es|as)|inici(?:as|es)|cerr(?:as|es)|ejecut(?:as|es)|elimin(?:as|es)|muev(?:es|as)|copi(?:as|es)|guard(?:as|es)|descarg(?:as|es)|envi(?:as|es)|modific(?:as|es)|instal(?:as|es)|reinici(?:as|es)|apag(?:as|es))|(?:i\s+want\s+you\s+to|please)\b)",
    re.IGNORECASE,
)
_ACTION_REQUEST_RE = re.compile(
    r"^\s*(?:(?:gaia|g\.a\.i\.a)\s*[,;:]?\s*)?(?:abre|abrir|inicia|iniciar|ejecuta|ejecutar|cierra|cerrar|elimina|eliminar|mueve|mover|copia|copiar|guarda|guardar|descarga|descargar|env[ií]a|enviar|modifica|modificar|instala|instalar|desinstala|desinstalar|reinicia|reiniciar|apaga|apagar|open|launch|start|run|close|delete|move|copy|save|download|send|modify|install|uninstall|restart|shutdown)\b",
    re.IGNORECASE,
)
_PLAN_REQUEST_RE = re.compile(
    r"\b(?:prepara|preparar|organiza|organizar|configura|configurar|monta|montar|ponme)\b"
    r".*\b(?:entorno|ambiente|espacio|proyecto|para\s+(?:trabajar|programar)|a\s+(?:trabajar|programar))\b",
    re.IGNORECASE,
)
_DANGEROUS_PLAN_RE = re.compile(
    r"\b(?:shutdown|apaga(?:r)?|formatea(?:r)?|elimina(?:r)?|borra(?:r)?|rm|del|sudo|powershell|cmd)\b",
    re.IGNORECASE,
)
_EMPTY_RESPONSE_FALLBACK = "No obtuve una respuesta útil del modelo. Inténtalo de otra forma."
_UNAVAILABLE_ACTION_FALLBACK = "No tengo una acción segura disponible para hacer eso todavía."
_ACTIONS_DISABLED_FALLBACK = "Las acciones están detenidas temporalmente; el chat sigue disponible."
_SAFE_MODE_ACTION_FALLBACK = "SAFE_MODE_BLOCKED: Safe Mode permite chat y diagnósticos, pero bloquea acciones, automatizaciones y mutaciones externas."
_CONTEXT_REFERENCE_RE = re.compile(r"\b(?:ventana|app|aplicaci[oó]n|programa|pantalla|monitor|display|escritorio|contexto|aqu[ií]|ci[eé]rr(?:alo|la)|minim[ií]z(?:alo|la)|m[uú][eé]v(?:elo|ela)|what am i doing|where am i|active window)\b", re.IGNORECASE)
_UNVERIFIED_EXECUTION_REPORT_RE = re.compile(
    r"^\s*(?:(?:listo|tambi[eé]n|ya)\s*[,;:]?\s*)*(?:he\s+\w+(?:ado|ido|to|so|cho)|[a-záéíóúñ]+[íé])\b(?:\s+.+)?[.!]?\s*$",
    re.IGNORECASE,
)


def _actions_enabled() -> bool:
    return bool(not SAFE_MODE and ACTION_ENGINE_ENABLED and GAIA_ACTIONS_ENABLED and GAIA_MODE != "CHAT_ONLY" and memory.get_state("gaia_actions_enabled", "1") == "1")


def _safe_mode_mutation_blocked() -> None:
    if SAFE_MODE:
        raise HTTPException(status_code=409, detail="SAFE_MODE_BLOCKED: Safe Mode permite chat, diagnósticos y lectura/auditoría de memoria; bloquea mutaciones, automatizaciones y acciones externas.")


class PairingStartPayload(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    capabilities: list[str] = Field(default_factory=list, max_length=32)


class PairingCompletePayload(BaseModel):
    pairing_id: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=6, max_length=12)
    features: dict[str, str] = Field(default_factory=dict)


class FeatureNegotiationPayload(BaseModel):
    features: dict[str, str] = Field(default_factory=dict)
    request_remote_actions: bool = False


class PermissionGrantPayload(BaseModel):
    capability: str = Field(min_length=1, max_length=160)
    resource_scope: str = Field(default="", max_length=500)
    decision: str = Field(min_length=3, max_length=20)
    risk_level: int = Field(ge=0, le=4)
    device_id: str = Field(default="pc-main", min_length=1, max_length=120)
    capability_version: str = Field(default="1", max_length=40)
    expires_at: str | None = Field(default=None, max_length=80)


class AppTrustPayload(BaseModel):
    app_id: str = Field(min_length=1, max_length=160)
    decision: str = Field(min_length=3, max_length=20)


class TrustedFolderPayload(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    label: str = Field(default="", max_length=120)
    rights: list[str] | None = Field(default=None, max_length=10)
    write_allowed: bool = False


class TrustedFolderUpdatePayload(BaseModel):
    folder_id: str = Field(min_length=1, max_length=160)
    label: str | None = Field(default=None, max_length=120)
    rights: list[str] | None = Field(default=None, max_length=10)
    trusted: bool | None = None


class TrustedFolderRevokePayload(BaseModel):
    folder_id: str = Field(min_length=1, max_length=160)


class AutomationRulePayload(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    trigger: dict[str, Any] = Field(default_factory=dict)
    conditions: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    routine_id: str | None = Field(default=None, max_length=80)
    steps: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    cooldown_seconds: int = Field(default=300, ge=5, le=86400)
    quiet_hour_policy: str = Field(default="skip", max_length=20)
    run_limit: int = Field(default=0, ge=0, le=1000)
    preview_confirmed: bool = False
    enabled: bool = False


class RoutinePayload(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=5)
    max_risk: int = Field(default=0, ge=0, le=4)
    failure_policy: str = Field(default="stop", max_length=20)
    preview_confirmed: bool = False
    enabled: bool = False


class SchedulePayload(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    schedule_type: str = Field(default="ONE_TIME", max_length=20)
    timezone: str = Field(default="UTC", max_length=64)
    spec: dict[str, Any] = Field(default_factory=dict)
    missed_policy: str = Field(default="SKIP", max_length=20)
    routine_id: str | None = Field(default=None, max_length=80)
    rule_id: str | None = Field(default=None, max_length=80)
    next_due_at: str | None = Field(default=None, max_length=80)
    max_runs_per_day: int = Field(default=10, ge=1, le=1000)
    preview_confirmed: bool = False
    enabled: bool = False


class AutomationModePayload(BaseModel):
    mode: str = Field(min_length=3, max_length=24)


class NotificationUpdatePayload(BaseModel):
    read: bool | None = None
    dismissed: bool | None = None


class AutomationDryRunPayload(BaseModel):
    rule: AutomationRulePayload
    event: dict[str, Any] | None = None


def _safe_apps_module():
    pc_dir = Path(__file__).resolve().parents[2] / "lumen-pc"
    if str(pc_dir) not in sys.path:
        sys.path.insert(0, str(pc_dir))
    from safe_apps import discover_installed_apps, get_app_trust, resolve_discovered_app, revoke_app_trust, set_app_trust
    return discover_installed_apps, get_app_trust, resolve_discovered_app, revoke_app_trust, set_app_trust


def _capture_module():
    pc_dir = Path(__file__).resolve().parents[2] / "lumen-pc"
    if str(pc_dir) not in sys.path:
        sys.path.insert(0, str(pc_dir))
    from screen_capture import get_capture_record
    return get_capture_record


def _trusted_folders_module():
    pc_dir = Path(__file__).resolve().parents[2] / "lumen-pc"
    if str(pc_dir) not in sys.path:
        sys.path.insert(0, str(pc_dir))
    from trusted_folders import grant_trusted_folder, list_trusted_folders, revoke_trusted_folder, update_trusted_folder
    return grant_trusted_folder, list_trusted_folders, revoke_trusted_folder, update_trusted_folder


def _actions_control_payload(*, pending_cancelled: int = 0) -> dict:
    return {"enabled": _actions_enabled(), "configured_enabled": bool(GAIA_ACTIONS_ENABLED), "mode": GAIA_MODE, "pending_cancelled": int(pending_cancelled)}


@router.post("/pairing/start")
async def pairing_start(payload: PairingStartPayload, principal: Annotated[Principal, Depends(require_master)]):
    if not LAN_ENABLED:
        raise HTTPException(status_code=409, detail="LAN/pairing está desactivado; activa GAIA_LAN_ENABLED de forma explícita.")
    result = PAIRING_MANAGER.start(payload.device_id, payload.capabilities)
    result["pairing_uri"] = "gaia://pair?" + urlencode({
        "id": result["pairing_id"],
        "code": result["code"],
        "url": PAIRING_SERVER_URL,
    })
    result["qr_payload"] = result["pairing_uri"]
    return result


@router.post("/pairing/complete")
async def pairing_complete(payload: PairingCompletePayload):
    if not LAN_ENABLED:
        raise HTTPException(status_code=409, detail="LAN/pairing está desactivado; activa GAIA_LAN_ENABLED de forma explícita.")
    if not DEVICE_TOKENS_ENABLED:
        raise HTTPException(status_code=409, detail="El onboarding requiere tokens de dispositivo habilitados.")
    try:
        paired = PAIRING_MANAGER.complete(payload.pairing_id, payload.code)
        device_id = str(paired.get("device_id") or "").strip()
        if not device_id:
            raise ValueError("La sesión de pairing no contiene un device_id válido.")
        requested = {str(item).strip() for item in paired.get("capabilities", [])}
        android_capabilities = ["chat", "memory_read", "actions_request", "device_self"]
        if "voice" in requested:
            android_capabilities.append("voice")
        memory.register_device(device_id, android_capabilities, permission_level=0, name=device_id, device_type="android")
        created = memory.create_device_token(device_id, ttl_days=DEVICE_TOKEN_TTL_DAYS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("No se pudo completar el onboarding de pairing para el dispositivo solicitado")
        raise HTTPException(status_code=500, detail="No se pudo completar el onboarding de forma segura.") from exc
    paired["device_id"] = device_id
    paired["display_name"] = device_id
    paired["token_id"] = created["token_id"]
    paired["token"] = created["token"]
    paired["protocol_version"] = paired.get("protocol_version", "1.0")
    paired["capabilities"] = android_capabilities
    paired["server"] = {"version": VERSION, "lan_enabled": True, "host": __import__("config").HOST, "port": __import__("config").PORT}
    paired["onboarding"] = {"status": "complete", "token_return": "one_time"}
    paired["negotiation"] = negotiate_features(KNOWN_FEATURES, payload.features, allow_remote_actions=False)
    return paired


@router.post("/devices/negotiate")
async def devices_negotiate(payload: FeatureNegotiationPayload, principal: Annotated[Principal, Depends(authenticate)]):
    allow_remote = bool(principal.is_master and LAN_ENABLED and payload.request_remote_actions)
    return negotiate_features(KNOWN_FEATURES, payload.features, allow_remote_actions=allow_remote)


@router.get("/apps/discovered")
async def apps_discovered(force_refresh: bool = False, principal: Annotated[Principal, Depends(require_master)] = None):
    discover_installed_apps, _get_app_trust, _resolve_discovered_app, _revoke_app_trust, _set_app_trust = _safe_apps_module()
    return {"apps": discover_installed_apps(force_refresh=force_refresh), "read_only": True}


@router.post("/apps/trust")
async def apps_trust(payload: AppTrustPayload, principal: Annotated[Principal, Depends(require_master)]):
    discover_installed_apps, _get_app_trust, resolve_discovered_app, _revoke_app_trust, set_app_trust = _safe_apps_module()
    decision = str(payload.decision).strip().upper()
    if decision not in {"ALLOW_ONCE", "ALWAYS_ALLOW", "DENY", "BLOCK"}:
        raise HTTPException(status_code=422, detail="Decisión de trust inválida.")
    item = next((row for row in discover_installed_apps(force_refresh=False) if str(row.get("app_id")) == payload.app_id), None)
    if not item or not payload.app_id.startswith("discovered:"):
        raise HTTPException(status_code=404, detail="La aplicación descubierta no existe o no es canónica.")
    if decision in {"DENY", "BLOCK"}:
        saved = set_app_trust(payload.app_id, trusted=False, blocked=True, trust_mode="ALWAYS", launch_definition=item.get("launch_definition"), display_name=str(item.get("display_name", "")), source=str(item.get("source", "")), process_names=tuple(item.get("process_names") or []))
    else:
        mode = "ONCE" if decision == "ALLOW_ONCE" else "ALWAYS"
        saved = set_app_trust(payload.app_id, trusted=True, blocked=False, trust_mode=mode, uses_remaining=1 if mode == "ONCE" else 0, launch_definition=item.get("launch_definition"), display_name=str(item.get("display_name", "")), source=str(item.get("source", "")), process_names=tuple(item.get("process_names") or []))
    return {"status": "trusted" if decision in {"ALLOW_ONCE", "ALWAYS_ALLOW"} else "blocked", "decision": decision, "app": saved}


@router.delete("/apps/trust")
async def apps_trust_revoke(payload: AppTrustPayload, principal: Annotated[Principal, Depends(require_master)]):
    _discover, _get_trust, _resolve, revoke, _set = _safe_apps_module()
    if not str(payload.app_id).startswith("discovered:"):
        raise HTTPException(status_code=404, detail="La aplicación no tiene app_id descubierto canónico.")
    if not revoke(payload.app_id):
        raise HTTPException(status_code=404, detail="Trust de aplicación no encontrado.")
    return {"status": "revoked", "app_id": payload.app_id}


@router.get("/trusted-folders")
async def trusted_folders_list(principal: Annotated[Principal, Depends(require_master)]):
    _grant, list_trusted, _revoke, _update = _trusted_folders_module()
    return {"folders": list_trusted(), "read_only": True, "rights": ["READ", "OPEN", "CREATE", "WRITE", "COPY_FROM", "COPY_TO", "MOVE_FROM", "MOVE_TO", "RENAME", "DELETE"]}


@router.post("/trusted-folders")
async def trusted_folders_grant(payload: TrustedFolderPayload, principal: Annotated[Principal, Depends(require_master)]):
    grant, _list_trusted, _revoke, _update = _trusted_folders_module()
    try:
        return {"status": "trusted", "folder": grant(payload.path, label=payload.label, rights=payload.rights, write_allowed=payload.write_allowed)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/trusted-folders")
async def trusted_folders_update(payload: TrustedFolderUpdatePayload, principal: Annotated[Principal, Depends(require_master)]):
    _grant, _list_trusted, _revoke, update = _trusted_folders_module()
    try:
        return {"status": "updated", "folder": update(payload.folder_id, label=payload.label, rights=payload.rights, trusted=payload.trusted)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/trusted-folders")
async def trusted_folders_revoke(payload: TrustedFolderRevokePayload, principal: Annotated[Principal, Depends(require_master)]):
    _grant, _list_trusted, revoke, _update = _trusted_folders_module()
    if not revoke(payload.folder_id):
        raise HTTPException(status_code=404, detail="Trusted folder no encontrado.")
    return {"status": "revoked", "folder_id": payload.folder_id}


@router.get("/permissions")
async def permissions_list(principal: Annotated[Principal, Depends(authenticate)]):
    if principal.is_master:
        return {"permissions": memory.list_permissions()}
    return {"permissions": memory.list_permissions(principal_type=principal.type, principal_id=str(principal.token_id or ""), device_id=str(principal.device_id or ""))}


@router.post("/permissions")
async def permissions_grant(payload: PermissionGrantPayload, principal: Annotated[Principal, Depends(require_master)]):
    decision = str(payload.decision).strip().upper()
    if decision in {"ALLOW_ONCE", "ALWAYS_ALLOW"} and payload.risk_level > PERMISSION_PERSISTENT_MAX_RISK:
        raise HTTPException(status_code=409, detail="Las capabilities de riesgo alto no admiten grant persistente.")
    if decision in {"ALWAYS_ALLOW", "ALWAYS_DENY"} and (not payload.resource_scope.strip() or payload.resource_scope.strip() == "*" or "unresolved" in payload.resource_scope.casefold()):
        raise HTTPException(status_code=422, detail="Los grants persistentes requieren un resource_scope explícito y resuelto.")
    try:
        grant_id = memory.save_permission_grant(principal_type="master", principal_id="", device_id=payload.device_id, capability=payload.capability, resource_scope=payload.resource_scope, decision=decision, risk_level=payload.risk_level, capability_version=payload.capability_version, expires_at=payload.expires_at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "granted", "permission_id": grant_id, "decision": decision}


@router.delete("/permissions")
async def permissions_revoke(capability: str, resource_scope: str = "", device_id: str = "pc-main", principal: Annotated[Principal, Depends(require_master)] = None):
    count = memory.revoke_permission(principal_type="master", principal_id="", device_id=device_id, capability=capability, resource_scope=resource_scope)
    return {"status": "revoked", "removed": count}


@router.get("/actions/control")
async def actions_control(principal: Annotated[Principal, Depends(require_chat)]):
    return _actions_control_payload(pending_cancelled=0)


@router.post("/actions/kill-switch")
async def actions_kill_switch(principal: Annotated[Principal, Depends(require_master)]):
    cancelled = memory.delete_states_prefix("pending_action:")
    memory.set_state("gaia_actions_enabled", "0")
    memory.set_state("gaia_actions_kill_switch_at", datetime.now().isoformat())
    return _actions_control_payload(pending_cancelled=cancelled)


@router.post("/actions/enable")
async def actions_enable(principal: Annotated[Principal, Depends(require_master)]):
    _safe_mode_mutation_blocked()
    memory.set_state("gaia_actions_enabled", "1")
    memory.set_state("gaia_actions_enabled_at", datetime.now().isoformat())
    return _actions_control_payload(pending_cancelled=0)


_TARGET_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def _resolve_target_host(requested: str, principal: Principal) -> str:
    candidate = str(requested or "").strip()
    if not candidate or candidate == PC_DEVICE_ID:
        return PC_DEVICE_ID
    if not principal.is_master or not _TARGET_HOST_RE.fullmatch(candidate):
        return PC_DEVICE_ID
    for item in memory.get_devices():
        capabilities = set(item.get("capabilities") or [])
        if str(item.get("device_id")) == candidate and not bool(item.get("revoked")) and "action_host" in capabilities:
            return candidate
    return PC_DEVICE_ID


def _pending_action_state(intent: ActionIntent | ActionPlan, *, session_id: str, principal: Principal, requesting_device: str, target_host: str, request_id: str = "") -> dict:
    auto_approved = not bool(intent.confirmation_required)
    return {
        "session_id": session_id,
        "device": requesting_device,
        "requesting_device": requesting_device,
        "target_host": target_host,
        "execution_host": target_host,
        "principal_type": principal.type,
        "device_id": principal.device_id,
        "token_id": principal.token_id,
        "request_state": "PLAN_REQUEST" if isinstance(intent, ActionPlan) else "ACTION_PENDING_CONFIRMATION",
        "intent": intent.as_dict(),
        "request_id": request_id,
        "approved": auto_approved,
        "auto_approved": auto_approved,
        "approval_source": "permission_policy" if auto_approved else "pending_confirmation",
        "approval_decision": "AUTO" if auto_approved else "",
        "created_at": datetime.now().isoformat(),
    }


def _normalized_user_request(message: str) -> str:
    text = re.sub(r"\s+", " ", str(message or "").strip())
    text = re.sub(r"^(?:[¿?\s]*(?:gaia|g\.a\.i\.a)\s*[,;:]?\s*)", "", text, flags=re.IGNORECASE)
    return text.strip(" \t\r\n¿?!.,;:")


def _is_capability_question(message: str) -> bool:
    text = _normalized_user_request(message)
    if not text:
        return False
    lower = text.casefold()
    interrogative = "?" in str(message) or lower.startswith(("qué ", "que ", "cómo ", "como ", "por qué ", "por que "))
    return bool(interrogative and _CAPABILITY_QUESTION_RE.search(text))


def _is_action_request(message: str) -> bool:
    """Recognize an expected external effect from linguistic framing, not app names."""
    text = _normalized_user_request(message)
    if not text or _is_capability_question(message):
        return False
    if _ACTION_REQUEST_RE.search(text):
        return True
    if _PLAN_REQUEST_RE.search(text) and not _DANGEROUS_PLAN_RE.search(text):
        return True
    if not _EXTERNAL_EFFECT_VERB_RE.search(text):
        return bool(re.search(r"\b(?:quiero|necesito)\b.+\b(?:abiert[oa]|cerrad[oa]|iniciad[oa]|ejecutad[oa]|instalad[oa])\b", text, re.IGNORECASE))
    return bool(_REQUEST_FRAME_RE.search(text) or text.casefold().startswith(("me ", "quiero ", "necesito ")) or str(message).strip().endswith("?"))


def _has_effect_claim(text: str) -> bool:
    for sentence in re.split(r"[.!?\n]+", str(text or "")):
        candidate = sentence.strip()
        if not candidate or _NON_CLAIM_PREFIX_RE.match(candidate):
            continue
        if _EFFECT_CLAIM_RE.search(candidate):
            return True
    return False


def _has_unverified_execution_report(text: str) -> bool:
    """Detect a first-person execution report without enumerating capabilities."""
    return bool(_UNVERIFIED_EXECUTION_REPORT_RE.match(str(text or "").strip()))


def _ground_conversation_response(text: str, *, user_message: str = "", profile: str = "", request_state: str = "CONVERSATION") -> str:
    """Ground conversational text; ACTION_REQUEST cannot claim an unverified system effect."""
    visible = str(text or "").strip()
    visible = re.sub(r"<think(?:ing)?\b[^>]*>.*?</think(?:ing)?\s*>", "", visible, flags=re.IGNORECASE | re.DOTALL).strip()
    if not visible:
        logger.warning("event=llm_empty_visible_output backend=%s model=%s profile=%s reasoning_filtered=true", llm.LLM_BACKEND, llm.LLM_MODEL, profile or "auto")
        return _EMPTY_RESPONSE_FALLBACK
    if request_state in {"CONVERSATION", "ACTION_REQUEST"} and (_has_effect_claim(visible) or (request_state == "CONVERSATION" and _has_unverified_execution_report(visible))):
        logger.warning("event=unverified_system_claim_blocked backend=%s model=%s profile=%s request_state=%s user_chars=%s", llm.LLM_BACKEND, llm.LLM_MODEL, profile or "auto", request_state, len(user_message))
        return _UNAVAILABLE_ACTION_FALLBACK
    return visible


def _deterministic_simple_response(pending_intent: dict, success: bool, message: str, data: dict) -> str | None:
    """Return factual templates for simple actions; None keeps selective LLM narration."""
    if pending_intent.get("type", "action") != "action":
        return None
    name = str(pending_intent.get("name", ""))
    if name == "list_projects":
        rows = data.get("projects") if isinstance(data, dict) else []
        names: list[str] = []
        seen: set[str] = set()
        for item in rows if isinstance(rows, list) else []:
            if not isinstance(item, dict):
                continue
            project_name = str(item.get("name", "")).strip()
            key = project_name.casefold()
            if project_name and key not in seen:
                seen.add(key)
                names.append(project_name)
        return f"Proyectos registrados: {', '.join(names) or 'ninguno'}."
    if name in {"open_calculator", "open_notepad", "open_spotify", "open_vscode_new_window", "open_vscode"}:
        return str(message or ("La acción se completó." if success else "La aplicación no está disponible.")).strip()
    if name in {"system_status", "system_ram", "system_cpu", "system_gpu", "system_disk"}:
        return str(message or "No pude obtener el estado solicitado.").strip()
    return None


@dataclass(frozen=True)
class VerifiedActionResult:
    """Immutable facts from the local Action Engine; narration cannot change them."""

    action: dict
    success: bool
    message: str
    data: dict
    execution_verified: bool = True
    status: str = ""
    request_validated: bool = True
    execution_attempted: bool = True
    capability_available: bool | None = None
    side_effect_performed: bool = False
    effect_verified: bool = False
    observation_completed: bool = False

    def __post_init__(self) -> None:
        data = dict(self.data or {})
        status = str(self.status or "").upper()
        available = self.capability_available
        if available is None and "capability_available" in data:
            available = bool(data.get("capability_available"))
        if not status:
            status = "UNAVAILABLE" if available is False else ("SUCCESS" if self.success else "FAILED")
        if status == "UNAVAILABLE":
            object.__setattr__(self, "success", False)
            object.__setattr__(self, "execution_verified", False)
            object.__setattr__(self, "capability_available", False)
            object.__setattr__(self, "effect_verified", False)
            object.__setattr__(self, "side_effect_performed", False)
        else:
            object.__setattr__(self, "capability_available", True if available is None else bool(available))
            if status != "SUCCESS":
                object.__setattr__(self, "execution_verified", False)
                object.__setattr__(self, "effect_verified", False)
                object.__setattr__(self, "side_effect_performed", False)
        object.__setattr__(self, "status", status)

    def as_payload(self) -> dict:
        return {
            "action": dict(self.action),
            "success": bool(self.success),
            "message": self.message,
            "data": dict(self.data),
            "status": self.status,
            "request_validated": bool(self.request_validated),
            "execution_attempted": bool(self.execution_attempted),
            "capability_available": self.capability_available,
            "side_effect_performed": bool(self.side_effect_performed),
            "effect_verified": bool(self.effect_verified),
            "observation_completed": bool(self.observation_completed),
            "execution_verified": bool(self.execution_verified),
        }


_POST_ACTION_INJECTION_RE = re.compile(
    r'(?:"?action"?\s*[:=]|```|\b(?:shutdown|delete[_ -]?file|powershell|cmd|sudo|format)\b)',
    re.IGNORECASE,
)
_POST_ACTION_EFFECT_RE = re.compile(
    r"\b(?:abiert[oa]s?|cerrad[oa]s?|iniciad[oa]s?|ejecutad[oa]s?|eliminad[oa]s?|movid[oa]s?|copiad[oa]s?|guardad[oa]s?|descargad[oa]s?|enviad[oa]s?|modificad[oa]s?|instalad[oa]s?|desinstalad[oa]s?|reiniciad[oa]s?|apagad[oa]s?|opened|closed|started|executed|deleted|moved|copied|saved|downloaded|sent|modified|installed|uninstalled|restarted|shutdown)\b",
    re.IGNORECASE,
)
_SAFE_POST_ACTION_SUFFIXES = frozenset({
    "listo",
    "buena suerte con las matemáticas",
    "qué época para estar vivos",
    "tu procesador agradece la colaboración",
    "al menos esta vez, sin drama",
})


def _fact_locked_base(verified: VerifiedActionResult) -> str:
    status = str(verified.status or "FAILED").upper()
    message = str(verified.message or "").strip()
    if status == "UNAVAILABLE":
        return message or "La capability solicitada no está disponible en este host; no se ejecutó nada."
    if status == "DENIED":
        return message or "La acción fue denegada por la política de permisos; no se ejecutó nada."
    if status == "CANCELLED":
        return message or "La acción fue cancelada antes de producir un efecto."
    if status == "PARTIAL":
        return message or "El plan se detuvo parcialmente; no todos sus pasos se completaron."
    if status != "SUCCESS":
        return message if message.lower().startswith(("no", "fall", "cancel", "la acción")) else (f"La acción no se completó: {message}" if message else "La acción no se completó; el sistema devolvió un resultado fallido.")
    if not verified.execution_verified:
        return "La acción terminó, pero el resultado no pudo verificarse; no afirmaré que el efecto ocurrió."
    action = verified.action if isinstance(verified.action, dict) else {}
    deterministic = _deterministic_simple_response(action, verified.success, verified.message, verified.data)
    if deterministic:
        return deterministic.strip()
    return message or ("La observación se completó." if verified.observation_completed else "La acción se completó correctamente.")


def _post_action_scope_valid(verified: VerifiedActionResult, natural: str, base: str) -> bool:
    if verified.status != "SUCCESS" or not verified.execution_verified or not natural or natural == base:
        return False
    base_position = natural.casefold().find(base.casefold())
    if base_position < 0:
        return False
    prefix = natural[:base_position].strip(" \\t\\r\\n.,;:-")
    suffix = natural[base_position + len(base):].strip(" \\t\\r\\n.,;:-")
    extra = " ".join(part for part in (prefix, suffix) if part).strip()
    if not extra or extra.casefold() not in _SAFE_POST_ACTION_SUFFIXES:
        return False
    if _POST_ACTION_INJECTION_RE.search(extra) or _POST_ACTION_EFFECT_RE.search(extra) or _has_effect_claim(extra):
        return False
    # Do not let a personality suffix/prefix smuggle new structured measurements or paths.
    if re.search(r"(?:\d|%|=|[A-Za-z]:[\\/]|/|\b(?:cpu|ram|gpu|disk|path|status|count|process|error)\b)", extra, re.IGNORECASE):
        return False
    return True


def _ground_post_action_response(verified: VerifiedActionResult | bool, natural_response: str, legacy_natural_response: str | None = None) -> str:
    """Return immutable verified facts and allow only a safe, non-effect personality suffix."""
    if not isinstance(verified, VerifiedActionResult):
        # Legacy internal callers pass (success, deterministic_message, natural_message).
        # Production completion always passes VerifiedActionResult and uses strict scope validation.
        legacy_success = bool(verified)
        deterministic = str(natural_response or "").strip()
        natural = str(legacy_natural_response or "").strip()
        if not legacy_success:
            return deterministic if deterministic.lower().startswith(("no", "fall", "cancel", "la acción")) else f"La acción no se completó: {deterministic}"
        return natural or deterministic or "La acción se completó correctamente."
    base = _fact_locked_base(verified)
    natural = str(natural_response or "").strip()
    if _post_action_scope_valid(verified, natural, base):
        return natural
    return base


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str = Field(default="", max_length=64, pattern=r"^[\w-]*$")
    device: str = Field(default="pc", min_length=1, max_length=40)
    target_host: str = Field(default="", max_length=80)
    profile: str = Field(default="", max_length=20)
    context: int | None = Field(default=None, ge=512, le=32768)
    intent: dict | None = None
    pc_context: dict | None = None
    desktop_snapshot: dict | None = None
    request_envelope: dict | None = None
    channel: str = Field(default="desktop_text", max_length=32)


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: str
    kind: str = "chat"
    request_state: str = "CONVERSATION"
    action_id: str | None = None
    request_id: str | None = None
    confirmation_required: bool = False
    preview: str | list[str] | None = None
    action: dict | None = None
    plan: dict | None = None
    confirmation_options: dict = Field(default_factory=dict)
    permission_entries: list[dict] = Field(default_factory=list)
    resource_scope_version: str = ""
    requesting_device: str | None = None
    target_host: str | None = None
    approved: bool = False
    active_context: dict | None = None


class CancelRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[\w-]+$")


class ActionCompleteRequest(BaseModel):
    action_id: str = Field(min_length=8, max_length=80, pattern=r"^[\w-]+$")
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[\w-]+$")
    device: str = Field(default="pc", min_length=1, max_length=40)
    success: bool
    message: str = Field(min_length=1, max_length=12000)
    data: dict = Field(default_factory=dict)
    status: str = Field(default="", max_length=20, pattern=r"^(?:SUCCESS|FAILED|UNAVAILABLE|DENIED|CANCELLED|PARTIAL)?$")
    request_validated: bool | None = None
    execution_attempted: bool | None = None
    capability_available: bool | None = None
    side_effect_performed: bool | None = None
    effect_verified: bool | None = None
    observation_completed: bool | None = None
    execution_verified: bool | None = None


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


class AdvancedMemoryPayload(BaseModel):
    memory_key: str = Field(min_length=1, max_length=160, pattern=r"^[\w.:-]+$")
    kind: str = Field(min_length=1, max_length=32)
    category: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=4000)
    source_type: str = Field(default="USER_EXPLICIT", max_length=32)
    source_ref: str = Field(default="", max_length=160)
    provenance_type: str = Field(default="", max_length=40)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.7, ge=0.0, le=1.0)
    scope: str = Field(default="personal", min_length=1, max_length=80, pattern=r"^[\w.:-]+$")
    project: str = Field(default="", max_length=120)
    session_id: str = Field(default="", max_length=80)
    device_id: str = Field(default="", max_length=80)
    user_confirmed: bool = True
    pinned: bool = False
    expires_at: str | None = Field(default=None, max_length=80)


class AdvancedMemoryUpdatePayload(BaseModel):
    memory_key: str | None = Field(default=None, max_length=160, pattern=r"^[\w.:-]+$")
    kind: str | None = Field(default=None, max_length=32)
    category: str | None = Field(default=None, max_length=80)
    content: str | None = Field(default=None, max_length=4000)
    source_type: str | None = Field(default=None, max_length=32)
    source_ref: str | None = Field(default=None, max_length=160)
    provenance_type: str | None = Field(default=None, max_length=40)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    scope: str | None = Field(default=None, max_length=80, pattern=r"^[\w.:-]+$")
    project: str | None = Field(default=None, max_length=120)
    session_id: str | None = Field(default=None, max_length=80)
    device_id: str | None = Field(default=None, max_length=80)
    user_confirmed: bool | None = None
    pinned: bool | None = None
    expires_at: str | None = Field(default=None, max_length=80)


class AdvancedMemoryFlagsPayload(BaseModel):
    pinned: bool | None = None
    user_confirmed: bool | None = None


class MemoryConsolidatePayload(BaseModel):
    session_id: str = Field(min_length=1, max_length=80, pattern=r"^[\w-]+$")
    max_messages: int = Field(default=32, ge=4, le=64)


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


def _request_context(request: ChatRequest) -> dict:
    """Select client context without treating it as execution authority."""
    context = dict(request.pc_context) if isinstance(request.pc_context, dict) else {}
    envelope = request.request_envelope if isinstance(request.request_envelope, dict) else {}
    snapshot = request.desktop_snapshot if isinstance(request.desktop_snapshot, dict) else envelope.get("desktop_snapshot")
    if isinstance(snapshot, dict):
        context["desktop_snapshot"] = dict(snapshot)
    return context


def _form_dict(value: str | None, *, limit: int = 24000) -> dict:
    """Parse a bounded multipart JSON field as data; malformed input is ignored."""
    raw = str(value or "")[:limit].strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _compact_pc_context(raw: dict | None) -> dict:
    """Whitelist read-only PC telemetry before it reaches the model prompt."""
    if not isinstance(raw, dict):
        return {}
    snapshot = raw.get("desktop_snapshot") if isinstance(raw.get("desktop_snapshot"), dict) else {}
    source = snapshot if snapshot else raw
    window = source.get("active_window") if isinstance(source.get("active_window"), dict) else {}
    if window and not window.get("app"):
        window = {**window, "app": window.get("process") or window.get("process_executable") or ""}
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


def _context_is_relevant(user_message: str) -> bool:
    return bool(_CONTEXT_REFERENCE_RE.search(str(user_message or "")))


def _relevant_active_context(user_message: str, pc_context: dict | None) -> dict | None:
    if not _context_is_relevant(user_message):
        return None
    compact = _compact_pc_context(pc_context)
    active = compact.get("active_window") if isinstance(compact, dict) else None
    if not active:
        return None
    snapshot = pc_context.get("desktop_snapshot") if isinstance(pc_context, dict) and isinstance(pc_context.get("desktop_snapshot"), dict) else {}
    return {"active_window": active, "snapshot_id": str(snapshot.get("snapshot_id") or "")[:100], "host_id": str(snapshot.get("host_id") or "")[:80], "expires_at": snapshot.get("expires_at"), "context_level": str(snapshot.get("context_level") or "FOREGROUND")[:32], "ephemeral": True, "source": "desktop.context", "read_only": True}


def _memory_access_context(principal: Principal, session_id: str = "", device_id: str | None = None, request_id: str = "", source_channel: str = "api") -> memory.MemoryAccessContext:
    effective = str(device_id if device_id is not None else (principal.device_id or "pc"))[:80]
    principal_id = "master" if principal.is_master else effective
    return memory.MemoryAccessContext(principal_id=principal_id, device_id=effective, session_id=str(session_id or "")[:80], capabilities=principal.capabilities, request_id=request_id, source_channel=source_channel, is_master=principal.is_master)


def _prepare_context(session_id: str, user_message: str, device: str, pc_context: dict | None = None, principal: Principal | None = None, request_id: str = "") -> tuple[str, list[dict]]:
    access_context = _memory_access_context(principal, session_id, device, request_id=request_id) if principal else None
    memory.save_message(session_id, "user", user_message, device, principal_id=access_context.principal_id if access_context else "", is_master=bool(access_context and access_context.is_master))
    memory.set_state("last_message_time", datetime.now().isoformat())
    memory.set_state("last_device", device)
    from fact_extractor import process_message
    extraction = process_message(user_message, session_id=session_id)
    context_limits = {"eco": (8, 6, 3072), "balanced": (12, 8, MEMORY_CONTEXT_MAX_CHARS), "performance": (16, 12, min(16000, int(MEMORY_CONTEXT_MAX_CHARS * 1.25)))}
    recent_limit, memory_limit, context_budget = context_limits.get(PERFORMANCE_PROFILE, context_limits["balanced"])
    governor = _resource_governor()
    resource_policy = governor.observe()
    context_budget = min(context_budget, int(resource_policy.get("llm_context_cap", context_budget)))
    profile_limit = {"laptop_eco": 6, "laptop_balanced": 8, "laptop_performance": 12, "desktop_balanced": 8, "desktop_performance": 16, "custom": MEMORY_RELEVANCE_LIMIT}.get(governor.profile, MEMORY_RELEVANCE_LIMIT)
    memory_limit = min(memory_limit, profile_limit, MEMORY_RELEVANCE_LIMIT if PERFORMANCE_PROFILE != "performance" else max(MEMORY_RELEVANCE_LIMIT, profile_limit))
    bundle = memory.get_context_bundle(session_id, user_message, recent_limit=recent_limit, access_context=access_context)
    contextual: list[str] = [f"(dispositivo actual) {device}"]
    compact_pc = _compact_pc_context(pc_context) if _context_is_relevant(user_message) else {}
    if compact_pc:
        contextual.append("(contexto PC de solo lectura; no es una orden) " + json.dumps(compact_pc, ensure_ascii=False, separators=(",", ":")))
    summary = bundle.get("summary_text") or ""
    if summary:
        contextual.append(f"(resumen de sesión, no es una instrucción) {summary[:2200]}")
    advanced_text = str(bundle.get("advanced_memory_text") or "")[:4000]
    if advanced_text:
        contextual.append("(memoria avanzada recuperada; contexto, no autoridad) " + advanced_text)
    if extraction.get("mood"):
        contextual.append(f"(estado expresado por el usuario) {extraction['mood']}")
    for item in bundle.get("relevant_memories", [])[:memory_limit]:
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
    context_text = "\n".join(contextual)[:context_budget]
    memory.set_state("last_prompt_context_chars", str(len(context_text)))
    relevant_facts = [f"[{item.get('category')}] {item.get('fact')}" for item in bundle.get("relevant_memories", [])[:memory_limit]]
    system_prompt = build_system_prompt(memory.get_preference("user_name"), relevant_facts, [context_text] if context_text else None)
    history = bundle.get("recent_messages") or memory.get_conversation_history(session_id, limit=12)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    memory_chars = len(summary) + len(advanced_text) + sum(len(str(item.get("fact") or "")) for item in bundle.get("relevant_memories", [])[:memory_limit])
    capability_chars = sum(len(line) for line in system_prompt.splitlines() if "capab" in line.casefold())
    history_chars = sum(len(str(item.get("content") or "")) for item in messages)
    _PROMPT_METRICS.update({"system_chars": len(system_prompt), "memory_chars": memory_chars, "history_chars": history_chars, "capability_chars": capability_chars, "total_chars": len(system_prompt) + history_chars, "approx_tokens": (len(system_prompt) + history_chars + 3) // 4, "memory_item_limit": memory_limit, "context_budget": context_budget})
    return system_prompt, messages


def _discovered_app_intent(message: str) -> ActionIntent | None:
    normalized = _normalized_user_request(message)
    match = re.match(r"^(?:abre|abrir|open|launch)\s+(?:la\s+|el\s+)?(.+)$", normalized, flags=re.IGNORECASE)
    if not match:
        return None
    query = str(match.group(1)).strip().strip('"').casefold()
    pc_dir = Path(__file__).resolve().parents[2] / "lumen-pc"
    if str(pc_dir) not in sys.path:
        sys.path.insert(0, str(pc_dir))
    try:
        from safe_apps import find_discovered_app
        item = find_discovered_app(query)
    except (ImportError, OSError, ValueError):
        return None
    app_id = str((item or {}).get("app_id") or "")
    if not app_id.startswith("discovered:"):
        return None
    return ActionIntent("open_discovered_app", {"app_id": app_id}, 2, False, 0.98, "deterministic")


def _allowed_intent(message: str, structured: dict | None = None, pc_context: dict | None = None) -> ActionIntent | ActionPlan | None:
    """Fast deterministic/explicit route; never calls an executor."""
    if not ACTION_ENGINE_ENABLED:
        return None
    if structured and isinstance(structured, dict) and structured.get("type") == "plan":
        intent = parse_action_plan(structured, max_actions=ACTION_PLAN_MAX, max_risk=ACTION_MAX_LEVEL)
    else:
        intent = parse_structured_intent(structured) if structured else None
    intent = intent or resolve_window_referent(message, pc_context) or detect_contextual_action(message, pc_context) or detect_workspace_profile(message, pc_context) or detect_action(message) or _discovered_app_intent(message)
    if intent and intent.risk_level <= ACTION_MAX_LEVEL:
        return intent
    return None


def _intent_permission_key(intent: ActionIntent | ActionPlan) -> tuple[str, str]:
    if isinstance(intent, ActionPlan):
        return "plan", "plan"
    name = intent.name
    key = {
        "open_calculator": "apps.open", "open_notepad": "apps.open", "open_spotify": "apps.open", "open_vscode": "apps.open", "open_vscode_new_window": "apps.open", "open_discovered_app": "apps.open_discovered",
        "list_safe_apps": "apps.list", "is_safe_app_running": "apps.is_running", "open_browser": "browser.open", "open_url": "url.open", "open_folder": "folders.open", "open_project": "projects.open",
        "system_status": "system.status", "system_ram": "system.status", "system_cpu": "system.status", "system_gpu": "system.status", "system_disk": "system.status", "system_processes": "processes.list", "system_network": "network.status",
        "git_status": "git.status", "list_projects": "projects.list", "show_project": "projects.info", "run_tests": "projects.tests", "start_project": "projects.start", "run_project_command": "projects.command", "open_terminal": "projects.terminal",
        "close_app": "apps.close", "focus_app": "apps.focus", "minimize_app": "apps.minimize", "set_volume": "audio.set_volume", "get_volume": "audio.get_volume", "mute": "audio.mute", "unmute": "audio.unmute",
        "windows_list": "windows.list", "windows_focus": "windows.focus", "windows_minimize": "windows.minimize", "windows_maximize": "windows.maximize", "windows_restore": "windows.restore", "windows_close": "windows.close", "windows_move_to_display": "windows.move_to_display", "desktop_context": "desktop.context", "uia_inspect_window": "uia.inspect_window", "uia_list_controls": "uia.list_controls", "uia_get_focused_control": "uia.get_focused_control", "uia_focus_control": "uia.focus_control", "uia_invoke_control": "uia.invoke_control", "uia_set_value": "uia.set_value", "vscode_focus": "vscode.focus", "vscode_open_project": "vscode.open_project", "vscode_new_window": "vscode.new_window", "vscode_open_file_trusted": "vscode.open_file_trusted", "vscode_open_terminal_trusted": "vscode.open_terminal_trusted", "media_status": "media.status", "media_play_pause": "media.play_pause", "media_next": "media.next", "media_previous": "media.previous", "media_stop": "media.stop", "screen_capture_display": "screen.capture_display", "screen_capture_window": "screen.capture_window", "list_audio_devices": "audio.list_devices",
        "file_exists": "files.exists", "file_list": "files.list", "file_info": "files.info", "file_open": "files.open", "file_delete": "files.delete", "file_copy": "files.copy", "file_move": "files.move", "file_rename": "files.rename", "folder_create": "folders.create",
        "clipboard_read": "clipboard.read", "clipboard_write": "clipboard.write", "display_list": "display.list", "display_info": "display.info", "network_adapters": "network.adapters", "network_ip": "network.ip", "process_info": "processes.info", "process_stop": "processes.stop",
        "git_branch": "git.branch", "git_log": "git.log", "git_diff": "git.diff", "git_add": "git.add", "git_commit": "git.commit", "system_lock": "system.lock", "system_sleep": "system.sleep", "system_restart": "system.restart", "system_shutdown": "system.shutdown",
    }.get(name, f"legacy.{name}")
    parameters = dict(intent.args)
    scope = resolve_resource_scope(key, parameters, {"legacy_action": name})
    return key, str(scope.get("resource_scope") or "")[:500]


def _intent_scope_metadata(intent: ActionIntent | ActionPlan) -> dict:
    if isinstance(intent, ActionPlan):
        return {"resource_scope": "plan:bounded", "human_scope_description": "plan estructurado acotado", "persistent_grant_allowed": False, "resource_scope_version": RESOURCE_SCOPE_VERSION, "resource_kind": "plan"}
    capability, _ = _intent_permission_key(intent)
    return resolve_resource_scope(capability, dict(intent.args), {"legacy_action": intent.name})


def _permission_for_intent(intent: ActionIntent | ActionPlan | None, principal: Principal | None, device_id: str = "") -> dict | None:
    if not intent or principal is None:
        return None
    capability, scope = _intent_permission_key(intent)
    permission = memory.resolve_permission(
        principal_type=principal.type,
        principal_id=str(principal.token_id or ""),
        device_id=device_id,
        capability=capability,
        resource_scope=scope,
        current_risk_level=intent.risk_level,
        capability_version="1",
        include_default=True,
    ) or {}
    if capability == "apps.open_discovered" and scope:
        try:
            _discover, get_app_trust, _resolve, _revoke, _set = _safe_apps_module()
            trust = get_app_trust(scope)
            if trust.get("trusted") and not trust.get("blocked"):
                permission = {**permission, "effective_decision": "ALWAYS_ALLOW", "source": "trusted_app", "risk_escalated": False, "version_changed": False}
        except (ImportError, OSError, ValueError):
            pass
    return permission or None


def _permission_entries(intent: ActionIntent | ActionPlan, principal: Principal, device_id: str) -> list[dict]:
    intents = intent.actions if isinstance(intent, ActionPlan) else [intent]
    entries: list[dict] = []
    for item in intents:
        capability, scope = _intent_permission_key(item)
        metadata = _intent_scope_metadata(item)
        permission = _permission_for_intent(item, principal, device_id) or {}
        entries.append({
            "capability": capability,
            "resource_scope": scope,
            "scope": scope,
            "human_scope_description": metadata.get("human_scope_description", "scope estructurado"),
            "resource_scope_version": metadata.get("resource_scope_version", RESOURCE_SCOPE_VERSION),
            "resource_kind": metadata.get("resource_kind", "unknown"),
            "persistent_grant_allowed": bool(metadata.get("persistent_grant_allowed")),
            "risk_level": item.risk_level,
            "decision": permission.get("effective_decision", "ALWAYS_ASK"),
            "source": permission.get("source", "grant"),
            "allow_always": bool(metadata.get("persistent_grant_allowed")) and item.risk_level <= 2,
        })
    return entries


def _action_policy_notice(intent: ActionIntent | ActionPlan | None, principal: Principal | None = None, device_id: str = "") -> str | None:
    if not intent:
        return None
    permission = _permission_for_intent(intent, principal, device_id)
    if permission and permission["effective_decision"] in {"DENY", "ALWAYS_DENY"}:
        return "La política de permisos deniega esta capability para el scope solicitado; no se ejecutó nada."
    if ACTION_CONFIRM_POLICY == "BLOCKED":
        return "Acciones deshabilitadas por configuración; no se ejecutó nada."
    if ACTION_CONFIRM_POLICY == "AUTO_SAFE" and intent.risk_level > 1:
        return None
    return None


def _action_capability_failure(session_id: str, user_message: str, device_id: str) -> ChatResponse:
    """Close an explicit unsupported action request without invoking free chat narration."""
    memory.save_message(session_id, "user", user_message, device_id)
    memory.save_message(session_id, "assistant", _UNAVAILABLE_ACTION_FALLBACK, device_id)
    return ChatResponse(response=_UNAVAILABLE_ACTION_FALLBACK, session_id=session_id, timestamp=datetime.now().isoformat(), request_state="ACTION_REQUEST")


def _apply_action_policy(intent: ActionIntent | ActionPlan | None, principal: Principal | None = None, device_id: str = "") -> ActionIntent | ActionPlan | None:
    if not intent or ACTION_CONFIRM_POLICY == "BLOCKED":
        return None
    permission = _permission_for_intent(intent, principal, device_id)
    effective = permission.get("effective_decision") if permission else None
    if effective in {"AUTO", "ALWAYS_ALLOW", "ALLOW_ONCE"} and not (permission and (permission.get("risk_escalated") or permission.get("version_changed"))):
        return replace(intent, confirmation_required=False)
    if effective in {"DENY", "ALWAYS_DENY"}:
        return None
    if ACTION_CONFIRM_POLICY == "AUTO_SAFE" and intent.risk_level <= 1:
        return replace(intent, confirmation_required=False)
    return replace(intent, confirmation_required=True)


def _action_contract(intent: ActionIntent | ActionPlan, action_id: str, session_id: str, request_id: str = "", *, requesting_device: str = "", target_host: str = "", approved: bool = False, permission_entries: list[dict] | None = None) -> dict:
    """Build the one response schema consumed by Core, PC GUI and terminal."""
    confirmation_required = bool(intent.confirmation_required)
    if isinstance(intent, ActionPlan):
        actions = []
        previews = []
        entries = list(permission_entries or [])
        for index, item in enumerate(intent.actions):
            action = item.as_dict()
            action.pop("confirmation_required", None)
            action["type"] = "action"
            if index < len(entries):
                action.update({key: entries[index].get(key) for key in ("capability", "resource_scope", "human_scope_description", "persistent_grant_allowed", "resource_scope_version", "resource_kind")})
            actions.append(action)
            previews.append(describe_action(item))
        plan = {"type": "plan", "plan_id": action_id, "actions": actions, "risk_level": intent.risk_level, "confidence": intent.confidence, "source": intent.source, "permission_entries": entries}
        response = "GAIA quiere ejecutar:\n" + "\n".join(f"{index}. {text}" for index, text in enumerate(previews, 1))
        return {"kind": "plan", "response": response, "action_id": action_id, "session_id": session_id, "request_id": request_id, "request_state": "PLAN_REQUEST", "confirmation_required": confirmation_required, "preview": previews, "plan": plan, "permission_entries": entries, "resource_scope_version": RESOURCE_SCOPE_VERSION, "confirmation_options": {"allow_once": True, "allow_always": bool(entries) and all(bool(item.get("allow_always")) for item in entries), "cancel": True}, "requesting_device": requesting_device, "target_host": target_host, "approved": approved}
    action = intent.as_dict()
    action.pop("confirmation_required", None)
    action["type"] = "action"
    entries = list(permission_entries or [])
    if entries:
        action.update({key: entries[0].get(key) for key in ("capability", "resource_scope", "human_scope_description", "persistent_grant_allowed", "resource_scope_version", "resource_kind")})
    preview = describe_action(intent)
    return {"kind": "action", "response": preview, "action_id": action_id, "session_id": session_id, "request_id": request_id, "request_state": "ACTION_PENDING_CONFIRMATION", "confirmation_required": confirmation_required, "preview": preview, "action": action, "permission_entries": entries, "resource_scope_version": RESOURCE_SCOPE_VERSION, "confirmation_options": {"allow_once": True, "allow_always": bool(entries) and bool(entries[0].get("allow_always")), "cancel": True}, "requesting_device": requesting_device, "target_host": target_host, "approved": approved}


async def _allowed_intent_with_llm(message: str, structured: dict | None = None, pc_context: dict | None = None) -> ActionIntent | ActionPlan | None:
    intent = _allowed_intent(message, structured, pc_context)
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


@router.get("/platform/status", dependencies=[Depends(require_diagnostics)])
async def platform_status(request: Request):
    runtime = getattr(request.app.state, "platform_runtime", None)
    if runtime is None:
        return {"status": "NOT_STARTED", "capabilities": {}}
    return runtime.status()

@router.get("/visualizer", response_class=HTMLResponse)
async def visualizer_page():
    """Read-only GAIA-native dashboard; mutating controls are intentionally absent."""
    path = Path(__file__).resolve().parents[1] / "static" / "gaia_visualizer.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))

@router.get("/visualizer/events")
async def visualizer_events(request: Request):
    runtime = getattr(request.app.state, "platform_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="platform runtime unavailable")
    async def stream():
        yield "retry: 3000\n\n"
        async for payload in runtime.visualizer_stream.subscribe():
            if await request.is_disconnected(): break
            yield f"data: {payload}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})


@router.get("/capabilities", dependencies=[Depends(require_diagnostics)])
async def capabilities_status(request: Request):
    runtime = getattr(request.app.state, "platform_runtime", None)
    return {} if runtime is None else runtime.capabilities.status()


@router.get("/platform/plan", dependencies=[Depends(require_chat)])
async def platform_plan(message: str, request: Request):
    runtime = getattr(request.app.state, "platform_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="PlatformRuntime unavailable")
    return runtime.planner.serialize(runtime.planner.plan(message, mcp_configs=runtime.mcp.configs))


@router.get("/skills", dependencies=[Depends(require_diagnostics)])
async def platform_skills(request: Request):
    runtime = getattr(request.app.state, "platform_runtime", None)
    return [] if runtime is None else runtime.skills.list()


@router.get("/mcp/servers", dependencies=[Depends(require_diagnostics)])
async def platform_mcp_servers(request: Request):
    runtime = getattr(request.app.state, "platform_runtime", None)
    if runtime is None: return []
    return [{"name": c.name, "transport": c.transport, "enabled": c.enabled, "allow_tools": sorted(c.allow_tools), "deny_tools": sorted(c.deny_tools)} for c in runtime.mcp.configs.values()]


@router.get("/projects", dependencies=[Depends(require_chat)])
async def platform_projects(request: Request, principal: Annotated[Principal, Depends(require_chat)]):
    runtime = getattr(request.app.state, "platform_runtime", None)
    return [] if runtime is None else runtime.projects.list("master" if principal.is_master else str(principal.device_id))


@router.get("/jobs", dependencies=[Depends(require_chat)])
async def platform_jobs(request: Request, principal: Annotated[Principal, Depends(require_chat)]):
    runtime = getattr(request.app.state, "platform_runtime", None)
    return [] if runtime is None else runtime.jobs.list("master" if principal.is_master else str(principal.device_id))


@router.post("/diagnostics/export", dependencies=[Depends(require_diagnostics)])
async def platform_diagnostics_export(request: Request):
    runtime = getattr(request.app.state, "platform_runtime", None)
    if runtime is None: raise HTTPException(status_code=503, detail="PlatformRuntime unavailable")
    output = runtime.data / "diagnostics" / f"gaia-diagnostics-{uuid.uuid4().hex}.zip"
    manifest = runtime.diagnostics_exporter.export(output, status=runtime.status(), events=[], errors=[])
    return {"status":"created", "path":str(output), "manifest":manifest, "secret_values_emitted":False}


@router.get("/status", dependencies=[Depends(require_diagnostics)])
async def status():
    from proactive import is_enabled
    return {
        "name": ASSISTANT_NAME, "version": VERSION, "environment": ENVIRONMENT, "status": "online",
        "llm": await llm.check_backend(), "memory": memory.get_stats(), "backup_enabled": BACKUP_ENABLED,
        "vault": brain_backup.vault_status(), "devices": len(memory.get_devices()),
        "voice": {"tts_enabled": TTS_ENABLED, "stt_enabled": STT_ENABLED},
        "features": {"safe_mode": SAFE_MODE, "auto_facts": AUTO_FACTS_ENABLED, "proactive_auto": is_enabled(), "proactive_muted": __import__("proactive").is_muted(), "proactive_default": PROACTIVE_ENABLED_DEFAULT,
                     "streaming": True, "action_engine": ACTION_ENGINE_ENABLED, "actions_enabled": _actions_enabled(), "gaia_mode": GAIA_MODE, "action_max_level": ACTION_MAX_LEVEL},
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/diagnostics/performance", dependencies=[Depends(require_diagnostics)])
async def diagnostics_performance():
    return {
        "version": VERSION,
        "timestamp": datetime.now().isoformat(),
        "llm": llm.metrics(),
        "backend": await llm.check_backend(),
        "performance": {"profile": PERFORMANCE_PROFILE, "context_budget": MEMORY_CONTEXT_MAX_CHARS, "prompt": prompt_metrics(), "resources": _automation_runtime().status().get("resources", {})},
    }


@router.get("/diagnostics", dependencies=[Depends(require_diagnostics)])
async def diagnostics():
    stats = memory.get_stats()
    vault = brain_backup.vault_status()
    from backup_scheduler import backup_runtime_status
    return {
        "core": {"name": ASSISTANT_NAME, "version": VERSION, "environment": ENVIRONMENT, "safe_mode": SAFE_MODE, "status": "online", "timestamp": datetime.now().isoformat()},
        "lan": {"enabled": __import__("config").LAN_ENABLED, "host": __import__("config").HOST, "tls": False, "warning": "LAN requiere opt-in explícito y TLS externo." if __import__("config").LAN_ENABLED else "Solo localhost por defecto."},
        "database": {"status": "ok", "schema_version": stats.get("schema_version"), "fts5": stats.get("fts5"), "size_mb": stats.get("db_size_mb"), "messages": stats.get("total_messages")},
        "vault": {"status": vault.get("status"), "configured": bool(vault.get("root")), "fallback_warning": vault.get("fallback_warning", "")},
        "ollama": await llm.check_backend(),
        "llm_metrics": llm.metrics(),
        "performance": {"profile": PERFORMANCE_PROFILE, "context_budget": MEMORY_CONTEXT_MAX_CHARS, "prompt": prompt_metrics(), "resources": _automation_runtime().status().get("resources", {})},
        "voice": {"tts_enabled": TTS_ENABLED, "stt_enabled": STT_ENABLED, "audio_retention": __import__("config").AUDIO_RETENTION},
        "action_engine": {"enabled": ACTION_ENGINE_ENABLED, "actions_enabled": _actions_enabled(), "safe_mode_blocked": SAFE_MODE, "mode": GAIA_MODE, "max_level": ACTION_MAX_LEVEL, "confirm_policy": ACTION_CONFIRM_POLICY},
        "auth": {"model": "master_or_device_capabilities", "rbac_enabled": True, "brain_restore": "master_only"},
        "backup_scheduler": backup_runtime_status(),
        "devices": {"registered": len(memory.get_devices()), "tokens_enabled": DEVICE_TOKENS_ENABLED},
        "version": VERSION,
    }


async def _chat_service(req: ChatRequest, principal: Principal, platform_runtime=None) -> ChatResponse:
    session_id = _session_id(req)
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío.")
    device_id = effective_device(principal, req.device)
    target_host = _resolve_target_host(req.target_host, principal)
    request_context = _request_context(req)
    access_context = _memory_access_context(principal, session_id, device_id, source_channel=str(req.channel or "chat")[:32])
    if not memory.claim_session(session_id, device_id=device_id, principal_id=access_context.principal_id, is_master=principal.is_master):
        raise HTTPException(status_code=403, detail="La sesión pertenece a otro dispositivo o está en cuarentena.")
    memory.touch_device(device_id)
    if platform_runtime is not None:
        platform_result = await platform_runtime.handle_chat(
            user_message,
            principal=principal,
            session_id=session_id,
            device_id=device_id,
        )
        if platform_result is not None:
            memory.save_message(session_id, "user", user_message, device_id)
            memory.save_message(session_id, "assistant", str(platform_result.get("response") or ""), device_id)
            return ChatResponse(
                response=str(platform_result.get("response") or ""),
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                request_state="PLATFORM_CAPABILITY",
                active_context={"capability": platform_result.get("capability"), "status": platform_result.get("status"), "metadata": {k: v for k, v in platform_result.items() if k not in {"response", "results"}}},
            )
    request_state = "ACTION_REQUEST" if _is_action_request(user_message) else "CONVERSATION"
    if SAFE_MODE and request_state == "ACTION_REQUEST":
        memory.save_message(session_id, "user", user_message, device_id)
        memory.save_message(session_id, "assistant", _SAFE_MODE_ACTION_FALLBACK, device_id)
        return ChatResponse(response=_SAFE_MODE_ACTION_FALLBACK, session_id=session_id, timestamp=datetime.now().isoformat(), request_state="ACTION_REQUEST")
    if request_state == "ACTION_REQUEST" and not _actions_enabled():
        memory.save_message(session_id, "user", user_message, device_id)
        memory.save_message(session_id, "assistant", _ACTIONS_DISABLED_FALLBACK, device_id)
        return ChatResponse(response=_ACTIONS_DISABLED_FALLBACK, session_id=session_id, timestamp=datetime.now().isoformat(), request_state="ACTION_REQUEST")
    can_actions = can_request_actions(principal)
    if can_actions and not _is_capability_question(user_message):
        deterministic = _allowed_intent(user_message, req.intent, request_context)
        candidate = deterministic
        if candidate is None and request_state == "ACTION_REQUEST":
            candidate = await _allowed_intent_with_llm(user_message, req.intent)
    else:
        candidate = None
    if can_actions and request_state == "ACTION_REQUEST" and candidate is None:
        return _action_capability_failure(session_id, user_message, device_id)
    notice = _action_policy_notice(candidate, principal, device_id)
    if notice:
        memory.save_message(session_id, "user", user_message, device_id)
        memory.save_message(session_id, "assistant", notice, device_id)
        return ChatResponse(response=notice, session_id=session_id, timestamp=datetime.now().isoformat())
    intent = _apply_action_policy(candidate, principal, device_id)
    if intent:
        action_id = uuid.uuid4().hex
        memory.save_message(session_id, "user", user_message, device_id)
        memory.set_state("last_message_time", datetime.now().isoformat())
        memory.set_state("last_device", device_id)
        pending_state = _pending_action_state(intent, session_id=session_id, principal=principal, requesting_device=device_id, target_host=target_host)
        memory.set_state(f"pending_action:{action_id}", json.dumps(pending_state, ensure_ascii=False))
        contract = _action_contract(intent, action_id, session_id, requesting_device=device_id, target_host=target_host, approved=bool(pending_state["approved"]), permission_entries=_permission_entries(intent, principal, device_id))
        return ChatResponse(timestamp=datetime.now().isoformat(), **contract)
    system_prompt, messages = _prepare_context(session_id, user_message, device_id, request_context, principal=principal)
    try:
        response_text = await llm.chat_completion(system_prompt, messages, profile=req.profile or None, context_override=req.context)
    except llm.LLMError as exc:
        logger.warning("Fallo de chat: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    response_text = _ground_conversation_response(response_text, user_message=user_message, profile=req.profile or "auto", request_state=request_state)
    memory.save_message(session_id, "assistant", response_text, device_id)
    return ChatResponse(response=response_text, session_id=session_id, timestamp=datetime.now().isoformat(), active_context=_relevant_active_context(user_message, request_context))


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, req: ChatRequest, principal: Annotated[Principal, Depends(require_chat)]):
    return await _chat_service(req, principal, getattr(request.app.state, "platform_runtime", None))


async def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _assistant_stream(req: ChatRequest, principal: Principal) -> AsyncIterator[str]:
    session_id = _session_id(req)
    user_message = req.message.strip()
    if not user_message:
        yield await _sse_event("error", {"detail": "El mensaje no puede estar vacío."})
        return
    device_id = effective_device(principal, req.device)
    target_host = _resolve_target_host(req.target_host, principal)
    memory.touch_device(device_id)
    request_context = _request_context(req)
    request_id = uuid.uuid4().hex
    access_context = _memory_access_context(principal, session_id, device_id, request_id=request_id, source_channel=str(req.channel or "stream")[:32])
    if not memory.claim_session(session_id, device_id=device_id, principal_id=access_context.principal_id, is_master=principal.is_master):
        yield await _sse_event("error", {"detail": "La sesión pertenece a otro dispositivo o está en cuarentena.", "session_id": session_id, "request_id": request_id})
        return
    cancel_key = f"cancel:{request_id}"
    owner_key = f"request_owner:{request_id}"
    memory.set_state(cancel_key, "0")
    memory.set_state(owner_key, json.dumps({"request_id": request_id, "principal_type": principal.type, "device_id": principal.device_id, "token_id": principal.token_id, "session_id": session_id, "created_at": datetime.now().isoformat()}))
    yield await _sse_event("meta", {"session_id": session_id, "request_id": request_id})
    request_state = "ACTION_REQUEST" if _is_action_request(user_message) else "CONVERSATION"
    if SAFE_MODE and request_state == "ACTION_REQUEST":
        memory.save_message(session_id, "user", user_message, device_id)
        memory.save_message(session_id, "assistant", _SAFE_MODE_ACTION_FALLBACK, device_id)
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        yield await _sse_event("done", {"kind": "chat", "response": _SAFE_MODE_ACTION_FALLBACK, "session_id": session_id, "request_id": request_id, "request_state": "ACTION_REQUEST", "safe_mode_blocked": True, "timestamp": datetime.now().isoformat()})
        return
    if request_state == "ACTION_REQUEST" and not _actions_enabled():
        memory.save_message(session_id, "user", user_message, device_id)
        memory.save_message(session_id, "assistant", _ACTIONS_DISABLED_FALLBACK, device_id)
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        yield await _sse_event("done", {"kind": "chat", "response": _ACTIONS_DISABLED_FALLBACK, "session_id": session_id, "request_id": request_id, "request_state": "ACTION_REQUEST", "timestamp": datetime.now().isoformat()})
        return
    can_actions = can_request_actions(principal)
    if can_actions and not _is_capability_question(user_message):
        deterministic = _allowed_intent(user_message, req.intent, request_context)
        candidate = deterministic
        if candidate is None and request_state == "ACTION_REQUEST":
            candidate = await _allowed_intent_with_llm(user_message, req.intent)
    else:
        candidate = None
    if can_actions and request_state == "ACTION_REQUEST" and candidate is None:
        memory.save_message(session_id, "user", user_message, device_id)
        memory.save_message(session_id, "assistant", _UNAVAILABLE_ACTION_FALLBACK, device_id)
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        yield await _sse_event("done", {"kind": "chat", "response": _UNAVAILABLE_ACTION_FALLBACK, "session_id": session_id, "request_id": request_id, "request_state": "ACTION_REQUEST", "timestamp": datetime.now().isoformat()})
        return
    notice = _action_policy_notice(candidate, principal, device_id)
    if notice:
        memory.save_message(session_id, "user", user_message, device_id)
        memory.save_message(session_id, "assistant", notice, device_id)
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        yield await _sse_event("done", {"kind": "chat", "response": notice, "session_id": session_id, "request_id": request_id, "timestamp": datetime.now().isoformat()})
        return
    intent = _apply_action_policy(candidate, principal, device_id)
    if intent:
        action_id = uuid.uuid4().hex
        memory.save_message(session_id, "user", user_message, device_id)
        pending_state = _pending_action_state(intent, session_id=session_id, principal=principal, requesting_device=device_id, target_host=target_host, request_id=request_id)
        memory.set_state(f"pending_action:{action_id}", json.dumps(pending_state, ensure_ascii=False))
        payload = _action_contract(intent, action_id, session_id, request_id, requesting_device=device_id, target_host=target_host, approved=bool(pending_state["approved"]), permission_entries=_permission_entries(intent, principal, device_id))
        yield await _sse_event("action", payload)
        yield await _sse_event("done", {**payload, "timestamp": datetime.now().isoformat()})
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        return

    system_prompt, messages = _prepare_context(session_id, user_message, device_id, request_context, principal=principal, request_id=request_id)
    chunks: list[str] = []
    try:
        async for chunk in llm.chat_completion_stream(system_prompt, messages, profile=req.profile or None, context_override=req.context):
            if memory.get_state(cancel_key, "0") == "1":
                yield await _sse_event("cancelled", {"session_id": session_id, "request_id": request_id, "detail": "Generación cancelada por el usuario."})
                memory.delete_state(owner_key)
                memory.delete_state(cancel_key)
                return
            if chunk:
                # Buffer until policy grounding has inspected the complete visible response.
                # Safety wins over token-by-token display for untrusted conversational text.
                chunks.append(chunk)
    except llm.LLMError as exc:
        logger.warning("Fallo de streaming: %s", exc)
        yield await _sse_event("error", {"detail": str(exc), "session_id": session_id, "request_id": request_id})
        memory.delete_state(owner_key)
        memory.delete_state(cancel_key)
        return
    raw_response_text = "".join(chunks).strip()
    response_text = _ground_conversation_response(raw_response_text, user_message=user_message, profile=req.profile or "auto", request_state=request_state)
    yield await _sse_event("token", {"text": response_text})
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


class ActionClaimPayload(BaseModel):
    action_id: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)


class ActionApprovalPayload(BaseModel):
    action_id: str = Field(min_length=1, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    decision: str | None = Field(default=None, min_length=3, max_length=20)


class ActionHostHeartbeatPayload(BaseModel):
    device_id: str = Field(default="pc-main", min_length=1, max_length=80)
    host_version: str = Field(default="0.6.1-pc", min_length=1, max_length=40)
    busy: bool = False


def _action_host_status(device_id: str = "pc-main") -> dict:
    raw = memory.get_state(f"action_host:{device_id}")
    if not raw:
        return {"device_id": device_id, "online": False, "busy": False, "last_seen": None, "version": None}
    try:
        status = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {"device_id": device_id, "online": False, "busy": False, "last_seen": None, "version": None}
    try:
        age = max(0.0, (datetime.now() - datetime.fromisoformat(str(status.get("last_seen")))).total_seconds())
    except (TypeError, ValueError):
        age = 999999.0
    timeout = max(30.0, float(__import__("config").REMOTE_HOST_HEARTBEAT_SECONDS) * 3.0)
    status.update({"device_id": device_id, "online": age <= timeout, "age_seconds": round(age, 2), "timeout_seconds": timeout})
    return status


@router.post("/action-host/heartbeat")
async def action_host_heartbeat(payload: ActionHostHeartbeatPayload, principal: Annotated[Principal, Depends(require_action_host)]):
    _safe_mode_mutation_blocked()
    if not principal.is_master and principal.device_id != payload.device_id:
        raise HTTPException(status_code=403, detail="El heartbeat solo puede publicarse para el dispositivo autenticado.")
    now = datetime.now().isoformat()
    memory.set_state(f"action_host:{payload.device_id}", json.dumps({"device_id": payload.device_id, "host_version": payload.host_version, "busy": bool(payload.busy), "last_seen": now}, ensure_ascii=False))
    return {"status": "online", "device_id": payload.device_id, "host_version": payload.host_version, "busy": bool(payload.busy), "last_seen": now}


@router.get("/action-host/status")
async def action_host_status(principal: Annotated[Principal, Depends(require_chat)]):
    device_id = "pc-main"
    return _action_host_status(device_id)


@router.get("/actions/pending")
async def pending_actions(principal: Annotated[Principal, Depends(require_action_host)]):
    pending: list[dict] = []
    for row in memory.list_states("pending_action:"):
        try:
            item = json.loads(row["value"])
        except (TypeError, json.JSONDecodeError):
            continue
        if item.get("completed") or item.get("cancelled") or not item.get("approved"):
            continue
        target_host = str(item.get("target_host") or item.get("execution_host") or item.get("device") or PC_DEVICE_ID)
        if not principal.is_master and target_host != str(principal.device_id or ""):
            continue
        if item.get("claimed_by") and item.get("claimed_by") != principal.device_id and not principal.is_master:
            continue
        intent = item.get("intent") if isinstance(item.get("intent"), dict) else {}
        pending.append({"action_id": row["key"].split("pending_action:", 1)[-1], "session_id": item.get("session_id", ""), "device": item.get("device", ""), "requesting_device": item.get("requesting_device") or item.get("device", ""), "target_host": target_host, "intent": intent, "request_state": item.get("request_state", ""), "approved": bool(item.get("approved")), "auto_approved": bool(item.get("auto_approved")), "claimed_by": item.get("claimed_by")})
    return {"actions": pending[:20], "host_device": principal.device_id, "host_status": _action_host_status(str(principal.device_id or "pc-main"))}


async def _set_action_approval(payload: ActionApprovalPayload, principal: Principal, approved: bool) -> dict:
    _safe_mode_mutation_blocked()
    state_key = f"pending_action:{payload.action_id}"
    raw = memory.get_state(state_key)
    if not raw:
        raise HTTPException(status_code=404, detail="La acción ya no está pendiente o expiró.")
    try:
        pending = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Estado de acción inválido.") from exc
    if pending.get("session_id") != payload.session_id:
        raise HTTPException(status_code=409, detail="La sesión no coincide con la acción pendiente.")
    same_owner = principal.is_master or (pending.get("principal_type") == "device" and pending.get("device_id") == principal.device_id and pending.get("token_id") == principal.token_id)
    if not same_owner:
        raise HTTPException(status_code=403, detail="Solo el Principal propietario puede aprobar o rechazar esta acción.")
    if approved:
        decision = str(payload.decision or "").strip().upper()
        valid_decisions = {"ALLOW_ONCE", "ALWAYS_ALLOW", "ASK", "ALWAYS_ASK", "DENY", "ALWAYS_DENY"}
        if decision and decision not in valid_decisions:
            raise HTTPException(status_code=422, detail="Decisión de permiso inválida.")
        if decision in {"DENY", "ALWAYS_DENY", "ASK", "ALWAYS_ASK"}:
            raise HTTPException(status_code=422, detail="No se puede aprobar una acción con una decisión de rechazo o consulta. Usa /actions/reject.")
        pending_intent = pending.get("intent") if isinstance(pending.get("intent"), dict) else {}
        intents = pending_intent.get("actions", []) if pending_intent.get("type") == "plan" else [pending_intent]
        permission_ids: list[int] = []
        temporary_trust_apps: list[str] = []
        trusted_apps: list[str] = []
        if decision:
            for item in intents:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or item.get("action") or "")
                args = item.get("args") if isinstance(item.get("args"), dict) else {}
                risk = int(item.get("risk_level", 0))
                if decision in {"ALLOW_ONCE", "ALWAYS_ALLOW"} and risk > 2:
                    raise HTTPException(status_code=409, detail="Esta capability de riesgo alto solo admite confirmación puntual.")
                capability, scope = _intent_permission_key(ActionIntent(name=name, args=args, risk_level=risk))
                permission_ids.append(memory.save_permission_grant(
                    principal_type=principal.type,
                    principal_id=str(principal.token_id or ""),
                    device_id=str(pending.get("requesting_device") or pending.get("device") or principal.device_id or "pc-main"),
                    capability=capability,
                    resource_scope=scope,
                    decision=decision,
                    risk_level=risk,
                    capability_version="1",
                ))
                if capability == "apps.open_discovered" and decision in {"ALLOW_ONCE", "ALWAYS_ALLOW"}:
                    try:
                        _discover, _get_trust, resolve_discovered_app, _revoke, set_app_trust = _safe_apps_module()
                        discovered = resolve_discovered_app(scope, require_trusted=False)
                        if not discovered:
                            raise HTTPException(status_code=404, detail="La aplicación descubierta ya no está disponible; vuelve a descubrirla.")
                        set_app_trust(scope, trusted=True, blocked=False, launch_definition=discovered.get("launch_definition"), display_name=str(discovered.get("display_name", "")), source=str(discovered.get("source", "")), process_names=tuple(discovered.get("process_names") or []))
                        trusted_apps.append(scope)
                        if decision == "ALLOW_ONCE":
                            temporary_trust_apps.append(scope)
                    except HTTPException:
                        raise
                    except (ImportError, OSError, ValueError) as exc:
                        raise HTTPException(status_code=409, detail=f"No se pudo validar el trust de la app: {exc}") from exc
        pending["approved"] = True
        pending["approved_by"] = principal.device_id or "master"
        pending["approved_at"] = datetime.now().isoformat()
        pending["approval_decision"] = decision or "CONFIRM_ONCE"
        pending["permission_ids"] = permission_ids
        pending["temporary_trust_apps"] = temporary_trust_apps
        pending["trusted_apps"] = trusted_apps
        memory.set_state(state_key, json.dumps(pending, ensure_ascii=False))
        return {"status": "approved", "action_id": payload.action_id, "session_id": payload.session_id, "decision": decision or "CONFIRM_ONCE", "permission_ids": permission_ids, "trusted_apps": trusted_apps}
    memory.delete_state(state_key)
    return {"status": "rejected", "action_id": payload.action_id, "session_id": payload.session_id}


@router.post("/actions/approve")
async def approve_action(payload: ActionApprovalPayload, principal: Annotated[Principal, Depends(authenticate)]):
    return await _set_action_approval(payload, principal, True)


@router.post("/actions/reject")
async def reject_action(payload: ActionApprovalPayload, principal: Annotated[Principal, Depends(authenticate)]):
    return await _set_action_approval(payload, principal, False)


@router.post("/actions/claim")
async def claim_action(payload: ActionClaimPayload, principal: Annotated[Principal, Depends(require_action_host)]):
    if SAFE_MODE:
        raise HTTPException(status_code=409, detail="SAFE_MODE_BLOCKED: no se pueden reclamar acciones remotas en Safe Mode.")
    state_key = f"pending_action:{payload.action_id}"
    raw = memory.get_state(state_key)
    if not raw:
        raise HTTPException(status_code=404, detail="La acción ya no está pendiente o expiró.")
    try:
        pending = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Estado de acción inválido.") from exc
    if pending.get("session_id") != payload.session_id:
        raise HTTPException(status_code=409, detail="La sesión no coincide con la acción pendiente.")
    if not pending.get("approved"):
        raise HTTPException(status_code=409, detail="La acción requiere aprobación explícita del dispositivo solicitante.")
    target_host = str(pending.get("target_host") or pending.get("execution_host") or pending.get("device") or PC_DEVICE_ID)
    if not principal.is_master and target_host != str(principal.device_id or ""):
        raise HTTPException(status_code=403, detail="La acción está dirigida a otro host autorizado.")
    claimed_by = str(pending.get("claimed_by") or "")
    if claimed_by and claimed_by != str(principal.device_id or "") and not principal.is_master:
        raise HTTPException(status_code=409, detail="La acción ya fue reclamada por otro host.")
    pending["claimed_by"] = str(principal.device_id or "master")
    pending["claimed_by_token"] = str(principal.token_id or "") if not principal.is_master else "master"
    memory.set_state(state_key, json.dumps(pending, ensure_ascii=False))
    return {"status": "claimed", "action_id": payload.action_id, "session_id": payload.session_id, "intent": pending.get("intent", {}), "claimed_by": pending["claimed_by"]}


@router.post("/actions/complete")
async def complete_action(req: ActionCompleteRequest, principal: Annotated[Principal, Depends(require_action_execution)]):
    if SAFE_MODE:
        raise HTTPException(status_code=409, detail="SAFE_MODE_BLOCKED: no se pueden completar acciones en Safe Mode.")
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
    if pending.get("cancelled") or not pending.get("approved"):
        raise HTTPException(status_code=409, detail="La acción fue rechazada o todavía no está autorizada; no se puede completar.")
    claimed_by = str(pending.get("claimed_by") or "")
    if claimed_by and claimed_by != str(principal.device_id or "") and not principal.is_master:
        raise HTTPException(status_code=409, detail="Un host diferente ya reclamó esta acción.")
    if not principal.is_master:
        same_device = pending.get("principal_type") == "device" and pending.get("device_id") == principal.device_id and pending.get("token_id") == principal.token_id
        claimed_host = claimed_by == principal.device_id and principal.allows(CAP_ACTION_HOST)
        if not same_device and not claimed_host:
            raise HTTPException(status_code=403, detail="La acción pertenece a otro Principal y no fue reclamada por este host.")
    pending_intent = pending.get("intent", {}) if isinstance(pending.get("intent"), dict) else {}
    if pending_intent.get("type") == "plan" and req.data.get("plan_id") != req.action_id:
        raise HTTPException(status_code=409, detail="El resultado no referencia el plan pendiente correcto.")
    deterministic_result = req.message.strip()
    result_data = dict(req.data)
    available_value = req.capability_available if req.capability_available is not None else result_data.get("capability_available", result_data.get("available"))
    status = str(req.status or result_data.get("status") or "").upper()
    observation_completed = bool(req.observation_completed if req.observation_completed is not None else result_data.get("observation_completed", False))
    effect_verified = bool(req.effect_verified if req.effect_verified is not None else result_data.get("effect_verified", False))
    side_effect_performed = bool(req.side_effect_performed if req.side_effect_performed is not None else result_data.get("side_effect_performed", False))
    execution_verified = bool(req.execution_verified if req.execution_verified is not None else result_data.get("execution_verified", False))
    if not status:
        if available_value is False:
            status = "UNAVAILABLE"
        elif bool(result_data.get("cancelled")):
            status = "CANCELLED"
        elif execution_verified:
            status = "SUCCESS"
        elif bool(req.success) and (observation_completed or effect_verified):
            status = "SUCCESS"
        else:
            status = "FAILED"
    if status == "SUCCESS" and available_value is False:
        status = "UNAVAILABLE"
    if status == "SUCCESS" and not (observation_completed or effect_verified):
        # Legacy hosts sent only execution_verified; treat that proof as the mutation evidence.
        if execution_verified:
            effect_verified = True
            side_effect_performed = True
        else:
            status = "FAILED"
            execution_verified = False
    if status != "SUCCESS":
        execution_verified = False
        effect_verified = False
        side_effect_performed = False
    success = status == "SUCCESS"
    result_data.update({"status": status, "capability_available": False if status == "UNAVAILABLE" else (True if available_value is None else bool(available_value)), "observation_completed": observation_completed, "effect_verified": effect_verified, "side_effect_performed": side_effect_performed, "execution_verified": execution_verified})
    verified = VerifiedActionResult(action=dict(pending_intent), success=success, message=deterministic_result, data=result_data, execution_verified=execution_verified, status=status, request_validated=bool(req.request_validated if req.request_validated is not None else result_data.get("request_validated", True)), execution_attempted=bool(req.execution_attempted if req.execution_attempted is not None else result_data.get("execution_attempted", True)), capability_available=result_data.get("capability_available"), side_effect_performed=side_effect_performed, effect_verified=effect_verified, observation_completed=observation_completed)
    verified_payload = verified.as_payload()
    deterministic_response = _deterministic_simple_response(pending_intent, verified.success, verified.message, verified.data)
    natural_response = _ground_post_action_response(verified, deterministic_response or verified.message)
    generated_by_llm = False
    request_state = {"SUCCESS": "ACTION_EXECUTED_SUCCESS", "UNAVAILABLE": "ACTION_EXECUTED_UNAVAILABLE", "DENIED": "ACTION_EXECUTED_DENIED", "CANCELLED": "ACTION_EXECUTED_CANCELLED", "PARTIAL": "ACTION_EXECUTED_PARTIAL"}.get(status, "ACTION_EXECUTED_FAILURE")
    result_payload = {**verified.as_payload(), "cancelled": status == "CANCELLED", "request_state": request_state, "natural_response": natural_response}
    device_id = effective_device(principal, req.device)
    memory.save_action(req.action_id, req.session_id, device_id, pending_intent, result_payload)
    permission_ids_to_mark = list(pending.get("permission_ids", [])) + list(req.data.get("permission_ids", []))
    for permission_id in permission_ids_to_mark:
        try:
            memory.mark_permission_used(int(permission_id))
        except (TypeError, ValueError):
            logger.warning("No se pudo consumir permission grant asociado a la acción %s", req.action_id)
    for app_id in list(pending.get("temporary_trust_apps", [])):
        try:
            _discover, _get_trust, _resolve, _revoke, set_app_trust = _safe_apps_module()
            trust = _get_trust(app_id)
            set_app_trust(app_id, trusted=False, blocked=bool(trust.get("blocked")), launch_definition=trust.get("launch_definition"), display_name=str(trust.get("display_name", "")), source=str(trust.get("source", "")), process_names=tuple(trust.get("process_names") or []))
        except (ImportError, OSError, ValueError):
            logger.warning("No se pudo retirar trust temporal de app para la acción %s", req.action_id)
    owner_device = str(pending.get("requesting_device") or pending.get("device") or device_id)[:80]
    memory.save_verified_owner_message(req.session_id, natural_response, owner_device)
    memory.set_state(state_key, json.dumps({"completed": True, **result_payload}))
    automation_run_id = str(pending.get("automation_run_id") or "")[:80]
    if automation_run_id:
        try:
            from automation_runtime import runtime
            runtime.publish({
                "event_type": "action.completed" if success else "action.failed",
                "source": "action_host",
                "source_id": req.action_id,
                "host": str(pending.get("target_host") or PC_DEVICE_ID),
                "device": device_id,
                "severity": "info" if success else "warning",
                "payload": {
                    "action_id": req.action_id,
                    "automation_run_id": automation_run_id,
                    "automation_rule_id": str(pending.get("automation_rule_id") or "")[:80],
                    "status": status,
                    "success": success,
                    "execution_verified": execution_verified,
                    "effect_verified": effect_verified,
                    "side_effect_performed": side_effect_performed,
                    "observation_completed": observation_completed,
                },
                "dedup_key": f"automation-action:{req.action_id}:{status}",
            })
        except (ImportError, RuntimeError, ValueError):
            logger.exception("No se pudo publicar el resultado de acción automatizada %s", req.action_id)
    return {"status": "completed", "action_id": req.action_id, "session_id": req.session_id, "request_state": request_state, "response": natural_response, "deterministic_response": deterministic_response or verified.message, "success": verified.success, "data": verified.data, "verified_result": verified_payload, "result_status": status, "capability_available": verified.capability_available, "side_effect_performed": verified.side_effect_performed, "effect_verified": verified.effect_verified, "observation_completed": verified.observation_completed, "execution_verified": verified.execution_verified, "generated_by_llm": generated_by_llm, "timestamp": datetime.now().isoformat()}


@router.post("/chat/voice")
async def chat_voice(
    principal: Annotated[Principal, Depends(require_voice_chat)],
    audio: UploadFile = File(...),
    session_id: str = "",
    device: str = "pc",
    target_host: str = Form(default=""),
    channel: str = Form(default="desktop_voice", max_length=32),
    request_envelope: str = Form(default="", max_length=24000),
    desktop_snapshot: str = Form(default="", max_length=24000),
):
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
    envelope = _form_dict(request_envelope)
    snapshot = _form_dict(desktop_snapshot)
    if not snapshot and isinstance(envelope.get("desktop_snapshot"), dict):
        snapshot = dict(envelope["desktop_snapshot"])
    envelope_session = str(envelope.get("session_id") or session_id)[:64]
    envelope_device = str(envelope.get("requesting_device") or device)[:40]
    envelope_target = str(envelope.get("target_host") or target_host)[:80]
    voice_context = {"desktop_snapshot": snapshot} if snapshot else {}
    chat_resp = await _chat_service(ChatRequest(message=user_text, session_id=envelope_session, device=envelope_device, target_host=envelope_target, channel=str(channel or "desktop_voice")[:32], request_envelope=envelope, desktop_snapshot=snapshot or None, pc_context=voice_context), principal)
    audio_url: str | None = None
    tts_error: str | None = None
    if TTS_ENABLED and chat_resp.kind == "chat":
        try:
            audio_path = await text_to_speech(chat_resp.response)
            audio_url = f"/api/voice/audio/{Path(audio_path).name}"
        except Exception as exc:
            tts_error = str(exc)
            logger.warning("Respuesta generada, pero TTS falló: %s", exc)
    return {"user_text": user_text, "response": chat_resp.response, "session_id": chat_resp.session_id, "timestamp": chat_resp.timestamp, "kind": chat_resp.kind, "action_id": chat_resp.action_id, "request_id": chat_resp.request_id, "confirmation_required": chat_resp.confirmation_required, "preview": chat_resp.preview, "action": chat_resp.action, "plan": chat_resp.plan, "confirmation_options": chat_resp.confirmation_options, "audio_url": audio_url, "tts_error": tts_error}


@router.get("/captures/{capture_id}")
async def get_capture(capture_id: str, principal: Annotated[Principal, Depends(require_chat)]):
    get_capture_record = _capture_module()
    owner_device = str(principal.device_id or "")
    record = get_capture_record(capture_id, owner_device=owner_device, is_master=principal.is_master)
    if not record:
        raise HTTPException(status_code=404, detail="Captura inexistente, expirada o fuera del scope del dispositivo.")
    return FileResponse(str(record["path"]), media_type="image/png", filename=f"{capture_id}.png", headers={"Cache-Control": "no-store"})


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


def _advanced_memory_context(principal: Principal, *, session_id: str = "") -> memory.MemoryAccessContext:
    device_id = str(principal.device_id or "") if not principal.is_master else ""
    return _memory_access_context(principal, session_id=session_id, device_id=device_id, source_channel="advanced-memory")


def _advanced_memory_visible(item: dict[str, Any] | None, principal: Principal) -> bool:
    if not item:
        return False
    if principal.is_master:
        return True
    device_id = str(principal.device_id or "")
    item_device = str(item.get("device_id") or "")
    if not device_id or not item_device or item_device != device_id:
        return False
    session_id = str(item.get("session_id") or "")
    return not session_id or memory.session_access_allowed(session_id, device_id=device_id, principal_id=device_id, is_master=False)


def _advanced_memory_device(payload_device: str, principal: Principal) -> str:
    requested = str(payload_device or "").strip()[:80]
    if requested and not principal.is_master and requested != principal.device_id:
        raise HTTPException(status_code=403, detail="Solo puedes escribir memoria de tu propio dispositivo.")
    return requested


@router.get("/memory/advanced/search")
async def advanced_memory_search(query: str = Query(default="", max_length=500), scope: str | None = Query(default=None, max_length=80), project: str | None = Query(default=None, max_length=120), session_id: str | None = Query(default=None, max_length=80), limit: int = Query(default=12, ge=1, le=50), max_chars: int = Query(default=5000, ge=800, le=12000), principal: Annotated[Principal, Depends(require_memory_read)] = None):
    context = _advanced_memory_context(principal, session_id=session_id or "")
    try:
        return advanced_memory.retrieve(query, scope=scope, project=project, session_id=session_id, device_id=None if principal.is_master else principal.device_id, include_all_devices=principal.is_master, limit=limit, max_chars=max_chars, access_context=context)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.") from exc


@router.get("/memory/advanced/items")
async def advanced_memory_items(scope: str | None = Query(default=None, max_length=80), project: str | None = Query(default=None, max_length=120), session_id: str | None = Query(default=None, max_length=80), limit: int = Query(default=50, ge=1, le=50), principal: Annotated[Principal, Depends(require_memory_read)] = None):
    context = _advanced_memory_context(principal, session_id=session_id or "")
    try:
        return advanced_memory.list_items(scope=scope, project=project, session_id=session_id, device_id=None if principal.is_master else principal.device_id, include_all_devices=principal.is_master, limit=limit, access_context=context)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.") from exc


@router.post("/memory/advanced/item")
async def advanced_memory_add(payload: AdvancedMemoryPayload, principal: Annotated[Principal, Depends(require_memory_write)]):
    _safe_mode_mutation_blocked()
    try:
        values = payload.model_dump()
        if principal.is_master:
            values["device_id"] = _advanced_memory_device(values.get("device_id", ""), principal)
        else:
            values["device_id"] = str(principal.device_id or "")
        session_id = str(values.get("session_id") or "")
        context = _advanced_memory_context(principal, session_id=session_id)
        if session_id and not principal.is_master and not memory.claim_session(session_id, device_id=context.device_id, principal_id=context.principal_id, is_master=False):
            raise HTTPException(status_code=403, detail="La sesión pertenece a otro dispositivo o está en cuarentena.")
        return {"status": "saved", "item": advanced_memory.save_item(**values, access_context=context)}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/memory/advanced/item/{item_id}")
async def advanced_memory_get(item_id: int, history: bool = False, principal: Annotated[Principal, Depends(require_memory_read)] = None):
    context = _advanced_memory_context(principal)
    try:
        item = advanced_memory.get_item(item_id, include_history=history, access_context=context)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.") from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.")
    return item


@router.put("/memory/advanced/item/{item_id}")
async def advanced_memory_edit(item_id: int, payload: AdvancedMemoryUpdatePayload, principal: Annotated[Principal, Depends(require_memory_write)]):
    _safe_mode_mutation_blocked()
    context = _advanced_memory_context(principal)
    values = {key: value for key, value in payload.model_dump().items() if value is not None}
    if principal.is_master and "device_id" in values:
        values["device_id"] = _advanced_memory_device(values["device_id"], principal)
    elif not principal.is_master:
        values["device_id"] = str(principal.device_id or "")
    try:
        item = advanced_memory.update_item(item_id, access_context=context, **values)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.")
    return {"status": "updated", "item": item}


@router.patch("/memory/advanced/item/{item_id}/flags")
async def advanced_memory_flags(item_id: int, payload: AdvancedMemoryFlagsPayload, principal: Annotated[Principal, Depends(require_memory_write)]):
    _safe_mode_mutation_blocked()
    context = _advanced_memory_context(principal)
    try:
        item = advanced_memory.set_flags(item_id, pinned=payload.pinned, user_confirmed=payload.user_confirmed, access_context=context)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.") from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.")
    return {"status": "updated", "item": item}


@router.delete("/memory/advanced/item/{item_id}")
async def advanced_memory_delete(item_id: int, principal: Annotated[Principal, Depends(require_memory_write)]):
    _safe_mode_mutation_blocked()
    context = _advanced_memory_context(principal)
    try:
        deleted = advanced_memory.delete_item(item_id, access_context=context)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.")
    return {"status": "deleted", "id": item_id}


@router.get("/memory/advanced/audit")
async def advanced_memory_audit(limit: int = Query(default=100, ge=1, le=200), principal: Annotated[Principal, Depends(require_memory_read)] = None):
    context = _advanced_memory_context(principal)
    entries = advanced_memory.audit(limit, access_context=context)
    if principal.is_master:
        return entries
    return [entry for entry in entries if entry.get("device_id") == principal.device_id]


@router.post("/memory/advanced/consolidate")
async def advanced_memory_consolidate(payload: MemoryConsolidatePayload, principal: Annotated[Principal, Depends(require_memory_write)]):
    _safe_mode_mutation_blocked()
    resource_policy = _resource_governor().observe()
    if resource_policy.get("defer_consolidation"):
        raise HTTPException(status_code=409, detail="RESOURCE_GOVERNOR_DEFERRED: consolidación pospuesta por batería o presión térmica sostenida.")
    access_context = _memory_access_context(principal, payload.session_id, principal.device_id, source_channel="memory.consolidate")
    if not memory.session_access_allowed(payload.session_id, device_id=access_context.device_id, principal_id=access_context.principal_id, is_master=principal.is_master):
        raise HTTPException(status_code=403, detail="Solo puedes consolidar una sesión de tu propio dispositivo.")
    try:
        return advanced_memory.consolidate_session(payload.session_id, max_messages=payload.max_messages, access_context=access_context)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Solo puedes consolidar una sesión de tu propio dispositivo.") from exc


@router.get("/memory/tasks", dependencies=[Depends(require_memory_read)])
async def memory_tasks(limit: int = Query(default=30, ge=1, le=100)):
    return memory.get_open_tasks(limit)


@router.post("/memory/tasks", dependencies=[Depends(require_memory_write)])
async def add_memory_task(req: OpenTaskRequest):
    _safe_mode_mutation_blocked()
    return {"status": "saved", "id": memory.save_open_task(req.task, req.session_id)}


@router.post("/memory/tasks/{task_id}/close", dependencies=[Depends(require_memory_write)])
async def close_memory_task(task_id: int):
    _safe_mode_mutation_blocked()
    if not memory.close_open_task(task_id):
        raise HTTPException(status_code=404, detail="Tarea abierta no encontrada.")
    return {"status": "closed", "id": task_id}


@router.post("/memory/project-note", dependencies=[Depends(require_memory_write)])
async def add_project_note(req: ProjectNoteRequest):
    _safe_mode_mutation_blocked()
    memory.save_project_note(req.project, req.note, req.note_key)
    return {"status": "saved", "project": req.project}


@router.get("/memory/project-notes", dependencies=[Depends(require_memory_read)])
async def project_notes(project: str = Query(min_length=1, max_length=120)):
    return memory.get_project_notes(project)


@router.get("/memory/sessions/{session_id}/summary")
async def session_summary(session_id: str, refresh: bool = False, principal: Annotated[Principal, Depends(require_memory_read)] = None):
    if refresh:
        _safe_mode_mutation_blocked()
    access_context = _memory_access_context(principal, session_id, principal.device_id, source_channel="memory.summary")
    if not memory.session_access_allowed(session_id, device_id=access_context.device_id, principal_id=access_context.principal_id, is_master=principal.is_master):
        raise HTTPException(status_code=404, detail="Sesión no encontrada o fuera del scope del dispositivo.")
    try:
        summary = memory.maybe_update_session_summary(session_id, force=refresh, access_context=access_context)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o fuera del scope del dispositivo.") from exc
    return {"session_id": session_id, "summary": summary, **memory.get_session_summary_record(session_id)}


@router.get("/memory/context/{session_id}")
async def memory_context(session_id: str, query: str = Query(default="", max_length=500), principal: Annotated[Principal, Depends(require_memory_read)] = None):
    access_context = _memory_access_context(principal, session_id, principal.device_id, source_channel="memory.context")
    if not memory.session_access_allowed(session_id, device_id=access_context.device_id, principal_id=access_context.principal_id, is_master=principal.is_master):
        raise HTTPException(status_code=404, detail="Sesión no encontrada o fuera del scope del dispositivo.")
    try:
        return memory.get_context_bundle(session_id, query, access_context=access_context)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o fuera del scope del dispositivo.") from exc


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


@router.post("/devices/{device_id}/rotate-token", dependencies=[Depends(require_master_auth)])
async def rotate_device_token(device_id: str, req: DeviceTokenRequest):
    if not DEVICE_TOKENS_ENABLED:
        raise HTTPException(status_code=409, detail="Los tokens de dispositivo están desactivados.")
    try:
        rotated = memory.rotate_device_token(device_id, ttl_days=req.ttl_days)
        memory.record_admin_audit("master", None, "device_token_rotate", device_id, "success", {"token_id": rotated.get("token_id"), "ttl_days": req.ttl_days})
        return {"status": "rotated", "old_tokens_revoked": True, **rotated}
    except ValueError as exc:
        memory.record_admin_audit("master", None, "device_token_rotate", device_id, "failed")
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    _safe_mode_mutation_blocked()
    memory.set_preference(req.key, req.value)
    return {"status": "saved"}


@router.get("/memory/preferences", dependencies=[Depends(require_memory_read)])
async def get_prefs():
    return memory.get_all_preferences()


@router.get("/memory/sessions")
async def list_sessions(principal: Annotated[Principal, Depends(require_memory_read)]):
    return memory.get_all_sessions(_memory_access_context(principal, device_id=principal.device_id, source_channel="memory.sessions"))


@router.get("/memory/history/{session_id}")
async def get_history(session_id: str, limit: int = Query(default=50, ge=1, le=200), principal: Annotated[Principal, Depends(require_memory_read)] = None):
    access_context = _memory_access_context(principal, session_id, principal.device_id, source_channel="memory.history")
    if not memory.session_access_allowed(session_id, device_id=access_context.device_id, principal_id=access_context.principal_id, is_master=principal.is_master):
        raise HTTPException(status_code=404, detail="Sesión no encontrada o fuera del scope del dispositivo.")
    try:
        return memory.get_conversation_history(session_id, limit, access_context=access_context)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o fuera del scope del dispositivo.") from exc


@router.post("/backup", dependencies=[Depends(require_backup_create)])
async def backup():
    _safe_mode_mutation_blocked()
    return {"status": "backup_created", "path": memory.create_backup()}


@router.post("/backup/brain")
async def brain_backup_create(principal: Annotated[Principal, Depends(require_backup_create)]):
    _safe_mode_mutation_blocked()
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
    _safe_mode_mutation_blocked()
    message_id = memory.enqueue_proactive_message("manual_test", req.message)
    return {"status": "queued", "id": message_id, "message": req.message}


@router.post("/proactive/toggle", dependencies=[Depends(require_proactive_control)])
async def proactive_toggle(enabled: bool = True):
    _safe_mode_mutation_blocked()
    from proactive import set_enabled
    set_enabled(enabled)
    return {"status": "ok", "enabled": enabled}


@router.post("/proactive/mute", dependencies=[Depends(require_proactive_control)])
async def proactive_mute(muted: bool = True):
    _safe_mode_mutation_blocked()
    from proactive import set_muted
    set_muted(muted)
    return {"status": "ok", "muted": muted}


@router.get("/profile", dependencies=[Depends(require_memory_read)])
async def user_profile():
    from fact_extractor import get_user_profile
    return get_user_profile()


# ---------------------------------------------------------------------------
# v0.8 Event Engine / Automations
# ---------------------------------------------------------------------------


def _automation_owner(principal: Principal) -> str:
    return "master" if principal.is_master else str(principal.device_id or "")[:80]


def _automation_runtime():
    from automation_runtime import runtime
    return runtime


def _event_from_payload(payload: dict[str, Any] | None) -> Event | None:
    if not payload:
        return None
    try:
        return Event.create(
            str(payload.get("event_type") or "core.ready"),
            source=str(payload.get("source") or "dry_run")[:80],
            source_id=str(payload.get("source_id") or "")[:80],
            host=str(payload.get("host") or "core")[:80],
            device=str(payload.get("device") or "")[:80],
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            severity=str(payload.get("severity") or "info"),
            dedup_key="dry-run:" + uuid.uuid4().hex,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Evento de dry-run inválido: {exc}") from exc


@router.get("/automation/status", dependencies=[Depends(require_proactive_read)])
async def automation_status():
    return _automation_runtime().status()


@router.post("/automation/mode", dependencies=[Depends(require_master_auth)])
async def automation_mode(payload: AutomationModePayload):
    if SAFE_MODE and str(payload.mode).strip().upper() != "OFF":
        raise HTTPException(status_code=409, detail="SAFE_MODE_BLOCKED: solo se permite OFF en Safe Mode.")
    try:
        mode = _automation_runtime().set_mode(payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "updated", "mode": mode}


@router.post("/automation/pause", dependencies=[Depends(require_master_auth)])
async def automation_pause(paused: bool = True):
    if SAFE_MODE and not paused:
        raise HTTPException(status_code=409, detail="SAFE_MODE_BLOCKED: las automatizaciones permanecen pausadas.")
    _automation_runtime().pause(paused)
    return {"status": "paused" if paused else "resumed", "paused": bool(paused)}


@router.get("/automations")
async def automations_list(principal: Annotated[Principal, Depends(authenticate)]):
    owner = None if principal.is_master else _automation_owner(principal)
    return {"automations": automation_store.list_rules(owner, include_disabled=True)}


@router.post("/automations/dry-run")
async def automations_dry_run(payload: AutomationDryRunPayload, principal: Annotated[Principal, Depends(authenticate)]):
    owner = _automation_owner(principal)
    rule = payload.rule.model_dump()
    rule["owner_device"] = owner
    event = _event_from_payload(payload.event)
    routine = automation_store.get_routine(str(rule.get("routine_id") or "")) if rule.get("routine_id") else None
    preview = _automation_runtime().automation.dry_run(rule, event, routine)
    return {"status": "preview", "owner_device": owner, "preview": preview}


@router.post("/automations")
async def automations_create(payload: AutomationRulePayload, principal: Annotated[Principal, Depends(authenticate)]):
    if SAFE_MODE:
        raise HTTPException(status_code=409, detail="SAFE_MODE_BLOCKED: no se pueden crear automatizaciones en Safe Mode.")
    if not payload.preview_confirmed:
        raise HTTPException(status_code=409, detail="La regla requiere dry-run y preview confirmado antes de guardarse.")
    owner = _automation_owner(principal)
    rule = payload.model_dump()
    rule_errors = AutomationEngine.validate_rule(rule)
    if rule_errors:
        raise HTTPException(status_code=422, detail=rule_errors)
    if payload.enabled and _automation_runtime().automation.mode == "OFF":
        raise HTTPException(status_code=409, detail="El modo de automatización está OFF; cambia el modo explícitamente antes de habilitar reglas.")
    saved = automation_store.save_rule(rule, owner_device=owner, enabled=payload.enabled)
    await _automation_runtime().refresh_watchers()
    return {"status": "saved", "automation": saved}


@router.post("/automations/{rule_id}/enabled")
async def automations_enabled(rule_id: str, enabled: bool = True, principal: Annotated[Principal, Depends(authenticate)] = None):
    if SAFE_MODE and enabled:
        raise HTTPException(status_code=409, detail="SAFE_MODE_BLOCKED: no se pueden activar automatizaciones en Safe Mode.")
    owner = None if principal and principal.is_master else _automation_owner(principal)
    if enabled and _automation_runtime().automation.mode == "OFF":
        raise HTTPException(status_code=409, detail="El modo de automatización está OFF.")
    if not automation_store.set_rule_enabled(rule_id, enabled, owner_device=owner):
        raise HTTPException(status_code=404, detail="Automatización no encontrada o fuera del ownership.")
    await _automation_runtime().refresh_watchers()
    return {"status": "enabled" if enabled else "disabled", "rule_id": rule_id}


@router.get("/routines")
async def routines_list(principal: Annotated[Principal, Depends(authenticate)]):
    owner = None if principal.is_master else _automation_owner(principal)
    return {"routines": automation_store.list_routines(owner, include_disabled=True)}


@router.post("/routines")
async def routines_create(payload: RoutinePayload, principal: Annotated[Principal, Depends(authenticate)]):
    _safe_mode_mutation_blocked()
    if not payload.preview_confirmed:
        raise HTTPException(status_code=409, detail="La rutina requiere dry-run y preview confirmado antes de guardarse.")
    if payload.max_risk >= 3:
        raise HTTPException(status_code=409, detail="Las rutinas de riesgo 3/4 no se guardan como automatización unattended.")
    routine_errors = AutomationEngine._validate_steps(payload.steps)
    if routine_errors:
        raise HTTPException(status_code=422, detail=routine_errors)
    owner = _automation_owner(principal)
    try:
        saved = automation_store.save_routine(payload.model_dump(), owner_device=owner, enabled=payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "saved", "routine": saved}


@router.post("/routines/{routine_id}/enabled")
async def routines_enabled(routine_id: str, enabled: bool = True, principal: Annotated[Principal, Depends(authenticate)] = None):
    if enabled:
        _safe_mode_mutation_blocked()
    owner = None if principal and principal.is_master else _automation_owner(principal)
    if not automation_store.set_routine_enabled(routine_id, enabled, owner_device=owner):
        raise HTTPException(status_code=404, detail="Rutina no encontrada o fuera del ownership.")
    return {"status": "enabled" if enabled else "disabled", "routine_id": routine_id}


@router.get("/schedules")
async def schedules_list(principal: Annotated[Principal, Depends(authenticate)]):
    owner = None if principal.is_master else _automation_owner(principal)
    return {"schedules": automation_store.list_schedules(owner, include_disabled=True)}


@router.post("/schedules")
async def schedules_create(payload: SchedulePayload, principal: Annotated[Principal, Depends(authenticate)]):
    _safe_mode_mutation_blocked()
    if not payload.preview_confirmed:
        raise HTTPException(status_code=409, detail="El schedule requiere dry-run y preview confirmado antes de guardarse.")
    owner = _automation_owner(principal)
    schedule = payload.model_dump()
    if not schedule.get("next_due_at"):
        from scheduler import next_due
        schedule["next_due_at"] = next_due(schedule)
    try:
        saved = automation_store.save_schedule(schedule, owner_device=owner, enabled=payload.enabled)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "saved", "schedule": saved}


@router.post("/schedules/{schedule_id}/enabled")
async def schedules_enabled(schedule_id: str, enabled: bool = True, principal: Annotated[Principal, Depends(authenticate)] = None):
    if enabled:
        _safe_mode_mutation_blocked()
    owner = None if principal and principal.is_master else _automation_owner(principal)
    if not automation_store.set_schedule_enabled(schedule_id, enabled, owner_device=owner):
        raise HTTPException(status_code=404, detail="Schedule no encontrado o fuera del ownership.")
    return {"status": "enabled" if enabled else "disabled", "schedule_id": schedule_id}


@router.get("/notifications")
async def notifications_list(principal: Annotated[Principal, Depends(authenticate)]):
    return {"notifications": automation_store.list_notifications(None if principal.is_master else _automation_owner(principal))}


@router.patch("/notifications/{notification_id}")
async def notifications_update(notification_id: str, payload: NotificationUpdatePayload, principal: Annotated[Principal, Depends(authenticate)]):
    note = automation_store.get_notification(notification_id)
    if not note or (not principal.is_master and note.get("device_scope") not in {"", _automation_owner(principal)}):
        raise HTTPException(status_code=404, detail="Notificación no encontrada o fuera del ownership.")
    if not automation_store.mark_notification(notification_id, read=payload.read, dismissed=payload.dismissed):
        raise HTTPException(status_code=422, detail="No se indicó ningún cambio válido.")
    return {"status": "updated", "notification": automation_store.get_notification(notification_id)}
