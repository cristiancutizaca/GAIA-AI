from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

with tempfile.TemporaryDirectory(prefix="gaia_backup_integrity_") as tmp:
    os.environ.update({
        "LUMEN_DATA_DIR": tmp,
        "LUMEN_LLM_BACKEND": "mock",
        "LUMEN_SECRET": "test-secret-backup-integrity",
        "LUMEN_BACKUP_ENABLED": "false",
        "LUMEN_PROACTIVE_ENABLED": "false",
    })
    import memory
    from brain_backup import create_brain_backup, restore_brain_backup, SCHEMA_VERSION

    memory.init_db()
    memory.save_message("restore-session", "user", "estado original", "test")
    archive = Path(create_brain_backup(Path(tmp) / "archives"))
    memory.save_message("restore-session", "user", "marker activo antes del rechazo", "test")
    before = [row["content"] for row in memory.get_conversation_history("restore-session", limit=20)]

    def read_entries(path: Path) -> dict[str, bytes]:
        with zipfile.ZipFile(path) as bundle:
            return {name: bundle.read(name) for name in bundle.namelist()}

    def write_archive(path: Path, entries: dict[str, bytes]) -> Path:
        output = Path(tmp) / "mutated" / f"{path.stem}-{len(list((Path(tmp) / 'mutated').glob('*'))) if (Path(tmp) / 'mutated').exists() else 0}.zip"
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, content in entries.items():
                bundle.writestr(name, content)
        return output

    tampered = read_entries(archive)
    tampered["preferences.json"] = b'{"user_name":"attacker"}'
    try:
        restore_brain_backup(write_archive(archive, tampered), create_current_backup=False)
        raise AssertionError("El backup manipulado fue aceptado")
    except RuntimeError as exc:
        assert "preferences.json hash mismatch" in str(exc)
    assert [row["content"] for row in memory.get_conversation_history("restore-session", limit=20)] == before

    missing = read_entries(archive)
    del missing["state.json"]
    try:
        restore_brain_backup(write_archive(archive, missing), create_current_backup=False)
        raise AssertionError("El backup sin state.json fue aceptado")
    except RuntimeError as exc:
        assert "obligatorios" in str(exc) or "manifest" in str(exc)

    extra = read_entries(archive)
    extra["unexpected.txt"] = b"dato externo"
    try:
        restore_brain_backup(write_archive(archive, extra), create_current_backup=False)
        raise AssertionError("El backup con archivo extra fue aceptado")
    except RuntimeError as exc:
        assert "extras" in str(exc)

    unknown = read_entries(archive)
    manifest = json.loads(unknown["manifest.json"])
    manifest["schema_version"] = SCHEMA_VERSION + 99
    unknown["manifest.json"] = json.dumps(manifest).encode()
    try:
        restore_brain_backup(write_archive(archive, unknown), create_current_backup=False)
        raise AssertionError("El backup con schema desconocido fue aceptado")
    except RuntimeError as exc:
        assert "compatible" in str(exc)

    corrupt = read_entries(archive)
    corrupt["memory.db"] = b"not-a-sqlite-database"
    corrupt_manifest = json.loads(corrupt["manifest.json"])
    corrupt_manifest["files"]["memory.db"] = hashlib.sha256(corrupt["memory.db"]).hexdigest()
    corrupt["manifest.json"] = json.dumps(corrupt_manifest).encode()
    try:
        restore_brain_backup(write_archive(archive, corrupt), create_current_backup=False)
        raise AssertionError("La SQLite corrupta fue aceptada")
    except RuntimeError as exc:
        assert "integrity_check" in str(exc)
    assert [row["content"] for row in memory.get_conversation_history("restore-session", limit=20)] == before

    valid = restore_brain_backup(archive, create_current_backup=False)
    assert valid["manifest_verified"] is True and valid["integrity"] == "ok"
    restored = [row["content"] for row in memory.get_conversation_history("restore-session", limit=20)]
    assert restored == ["estado original"]

print("BACKUP INTEGRITY TEST OK")
