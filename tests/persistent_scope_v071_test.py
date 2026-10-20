from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="gaia_persistent_scope_") as tmp:
    os.environ.update({"LUMEN_DATA_DIR": tmp, "GAIA_MEMORY_DB": str(Path(tmp) / "memory" / "lumen_memory.db")})
    sys.path.insert(0, str(ROOT / "lumen-core"))
    import memory

    for decision in ("ALWAYS_ALLOW", "ALWAYS_DENY"):
        for scope in ("", "*", "uia:app=unresolved|window=unresolved|control=unresolved"):
            try:
                memory.save_permission_grant(principal_type="master", device_id="pc-main", capability="uia.invoke_control", resource_scope=scope, decision=decision, risk_level=1)
            except ValueError:
                pass
            else:
                raise AssertionError(f"Se aceptó grant persistente inseguro: {decision}/{scope!r}")

    grant_id = memory.save_permission_grant(principal_type="master", device_id="pc-main", capability="media.play_pause", resource_scope="media:active_media_session", decision="ALWAYS_ALLOW", risk_level=1)
    assert grant_id > 0
    print("PERSISTENT SCOPE V071 TEST OK: persistent grants reject empty/wildcard/unresolved scope and accept explicit media scope.")
