HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.8.1 — Requirements

## Alcance

v0.8.1 es una release de **hardening y rendimiento** condicionada a que v0.8.0 pase sus gates. No incorpora un nuevo subsistema mayor ni modifica el modelo de autoridad. Mantiene el Event Engine, scheduler, watchers, notificaciones, bridge de rutinas, preflight, kill switch y resultado verificado de v0.8.0.

## Criterios de aceptación

| ID | Criterio | Evidencia requerida | Estado |
|---|---|---|---|
| H-01 | El Core, protocolo, host y companion declaran 0.8.1 coherentemente. | `config.py`, `lan_protocol.py`, `action_host.py`, `remote_action_host.py`, envelope y contratos Android. | PASS contractual |
| H-02 | No se añade shell libre, eval, exec, comando en reglas ni bypass de preflight. | Grep estático y regresión de seguridad. | PASS |
| H-03 | La deduplicación no retiene indefinidamente claves de eventos descartados por backpressure. | `automation_hardening_v081_test.py`, métrica `dedup_entries`. | PASS |
| H-04 | Eventos dirigidos no escanean reglas no relevantes cuando existe selector por event type. | `list_rules_for_event()` y fallback conservador. | PASS |
| H-05 | Scheduler consulta únicamente schedules vencidos mediante la ruta indexed/bounded. | `due_before`, `idx_schedules_due`, `EXPLAIN QUERY PLAN`. | PASS |
| H-06 | Queue, payload, reglas, schedules, notifications y watcher outputs siguen bounded. | Tests v0.8 heredados y fuzz bounded v0.8.1. | PASS |
| H-07 | Imports pesados siguen lazy y startup no carga Whisper, UIA, SMTC, audio ni captura sin solicitar la capability. | Inspección de imports y `profile_v081.py`. | PASS contractual |
| H-08 | Android evita reconnect polling agresivo y usa jitter bounded con máximo de intentos. | `ChatScreen`, timer cancelable y revisión estática. | PASS contractual |
| H-09 | Automatización determinista no consume LLM de fondo ni compite con chat interactivo. | `automation_background_priority_v080_test.py` y E2E. | PASS |
| H-10 | Entradas largas, Unicode, IDs vacíos, operadores inválidos, fechas inválidas y traversal se rechazan o acotan. | `automation_hardening_v081_test.py` y tests de seguridad previos. | PASS contractual |
| H-11 | El perfil de startup/idle mide, no inventa: import ms, runtime startup, queue depth, running state y RSS observable. | `tools/profile_v081.py` ejecutado con backend mock y temp dir. | PASS |
| H-12 | ZIP limpio, checksum, package gate, compileall y suite completa pasan desde extracción nueva. | Log de clean validation y archivos `.sha256`. | PASS |

## Parámetros de rendimiento observables

El perfil no fija un umbral artificial dependiente de la máquina. Registra métricas comparables del mismo entorno y evita presentar el sandbox Linux como benchmark de Windows, Android, Ollama, GPU o audio. Las optimizaciones de esta versión son: poda de dedup, selector de reglas por evento, consulta de schedules due con índice y reconnect jitter en Android.

## Compatibilidad y seguridad

La authority boundary de v0.8.0 permanece vigente. Los eventos siguen siendo datos, el LLM no cambia policies ni grants, la rutina unattended se mantiene en riesgo máximo 2, el kill switch gana a cualquier automatización y el resultado factual depende de `VerifiedActionResult` con evidencia de host.

## Gates físicos

Flutter/analyze/APK, Android físico, Windows UIA/SMTC/display, Action Host sobre aplicaciones reales, micrófono, Whisper, Edge TTS, GPU, Ollama/Qwen real, LAN, TLS y firewall continúan como **PENDING** cuando el equipo objetivo no esté disponible. No se convierten en FAIL de código ni en PASS físico por inferencia.

## Rollback

Si un equipo no supera el smoke test de v0.8.1, debe conservarse el ZIP v0.8.0 y seguir `ROLLBACK.md`. No se mezclan binarios de una versión con una SQLite no respaldada, no se replayan pending actions y no se reactivan schedules vencidos sin decisión explícita.
