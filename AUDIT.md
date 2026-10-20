# GAIA-AI v1.0-RC6 Audit

## Baseline y procedencia

El baseline único verificado para RC6 fue `GAIA-AI-v1.0-RC5-final.zip`, SHA-256 `db220f78f539a31dde812c35d7e974be9a09057520a8a7b88b4f4564186607d8`, extraído desde el ZIP maestro RC5 `GAIA-AI-v1.0-RC5-all-artifacts.zip`, SHA-256 `aab352d7be2b3770535e0d096df9444be3e172021955cfbe06e073404a3210cd`. RC5 no fue modificada. La clasificación conservada es **RC5 NOT FROZEN / ARTIFACT CONSISTENCY FAILURE**.

## Hallazgo reproducido y corrección

| Hallazgo RC5 | Corrección RC6 | Evidencia | Resultado |
|---|---|---|---|
| El ZIP documental RC5 tenía 75 miembros; cuatro eran exclusivos de docs y tres archivos Markdown/TXT del proyecto estaban ausentes. | `tools/build_docs.py` genera una proyección exacta de todos los `.md`/`.txt` del ZIP de proyecto RC6. | `tests/rc6_document_parity_test.py`, auditoría de ZIP y extracción limpia. | PASS: 79 documentos, missing=0, extra=0, content_mismatch=0. |
| Documentos históricos operativos podían confundirse con comandos vigentes. | 33 documentos históricos operativos comienzan con la advertencia exacta y enlaces a la documentación RC6. | `rc6_identity_documentation_test.py`, package gate. | PASS. |
| Identidad activa heredada RC5. | Core/PC, Android/Flutter, migrador, benchmark, ledger, runner, wrapper, manifest y tests usan identidad RC6; fuentes RC5 solo permanecen como baseline/compatibilidad. | Identidad, migración y suite completa. | PASS. |
| Runner/builder no auditaban completamente la consistencia documental extraída. | Package gate, documentación, file audit y security audit corren sobre worktree y extracción limpia. | `RC6-final-install-validation/validation.json`. | PASS. |

## Gates reproducibles

El run final con instalación autorizada creó y usó un venv externo, registró pip-freeze y reejecutó el runner con el intérprete del venv. Resultado: 22 pasos, 20 PASS y 2 PENDING físicos; ningún FAIL, TIMEOUT, BLOCKED o dependencia faltante posterior. La suite dinámica fue **126/126 PASS** en worktree y extracción limpia; compile fue **202/202 PASS** en ambos recorridos. El proyecto A/B produjo 325 miembros y hashes idénticos; docs A/B produjo 79 documentos y hashes idénticos.

## Seguridad

El security audit del runner pasó con 87 archivos ejecutables en worktree y 88 en extracción limpia, cero findings. El escáner externo cubrió 84 archivos antes del build y obtuvo cero hallazgos. Las coincidencias manuales `ollama pull` y secretos `test-` se clasificaron correctamente como hint/fixture sintético; no existe arranque automático, descarga automática, shell dinámico ni secreto real distribuible.

## Optimización

La candidata de cacheo WAL por proceso siguió `PROFILE → HYPOTHESIS → MINIMAL CHANGE → TEST → BENCHMARK`. Aunque sus tests funcionales pasaron, su comparación triple frente a RC5 fue `save −3.376%`, `retrieval +6.340%` y `ResourceGovernor +50.000%`; se clasificó **INCONCLUSIVE** y fue revertida. No se aceptó una optimización de runtime que empeorara retrieval/governor. La corrección de paridad documental no altera el núcleo funcional.

## Decisión

La decisión automatizada permitida es:

> **RC6 FROZEN / AUTOMATED PASS / PHYSICAL VALIDATION PENDING**

Los doce controles físicos siguen PENDING. Linux, mocks, imports, APIs locales y existencia de archivos no constituyen evidencia Windows, Android, audio, GPU/VRAM, batería, térmica, LAN/TLS, signing u Ollama. Esta decisión no declara producción ni crea una promoción fuera de RC6.
