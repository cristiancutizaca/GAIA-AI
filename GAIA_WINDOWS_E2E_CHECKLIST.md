# GAIA: pruebas reales pendientes en Windows 11

Esta versión integra diagnósticos locales, registro persistente de tareas de solo lectura, despacho de órdenes vocales de diagnóstico al escritorio y comprobación guiada de componentes. Las pruebas automáticas no sustituyen una prueba física de micrófono, GPU o pantalla.

## Prueba inicial (sin tocar configuraciones)

Desde la carpeta del proyecto, con el entorno de GAIA:

```powershell
.\.venv\Scripts\python.exe tools\gaia_preflight.py
.\.venv\Scripts\python.exe tools\gaia_preflight.py --json
```

**No corrige ni instala por sí solo.** Entrega acciones concretas ante Ollama ausente, modelo visual faltante, Faster-Whisper, Piper o gaia.onnx. Que un paquete esté presente no prueba un micrófono real.

## Comprobaciones en el Centro de Control

1. Abrir GAIA desde el supervisor; el holograma debe mostrar estado y abrir el Centro de Control al pulsarlo. En monitores pequeños, la barra lateral puede desplazarse.
2. Pulsar **Comprobar voz e IA**: identificar faltantes y solucionarlos explícitamente; repetir el diagnóstico.
3. Pulsar **Diagnosticar PC**: debe crear una tarea de lectura auditada, consultar CPU/RAM/GPU/discos/procesos/red y mostrar resultado, aun sin Ollama.
4. Pulsar **Diagnosticar ComfyUI**: sólo inventario de hardware y procesos. **No promete reparar automáticamente ROCm**.
5. Pulsar **Historial de tareas** y comprobar que permanecen tras reiniciar GAIA.
6. Pulsar **Hablar** o mantener **Ctrl+Espacio**: comprobar transcripción y respuesta escrita/hablada. Solicitar «GAIA, diagnostica mi PC» y comprobar que responde mediante el operador local.
7. Solicitar «GAIA, mira mi pantalla», seleccionar conscientemente un monitor y comprobar que sólo lo describe mediante un modelo de visión Ollama instalado. Repetir en el segundo monitor. **La captura nunca concede permiso de hacer clic**.
8. Comprobar una orden peligrosa: el sistema no debe ejecutar una modificación sin aprobación. `GAIA_OPERATOR_HALT=1` bloquea pasos nuevos del operador y `GAIA_SAFE_MODE=1` bloquea acciones con efectos.

## Límites

- Sin `gaia.onnx` entrenado, decir solamente «GAIA» **no activa** la escucha; usar pulsar-para-hablar.
- El modelo de chat y visión se descargan de forma explícita con Ollama. No se descargan en segundo plano.
- El control libre de aplicaciones, instaladores, reparaciones de drivers, automatización visual completa, TTS, latencia y estabilidad requieren pruebas de extremo a extremo en el PC físico.
- Una tarea interrumpida con efectos no se repite automáticamente. Las acciones propuestas por imágenes o texto no se ejecutan sin políticas y permisos.

Pruebas de desarrollo: `python -m compileall -q lumen-core lumen-pc tools tests` y `python -m pytest -q`.
