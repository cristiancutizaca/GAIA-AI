HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.5.4.1 — Requisitos y trazabilidad

## Propósito

GAIA-AI v0.5.4.1 es una revisión correctiva pequeña sobre v0.5.4. No es una expansión hacia v0.6. Conserva la arquitectura FastAPI/SQLite, el namespace `LUMEN_*`, el modelo configurado, los clientes PC, Android heredado, Brain Backup, safe apps, deduplicación, semaphore y GUI busy.

| Requisito | Implementación | Evidencia |
|---|---|---|
| Grounding general | Estado explícito de request, capability failure determinista y guard de verbos de efecto sin nombres de apps | `lumen-core/routes/api.py`, `tests/action_grounding_test.py` |
| Hechos post-action | `VerifiedActionResult` inmutable con `action`, `success`, `message`, `data` y `execution_verified` | `routes/api.py`, `tests/v041_test.py`, `tests/plan_post_action_test.py` |
| Inyección post-action | La salida del LLM se conserva como texto; no se vuelve a clasificar ni despachar | `tests/v041_test.py`, `action_grounding_test.py` |
| v04 | Se espera `generated_by_llm=False` para `open_vscode` determinista; no se elimina la assertion de completion | `tests/v04_test.py` |
| v041 | El fixture usa `git_status`, que fuerza la ruta de verbalización; el intento `shutdown` permanece texto | `tests/v041_test.py` |
| GUI | El test crea widgets falsos mínimos; la GUI productiva mantiene busy state | `tests/gui_action_contract_test.py`, `tests/gui_busy_test.py` |
| Timeout | Cliente calcula `max(60, requested client, post-action + 15)` y ambos parsers toleran env inválido | `config.py`, `desktop_api.py`, `timeout_config_test.py` |
| Slow post-action | Se simula respuesta más lenta que post-action y menor que timeout cliente | `tests/timeout_slow_post_action_test.py` |
| Seguridad heredada | Sin `shell=True`, `os.system(`, `eval(`, `exec(`); safe apps y ActionCoordinator intactos | grep final, regresiones y `safe_apps_test.py` |
| Release | Allowlist, dotfiles seguros, modos ZIP normalizados, limpieza y validación desde extracción | `tools/build_release.py`, `release_package_test.py`, `FINAL_VALIDATION.txt` |

## Baseline independiente

El ZIP v0.5.4 se verificó antes de modificarlo. La auditoría limpia reprodujo tres fallos: la expectation obsoleta de `tests/v04_test.py`, la falta de ejecución de la ruta post-action en `tests/v041_test.py` por usar una acción determinista y el `RecursionError` del fixture incompleto de `gui_action_contract_test.py`. El problema de grounding limitado por nombres de aplicaciones fue reproducido conceptualmente y se corrigió con estado de request y capability failure, no ampliando una regex de aplicaciones.

La suite final de v0.5.4.1 se ejecuta dos veces conceptualmente: primero desde el worktree limpio y después desde una nueva extracción del ZIP final. El reporte final debe conservar ambas evidencias y no tratar `FINAL_VALIDATION.txt` como evidencia previa suficiente.

## Fuera de alcance

No se añaden Android, LAN, TLS server, Spotify playback, browser automation, screen automation, mouse autonomy, acceso remoto Android→PC, multi-agent, agentes recursivos, niveles 3–4, cambio de modelo, ni rediseño de personalidad. La validación física de Windows, Ollama, GPU, micrófono, Whisper, Edge TTS, APK y GUI visual se reporta separadamente y no se inventa desde el sandbox.
