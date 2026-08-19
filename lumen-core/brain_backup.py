"""Portable, non-destructive GAIA Brain Backup and vault migration utilities."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import zipfile

import memory
from config import ASSISTANT_NAME, BACKUP_DIR, BRAIN_MAX_BACKUPS, DATA_DIR, DB_PATH, ENVIRONMENT, GAIA_VAULT, VERSION, VAULT_CONFIG_DIR, VAULT_LOG_DIR, VAULT_STATUS

SCHEMA_VERSION = 2
MANIFEST_NAME = "manifest.json"
# Esta allowlist es la fuente única del payload portable. Nunca se enumera root.iterdir().
BRAIN_BACKUP_FILES = (
    "memory.db",
    "memory_export.json",
    "profile.json",
    "preferences.json",
    "state.json",
    "personality.py",
    "config.json",
)
_SQLITE_SIDECARS = {"memory.db-wal", "memory.db-shm", "memory.db-journal"}
_BACKUP_LOCK = threading.Lock()


def vault_status() -> dict:
    root = str(GAIA_VAULT) if GAIA_VAULT else ""
    return {"status": VAULT_STATUS, "root": root, "data_dir": str(DATA_DIR), "backup_dir": str(BACKUP_DIR), "fallback_warning": "GAIA_VAULT no está configurado; se usa almacenamiento local de fallback." if not GAIA_VAULT else ""}


def _integrity_check(path: Path) -> str:
    try:
        with sqlite3.connect(str(path), timeout=15) as conn:
            conn.execute("PRAGMA busy_timeout=15000")
            row = conn.execute("PRAGMA integrity_check").fetchone()
        return str(row[0]) if row else "unknown"
    except sqlite3.DatabaseError as exc:
        return f"corrupt: {exc}"


def _copy_sqlite(source: Path, destination: Path) -> None:
    """Create a self-contained DELETE-journal snapshot without touching the active DB."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(source), timeout=15) as source_conn, sqlite3.connect(str(destination), timeout=15) as destination_conn:
        source_conn.execute("PRAGMA busy_timeout=15000")
        destination_conn.execute("PRAGMA busy_timeout=15000")
        # This applies only to the new snapshot, never to the active database.
        destination_conn.execute("PRAGMA journal_mode=DELETE")
        destination_conn.execute("PRAGMA synchronous=FULL")
        source_conn.backup(destination_conn)
        destination_conn.commit()
        destination_conn.execute("PRAGMA journal_mode=DELETE")
        destination_conn.commit()


def _stabilize_active_database() -> None:
    """Checkpoint active WAL and remove only closed sidecars before replacement."""
    if not DB_PATH.exists():
        return
    with sqlite3.connect(str(DB_PATH), timeout=15) as conn:
        conn.execute("PRAGMA busy_timeout=15000")
        result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if result and int(result[2]) != 0:
            raise RuntimeError(f"No se pudo estabilizar el WAL activo antes de restore: {result}")
    for suffix in ("-wal", "-shm", "-journal"):
        DB_PATH.with_name(DB_PATH.name + suffix).unlink(missing_ok=True)


def migrate_database(source: Path, destination: Path, dry_run: bool = False) -> dict:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.exists():
        raise RuntimeError(f"La base de origen no existe: {source}")
    integrity = _integrity_check(source)
    if integrity != "ok":
        raise RuntimeError(f"La base de origen no supera integrity_check: {integrity}")
    result = {"source": str(source), "destination": str(destination), "source_integrity": integrity, "dry_run": dry_run}
    if dry_run:
        result["would_copy"] = True
        return result
    if destination.exists():
        raise RuntimeError(f"No sobrescribo una base existente: {destination}")
    _copy_sqlite(source, destination)
    destination_integrity = _integrity_check(destination)
    if destination_integrity != "ok":
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"La base migrada no supera integrity_check: {destination_integrity}")
    result["destination_integrity"] = destination_integrity
    return result


def create_brain_backup(output_dir: Path | None = None) -> str:
    """Create and verify a deterministic portable Brain Backup.

    The lock serializes nearby calls, the manifest is computed from the explicit
    payload allowlist, and the resulting archive is reopened and checked before
    this function reports success.
    """
    with _BACKUP_LOCK:
        return _create_brain_backup_locked(output_dir)


