"""
GAIA — Wake Word Detection

Escucha continuamente el micrófono buscando la palabra "Gaia".
Cuando la detecta, graba el mensaje y lo envía al Core.

Usa Whisper en modo ultraligero (tiny) solo para detección.
Al detectar wake word, cambia a modelo normal para transcribir.
"""
import asyncio
import numpy as np
import tempfile
import wave
import os
import subprocess
import shutil
import threading
from typing import Callable

# Configuración
WAKE_WORD = "gaia"
SAMPLE_RATE = 16000
CHUNK_DURATION = 2.0  # Segundos por chunk para detección
RECORD_DURATION = 8.0  # Segundos de grabación después de wake word
SILENCE_THRESHOLD = 500  # Nivel de silencio para detener grabación
SILENCE_DURATION = 1.5  # Segundos de silencio para cortar


class WakeWordListener:
    def __init__(self, on_wake: Callable[[str], None] = None):
        """
        on_wake: callback que recibe la ruta del audio grabado
        """
        self.on_wake = on_wake
        self.running = False
        self._thread = None
        self._whisper_model = None

    def _load_whisper(self):
        if self._whisper_model is None:
            import whisper
            # Modelo tiny para detección rápida de wake word
            self._whisper_model = whisper.load_model("tiny")
        return self._whisper_model

    def _record_chunk(self, duration: float) -> np.ndarray:
        """Graba un chunk de audio."""
        import sounddevice as sd
        audio = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16'
        )
        sd.wait()
        return audio.flatten()

    def _save_wav(self, audio: np.ndarray, path: str):
        """Guarda audio como WAV."""
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())

    def _detect_wake_word(self, audio: np.ndarray) -> bool:
        """Verifica si el audio contiene la wake word."""
        # Verificar que hay sonido suficiente
        if np.max(np.abs(audio)) < SILENCE_THRESHOLD:
            return False

        model = self._load_whisper()
        # Guardar temporalmente
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
            tmp = temp.name
        self._save_wav(audio, tmp)

        try:
            result = model.transcribe(
                tmp,
                language="es",
                fp16=False,
                no_speech_threshold=0.6,
            )
            text = result["text"].lower().strip()
            # Buscar variaciones de "lumen"
            return any(w in text for w in ["gaia", "gaya", "gaia,", "oye gaia", "hey gaia", "hey gaya"])
        except:
            return False
        finally:
            try:
                os.unlink(tmp)
            except:
                pass

    def _record_message(self) -> str:
        """
        Graba el mensaje del usuario después de detectar wake word.
        Para cuando hay silencio prolongado.
        """
        import sounddevice as sd

        print("  🎤 Te escucho...")

        all_audio = []
        silence_frames = 0
        max_frames = int(RECORD_DURATION / 0.5)  # Máximo de chunks

        for _ in range(max_frames):
            chunk = sd.rec(
                int(0.5 * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='int16'
            )
            sd.wait()
            chunk_flat = chunk.flatten()
            all_audio.append(chunk_flat)

            # Detectar silencio
            volume = np.max(np.abs(chunk_flat))
            if volume < SILENCE_THRESHOLD:
                silence_frames += 1
                if silence_frames >= int(SILENCE_DURATION / 0.5):
                    break
            else:
                silence_frames = 0

        audio = np.concatenate(all_audio)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
            output_path = temp.name
        self._save_wav(audio, output_path)
        print("  ✓ Mensaje capturado")
        return output_path

    def _listen_loop(self):
        """Loop principal de escucha."""
        print("  👂 Escuchando wake word 'Gaia'...")

        while self.running:
            try:
                # Grabar chunk corto
                audio = self._record_chunk(CHUNK_DURATION)

                # Verificar wake word
                if self._detect_wake_word(audio):
                    print("  ✨ ¡Wake word detectada!")

                    # Grabar mensaje completo
                    audio_path = self._record_message()

                    # Callback
                    if self.on_wake:
                        self.on_wake(audio_path)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"  [WakeWord] Error: {e}")
                import time
                time.sleep(1)

    def start(self):
        """Iniciar escucha en thread separado."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Detener escucha."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None


# === Para usar desde el cliente PC ===

async def wake_word_client(core_url: str, secret: str, device: str = "pc"):
    """
    Cliente completo de wake word que escucha y envía al Core.
    """
    import httpx

    def on_wake(audio_path: str):
        """Callback cuando se detecta wake word."""
        async def send():
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    with open(audio_path, "rb") as f:
                        r = await client.post(
                            f"{core_url}/api/chat/voice",
                            headers={"Authorization": f"Bearer {secret}"},
                            params={"device": device},
                            files={"audio": ("message.wav", f, "audio/wav")},
                        )
                    data = r.json()
                    print(f"\n  Tú: {data.get('user_text', '?')}")
                    print(f"  GAIA: {data['response']}\n")

                    # Reproducir audio
                    audio_url = data.get("audio_url")
                    if audio_url:
                        r2 = await client.get(f"{core_url}{audio_url}", headers={"Authorization": f"Bearer {secret}"})
                        if r2.status_code == 200:
                            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp:
                                tmp = temp.name
                                temp.write(r2.content)
                            player = ["mpv", "--no-video", tmp] if shutil.which("mpv") else ["ffplay", "-nodisp", "-autoexit", tmp]
                            subprocess.run(player, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                            os.unlink(tmp)
            except Exception as e:
                print(f"  Error: {e}")
            finally:
                try:
                    os.unlink(audio_path)
                except:
                    pass

        asyncio.run(send())

    listener = WakeWordListener(on_wake=on_wake)
    listener.start()

    print("  Wake word activa. Di 'Gaia' para hablar.")
    print("  Ctrl+C para salir.\n")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        listener.stop()
        print("\n  Wake word desactivada.")
