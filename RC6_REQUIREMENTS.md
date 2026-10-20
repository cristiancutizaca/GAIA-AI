# GAIA-AI v1.0-RC6 Requirements

RC6 es una release candidate de consolidación documental, optimización controlada y preparación para validación física. Su baseline único es `GAIA-AI-v1.0-RC5-final.zip` con SHA-256 `db220f78f539a31dde812c35d7e974be9a09057520a8a7b88b4f4564186607d8`. RC5 permanece intacta y se clasifica como **RC5 NOT FROZEN / ARTIFACT CONSISTENCY FAILURE** por su inconsistencia proyecto↔docs; RC6 no modifica esa clasificación retroactivamente.

## Criterios obligatorios

| Área | Requisito |
|---|---|
| Baseline | Verificar el ZIP maestro RC5, el proyecto RC5 y el ZIP documental RC5 antes de editar. |
| Paridad | El ZIP documental RC6 debe ser una proyección exacta de todos los `.md` y `.txt` del ZIP principal RC6. |
| Documentos | Extras, faltantes, mismatches de contenido, colisiones Unicode/case-fold y rutas inseguras deben ser cero. |
| Identidad | Core/PC `1.0.0-rc6-pc`, protocolo `1.0-RC6`, Android `1.0.0-rc6+1`, target `1.0.0-rc6`. |
| Rendimiento | Comparar RC5 y RC6 en el mismo entorno, con fixtures idénticos y muestras suficientes. |
| Seguridad | Cero patrones inseguros reales, cero secretos, cero mutación de hardware y cero descarga automática de modelos. |
| Calidad | Package gate, compile, suite completa, benchmark, seguridad, builds A/B y extracción limpia PASS. |
| Física | Los doce controles siguen PENDING hasta evidencia humana en Windows y el equipo objetivo. |

## Regla de optimización

Cada cambio debe seguir `PROFILE → HYPOTHESIS → MINIMAL CHANGE → TEST → BENCHMARK → ACCEPT OR REVERT`. Una mejora menor que el ruido estadístico se clasifica `INCONCLUSIVE` y no se presenta como aceptación. No se reducen fixtures, iteraciones, asserts, límites, permisos, ownership, provenance, backpressure ni autoridad del ResourceGovernor.

## Condiciones de freeze

RC6 solo puede declararse congelada con la decisión exacta `RC6 FROZEN / AUTOMATED PASS / PHYSICAL VALIDATION PENDING`. Si falla la suite o seguridad se usa `RC6 NOT FROZEN / AUTOMATED FAILURES PRESENT`; si hay regresión mensurable, `RC6 NOT FROZEN / PERFORMANCE REGRESSION`; si falla la paridad, `RC6 NOT FROZEN / ARTIFACT CONSISTENCY FAILURE`. Ningún resultado Linux declara éxito físico ni autoriza una promoción fuera de RC6.
