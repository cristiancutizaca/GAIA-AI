#!/usr/bin/env python3
"""GAIA 2.0 CLI over the same authoritative internal APIs; no parallel execution core."""
from __future__ import annotations
import argparse, json, sys, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lumen-core"))
from gaia_ext.feature_flags import feature_flags
from gaia_ext.foundation import build_foundation
from gaia_platform.skills2 import SkillRegistryV2
skill_registry = SkillRegistryV2()
from gaia_platform.memory_v2 import MemoryV2Store
from platform_runtime import PlatformRuntime
from gaia_platform.backup import BackupManager

def main(argv=None):
    parser = argparse.ArgumentParser(prog="gaia")
    parser.add_argument("command", choices=["version","start","stop","restart","status","doctor","models","memory","skills","plugins","mcp","browser","voice","workers","automations","devices","backup","restore","update","rollback","logs","config","flags","plan","diagnostics","validate","desktop","startup"])
    parser.add_argument("target", nargs="?", default="list")
    parser.add_argument("--output", default="")
    parser.add_argument("--message", default="")
    args = parser.parse_args(argv)
    foundation = build_foundation()
    if args.command == "version":
        from gaia_version import PRODUCT_VERSION, RELEASE, WIRE_PROTOCOL
        print(json.dumps({"gaia":PRODUCT_VERSION,"release":RELEASE,"wire_protocol":WIRE_PROTOCOL,"schema":1,"flags":feature_flags.as_dict()}, indent=2)); return 0
    if args.command in {"doctor","status"}:
        from gaia_doctor_v2 import run
        print(json.dumps(run(), ensure_ascii=False, indent=2)); return 0
    if args.command in {"flags","config"}:
        print(json.dumps(feature_flags.as_dict(), ensure_ascii=False, indent=2)); return 0
    if args.command == "plan":
        runtime = PlatformRuntime(ROOT / "lumen-core")
        try: print(json.dumps(runtime.planner.serialize(runtime.planner.plan(args.message or args.target, mcp_configs=runtime.mcp.configs)), ensure_ascii=False, indent=2))
        finally:
            runtime.memory.close(); runtime.automations.close(); runtime.projects.close(); runtime.jobs.close()
        return 0
    if args.command == "diagnostics":
        runtime = PlatformRuntime(ROOT / "lumen-core")
        try:
            if args.target == "export":
                output = Path(args.output or ROOT / "diagnostics" / "gaia-diagnostics.zip")
                print(json.dumps(runtime.diagnostics_exporter.export(output,status=runtime.status(),events=[]), indent=2))
            else: print(json.dumps(runtime.status(), ensure_ascii=False, indent=2))
        finally: runtime.memory.close(); runtime.automations.close(); runtime.projects.close(); runtime.jobs.close()
        return 0
    if args.command == "validate":
        if args.target != "physical": print(json.dumps({"status":"PENDING","hint":"Use gaia validate physical"})); return 0
        return subprocess.call([sys.executable, str(ROOT / "tools" / "physical_validation.py"), "new", "--output-dir", args.output or str(ROOT / "physical-validation")])
    if args.command == "startup":
        action = args.target if args.target in {"enable", "disable", "status"} else "status"
        return subprocess.call([sys.executable, str(ROOT / "tools" / "gaia_startup.py"), action])
    if args.command == "desktop":
        sys.path.insert(0, str(ROOT / "lumen-pc"))
        from desktop_shell import DesktopShell
        shell = DesktopShell(); return shell.exec()
    if args.command == "plugins": print(json.dumps(foundation["plugins"].status(), indent=2)); return 0
    if args.command == "mcp": print(json.dumps(foundation["mcp"].health(), indent=2)); return 0
    if args.command == "skills":
        if args.target == "enable" and args.output: skill_registry.enable(args.output)
        elif args.target == "disable" and args.output: skill_registry.disable(args.output)
        print(json.dumps(skill_registry.list(), ensure_ascii=False, indent=2)); return 0
    if args.command == "memory":
        store = MemoryV2Store(ROOT / "lumen-core" / "data" / "lumen_memory_v12.db")
        print(json.dumps({"provider":"SQLiteMemoryProvider","path":str(store.path),"owner_required":True}, indent=2)); store.close(); return 0
    if args.command == "backup":
        output = Path(args.output or (ROOT / "backups" / "gaia-v12-backup.zip"))
        manifest = BackupManager(ROOT).create(output, [ROOT / "lumen-core" / "data"], owner="local")
        print(json.dumps({"archive":str(output),"manifest":manifest}, indent=2)); return 0
    if args.command == "restore":
        print(json.dumps({"status":"requires_explicit_archive_and_target","hint":"Use BackupManager.restore after GAIA authorization."}, indent=2)); return 0
    if args.command in {"start","stop","restart","update","rollback"}:
        print(json.dumps({"command":args.command,"status":"requires_existing GAIA service authorization","safe":True}, indent=2)); return 0
    print(json.dumps({"command":args.command,"status":"DISABLED","detail":"No optional integration is loaded without its feature flag; GAIA Core remains authoritative."}, indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
