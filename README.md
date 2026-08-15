# LUMEN v0.2.0-pc

Base ejecutable de **LUMEN para PC**: un Core local en FastAPI, memoria SQLite y dos clientes de escritorio: una GUI nueva con Tkinter y el cliente de terminal conservado como alternativa.

Esta versión no es un asistente autónomo terminado. Es una base utilizable y comprobable en PC. Android permanece como prototipo de interfaz y `wake word` permanece experimental.

## Estado honesto

| Área | Estado en v0.2 |
|---|---|
| Core FastAPI local | Implementado y probado |
| GUI PC de chat | Implementada; importación y API probadas, requiere validación visual en tu PC |
| Cliente terminal | Implementado y conservado |
| Chat real | Implementado; requiere Ollama o clave OpenAI/Anthropic |
| Memoria de historial | Implementada con SQLite |
| Facts | Guardado/edición manual implementado; extracción automática experimental y apagada por defecto |
| Voz push-to-talk | Flujo implementado; micrófono, Whisper, Edge TTS y reproducción se validan en el equipo físico |
| Wake word | Experimental, no activado en la GUI |
| Proactividad | Cola y prueba manual implementadas; generación automática apagada por defecto |
| Backup | Manual y automático implementados mediante snapshot SQLite |
| Android | Prototipo actualizado al contrato API; no compilado ni validado como app funcional |

## Por qué Tkinter para la GUI

La GUI usa **Tkinter**, incluido con Python en Windows y disponible en Linux mediante `python3-tk`. Evita sumar Electron, Node o un framework de escritorio adicional cuando la prioridad es estabilizar el Core y tener un cliente usable. La comunicación con el Core se concentra en `lumen-pc/desktop_api.py`, de modo que luego pueda sustituirse la interfaz sin reescribir la API.

## Estructura final

```text
lumen-project/
├── .env.example
├── .gitignore
├── README.md
├── CHANGELOG.md
├── AUDIT.md
├── TEST_REPORT.md
├── start.bat                 # Core, Windows
├── start-client.bat          # Terminal, Windows
├── start-gui.bat             # GUI, Windows
├── start.sh                  # Core, Linux
├── start-client.sh           # Terminal, Linux
├── start-gui.sh              # GUI, Linux
├── tests/
│   ├── smoke_test.py
│   └── gui_import_test.py
├── lumen-core/
│   ├── main.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── routes/api.py
│   ├── llm.py
│   ├── memory.py
│   ├── voice.py
│   ├── proactive.py
│   ├── backup_scheduler.py
│   ├── fact_extractor.py
│   ├── personality.py
│   └── requirements.txt
├── lumen-pc/
│   ├── gui.py
│   ├── desktop_api.py
│   ├── client.py
│   ├── wake_word.py
│   └── requirements.txt
└── lumen-mobile/             # prototipo, no entrega Android funcional
```

## Requisitos

### Windows 10/11

- Python **3.11 o superior**.
- Para texto únicamente: no necesitas micrófono ni FFmpeg.
- Para voz: micrófono funcional, **FFmpeg** en `PATH`, acceso a Internet para Edge TTS y dependencias de Python instaladas.
- Un backend para respuestas reales: Ollama local, OpenAI o Anthropic.

Tkinter se incluye normalmente con el instalador oficial de Python para Windows.

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-tk ffmpeg libportaudio2 portaudio19-dev
```

La GUI y el Core son compatibles con Linux a nivel de código y scripts. Esta entrega fue priorizada para PC; el flujo de micrófono/reproducción debe probarse en la distribución concreta.

## Instalación en Windows

Desde PowerShell, dentro de la carpeta extraída `lumen-project`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r .\lumen-core\requirements.txt
pip install -r .\lumen-pc\requirements.txt
Copy-Item .env.example .env
notepad .env
```

Si PowerShell impide activar el entorno:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Instalación en Linux

```bash
cd lumen-project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r lumen-core/requirements.txt
pip install -r lumen-pc/requirements.txt
cp .env.example .env
nano .env
```

## Configuración mínima `.env`

Cambia siempre el token local:

```env
LUMEN_ENV=development
LUMEN_SECRET=reemplaza_esto_por_un_token_largo_privado
LUMEN_HOST=127.0.0.1
LUMEN_PORT=8090
LUMEN_CORE_URL=http://localhost:8090
```

`LUMEN_ENV=production` bloquea el arranque si conservas un token débil, usas CORS abierto o intentas ejecutar el backend `mock`.

### Opción A: Ollama local

```env
LUMEN_LLM_BACKEND=ollama
LUMEN_LLM_MODEL=llama3.1
OLLAMA_URL=http://localhost:11434
```

Luego instala Ollama y ejecuta:

```powershell
ollama pull llama3.1
ollama serve
```

### Opción B: OpenAI

```env
LUMEN_LLM_BACKEND=openai
LUMEN_LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=TU_CLAVE_REAL_LOCAL
```

