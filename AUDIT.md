# Auditoría técnica — LUMEN v0.1.1-working → v0.2.0-pc

Clasificación aplicada al código recibido antes de los cambios de v0.2. La última columna indica la acción ejecutada y el estado final.

| Archivo / área | Propósito real | Estado auditado en v0.1.1 | Acción realizada en v0.2 / estado final |
|---|---|---|---|
| `.env.example` | Variables de ejecución | Funciona pero está verde | Ampliado con entorno, logs, límites de audio, flags de voz/facts y proactividad; **funciona** |
| `.gitignore` | Evitar secretos/datos generados | Funciona | Conservado; **funciona** |
| `start.bat` | Arrancar Core en Windows | Funciona | Conservado; **funciona** |
| `start-client.bat` | Arrancar terminal en Windows | Funciona | Conservado; **funciona** |
| `start.sh` | Arrancar Core en Linux | Funciona | Conservado; **funciona** |
| `start-gui.bat` / `start-gui.sh` | Arrancar GUI | No existía | Añadido; **funciona, pendiente validación visual física** |
| `start-client.sh` | Terminal Linux | No existía | Añadido; **funciona a nivel de script** |
| `lumen-core/main.py` | Ciclo de vida FastAPI | Funciona pero está verde | Logs, versión y validación de config; **funciona** |
| `lumen-core/config.py` | Configuración `.env` | Funciona pero está verde | Flags limpios y validación dev/prod; **funciona** |
| `lumen-core/logging_setup.py` | Logging | No existía | Añadido; **funciona** |
| `lumen-core/routes/api.py` | Contrato HTTP | Funciona pero debe refactorizarse | Auth consistente, health, validación, TTS JSON, delete fact, manejo de errores; **funciona** |
| `lumen-core/llm.py` | Adaptadores LLM | Funciona pero está verde | Excepciones claras y no guardar fallos como mensajes; **flujo probado con mock; backends reales pendientes de clave/servicio** |
| `lumen-core/memory.py` | SQLite, facts, backups, cola | Funciona | Facts manuales enriquecidos, borrado y contexto simple; **funciona** |
| `lumen-core/backup_scheduler.py` | Backup periódico | Funciona pero está verde | Logging y manejo de error; **funciona; ciclo diario no se esperó en prueba** |
| `lumen-core/voice.py` | Whisper + Edge TTS | Funciona pero está verde | Flags on/off, límites y logging; **flujo API probado, hardware/red pendientes** |
| `lumen-core/proactive.py` | Reglas/cola proactiva | Funciona pero está verde | Automático apagado por defecto; test manual estable; **parcial** |
| `lumen-core/fact_extractor.py` | Extraer facts por regex | Debe refactorizarse | Reducido y apagado por defecto para evitar memoria falsa; **experimental** |
| `lumen-core/personality.py` | Prompt de identidad | Funciona | Conservado sin rediseño; **funciona sujeto al LLM usado** |
| `lumen-core/requirements.txt` | Dependencias Core | Funciona | Conservado y renombrado a v0.2; **funciona** |
| `lumen-pc/client.py` | Cliente terminal | Funciona pero queda verde | Corregido para status autenticado y TTS JSON; **funciona como alternativa** |
| `lumen-pc/desktop_api.py` | Acceso HTTP/audio GUI | No existía | Añadido; **funciona y probado contra Core real en mock** |
| `lumen-pc/gui.py` | GUI escritorio | No existía | Añadido; **funcional por código, pendiente prueba visual/audio en Windows del usuario** |
| `lumen-pc/wake_word.py` | Escucha continua | Experimental | Conservado fuera de GUI estable; corregida descarga autenticada; **experimental** |
| `lumen-pc/requirements.txt` | Dependencias PC | Funciona pero sobredimensionado | Whisper retirado del cliente porque STT ocurre en Core; **funciona** |
| `lumen-mobile/pubspec.yaml` | Dependencias/version móvil | Incompleto | Versión ajustada; **prototipo** |
| `lumen-mobile/lib/main.dart` | Shell Flutter | Incompleto | Conservado; **prototipo** |
| `lumen-mobile/lib/services/lumen_service.dart` | Cliente API móvil | Funciona pero incompatible con API endurecida | Ajustado a token en status y TTS JSON; **no validado en dispositivo** |
| `lumen-mobile/lib/screens/chat_screen.dart` | UI móvil chat | Incompleto | Conservado; **prototipo** |
| `lumen-mobile/lib/screens/settings_screen.dart` | UI ajustes móvil | Incompleto | Etiqueta de versión honesta; **prototipo** |
| `tests/smoke_test.py` | Validación API | Funciona pero insuficiente para v0.2 | Ampliado con auth, facts manuales y flags; **funciona** |
| `tests/gui_import_test.py` | Validar GUI sin display | No existía | Añadido; **funciona** |
| `README.md` | Ejecución/documentación | Funciona pero enfocado v0.1 | Reescrito con estado real Windows/Linux; **funciona** |
| `TEST_REPORT.md` | Registro de pruebas | Funciona pero desactualizado | Actualizado para v0.2; **funciona** |
| `CHANGELOG.md` | Cambios | Funciona pero desactualizado | Actualizado; **funciona** |

## Archivos que no conviene promocionar como estables

- `lumen-pc/wake_word.py`: escucha continua basada en Whisper `tiny`; consume recursos y no se integró en la GUI estable.
- `lumen-core/fact_extractor.py`: regex útil como experimento, no como memoria confiable automática.
- `lumen-mobile/`: conserva base visual y contrato HTTP, pero no hay validación APK ni permisos reales.
