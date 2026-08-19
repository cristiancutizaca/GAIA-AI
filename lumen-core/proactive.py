"""Proactividad segura por cola; desactivada y silenciada por defecto."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

import llm
import memory
from config import BACKUP_ENABLED, PROACTIVE_COOLDOWN_MINUTES, PROACTIVE_CPU_THRESHOLD, PROACTIVE_ENABLED_DEFAULT, PROACTIVE_EVENT_COOLDOWN_MINUTES, PROACTIVE_LONG_SESSION_HOURS, PROACTIVE_MAX_DAILY, PROACTIVE_MEMORY_THRESHOLD, PROACTIVE_MUTED_DEFAULT, PROACTIVE_QUIET_END, PROACTIVE_QUIET_START, PROACTIVE_RULE_CHECK_SECONDS, PROACTIVE_SUSTAINED_SECONDS
from personality import build_system_prompt
import brain_backup

logger = logging.getLogger("lumen.proactive")


def is_enabled() -> bool:
    stored = memory.get_state("proactive_enabled", "")
    return PROACTIVE_ENABLED_DEFAULT if stored == "" else stored == "true"


def set_enabled(enabled: bool) -> None:
    memory.set_state("proactive_enabled", "true" if enabled else "false")


def is_muted() -> bool:
    stored = memory.get_state("proactive_muted", "")
    return PROACTIVE_MUTED_DEFAULT if stored == "" else stored == "true"


def set_muted(muted: bool) -> None:
    memory.set_state("proactive_muted", "true" if muted else "false")


def _in_quiet_hours(hour: int) -> bool:
    if PROACTIVE_QUIET_START == PROACTIVE_QUIET_END:
        return False
    if PROACTIVE_QUIET_START > PROACTIVE_QUIET_END:
        return hour >= PROACTIVE_QUIET_START or hour < PROACTIVE_QUIET_END
    return PROACTIVE_QUIET_START <= hour < PROACTIVE_QUIET_END


def _daily_count(now: datetime) -> int:
    if memory.get_state("proactive_count_date", "") != now.date().isoformat():
        return 0
    try:
        return int(memory.get_state("proactive_daily_count", "0"))
    except ValueError:
        return 0


def should_intervene() -> tuple[bool, str | None]:
    now = datetime.now()
    if not is_enabled() or is_muted() or _in_quiet_hours(now.hour) or _daily_count(now) >= PROACTIVE_MAX_DAILY:
        return False, None
    last = memory.get_state("last_proactive_time")
    if last:
        try:
            if now - datetime.fromisoformat(last) < timedelta(minutes=PROACTIVE_COOLDOWN_MINUTES):
                return False, None
        except ValueError:
            pass
    last_msg = memory.get_state("last_message_time")
    if last_msg:
        try:
            if (now - datetime.fromisoformat(last_msg)).total_seconds() / 3600 > 4:
                return True, "long_absence"
        except ValueError:
            pass
    return False, None


def _sustained(name: str, value: float, threshold: float) -> bool:
    key = f"proactive_metric_started:{name}"
    now = datetime.now()
    if value < threshold:
        memory.set_state(key, "")
        return False
    started = memory.get_state(key, "")
    if not started:
        memory.set_state(key, now.isoformat())
        return False
    try:
        return (now - datetime.fromisoformat(started)).total_seconds() >= PROACTIVE_SUSTAINED_SECONDS
    except ValueError:
        memory.set_state(key, now.isoformat())
        return False


def _event_available(reason: str) -> bool:
    value = memory.get_state(f"proactive_event_last:{reason}", "")
    if not value:
        return True
    try:
        return datetime.now() - datetime.fromisoformat(value) >= timedelta(minutes=PROACTIVE_EVENT_COOLDOWN_MINUTES)
    except ValueError:
        return True


def _first_available_event(reasons: list[str]) -> str | None:
    for reason in reasons:
        if _event_available(reason):
            memory.set_state(f"proactive_event_last:{reason}", datetime.now().isoformat())
            return reason
    return None


async def detect_environment_event() -> str | None:
    """Return one sustained event only when normal proactive gates permit it."""
    now = datetime.now()
    if not is_enabled() or is_muted() or _in_quiet_hours(now.hour) or _daily_count(now) >= PROACTIVE_MAX_DAILY:
        return None
    last = memory.get_state("last_proactive_time", "")
    if last:
        try:
            if now - datetime.fromisoformat(last) < timedelta(minutes=PROACTIVE_COOLDOWN_MINUTES):
                return None
        except ValueError:
            pass
    reasons: list[str] = []
    try:
        import psutil
        if _sustained("cpu", float(psutil.cpu_percent(interval=None)), PROACTIVE_CPU_THRESHOLD):
            reasons.append("high_cpu_sustained")
        if _sustained("memory", float(psutil.virtual_memory().percent), PROACTIVE_MEMORY_THRESHOLD):
            reasons.append("high_memory_sustained")
    except (ImportError, OSError):
        pass
    try:
        backend = await llm.check_backend()
        if str(backend.get("status", "")).lower() in {"offline", "error", "unavailable"}:
            reasons.append("ollama_failure")
    except Exception:
        reasons.append("ollama_failure")
    session = memory.get_work_session()
    started = str(session.get("started_at") or "")
    if started:
        try:
            if now - datetime.fromisoformat(started) >= timedelta(hours=PROACTIVE_LONG_SESSION_HOURS) and memory.get_state("last_message_time", ""):
                reasons.append("long_work_session")
        except ValueError:
            pass
    if BACKUP_ENABLED and memory.backup_due():
        reasons.append("backup_overdue")
    vault = brain_backup.vault_status()
    if str(vault.get("status", "")).lower() in {"missing", "unavailable", "not_configured"}:
        reasons.append("vault_missing")
    if memory.get_state("project_process_crashed", "false") == "true":
        reasons.append("project_process_crashed")
    return _first_available_event(reasons)


async def generate_proactive_message(reason: str) -> str:
    instruction = {"long_absence": "Envía un mensaje breve al usuario tras varias horas de ausencia.", "high_cpu_sustained": "Avisa en español y con sarcasmo breve que la CPU lleva varios minutos muy alta; no inventes la causa.", "high_memory_sustained": "Avisa que la RAM lleva varios minutos muy alta y recomienda revisar aplicaciones, sin ejecutar nada.", "ollama_failure": "Avisa que Ollama no responde o falló; distingue claramente que no puedes arreglarlo sin intervención.", "project_process_crashed": "Avisa que un proceso registrado del proyecto parece haber terminado o fallado.", "long_work_session": "Sugiere una pausa porque la sesión de trabajo lleva demasiadas horas.", "backup_overdue": "Avisa que el backup de memoria está atrasado y que es opcional según configuración.", "vault_missing": "Avisa que el Vault no está disponible y que no debes fingir que los secretos están protegidos."}.get(reason, "Envía un mensaje breve.")
    prompt = build_system_prompt(memory.get_preference("user_name"), memory.get_facts_summary())
    return await llm.chat_completion(prompt, [{"role": "user", "content": instruction}], profile="fast")


async def proactive_loop() -> None:
    while True:
        try:
            intervene, reason = should_intervene()
            if not intervene:
                reason = await detect_environment_event()
                intervene = bool(reason)
            if intervene and reason:
                message = await generate_proactive_message(reason)
                message_id = memory.enqueue_proactive_message(reason, message)
                now = datetime.now()
                memory.set_state("last_proactive_time", now.isoformat())
                memory.set_state("proactive_count_date", now.date().isoformat())
                memory.set_state("proactive_daily_count", str(_daily_count(now) + 1))
                logger.info("Mensaje proactivo encolado id=%s reason=%s daily_count=%s", message_id, reason, _daily_count(now))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Fallo controlado en proactividad automática: %s", exc)
        await asyncio.sleep(PROACTIVE_RULE_CHECK_SECONDS)
