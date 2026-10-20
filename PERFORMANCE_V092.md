# GAIA-AI v0.9.2 — Performance Record

## Método

Las mediciones siguientes corresponden a una ejecución del script `tools/profile_v092.py` en una extracción de trabajo v0.9.2, con DB temporal, backend LLM `mock`, `GAIA_HARDWARE_PROFILE=laptop_balanced`, automatización `ROUTINES` únicamente para observar el runtime y `PYTHONDONTWRITEBYTECODE=1`. El script no ejecuta capabilities del host y no es un benchmark de la laptop ASUS TUF objetivo.

El perfil mide importación de módulos seleccionados, retrieval determinista de memoria, una preparación de prompt, arranque/idle del runtime y estado read-only del governor. Los números pueden variar entre ejecuciones por carga del sandbox; no se presentan como SLA ni como medición física de Windows.

## Última medición de trabajo registrada

| Métrica | Valor observado | Interpretación |
|---|---:|---|
| Perfil solicitado/efectivo | `laptop_balanced` / `laptop_balanced` | Configuración explícita del perfil |
| Import de módulos seleccionados | 69.862 ms | Medición del proceso de perfil |
| RSS después de import | 27.188 MB | `ru_maxrss`; no es working set Windows |
| Retrieval bruto | 6.574 ms | 12 resultados, `limit=12`, `max_chars=2400` |
| Items almacenados de muestra | 24 | DB temporal, una namespace de perfil |
| Contexto retrieval bruto | 640 caracteres | Truncado por `max_chars=2400` en selección de texto |
| Prompt memory item limit | 8 | Límite efectivo en `balanced` laptop |
| Prompt context budget | 4096 caracteres | Cap aplicado por config/governor |
| Prompt total chars | 3525 | Solo métrica numérica; no se guarda texto |
| Runtime startup | 104.496 ms | Incluye start y espera de readiness de 100 ms |
| Idle queue depth | 0 | Cola vacía en el instante observado |
| Idle scheduler/event engine | `true` / `true` | Runtime puede estar listo sin trabajo de evento |
| Idle RSS final | 55.141 MB | `ru_maxrss` acumulado del proceso; no benchmark físico |
| Concurrent background policy | 1 | No se añade paralelismo de generación |
| Watcher/scheduler multipliers | 1.5 / 1.5 | Política balanced laptop |
| Keep-alive recomendado | `5m` | Política informativa; no muta transporte Ollama |
| Proactividad LLM por minuto | 1 | Reserva de política; proactividad global seguía apagada por defecto |
| Consolidation defer | `false` | No hubo señal real de batería/thermal |
| Embeddings | `false` | Backend opcional desactivado |

## Señales no disponibles en el sandbox

El host de perfil fue Linux y no expuso psutil utilizable para varias señales. Por ello el mismo registro reportó `logical_cpus=6`, pero `ram_mb=0`, `cpu_percent=null`, `memory_percent=null`, `process_rss_mb=null`, `temperature_c=null`, `battery_present=false`, `on_ac=null` y `gpu_info=not_detected`. Estos valores significan **NOT MEASURED/NOT DETECTED**, no consumo cero ni PASS térmico.

Las siguientes mediciones permanecen `PENDING` hasta una ejecución física autorizada en Windows: temperatura sostenida y throttling de la ASUS TUF, batería/AC real, RAM/VRAM, GPU RTX 3050, Ollama/Qwen real, audio/Whisper/TTS, UIA/SMTC, múltiples monitores, LAN y duración de sesiones largas. No se fabrican valores para cerrar esos gaps.

## Contratos ejecutados

| Área | Evidencia |
|---|---|
| Perfiles, batería y hysteresis | `tests/resource_governor_v092_test.py` |
| Diagnostics size-only | `tests/resource_governor_api_v092_test.py` |
| Presupuesto de prompt | `tests/prompt_budget_v092_test.py` |
| Caché TTL e invalidación | `tests/cache_contract_v092_test.py` |
| Runtime idle y cola bounded | `tools/profile_v092.py`, regresión automation |
| Memoria/ownership/provenance heredada | `advanced_memory_v091_hardening_test.py`, `memory_security_matrix_v091_test.py` |

## Decisiones de optimización

El perfil balanced reduce cadencias de background y limita la selección de memoria que entra al prompt; no reduce ni reemplaza el modelo configurado. Interactive chat conserva prioridad y no se cancela por presión. En batería o presión sostenida, el governor difiere consolidation y apaga la proactividad LLM reservada. La configuración de keep-alive se expone como política para una futura integración explícita; v0.9.2 no muta de forma silenciosa el cliente Ollama.

## Reproducibilidad y release

Esta tabla es de desarrollo y debe actualizarse con la salida exacta del build final. El informe definitivo debe incluir el SHA-256 del ZIP de proyecto y docs, el conteo de archivos, el resultado del gate de paquete primero, compileall, suite completa desde extracción limpia y dos reconstrucciones byte-idénticas. Las diferencias de tiempos entre corridas no invalidan el criterio de reproducibilidad del archivo, que se verifica por hash.
