# Gaia wake-word model

GAIA never substitutes another assistant's acoustic model. Production requires an OpenWakeWord-compatible ONNX model trained for **Gaia**, installed with:

```bash
python tools/setup_gaia_wakeword.py /path/to/gaia.onnx --sha256 <trusted-sha256>
```

Then set `GAIA_WAKEWORD_MODEL` to the installed file and enable `GAIA_WAKEWORD_ENABLED=true`. The Sandbox has no microphone, so acoustic false-positive/false-negative validation remains a physical Windows task. `GAIA_WAKEWORD_WHISPER_FALLBACK=true` is development-only and is reported as such by health checks.
