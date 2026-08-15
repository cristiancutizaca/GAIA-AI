"""Mensajes proactivos por cola; automatismo desactivado por defecto en v0.2."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
import memory
import llm
from personality import build_system_prompt
from config import PROACTIVE_ENABLED_DEFAULT, PROACTIVE_RULE_CHECK_SECONDS

logger = logging.getLogger("lumen.proactive")
MIN_INTERVAL_MINUTES = 30


def is_enabled() -> bool:
    stored = memory.get_state("proactive_enabled", "")
    return PROACTIVE_ENABLED_DEFAULT if stored == "" else stored == "true"


def set_enabled(enabled: bool) -> None:
    memory.set_state("proactive_enabled", "true" if enabled else "false")


def should_intervene() -> tuple[bool, str | None]:
    if not is_enabled():
        return False, None
    now = datetime.now()
    last = memory.get_state("last_proactive_time")
    if last:
        try:
            if now - datetime.fromisoformat(last) < timedelta(minutes=MIN_INTERVAL_MINUTES):
                return False, None
        except ValueError:
            pass
    last_msg = memory.get_state("last_message_time")
    if last_msg:
        try:
            if (now - datetime.fromisoformat(last_msg)).total_seconds() / 3600 > 4 and 9 <= now.hour <= 22:
                return True, "long_absence"
        except ValueError:
            pass
    return False, None


async def generate_proactive_message(reason: str) -> str:
    instruction = {"long_absence": "Envía un mensaje breve al usuario tras varias horas de ausencia."}.get(reason, "Envía un mensaje breve.")
    prompt = build_system_prompt(memory.get_preference("user_name"), memory.get_facts_summary())
    return await llm.chat_completion(prompt, [{"role": "user", "content": instruction}], temperature=0.7)


async def proactive_loop() -> None:
    while True:
        try:
            intervene, reason = should_intervene()
            if intervene and reason:
                message = await generate_proactive_message(reason)
                memory.enqueue_proactive_message(reason, message)
                memory.set_state("last_proactive_time", datetime.now().isoformat())
                logger.info("Mensaje proactivo encolado: %s", reason)
        except Exception:
            logger.exception("Fallo en proactividad automática")
        await asyncio.sleep(PROACTIVE_RULE_CHECK_SECONDS)
