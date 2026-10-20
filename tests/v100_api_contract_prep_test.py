"""API/error contract review for the v1.0 preparation stage."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_v100_api_contract_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-api-contract-v100-master-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    from fastapi.testclient import TestClient
    from main import app

    expected_paths = {
        "/api/health", "/api/status", "/api/chat",
        "/api/memory/advanced/search", "/api/memory/advanced/items",
        "/api/memory/advanced/item", "/api/memory/advanced/audit",
        "/api/memory/advanced/consolidate", "/api/diagnostics/performance",
    }
    paths = set(app.openapi().get("paths", {}))
    assert expected_paths.issubset(paths), sorted(expected_paths - paths)

    with TestClient(app) as client:
        unauthorized = client.get("/api/memory/advanced/search", params={"query": "x"})
        assert unauthorized.status_code == 401
        assert "test-api-contract" not in unauthorized.text

        master = {"Authorization": "Bearer test-api-contract-v100-master-secret"}
        missing = client.get("/api/memory/advanced/item/999999", headers=master)
        assert missing.status_code == 404
        assert "test-api-contract" not in missing.text

        invalid = client.post("/api/memory/advanced/item", headers=master, json={
            "memory_key": "bad", "kind": "not-a-kind", "category": "x", "content": "invalid"
        })
        assert invalid.status_code == 422
        assert "test-api-contract" not in invalid.text

        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json().get("version") == "2.0.0"

        diagnostics = client.get("/api/diagnostics/performance", headers=master)
        assert diagnostics.status_code == 200
        performance = diagnostics.json()["performance"]
        assert performance["resources"]["read_only"] is True
        assert performance["prompt"] == {}
        assert "test-api-contract" not in diagnostics.text

print("V100 RC1 API CONTRACT TEST OK: route inventory, auth/error statuses 401/404/422, RC1 health, diagnostics read-only and secret non-disclosure.")
