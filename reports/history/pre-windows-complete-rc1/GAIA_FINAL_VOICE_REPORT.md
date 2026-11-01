# GAIA Final Voice Report

Status: `REAL_IMPLEMENTATION_PHYSICAL_VALIDATION_PENDING`.

Wake detection has a real openWakeWord path with explicit Whisper fallback, post-wake recording and cleanup. Pipecat creates a real `PipelineTask` and sends `InterruptionFrame` for barge-in; Silero VAD, STT and TTS are lazy provider boundaries. The Sandbox has no microphone/speaker and lacks sounddevice, openwakeword and Silero packages, so audio capture, wake accuracy, playback latency and interruption must be validated on Windows.
