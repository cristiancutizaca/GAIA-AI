from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
import unicodedata
from uuid import uuid4

from memory_privacy import contains_credentials

PRIVACY = {"PUBLIC", "PRIVATE", "SECRET", "DEVICE_SECRET"}
_STOP_WORDS = set("acerca al alguno como con cual cuales cuando de del dice donde el en es esta esto fue hay hoy la las le lo los mas me mensaje mi mis para por que recuerda recuerdas recuerdo recuerdos sabes se si sobre te tengo tu una unos ayer what about remember".split())


def _words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.findall(r"[^\W_]{2,}", normalized)


def _tokens(query: str) -> list[str]:
    return list(dict.fromkeys(word for word in _words(query[:500]) if word not in _STOP_WORDS))[:12]


class MemoryV2Store:
    """Explicit memories, isolated by authenticated owner, device and project."""

    def __init__(self, path: Path, *, legacy_path: Path | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()
        if legacy_path and legacy_path.is_file() and legacy_path.resolve() != self.path.resolve():
            self._import_legacy(legacy_path)

    @contextmanager
    def _connection(self):
        with closing(sqlite3.connect(self.path, timeout=10, uri=True)) as db, db:
            db.row_factory = sqlite3.Row
            yield db

    def initialize(self):
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY, owner_id TEXT, namespace TEXT,
                    session TEXT, device TEXT, project TEXT, kind TEXT, content TEXT,
                    source TEXT, confidence REAL, importance REAL, privacy_level TEXT,
                    created_at TEXT, updated_at TEXT, valid_from TEXT, valid_until TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_memories_scope
                    ON memories(owner_id, namespace, project, updated_at DESC);
                CREATE TABLE IF NOT EXISTS memory_v2_migrations (name TEXT PRIMARY KEY);
            """)
            try:
                db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content, content='memories', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2'
                )""")
                db.execute("SELECT rowid FROM memories_fts LIMIT 0")
            except sqlite3.OperationalError as exc:
                if "no such module" not in str(exc):
                    raise
                db.executescript("""
                    DROP TRIGGER IF EXISTS memories_insert;
                    DROP TRIGGER IF EXISTS memories_delete;
                    DROP TRIGGER IF EXISTS memories_update;
                    DELETE FROM memory_v2_migrations WHERE name='fts5-v1';
                """)
                return
            db.executescript("""
                CREATE TRIGGER IF NOT EXISTS memories_insert AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_delete AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_update AFTER UPDATE OF content ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
                    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
                END;
            """)
            db.execute("BEGIN IMMEDIATE")
            if self._mark_migration(db, "fts5-v1"):
                db.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")

    @staticmethod
    def _mark_migration(db, name):
        return db.execute("INSERT OR IGNORE INTO memory_v2_migrations VALUES (?)", (name,)).rowcount

    def _import_legacy(self, path: Path):
        uri = path.resolve().as_uri() + "?mode=ro"
        with self._connection() as db:
            db.execute("ATTACH DATABASE ? AS legacy", (uri,))
            if not db.execute("SELECT 1 FROM legacy.sqlite_master WHERE name='memories' AND type='table'").fetchone():
                return
            db.execute("BEGIN IMMEDIATE")
            if self._mark_migration(db, "platform-memory-v13"):
                db.execute("""
                    INSERT OR IGNORE INTO main.memories
                    SELECT memory_id, owner_id, namespace, session, device, project, kind, content,
                           source, confidence, importance, privacy_level, created_at, updated_at,
                           valid_from, valid_until
                    FROM legacy.memories
                """)

    @staticmethod
    def _content(content: str) -> str:
        if not content.strip() or len(content) > 20000:
            raise ValueError("El recuerdo debe tener entre 1 y 20000 caracteres.")
        if contains_credentials(content):
            raise ValueError("Este recuerdo contiene posibles credenciales.")
        return content.strip()

    def add(self, content: str, *, owner_id: str, namespace: str = "default", session: str = "",
            device: str = "", project: str = "", kind: str = "semantic", source: str = "user",
            confidence: float = 1.0, importance: float = 0.5, privacy_level: str = "PRIVATE",
            valid_from: str = "", valid_until: str = ""):
        if privacy_level not in PRIVACY or not owner_id:
            raise ValueError("Propietario o nivel de privacidad inválido.")
        content = self._content(content)
        now = datetime.now(timezone.utc).isoformat()
        mid = "mem_" + uuid4().hex[:24]
        with self._connection() as db:
            db.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (mid, owner_id, namespace, session, device, project, kind, content, source,
                        max(0, min(1, confidence)), max(0, min(1, importance)), privacy_level,
                        now, now, valid_from, valid_until))
        return mid

    def search(self, query: str, *, owner_id: str, namespace: str = "default", project: str = "",
               limit: int = 8, include_secrets: bool = False):
        terms = _tokens(query)
        if query.strip() and not terms:
            return []
        now = datetime.now(timezone.utc).isoformat()
        scope = """m.owner_id=? AND m.namespace=? AND m.project=?
                   AND (m.valid_from='' OR m.valid_from<=?)
                   AND (m.valid_until='' OR m.valid_until>?)"""
        if not include_secrets:
            scope += " AND m.privacy_level IN ('PUBLIC', 'PRIVATE')"
        params = (owner_id, namespace, project, now, now)
        limit = max(1, min(50, limit))
        with self._connection() as db:
            if terms:
                expression = " OR ".join(f'"{term}"' for term in terms)
                try:
                    rows = db.execute(f"""
                        SELECT m.* FROM memories_fts JOIN memories m ON m.rowid=memories_fts.rowid
                        WHERE {scope} AND memories_fts MATCH ?
                        ORDER BY rank, m.importance DESC, m.updated_at DESC LIMIT ?
                    """, (*params, expression, limit)).fetchall()
                except sqlite3.OperationalError as exc:
                    if "no such table" not in str(exc) and "no such module" not in str(exc):
                        raise
                    db.create_function("memory_tokens", 1, lambda content: " " + " ".join(_words(content)) + " ")
                    matches = " OR ".join("memory_tokens(m.content) LIKE ?" for _ in terms)
                    rows = db.execute(f"""
                        SELECT m.* FROM memories m WHERE {scope} AND ({matches})
                        ORDER BY m.importance DESC, m.updated_at DESC LIMIT ?
                    """, (*params, *(f"% {term} %" for term in terms), limit)).fetchall()
            else:
                rows = db.execute(f"""
                    SELECT m.* FROM memories m WHERE {scope} ORDER BY m.updated_at DESC LIMIT ?
                """, (*params, limit)).fetchall()
        return [dict(row) for row in rows if include_secrets or not contains_credentials(row["content"])]

    def update(self, memory_id: str, content: str, *, owner_id: str, namespace: str) -> bool:
        content = self._content(content)
        with self._connection() as db:
            return db.execute("""
                UPDATE memories SET content=?, updated_at=?
                WHERE memory_id=? AND owner_id=? AND namespace=?
            """, (content, datetime.now(timezone.utc).isoformat(), memory_id, owner_id, namespace)).rowcount > 0

    def delete(self, memory_id: str, *, owner_id: str, namespace: str | None = None) -> bool:
        with self._connection() as db:
            if namespace is None:
                result = db.execute("DELETE FROM memories WHERE memory_id=? AND owner_id=?", (memory_id, owner_id))
            else:
                result = db.execute("DELETE FROM memories WHERE memory_id=? AND owner_id=? AND namespace=?",
                                    (memory_id, owner_id, namespace))
            return result.rowcount > 0

    def export(self, *, owner_id: str, namespace: str | None = None):
        with self._connection() as db:
            if namespace is None:
                rows = db.execute("SELECT * FROM memories WHERE owner_id=?", (owner_id,))
            else:
                rows = db.execute("SELECT * FROM memories WHERE owner_id=? AND namespace=?", (owner_id, namespace))
            return [dict(row) for row in rows]

    def close(self):
        """Compatibility with older callers. Each operation closes its own connection."""
