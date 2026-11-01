# GAIA-AI v1.0-RC6 + DeepSeek-Harness

Esta edición usa DeepSeek-Harness como motor de razonamiento con Ollama local. Consulta `DEEPSEEK_HARNESS.md` para instalarlo y configurarlo.

RC6 consolida el trabajo funcional de RC5, corrige la inconsistencia documental reproducida y añade optimización controlada únicamente cuando existe medición comparable. La prioridad es preservar verdad, seguridad, datos, compatibilidad y reproducibilidad antes que perseguir una cifra de benchmark.

## Estado de la release

RC5 se conserva como baseline histórico y está clasificada como **RC5 NOT FROZEN / ARTIFACT CONSISTENCY FAILURE** porque su ZIP documental contenía cuatro documentos que no existían en el ZIP principal y omitía tres archivos de requisitos del proyecto. RC6 adopta una política única: el ZIP documental se genera automáticamente como proyección exacta de todos los miembros Markdown/TXT del ZIP de proyecto. No se copia documentación desde una carpeta paralela.

La decisión RC6 solo podrá ser **RC6 FROZEN / AUTOMATED PASS / PHYSICAL VALIDATION PENDING** después de que pasen todos los gates y la auditoría externa. Ninguna ejecución Linux convierte los controles físicos en PASS y ningún documento autoriza una promoción fuera de la condición RC6.

## Identidad activa

| Superficie | Identidad RC6 |
|---|---|
| Release | `1.0-RC6` |
| Core/PC | `1.0.0-rc6-pc` |
| Protocolo | `1.0-RC6` |
| Flutter/Android | `1.0.0-rc6+1` |
| Android `versionName` | `1.0-RC6` |
| Migración target | `1.0.0-rc6` |
| Snapshot | `gaia-rc6-snapshot-1` |
| Package root | `GAIA-AI-v1.0-RC6` |
| Runner | `gaia_rc6_validator` |
| Wrapper | `validate-gaia-rc6.ps1` |

## Superficie activa

Los contratos, herramientas y documentos operativos RC6 incluidos en el paquete son `tools/validate_rc6.py`, `tools/build_release.py`, `tools/build_docs.py`, `tools/gaia_migrate.py`, `tools/gaia_benchmark.py`, `tools/physical_validation.py`, `validate-gaia-rc6.ps1`, `install-gaia.ps1`, `setup-windows.bat`, `release_manifest.json`, `RC6_REQUIREMENTS.md`, `PERFORMANCE_RC6_REPORT.md`, `PERFORMANCE_COMPARISON_RC5_RC6.md`, `PHYSICAL_VALIDATION_RC6.md`, `WINDOWS_RC6_VALIDATION_CHECKLIST.md`, `MIGRATION_MATRIX_RC5_RC6.md`, `RELEASE_DECISION_RC6.md`, `UPDATE_ROLLBACK_GUIDE.md`, `DOCUMENT_CLASSIFICATION_RC6.md`, `TEST_REPORT.md`, `FINAL_VALIDATION.txt`, `AUDIT.md`, `SECURITY_MODEL.md`, `THREAT_MODEL.md`, `KNOWN_LIMITATIONS.md`, `MODIFIED_FILES.md`, `tests/rc6_identity_documentation_test.py`, `tests/rc6_document_parity_test.py`, `tests/rc6_validation_runner_test.py`, `tests/rc6_physical_validation_test.py`, `tests/rc6_migrator_cli_contract_test.py`, `tests/rc6_benchmark_contract_test.py`, `tests/rc6_builder_contract_test.py`, `tests/rc6_validation_runner_contract_test.py`, `tests/release_package_test.py` y los contratos heredados actualizados.

## Validación reproducible

El orden de validación es package gate, identidad, preflight inicial, instalación explícitamente autorizada si es necesaria, reejecución en venv externo, preflight posterior, compile, suite completa, benchmark RC5, benchmark RC6, comparación, seguridad, builds A/B, extracción limpia, suite desde ZIP, paridad proyecto↔docs y auditoría de artefactos. Las métricas de rendimiento se comparan solo en el mismo entorno y con fixtures idénticos.

```text
python tools/validate_rc6.py --all --output-dir ..\RC6-validation --confirm-install --recreate-venv
python tools/build_release.py --output-dir ..\RC6-build-a
python tools/build_docs.py --project-zip ..\RC6-build-a\GAIA-AI-v1.0-RC6-final.zip --output-dir ..\RC6-docs-a
```

La evidencia, el venv, las bases, los logs y los resultados privados permanecen fuera del árbol del proyecto. Los comandos de Windows vigentes están en `WINDOWS_RC6_VALIDATION_CHECKLIST.md` y `UPDATE_ROLLBACK_GUIDE.md`.

## Seguridad y validación física

El runner usa procesos en forma de lista, `shell=False`, límites temporales y redacción. No inicia Ollama, no descarga modelos, no modifica hardware y no deja servicios persistentes. La validación física mantiene los doce controles en `PENDING` hasta contar con evidencia humana en el equipo objetivo. Consulte `SECURITY_MODEL.md`, `THREAT_MODEL.md` y `PHYSICAL_VALIDATION_RC6.md` para los límites completos.

## Índice literal de archivos activos RC6

La siguiente tabla es el índice cruzado que valida el package gate:

| Categoría | Archivos |
|---|---|
| Gobierno | `CHANGELOG.md`, `AUDIT.md`, `TEST_REPORT.md`, `FINAL_VALIDATION.txt`, `KNOWN_LIMITATIONS.md`, `MODIFIED_FILES.md`, `SECURITY_MODEL.md`, `THREAT_MODEL.md` |
| Requisitos y operación | `RC6_REQUIREMENTS.md`, `PERFORMANCE_RC6_REPORT.md`, `PERFORMANCE_COMPARISON_RC5_RC6.md`, `PHYSICAL_VALIDATION_RC6.md`, `WINDOWS_RC6_VALIDATION_CHECKLIST.md`, `MIGRATION_MATRIX_RC5_RC6.md`, `RELEASE_DECISION_RC6.md`, `UPDATE_ROLLBACK_GUIDE.md`, `DOCUMENT_CLASSIFICATION_RC6.md` |
| Entrypoints | `install-gaia.ps1`, `validate-gaia-rc6.ps1`, `setup-windows.bat`, `tools/validate_rc6.py`, `tools/build_release.py`, `tools/build_docs.py`, `tools/gaia_migrate.py`, `tools/gaia_benchmark.py`, `tools/physical_validation.py` |
| Contratos | `tests/release_package_test.py`, `tests/rc6_identity_documentation_test.py`, `tests/rc6_document_parity_test.py`, `tests/rc6_validation_runner_test.py`, `tests/rc6_validation_runner_contract_test.py`, `tests/rc6_physical_validation_test.py`, `tests/rc6_migrator_cli_contract_test.py`, `tests/rc6_powershell_wrapper_contract_test.py`, `tests/rc6_benchmark_contract_test.py`, `tests/rc6_builder_contract_test.py` |
