from __future__ import annotations

import os
from pathlib import Path
import tempfile

from rc2_migration_fixture import migration

keys = ("GAIA_MEMORY_DB", "LUMEN_MEMORY_DB", "GAIA_DATA_DIR", "LUMEN_DATA_DIR", "GAIA_HOME", "GAIA_VAULT")
with tempfile.TemporaryDirectory(prefix="gaia_rc2_env_order_") as tmp:
    root = Path(tmp) / "install"
    root.mkdir(parents=True)
    paths = {key: Path(tmp) / key.lower() for key in keys}
    (root / ".env").write_text(
        "GAIA_MEMORY_DB=gaia-memory.db\n"
        "LUMEN_MEMORY_DB=lumen-memory.db\n"
        "GAIA_DATA_DIR=gaia-data\n"
        "LUMEN_DATA_DIR=lumen-data\n"
        "GAIA_HOME=gaia-home\n"
        "GAIA_VAULT=gaia-vault\n",
        encoding="utf-8",
    )
    saved = {key: os.environ.pop(key, None) for key in keys}
    try:
        assert migration.resolve_db_path(root, include_process=False) == root / "gaia-memory.db"
        (root / ".env").write_text("LUMEN_MEMORY_DB=lumen-memory.db\nGAIA_DATA_DIR=gaia-data\n", encoding="utf-8")
        assert migration.resolve_db_path(root, include_process=False) == root / "lumen-memory.db"
        (root / ".env").write_text("GAIA_DATA_DIR=gaia-data\nLUMEN_DATA_DIR=lumen-data\n", encoding="utf-8")
        assert migration.resolve_db_path(root, include_process=False) == root / "gaia-data" / "lumen_memory.db"
        (root / ".env").write_text("LUMEN_DATA_DIR=lumen-data\n", encoding="utf-8")
        assert migration.resolve_db_path(root, include_process=False) == root / "lumen-data" / "lumen_memory.db"
        (root / ".env").write_text("GAIA_HOME=gaia-home\n", encoding="utf-8")
        assert migration.resolve_db_path(root, include_process=False) == root / "gaia-home" / "data" / "memory" / "lumen_memory.db"
        (root / ".env").write_text("", encoding="utf-8")
        assert migration.resolve_db_path(root, include_process=False) == root / "lumen-core" / "data" / "lumen_memory.db"
        os.environ["GAIA_MEMORY_DB"] = "/process/overrides.env.db"
        assert migration.resolve_db_path(root, include_process=True) == Path("/process/overrides.env.db")
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

print("MIGRATION ENV RESOLUTION ORDER RC2 TEST OK: GAIA aliases, LUMEN compatibility, data/vault fallbacks and process precedence are deterministic.")
