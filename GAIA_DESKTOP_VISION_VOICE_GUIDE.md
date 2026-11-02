# GAIA · Voz, pantalla y escritorio holográfico (2.0 RC3)

Esta entrega **no activa una cámara ni graba continuamente la pantalla**. La captura se hace una sola vez, con autorización explícita y elección de monitor, y se interpreta mediante Ollama **local**. Las imágenes no se guardan en disco ni se convierten en órdenes ejecutables.

## Uso en Windows 11

1. Instala GAIA con `Setup-GAIA.ps1` y el perfil Desktop/Full-Computer. Debe estar presente **PySide6**.
2. Inicia el lanzador `lumen-pc/gaia_desktop_launcher.py`. El icono holográfico animado se muestra permanentemente; haz clic en él para abrir **Centro de Control**, donde se ven las respuestas y errores.
3. Configura Ollama para chat mediante `OLLAMA_URL=http://127.0.0.1:11434` y un modelo de conversación instalado, según la configuración del Core. El Core responde por HTTP aunque Ollama esté apagado, pero el chat no funciona hasta que el backend responda.
4. Para visión, instala un modelo local explícitamente con `ollama pull qwen2.5vl:7b` (o `qwen2.5vl:3b` si hay menos memoria) y establece `GAIA_VISION_MODEL=qwen2.5vl:7b`. No se descargan modelos grandes silenciosamente. También puedes elegir `qwen3-vl:4b` con una versión de Ollama compatible.
5. Abre Centro de Control y pulsa **Analizar pantalla** para el monitor seleccionado o escribe «GAIA mira mi pantalla»; esta última opción abre un diálogo de selección de monitor. Los dos monitores aparecen de forma independiente, incluso si uno está en la gráfica integrada y otro en la dedicada.
6. Para hablar, **mantén Ctrl+Espacio**, habla y suelta la tecla. También funciona el botón **Hablar / Detener** del Centro de Control. La voz requiere `faster-whisper`, Piper TTS y sus modelos; si no están disponibles, la transcripción o síntesis informa el error en la interfaz. Comprueba **Diagnóstico**.
7. `GAIA_WAKEWORD_ENABLED=false` es la configuración inicial segura. Para activación con la palabra «GAIA» hace falta un modelo real `assets/wakeword/gaia.onnx`. Si falta, el interruptor informa el problema y **no** sustituye a GAIA por Jarvis. El botón PTT sigue disponible.

## Límites y seguridad

- Las observaciones visuales son **solo lectura**, nunca disparan clics ni ejecutan comandos. Captura y acción operativa tienen permisos y componentes distintos.
- Las capturas se reducen a 1600×1000 píxeles, se envían solo a Ollama en `localhost` y no se guardan en archivos.
- Si el modelo de visión, el micrófono, Piper o el Core faltan, GAIA debe decir cuál es el problema en el panel. Una prueba del Core `HTTP 200` no significa que el modelo esté listo.
- No se ha certificado aún el efecto visual PySide6, los atajos globales o la voz real en el equipo Windows del usuario. Se requiere una prueba física para confirmar control, volumen y rendimiento.
- No se incluye un modelo de activación por voz personalizado no entrenado ni se promete visión permanente del escritorio.
