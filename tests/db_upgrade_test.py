"""Prueba de migración SQLite desde el esquema v4 mínimo al v5."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_upgrade_") as tmp:
    data_dir = Path(tmp)
    db_path = data_dir / "lumen_memory.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, device TEXT NOT NULL DEFAULT 'pc', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE user_facts (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, fact TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 1.0, source TEXT NOT NULL DEFAULT 'manual', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE devices (device_id TEXT PRIMARY KEY, capabilities_json TEXT NOT NULL DEFAULT '[]', permission_level INTEGER NOT NULL DEFAULT 0, revoked INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO user_facts(category, fact, confidence, source) VALUES ('nombre', 'Cris', 1.0, 'manual');
        """)
    os.environ.update({"LUMEN_DATA_DIR": str(data_dir), "GAIA_MEMORY_DB": str(db_path), "LUMEN_LLM_BACKEND": "mock"})
    import memory

    memory.init_db()
    assert memory.schema_version() == 5
    with memory.get_db() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(user_facts)").fetchall()}
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"memory_key", "status", "pinned", "last_used_at"}.issubset(columns)
    assert {"device_tokens", "fact_history", "open_tasks", "project_notes", "work_sessions", "session_summaries"}.issubset(tables)
    facts = memory.get_facts()
    assert facts and facts[0]["fact"] == "Cris"
    assert memory.search_memories("Cris")

print("DB UPGRADE TEST OK: v4 -> v5 conserva datos y crea tablas nuevas.")
