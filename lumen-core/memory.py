"""Memoria local SQLite: historial, facts explícitos, estado y backups."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta
from config import DB_PATH, BACKUP_DIR, MAX_BACKUPS, BACKUP_INTERVAL_HOURS


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                content TEXT NOT NULL,
                device TEXT DEFAULT 'unknown',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS user_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                fact TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                source TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, fact)
            );
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS lumen_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS proactive_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason TEXT NOT NULL,
                message TEXT NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, id);
            CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_at);
            CREATE INDEX IF NOT EXISTS idx_facts_category ON user_facts(category);
            CREATE INDEX IF NOT EXISTS idx_proactive_pending ON proactive_messages(delivered, id);
        """)


def save_message(session_id: str, role: str, content: str, device: str = "unknown") -> None:
    with get_db() as conn:
        conn.execute("INSERT INTO conversations (session_id, role, content, device) VALUES (?, ?, ?, ?)",
                     (session_id, role, content, device))


def get_conversation_history(session_id: str, limit: int = 50) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content, device, created_at FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_recent_messages(limit: int = 20) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT role, content, device, session_id, created_at FROM conversations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_all_sessions() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT session_id, MIN(created_at) AS started, MAX(created_at) AS last_message,
                   COUNT(*) AS message_count, MAX(device) AS device
            FROM conversations GROUP BY session_id ORDER BY last_message DESC LIMIT 100
        """).fetchall()
    return [dict(r) for r in rows]


def save_fact(category: str, fact: str, source: str = "manual", confidence: float = 1.0) -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT INTO user_facts (category, fact, source, confidence, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(category, fact) DO UPDATE SET
              confidence = MAX(user_facts.confidence, excluded.confidence),
              source = excluded.source,
              updated_at = CURRENT_TIMESTAMP
        """, (category, fact, source, min(max(confidence, 0.0), 1.0)))


def delete_fact(fact_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM user_facts WHERE id = ?", (fact_id,))
        return cur.rowcount > 0


def get_facts(category: str | None = None) -> list[dict]:
    with get_db() as conn:
        if category:
            rows = conn.execute("SELECT id, category, fact, confidence, source, created_at, updated_at FROM user_facts WHERE category = ? ORDER BY updated_at DESC", (category,)).fetchall()
        else:
            rows = conn.execute("SELECT id, category, fact, confidence, source, created_at, updated_at FROM user_facts ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_facts_summary() -> list[str]:
    return [f"[{f['category']}] {f['fact']}" for f in get_facts()[:30]]


def set_preference(key: str, value: str) -> None:
    with get_db() as conn:
        conn.execute("""INSERT INTO user_preferences (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""", (key, value))


def get_preference(key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM user_preferences WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_all_preferences() -> dict:
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM user_preferences").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_state(key: str, value: str) -> None:
    with get_db() as conn:
        conn.execute("""INSERT INTO lumen_state (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""", (key, value))


def get_state(key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM lumen_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def enqueue_proactive_message(reason: str, message: str) -> int:
    with get_db() as conn:
        cur = conn.execute("INSERT INTO proactive_messages (reason, message) VALUES (?, ?)", (reason, message))
        return int(cur.lastrowid)


def pop_proactive_message() -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT id, reason, message, created_at FROM proactive_messages WHERE delivered = 0 ORDER BY id LIMIT 1").fetchone()
        if not row:
            return None
        conn.execute("UPDATE proactive_messages SET delivered = 1, delivered_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
    return dict(row)


def create_backup() -> str:
    """Crea un snapshot consistente incluso con SQLite en modo WAL."""
    init_db()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"lumen_memory_{timestamp}.db"
    with sqlite3.connect(str(DB_PATH)) as source, sqlite3.connect(str(backup_path)) as destination:
        source.backup(destination)
    backups = sorted(BACKUP_DIR.glob("lumen_memory_*.db"), key=lambda p: p.stat().st_mtime)
    while len(backups) > MAX_BACKUPS:
        backups.pop(0).unlink(missing_ok=True)
    set_state("last_backup_time", datetime.now().isoformat())
    set_state("last_backup_path", str(backup_path))
    return str(backup_path)


def backup_due() -> bool:
    last = get_state("last_backup_time")
    if not last:
        return True
    try:
        return datetime.now() - datetime.fromisoformat(last) >= timedelta(hours=BACKUP_INTERVAL_HOURS)
    except ValueError:
        return True


def get_stats() -> dict:
    with get_db() as conn:
        msg_count = conn.execute("SELECT COUNT(*) AS c FROM conversations").fetchone()["c"]
        fact_count = conn.execute("SELECT COUNT(*) AS c FROM user_facts").fetchone()["c"]
        session_count = conn.execute("SELECT COUNT(DISTINCT session_id) AS c FROM conversations").fetchone()["c"]
        first_msg = conn.execute("SELECT MIN(created_at) AS d FROM conversations").fetchone()["d"]
        pending = conn.execute("SELECT COUNT(*) AS c FROM proactive_messages WHERE delivered = 0").fetchone()["c"]
    return {"total_messages": msg_count, "total_facts": fact_count, "total_sessions": session_count,
            "first_interaction": first_msg, "db_size_mb": round(DB_PATH.stat().st_size / (1024 * 1024), 2) if DB_PATH.exists() else 0,
            "pending_proactive": pending, "last_backup_time": get_state("last_backup_time", "")}
