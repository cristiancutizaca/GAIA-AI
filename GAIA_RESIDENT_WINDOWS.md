# GAIA-AI 2.0 | Asistente residente en Windows 11

Este documento describe la ruta **v2.0**. El README principal conserva
contratos históricos RC6. No confundas los informes automatizados con pruebas
físicas del micrófono o la GPU.

## Instalación

1. Usa Python **3.11 x64** y Windows 11. Coloca el proyecto en una ruta estable,
   preferiblemente fuera de carpetas sincronizadas, por ejemplo `C:\\GAIA`.
2. Abre PowerShell dentro de la carpeta del repositorio y ejecuta:

   ```powershell
   .\install-gaia.ps1 -GenerateSecret
   ```

   El instalador conserva tu `.env` y los datos. Si el secreto existente es
   fuerte no lo reemplaza. No compartas ese archivo ni el token del Action Host.
   DeepSeek Harness se instala como componente opcional heredado. El backend
   predeterminado es Ollama: no requiere instalar DeepSeek para responder.
3. Instala Ollama por separado, inicia su servidor y descarga el modelo que
   hayas configurado en `LUMEN_LLM_MODEL`. Consulta modelos instalados con
   `ollama list`. No se garantiza aceleración AMD hasta ver `ollama ps`.
4. Mantén `LUMEN_HOST=127.0.0.1` y `GAIA_LAN_ENABLED=false` mientras pruebas.
   No habilites acceso remoto sin un canal cifrado.

## Iniciar y activar el arranque automático

```powershell
.\start-gaia.bat
# En otra terminal, con GAIA ejecutándose:
.\.venv\Scripts\python.exe tools\gaia_resident_doctor.py --json
# Solo después de confirmar que funciona:
.\.venv\Scripts\python.exe tools\gaia_startup.py enable
.\.venv\Scripts\python.exe tools\gaia_startup.py status
```

**No ejecutes GAIA como administrador por defecto.** El arranque automático es
por usuario al iniciar sesión, no un servicio anterior al inicio de sesión.

Para desactivar el inicio con Windows:

```powershell
.\.venv\Scripts\python.exe tools\gaia_startup.py disable
```

La interfaz debe aparecer en la bandeja de Windows. En ella puedes abrir
«Comandos», encender/apagar el micrófono y reiniciar o cerrar GAIA.

## Voz

- Acceso rápido: **Ctrl+Espacio**. Primera pulsación inicia la grabación;
  segunda pulsación la finaliza y envía. Esta combinación funciona como
  **interruptor**, no como «mantener pulsado». Máximo 20 segundos por captura.
- El menú «Grabar / finalizar voz» hace lo mismo.
- `GAIA_MICROPHONE_ENABLED=false` desactiva la captura inicial.
- `GAIA_SPEAK_RESPONSES=true` permite respuestas TTS para comandos de voz.
- La detección continua de «GAIA» está desactivada por defecto. Para usarla
  se requiere un **modelo ONNX específico** y `GAIA_WAKEWORD_MODEL` con su ruta.
  Instala `requirements-wakeword.txt` únicamente si tienes el modelo.
- «Micrófono OFF» detiene la grabación y el detector de wake word de GAIA; no
  silencia otros programas del sistema.

## Control de PC y seguridad

El supervisor inicia Core, PC Action Host y Qt Shell en la misma sesión.
El Core sigue siendo responsable de aprobar las acciones. Configuración de
referencia: `GAIA_ACTION_CONFIRM_POLICY=CONFIRM_EXECUTION` y
`GAIA_REMOTE_HOST_ENABLED=true`. No configures `AUTO_SAFE` ni otorgues
permisos amplios sin comprobar el alcance de cada acción.

El supervisor reinicia un Shell que se cierra inesperadamente hasta tres
veces por minuto; «Salir» lo detiene. Registros:
`%USERPROFILE%\.gaia\logs\core.log`,
`action-host.log` y `desktop.log`.

Si Windows entra en suspensión, GAIA no controla el escritorio. Funciona
mientras la sesión de usuario esté activa; puede seguir escuchando órdenes
de texto con el sistema desbloqueado. No sortea bloqueo de pantalla/UAC ni
ventanas seguras de Windows.

## Pruebas pendientes sobre hardware real

- Instalación de PySide6/Whisper en el PC de destino.
- Reinicio y entrada automática del usuario en Windows.
- Captura de micrófono y permiso de grabación.
- `RegisterHotKey` con la combinación Ctrl+Espacio libre.
- TTS y reproducción con el dispositivo de salida seleccionado.
- Modelo Ollama y uso real de VRAM AMD.
- Emparejamiento y autorización del Action Host.
- Ejecución verificada de órdenes de Windows, sin elevación de privilegios.

Los módulos de planificación multiacción, visión, OpenHands, Android y
automatizaciones siguen siendo funciones que requieren integración y pruebas:
**no se consideran terminadas por la existencia de este instalador**.
