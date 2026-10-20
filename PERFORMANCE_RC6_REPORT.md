# GAIA-AI v1.0-RC6 Performance and Reproducibility Report

RC5 y RC6 se midieron en el mismo Python 3.12, Linux, venv externo, configuración mock/safe-mode y base SQLite temporal. Startup/import usó cinco procesos independientes, una primera solicitud y cinco solicitudes posteriores por proceso. El benchmark de memoria/ResourceGovernor usó 200 elementos, 30 iteraciones y tres ejecuciones por versión.

## Medición comparable

| Métrica | RC5 media | RC6 media | Cambio |
|---|---:|---:|---:|
| Importación | 729.368 ms | 599.742 ms | −17.772% |
| Primera solicitud | 9.439 ms | 7.103 ms | −24.748% |
| Solicitudes posteriores | 1.997 ms | 2.191 ms | +9.715% |
| Memory save p95 medio | 6.516 ms | 6.248 ms | −4.113% |
| Memory retrieval p95 medio | 7.760 ms | 7.663 ms | −1.250% |
| ResourceGovernor observe p95 medio | 0.008 ms | 0.009 ms | +12.500% |
| RSS máximo medio | 55,690.4 KiB | 55,210.4 KiB | −0.862% |
| Módulos cargados | 502 | 502 | 0% |
| Threads | 1 | 1 | 0% |

La variación de startup y las diferencias pequeñas de runtime no se atribuyen automáticamente a optimización porque RC6 solo cambió identidad, contratos y empaquetado en esos hot paths. Las métricas completas y la dispersión permanecen en la evidencia externa.

## Candidata WAL

Se probó y revirtió una candidata que configuraba WAL una vez por proceso/ruta bajo lock en lugar de ejecutar el pragma en cada conexión. Los tests SQLite/WAL, memoria, backup y paridad pasaron, pero el benchmark triple mostró save −3.376%, retrieval +6.340% y governor +50.000% frente a RC5. Se clasificó `INCONCLUSIVE` y se revirtió; no forma parte del runtime RC6 congelado.

## Efectos laterales y límites

Los benchmarks usaron SQLite temporal, no iniciaron servicios, no descargaron modelos, no iniciaron Ollama y no mutaron hardware. El escáner ejecutable RC6 cubrió 84 archivos y obtuvo cero hallazgos. Las métricas no demuestran rendimiento Windows, Android, GPU/VRAM, batería, térmica, audio, LAN/TLS, signing u Ollama físico; esos controles continúan PENDING.

Una mejora futura debe repetir `PROFILE → HYPOTHESIS → MINIMAL CHANGE → TEST → BENCHMARK → ACCEPT OR REVERT`. No se reducen fixtures, iteraciones, asserts, ownership, provenance, backpressure ni límites para mejorar una cifra.
