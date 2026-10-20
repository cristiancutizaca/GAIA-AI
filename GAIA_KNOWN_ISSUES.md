# Known issues and limits

- Windows 11 + Python 3.11 installation must still be run on the ASUS TUF.
- Real DeepSeek Harness response/streaming/timeout/cancel/shutdown requires the pinned SDK, Ollama and an installed model. It is not claimed here.
- Ollama/Qwen physical inference is not measured in this sandbox.
- Tkinter is absent in the sandbox; GUI tests are `DEPENDENCY_MISSING`, not PASS.
- Audio, GPU/VRAM, battery/thermal, LAN/TLS and Android remain physical validation items.
- The package does not download models or start Ollama automatically.
