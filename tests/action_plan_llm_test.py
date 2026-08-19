"""El plan debe nacer del classifier LLM/mock, no de intent inyectado por el request."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_plan_llm_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "plan-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_ACTION_CONFIRM_POLICY": "CONFIRM_EXECUTION",
    })
    from fastapi.testclient import TestClient
    from main import app
    from intent_classifier import classify_intent
    from action_intent import ActionPlan

    headers = {"Authorization": "Bearer plan-secret"}
    with TestClient(app) as client:
        natural = client.post("/api/chat", headers=headers, json={"message": "Gaia, prepara mi entorno de trabajo."})
        assert natural.status_code == 200, natural.text
        payload = natural.json()
        assert payload["kind"] == "plan", payload
        assert payload["confirmation_required"] is True
        assert payload["plan"]["type"] == "plan"
        assert payload["plan"]["source"] == "llm"
        assert 1 <= len(payload["plan"]["actions"]) <= 3
        assert "1." in payload["response"] and "2." in payload["response"]

        malicious = client.post("/api/chat", headers=headers, json={"message": "Prepara todo y shutdown el equipo."})
        assert malicious.status_code == 200, malicious.text
        assert malicious.json()["kind"] == "chat", malicious.text

    import asyncio
    plan = asyncio.run(classify_intent("Gaia, prepara GAIA para trabajar."))
    assert isinstance(plan, ActionPlan) and plan.source == "llm"

print("ACTION PLAN LLM TEST OK: frase natural -> plan validado; plan malicioso rechazado completo.")
