HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.9.2 — Requirements and Acceptance Record

## Estado y alcance

GAIA-AI v0.9.2 es una release de **optimización configurable para laptop** derivada exclusivamente del baseline congelado v0.9.1. No es v1.0, no habilita un modo desktop silencioso y no reemplaza el modelo configurado. El objetivo es reducir trabajo de background, limitar el prompt y exponer diagnósticos suficientes para una medición posterior honesta.

El perfil recomendado para la laptop objetivo es `GAIA_HARDWARE_PROFILE=laptop_balanced` junto con `GAIA_PERFORMANCE_PROFILE=balanced`. El valor `auto` puede resolver un perfil según las señales disponibles; esa detección solo produce política y diagnóstico. No modifica BIOS, ventiladores, plan de energía, prioridad del sistema, instalación de modelos ni configuración de Ollama.

## Criterios de aceptación

| ID | Criterio | Implementación/evidencia | Estado |
|---|---|---|---|
| V092-01 | Versionado coherente Core/PC/protocolo/Android | `config.py`, `lan_protocol.py`, `action_host.py`, `request_envelope.py`, `pubspec.yaml`, Gradle y tests de integración | PASS en sandbox |
| V092-02 | Perfil Hardware/Performance explícito y validado | `HARDWARE_PROFILE`, `PERFORMANCE_PROFILE`, `ResourceGovernor` y `.env.example` | PASS |
| V092-03 | Governor read-only | Solo calcula `policy`; no muta hardware, modelos, power plan o fan control | PASS por inspección y test |
| V092-04 | Hysteresis de presión | Dos muestras altas activan `throttled`; tres bajas restauran `normal` | PASS en `resource_governor_v092_test.py` |
| V092-05 | Batería conservadora | En batería se extienden cadencias, se desactiva proactividad LLM y se difiere consolidation | PASS en test de governor |
| V092-06 | Interactividad con prioridad | La conversación no se cancela ni se limita por el governor; la política solo ajusta scheduler/watchers/background | PASS por contrato de runtime y suite heredada |
| V092-07 | Una generación LLM pesada | `GAIA_MAX_CONCURRENT_LLM_REQUESTS=1` continúa como default y no se introduce paralelismo de generación | PASS por configuración y regresión |
| V092-08 | Prompt laptop bounded | Default `GAIA_MEMORY_CONTEXT_MAX_CHARS=4096`, `GAIA_MEMORY_RELEVANCE_LIMIT=8`; el governor aplica cap de contexto | PASS en `prompt_budget_v092_test.py` y profile |
| V092-09 | Diagnósticos sin contenido | `/api/diagnostics/performance` expone tamaños, tokens aproximados, perfil y política; no guarda prompt/texto/memoria | PASS en `resource_governor_api_v092_test.py` |
| V092-10 | Cachés bounded | Desktop context mantiene TTL corto; Trusted Folders añade TTL configurable e invalidación al escribir | PASS en `cache_contract_v092_test.py` y regresión PC |
| V092-11 | Importación y idle razonables | Perfil registra importación, RSS, startup, cola, scheduler/event engine y backend de embeddings | PASS medido en sandbox mock |
| V092-12 | Compatibilidad y seguridad heredadas | Los 97 contratos v0.9.1 más nuevas pruebas Stage B permanecen en la suite; sin shell libre, eval/exec, self-grant, fuga de tokens o memoria operacional | PASS sujeto a clean release gate |
| V092-13 | Paquete reproducible | Builder allowlist, timestamps fijos, checksum externo, extracción limpia, gate de paquete primero, compileall y tests | Pendiente hasta build final |

## Configuración laptop recomendada

```dotenv
GAIA_HARDWARE_PROFILE=laptop_balanced
GAIA_PERFORMANCE_PROFILE=balanced
GAIA_MEMORY_CONTEXT_MAX_CHARS=4096
GAIA_MEMORY_RELEVANCE_LIMIT=8
GAIA_MAX_CONCURRENT_LLM_REQUESTS=1
GAIA_AUTOMATION_MODE=OFF
LUMEN_PROACTIVE_ENABLED=false
```

La configuración conserva el modelo declarado por el usuario, por ejemplo `qwen3.5:9b`, y no descarga automáticamente modelos, embeddings, Whisper más grandes o un backend de visión. Un perfil `performance` o un aumento de contexto debe ser una elección explícita y puede elevar consumo.

## Límites y compatibilidad

El governor no controla GPU, VRAM, temperatura de ventiladores, plan de energía o prioridad Windows. Cuando la plataforma no entrega una señal, el valor se reporta como `null`, `0`, `not_detected` o `NOT MEASURED`; no se convierte en PASS. Las pruebas físicas de Windows/UIA/SMTC, Android compilado, LAN real, Ollama, GPU RTX, audio y batería/thermal de la laptop permanecen `PENDING` en el sandbox Linux.

## Seguridad preservada

Los eventos, automatizaciones, clipboard, screenshots, UIA y contexto temporal no se convierten automáticamente en memoria semántica. Los diagnostics son size-only. La ownership de sesiones, namespaces, precedence, provenance, token hashing, fail-closed y confirmación de acciones derivan del v0.9.1 y deben permanecer intactos.

## Validación requerida

La validación final se ejecutará desde extracción limpia con `PYTHONDONTWRITEBYTECODE=1`. El orden obligatorio es: checksum, `unzip -tq`, `tests/release_package_test.py` como primer test de aplicación, `compileall`, suite completa, Doctor read-only y comparación de dos builds del mismo source. Los conteos exactos, hashes, skips y valores medidos se escriben en `FINAL_VALIDATION.txt` y `PERFORMANCE_V092.md` después del build definitivo.
