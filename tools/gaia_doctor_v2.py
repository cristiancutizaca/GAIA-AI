#!/usr/bin/env python3
"""GAIA Doctor 2.1: read-only capability/dependency inventory from canonical manifest."""
from __future__ import annotations
import argparse, importlib.util, json, os, platform, re, shutil, sqlite3, subprocess, sys, tempfile
from urllib.parse import urlsplit
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'lumen-core')); sys.path.insert(0,str(ROOT/'lumen-pc')); sys.path.insert(0,str(ROOT/'tools'))
from gaia_ext.feature_flags import feature_flags
from gaia_dependencies import component_status, load

def check(name,status,detail='',suggestion=''): return {'name':name,'status':status,'detail':detail,'suggestion':suggestion}
def mod(name): return importlib.util.find_spec(name) is not None

def memory_check():
    """Inspect the effective SQLite file without creating or disclosing its contents."""
    from config import AUTO_FACTS_ENABLED, AUTO_MEMORY_ENABLED, DB_PATH, MEMORY_CONTEXT_MAX_CHARS, MEMORY_RELEVANCE_LIMIT

    evidence = {"path": str(DB_PATH), "auto_memory": AUTO_MEMORY_ENABLED, "legacy_auto_facts": AUTO_FACTS_ENABLED,
                "context_max_chars": MEMORY_CONTEXT_MAX_CHARS, "relevance_limit": MEMORY_RELEVANCE_LIMIT}
    if not DB_PATH.is_file():
        return {**check("MEMORY_SQLITE", "MISSING", "La ruta configurada todavía no contiene una base SQLite.",
                        "Comprueba GAIA_MEMORY_DB o inicia el Core de la instalación que deseas revisar."), **evidence}
    try:
        from contextlib import closing
        with closing(sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            evidence["indexed_explicit_memory"] = "memories_fts" in tables
            evidence["legacy_file_also_exists"] = (ROOT / "data" / "platform_memory_v13.db").is_file()
            evidence["explicit_count"] = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0] if "memories" in tables else None
            evidence["legacy_fact_count"] = db.execute("SELECT COUNT(*) FROM user_facts").fetchone()[0] if "user_facts" in tables else None
        return {**check("MEMORY_SQLITE", "DB_READABLE", "SQLite abrió la base efectiva en modo de solo lectura."), **evidence}
    except sqlite3.Error as exc:
        return {**check("MEMORY_SQLITE", "DB_READ_FAILED", f"SQLite no pudo leer la base ({type(exc).__name__}).",
                        "Comprueba permisos, bloqueo y respaldos antes de reparar."), **evidence}


