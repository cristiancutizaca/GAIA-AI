from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-pc"))

with tempfile.TemporaryDirectory(prefix="gaia_cache_v092_") as tmp:
    os.environ["LUMEN_DATA_DIR"] = tmp
    os.environ["GAIA_TRUSTED_FOLDERS_TTL_SECONDS"] = "30"
    import trusted_folders

    initial = trusted_folders.list_trusted_folders()
    initial.append({"folder_id": "local-mutation"})
    assert all(row.get("folder_id") != "local-mutation" for row in trusted_folders.list_trusted_folders())

    candidate = Path(tmp) / "trusted"
    candidate.mkdir()
    granted = trusted_folders.grant_trusted_folder(str(candidate), rights=["READ"])
    assert granted["trusted"] is True
    assert trusted_folders.is_trusted_path(candidate) is True
    refreshed = trusted_folders.list_trusted_folders()
    assert any(row.get("folder_id") == granted["folder_id"] for row in refreshed)

print("CACHE CONTRACT V092 OK: TTL cache, defensive copies and write invalidation.")
