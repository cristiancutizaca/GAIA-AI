from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))

import brain_backup  # noqa: E402
from config import BACKUP_DIR, DB_PATH, GAIA_VAULT  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="GAIA: migración, Brain Backup y restauración segura")
    sub = parser.add_subparsers(dest="command", required=True)
    migrate = sub.add_parser("migrate", help="Migra SQLite sin borrar el origen")
    migrate.add_argument("--source", type=Path, default=DB_PATH)
    migrate.add_argument("--destination", type=Path, default=(GAIA_VAULT / "data" / "memory" / "lumen_memory.db" if GAIA_VAULT else ROOT / "gaia_vault" / "data" / "memory" / "lumen_memory.db"))
    migrate.add_argument("--dry-run", action="store_true")
    backup = sub.add_parser("brain-backup", help="Crea GAIA Brain Backup")
    backup.add_argument("--output-dir", type=Path, default=BACKUP_DIR)
    restore = sub.add_parser("restore", help="Restaura un Brain Backup después de crear snapshot actual")
    restore.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "migrate":
            print(brain_backup.migrate_database(args.source, args.destination, args.dry_run))
        elif args.command == "brain-backup":
            print(brain_backup.create_brain_backup(args.output_dir))
        else:
            print(brain_backup.restore_brain_backup(args.archive))
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"GAIA: operación no completada: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
