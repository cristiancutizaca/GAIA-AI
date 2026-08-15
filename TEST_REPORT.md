# Reporte de validación — LUMEN v0.2.0-pc

Fecha de ejecución: **2026-05-24**

## Pruebas ejecutadas correctamente en este entorno

```bash
python -m compileall -q lumen-core lumen-pc tests
python tests/gui_import_test.py
python tests/smoke_test.py
```

Resultados observados:

| Prueba | Resultado |
|---|---|
| Compilación Python de Core, cliente terminal, GUI y tests | Correcta |
| Importación de `gui.py` sin abrir ventana (`--check`) | Correcta |
| `GET /api/health` público | Correcto |
| `GET /api/status` sin token | Rechazado con 401 como se espera |
| `GET /api/status` autenticado | Correcto |
| Chat mediante backend `mock` | Correcto |
| Historial SQLite de la sesión | Correcto |
| Auto-facts apagado por defecto | Correcto |
| Alta/borrado manual de facts | Correcto |
| Flujo HTTP de voz con STT/TTS sustituidos controladamente | Correcto |
| Descarga autenticada del audio generado | Correcta |
| Backup manual SQLite | Correcto |
| Encolado/recepción de mensaje proactivo de prueba | Correcto |

## Prueba con servidor real y cliente de escritorio

Se inició `lumen-core/main.py` mediante Uvicorn en un puerto temporal con:

```env
LUMEN_LLM_BACKEND=mock
LUMEN_SECRET=test-secret-for-live-v02
LUMEN_PORT=8192
LUMEN_BACKUP_ENABLED=false
LUMEN_PROACTIVE_ENABLED=false
```

Luego se utilizó `lumen-pc/desktop_api.py` como cliente real por HTTP para:

- consultar status autenticado;
- enviar un mensaje de chat;
- guardar y leer un fact manual;
- crear un backup.

Resultado: **correcto**.

## Lo que esta prueba NO demuestra

| Componente | Motivo de no validación completa |
|---|---|
| Ventana GUI renderizada en Windows | El entorno de ejecución no es el equipo Windows del usuario |
| Micrófono físico | Requiere dispositivo de audio disponible |
| Whisper real | Requiere audio real, FFmpeg/modelo local y mayor tiempo de ejecución |
| Edge TTS real y reproducción | Requiere red y salida de audio física |
| Ollama real | Requiere servicio/modelo instalado localmente |
| OpenAI/Anthropic real | Requiere credenciales del usuario |
| Flutter Android | No se generó APK ni se ejecutó en Android |
| Proactividad automática prolongada | Queda desactivada por defecto; solo se comprobó la cola y polling manual |

## Comandos de validación manual recomendados en Windows

Con el Core y la GUI ya configurados:

```powershell
.\start.bat
.\start-gui.bat
```

En la GUI:

1. Enviar un mensaje de texto con Ollama o API configurada.
2. Activar `Responder con voz` y pulsar `Hablar`.
3. Abrir `Memoria`, agregar un fact y volver a abrir la ventana.
4. Pulsar `Backup` y verificar el archivo dentro de `lumen-core\data\backups`.
5. Pulsar `Probar aviso` y comprobar que aparece el mensaje proactivo.
