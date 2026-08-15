"""API HTTP estable para clientes PC de LUMEN."""
from __future__ import annotations
import asyncio
import hmac
import logging
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Header, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import memory
import llm
from personality import build_system_prompt
from voice import text_to_speech, speech_to_text, get_available_voices
from config import (
    API_SECRET, DATA_DIR, BACKUP_ENABLED, AUTO_FACTS_ENABLED, PROACTIVE_ENABLED_DEFAULT,
    TTS_ENABLED, STT_ENABLED, MAX_AUDIO_UPLOAD_MB, VERSION, ENVIRONMENT,
)

logger = logging.getLogger("lumen.api")
router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str = Field(default="", max_length=64, pattern=r"^[\w-]*$")
    device: str = Field(default="pc", min_length=1, max_length=40)


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: str


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class FactRequest(BaseModel):
    category: str = Field(min_length=1, max_length=60)
    fact: str = Field(min_length=1, max_length=300)


class PreferenceRequest(BaseModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[\w.-]+$")
    value: str = Field(max_length=300)


class ProactiveTestRequest(BaseModel):
    message: str = Field(default="Mensaje proactivo de prueba: la cola y el polling funcionan.", min_length=1, max_length=500)


def require_auth(authorization: Annotated[str, Header()] = "") -> None:
    expected = f"Bearer {API_SECRET}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="No autorizado")


@router.get("/health")
async def health():
    """Comprobación mínima pública para saber si el Core está vivo."""
    return {"name": "LUMEN", "version": VERSION, "status": "online"}


@router.get("/status", dependencies=[Depends(require_auth)])
async def status():
    from proactive import is_enabled
    return {
        "name": "LUMEN", "version": VERSION, "environment": ENVIRONMENT, "status": "online",
        "llm": await llm.check_backend(), "memory": memory.get_stats(), "backup_enabled": BACKUP_ENABLED,
        "voice": {"tts_enabled": TTS_ENABLED, "stt_enabled": STT_ENABLED},
        "features": {"auto_facts": AUTO_FACTS_ENABLED, "proactive_auto": is_enabled(), "proactive_default": PROACTIVE_ENABLED_DEFAULT},
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_auth)])
async def chat(req: ChatRequest):
    session_id = req.session_id.strip() or uuid.uuid4().hex[:12]
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío.")
    memory.save_message(session_id, "user", user_message, req.device)
    memory.set_state("last_message_time", datetime.now().isoformat())
    memory.set_state("last_device", req.device)
    from fact_extractor import process_message
    extraction = process_message(user_message)
    contextual = [
        f"(historial reciente) {item['role']}: {item['content'][:180]}"
        for item in memory.get_recent_messages(14)
        if item["session_id"] != session_id
    ][-6:]
    if extraction.get("mood"):
        contextual.append(f"El usuario expresó que se siente {extraction['mood']}.")
    system_prompt = build_system_prompt(memory.get_preference("user_name"), memory.get_facts_summary(), contextual or None)
    history = memory.get_conversation_history(session_id, limit=20)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    try:
        response_text = await llm.chat_completion(system_prompt, messages)
    except llm.LLMError as exc:
        logger.warning("Fallo de chat: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    memory.save_message(session_id, "assistant", response_text, req.device)
    return ChatResponse(response=response_text, session_id=session_id, timestamp=datetime.now().isoformat())


@router.post("/chat/voice", dependencies=[Depends(require_auth)])
async def chat_voice(audio: UploadFile = File(...), session_id: str = "", device: str = "pc"):
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
    chat_resp = await chat(ChatRequest(message=user_text, session_id=session_id, device=device))
    audio_url: str | None = None
    tts_error: str | None = None
    if TTS_ENABLED:
        try:
            audio_path = await text_to_speech(chat_resp.response)
            audio_url = f"/api/voice/audio/{Path(audio_path).name}"
        except Exception as exc:
            tts_error = str(exc)
            logger.warning("Respuesta generada, pero TTS falló: %s", exc)
    return {"user_text": user_text, "response": chat_resp.response, "session_id": chat_resp.session_id,
            "audio_url": audio_url, "tts_error": tts_error, "timestamp": chat_resp.timestamp}


@router.get("/voice/audio/{filename}", dependencies=[Depends(require_auth)])
async def get_audio(filename: str):
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Nombre de audio inválido.")
    audio_path = DATA_DIR / "audio" / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio no encontrado.")
    return FileResponse(str(audio_path), media_type="audio/mpeg", filename=filename)


@router.post("/voice/tts", dependencies=[Depends(require_auth)])
async def tts_only(req: TTSRequest):
    try:
        audio_path = await text_to_speech(req.text)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return FileResponse(str(audio_path), media_type="audio/mpeg")


@router.get("/voice/voices", dependencies=[Depends(require_auth)])
async def list_voices():
    return await get_available_voices()


@router.post("/memory/fact", dependencies=[Depends(require_auth)])
async def add_fact(req: FactRequest):
    memory.save_fact(req.category.strip(), req.fact.strip(), source="manual", confidence=1.0)
    return {"status": "saved"}


@router.delete("/memory/fact/{fact_id}", dependencies=[Depends(require_auth)])
async def remove_fact(fact_id: int):
    if not memory.delete_fact(fact_id):
        raise HTTPException(status_code=404, detail="Fact no encontrado.")
    return {"status": "deleted"}


@router.get("/memory/facts", dependencies=[Depends(require_auth)])
async def get_facts(category: str | None = None):
    return memory.get_facts(category)


@router.post("/memory/preference", dependencies=[Depends(require_auth)])
async def set_pref(req: PreferenceRequest):
    memory.set_preference(req.key, req.value)
    return {"status": "saved"}


@router.get("/memory/preferences", dependencies=[Depends(require_auth)])
async def get_prefs():
    return memory.get_all_preferences()


@router.get("/memory/sessions", dependencies=[Depends(require_auth)])
async def list_sessions():
    return memory.get_all_sessions()


@router.get("/memory/history/{session_id}", dependencies=[Depends(require_auth)])
async def get_history(session_id: str, limit: int = Query(default=50, ge=1, le=200)):
    return memory.get_conversation_history(session_id, limit)


@router.post("/backup", dependencies=[Depends(require_auth)])
async def backup():
    return {"status": "backup_created", "path": memory.create_backup()}


@router.get("/proactive/check", dependencies=[Depends(require_auth)])
async def proactive_check():
    pending = memory.pop_proactive_message()
    return {"has_message": bool(pending), **(pending or {})}


@router.post("/proactive/test", dependencies=[Depends(require_auth)])
async def proactive_test(req: ProactiveTestRequest):
    message_id = memory.enqueue_proactive_message("manual_test", req.message)
    return {"status": "queued", "id": message_id, "message": req.message}


@router.post("/proactive/toggle", dependencies=[Depends(require_auth)])
async def proactive_toggle(enabled: bool = True):
    from proactive import set_enabled
    set_enabled(enabled)
    return {"status": "ok", "enabled": enabled}


@router.get("/profile", dependencies=[Depends(require_auth)])
async def user_profile():
    from fact_extractor import get_user_profile
    return get_user_profile()
