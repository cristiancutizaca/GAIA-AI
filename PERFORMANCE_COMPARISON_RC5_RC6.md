# GAIA-AI v1.0-RC6 Performance Comparison

Las mediciones RC5 y RC6 se realizaron en el mismo Python 3.12, sistema Linux, venv externo, fixtures temporales y configuración mock/safe-mode. Cada benchmark usó 200 elementos de memoria y 30 iteraciones de retrieval/ResourceGovernor, con tres ejecuciones independientes. Startup/import usó cinco procesos independientes y cinco solicitudes posteriores por proceso.

## Baseline identity-only

| Métrica | RC5 media | RC6 media | Cambio RC5→RC6 |
|---|---:|---:|---:|
| Importación | 729.368 ms | 599.742 ms | −17.772% |
| Primera solicitud | 9.439 ms | 7.103 ms | −24.748% |
| Solicitudes posteriores | 1.997 ms | 2.191 ms | +9.715% |
| Memory save p95 por ejecución | 6.516 ms | 6.248 ms | −4.113% |
| Memory retrieval p95 por ejecución | 7.760 ms | 7.663 ms | −1.250% |
| ResourceGovernor observe p95 por ejecución | 0.008 ms | 0.009 ms | +12.500% |

Las diferencias del baseline no se atribuyen a una optimización de runtime: RC6 todavía era funcionalmente equivalente en esos hot paths, y el primer-request/import presenta dispersión dependiente del proceso.

## Candidata WAL — revertida

Se probó una modificación mínima que evitaba ejecutar `PRAGMA journal_mode=WAL` en cada conexión y lo configuraba una vez por proceso/ruta bajo lock, manteniendo `foreign_keys=ON` en cada conexión. Los tests SQLite/WAL, memoria, backup y paridad pasaron; el benchmark triple produjo:

| Métrica | RC5 baseline | Candidata WAL RC6 | Cambio |
|---|---:|---:|---:|
| Memory save p95 medio | 6.516 ms | 6.296 ms | −3.376% |
| Memory retrieval p95 medio | 7.760 ms | 8.252 ms | +6.340% |
| ResourceGovernor observe p95 medio | 0.008 ms | 0.012 ms | +50.000% |

La candidata se clasificó **INCONCLUSIVE** y fue revertida porque no mejoró todos los objetivos y empeoró retrieval y governor. Por tanto, no se cuenta como optimización aceptada en RC6. Se conserva la evidencia externa de la hipótesis, sus tests y su rollback.

## Decisión de rendimiento

| Cambio | Estado | Justificación |
|---|---|---|
| Builder documental por proyección exacta | ACCEPTED | Corrige consistencia de artefactos sin mutar runtime. |
| Identidad y contratos RC6 | ACCEPTED | Cambios de release y validación, sin afirmar mejora de rendimiento. |
| Cacheo WAL por proceso | REVERTED / INCONCLUSIVE | Beneficio parcial inferior al criterio; regresiones en retrieval/governor. |
| Cambios adicionales de núcleo | NOT APPLIED | No se introduce una modificación sin hipótesis y evidencia mejor que el baseline. |

Una diferencia menor que el ruido estadístico no es una mejora. Las regresiones funcionales, de seguridad, ownership, provenance, backpressure, límites o integridad obligan a revertir.
