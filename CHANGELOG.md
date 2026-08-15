# CHANGELOG — LUMEN

## v0.2.0-pc — 2026-05-24

### Añadido
- GUI de escritorio real en `lumen-pc/gui.py` basada en Tkinter.
- Cliente HTTP reutilizable para escritorio en `lumen-pc/desktop_api.py`.
- Scripts `start-gui.bat`, `start-gui.sh` y `start-client.sh`.
- Logging central configurable en `lumen-core/logging_setup.py`.
- Endpoint público mínimo `GET /api/health`.
- Eliminación manual de facts mediante `DELETE /api/memory/fact/{id}`.
- Prueba de importación de GUI en `tests/gui_import_test.py`.
- Informe de auditoría `AUDIT.md`.

### Cambiado
- Core versionado como `0.2.0-pc`.
- `/api/status` requiere token; ya no expone estadísticas sin autenticación.
- CORS permite únicamente métodos/cabeceras necesarios configurados.
- Validación de entorno: en producción falla con token débil, backend `mock` o CORS global.
- Errores de backend LLM se reportan como fallo real HTTP 502; ya no se guardan como respuesta conversacional fingida.
- STT se ejecuta fuera del event loop de FastAPI.
- TTS de `/api/voice/tts` usa cuerpo JSON validado.
- Chat de voz conserva la respuesta textual aunque TTS falle, informando `tts_error`.
- Memoria de facts expone fuente y timestamps, admite borrar datos y usa guardado manual como camino estable.
- Extracción automática de facts se reduce y queda desactivada por defecto.
- Proactividad automática queda desactivada por defecto; cola y prueba manual se mantienen.
- Cliente terminal actualizado a la autenticación de status y al nuevo contrato TTS.
- Servicio Flutter actualizado al contrato API v0.2 sin declarar Android funcional.

### Conservado como experimental
- `lumen-pc/wake_word.py`.
- Extractor automático de facts si se habilita manualmente.
- Reglas de mensajes proactivos automáticos si se habilitan manualmente.

### No validado automáticamente
- Grabación real de micrófono, Whisper y reproducción de audio en Windows/Linux.
- TTS Edge con red disponible.
- Respuestas reales de Ollama/OpenAI/Anthropic.
- Build y ejecución Android/Flutter.
