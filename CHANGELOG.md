# Changelog

## v1.0-RC6 + DeepSeek-Harness

Integra DeepSeek-Harness `0.1.5-rc.1` como motor de razonamiento sobre Ollama local. Conserva memoria, voz, automatizaciones, clientes y permisos de GAIA. El perfil seguro desactiva el shell directo del Harness y deja toda acción del equipo bajo el flujo de autorización existente de GAIA. Incluye SDK Python oficial integrado, instaladores para Windows/Linux, diagnóstico y retorno inmediato al backend Ollama anterior.

## v1.0-RC6

RC6 corrige la inconsistencia reproducida entre el proyecto RC5 y su ZIP documental, adopta un builder documental derivado del archive de proyecto, añade paridad byte-a-byte sobre archivos Markdown/TXT, amplía la clasificación de documentos históricos, actualiza la identidad activa a RC6 y prepara comparaciones de rendimiento reproducibles. El trabajo funcional de RC5 se conserva; RC5 permanece clasificada como `RC5 NOT FROZEN / ARTIFACT CONSISTENCY FAILURE` y no se modifica retroactivamente.

Las optimizaciones solo se aceptan después de perfilado, cambio mínimo, tests y benchmark comparable. Los controles físicos continúan PENDING hasta validación humana en Windows.

## Historial

Los cambios RC1–RC5 permanecen en los documentos históricos y en la matriz de migración. No deben confundirse con comandos operativos vigentes.

## DeepSeek Harness hardening (local patch)
- Harness usa el SDK Python público `deepseek-harness-sdk==0.1.5rc1` y su runtime emparejado; se retiró la copia vendorizada y la ruta privada `_launch_args`.
- Laptop default cambiado a `qwen3.5:4b`, contexto global 4096 y concurrencia 1.
- Harness se ejecuta en un workspace dedicado y conserva el patch que desactiva shells del perfil `sdk-minimal`.
- Si Harness falla, GAIA puede degradar automáticamente a Ollama directo mediante `GAIA_DSH_FALLBACK_TO_OLLAMA=true`.
- Se añadió smoke E2E físico en `tools/test_deepseek_harness_e2e.py` y pruebas de integración/fallback.
