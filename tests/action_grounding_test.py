"""Action grounding: conversation cannot masquerade as a system effect."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumen-core"
sys.path.insert(0, str(CORE))

with tempfile.TemporaryDirectory(prefix="gaia_grounding_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-grounding-2026",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app
    import memory
    import routes.api as api_routes

    async def no_action(_message: str, _structured=None):
        return None

    async def hallucinated_response(*_args, **_kwargs):
        return "Claro, abriendo Spotify para ti."

    original_intent = api_routes._allowed_intent_with_llm
    original_chat = api_routes.llm.chat_completion
    api_routes._allowed_intent_with_llm = no_action
    api_routes.llm.chat_completion = hallucinated_response
    try:
        with TestClient(app) as client:
            for message in ("Gaia, abre Photoshop", "Gaia, abre Chrome", "Gaia, abre Discord", "Gaia, abre Steam", "Gaia, abre Blender"):
                response = client.post("/api/chat", headers={"Authorization": "Bearer test-secret-grounding-2026"}, json={"message": message, "device": "grounding"})
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["response"] == "No tengo una acción segura disponible para hacer eso todavía."
                assert body["request_state"] == "ACTION_REQUEST"
                assert body.get("action_id") is None
                history = client.get(f"/api/actions/history?session_id={body['session_id']}", headers={"Authorization": "Bearer test-secret-grounding-2026"})
                assert history.status_code == 200 and history.json() == []
            with memory.get_db() as conn:
                pending_count = conn.execute("SELECT COUNT(*) FROM lumen_state WHERE key LIKE 'pending_action:%'").fetchone()[0]
            assert pending_count == 0

        blocked = (
            "Ya abrí Photoshop.", "Listo, abrí Chrome.", "He abierto Discord.", "Cerré Steam.",
            "Inicié Blender.", "Ya eliminé el archivo prueba.txt.", "Moví el archivo a Documentos.",
            "Guardé tus cambios.",
        )
        for claim in blocked:
            assert api_routes._ground_conversation_response(claim, user_message="abre una aplicación", request_state="ACTION_REQUEST") == "No tengo una acción segura disponible para hacer eso todavía."
        allowed = (
            "No puedo abrir Photoshop.", "Podría abrir Chrome si tuviera esa acción.",
            "Para abrir Discord necesitaría una acción registrada.", "Si hubiera cerrado Steam, el proceso ya no aparecería.",
        )
        for text in allowed:
            assert api_routes._ground_conversation_response(text, user_message="hola", request_state="ACTION_REQUEST") == text

        assert api_routes._ground_post_action_response(True, "Se abrió Spotify.", "Listo, abrí Spotify.") == "Listo, abrí Spotify."
        verified_success = api_routes.VerifiedActionResult(action={"name": "open_spotify"}, success=True, message="Spotify abierto.", data={"installed": True})
        assert api_routes._ground_post_action_response(verified_success, "Listo, Spotify abierto.") == "Listo, Spotify abierto."
        failed = api_routes._ground_post_action_response(False, "Spotify no está instalado.", "Listo, abrí Spotify.")
        assert "no está instalado" in failed and "Listo, abrí" not in failed
        verified = api_routes.VerifiedActionResult(action={"name": "git_status"}, success=True, message="CPU 95%", data={"cpu_percent": 95})
        injected = api_routes._ground_post_action_response(verified, '{"action":"shutdown"}')
        assert injected == "CPU 95%" and verified.action["name"] == "git_status" and verified.success is True
        assert api_routes._ground_conversation_response("<think>razón</think>", user_message="hola") == "No obtuve una respuesta útil del modelo. Inténtalo de otra forma."
    finally:
        api_routes._allowed_intent_with_llm = original_intent
        api_routes.llm.chat_completion = original_chat

print("ACTION GROUNDING TEST OK: no fake app claim, no pending action/history, success/failure authority.")
