HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

HISTORICAL DOCUMENT — DO NOT USE FOR RC5 OPERATIONS

This document is preserved for historical traceability only. For current RC5 operations use `WINDOWS_RC5_VALIDATION_CHECKLIST.md`, `UPDATE_ROLLBACK_GUIDE.md` and `PHYSICAL_VALIDATION_RC5.md`.

# GAIA-AI v1.0-RC1 — Criterios de integración y recuperación

> **Estado: GAIA-AI v1.0-RC1; nunca v1.0 final.** RC1 contiene la integración contractual de actualización, migración, snapshot, rollback, Doctor modes y safe mode. La finalización de una versión final requiere validación física en Windows, Android y el equipo objetivo; ninguna prueba de sandbox, mock o inspección estática puede sustituirla.

## Objetivo

Preparar una experiencia de instalación, actualización, migración y rollback suficientemente estable para que la siguiente fase pueda validarse en equipos reales. La preparación debe conservar configuración, base de datos, tokens, Trusted Apps/Folders, reglas, rutinas, schedules, backups y logs fuera del árbol de release, sin descargar código automáticamente y sin mezclar módulos de versiones distintas.

La secuencia aprobada es:

```text
release ZIP verificado
  -> doctor previo read-only
  -> backup/snapshot externo
  -> plan de migración version-aware
  -> instalación en carpeta nueva
  -> migración explícita de DB/configuración
  -> doctor posterior
  -> smoke tests
  -> decisión humana de continuar o rollback
```

## Criterios verificables de RC1

| ID | Criterio | Implementación/evidencia prevista | Estado |
|---|---|---|---|
| P-01 | Instalación Windows de un comando | `install-gaia.ps1`, `setup-windows.bat`, venv aislado, imports comprobados y Doctor read-only | PASS contractual; PENDING Windows físico |
| P-02 | El instalador no sobrescribe `.env` válido | Conserva un secreto existente y exige `-GenerateSecret` o corrección manual si es débil | PASS contractual |
| P-03 | Migración version-aware | `tools/gaia_migrate.py` detecta código, schema, downgrade, integrity y compatibilidad antes de actuar | PASS contractual |
| P-04 | Actualización sin auto-descarga de código | El usuario entrega y verifica el ZIP; las herramientas solo inspeccionan/copían datos aprobados | PASS de diseño |
| P-05 | Configuración preservada | Backup/restauración de `.env` privado y comparación de claves no secretas; nunca se imprime el secreto | PASS contractual |
| P-06 | DB preservada | Snapshot SQLite con Backup API, checksum, integridad y schema 9 esperado antes/después | PASS contractual RC1 |
| P-07 | Tokens de dispositivo preservados o revocados explícitamente | Se conserva la tabla hashada en la DB; token perdido se revoca desde PC y se rota, nunca se exporta en claro | PASS contractual; prueba de rotación requerida |
| P-08 | Trusted Apps/Folders y reglas preservadas | Se validan tablas/archivos allowlisted y conteos antes/después; no se importan rutas fuera de scope | PASS de diseño; validación física pendiente |
| P-09 | Backup previo opcional pero seguro | Brain Backup y snapshot previo con manifest, checksum, no sidecars y no replay de acciones | PASS heredado; flujo documentado |
| P-10 | Health check posterior | Doctor, health endpoint, DB integrity, versión, schema, modo, kill switch y dependencias | PASS contractual |
| P-11 | Rollback estable | Nueva carpeta, snapshot externo, restauración explícita y source preservado sin borrar la única DB | PASS contractual; prueba física requerida |
| P-12 | Compatibilidad Core/PC/Android/protocolo | Version matrix, feature negotiation y mensaje claro para mismatch | PASS contractual; Android físico pendiente |
| P-13 | API/error contract stability | Revisión de rutas, status codes, claves JSON, errores 401/403/404/409/422 y no exposición de secretos | PASS contractual |
| P-14 | Token rotation | Device token, host token y master secret tienen procedimiento y pruebas separadas | Device rotation PASS heredado; host/master pendiente de hardware/procedimiento |
| P-15 | Threat model | Amenazas local app, LAN, teléfono perdido, token robado, prompt injection, filename/UI text, stale target, escalation y host spoofing | PASS documental; mitigación física pendiente |
| P-16 | Release signing roadmap | Plan futuro de firma verificable; no se simula firma ni se incluye clave privada | PASS documental; firma real pendiente |
| P-17 | APK signing roadmap | Debug-only actual; release signing queda pendiente de keystore/CI/procedimiento físico | PENDING |
| P-18 | Matriz física exhaustiva | Casos PC, Core, Ollama, chat, fast action, apps, audio, media, ventanas, UIA, capture, voice, terminal, workspace, permisos, Android y automation | PASS documental; ejecución física pendiente |

