# Validación física de GAIA en Windows 11

Esta guía sirve para registrar la prueba con la PC de destino. Usa la rama `fix/gaia-windows-stability`, una copia de la instalación y datos de prueba. Conserva el entorno existente y apunta la copia a una base temporal para las pruebas que escriben o borran recuerdos. Si se necesita probar una migración real, usa una copia consistente de SQLite o un Brain Backup.

## 1. Preparar la instalación de prueba

Desde **PowerShell**, situado en la carpeta de GAIA, comprueba los intérpretes con `py -0p`. El perfil completo usa Python 3.11 para Core, Desktop, Browser y Memory, y 3.12 para el sidecar de Coding. Puedes reparar solo el perfil que estás comprobando. El ejemplo completo reutiliza las instalaciones de Ollama y los modelos ya preparados.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Setup-GAIA.ps1 -SkipOllama -SkipModels
.\.venv\Scripts\python.exe tools\gaia_models.py status
.\.venv\Scripts\python.exe tools\gaia_doctor_v2.py
.\.venv\Scripts\python.exe lumen-pc\gaia_desktop_launcher.py --once
```

Si estás corrigiendo únicamente la incompatibilidad PyAV en una instalación con voz, puedes reparar ese entorno sin reinstalar GAIA. Usa la copia con los cambios de la rama.

```powershell
.\.venv\Scripts\python.exe -m pip install "av>=11,<19"
.\.venv\Scripts\python.exe -m pip check
```

Si faltan los pesos y autorizas prepararlos, ejecuta `tools\gaia_models.py install baseline` con el mismo Python. Los pesos de Whisper preparados en la instalación se utilizan sin descarga automática al pulsar Hablar. `LUMEN_STT_ALLOW_DOWNLOAD=true` permite esa descarga si se desea. Conserva `LUMEN_PIPER_DATA_DIR` y `GAIA_MEMORY_DB` cuando apunten a ubicaciones ya válidas. Si cambias `LUMEN_PORT`, verifica que la URL explícita `LUMEN_CORE_URL` use ese mismo puerto.

## 2. Comprobar Ollama y OpenCode

Ejecuta las consultas desde PowerShell con el servicio local que usa GAIA. Sustituye la variable de ejemplo por tu modelo configurado y el puerto si es distinto.

```powershell
$gaiaModel = 'qwen3.5:4b'
$gaiaOllama = 'http://127.0.0.1:11434'
Get-Command ollama -All
ollama --version
ollama list
ollama ps
ollama show $gaiaModel
Invoke-RestMethod "$gaiaOllama/api/version"
Invoke-RestMethod "$gaiaOllama/api/ps"
```

Compara `ollama ps` antes y después de una respuesta de GAIA. Anota el procesador informado, el contexto efectivo y `size_vram` si está presente. Compara el Administrador de tareas en memoria dedicada y compartida. Una lista vacía indica que el servicio no reporta un modelo cargado en ese momento. El máximo del modelo y el contexto activo de la sesión son datos distintos. Usa un solo modelo durante la prueba de base y registra el tiempo con modelo frío y caliente.

Ejecuta el Doctor desde la carpeta donde falla OpenCode. La ruta absoluta del ejemplo debe ajustarse a tu instalación.

```powershell
Get-Command opencode -All
opencode --version
& 'C:\ruta\GAIA-AI\.venv\Scripts\python.exe' 'C:\ruta\GAIA-AI\tools\gaia_doctor_v2.py' --opencode-config
```

El Doctor identifica ejecutable, coincidencias de PATH y archivos de configuración visibles. `CONFIG_ERROR` indica que la CLI rechazó la configuración en ese contexto. La configuración efectiva puede contener credenciales. Si ejecutas `opencode --pure debug config` manualmente, conserva la salida en tu equipo y comparte solo el error redactado. Si confirmas un archivo defectuoso, guarda una copia privada antes de editarlo. Prueba Qwen con un proyecto temporal, comprobando ruta, existencia y contenido con PowerShell después de cada acción autorizada.

## 3. Ejecutar la prueba física

Inicia GAIA con `.\.venv\Scripts\python.exe lumen-pc\gaia_desktop_launcher.py`. Crea el registro de verificación en una carpeta privada fuera del repositorio con el comando siguiente.

```powershell
.\.venv\Scripts\python.exe tools\physical_validation.py new --output-dir "$env:USERPROFILE\Documents\GAIA-Pruebas"
```

| Paso | Acción y evidencia necesaria |
|---|---|
| 1–2 | Abre el Centro de Control desde la bandeja. Comprueba que haya una sola instancia, que el Core responda y que una configuración sin Ollama muestre su estado por separado. Observa los estados al hablar, procesar y ejecutar. |
| 3–6 | Elige **MCHOSE V9 PRO**. Habla en español con el botón y luego con `Ctrl+Espacio`, con GAIA minimizada y otra aplicación enfocada. Prueba soltar Espacio primero y Ctrl primero. Cada pulsación debe producir una sola transcripción. Repite con un atajo alternativo si hay conflicto. |
| 7–9 | Pide una respuesta a Ollama con dos frases. Comprueba el texto, el primer bloque de audio y que ambas frases se oigan en orden. Registra si Piper funciona o se activa SAPI. Interrumpe durante la primera frase y durante la síntesis de otra. Repite con los altavoces y el headset para detectar eco o cortes falsos. |
| 10 | Guarda por voz «Recuerda que la caja de prueba es naranja». Recupera, edita y vuelve a recuperar el recuerdo. |
| 11–12 | Pide que abra el Bloc de notas. Rechaza primero y comprueba que no se abre. Autoriza una nueva propuesta y comprueba que sí se abre. Registra el resultado visible y la auditoría del host. |
| 13–14 | Di «GAIA, mira mi pantalla». Cancela el selector una vez. Después elige cada monitor por separado con un texto de prueba distinto y confirma que el resultado se refiere al monitor correcto. Registra captura y análisis por separado. |
| 15 | Alterna conversación, memoria y acciones durante al menos 20 minutos. Registra CPU, RAM y VRAM al inicio, después del primer uso de voz y al final. Revisa que los temporales y procesos no se acumulen. |
| 16–17 | Apaga el micrófono a mitad de una grabación y verifica que no se envíe. Sal por la bandeja, comprueba que el Core que arrancó GAIA dejó el puerto y que no quedó otra instancia. Reinicia y vuelve a recuperar el recuerdo. |
| 18 | Prueba con modelo visual ausente y sin `gaia.onnx` en la copia de prueba. Debe verse el componente faltante. Si tienes un modelo auténtico, registra activaciones correctas, falsos positivos y que el micrófono apagado detenga la escucha. |

Para medir latencia guarda en el registro el tiempo de captura mostrado por el escritorio, el tiempo desde la entrega del WAV hasta el primer bloque de salida y los percentiles de `GET /api/diagnostics/performance`. El primer bloque enviado al dispositivo y el primer sonido que oyes son mediciones distintas. Registra la latencia audible por separado.

Valida el registro con el subcomando `validate` y usa `record` para anotar observaciones con evidencia. Una comprobación sin evidencia física queda pendiente. El `PASS` de integridad del archivo de registro valida el formato y la coherencia del registro.

## Referencias

- [Registro físico de GAIA](tools/physical_validation.py)
- [Comandos de diagnóstico de Ollama](https://docs.ollama.com/api/ps)
- [Diagnóstico oficial de OpenCode](https://docs.opencode.ai/docs/troubleshooting/)
- [Incompatibilidad PyAV 19 y faster-whisper](https://github.com/SYSTRAN/faster-whisper/issues/1589)