def opencode_check(*, validate_config=False, cwd=None):
    """Read-only diagnosis. Never echo merged config, plugin output or credentials."""
    executable = shutil.which("opencode")
    if not executable:
        return check("OPENCODE", "MISSING", "OpenCode no está en PATH.", "En Windows, comprueba Get-Command opencode.")
    env = {**os.environ, "OPENCODE_DISABLE_AUTOUPDATE": "true", "OPENCODE_DISABLE_PRUNE": "true"}
    candidates = {str(Path(executable).resolve())}
    for directory in os.get_exec_path(env):
        candidate = shutil.which("opencode", path=directory)
        if candidate:
            candidates.add(str(Path(candidate).resolve()))
    working_dir = Path(cwd or Path.cwd()).resolve()
    global_dir = Path(env.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "opencode"
    configured = [global_dir / name for name in ("opencode.json", "opencode.jsonc")]
    for folder in (working_dir, *working_dir.parents):
        for name in ("opencode.json", "opencode.jsonc"):
            configured.extend((folder / name, folder / ".opencode" / name))
    explicit_file = env.get("OPENCODE_CONFIG")
    if explicit_file:
        configured.append(working_dir / Path(explicit_file).expanduser())

    def result(status, detail, suggestion=""):
        return {**check("OPENCODE", status, detail, suggestion), "executable": executable,
                "path_matches": sorted(candidates), "config_files_found": [str(path) for path in configured if path.is_file()],
                "explicit_config_missing": bool(explicit_file and not configured[-1].is_file()),
                "inline_config_present": bool(env.get("OPENCODE_CONFIG_CONTENT"))}

    def invoke(*args, runtime_env=None):
        return subprocess.run([executable, *args], cwd=cwd, env=runtime_env or env, capture_output=True,
                              encoding="utf-8", errors="replace", timeout=12, check=False)

    try:
        version = invoke("--version")
        found = re.search(r"(?m)^v?(\d+\.\d+\.\d+(?:[-+.][\w.-]+)?)\s*$", version.stdout)
        if version.returncode or not found:
            return result("START_FAILED", f"OpenCode --version salió con código {version.returncode}.",
                         "Comprueba manualmente el ejecutable y su PATH.")
        installed = found.group(1)
        if not validate_config:
            return result("CONFIG_NOT_CHECKED", f"OpenCode {installed} detectado.",
                         "Ejecuta este Doctor con --opencode-config desde la carpeta donde falla.")
        help_text = invoke("--help")
        if help_text.returncode or "--pure" not in help_text.stdout + help_text.stderr:
            return result("CONFIG_NOT_CHECKED", f"OpenCode {installed} no anunció --pure.",
                         "Ejecuta opencode debug config localmente y protege la salida, que puede contener secretos.")
        with tempfile.TemporaryDirectory(prefix="gaia-opencode-check-") as isolated:
            root = Path(isolated)
            home = root / "config" / "opencode"
            home.mkdir(parents=True)
            for path in configured[:2]:
                if path.is_file():
                    shutil.copyfile(path, home / path.name)
            runtime_env = {**env, "XDG_CONFIG_HOME": str(home.parent), "XDG_CACHE_HOME": str(root / "cache"),
                           "XDG_DATA_HOME": str(root / "data"), "XDG_STATE_HOME": str(root / "state"),
                           "OPENCODE_DISABLE_MODELS_FETCH": "true"}
            debug = invoke("--pure", "debug", "config", runtime_env=runtime_env)
        if debug.returncode:
            syntax = bool(re.search(r"jsonc?|parse|syntax|trailing comma", debug.stderr, re.I))
            detail = f"OpenCode {installed}. debug config salió con código {debug.returncode}."
            if syntax:
                detail += " La salida indica un posible error de sintaxis o esquema."
            return result("CONFIG_ERROR", detail,
                         "Revisa JSON/JSONC global, del proyecto y OPENCODE_CONFIG. Respalda antes de editar.")
        evidence = result("CONFIG_PARSED", f"OpenCode {installed} cargó la configuración sin plugins externos.")
        try:
            config = json.loads(debug.stdout)
            providers = config.get("provider") or {}
            evidence["configured_providers"] = len(providers)
            evidence["model_configured"] = bool(config.get("model"))
            evidence["providers_with_loopback"] = sum(
                urlsplit(str((provider.get("options") or {}).get("baseURL", ""))).hostname in {"localhost", "127.0.0.1", "::1"}
                for provider in providers.values()
            )
        except (ValueError, TypeError, AttributeError):
            pass
        return evidence
    except subprocess.TimeoutExpired:
        return result("TIMEOUT", "OpenCode superó el plazo de diagnóstico.")
    except OSError as exc:
        return result("START_FAILED", f"No se pudo iniciar OpenCode ({type(exc).__name__}).")


def run(*, validate_opencode_config=False)->dict:
    flags=feature_flags.as_dict(); checks=[]
    checks.append(check('PYTHON','PASS' if sys.version_info[:2]==(3,11) else 'CONFIG_REQUIRED',sys.version.split()[0],'GAIA release targets Python 3.11.'))
    checks.append(check('CORE','PASS','GAIA Core + central authority import path present'))
    checks.append(check('OLLAMA','PASS' if shutil.which('ollama') else 'CONFIG_REQUIRED',shutil.which('ollama') or 'ollama executable not found','Install Ollama only if local LLM is desired.'))
    checks.append(check('GIT','PASS' if shutil.which('git') else 'CONFIG_REQUIRED',shutil.which('git') or 'git executable not found'))
    checks.append(opencode_check(validate_config=validate_opencode_config))
    checks.append(memory_check())
    for item in component_status():
        st='PASS' if item['status']=='READY' else item['status']
        checks.append(check(item['name'].upper(),st,f"{item['distribution']} -> {item['import']}; profile={item['profile']}",item.get('external','')))
        if 'model_status' in item: checks.append(check(item['name'].upper()+'_MODEL','PASS' if item['model_status']=='READY' else 'CONFIG_REQUIRED',item.get('model') or 'GAIA_WAKEWORD_MODEL not configured','Use tools/setup_gaia_wakeword.py with a trusted Gaia ONNX model.'))
    piper_ready=mod('piper'); checks.append(check('PIPER_RUNTIME','PASS' if piper_ready else 'MISSING_DEPENDENCY','API Python de Piper importable' if piper_ready else 'piper module not found','Install Voice/Full profile (piper-tts).'))
    wake_default=ROOT/'assets'/'wakeword'/'gaia.onnx'; wake=os.getenv('GAIA_WAKEWORD_MODEL','').strip(); wake_path=Path(wake) if wake else wake_default
    checks.append(check('GAIA_WAKE_MODEL','PASS' if wake_path.is_file() else 'CONFIG_REQUIRED',str(wake_path),'Train/install an actual Gaia model; no Jarvis fallback is used.'))
    browser_py=ROOT/'.venv-browser'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    browser_playwright=False
    if browser_py.is_file():
        try:
            browser_playwright=subprocess.run([str(browser_py),'-c','import playwright'],capture_output=True,timeout=10).returncode==0
        except Exception: browser_playwright=False
    checks.append(check('CHROMIUM_RUNTIME','DEGRADED' if browser_playwright else 'MISSING_DEPENDENCY','Playwright present in .venv-browser' if browser_playwright else 'Browser sidecar/Playwright missing','Installer runs Chromium install inside .venv-browser; physical launch still needs validation.'))
    checks += [check('PERMISSIONS','PASS','central Permission Layer + Action Host'),check('SAFE_MODE','PASS','fail-closed for effects'),check('KILL_SWITCH','PASS','global effect block'),check('PHYSICAL_WINDOWS','PHYSICAL_VALIDATION_REQUIRED','microphone, speaker, hotkeys, wake accuracy and real desktop control need operator validation')]
    return {'doctor':'2.1-clean-install','read_only':True,'platform':platform.platform(),'flags':flags,'dependency_schema':load().get('schema'),'checks':checks}
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--opencode-config", action="store_true",
                        help="Ask the installed OpenCode to validate the config without external plugins.")
    args = parser.parse_args()
    print(json.dumps(run(validate_opencode_config=args.opencode_config), ensure_ascii=False, indent=2))
