from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="gaia_trusted_api_v063_") as tmp:
    root = Path(tmp)
    os.environ.update({
        "LUMEN_DATA_DIR": str(root / "data"),
        "GAIA_MEMORY_DB": str(root / "data" / "memory.db"),
        "GAIA_TRUSTED_FOLDERS_FILE": str(root / "trusted_folders.json"),
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-trusted-folders-api-v063-secret",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    folder = root / "Documents"
    folder.mkdir()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lumen-core"))
    from fastapi.testclient import TestClient
    from main import app

    headers = {"Authorization": "Bearer test-trusted-folders-api-v063-secret"}
    with TestClient(app) as client:
        granted = client.post("/api/trusted-folders", headers=headers, json={"path": str(folder), "label": "Docs", "rights": ["READ", "OPEN"]})
        assert granted.status_code == 200, granted.text
        row = granted.json()["folder"]
        assert row["trusted"] is True and row["rights"] == ["OPEN", "READ"], row
        assert row["write_allowed"] is False, row

        listed = client.get("/api/trusted-folders", headers=headers)
        assert listed.status_code == 200 and "COPY_FROM" in listed.json()["rights"]
        assert any(item["folder_id"] == row["folder_id"] for item in listed.json()["folders"])

        updated = client.patch("/api/trusted-folders", headers=headers, json={"folder_id": row["folder_id"], "rights": ["READ", "OPEN", "COPY_TO"], "trusted": True})
        assert updated.status_code == 200, updated.text
        assert "COPY_TO" in updated.json()["folder"]["rights"]

        disabled = client.patch("/api/trusted-folders", headers=headers, json={"folder_id": row["folder_id"], "trusted": False})
        assert disabled.status_code == 200, disabled.text
        assert disabled.json()["folder"]["state"] == "DISABLED"

        revoked = client.request("DELETE", "/api/trusted-folders", headers=headers, json={"folder_id": row["folder_id"]})
        assert revoked.status_code == 200, revoked.text

print("TRUSTED FOLDERS API V063 TEST OK: explicit rights, disable and revoke are master-controlled.")
