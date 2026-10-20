"""Visible fallback tests for empty/reasoning-only model output."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_empty_output_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-empty-output-2026",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app
    import routes.api as api_routes

    async def no_action(_message: str, _structured=None):
        return None

    async def empty_completion(*_args, **_kwargs):
        return "<think>razonamiento interno filtrable</think>"

    async def empty_stream(*_args, **_kwargs):
        if False:
            yield "nunca"

    original_intent = api_routes._allowed_intent_with_llm
    original_chat = api_routes.llm.chat_completion
    original_stream = api_routes.llm.chat_completion_stream
    api_routes._allowed_intent_with_llm = no_action
    api_routes.llm.chat_completion = empty_completion
    api_routes.llm.chat_completion_stream = empty_stream
    headers = {"Authorization": "Bearer test-secret-empty-output-2026"}
    try:
        with TestClient(app) as client:
            chat = client.post("/api/chat", headers=headers, json={"message": "dime algo", "device": "empty"})
            assert chat.status_code == 200, chat.text
            assert chat.json()["response"] == "No obtuve una respuesta útil del modelo. Inténtalo de otra forma."

            stream = client.post("/api/assistant/stream", headers=headers, json={"message": "dime algo en stream", "device": "empty"})
            assert stream.status_code == 200, stream.text
            assert "No obtuve una respuesta útil del modelo" in stream.text
            assert "El backend no devolvió texto visible" not in stream.text
    finally:
        api_routes._allowed_intent_with_llm = original_intent
        api_routes.llm.chat_completion = original_chat
        api_routes.llm.chat_completion_stream = original_stream

assert api_routes._ground_conversation_response("   ") == "No obtuve una respuesta útil del modelo. Inténtalo de otra forma."
print("EMPTY LLM OUTPUT TEST OK: conversation, reasoning-only and empty stream use visible fallback.")