def _create_brain_backup_locked(output_dir: Path | None = None) -> str:
    memory.init_db()
    output_dir = (output_dir or BACKUP_DIR).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    archive = output_dir / f"gaia_brain_{timestamp}.zip"
    try:
        with tempfile.TemporaryDirectory(prefix="gaia_brain_") as temp:
            root = Path(temp)
            snapshot = root / "memory.db"
            _copy_sqlite(DB_PATH, snapshot)
            _assert_no_sqlite_sidecars(root)
            if _integrity_check(snapshot) != "ok":
                raise RuntimeError("El snapshot de memoria no supera integrity_check.")
            _write_json(root / "memory_export.json", {"conversations": memory.get_recent_messages(500), "facts": memory.get_facts()})
            _write_json(root / "profile.json", _safe_profile())
            _write_json(root / "preferences.json", memory.get_all_preferences())
            _write_json(root / "state.json", _safe_state())
            personality = Path(__file__).with_name("personality.py")
            (root / "personality.py").write_text(personality.read_text(encoding="utf-8"), encoding="utf-8")
            _write_json(root / "config.json", {"assistant_name": ASSISTANT_NAME, "version": VERSION, "environment": ENVIRONMENT, "vault_status": VAULT_STATUS, "schema_version": SCHEMA_VERSION})
            _assert_payload_files(root)
            files = {name: _sha256(root / name) for name in BRAIN_BACKUP_FILES}
            manifest = {"format": "GAIA Brain Backup", "schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "assistant_name": ASSISTANT_NAME, "version": VERSION, "files": files, "contains_secrets": False}
            _write_json(root / MANIFEST_NAME, manifest)
            _assert_no_sqlite_sidecars(root)
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for name in (*BRAIN_BACKUP_FILES, MANIFEST_NAME):
                    bundle.write(root / name, name)
        _verify_backup_archive(archive)
    except Exception:
        archive.unlink(missing_ok=True)
        raise
    prune_brain_backups(output_dir, protect=archive)
    memory.set_state("last_brain_backup_at", datetime.now().isoformat())
    memory.set_state("last_brain_backup_path", str(archive))
    return str(archive)


def _assert_no_sqlite_sidecars(root: Path) -> None:
    sidecars = sorted(path.name for path in root.iterdir() if path.name in _SQLITE_SIDECARS or path.name.endswith(("-wal", "-shm", "-journal")))
    if sidecars:
        raise RuntimeError(f"El staging de Brain Backup contiene sidecars SQLite prohibidos: {sidecars}")


def _assert_payload_files(root: Path) -> None:
    _assert_no_sqlite_sidecars(root)
    missing = [name for name in BRAIN_BACKUP_FILES if not (root / name).is_file()]
    if missing:
        raise RuntimeError(f"Faltan archivos del payload canónico: {missing}")


def _verify_backup_archive(archive: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("El Brain Backup generado contiene nombres duplicados.")
        expected_names = set(BRAIN_BACKUP_FILES) | {MANIFEST_NAME}
        if set(names) != expected_names:
            extras = sorted(set(names) - expected_names)
            missing = sorted(expected_names - set(names))
            raise RuntimeError(f"Contenido del Brain Backup generado no coincide; extras={extras}, faltantes={missing}.")
        if any(name.endswith(("-wal", "-shm", "-journal")) for name in names):
            raise RuntimeError("El Brain Backup generado contiene un sidecar SQLite prohibido.")
        try:
            manifest = json.loads(bundle.read(MANIFEST_NAME).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("El manifest generado no es JSON válido.") from exc
        declared = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(declared, dict) or set(declared) != set(BRAIN_BACKUP_FILES):
            raise RuntimeError("El manifest generado no declara exactamente el payload canónico.")
        with tempfile.TemporaryDirectory(prefix="gaia_backup_verify_") as temp:
            root = Path(temp)
            for name in BRAIN_BACKUP_FILES:
                target = root / name
                target.write_bytes(bundle.read(name))
                if _sha256(target).lower() != str(declared[name]).lower():
                    raise RuntimeError(f"IntegrityError en el Brain Backup generado: {name}")


def prune_brain_backups(output_dir: Path | None = None, *, protect: Path | None = None, max_files: int | None = None) -> list[str]:
    """Retain only Brain Backups, never deleting the newly created protected file."""
    directory = (output_dir or BACKUP_DIR).expanduser().resolve()
    limit = max(1, int(max_files if max_files is not None else BRAIN_MAX_BACKUPS))
    protected = protect.resolve() if protect else None
    archives = sorted(directory.glob("gaia_brain_*.zip"), key=lambda item: item.stat().st_mtime)
    removable = [item for item in archives if protected is None or item.resolve() != protected]
    while len(archives) > limit and removable:
        candidate = removable.pop(0)
        candidate.unlink(missing_ok=True)
        archives.remove(candidate)
    return [str(item) for item in archives]


def restore_brain_backup(archive_path: Path, *, create_current_backup: bool = True) -> dict:
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.exists():
        raise RuntimeError(f"No existe el archivo de backup: {archive_path}")
    with tempfile.TemporaryDirectory(prefix="gaia_restore_") as temp:
        root = Path(temp)
        with zipfile.ZipFile(archive_path) as bundle:
            raw_names = bundle.namelist()
            if len(raw_names) != len(set(raw_names)):
                raise RuntimeError("El Brain Backup contiene nombres de archivo duplicados.")
            for name in raw_names:
                candidate = Path(name)
                if candidate.is_absolute() or name.startswith(("/", "\\")) or ".." in candidate.parts or len(candidate.parts) != 1:
                    raise RuntimeError(f"Ruta insegura dentro del Brain Backup: {name}")
            names = set(raw_names)
            if MANIFEST_NAME not in names:
                raise RuntimeError("El Brain Backup no contiene manifest.json.")
            manifest_bytes = bundle.read(MANIFEST_NAME)
            try:
                manifest = json.loads(manifest_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("manifest.json no es JSON válido.") from exc
            if not isinstance(manifest, dict) or manifest.get("format") != "GAIA Brain Backup":
                raise RuntimeError("Formato de Brain Backup no compatible.")
            try:
                schema_version = int(manifest.get("schema_version", 0))
            except (TypeError, ValueError) as exc:
                raise RuntimeError("schema_version inválido en manifest.json.") from exc
            if schema_version < 1 or schema_version > SCHEMA_VERSION:
                raise RuntimeError("Versión de Brain Backup no compatible.")
            declared = manifest.get("files")
            if not isinstance(declared, dict) or not declared:
                raise RuntimeError("manifest.json no declara hashes de archivos.")
            expected_names = set(str(name) for name in declared)
            required = {"memory.db", "preferences.json", "state.json"}
            if not required.issubset(expected_names) or not required.issubset(names):
                raise RuntimeError("El Brain Backup no contiene todos los archivos obligatorios.")
            if names != expected_names | {MANIFEST_NAME}:
                extras = sorted(names - expected_names - {MANIFEST_NAME})
                missing = sorted(expected_names - names)
                raise RuntimeError(f"Contenido del Brain Backup no coincide con manifest; extras={extras}, faltantes={missing}.")
            if any(name.endswith(("-wal", "-shm", "-journal")) for name in names):
                raise RuntimeError("El Brain Backup contiene un sidecar SQLite prohibido.")
            for filename, expected_hash in declared.items():
                if not isinstance(filename, str) or not isinstance(expected_hash, str) or len(expected_hash) != 64:
                    raise RuntimeError(f"Hash inválido en manifest para {filename!r}.")
                target_file = root / filename
                target_file.write_bytes(bundle.read(filename))
                actual_hash = _sha256(target_file)
                if actual_hash.lower() != expected_hash.lower():
                    raise RuntimeError(f"IntegrityError: {filename} hash mismatch")
            (root / MANIFEST_NAME).write_bytes(manifest_bytes)
        source_db = root / "memory.db"
        if not source_db.is_file() or _integrity_check(source_db) != "ok":
            raise RuntimeError("La base del Brain Backup no supera integrity_check.")
        if create_current_backup:
            current_backup = memory.create_backup()
        else:
            current_backup = ""
        _stabilize_active_database()
        target = DB_PATH.with_name(f".{DB_PATH.name}.restore-{datetime.now().strftime('%Y%m%d%H%M%S%f')}.tmp")
        try:
            _copy_sqlite(source_db, target)
            if _integrity_check(target) != "ok":
                raise RuntimeError("La copia restaurada no supera integrity_check.")
            target.replace(DB_PATH)
        finally:
            target.unlink(missing_ok=True)
        return {"status": "restored", "archive": str(archive_path), "current_backup": current_backup, "db": str(DB_PATH), "integrity": "ok", "manifest_verified": True}


def _safe_profile() -> dict:
    try:
        return {"user_name": memory.get_preference("user_name", ""), "facts_count": len(memory.get_facts())}
    except Exception:
        return {}


def _safe_state() -> dict:
    try:
        return {"last_backup_time": memory.get_state("last_backup_time", ""), "last_device": memory.get_state("last_device", ""), "vault_status": VAULT_STATUS}
    except Exception:
        return {}


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
