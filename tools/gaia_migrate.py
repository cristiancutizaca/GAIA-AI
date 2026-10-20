"""GAIA v1.0-RC6 migration, Vault strategy, snapshot and recovery helper.

Inspection is read-only by default. Apply/rollback require explicit approval,
verified release identity and an explicit database/rollback strategy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
from typing import Any

RC6_VERSION = "1.0.0-rc6"
RC6_CORE_VERSION = "1.0.0-rc6-pc"
RC6_LABEL = "1.0-RC6"
RC6_PROTOCOL = "1.0-RC6"
MIN_SUPPORTED_SCHEMA = 8
SUPPORTED_SCHEMA_MAX = 9
DB_STRATEGIES = frozenset({"CLONE_TO_TARGET", "REUSE_EXISTING_EXTERNAL_VAULT", "CLONE_TO_NEW_VAULT", "KEEP_TARGET_CONFIG"})
ROLLBACK_MODES = frozenset({"ROLLBACK_DATABASE_ONLY", "ROLLBACK_DATABASE_AND_CONFIG", "ROLLBACK_TO_PREVIOUS_INSTALLATION"})
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_RE = re.compile(r"^(?:\\\\|//)")
_ALLOWED_PATH_KEYS = {"GAIA_MEMORY_DB", "LUMEN_MEMORY_DB", "GAIA_DATA_DIR", "LUMEN_DATA_DIR", "GAIA_HOME", "GAIA_VAULT", "GAIA_BACKUP_DIR", "LUMEN_BACKUP_DIR"}
_COUNT_TABLES = ("devices", "device_tokens", "permission_grants", "memory_items", "memory_item_history", "session_owners", "automation_rules", "routines", "schedules", "trusted_apps", "trusted_folders")


def _version_tuple(value: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.match(str(value).strip().lstrip("v"))
    return tuple(int(part) for part in match.groups()) if match else None


def _read_version(root: Path) -> str:
    path = root / "lumen-core" / "config.py"
    if not path.is_file():
        return "unknown"
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', path.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    return match.group(1) if match else "unknown"


def _windows_like(value: str) -> bool:
    token = str(value or "").strip()
    return bool(_WINDOWS_DRIVE_RE.match(token) or _UNC_RE.match(token))


def _path_from_value(value: str, root: Path) -> Path:
    token = str(value or "").strip()
    if _windows_like(token):
        return Path(token)
    path = Path(token).expanduser()
    return path if path.is_absolute() else root / path


def _read_env_paths(root: Path, *, include_process: bool = True) -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = root / ".env"
    if env_file.is_file():
        for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in _ALLOWED_PATH_KEYS and value.strip():
                values[key.strip()] = value.strip().strip("\"'")
    if include_process:
        for key in _ALLOWED_PATH_KEYS:
            value = os.getenv(key, "").strip()
            if value:
                values[key] = value
    return values


def _safe_env_paths(root: Path) -> dict[str, str]:
    return _read_env_paths(root, include_process=True)


def resolve_db_path(root: Path, *, include_process: bool = True) -> Path:
    root = root.expanduser().resolve()
    values = _read_env_paths(root, include_process=include_process)
    explicit = values.get("GAIA_MEMORY_DB") or values.get("LUMEN_MEMORY_DB")
    if explicit:
        return _path_from_value(explicit, root)
    data = values.get("GAIA_DATA_DIR") or values.get("LUMEN_DATA_DIR")
    if data:
        return _path_from_value(data, root) / "lumen_memory.db"
    vault = values.get("GAIA_HOME") or values.get("GAIA_VAULT")
    if vault:
        return _path_from_value(vault, root) / "data" / "memory" / "lumen_memory.db"
    return root / "lumen-core" / "data" / "lumen_memory.db"


def _path_token(path: Path) -> str:
    token = str(path).replace("\\", "/").rstrip("/")
    return token.casefold() if _windows_like(str(path)) else token


def _same_path(left: Path, right: Path) -> bool:
    if _windows_like(str(left)) or _windows_like(str(right)):
        return _path_token(left) == _path_token(right)
    left_resolved = left.expanduser().resolve(strict=False)
    right_resolved = right.expanduser().resolve(strict=False)
    if left_resolved == right_resolved:
        return True
    try:
        return left_resolved.exists() and right_resolved.exists() and os.path.samefile(left_resolved, right_resolved)
    except OSError:
        return False


def _inside(child: Path, parent: Path) -> bool:
    if _windows_like(str(child)) or _windows_like(str(parent)):
        c, p = _path_token(child), _path_token(parent).rstrip("/")
        return c == p or c.startswith(p + "/")
    try:
        child.expanduser().resolve(strict=False).relative_to(parent.expanduser().resolve(strict=False))
        return True
    except ValueError:
        return False


def _schema_and_counts(db_path: Path) -> tuple[str, str, dict[str, int]]:
    if not db_path.is_file():
        return "absent", "not_checked", {}
    try:
        with sqlite3.connect(str(db_path), timeout=3) as conn:
            conn.execute("PRAGMA query_only=ON")
            integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone() if "schema_meta" in tables else None
            schema = str(row[0]) if row else "unknown"
            counts = {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in _COUNT_TABLES if table in tables}
            return schema, integrity, counts
    except (OSError, sqlite3.DatabaseError) as exc:
        return "error", f"{type(exc).__name__}: {exc}", {}


def _compatibility(current_version: str, schema: str, target_version: str) -> dict[str, Any]:
    current_tuple = _version_tuple(current_version)
    target_tuple = _version_tuple(target_version)
    schema_number = int(schema) if schema.isdigit() else None
    if current_tuple is None or target_tuple is None:
        return {"status": "blocked_version_format", "source_supported": False}
    if current_tuple > target_tuple:
        return {"status": "blocked_downgrade", "source_supported": False}
    if schema_number is None:
        return {"status": "blocked_unknown_schema", "source_supported": False}
    if schema_number > SUPPORTED_SCHEMA_MAX:
        return {"status": "blocked_newer_schema", "source_supported": False}
    if schema_number < MIN_SUPPORTED_SCHEMA:
        return {"status": "blocked_old_schema", "source_supported": False}
    return {"status": "compatible_review_required", "source_supported": True, "schema_target": SUPPORTED_SCHEMA_MAX}


def inspect_installation(root: Path, target_version: str = RC6_VERSION, *, safe_mode: bool = False) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"installation root does not exist: {root}")
    current, target = _read_version(root), str(target_version).strip()
    db_path = resolve_db_path(root)
    schema, integrity, counts = _schema_and_counts(db_path)
    compatibility = _compatibility(current, schema, target)
    if not db_path.is_file():
        migration_state = "no_database"
    elif integrity != "ok":
        migration_state = "blocked_integrity"
    elif compatibility["status"].startswith("blocked_"):
        migration_state = compatibility["status"]
    else:
        migration_state = compatibility["status"]
    return {"tool": "gaia_migrate", "release_target": RC6_LABEL, "target_version": target, "read_only_default": True, "safe_mode": bool(safe_mode), "root": str(root), "current_version": current, "db_path": str(db_path), "db_exists": db_path.is_file(), "source_db_external": not _inside(db_path, root), "schema": schema, "schema_min_supported": MIN_SUPPORTED_SCHEMA, "schema_max_supported": SUPPORTED_SCHEMA_MAX, "integrity": integrity, "migration_state": migration_state, "compatibility": compatibility, "preservation": {"env_present": (root / ".env").is_file(), "env_example_present": (root / ".env.example").is_file(), "data_dir_present": (root / "lumen-core" / "data").is_dir(), "backup_dir_present": (root / "lumen-core" / "data" / "backups").is_dir(), "counts": counts}, "code_downloaded": False, "secret_values_emitted": False}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_external_destination(root: Path, destination: Path) -> None:
    root, destination = root.expanduser().resolve(), destination.expanduser().resolve()
    if destination == root or root in destination.parents:
        raise ValueError("snapshot destination must be outside installation root")


def _assert_distinct_roots(source_root: Path, target_root: Path) -> None:
    source_root, target_root = source_root.expanduser().resolve(), target_root.expanduser().resolve()
    if source_root == target_root or _inside(source_root, target_root) or _inside(target_root, source_root):
        raise ValueError("source and target installation roots must be distinct and non-nested")


def _copy_private_env(source: Path, destination: Path, name: str) -> Path | None:
    if not source.is_file():
        return None
    copy = destination / name
    shutil.copy2(source, copy)
    try:
        copy.chmod(0o600)
    except OSError:
        pass
    return copy


def create_snapshot(root: Path, destination: Path, report: dict[str, Any], *, config_root: Path | None = None) -> dict[str, Any]:
    root, destination = root.expanduser().resolve(), destination.expanduser().resolve()
    _assert_external_destination(root, destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("snapshot destination must be new or empty")
    destination.mkdir(parents=True, exist_ok=True)
    source_env_copy = _copy_private_env(root / ".env", destination, ".env.private.copy")
    target_env_copy = None
    if config_root is not None:
        config_root = config_root.expanduser().resolve()
        _assert_external_destination(root, config_root)
        target_env_copy = _copy_private_env(config_root / ".env", destination, ".env.target.before.copy")
    db_source = Path(report["db_path"])
    db_copy = None
    if db_source.is_file():
        db_copy = destination / "memory.snapshot.sqlite"
        source = sqlite3.connect(f"file:{db_source.as_posix()}?mode=ro", uri=True, timeout=5)
        try:
            target = sqlite3.connect(str(db_copy), timeout=5)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
    manifest = {"format": "gaia-rc6-snapshot-1", "release_target": RC6_LABEL, "source_version": report["current_version"], "target_version": report["target_version"], "schema": report["schema"], "integrity_before": report["integrity"], "source_db_external": bool(report.get("source_db_external")), "files": {"source_env_private_copy": bool(source_env_copy), "target_env_before_copy": bool(target_env_copy), "memory_snapshot": bool(db_copy)}, "sha256": {"memory_snapshot": _sha256(db_copy) if db_copy else None}, "secret_values_emitted": False, "code_downloaded": False}
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _copy_sqlite_snapshot(snapshot_db: Path, target_db: Path) -> None:
    if not snapshot_db.is_file():
        raise ValueError("snapshot has no memory database")
    target_db.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"file:{snapshot_db.as_posix()}?mode=ro", uri=True, timeout=5)
    try:
        target = sqlite3.connect(str(target_db), timeout=5)
        try:
            source.backup(target)
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            target.close()
    finally:
        source.close()


def _load_verified_snapshot(snapshot_dir: Path, report: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot_dir = snapshot_dir.expanduser().resolve()
    manifest_path, snapshot_db = snapshot_dir / "manifest.json", snapshot_dir / "memory.snapshot.sqlite"
    if not manifest_path.is_file() or not snapshot_db.is_file():
        raise ValueError("snapshot manifest/database missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "gaia-rc6-snapshot-1":
        raise ValueError("unsupported snapshot format")
    expected = ((manifest.get("sha256") or {}).get("memory_snapshot"))
    if not expected or _sha256(snapshot_db) != expected:
        raise ValueError("snapshot checksum mismatch")
    if report is not None:
        if manifest.get("source_version") != report.get("current_version"):
            raise ValueError("snapshot source version differs from inspected installation")
        if manifest.get("target_version") != report.get("target_version"):
            raise ValueError("snapshot target version differs from requested migration")
    return manifest


def _read_release_manifest(root: Path) -> dict[str, Any]:
    path = root / "release_manifest.json"
    if not path.is_file():
        raise ValueError("target release manifest missing; refuse to mutate unknown folder")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"target release manifest invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("target release manifest must be an object")
    return value


def _validate_target_identity(target_root: Path) -> dict[str, Any]:
    manifest = _read_release_manifest(target_root)
    try:
        schema_min, schema_max = int(manifest.get("schema_min", -1)), int(manifest.get("schema_max", -1))
    except (TypeError, ValueError) as exc:
        raise ValueError("target release manifest schema range invalid") from exc
    if manifest.get("product") != "GAIA-AI" or manifest.get("release") != RC6_LABEL or manifest.get("version") != RC6_CORE_VERSION or manifest.get("protocol") != RC6_PROTOCOL:
        raise ValueError("target release identity/version/protocol mismatch")
    if schema_min != MIN_SUPPORTED_SCHEMA or schema_max != SUPPORTED_SCHEMA_MAX:
        raise ValueError("target release manifest schema range mismatch")
    if _read_version(target_root) != RC6_CORE_VERSION:
        raise ValueError("target config VERSION mismatch")
    required = (target_root / "lumen-core" / "config.py", target_root / "tools" / "gaia_migrate.py", target_root / "release_manifest.json")
    if any(not item.is_file() for item in required):
        raise ValueError("target release is missing required files")
    return manifest


def _set_env_path(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.is_file() else []
    output, found = [], False
    for line in lines:
        if line.lstrip().startswith(f"{key}="):
            if not found:
                output.append(f"{key}={value}")
                found = True
        else:
            output.append(line)
    if not found:
        output.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _target_db_for_strategy(source_root: Path, target_root: Path, source_db: Path, strategy: str, new_vault: Path | None) -> tuple[Path, bool, dict[str, Any]]:
    strategy = str(strategy or "").strip().upper()
    if strategy not in DB_STRATEGIES:
        raise ValueError(f"unsupported db strategy: {strategy}")
    target_env = target_root / ".env"
    changes: dict[str, Any] = {"strategy": strategy, "env_changed": False, "same_physical_db": False}
    internal = (target_root / "lumen-core" / "data" / "lumen_memory.db").resolve()
    if strategy == "CLONE_TO_TARGET":
        if target_env.is_file() and not _same_path(resolve_db_path(target_root, include_process=False), internal):
            raise ValueError("target configuration selects an external/aliased DB; choose an explicit strategy")
        return internal, False, changes
    if strategy == "CLONE_TO_NEW_VAULT":
        if new_vault is None:
            raise ValueError("CLONE_TO_NEW_VAULT requires --new-vault")
        vault = new_vault.expanduser().resolve()
        if _inside(vault, source_root) or _inside(vault, target_root):
            raise ValueError("new vault must be outside source and target installations")
        target_db = vault / "data" / "memory" / "lumen_memory.db"
        _set_env_path(target_env, "GAIA_MEMORY_DB", str(target_db))
        changes.update({"env_changed": True, "target_env_key": "GAIA_MEMORY_DB"})
        return target_db, False, changes
    if strategy == "REUSE_EXISTING_EXTERNAL_VAULT":
        if _inside(source_db, source_root):
            raise ValueError("REUSE_EXISTING_EXTERNAL_VAULT requires an external source DB")
        _set_env_path(target_env, "GAIA_MEMORY_DB", str(source_db))
        changes.update({"env_changed": True, "target_env_key": "GAIA_MEMORY_DB", "same_physical_db": True})
        return source_db, True, changes
    if not target_env.is_file():
        raise ValueError("KEEP_TARGET_CONFIG requires an existing target .env")
    return resolve_db_path(target_root, include_process=False), False, changes


def _snapshot_context(snapshot_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _load_verified_snapshot(snapshot_dir)
    apply_manifest: dict[str, Any] = {}
    path = snapshot_dir / "apply-manifest.json"
    if path.is_file():
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            apply_manifest = value
    return manifest, apply_manifest


def apply_migration(source_root: Path, target_root: Path, snapshot_dir: Path, report: dict[str, Any], *, approved: bool = False, safe_mode: bool = False, db_strategy: str = "CLONE_TO_TARGET", new_vault: Path | None = None) -> dict[str, Any]:
    if not approved:
        raise PermissionError("apply requires explicit approval")
    source_root, target_root, snapshot_dir = source_root.expanduser().resolve(), target_root.expanduser().resolve(), snapshot_dir.expanduser().resolve()
    if not target_root.is_dir() or not (target_root / "lumen-core").is_dir():
        raise ValueError("target installation must be an existing release folder")
    _assert_distinct_roots(source_root, target_root)
    _assert_external_destination(source_root, snapshot_dir)
    _validate_target_identity(target_root)
    if report.get("migration_state") not in {"compatible_review_required", "ready_to_review"}:
        raise ValueError(f"migration blocked: {report.get('migration_state')}")
    manifest = _load_verified_snapshot(snapshot_dir, report) if snapshot_dir.exists() and any(snapshot_dir.iterdir()) else create_snapshot(source_root, snapshot_dir, report, config_root=target_root)
    source_db = Path(report["db_path"]).expanduser()
    target_db, same_physical_db, config_changes = _target_db_for_strategy(source_root, target_root, source_db, db_strategy, new_vault)
    if not same_physical_db and _same_path(source_db, target_db):
        raise ValueError("source and target resolve to the same DB; choose explicit REUSE_EXISTING_EXTERNAL_VAULT")
    if not same_physical_db:
        _copy_sqlite_snapshot(snapshot_dir / "memory.snapshot.sqlite", target_db)
    applied = {"operation": "apply", "release_target": RC6_LABEL, "source_root": str(source_root), "target_root": str(target_root), "source_db": str(source_db), "target_db": str(target_db), "snapshot_dir": str(snapshot_dir), "db_strategy": str(db_strategy).upper(), "same_physical_db": same_physical_db, "safe_mode": bool(safe_mode), "config_changes": config_changes, "memory_copied": not same_physical_db, "source_preserved": True, "secret_values_emitted": False, "code_downloaded": False, "snapshot": manifest}
    manifest.update({"db_strategy": str(db_strategy).upper(), "target_db": str(target_db), "same_physical_db": same_physical_db})
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (snapshot_dir / "apply-manifest.json").write_text(json.dumps(applied, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return applied


def rollback_from_snapshot(snapshot_dir: Path, target_root: Path, *, approved: bool = False, safe_mode: bool = True, rollback_mode: str = "ROLLBACK_DATABASE_ONLY") -> dict[str, Any]:
    if not approved:
        raise PermissionError("rollback requires explicit approval")
    snapshot_dir, target_root = snapshot_dir.expanduser().resolve(), target_root.expanduser().resolve()
    rollback_mode = str(rollback_mode or "").strip().upper()
    if rollback_mode not in ROLLBACK_MODES:
        raise ValueError(f"unsupported rollback mode: {rollback_mode}")
    if not snapshot_dir.is_dir() or not target_root.is_dir():
        raise ValueError("snapshot and target installation must exist")
    manifest, apply_manifest = _snapshot_context(snapshot_dir)
    target_db = Path(str(apply_manifest.get("target_db") or manifest.get("target_db") or resolve_db_path(target_root, include_process=False))).expanduser()
    before_sha = _sha256(target_db) if target_db.is_file() else None
    same_physical_db = bool(manifest.get("same_physical_db"))
    if not same_physical_db:
        _copy_sqlite_snapshot(snapshot_dir / "memory.snapshot.sqlite", target_db)
    config_restored = False
    if rollback_mode in {"ROLLBACK_DATABASE_AND_CONFIG", "ROLLBACK_TO_PREVIOUS_INSTALLATION"}:
        if not bool((manifest.get("files") or {}).get("target_env_before_copy")) or not (snapshot_dir / ".env.target.before.copy").is_file():
            raise ValueError("full config rollback requested but target config snapshot is missing")
        shutil.copy2(snapshot_dir / ".env.target.before.copy", target_root / ".env")
        try:
            (target_root / ".env").chmod(0o600)
        except OSError:
            pass
        config_restored = True
    result = {"operation": "rollback", "release_target": RC6_LABEL, "target_root": str(target_root), "target_db": str(target_db), "snapshot_dir": str(snapshot_dir), "rollback_mode": rollback_mode, "safe_mode": bool(safe_mode), "before_sha256": before_sha, "after_sha256": _sha256(target_db) if target_db.is_file() else None, "database_restored": same_physical_db or target_db.is_file(), "config_restored": config_restored, "installation_code_restored": False, "source_preserved": True, "secret_values_emitted": False}
    (snapshot_dir / "rollback-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="GAIA v1.0-RC6 migration, Vault strategy, snapshot and rollback tool")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--target-root", type=Path)
    parser.add_argument("--target-version", default=RC6_VERSION)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--safe-mode", action="store_true")
    parser.add_argument("--snapshot-dir", type=Path)
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--db-strategy", choices=sorted(DB_STRATEGIES), default="CLONE_TO_TARGET")
    parser.add_argument("--new-vault", type=Path)
    parser.add_argument("--rollback-mode", choices=sorted(ROLLBACK_MODES), default="ROLLBACK_DATABASE_ONLY")
    args = parser.parse_args()
    try:
        if args.rollback:
            if not args.snapshot_dir:
                raise ValueError("--rollback requires --snapshot-dir")
            result = rollback_from_snapshot(args.snapshot_dir, args.root, approved=args.approve, safe_mode=args.safe_mode, rollback_mode=args.rollback_mode)
        else:
            report = inspect_installation(args.root, args.target_version, safe_mode=args.safe_mode)
            if args.snapshot and (args.apply or args.rollback):
                raise ValueError("--snapshot cannot be combined with --apply/--rollback")
            if args.snapshot:
                if not args.snapshot_dir:
                    raise ValueError("--snapshot requires --snapshot-dir")
                if report.get("migration_state") not in {"compatible_review_required", "ready_to_review"}:
                    raise ValueError(f"migration blocked: {report.get('migration_state')}")
                result = {"operation": "snapshot", "release_target": RC6_LABEL, "safe_mode": bool(args.safe_mode), "snapshot": create_snapshot(args.root, args.snapshot_dir, report), "secret_values_emitted": False, "code_downloaded": False}
            elif args.apply:
                if not args.target_root or not args.snapshot_dir:
                    raise ValueError("--apply requires --target-root and --snapshot-dir")
                result = apply_migration(args.root, args.target_root, args.snapshot_dir, report, approved=args.approve, safe_mode=args.safe_mode, db_strategy=args.db_strategy, new_vault=args.new_vault)
            else:
                result = report
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        elif result.get("operation") == "apply":
            print(f"GAIA RC6 migration applied: target={result['target_root']} strategy={result['db_strategy']} same_physical_db={result['same_physical_db']}")
        elif result.get("operation") == "rollback":
            print(f"GAIA RC6 rollback complete: mode={result['rollback_mode']} config_restored={result['config_restored']}")
        elif result.get("operation") == "snapshot":
            print(f"GAIA RC6 external snapshot created: {result['snapshot'].get('sha256', {}).get('memory_snapshot')}")
        else:
            print(f"GAIA RC6 migration plan: {result['current_version']} -> {result['target_version']}; state={result['migration_state']}")
        return 0 if not str(result.get("migration_state", "")).startswith("blocked_") else 2
    except (OSError, ValueError, PermissionError, sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        print(f"gaia_migrate: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
