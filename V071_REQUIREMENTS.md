HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS

This document is preserved for historical traceability only. For current RC6 operations use WINDOWS_RC6_VALIDATION_CHECKLIST.md, UPDATE_ROLLBACK_GUIDE.md and PHYSICAL_VALIDATION_RC6.md.

# GAIA-AI v0.7.1 — Requisitos y evidencia

## Propósito

La versión 0.7.1 es una hardening release sobre la base v0.7.0. Su objetivo es cerrar ambigüedades de instalación, scopes, resultados, UIA, routing contextual, trust de aplicaciones y scaffold Android sin ampliar el perímetro de ejecución insegura. La versión solo se considera aceptable cuando una capability tiene routing utilizable, validación de parámetros, política de permisos, executor real o degradación honesta y pruebas reproducibles.

## Matriz de aceptación

| Requisito | Implementación | Evidencia automatizada | Estado físico |
|---|---|---|---|
| Instalador con import-check real | `install-gaia.ps1` ejecuta un probe Python y conserva su exit code | `installer_execution_contract_v071_test.py` | **PASS** contractual; instalación Windows posterior |
| Scope autoritativo único | `lumen-core/resource_scope.py` resuelve scopes compuestos y descripción humana | `resource_scope_v071_test.py`, `resource_scope_contract_api_v071_test.py` | **PASS** contractual |
| Transporte de permisos sin reconstrucción local | Core emite `permission_entries` y `resource_scope_version`; PC/Android los consumen | `client_scope_display_v071_test.py`, inspección estática Android | **PASS** contractual |
| Grants persistentes de alcance explícito | `ALWAYS_ALLOW`/`ALWAYS_DENY` rechazan vacío, wildcard y unresolved | `persistent_scope_v071_test.py`, `resource_scope_v071_test.py` | **PASS** contractual |
| Semántica de resultado explícita | `SUCCESS`, `UNAVAILABLE`, `DENIED`, `CANCELLED`, `PARTIAL`, `FAILED` y flags separados | `result_semantics_v071_test.py` | **PASS** contractual |
| No falsear backend ausente | `UNAVAILABLE` fuerza `success=false`, `execution_verified=false` y `capability_available=false` | `result_semantics_v071_test.py`, `audio_capability_v063_test.py` | **PASS** con backend simulado ausente |
| Observación separada de efecto | `observation_completed` no se interpreta como `effect_verified`; completion exige prueba coherente | `result_semantics_v071_test.py`, `v041_test.py`, `v04_test.py` | **PASS** contractual |
| Compatibilidad legacy acotada | Payloads host antiguos con `execution_verified=true` se normalizan; `success=true` solo no prueba nada | `remote_action_e2e_v062_test.py`, `remote_action_host_test.py`, `result_semantics_v071_test.py` | **PASS** contractual |
| Riesgo UIA dinámico | Tokens destructivos, críticos y sensibles pueden elevar el riesgo antes del efecto | `dynamic_uia_risk_v071_test.py` | **PASS** pre-flight; **PENDING** Windows UIA físico |
| UIA stale-target | `expected_target` y la identidad de ventana se validan antes de lectura o mutación | `natural_routing_v071_test.py`, `v070_workspace_plan_test.py` | **PASS** contractual; **PENDING** handles Windows reales |
| Protección de password | Controles password se redactan; `set_value` sensible se rechaza | `v070_observation_contract_test.py`, `natural_routing_v071_test.py` | **PASS** contractual; **PENDING** control Windows físico |
| Routing contextual natural | Frases de media, captura, UIA, campos, workspace y referents se enrutan solo a intents allowlisted | `natural_routing_v071_test.py` | **PASS** contractual; **PENDING** host físico |
| Contexto efímero | Foreground snapshot tiene TTL, se inyecta solo cuando es relevante y no se persiste | `v070_context_injection_test.py`, `v070_observation_contract_test.py` | **PASS** contractual; **PENDING** captura Windows |
| Safe App identity | Trust de ejecutable usa ruta canónica y fingerprint SHA-256; binario modificado invalida trust | `app_discovery_test.py`, `safe_apps_test.py` | **PASS** contractual; **PENDING** Windows físico |
| Adapters code-owned | Registry fijo para VS Code; no hay loader dinámico ni comandos del LLM | `capability_registry_test.py`, `security_regression_test.py`, `v070_workspace_plan_test.py` | **PASS** contractual |
| Media por OS SMTC | Controles allowlisted; mock/degrade honesto; sin credenciales ni scraping | `media_capability_v070_test.py` | **PASS** mock/degrade; **PENDING** SMTC Windows |
| Android build-ready | Wrapper oficial Gradle 8.2, estructura Android y transporte de permisos | `android_scaffold_v071_test.py`, `android_onboarding_contract_test.py` | **PASS** estático/Gradle; Flutter/APK **PENDING** |
| No shell/eval/exec/coordenadas | Action Engine y adapters usan allowlists, argumentos estructurados y no aceptan control libre | `process_safety_test.py`, `security_regression_test.py`, `v063_p0_security_test.py` | **PASS** contractual |
| Release reproducible | Allowlist, dotfiles, exclusión de runtime/secretos/bytecode/ZIP, reapertura y SHA-256 | `tools/build_release.py`, `release_package_test.py` | **PASS** al finalizar gate limpio |

## Invariantes de seguridad

La release no es aceptable si vuelve alcanzable cualquier shell arbitrario, si la salida del modelo se trata como código ejecutable, si UIA acepta coordenadas crudas, si se exponen valores password, si un ejecutable no confiable recibe interacción UIA, si un target se vuelve a resolver después de confirmar, si un cambio de binario conserva trust persistente, si una sesión media usa credenciales del proveedor, o si Android evita Permission Memory, ownership y `VerifiedActionResult`.

Un resultado `UNAVAILABLE` nunca puede ser presentado como éxito o ejecución verificada. Un resultado read-only debe declarar `observation_completed` y no `effect_verified`. Una mutación debe declarar `effect_verified` y solo se verbaliza como completada cuando `execution_verified` es verdadero. Los claims posteriores del modelo no pueden modificar la acción, estado, datos, rutas ni hechos del resultado estructurado.

Los grants `ALWAYS_ALLOW` y `ALWAYS_DENY` solo pueden persistirse para un recurso explícito y resoluble. No se aceptan scopes vacíos, wildcard o unresolved. El contexto activo se mantiene efímero, se limita al contenido relevante y no se incorpora automáticamente a la memoria permanente o a Brain Backup.

## Interpretación de estados

**PASS** significa que el comportamiento está demostrado por tests deterministas de sandbox o por un contrato de código que no requiere un sistema Windows/Flutter físico. **PENDING** significa que la implementación y el contrato existen, pero la dependencia física no está disponible. PENDING no es FAIL, pero tampoco se presenta como validación física.

La validación de esta release se ejecuta con Python 3.12 en Linux; Python 3.11 es el objetivo recomendado para Windows. El backend LLM de la suite es mock y los tests aíslan sus datos temporales. Flutter, Android SDK, Windows UIA/SMTC, displays físicos, micrófono, TTS, GPU, Ollama real y LAN/TLS físico permanecen sujetos a validación posterior en el equipo objetivo.

## Reproducibilidad

El archivo final debe construirse mediante `tools/build_release.py`, que detecta `0.7.1-pc`, copia la allowlist, verifica el staging, reabre el ZIP y genera el SHA-256 después de pasar la verificación. El ZIP debe extraerse a un directorio nuevo y repetir los tests, `unzip -tq`, checksum, hygiene y greps de seguridad sin runtime local, credenciales, bytecode ni ZIPs internos.