### Opción C: Anthropic

```env
LUMEN_LLM_BACKEND=anthropic
LUMEN_LLM_MODEL=TU_MODELO_CONFIGURADO
ANTHROPIC_API_KEY=TU_CLAVE_REAL_LOCAL
```

### Modo técnico de prueba

```env
LUMEN_LLM_BACKEND=mock
```

`mock` solo responde con eco controlado para validar endpoints y clientes. No es un modelo conversacional.

## Arranque en Windows

### 1. Iniciar el Core

```powershell
.\start.bat
```

### 2. Iniciar la GUI PC

En otra terminal:

```powershell
.\start-gui.bat
```

La ventana incluye:

- historial de la sesión visible;
- caja de texto y envío con botón o `Ctrl + Enter`;
- indicador de conexión y backend;
- botón de grabación de voz;
- switch para reproducir respuestas con voz;
- botón de backup;
- ventana de facts guardados con alta/eliminación manual;
- prueba de mensajes proactivos por polling.

### Cliente terminal alternativo

```powershell
.\start-client.bat
```

## Arranque en Linux

```bash
./start.sh
```

En otra terminal:

```bash
./start-gui.sh
# o terminal:
./start-client.sh
```

## Voz: qué funciona y qué debes validar

Configuración base:

```env
LUMEN_STT_ENABLED=true
LUMEN_WHISPER_MODEL=base
LUMEN_TTS_ENABLED=true
LUMEN_TTS_ENGINE=edge
LUMEN_TTS_VOICE=es-MX-DaliaNeural
```

Flujo de la GUI:

1. `Hablar` graba 5 segundos desde el micrófono.
2. El Core transcribe el audio con Whisper.
3. Envía el texto al backend LLM.
4. Devuelve respuesta escrita.
5. Si TTS está activo, genera audio Edge TTS.
6. Si `Responder con voz` está activado, la GUI reproduce el archivo generado.

La orquestación HTTP se probó con audio simulado. La captura física, instalación de FFmpeg, descarga del modelo Whisper, Edge TTS y altavoces dependen del equipo donde ejecutes LUMEN.

## Memoria

- Base de datos: `lumen-core/data/lumen_memory.db`.
- Conserva historial por sesión.
- Recupera hasta seis mensajes recientes de sesiones anteriores como contexto básico.
- Los facts se gestionan manualmente desde la GUI o por API.
- `LUMEN_AUTO_FACTS_ENABLED=false` es el valor por defecto. Activarlo ejecuta patrones simples y puede guardar datos incorrectos; por eso sigue marcado como experimental.

## Backup

Los backups se guardan en:

```text
lumen-core/data/backups/
```

Configuración:

```env
LUMEN_BACKUP_ENABLED=true
LUMEN_BACKUP_INTERVAL_HOURS=24
LUMEN_BACKUP_CHECK_MINUTES=60
LUMEN_MAX_BACKUPS=30
```

Puedes crear un backup inmediato con el botón **Backup** de la GUI o con API autenticada:

```powershell
$headers = @{ Authorization = "Bearer TU_TOKEN" }
Invoke-RestMethod -Method POST -Uri http://localhost:8090/api/backup -Headers $headers
```

Se usa el mecanismo de snapshot de SQLite, no una copia ciega del archivo mientras WAL está activo.

## Proactividad

En v0.2:

```env
LUMEN_PROACTIVE_ENABLED=false
```

- La cola persistente y el polling del cliente están implementados.
- El botón **Probar aviso** comprueba la recepción inmediatamente.
- Las intervenciones automáticas están desactivadas por defecto, porque todavía son reglas simples y dependen del LLM.

## Seguridad local

- `/api/health` es público y solo informa que el Core está vivo.
- `/api/status`, chat, memoria, backup, voz y proactividad requieren `Authorization: Bearer <LUMEN_SECRET>`.
- El Core se enlaza a `127.0.0.1` por defecto.
- No uses claves reales en `.env.example` ni subas tu `.env`.
- Abrir el Core a la red local para Android exige cambiar host y token con cuidado; no forma parte de la validación principal.

## Pruebas incluidas

Desde la raíz y con dependencias instaladas:

```powershell
python -m compileall -q lumen-core lumen-pc tests
python tests\gui_import_test.py
python tests\smoke_test.py
```

En Linux cambia `\` por `/`.

Estas pruebas validan importación/compilación, auth, endpoints, chat con backend `mock`, memoria manual, voz orquestada mediante dobles controlados, backup y polling. No falsifican una prueba de micrófono o API real.

## Android

`lumen-mobile/` conserva pantallas Flutter y un servicio HTTP ajustado al contrato v0.2. No se generó APK, no se probaron permisos de micrófono ni persistencia real de configuración. Se mantiene solo para no perder la base móvil mientras el cliente PC se estabiliza.
