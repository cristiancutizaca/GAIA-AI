from __future__ import annotations

"""Proveedor de telemetría local de Ollama; no cambia modelos ni ejecuta acciones."""

import os
from typing import Any

import httpx


OLLAMA_URL = os.getenv("GAIA_OLLAMA_URL", os.getenv("LUMEN_OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")


def collect_ollama_context(timeout: float = 1.5) -> dict[str, Any]:
    """Return loaded-model and runtime hints, or ``offline`` when unavailable."""
    try:
        with httpx.Client(timeout=max(0.2, float(timeout))) as client:
            ps_response = client.get(f"{OLLAMA_URL}/api/ps")
            tags_response = client.get(f"{OLLAMA_URL}/api/tags")
        if ps_response.status_code >= 400 and tags_response.status_code >= 400:
            return {"status": "offline"}
        ps_payload = ps_response.json() if ps_response.status_code < 400 else {}
        tags_payload = tags_response.json() if tags_response.status_code < 400 else {}
    except (httpx.HTTPError, ValueError, OSError):
        return {"status": "offline"}

    loaded = [_model_summary(item) for item in (ps_payload.get("models") or []) if isinstance(item, dict)]
    available = [str(item.get("name", "")) for item in (tags_payload.get("models") or []) if isinstance(item, dict) and item.get("name")]
    primary = loaded[0] if loaded else {}
    return {
        "status": "online",
        "model": primary.get("model") or (available[0] if available else None),
        "loaded_models": loaded[:8],
        "available_model_count": len(available),
        "processor_split": primary.get("processor_split"),
        "context_length": primary.get("context_length"),
        "keep_alive": primary.get("keep_alive"),
    }


def _model_summary(item: dict[str, Any]) -> dict[str, Any]:
    details = item.get("details") if isinstance(item.get("details"), dict) else {}
    processor = item.get("processor") or item.get("processor_split")
    return {
        "model": str(item.get("name") or item.get("model") or ""),
        "size": item.get("size"),
        "size_vram": item.get("size_vram"),
        "processor_split": processor,
        "context_length": item.get("context_length") or item.get("context"),
        "keep_alive": item.get("expires_at") or item.get("keep_alive"),
        "family": details.get("family"),
        "parameter_size": details.get("parameter_size"),
    }


__all__ = ["collect_ollama_context"]
