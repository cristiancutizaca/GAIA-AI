from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_governor_api_v092_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "GAIA_MEMORY_DB": str(Path(tmp) / "memory.db"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-v092-governor-api-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
        "GAIA_AUTOMATION_MODE": "OFF",
    })
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    headers = {"Authorization": "Bearer test-v092-governor-api-secret"}
    response = client.get("/api/diagnostics/performance", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["performance"]["resources"]["read_only"] is True
    assert body["performance"]["prompt"] == {}
    assert "content" not in str(body["performance"]["prompt"]).casefold()

print("RESOURCE GOVERNOR API V092 TEST OK: diagnostics expose read-only resource/prompt metrics without content.")
