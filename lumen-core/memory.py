from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import BACKUP_DIR, BACKUP_INTERVAL_HOURS, DB_PATH, DEVICE_TOKEN_TTL_DAYS, MAX_BACKUPS, MEMORY_RELEVANCE_LIMIT, SESSION_SUMMARY_EVERY_TURNS

SCHEMA_VERSION = 9


@dataclass(frozen=True)
class MemoryAccessContext:
    """Authenticated memory boundary carried through chat, API and retrieval."""

    principal_id: str = ""
    device_id: str = ""
    session_id: str = ""
    project_id: str = ""
    capabilities: frozenset[str] = frozenset()
    request_id: str = ""
    source_channel: str = "internal"
    is_master: bool = False



def _derive_memory_namespace(kind: str, project: str, session_id: str, device_id: str) -> tuple[str, str]:
    kind = str(kind or "").strip().lower()
    project = str(project or "").strip()
    session_id = str(session_id or "").strip()
    device_id = str(device_id or "").strip()
    if kind == "device_system":
        return "device", f"device:{device_id or 'unknown'}"
    if kind == "working":
        return "working", f"device:{device_id or 'unknown'}/session:{session_id or 'unknown'}"
    if kind in {"session", "task"} and session_id:
        return "session", f"session:{session_id}"
    if kind == "project" or project:
        return "project", f"project:{project or 'unknown'}"
    if device_id:
        return "device", f"device:{device_id}"
    return "global", "global:user"


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


def _migrate_memory_namespace(conn: sqlite3.Connection) -> None:
    """Upgrade schema-8 memory rows without dropping data or history."""
    memory_columns = {row[1] for row in conn.execute("PRAGMA table_info(memory_items)").fetchall()}
    if "namespace_type" not in memory_columns:
        _ensure_column(conn, "memory_items", "namespace_type", "TEXT NOT NULL DEFAULT 'global'")
    if "namespace_id" not in memory_columns:
        _ensure_column(conn, "memory_items", "namespace_id", "TEXT NOT NULL DEFAULT 'global:user'")
    table_sql_row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='memory_items'").fetchone()
    table_sql = str(table_sql_row[0] or "").lower() if table_sql_row else ""
    if "unique(namespace_type" not in table_sql:
        conn.execute("""
            CREATE TABLE memory_items_v091 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL DEFAULT '',
                provenance_type TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.6,
                importance REAL NOT NULL DEFAULT 0.5,
                scope TEXT NOT NULL DEFAULT 'personal',
                project TEXT NOT NULL DEFAULT '',
                session_id TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL DEFAULT '',
                namespace_type TEXT NOT NULL DEFAULT 'global',
                namespace_id TEXT NOT NULL DEFAULT 'global:user',
                user_confirmed INTEGER NOT NULL DEFAULT 0,
                pinned INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                content_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_used_at TIMESTAMP,
                UNIQUE(namespace_type, namespace_id, memory_key, content_hash)
            )
        """)
        conn.execute("""
            INSERT INTO memory_items_v091
            (id, memory_key, kind, category, content, source_type, source_ref, provenance_type,
             confidence, importance, scope, project, session_id, device_id, namespace_type,
             namespace_id, user_confirmed, pinned, status, content_hash, created_at, updated_at,
             expires_at, last_used_at)
            SELECT id, memory_key, kind, category, content, source_type, source_ref, provenance_type,
                   confidence, importance, scope, project, session_id, device_id,
                   CASE WHEN kind='device_system' OR device_id<>'' THEN 'device'
                        WHEN kind='working' THEN 'working'
                        WHEN kind IN ('session','task') AND session_id<>'' THEN 'session'
                        WHEN kind='project' OR project<>'' THEN 'project'
                        ELSE 'global' END,
                   CASE WHEN kind='device_system' OR device_id<>'' THEN 'device:' || COALESCE(NULLIF(device_id,''),'unknown')
                        WHEN kind='working' THEN 'device:' || COALESCE(NULLIF(device_id,''),'unknown') || '/session:' || COALESCE(NULLIF(session_id,''),'unknown')
                        WHEN kind IN ('session','task') AND session_id<>'' THEN 'session:' || session_id
                        WHEN kind='project' OR project<>'' THEN 'project:' || COALESCE(NULLIF(project,''),'unknown')
                        ELSE 'global:user' END,
                   user_confirmed, pinned, status, content_hash, created_at, updated_at,
                   expires_at, last_used_at
            FROM memory_items
        """)
        conn.execute("DROP TABLE memory_items")
        conn.execute("ALTER TABLE memory_items_v091 RENAME TO memory_items")
    for row in conn.execute("SELECT id, kind, project, session_id, device_id FROM memory_items").fetchall():
        namespace_type, namespace_id = _derive_memory_namespace(row[1], row[2], row[3], row[4])
        conn.execute("UPDATE memory_items SET namespace_type=?, namespace_id=? WHERE id=?", (namespace_type, namespace_id, int(row[0])))
    history_columns = {row[1] for row in conn.execute("PRAGMA table_info(memory_item_history)").fetchall()}
    if "namespace_type" not in history_columns:
        _ensure_column(conn, "memory_item_history", "namespace_type", "TEXT NOT NULL DEFAULT 'global'")
    if "namespace_id" not in history_columns:
        _ensure_column(conn, "memory_item_history", "namespace_id", "TEXT NOT NULL DEFAULT 'global:user'")
    conn.execute("""
        UPDATE memory_item_history
        SET namespace_type=COALESCE((SELECT namespace_type FROM memory_items m WHERE m.id=memory_item_history.memory_id), namespace_type),
            namespace_id=COALESCE((SELECT namespace_id FROM memory_items m WHERE m.id=memory_item_history.memory_id), namespace_id)
    """)


