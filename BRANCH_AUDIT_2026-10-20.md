# Auditoría de ramas: GAIA-AI (20 de octubre de 2026)

Se consultó el listado completo de ramas del repositorio y se utilizó
la comparación de commits entre `main` y cada rama de respaldo.

| Rama | Commit de respaldo | Commits exclusivos respecto a main |
| --- | --- | ---: |
| `backup/pre-archive-gaia-2026-10-19` | `a021d91298c9fefed5e03645b616859c508987e0` | 0 |
| `backup/pre-resident-v20-2026-10-20` | `7646c20c18931309de9f85dbb83da60d11cd546f` | 0 |
| `backup/pre-permissions-hardening-2026-10-20` | `707f594d968a691d82e82f8dce615d305f831774` | 0 |

**Resultado:** las tres ramas son ancestros de `main`; no existe
ningún commit exclusivo ni archivo de trabajo pendiente de fusionar desde
ellas. La reorganización de los informes históricos y los trabajos de
interfaz residente y autorizaciones están ya incorporados en `main`.

Las ramas `backup/` se conservan para recuperación: fusionarlas hacia
adelante no añadiría código y borrarlas reduciría las posibilidades de
restaurar versiones anteriores.

## Riesgos que requieren validación en Windows

1. Los trabajos de GitHub Actions no han ejecutado pruebas: aparecen como
   fallidos con cero pasos y sin runner. No equivalen a fallos de test
   concretos, pero **la compilación y las pruebas CI siguen sin validarse**.
2. El inicio de sesión, el atajo global, audio, selección del micrófono,
   TTS, Ollama y la GPU necesitan pruebas físicas.
3. Una solicitud enviada al host no equivale a una acción verificada.
4. El planificador de tareas complejas y la compatibilidad con otras
   aplicaciones siguen requiriendo desarrollo.

Para las comprobaciones locales, consulta
`GAIA_RESIDENT_WINDOWS.md` y `tools/gaia_resident_doctor.py`.
