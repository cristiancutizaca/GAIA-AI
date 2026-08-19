# TEST REPORT — GAIA-AI v0.5.3

## Alcance

Esta release se valida en dos superficies distintas. **WORKTREE TESTS** comprueba el código durante el desarrollo; **FINAL ZIP EXTRACTED TESTS** debe ejecutarse después de construir, extraer en una ruta limpia y cambiar el working directory a esa copia. El backend es mock y las bases son temporales; estos resultados no certifican Ollama/Qwen, GPU, audio físico, LAN o Android.

## Baseline v0.5.2 desde ZIP

La extracción independiente de `GAIA-AI-v0.5.2-final.zip` confirmó que `.env.example` y `.gitignore` no estaban presentes. `fresh_install_test.py` falló con `FileNotFoundError` al intentar copiar `.env.example`. `v04_test.py` pasó en la reproducción disponible; no se afirma que el fallo WAL/SHM haya sido reproducido por ese comando. El baseline completo está en `BASELINE_V052.txt`.

## WORKTREE TESTS

| Suite | Resultado | Cobertura |
|---|---:|---|
| `tests/release_package_test.py` | PASS | Dotfiles, docs, estructura, higiene y git safety |
| `tests/brain_backup_wal_test.py` | PASS | DB activa WAL preservada; sidecars excluidos |
| `tests/brain_backup_portability_test.py` | PASS | Conexión abierta, WAL real y 12 round-trips create→restore |
| `compileall` | PASS | Sintaxis Core, PC, tests y tools |
| Regresiones históricas v0.3–v0.5.2 | PASS | Contratos y seguridad heredados |

Los tres tests nuevos pasaron en el árbol de trabajo y volvieron a pasar desde la extracción final. La corrida completa también pasó después de estabilizar la DB activa durante restore.

## Brain Backup portable

`create_brain_backup()` usa `BRAIN_BACKUP_FILES` explícito: `memory.db`, `memory_export.json`, `profile.json`, `preferences.json`, `state.json`, `personality.py` y `config.json`. El manifest se calcula solo después de confirmar existencia y cerrar las operaciones temporales; el ZIP se reabre antes de devolver éxito. `memory.db-wal`, `memory.db-shm` y `memory.db-journal` no están permitidos.

`brain_backup_portability_test.py` fuerza `PRAGMA journal_mode=WAL`, mantiene otra conexión abierta, crea actividad, realiza 12 iteraciones de backup y restore en una DB temporal y verifica que el estado A se recupere después de introducir el estado B. `brain_backup_wal_test.py` confirma que la DB activa continúa en WAL después del backup. Restore sigue rechazando tampering, missing, extra, traversal, duplicate, hash mismatch, schema desconocido y SQLite corrupta mediante las regresiones existentes.

## FINAL ZIP EXTRACTED TESTS

La tabla siguiente corresponde a una extracción limpia de `GAIA-AI-v0.5.3-final.zip`; la suite se ejecutó con el working directory dentro de esa copia. No se sustituyó por `unzip -tq` solamente.

| Control | Resultado | Evidencia |
|---|---:|---|
| Estructura final y dotfiles | PASS | `release_package_test.py` desde extracción |
| Fresh install desde extracción | PASS | `fresh_install_test.py` desde extracción |
| Brain Backup WAL round-trip | PASS | WAL test y 12 round-trips desde extracción |
| Suite histórica completa | PASS | listado reproducible abajo |
| Doctor read-only | PASS | JSON desde extracción; `read_only` presente |
| Package hygiene/path safety | PASS | build allowlist, ZIP test y package test |

## Comandos reproducibles desde una raíz extraída

```bash
python3 tests/release_package_test.py
python3 tests/brain_backup_wal_test.py
python3 tests/brain_backup_portability_test.py
python3 -m compileall -q lumen-core lumen-pc tests tools
python3 tests/gui_import_test.py
python3 tests/smoke_test.py
python3 tests/v03_test.py
python3 tests/v04_test.py
python3 tests/v041_test.py
python3 tests/v05_test.py
python3 tests/v051_test.py
python3 tests/action_plan_llm_test.py
python3 tests/device_permissions_test.py
python3 tests/device_touch_test.py
python3 tests/brain_backup_scheduler_test.py
python3 tests/startup_test.py
python3 tests/db_upgrade_test.py
python3 tests/backup_integrity_test.py
python3 tests/process_safety_test.py
python3 tests/security_regression_test.py
python3 tests/llm_health_test.py
python3 tests/fresh_install_test.py
python3 tests/vault_missing_test.py
python3 tests/gui_import_test.py
python3 tests/gui_action_contract_test.py
python3 tests/terminal_plan_test.py
python3 tests/voice_permissions_test.py
python3 tests/request_ownership_test.py
python3 tests/permission_level_test.py
python3 tests/plan_post_action_test.py
python3 tools/gaia_doctor.py --json
```

## Límites

| Área | Estado |
|---|---|
| Python | 3.11 es objetivo recomendado; 3.12 es el entorno validado; 3.13 no fue probado |
| Ollama/Qwen | Health gate, errores y mock; servicio, modelo, contexto y rendimiento reales pendientes |
| GPU | No se afirma reparto CPU/GPU ni velocidad sin drivers y hardware |
| Micrófono/Whisper/TTS | Orquestación y errores mock; captura, Edge TTS y altavoces pendientes |
| GUI visual/ventana activa | Importación y callbacks mock; revisión por sistema pendiente |
| Android | Dart/pubspec y secure storage estáticos; SDK no instalado, sin APK |
| LAN/TLS | Opt-in implementado; TLS, firewall y red confiable pendientes |
| Proactividad | Reglas implementadas, automática apagada por defecto |

## Validación manual recomendada

En el equipo objetivo, extrae el ZIP final, crea `.env` desde `.env.example`, instala Python 3.11 y dependencias, configura un secreto fuerte, instala manualmente `qwen3.5:9b` si corresponde, inicia Ollama y ejecuta Doctor. Prueba conversación, diagnóstico, memoria, voz, cancelación, confirmación, plan de dos pasos y Brain Backup. No marques proyectos como `trusted` sin revisar cada comando.
