from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from config import BACKUP_DIR, BACKUP_INTERVAL_HOURS, DB_PATH, DEVICE_TOKEN_TTL_DAYS, MAX_BACKUPS, MEMORY_RELEVANCE_LIMIT, SESSION_SUMMARY_EVERY_TURNS

SCHEMA_VERSION = 5
FTS5_AVAILABLE = False
_SOURCE_PRIORITY = {"SYSTEM": 0.7, "INFERRED": 0.6, "AUTO_EXTRACT": 0.6, "manual": 1.0, "MANUAL": 1.0, "USER_EXPLICIT": 1.0}
_TOKEN_RE = re.compile(r"[\wáéíóúüñ]{2,}", re.IGNORECASE)
_KNOWN_DEVICE_CAPABILITIES = frozenset({
    "chat", "memory_read", "memory_write", "voice", "diagnostics",
    "actions_request", "actions_execute", "action_host", "backup_create",
    "proactive_read", "proactive_control", "device_self", "device_admin",
    "brain_restore", "admin",
})


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _try_fts(conn: sqlite3.Connection) -> None:
    global FTS5_AVAILABLE
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(category, memory_key, value, source, status, tokenize='unicode61')")
        FTS5_AVAILABLE = True
    except sqlite3.OperationalError:
        FTS5_AVAILABLE = False


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
            CREATE TABLE IF NOT EXISTS action_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                device TEXT NOT NULL DEFAULT 'unknown',
                action_name TEXT NOT NULL,
                risk_level INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 0,
                request_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS session_summaries (
                session_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                topics_json TEXT NOT NULL DEFAULT '[]',
                projects_json TEXT NOT NULL DEFAULT '[]',
                important_decisions_json TEXT NOT NULL DEFAULT '[]',
                open_tasks_json TEXT NOT NULL DEFAULT '[]',
                turn_count INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                capabilities_json TEXT NOT NULL DEFAULT '[]',
                permission_level INTEGER NOT NULL DEFAULT 0,
                revoked INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS device_tokens (
                token_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                expires_at TIMESTAMP,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(device_id) REFERENCES devices(device_id)
            );
            CREATE TABLE IF NOT EXISTS fact_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_id INTEGER,
                category TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                fact TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS open_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                source_session TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS project_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                note_key TEXT NOT NULL,
                note TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'USER_EXPLICIT',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project, note_key)
            );
            CREATE TABLE IF NOT EXISTS work_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                active_project TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'active'
            );
            CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS admin_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                principal_type TEXT NOT NULL,
                device_id TEXT,
                action TEXT NOT NULL,
                target TEXT,
                result TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, id);
            CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_at);
            CREATE INDEX IF NOT EXISTS idx_facts_category ON user_facts(category);
            CREATE INDEX IF NOT EXISTS idx_proactive_pending ON proactive_messages(delivered, id);
            CREATE INDEX IF NOT EXISTS idx_actions_session ON action_history(session_id, id);
            CREATE INDEX IF NOT EXISTS idx_actions_created ON action_history(created_at);
            CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen);
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON open_tasks(status, updated_at);
            CREATE INDEX IF NOT EXISTS idx_project_notes_project ON project_notes(project, updated_at);
            CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON admin_audit(created_at);
        """)
        _ensure_column(conn, "user_facts", "memory_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "user_facts", "updated_at", "TIMESTAMP")
        _ensure_column(conn, "user_facts", "last_used_at", "TIMESTAMP")
        _ensure_column(conn, "user_facts", "pinned", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "user_facts", "status", "TEXT NOT NULL DEFAULT 'active'")
        _ensure_column(conn, "devices", "name", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "devices", "device_type", "TEXT NOT NULL DEFAULT 'unknown'")
        _ensure_column(conn, "action_history", "plan_id", "TEXT")
        _ensure_column(conn, "action_history", "step", "INTEGER")
        _ensure_column(conn, "action_history", "status", "TEXT")
        _ensure_column(conn, "action_history", "duration_ms", "REAL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_key_status ON user_facts(memory_key, status)")
        conn.execute("UPDATE user_facts SET memory_key = lower(category || ':' || fact) WHERE memory_key = '' OR memory_key IS NULL")
        conn.execute("INSERT INTO schema_meta(key, value) VALUES ('schema_version', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))
        _try_fts(conn)
        if FTS5_AVAILABLE:
            conn.execute("DELETE FROM memory_fts")
            for row in conn.execute("SELECT id, category, memory_key, fact, source, status FROM user_facts WHERE status='active'"):
                conn.execute("INSERT INTO memory_fts(rowid, category, memory_key, value, source, status) VALUES (?, ?, ?, ?, ?, ?)", (row["id"], row["category"], row["memory_key"], row["fact"], row["source"], row["status"]))


def schema_version() -> int:
    init_db()
    with get_db() as conn:
        row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    return int(row["value"]) if row else SCHEMA_VERSION


def save_message(session_id: str, role: str, content: str, device: str = "unknown") -> None:
    with get_db() as conn:
        conn.execute("INSERT INTO conversations (session_id, role, content, device) VALUES (?, ?, ?, ?)", (session_id, role, content[:20000], device[:80]))


def get_conversation_history(session_id: str, limit: int = 50) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT role, content, device, created_at FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_recent_messages(limit: int = 20, session_id: str | None = None) -> list[dict]:
    with get_db() as conn:
        if session_id:
            rows = conn.execute("SELECT role, content, device, session_id, created_at FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT role, content, device, session_id, created_at FROM conversations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_all_sessions() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT session_id, MIN(created_at) AS started, MAX(created_at) AS last_message, COUNT(*) AS message_count, MAX(device) AS device FROM conversations GROUP BY session_id ORDER BY last_message DESC LIMIT 100").fetchall()
    return [dict(r) for r in rows]


def _normalize_key(value: str) -> str:
    return re.sub(r"[^\wáéíóúüñ:.-]+", "_", value.strip().lower())[:160]


def save_fact(category: str, fact: str, source: str = "manual", confidence: float = 1.0, key: str | None = None, pinned: bool = False, status: str = "active") -> int:
    init_db()
    category = category.strip()[:80]
    fact = fact.strip()[:1000]
    if not category or not fact:
        raise ValueError("category y fact son obligatorios")
    source = source.strip()[:40] or "manual"
    memory_key = _normalize_key(key or f"{category}:{fact}")
    confidence = min(max(float(confidence), 0.0), 1.0)
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM user_facts WHERE category=? AND memory_key=? AND status='active' ORDER BY id DESC LIMIT 1", (category, memory_key)).fetchone()
        if existing and existing["fact"] != fact:
            conn.execute("UPDATE user_facts SET status='superseded', updated_at=CURRENT_TIMESTAMP WHERE id=?", (existing["id"],))
            conn.execute("INSERT INTO fact_history(fact_id, category, memory_key, fact, confidence, source, status) VALUES (?, ?, ?, ?, ?, ?, 'superseded')", (existing["id"], existing["category"], existing["memory_key"], existing["fact"], existing["confidence"], existing["source"]))
        row = conn.execute("SELECT id FROM user_facts WHERE category=? AND fact=?", (category, fact)).fetchone()
        if row:
            fact_id = int(row["id"])
            conn.execute("UPDATE user_facts SET confidence=MAX(confidence,?), source=?, memory_key=?, pinned=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (confidence, source, memory_key, int(pinned), status, fact_id))
        else:
            cur = conn.execute("INSERT INTO user_facts(category, fact, confidence, source, memory_key, pinned, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (category, fact, confidence, source, memory_key, int(pinned), status))
            fact_id = int(cur.lastrowid)
        if FTS5_AVAILABLE:
            conn.execute("DELETE FROM memory_fts WHERE rowid=?", (fact_id,))
            if status == "active":
                conn.execute("INSERT INTO memory_fts(rowid, category, memory_key, value, source, status) VALUES (?, ?, ?, ?, ?, ?)", (fact_id, category, memory_key, fact, source, status))
    return fact_id


def update_fact(fact_id: int, category: str, fact: str, confidence: float = 1.0, pinned: bool = False) -> bool:
    with get_db() as conn:
        old = conn.execute("SELECT * FROM user_facts WHERE id=?", (fact_id,)).fetchone()
        if not old:
            return False
        conn.execute("INSERT INTO fact_history(fact_id, category, memory_key, fact, confidence, source, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (fact_id, old["category"], old["memory_key"], old["fact"], old["confidence"], old["source"], old["status"]))
        memory_key = _normalize_key(f"{category}:{fact}")
        conn.execute("UPDATE user_facts SET category=?, fact=?, confidence=?, memory_key=?, pinned=?, status='active', updated_at=CURRENT_TIMESTAMP WHERE id=?", (category[:80], fact[:1000], min(max(float(confidence), 0.0), 1.0), memory_key, int(pinned), fact_id))
        if FTS5_AVAILABLE:
            conn.execute("DELETE FROM memory_fts WHERE rowid=?", (fact_id,))
            conn.execute("INSERT INTO memory_fts(rowid, category, memory_key, value, source, status) VALUES (?, ?, ?, ?, ?, 'active')", (fact_id, category[:80], memory_key, fact[:1000], old["source"]))
    return True


def delete_fact(fact_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM user_facts WHERE id = ?", (fact_id,))
        if FTS5_AVAILABLE:
            conn.execute("DELETE FROM memory_fts WHERE rowid=?", (fact_id,))
        return cur.rowcount > 0


def get_facts(category: str | None = None, include_history: bool = False) -> list[dict]:
    with get_db() as conn:
        filters = []
        values: list[Any] = []
        if category:
            filters.append("category=?")
            values.append(category)
        if not include_history:
            filters.append("status='active'")
        clause = " WHERE " + " AND ".join(filters) if filters else ""
        rows = conn.execute(f"SELECT id, category, fact, confidence, source, created_at, updated_at, last_used_at, pinned, status, memory_key FROM user_facts{clause} ORDER BY pinned DESC, updated_at DESC", values).fetchall()
    return [dict(r) for r in rows]


def get_fact_history(fact_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM fact_history WHERE fact_id=? ORDER BY changed_at DESC", (fact_id,)).fetchall()
    return [dict(r) for r in rows]


def search_memories(query: str, category: str | None = None, limit: int = MEMORY_RELEVANCE_LIMIT) -> list[dict]:
    init_db()
    query = query.strip()[:500]
    if not query:
        return get_facts(category)[:limit]
    terms = [term.lower() for term in _TOKEN_RE.findall(query) if term.lower() not in {"gaia", "qué", "que", "era", "estoy", "haciendo", "ahora"}]
    with get_db() as conn:
        rows: list[sqlite3.Row] = []
        if FTS5_AVAILABLE and terms:
            fts_query = " OR ".join(f'"{term.replace(chr(34), "")}"*' for term in terms[:12])
            try:
                if category:
                    rows = conn.execute("SELECT f.* FROM user_facts f JOIN memory_fts m ON m.rowid=f.id WHERE m.memory_fts MATCH ? AND f.category=? AND f.status='active' ORDER BY rank LIMIT ?", (fts_query, category, limit)).fetchall()
                else:
                    rows = conn.execute("SELECT f.* FROM user_facts f JOIN memory_fts m ON m.rowid=f.id WHERE m.memory_fts MATCH ? AND f.status='active' ORDER BY rank LIMIT ?", (fts_query, limit)).fetchall()
            except sqlite3.OperationalError:
                rows = []
        if not rows:
            patterns = [f"%{term}%" for term in terms] or [f"%{query.lower()}%"]
            clauses = ["status='active'"]
            values: list[Any] = []
            if category:
                clauses.append("category=?")
                values.append(category)
            text_clauses = []
            for pattern in patterns[:8]:
                text_clauses.append("(lower(fact) LIKE ? OR lower(memory_key) LIKE ? OR lower(category) LIKE ?)")
                values.extend([pattern, pattern, pattern])
            if text_clauses:
                clauses.append("(" + " OR ".join(text_clauses) + ")")
            rows = conn.execute(f"SELECT * FROM user_facts WHERE {' AND '.join(clauses)} ORDER BY pinned DESC, confidence DESC, updated_at DESC LIMIT ?", (*values, limit)).fetchall()
        result = [dict(row) for row in rows]
        if result:
            conn.executemany("UPDATE user_facts SET last_used_at=CURRENT_TIMESTAMP WHERE id=?", [(item["id"],) for item in result])
    return result


def get_facts_summary() -> list[str]:
    return [f"[{f['category']}] {f['fact']}" for f in get_facts()[:30]]


def set_preference(key: str, value: str) -> None:
    with get_db() as conn:
        conn.execute("INSERT INTO user_preferences (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP", (key, value[:2000]))


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
        conn.execute("INSERT INTO lumen_state (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP", (key, value[:20000]))


def get_state(key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM lumen_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def delete_state(key: str) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM lumen_state WHERE key = ?", (key,))


def save_open_task(task: str, source_session: str = "") -> int:
    text = task.strip()[:500]
    with get_db() as conn:
        row = conn.execute("SELECT id FROM open_tasks WHERE lower(task)=lower(?) AND status='open'", (text,)).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute("INSERT INTO open_tasks(task, source_session) VALUES (?, ?)", (text, source_session[:80]))
        return int(cur.lastrowid)


def get_open_tasks(limit: int = 30) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM open_tasks WHERE status='open' ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def close_open_task(task_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("UPDATE open_tasks SET status='done', updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='open'", (task_id,))
    return cur.rowcount > 0


def save_project_note(project: str, note: str, note_key: str = "general", source: str = "USER_EXPLICIT") -> None:
    with get_db() as conn:
        conn.execute("INSERT INTO project_notes(project, note_key, note, source, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(project, note_key) DO UPDATE SET note=excluded.note, source=excluded.source, updated_at=CURRENT_TIMESTAMP", (project[:120], note_key[:120], note[:1000], source[:40]))


def get_project_notes(project: str, limit: int = 30) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM project_notes WHERE project=? ORDER BY updated_at DESC LIMIT ?", (project, limit)).fetchall()
    return [dict(row) for row in rows]


def set_active_project(project: str, session_id: str = "", device_id: str = "pc") -> None:
    set_state("active_project", project[:120])
    set_state("active_project_session", session_id[:80])
    set_state("active_project_device", device_id[:80])
    with get_db() as conn:
        conn.execute("INSERT INTO work_sessions(session_id, device_id, active_project) VALUES (?, ?, ?)" , (session_id[:80] or "unknown", device_id[:80], project[:120]))


def get_active_project() -> str:
    return get_state("active_project", "")


def get_work_session() -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM work_sessions WHERE status='active' ORDER BY last_active DESC LIMIT 1").fetchone()
    return dict(row) if row else {}


def set_session_summary(session_id: str, summary: str, topics: list[str] | None = None, projects: list[str] | None = None, decisions: list[str] | None = None, open_tasks: list[str] | None = None, turn_count: int = 0) -> None:
    with get_db() as conn:
        conn.execute("INSERT INTO session_summaries(session_id, summary, topics_json, projects_json, important_decisions_json, open_tasks_json, turn_count, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(session_id) DO UPDATE SET summary=excluded.summary, topics_json=excluded.topics_json, projects_json=excluded.projects_json, important_decisions_json=excluded.important_decisions_json, open_tasks_json=excluded.open_tasks_json, turn_count=excluded.turn_count, updated_at=CURRENT_TIMESTAMP", (session_id, summary[:6000], json.dumps(topics or [], ensure_ascii=False), json.dumps(projects or [], ensure_ascii=False), json.dumps(decisions or [], ensure_ascii=False), json.dumps(open_tasks or [], ensure_ascii=False), int(turn_count)))


def get_session_summary_record(session_id: str) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM session_summaries WHERE session_id=?", (session_id,)).fetchone()
    if not row:
        return {}
    item = dict(row)
    for key in ("topics_json", "projects_json", "important_decisions_json", "open_tasks_json"):
        target = key[:-5]
        try:
            item[target] = json.loads(item.pop(key))
        except (ValueError, TypeError):
            item[target] = []
    return item


def get_session_summary(session_id: str) -> str:
    return str(get_session_summary_record(session_id).get("summary", ""))


def _summary_topics(messages: list[dict]) -> tuple[list[str], list[str], list[str], list[str]]:
    text = " ".join(item["content"] for item in messages)
    topics: list[str] = []
    projects: list[str] = []
    decisions: list[str] = []
    tasks: list[str] = []
    if re.search(r"\b(?:program|código|python|backend|frontend|repo|git|proyecto)\b", text, re.I):
        topics.append("programación")
    if re.search(r"\b(?:android|flutter|móvil|mobile)\b", text, re.I):
        topics.append("Android")
    if re.search(r"\b(?:ollama|qwen|modelo|gpu|cpu)\b", text, re.I):
        topics.append("IA local")
    for match in re.findall(r"(?:proyecto|repo(?:sitorio)?)[\s:]+([\w.-]{2,80})", text, re.I):
        projects.append(match)
    for line in text.splitlines():
        clean = line.strip()
        if re.search(r"\b(?:decidí|decidimos|usaremos|vamos a usar|elegí)\b", clean, re.I):
            decisions.append(clean[:220])
        if re.search(r"\b(?:luego|después|pendiente|tenemos que|hay que)\b", clean, re.I):
            tasks.append(clean[:220])
    return list(dict.fromkeys(topics))[:8], list(dict.fromkeys(projects))[:8], list(dict.fromkeys(decisions))[:8], list(dict.fromkeys(tasks))[:8]


def build_session_summary(session_id: str, limit: int = 32) -> str:
    messages = get_conversation_history(session_id, limit=limit)
    if not messages:
        return ""
    topics, projects, decisions, tasks = _summary_topics(messages)
    lines = [f"{item['role']}: {item['content'][:260]}" for item in messages[-12:]]
    summary = "\n".join(lines)
    set_session_summary(session_id, summary, topics, projects, decisions, tasks, turn_count=len(messages) // 2)
    return summary


def maybe_update_session_summary(session_id: str, force: bool = False) -> str:
    record = get_session_summary_record(session_id)
    messages = get_conversation_history(session_id, limit=SESSION_SUMMARY_EVERY_TURNS * 4)
    turn_count = len(messages) // 2
    last_count = int(record.get("turn_count", 0) or 0)
    if force or (turn_count >= 1 and turn_count - last_count >= SESSION_SUMMARY_EVERY_TURNS):
        return build_session_summary(session_id)
    return str(record.get("summary", ""))


def get_context_bundle(session_id: str, user_message: str, recent_limit: int = 10) -> dict:
    summary = maybe_update_session_summary(session_id)
    memories = search_memories(user_message, limit=MEMORY_RELEVANCE_LIMIT)
    active_project = get_active_project()
    project_notes = get_project_notes(active_project) if active_project else []
    work_session = get_work_session()
    tasks = get_open_tasks(12)
    recent_actions = get_action_history(session_id, 8)
    return {"recent_messages": get_conversation_history(session_id, recent_limit), "session_summary": get_session_summary_record(session_id), "relevant_memories": memories, "active_project": active_project, "project_notes": project_notes, "work_session": work_session, "open_tasks": tasks, "recent_actions": recent_actions, "summary_text": summary}


def _normalize_capabilities(capabilities: list[str] | None) -> list[str]:
    return sorted({str(item).strip()[:80] for item in (capabilities or []) if str(item).strip() in _KNOWN_DEVICE_CAPABILITIES})


def register_device(device_id: str, capabilities: list[str] | None = None, permission_level: int = 0, name: str = "", device_type: str = "unknown") -> None:
    """Administrative registration/update; callers must pass a master Principal."""
    safe_id = str(device_id or "").strip()[:80]
    if not safe_id:
        raise ValueError("device_id vacío")
    safe_level = min(2, max(0, int(permission_level)))
    normalized = json.dumps(_normalize_capabilities(capabilities))
    with get_db() as conn:
        conn.execute("INSERT INTO devices(device_id, name, device_type, capabilities_json, permission_level, revoked, last_seen) VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP) ON CONFLICT(device_id) DO UPDATE SET name=excluded.name, device_type=excluded.device_type, capabilities_json=excluded.capabilities_json, permission_level=excluded.permission_level, revoked=0, last_seen=CURRENT_TIMESTAMP", (safe_id, name[:120], device_type[:40], normalized, safe_level))


def update_device_permissions(device_id: str, capabilities: list[str], permission_level: int) -> bool:
    """Explicit administrative metadata change; never used for presence touches."""
    safe_level = min(2, max(0, int(permission_level)))
    with get_db() as conn:
        cur = conn.execute("UPDATE devices SET capabilities_json=?, permission_level=? WHERE device_id=?", (json.dumps(_normalize_capabilities(capabilities)), safe_level, str(device_id)[:80]))
    return cur.rowcount > 0


def touch_device(device_id: str, capabilities: list[str] | None = None) -> None:
    """Update only presence; existing permissions and metadata are immutable here."""
    safe_id = str(device_id or "").strip()[:80]
    if not safe_id:
        return
    with get_db() as conn:
        cur = conn.execute("UPDATE devices SET last_seen=CURRENT_TIMESTAMP WHERE device_id=?", (safe_id,))
        if cur.rowcount == 0:
            conn.execute("INSERT INTO devices(device_id, capabilities_json, permission_level, revoked, last_seen) VALUES (?, '[]', 0, 0, CURRENT_TIMESTAMP)", (safe_id,))


def create_device_token(device_id: str, *, ttl_days: int = DEVICE_TOKEN_TTL_DAYS) -> dict:
    """Create a one-time-visible token; only its SHA-256 digest is stored."""
    safe_device = str(device_id or "").strip()[:80]
    if not safe_device:
        raise ValueError("device_id vacío")
    with get_db() as conn:
        exists = conn.execute("SELECT 1 FROM devices WHERE device_id=?", (safe_device,)).fetchone()
    if not exists:
        register_device(safe_device)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    token_id = secrets.token_hex(12)
    expires_at = datetime.now() + timedelta(days=max(1, int(ttl_days)))
    with get_db() as conn:
        conn.execute("INSERT INTO device_tokens(token_id, device_id, token_hash, expires_at) VALUES (?, ?, ?, ?)", (token_id, safe_device, token_hash, expires_at.isoformat()))
    return {"token_id": token_id, "device_id": safe_device, "token": token, "expires_at": expires_at.isoformat()}


def verify_device_token(token: str) -> dict | None:
    value = str(token or "").strip()
    if not value or len(value) > 200:
        return None
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    with get_db() as conn:
        row = conn.execute("SELECT t.token_id, t.device_id, t.token_hash, t.expires_at, d.permission_level, d.capabilities_json FROM device_tokens t JOIN devices d ON d.device_id=t.device_id WHERE t.token_hash=? AND t.revoked=0 AND d.revoked=0", (digest,)).fetchone()
        if not row or not hmac.compare_digest(str(row["token_hash"]), digest):
            return None
        try:
            expired = bool(row["expires_at"] and datetime.fromisoformat(str(row["expires_at"])) <= datetime.now())
        except ValueError:
            expired = True
        if expired:
            conn.execute("UPDATE device_tokens SET revoked=1 WHERE token_id=?", (row["token_id"],))
            return None
        conn.execute("UPDATE device_tokens SET last_used_at=CURRENT_TIMESTAMP WHERE token_id=?", (row["token_id"],))
        conn.execute("UPDATE devices SET last_seen=CURRENT_TIMESTAMP WHERE device_id=?", (row["device_id"],))
    try:
        capabilities = json.loads(row["capabilities_json"])
    except (TypeError, ValueError):
        capabilities = []
    return {"token_id": row["token_id"], "device_id": row["device_id"], "permission_level": int(row["permission_level"]), "capabilities": capabilities}


def revoke_device_token(token_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute("UPDATE device_tokens SET revoked=1 WHERE token_id=?", (str(token_id)[:80],))
    return cur.rowcount > 0


def get_device_tokens(device_id: str | None = None) -> list[dict]:
    query = "SELECT token_id, device_id, created_at, last_used_at, expires_at, revoked FROM device_tokens"
    params: tuple[Any, ...] = ()
    if device_id:
        query += " WHERE device_id=?"
        params = (device_id,)
    query += " ORDER BY created_at DESC"
    with get_db() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def revoke_device(device_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute("UPDATE devices SET revoked = 1 WHERE device_id = ?", (device_id,))
        conn.execute("UPDATE device_tokens SET revoked=1 WHERE device_id=?", (device_id,))
    return cur.rowcount > 0


def get_devices() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT device_id, name, device_type, capabilities_json, permission_level, revoked, created_at, last_seen FROM devices ORDER BY last_seen DESC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["capabilities"] = json.loads(item.pop("capabilities_json"))
        except (ValueError, TypeError):
            item["capabilities"] = []
        result.append(item)
    return result


def record_admin_audit(principal_type: str, device_id: str | None, action: str, target: str | None, result: str, details: dict | None = None) -> int:
    with get_db() as conn:
        cursor = conn.execute("INSERT INTO admin_audit(principal_type, device_id, action, target, result, details_json) VALUES (?, ?, ?, ?, ?, ?)", (str(principal_type)[:30], str(device_id)[:80] if device_id else None, str(action)[:80], str(target)[:120] if target else None, str(result)[:40], json.dumps(details or {}, ensure_ascii=False)[:4000]))
    return int(cursor.lastrowid)


def get_admin_audit(limit: int = 100) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT id, created_at, principal_type, device_id, action, target, result, details_json FROM admin_audit ORDER BY id DESC LIMIT ?", (max(1, min(500, int(limit))),)).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        try:
            item["details"] = json.loads(item.pop("details_json"))
        except (TypeError, ValueError):
            item["details"] = {}
        output.append(item)
    return output


def save_action(action_id: str, session_id: str, device: str, action: dict, result: dict) -> None:
    """Persist aggregate action and bounded per-step records for plans."""
    with get_db() as conn:
        plan_id = str(action.get("plan_id") or action_id) if action.get("type") == "plan" else None
        conn.execute("INSERT INTO action_history(action_id, session_id, device, action_name, risk_level, success, request_json, result_json, plan_id, step, status, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (action_id, session_id, device, str(action.get("name") or action.get("type") or "unknown"), int(action.get("risk_level", 0)), int(bool(result.get("success"))), json.dumps(action, ensure_ascii=False), json.dumps(result, ensure_ascii=False), plan_id, 0 if plan_id else None, "success" if result.get("success") else ("cancelled" if result.get("cancelled") else "failed"), result.get("duration_ms")))
        if action.get("type") == "plan":
            steps = result.get("data", {}).get("actions", []) if isinstance(result.get("data"), dict) else []
            for index, step_result in enumerate(steps, 1):
                step_action = step_result.get("action") if isinstance(step_result, dict) else "unknown"
                status = "success" if step_result.get("success") else ("cancelled" if step_result.get("cancelled") else "failed")
                step_data = step_result.get("data") if isinstance(step_result.get("data"), dict) else {}
                conn.execute("INSERT INTO action_history(action_id, session_id, device, action_name, risk_level, success, request_json, result_json, plan_id, step, status, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (f"{action_id}:{index}", session_id, device, str(step_action), int(step_result.get("risk_level", action.get("risk_level", 0))), int(bool(step_result.get("success"))), json.dumps({"plan_id": plan_id, "step": index, "action": step_result}, ensure_ascii=False), json.dumps(step_result, ensure_ascii=False), plan_id, index, status, step_result.get("duration_ms", step_data.get("duration_ms"))))


def get_action_history(session_id: str | None = None, limit: int = 50) -> list[dict]:
    with get_db() as conn:
        if session_id:
            rows = conn.execute("SELECT * FROM action_history WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM action_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        for key in ("request_json", "result_json"):
            try:
                item[key[:-5]] = json.loads(item.pop(key))
            except (ValueError, TypeError):
                item[key[:-5]] = {}
        result.append(item)
    return result


def enqueue_proactive_message(reason: str, message: str) -> int:
    with get_db() as conn:
        cur = conn.execute("INSERT INTO proactive_messages(reason, message) VALUES (?, ?)", (reason, message[:4000]))
        return int(cur.lastrowid)


def pop_proactive_message() -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT id, reason, message, created_at FROM proactive_messages WHERE delivered = 0 ORDER BY id LIMIT 1").fetchone()
        if not row:
            return None
        conn.execute("UPDATE proactive_messages SET delivered = 1, delivered_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
    return dict(row)


def create_backup() -> str:
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
    init_db()
    with get_db() as conn:
        msg_count = conn.execute("SELECT COUNT(*) AS c FROM conversations").fetchone()["c"]
        fact_count = conn.execute("SELECT COUNT(*) AS c FROM user_facts WHERE status='active'").fetchone()["c"]
        session_count = conn.execute("SELECT COUNT(DISTINCT session_id) AS c FROM conversations").fetchone()["c"]
        first_msg = conn.execute("SELECT MIN(created_at) AS d FROM conversations").fetchone()["d"]
        pending = conn.execute("SELECT COUNT(*) AS c FROM proactive_messages WHERE delivered = 0").fetchone()["c"]
        action_count = conn.execute("SELECT COUNT(*) AS c FROM action_history").fetchone()["c"]
        task_count = conn.execute("SELECT COUNT(*) AS c FROM open_tasks WHERE status='open'").fetchone()["c"]
    return {"total_messages": msg_count, "total_facts": fact_count, "total_sessions": session_count, "first_interaction": first_msg, "db_size_mb": round(DB_PATH.stat().st_size / (1024 * 1024), 2) if DB_PATH.exists() else 0, "pending_proactive": pending, "total_actions": action_count, "open_tasks": task_count, "schema_version": schema_version(), "fts5": FTS5_AVAILABLE, "last_backup_time": get_state("last_backup_time", "")}
