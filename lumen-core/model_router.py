from __future__ import annotations

"""Model/profile routing kept independent from the conversation transport."""

from dataclasses import dataclass
import logging

from config import LLM_FALLBACK_MODEL, LLM_MODEL, MODEL_BY_PROFILE

logger = logging.getLogger("lumen.model_router")


@dataclass(frozen=True)
class ModelSelection:
    profile: str
    preferred_model: str
    fallback_model: str
    selected_model: str
    used_fallback: bool = False
    reason: str = "configured"

    def as_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "preferred_model": self.preferred_model,
            "fallback_model": self.fallback_model,
            "selected_model": self.selected_model,
            "used_fallback": self.used_fallback,
            "reason": self.reason,
        }


VALID_PROFILES = {"auto", "fast", "normal", "reasoning", "code"}

PROFILES: dict[str, dict[str, int | float]] = {
    "fast": {"temperature": 0.55, "num_predict": 512, "num_ctx": 2048},
    "normal": {"temperature": 0.8, "num_predict": 1024, "num_ctx": 4096},
    "reasoning": {"temperature": 0.45, "num_predict": 2048, "num_ctx": 8192},
    "code": {"temperature": 0.25, "num_predict": 1536, "num_ctx": 8192},
}


def resolve_profile(message: str = "", requested: str | None = None, default: str = "normal") -> str:
    """Resolve request override > configured profile > global normal default."""
    requested_profile = (requested or "").strip().lower()
    text = " ".join(message.lower().split())
    if requested_profile in {"fast", "normal", "reasoning", "code"}:
        return requested_profile
    automatic = requested_profile in {"", "auto"}
    if automatic:
        if any(word in text for word in ("python", "javascript", "typescript", "bug", "error", "debug", "git", "stack trace", "traceback", "código", "codigo")):
            return "code"
        if any(phrase in text for phrase in ("analiza", "compara", "razona", "explica a fondo", "paso a paso", "profundamente", "pros y contras")):
            return "reasoning"
        if any(phrase in text for phrase in ("explícame", "explicame", "qué significa", "que significa", "cómo funciona", "como funciona")):
            return "normal"
        if len(text) < 80 or any(word in text for word in ("abre", "abrir", "inicia", "iniciar", "dime", "hola", "gracias")):
            return "fast"
    return default if default in PROFILES else "normal"


def profile_options(profile: str | None, context_override: int | None = None) -> dict[str, int | float]:
    selected = profile if profile in PROFILES else "normal"
    options = dict(PROFILES[selected])
    if context_override is not None:
        options["num_ctx"] = min(32768, max(512, int(context_override)))
    return options


def is_valid_profile(profile: str | None) -> bool:
    return (profile or "").strip().lower() in VALID_PROFILES


def selection_for(profile: str | None, installed_models: list[str] | None = None) -> ModelSelection:
    selected_profile = profile if profile in PROFILES else "normal"
    preferred = MODEL_BY_PROFILE.get(selected_profile) or LLM_MODEL
    fallback = LLM_FALLBACK_MODEL if LLM_FALLBACK_MODEL and LLM_FALLBACK_MODEL != preferred else ""
    installed = installed_models or []
    if installed and preferred not in installed:
        if fallback and fallback in installed:
            logger.warning("Modelo preferido no instalado; usando fallback configurado: %s -> %s", preferred, fallback)
            return ModelSelection(selected_profile, preferred, fallback, fallback, True, "preferred_model_not_installed")
        return ModelSelection(selected_profile, preferred, fallback, preferred, False, "preferred_model_not_installed")
    return ModelSelection(selected_profile, preferred, fallback, preferred)


def fallback_selection(selection: ModelSelection, reason: str) -> ModelSelection | None:
    if not selection.fallback_model or selection.used_fallback:
        return None
    logger.warning("Activando fallback explícito de modelo %s -> %s: %s", selection.selected_model, selection.fallback_model, reason)
    return ModelSelection(selection.profile, selection.preferred_model, selection.fallback_model, selection.fallback_model, True, reason)
