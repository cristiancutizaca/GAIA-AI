# AUDIT — GAIA-AI v0.5.3

## Resumen ejecutivo

GAIA-AI v0.5.3 es un hotfix sobre v0.5.2. No cambia SQLite schema 5, el contrato action/plan, RBAC, ownership, ActionCoordinator, Android ni LAN. Corrige dos defectos de distribución y portabilidad: el ZIP v0.5.2 carecía de `.env.example` y `.gitignore`, y el Brain Backup deja de construir manifests desde contenido temporal potencialmente afectado por WAL/SHM.

> **Conclusión.** La evidencia de v0.5.3 separa la carpeta de trabajo del artefacto entregado. El release se construye mediante allowlist, se reabre y compara con staging, se extrae en una carpeta aislada y se vuelve a probar desde allí. Brain Backup usa payload canónico, snapshot autónomo, verificación de ZIP y round-trips reales con SQLite WAL. Ollama/Qwen, GPU, audio, LAN física y Android siguen pendientes de validación física.

## Hallazgos baseline v0.5.2

| Hallazgo | Reproducción | Corrección v0.5.3 |
|---|---|---|
| Falta `.env.example` en ZIP final | La extracción baseline no lo contiene; `fresh_install_test.py` termina en `FileNotFoundError` | Dotfile restaurado y exigido por build/test |
| Falta `.gitignore` en ZIP final | La extracción baseline no lo contiene | Dotfile restaurado con reglas de secretos y runtime |
| Riesgo de manifest WAL/SHM | La implementación previa enumeraba `root.iterdir()` después del snapshot e integrity check | Allowlist explícita, sidecars prohibidos y ZIP verificado |
| Reproducción independiente de `v04_test.py` | Pasó en el baseline disponible | No se afirma que ese comando haya fallado; se añade prueba WAL real específica |

## Matriz de controles v0.5.3

| Riesgo | Control | Evidencia |
|---|---|---|
| Instalación desde ZIP incompleta | `.env.example`, `.gitignore`, scripts, Doctor y docs incluidos | `release_package_test.py` |
| Secreto o DB en release | Allowlist y build fail-closed para `.env`, DB, logs, audio, tokens, caches y `.git` | `tools/build_release.py`, package test |
| Release distinto del staging | ZIP reabierto, `testzip()` y comparación exacta de entradas | `tools/build_release.py` |
| Manifest declara archivo inexistente | Payload canónico `BRAIN_BACKUP_FILES`; hashes solo después de confirmar existencia | `brain_backup.py` |
| WAL/SHM entra en Brain Backup | Sidecars `-wal`, `-shm`, `-journal` rechazados explícitamente | `brain_backup_wal_test.py`, portability test |
| Backup generado no es restaurable | Verificación inmediata de names, manifest, hashes e integridad | `create_brain_backup()` y `backup_integrity_test.py` |
| DB activa degradada al crear snapshot | SQLite Backup API en destino temporal; journal mode activo no se cambia | `brain_backup_wal_test.py` |
| Restore deja conexiones/sidecars inconsistentes | Checkpoint WAL activo antes de reemplazar DB; temp target validado y eliminado | `brain_backup.py`, portability test |
| Dos backups pisan staging | Lock de thread alrededor de creación completa | `brain_backup_portability_test.py` |
| Round-trip falso | DB WAL real, conexión abierta, 12 create→restore y comparación de estado | `brain_backup_portability_test.py` |
| Restore debilitado | Continúa rechazando traversal, duplicates, extras, missing, hash mismatch, schema y SQLite corrupta | `backup_integrity_test.py` |
| Acción maliciosa del LLM | Parser atómico, catálogo, riesgo máximo 2 y plan máximo 3 | Regresiones v0.5.2 |
| Shell o ejecución del prompt | Allowlist y listas de argumentos; greps prohibidos | `security_regression_test.py` |
| RBAC/ownership regresan | Principal, voice+chat, cancelación owner y `permission_level` metadata preservados | Regresiones v0.5.2 |

## Brain Backup portable

El payload permitido es exactamente `memory.db`, `memory_export.json`, `profile.json`, `preferences.json`, `state.json`, `personality.py` y `config.json`. `manifest.json` se trata como metadata del archive y no se declara dentro de `files`. El código no enumera indiscriminadamente el staging; crea cada archivo conocido, confirma que existe, calcula SHA-256, escribe manifest, construye el ZIP con la misma lista y lo reabre antes de persistir estado de éxito.

El snapshot se produce en una copia temporal con SQLite Backup API y journal mode `DELETE` de esa copia únicamente. La DB activa conserva su configuración WAL. Restore valida el contenido completo antes de tocar la DB activa y ejecuta checkpoint del WAL activo antes del reemplazo. No se ignoran faltantes: si el manifest declara un archivo que no está, o aparece un extra, el restore rechaza el backup.

## Distribución y secretos

`tools/build_release.py` exige los dotfiles seguros y fuentes obligatorias, copia mediante allowlist, bloquea archivos privados y genera timestamps ZIP fijos para reproducibilidad. El `.env.example` contiene defaults y un placeholder visible, nunca un secreto real. El `.gitignore` cubre `.env`, DB, WAL/SHM, logs, backups, tokens, audio y caches. El SHA-256 se calcula solo después de validar el ZIP y la extracción final.

## Límites físicos y de versiones

Python 3.11 es el objetivo recomendado y oficialmente previsto para el equipo del usuario. Esta validación se ejecuta en Python 3.12; Python 3.13 no fue probado. No se afirma validación de Ollama/Qwen, GPU, micrófono, Whisper, Edge TTS, reproductores, VS Code, navegador, ventanas activas, proyectos trusted, LAN/TLS ni APK Android. Flutter/Dart no está disponible en el sandbox.
