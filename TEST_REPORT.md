# TEST REPORT — GAIA-AI v1.0-RC6

## Ejecución final

El run final se ejecutó con `--all --install-dependencies --confirm-install --recreate-venv` y un directorio de evidencia externo. El flujo fue package gate, preflight inicial, instalación privada, pip-freeze, reejecución real en el venv, preflight posterior, documentación, file audit, security audit, compile, suite, benchmark, ledger físico, extracción limpia y repetición de los gates sobre el archive.

| Gate | Resultado |
|---|---|
| Package gate | PASS |
| Preflight inicial/posterior | PASS / PASS |
| Instalación y transición | PASS; venv externo y `pip-freeze` |
| Documentation contract | PASS |
| File audit | PASS; 0 archivos prohibidos |
| Security audit | PASS; 0 hallazgos |
| Compile worktree | 202/202 PASS |
| Suite worktree | 126/126 PASS; 0 FAIL, 0 TIMEOUT |
| Benchmark worktree | PASS; 200 elementos/30 iteraciones |
| Ledger físico worktree | PENDING; 12 PENDING |
| ZIP integrity/paths | PASS; 325 miembros |
| Package/manifest/audit/security limpio | PASS |
| Compile extracción limpia | 202/202 PASS |
| Suite extracción limpia | 126/126 PASS; 0 FAIL, 0 TIMEOUT |
| Benchmark extracción limpia | PASS |
| Ledger físico limpio | PENDING; 12 PENDING |
| Paridad documental | PASS; 79/79, missing=0, extra=0, content_mismatch=0 |

La suite se descubre dinámicamente; el valor 126 corresponde a esta ejecución concreta y no se usa como sustituto de descubrimiento dinámico. La evidencia detallada y sus logs redacted están fuera del proyecto en `RC6-final-install-validation`.

## Seguridad y side effects

El runner usa subprocessos en lista, `shell=False`, timeouts y redacción. No instala globalmente, no descarga modelos, no inicia Ollama, no muta hardware y no deja servicios persistentes. El escáner ejecutable externo cubrió 84 archivos con cero hallazgos; el runner cubrió 87 archivos en worktree y 88 en extracción limpia con cero hallazgos.

## Rendimiento

RC5 y RC6 se compararon en el mismo entorno con fixtures idénticos. Las cifras y la candidata WAL `INCONCLUSIVE/REVERTED` están en `PERFORMANCE_RC6_REPORT.md` y `PERFORMANCE_COMPARISON_RC5_RC6.md`. No se aceptó una optimización que empeoró retrieval o ResourceGovernor.

## Estado físico

Los doce controles físicos permanecen PENDING. Linux, mocks, imports, APIs locales y existencia de archivos no demuestran Windows 11, Android, audio, GPU/VRAM, batería, térmica, LAN/TLS, signing, Ollama/Qwen ni sesiones prolongadas.

La decisión automatizada permitida es **RC6 FROZEN / AUTOMATED PASS / PHYSICAL VALIDATION PENDING**. No se declara una promoción fuera de RC6.
