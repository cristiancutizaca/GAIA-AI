"""Conteo de llamadas LLM para fast paths y completion post-action v0.6.0."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "lumen-core"
sys.path.insert(0, str(CORE))

with tempfile.TemporaryDirectory(prefix="gaia_v0543_perf_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-performance-v0543-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    import routes.api as api_routes
    from main import app

    calls = {"chat": 0, "stream": 0}
    original_chat = api_routes.llm.chat_completion
    original_stream = api_routes.llm.chat_completion_stream

    async def counted_chat(*args, **kwargs):
        calls["chat"] += 1
        return "Respuesta conversacional medida."

    async def counted_stream(*args, **kwargs):
        calls["stream"] += 1
        yield "Respuesta streaming medida."

    api_routes.llm.chat_completion = counted_chat
    api_routes.llm.chat_completion_stream = counted_stream
    headers = {"Authorization": "Bearer test-performance-v0543-secret"}
    try:
        with TestClient(app) as client:
            cases = (
                ("abre la calculadora", 0),
                ("baja el volumen al 20%", 0),
                ("estado del sistema", 0),
                ("lista proyectos", 0),
                ("¿Cómo está mi PC?", 0),
            )
            measured = []
            for message, expected_calls in cases:
                calls["chat"] = 0
                started = time.perf_counter()
                response = client.post("/api/chat", headers=headers, json={"message": message, "device": "perf"})
                elapsed_ms = (time.perf_counter() - started) * 1000
                assert response.status_code == 200, response.text
                assert calls["chat"] == expected_calls, (message, calls, response.json())
                measured.append((message, calls["chat"], elapsed_ms, response.json().get("kind")))

            calls["chat"] = 0
            calls["stream"] = 0
            with client.stream("POST", "/api/chat/stream", headers=headers, json={"message": "abre la calculadora", "device": "perf-sse"}) as streamed:
                assert streamed.status_code == 200
                stream_body = "\n".join(streamed.iter_lines())
            assert "event: action" in stream_body and calls["chat"] == 0 and calls["stream"] == 0, (stream_body, calls)
            measured.append(("SSE fast path", calls["chat"] + calls["stream"], 0.0, "action"))

            calls["chat"] = 0
            started = time.perf_counter()
            normal = client.post("/api/chat", headers=headers, json={"message": "Explícame qué es un proceso de Python.", "device": "perf"})
            elapsed_ms = (time.perf_counter() - started) * 1000
            assert normal.status_code == 200, normal.text
            assert calls["chat"] == 1, calls
            measured.append(("conversación normal", calls["chat"], elapsed_ms, normal.json().get("kind")))

            calls["chat"] = 0
            proposed = client.post("/api/chat", headers=headers, json={
                "message": "Gaia, muestra el estado de git",
                "device": "perf",
                "intent": {"type": "action", "action": "git_status", "args": {"path": ""}, "confidence": 0.97, "source": "deterministic"},
            })
            assert proposed.status_code == 200, proposed.text
            proposal = proposed.json()
            completed = client.post("/api/actions/complete", headers=headers, json={
                "action_id": proposal["action_id"],
                "session_id": proposal["session_id"],
                "device": "perf",
                "success": True,
                "message": "Git limpio.",
                "data": {"clean": True},
            })
            assert completed.status_code == 200, completed.text
            assert calls["chat"] == 0, "post-action completion debe ser factual y no llamar al LLM"
            measured.append(("post-action completion", calls["chat"], 0.0, completed.json().get("request_state")))
    finally:
        api_routes.llm.chat_completion = original_chat
        api_routes.llm.chat_completion_stream = original_stream

print("V0543 PERFORMANCE TEST OK: calculator/volume/system/projects fast paths=0 LLM, normal conversation=1 LLM, post-action=0 LLM")
