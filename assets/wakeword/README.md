# Gaia wake-word model

GAIA never substitutes another assistant's acoustic model. The runtime requires a real OpenWakeWord-compatible model trained for **Gaia**.

- `gaia_training.yml` is a reproducible starting configuration for the current official OpenWakeWord custom-model workflow.
- `python tools/prepare_gaia_wakeword.py status` reports whether the model is installed.
- Install a trained model with `python tools/setup_gaia_wakeword.py /path/to/gaia.onnx --sha256 <trusted-sha256>`.

The release intentionally does **not** bundle an unverified third-party “Gaia” model. Current public OpenWakeWord tooling supports custom training, but the final acoustic model must be trained/evaluated and then physically calibrated on the target microphone. Whisper fallback remains development-only.