def _ensure_session_owner(conn: sqlite3.Connection, session_id: str, device_id: str = "", principal_id: str = "") -> bool:
    session_id = str(session_id or "").strip()[:80]
    device_id = str(device_id or "").strip()[:80]
    principal_id = str(principal_id or "").strip()[:120]
    if not session_id:
        return False
    row = conn.execute("SELECT owner_device_id, owner_principal_id, status FROM session_owners WHERE session_id=?", (session_id,)).fetchone()
    meaningful_device = device_id if device_id not in {"", "unknown"} else ""
    if not row:
        conn.execute("INSERT INTO session_owners(session_id, owner_device_id, owner_principal_id, status) VALUES (?, ?, ?, 'active')", (session_id, meaningful_device, principal_id))
        return True
    if str(row[2]) != "active":
        return False
    owner_device = str(row[0] or "")
    owner_principal = str(row[1] or "")
    if owner_device and meaningful_device and owner_device != meaningful_device:
        return False
    if owner_principal and principal_id and owner_principal != principal_id:
        return False
    if not owner_device and meaningful_device:
        conn.execute("UPDATE session_owners SET owner_device_id=?, updated_at=CURRENT_TIMESTAMP WHERE session_id=?", (meaningful_device, session_id))
    if not owner_principal and principal_id:
        conn.execute("UPDATE session_owners SET owner_principal_id=?, updated_at=CURRENT_TIMESTAMP WHERE session_id=?", (principal_id, session_id))
    return True


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
            CREATE TABLE IF NOT EXISTS session_owners (
                session_id TEXT PRIMARY KEY,
                owner_device_id TEXT NOT NULL DEFAULT '',
                owner_principal_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','quarantined')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
            CREATE TABLE IF NOT EXISTS permission_grants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                principal_type TEXT NOT NULL,
                principal_id TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL DEFAULT '',
                capability TEXT NOT NULL,
                resource_scope TEXT NOT NULL DEFAULT '',
                decision TEXT NOT NULL CHECK(decision IN ('ALLOW_ONCE','ALWAYS_ALLOW','ASK','ALWAYS_ASK','DENY','ALWAYS_DENY')),
                risk_level_at_grant INTEGER NOT NULL DEFAULT 0,
                capability_version TEXT NOT NULL DEFAULT '1',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                expires_at TIMESTAMP,
                UNIQUE(principal_type, principal_id, device_id, capability, resource_scope)
            );
            CREATE TABLE IF NOT EXISTS automation_rules (
                rule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_device TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                trigger_json TEXT NOT NULL DEFAULT '{}',
                conditions_json TEXT NOT NULL DEFAULT '[]',
                routine_id TEXT,
                steps_json TEXT NOT NULL DEFAULT '[]',
                cooldown_seconds INTEGER NOT NULL DEFAULT 300,
                quiet_hour_policy TEXT NOT NULL DEFAULT 'skip',
                run_limit INTEGER NOT NULL DEFAULT 0,
                run_count INTEGER NOT NULL DEFAULT 0,
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS routines (
                routine_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_device TEXT NOT NULL,
                steps_json TEXT NOT NULL DEFAULT '[]',
                required_capabilities_json TEXT NOT NULL DEFAULT '[]',
                max_risk INTEGER NOT NULL DEFAULT 0,
                failure_policy TEXT NOT NULL DEFAULT 'stop',
                enabled INTEGER NOT NULL DEFAULT 0,
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_device TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'UTC',
                spec_json TEXT NOT NULL DEFAULT '{}',
                missed_policy TEXT NOT NULL DEFAULT 'SKIP',
                routine_id TEXT,
                rule_id TEXT,
                enabled INTEGER NOT NULL DEFAULT 0,
                next_due_at TIMESTAMP,
                last_due_at TIMESTAMP,
                run_count INTEGER NOT NULL DEFAULT 0,
                max_runs_per_day INTEGER NOT NULL DEFAULT 10,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS automation_runs (
                run_id TEXT PRIMARY KEY,
                rule_id TEXT,
                schedule_id TEXT,
                routine_id TEXT,
                event_id TEXT,
                dedup_key TEXT NOT NULL DEFAULT '',
                chain_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                result_json TEXT NOT NULL DEFAULT '{}',
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                source TEXT NOT NULL DEFAULT 'automation',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                device_scope TEXT NOT NULL DEFAULT '',
                read INTEGER NOT NULL DEFAULT 0,
                dismissed INTEGER NOT NULL DEFAULT 0,
                sensitive INTEGER NOT NULL DEFAULT 0,
                expires_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS automation_event_log (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL DEFAULT '',
                host TEXT NOT NULL DEFAULT '',
                device TEXT NOT NULL DEFAULT '',
                timestamp TIMESTAMP NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                severity TEXT NOT NULL DEFAULT 'info',
                dedup_key TEXT NOT NULL DEFAULT '',
                chain_id TEXT NOT NULL DEFAULT '',
                chain_depth INTEGER NOT NULL DEFAULT 0,
                expires_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL DEFAULT '',
                provenance_type TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.6,
                importance REAL NOT NULL DEFAULT 0.5,
                scope TEXT NOT NULL DEFAULT 'personal',
                project TEXT NOT NULL DEFAULT '',
                session_id TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL DEFAULT '',
                namespace_type TEXT NOT NULL DEFAULT 'global',
                namespace_id TEXT NOT NULL DEFAULT 'global:user',
                user_confirmed INTEGER NOT NULL DEFAULT 0,
                pinned INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                content_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_used_at TIMESTAMP,
                UNIQUE(namespace_type, namespace_id, memory_key, content_hash)
            );
            CREATE TABLE IF NOT EXISTS memory_item_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER,
                memory_key TEXT NOT NULL,
                content TEXT NOT NULL,
                source_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                importance REAL NOT NULL,
                scope TEXT NOT NULL,
                project TEXT NOT NULL DEFAULT '',
                namespace_type TEXT NOT NULL DEFAULT 'global',
                namespace_id TEXT NOT NULL DEFAULT 'global:user',
                status TEXT NOT NULL,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                change_reason TEXT NOT NULL DEFAULT 'update'
            );
            CREATE INDEX IF NOT EXISTS idx_automation_rules_enabled ON automation_rules(enabled, owner_device);
            CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules(enabled, next_due_at);
            CREATE INDEX IF NOT EXISTS idx_automation_runs_dedup ON automation_runs(dedup_key, created_at);
            CREATE INDEX IF NOT EXISTS idx_notifications_pending ON notifications(device_scope, dismissed, read, timestamp);
            CREATE INDEX IF NOT EXISTS idx_event_log_created ON automation_event_log(timestamp);
            CREATE INDEX IF NOT EXISTS idx_memory_items_active ON memory_items(namespace_type, namespace_id, status, scope, project, updated_at);
            CREATE INDEX IF NOT EXISTS idx_memory_items_key ON memory_items(namespace_type, namespace_id, memory_key, status);
            CREATE INDEX IF NOT EXISTS idx_memory_items_expiry ON memory_items(status, expires_at);
            CREATE INDEX IF NOT EXISTS idx_memory_history_key ON memory_item_history(memory_key, changed_at);
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
            CREATE INDEX IF NOT EXISTS idx_permissions_lookup ON permission_grants(principal_type, principal_id, device_id, capability, resource_scope);
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
        _migrate_memory_namespace(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_key_status ON user_facts(memory_key, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_items_namespace ON memory_items(namespace_type, namespace_id, memory_key, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_owners_device ON session_owners(owner_device_id, status)")
        conn.execute("UPDATE user_facts SET memory_key = lower(category || ':' || fact) WHERE memory_key = '' OR memory_key IS NULL")
        _migrate_session_owners(conn)
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


def _migrate_session_owners(conn: sqlite3.Connection) -> None:
    """Infer one owner only when legacy conversation data is unambiguous."""
    rows = conn.execute("SELECT session_id, GROUP_CONCAT(DISTINCT device) AS devices FROM conversations GROUP BY session_id").fetchall()
    for row in rows:
        session_id = str(row[0] or "").strip()[:80]
        devices = {part.strip() for part in str(row[1] or "").split(",") if part.strip() and part.strip() != "unknown"}
        owner_device = next(iter(devices)) if len(devices) == 1 else ""
        status = "active" if len(devices) <= 1 else "quarantined"
        conn.execute("INSERT OR IGNORE INTO session_owners(session_id, owner_device_id, owner_principal_id, status) VALUES (?, ?, '', ?)", (session_id, owner_device, status))


def claim_session(session_id: str, *, device_id: str = "", principal_id: str = "", is_master: bool = False) -> bool:
    init_db()
    with get_db() as conn:
        return bool(is_master or _ensure_session_owner(conn, session_id, device_id, principal_id))


def get_session_owner(session_id: str) -> dict[str, Any]:
    init_db()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM session_owners WHERE session_id=?", (str(session_id or "").strip()[:80],)).fetchone()
    return dict(row) if row else {}


def session_access_allowed(session_id: str, *, device_id: str = "", principal_id: str = "", is_master: bool = False) -> bool:
    if is_master:
        return True
    owner = get_session_owner(session_id)
    if not owner or owner.get("status") != "active":
        return False
    owner_device = str(owner.get("owner_device_id") or "")
    owner_principal = str(owner.get("owner_principal_id") or "")
    return bool(owner_device and str(device_id or "") == owner_device and (not owner_principal or owner_principal == str(principal_id or "")))


def save_message(session_id: str, role: str, content: str, device: str = "unknown", principal_id: str = "", is_master: bool = False) -> None:
    init_db()
    with get_db() as conn:
        if not is_master and not _ensure_session_owner(conn, session_id, device, principal_id):
            raise PermissionError("La sesión pertenece a otro dispositivo o está en cuarentena.")
        if is_master:
            _ensure_session_owner(conn, session_id, device, principal_id)
        conn.execute("INSERT INTO conversations (session_id, role, content, device) VALUES (?, ?, ?, ?)", (session_id, role, content[:20000], device[:80]))


def save_verified_owner_message(session_id: str, content: str, owner_device: str) -> None:
    """Record a verified system result under the already established session owner."""
    init_db()
    with get_db() as conn:
        row = conn.execute("SELECT owner_device_id, status FROM session_owners WHERE session_id=?", (session_id,)).fetchone()
        if not row or row[1] != "active" or str(row[0] or "") != str(owner_device or ""):
            raise PermissionError("No existe ownership verificable para la sesión.")
        conn.execute("INSERT INTO conversations (session_id, role, content, device) VALUES (?, 'assistant', ?, ?)", (session_id, content[:20000], str(owner_device)[:80]))


def get_conversation_history(session_id: str, limit: int = 50, access_context: MemoryAccessContext | None = None) -> list[dict]:
    if access_context and not session_access_allowed(session_id, device_id=access_context.device_id, principal_id=access_context.principal_id, is_master=access_context.is_master):
        raise PermissionError("La sesión no pertenece al Principal autenticado.")
    with get_db() as conn:
        rows = conn.execute("SELECT role, content, device, created_at FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_recent_messages(limit: int = 20, session_id: str | None = None, access_context: MemoryAccessContext | None = None) -> list[dict]:
    if access_context and session_id and not session_access_allowed(session_id, device_id=access_context.device_id, principal_id=access_context.principal_id, is_master=access_context.is_master):
        raise PermissionError("La sesión no pertenece al Principal autenticado.")
    with get_db() as conn:
        if session_id:
            rows = conn.execute("SELECT role, content, device, session_id, created_at FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
        elif access_context and not access_context.is_master:
            rows = conn.execute("SELECT role, content, device, session_id, created_at FROM conversations WHERE device=? ORDER BY id DESC LIMIT ?", (access_context.device_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT role, content, device, session_id, created_at FROM conversations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_all_sessions(access_context: MemoryAccessContext | None = None) -> list[dict]:
    with get_db() as conn:
        if access_context and not access_context.is_master:
            rows = conn.execute("SELECT session_id, MIN(created_at) AS started, MAX(created_at) AS last_message, COUNT(*) AS message_count, MAX(device) AS device FROM conversations WHERE device=? GROUP BY session_id ORDER BY last_message DESC LIMIT 100", (access_context.device_id,)).fetchall()
        else:
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


def set_session_summary(session_id: str, summary: str, topics: list[str] | None = None, projects: list[str] | None = None, decisions: list[str] | None = None, open_tasks: list[str] | None = None, turn_count: int = 0, access_context: MemoryAccessContext | None = None) -> None:
    if access_context and not session_access_allowed(session_id, device_id=access_context.device_id, principal_id=access_context.principal_id, is_master=access_context.is_master):
        raise PermissionError("La sesión no pertenece al Principal autenticado.")
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


def build_session_summary(session_id: str, limit: int = 32, access_context: MemoryAccessContext | None = None) -> str:
    messages = get_conversation_history(session_id, limit=limit, access_context=access_context)
    if not messages:
        return ""
    topics, projects, decisions, tasks = _summary_topics(messages)
    lines = [f"{item['role']}: {item['content'][:260]}" for item in messages[-12:]]
    summary = "\n".join(lines)
    set_session_summary(session_id, summary, topics, projects, decisions, tasks, turn_count=len(messages) // 2, access_context=access_context)
    return summary


def maybe_update_session_summary(session_id: str, force: bool = False, access_context: MemoryAccessContext | None = None) -> str:
    if access_context and not session_access_allowed(session_id, device_id=access_context.device_id, principal_id=access_context.principal_id, is_master=access_context.is_master):
        raise PermissionError("La sesión no pertenece al Principal autenticado.")
    record = get_session_summary_record(session_id)
    messages = get_conversation_history(session_id, limit=SESSION_SUMMARY_EVERY_TURNS * 4, access_context=access_context)
    turn_count = len(messages) // 2
    last_count = int(record.get("turn_count", 0) or 0)
    if force or (turn_count >= 1 and turn_count - last_count >= SESSION_SUMMARY_EVERY_TURNS):
        return build_session_summary(session_id, access_context=access_context)
    return str(record.get("summary", ""))


def get_context_bundle(session_id: str, user_message: str, recent_limit: int = 10, access_context: MemoryAccessContext | None = None) -> dict:
    if access_context and not session_access_allowed(session_id, device_id=access_context.device_id, principal_id=access_context.principal_id, is_master=access_context.is_master):
        raise PermissionError("La sesión no pertenece al Principal autenticado.")
    summary = maybe_update_session_summary(session_id, access_context=access_context)
    memories = search_memories(user_message, limit=MEMORY_RELEVANCE_LIMIT)
    active_project = get_active_project()
    project_notes = get_project_notes(active_project) if active_project else []
    advanced: dict[str, Any] = {"items": [], "context_text": "", "truncated": False, "retrieval_ms": 0}
    try:
        from advanced_memory import retrieve
        advanced = retrieve(user_message, project=active_project or None, session_id=session_id, device_id=access_context.device_id if access_context and not access_context.is_master else None, include_all_devices=bool(access_context and access_context.is_master), limit=MEMORY_RELEVANCE_LIMIT, max_chars=4000)
    except (ImportError, OSError, ValueError):
        # Advanced memory is an additive layer; legacy facts remain available.
        advanced = {"items": [], "context_text": "", "truncated": False, "retrieval_ms": 0}
    work_session = get_work_session()
    tasks = get_open_tasks(12)
    recent_actions = get_action_history(session_id, 8)
    return {"recent_messages": get_conversation_history(session_id, recent_limit, access_context=access_context), "session_summary": get_session_summary_record(session_id), "relevant_memories": memories, "advanced_memories": advanced.get("items", []), "advanced_memory_text": str(advanced.get("context_text", ""))[:4000], "advanced_memory_truncated": bool(advanced.get("truncated")), "summary_text": summary, "active_project": active_project, "project_notes": project_notes, "work_session": work_session, "open_tasks": tasks, "recent_actions": recent_actions}


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


def rotate_device_token(device_id: str, *, ttl_days: int = DEVICE_TOKEN_TTL_DAYS) -> dict:
    """Rotate all active device tokens atomically; return the new secret once."""
    safe_device = str(device_id or "").strip()[:80]
    if not safe_device:
        raise ValueError("device_id vacío")
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    token_id = secrets.token_hex(12)
    expires_at = datetime.now() + timedelta(days=max(1, int(ttl_days)))
    with get_db() as conn:
        device = conn.execute("SELECT device_id, revoked FROM devices WHERE device_id=?", (safe_device,)).fetchone()
        if not device or int(device["revoked"]):
            raise ValueError("Dispositivo inexistente o revocado.")
        conn.execute("UPDATE device_tokens SET revoked=1 WHERE device_id=? AND revoked=0", (safe_device,))
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
        aggregate_status = str(result.get("status") or ("SUCCESS" if result.get("success") else ("CANCELLED" if result.get("cancelled") else "FAILED"))).lower()
        conn.execute("INSERT INTO action_history(action_id, session_id, device, action_name, risk_level, success, request_json, result_json, plan_id, step, status, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (action_id, session_id, device, str(action.get("name") or action.get("type") or "unknown"), int(action.get("risk_level", 0)), int(bool(result.get("success"))), json.dumps(action, ensure_ascii=False), json.dumps(result, ensure_ascii=False), plan_id, 0 if plan_id else None, aggregate_status, result.get("duration_ms")))
        if action.get("type") == "plan":
            steps = result.get("data", {}).get("actions", []) if isinstance(result.get("data"), dict) else []
            for index, step_result in enumerate(steps, 1):
                step_action = step_result.get("action") if isinstance(step_result, dict) else "unknown"
                status = str(step_result.get("status") or ("SUCCESS" if step_result.get("success") else ("CANCELLED" if step_result.get("cancelled") else "FAILED"))).lower()
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


_PERMISSION_DECISIONS = frozenset({"ALLOW_ONCE", "ALWAYS_ALLOW", "ASK", "ALWAYS_ASK", "DENY", "ALWAYS_DENY"})


def default_permission_decision(risk_level: int, device_id: str = "pc-main") -> str:
    """Personal pc-main auto-runs read/trivial work; other devices stay conservative."""
    risk = int(risk_level)
    if risk <= 1 and str(device_id) == "pc-main":
        return "AUTO"
    if risk <= 1:
        return "ASK"
    if risk == 2:
        return "ASK"
    return "ALWAYS_ASK"


def save_permission_grant(
    *,
    principal_type: str,
    principal_id: str = "",
    device_id: str = "",
    capability: str,
    resource_scope: str = "",
    decision: str,
    risk_level: int,
    capability_version: str = "1",
    expires_at: str | None = None,
) -> int:
    """Persist a scoped permission decision; no token or secret is stored."""
    init_db()
    decision = str(decision).strip().upper()
    if decision not in _PERMISSION_DECISIONS:
        raise ValueError("Decisión de permiso inválida.")
    clean_scope = str(resource_scope or "").strip()[:500]
    if decision in {"ALWAYS_ALLOW", "ALWAYS_DENY"} and (not clean_scope or clean_scope == "*" or "unresolved" in clean_scope.casefold()):
        raise ValueError("Los grants persistentes requieren un resource_scope explícito y resuelto.")
    resource_scope = clean_scope
    risk_level = int(risk_level)
    if risk_level not in range(5):
        raise ValueError("risk_level debe estar entre 0 y 4.")
    fields = (str(principal_type)[:40], str(principal_id)[:120], str(device_id)[:120], str(capability)[:160], str(resource_scope)[:500], decision, risk_level, str(capability_version)[:40], expires_at)
    with get_db() as conn:
        row = conn.execute("""
            INSERT INTO permission_grants(principal_type, principal_id, device_id, capability, resource_scope, decision, risk_level_at_grant, capability_version, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(principal_type, principal_id, device_id, capability, resource_scope)
            DO UPDATE SET decision=excluded.decision, risk_level_at_grant=excluded.risk_level_at_grant, capability_version=excluded.capability_version, updated_at=CURRENT_TIMESTAMP, expires_at=excluded.expires_at
            RETURNING id
        """, fields).fetchone()
    return int(row["id"])


def _permission_row(*, principal_type: str, principal_id: str, device_id: str, capability: str, resource_scope: str) -> sqlite3.Row | None:
    init_db()
    with get_db() as conn:
        return conn.execute("""
            SELECT * FROM permission_grants
            WHERE principal_type=? AND principal_id=? AND device_id=? AND capability=? AND resource_scope=?
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            ORDER BY id DESC LIMIT 1
        """, (principal_type, principal_id, device_id, capability, resource_scope)).fetchone()


def _permission_rows(*, principal_type: str, principal_id: str, device_id: str, capability: str, resource_scope: str) -> list[sqlite3.Row]:
    init_db()
    with get_db() as conn:
        return conn.execute("""
            SELECT *, CASE WHEN resource_scope=? THEN 2 WHEN resource_scope='*' THEN 1 ELSE 0 END AS scope_specificity
            FROM permission_grants
            WHERE principal_type=? AND principal_id=? AND device_id=? AND capability=?
              AND resource_scope IN (?, '*')
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            ORDER BY scope_specificity DESC, updated_at DESC, id DESC
        """, (resource_scope, principal_type, principal_id, device_id, capability, resource_scope)).fetchall()


def resolve_permission(
    *,
    principal_type: str,
    principal_id: str = "",
    device_id: str = "",
    capability: str,
    resource_scope: str = "",
    current_risk_level: int,
    capability_version: str = "1",
    include_default: bool = False,
) -> dict | None:
    """Resolve most-specific scope and invalidate grants that would under-ask after risk increases."""
    rows = _permission_rows(principal_type=principal_type, principal_id=principal_id, device_id=device_id, capability=capability, resource_scope=resource_scope)
    row = rows[0] if rows else None
    if not row:
        if not include_default:
            return None
        decision = default_permission_decision(current_risk_level, device_id)
        return {
            "id": None,
            "principal_type": str(principal_type),
            "principal_id": str(principal_id),
            "device_id": str(device_id),
            "capability": str(capability),
            "resource_scope": str(resource_scope),
            "decision": decision,
            "effective_decision": decision,
            "risk_level_at_grant": int(current_risk_level),
            "capability_version": str(capability_version),
            "risk_escalated": False,
            "version_changed": False,
            "source": "default_policy",
            "scope_specificity": 0,
        }
    data = dict(row)
    data["risk_escalated"] = int(current_risk_level) > int(row["risk_level_at_grant"])
    data["version_changed"] = str(capability_version) != str(row["capability_version"])
    if data["risk_escalated"] or data["version_changed"]:
        data["effective_decision"] = "ALWAYS_ASK" if row["decision"] in {"ALWAYS_ALLOW", "ALLOW_ONCE"} else row["decision"]
    else:
        data["effective_decision"] = row["decision"]
    return data


def mark_permission_used(permission_id: int) -> None:
    init_db()
    with get_db() as conn:
        row = conn.execute("SELECT decision FROM permission_grants WHERE id=?", (int(permission_id),)).fetchone()
        if not row:
            return
        if row["decision"] == "ALLOW_ONCE":
            conn.execute("DELETE FROM permission_grants WHERE id=?", (int(permission_id),))
        else:
            conn.execute("UPDATE permission_grants SET last_used_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(permission_id),))


def revoke_permission(*, principal_type: str, principal_id: str = "", device_id: str = "", capability: str, resource_scope: str = "") -> int:
    init_db()
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM permission_grants WHERE principal_type=? AND principal_id=? AND device_id=? AND capability=? AND resource_scope=?", (principal_type, principal_id, device_id, capability, resource_scope))
    return int(cursor.rowcount)


def list_permissions(*, principal_type: str | None = None, principal_id: str | None = None, device_id: str | None = None) -> list[dict]:
    init_db()
    clauses: list[str] = []
    values: list[str] = []
    for column, value in (("principal_type", principal_type), ("principal_id", principal_id), ("device_id", device_id)):
        if value is not None:
            clauses.append(f"{column}=?")
            values.append(str(value))
    query = "SELECT * FROM permission_grants" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY updated_at DESC, id DESC"
    with get_db() as conn:
        return [dict(row) for row in conn.execute(query, values).fetchall()]



def list_states(prefix: str = "") -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT key, value, updated_at FROM lumen_state WHERE key LIKE ? ORDER BY updated_at DESC", (str(prefix) + "%",)).fetchall()
    return [dict(row) for row in rows]


def delete_states_prefix(prefix: str) -> int:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM lumen_state WHERE key LIKE ?", (str(prefix) + "%",))
    return int(cursor.rowcount)