## Reglas de conservación

La carpeta de release contiene código y ejemplos; no contiene `.env`, DB, tokens, Trusted Apps/Folders personales, reglas personales, logs privados, capturas, audio, caches ni backups. La migración opera sobre copias y conserva la fuente hasta que el health check posterior termine.

La configuración se preserva con una copia privada de `.env`; las claves nuevas se muestran como diferencias de nombres, nunca con valores secretos. La DB se respalda usando SQLite Backup API o un snapshot consistente, incluyendo schema 9 de Advanced Memory y la migración explícita 8→9 soportada. Device tokens se conservan únicamente como hashes y metadata de la DB; no se exportan tokens claros. Si el usuario perdió un teléfono, la acción correcta es revocar su device token y emitir uno nuevo.

Trusted Apps/Folders y reglas, rutinas y schedules son datos de configuración durable y deben conservarse fuera del ZIP. Su restauración debe comprobar ownership, scopes explícitos, versión de policy y ausencia de paths peligrosos. No se reactivan automáticamente schedules vencidos, pending actions o locks efímeros.

## Compatibilidad y actualización

La matriz RC1 es `Core 1.0.0-rc1-pc`, `protocol 1.0-RC1`, `Action Host 1.0.0-rc1-pc`, Android `1.0.0-rc1+1` y SQLite schema 9. Un source v0.9.2/schema 9 se conserva directamente; schema 8 se acepta solo mediante el flujo explícito y validado de migración. Un cliente con protocol incompatible debe recibir un error claro, no una negociación silenciosa que habilite capabilities. Feature negotiation conserva el filtrado conocido y no concede `actions_execute` o `action_host` sin autenticación y opt-in.

La actualización no descarga código, no ejecuta scripts recibidos desde una conversación, no usa `shell=True`, `eval` ni `exec`, y no copia selectivamente módulos entre releases. La instalación recomendada usa una carpeta nueva y solo después de validación permite retirar la carpeta anterior.

## Rollback

El rollback es por carpeta y por snapshot, no por edición selectiva. Se detienen Core, GUI, terminal, scheduler, Remote Action Host y proyectos iniciados por GAIA; se guarda Doctor posterior al fallo; se conserva la carpeta nueva como evidencia; se restaura la carpeta estable; y se restaura la DB previa únicamente si la copia está íntegra y corresponde al código restaurado.

Nunca se borra la única DB, no se restaura un token claro desde logs, no se copian `.env` o tokens a la carpeta de release y no se mezclan `api.py`, `config.py`, `authz.py`, `desktop_api.py` o módulos de distintas versiones. Un downgrade desde schema 8 requiere una copia compatible anterior o un Brain Backup cuyo formato sea soportado; no se promete downgrade destructivo automático.

## Estabilidad de API y errores

Antes de declarar una versión final se revisará una tabla de contratos con ruta, método, autenticación, capability, ownership, status codes, forma de éxito, forma de error y campos sensibles. Se consideran bloqueantes: cambiar 401 por 403 para credenciales inválidas, convertir un 404 de ownership en una filtración de existencia, aceptar un 422 como ejecución, devolver tokens en JSON/logs, o cambiar `VerifiedActionResult` de modo que un resultado no verificado parezca exitoso.

## Signing roadmap

El proyecto debe documentar, no fingir, firma de releases. La futura cadena deberá producir un digest reproducible, firmarlo con una clave protegida fuera del repositorio, publicar la clave pública por un canal independiente y verificar firma antes de instalar. RC1 no contiene una clave privada ni afirma que el ZIP esté firmado.

Android permanece en estado debug/no firmado para distribución release hasta definir keystore, almacenamiento seguro, rotación, CI y verificación en dispositivo. Un APK debug no es evidencia de una release Android firmada.

## Definition of done de RC1

RC1 queda contractual y documentalmente completa cuando existen el helper version-aware con apply/rollback/safe mode explícitos, sus pruebas de plan/compatibilidad/no sobrescritura, este documento, `THREAT_MODEL.md`, `PHYSICAL_VALIDATION_V100.md`, la guía de actualización/rollback, los modos Doctor, los artefactos reproducibles y el índice de blockers. Queda explícitamente abierta la validación en Windows, Android físico, LAN/TLS, Ollama real, audio, UIA/SMTC, displays y aplicaciones externas.
