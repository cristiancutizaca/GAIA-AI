# GAIA-AI v1.0-RC6 Document Classification

| Clasificación | Regla | Ejemplos |
|---|---|---|
| `ACTIVE_RC6` | Documento operativo o de gobierno vigente con comandos e identidad RC6. | README, guía rollback, checklist RC6, requirements RC6, reportes RC6. |
| `HISTORICAL_NON_OPERATIONAL` | Registro histórico descriptivo sin instrucciones ejecutables vigentes. | Changelog histórico, decisiones y reportes puramente narrativos. |
| `HISTORICAL_OPERATIONAL_WARNING_REQUIRED` | Contiene comandos, instalación, migración, rollback, Windows, Android o validación física anterior. | Checklist Windows antigua, validaciones V100/RC4/RC5, guía Vault, requirements operativos antiguos. |
| `COMPATIBILITY_FIXTURE` | Fixture o test que conserva deliberadamente una versión de origen para probar compatibilidad o fail-closed. | Tests de migración RC2/RC3/RC4/RC5. |
| `BASELINE_EVIDENCE` | Hashes, inventarios o procedencia externa; no son instrucciones de operación. | Baseline verification e inventarios externos. |

Los documentos de la última fila no se mezclan con la documentación operativa. Los históricos operativos empiezan exactamente con `HISTORICAL DOCUMENT — DO NOT USE FOR RC6 OPERATIONS` y enlazan a `WINDOWS_RC6_VALIDATION_CHECKLIST.md`, `UPDATE_ROLLBACK_GUIDE.md` y `PHYSICAL_VALIDATION_RC6.md`.
