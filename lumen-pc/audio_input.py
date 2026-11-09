"""Resolve the configured microphone and a supported capture format."""
from __future__ import annotations


def input_settings(backend, preferred: int | None, rate: int = 16000, *, allow_native=False):
    try:
        device = backend.query_devices(preferred, "input")
    except Exception as exc:
        label = "predeterminado" if preferred is None else f"seleccionado ({preferred})"
        raise RuntimeError(f"No se pudo abrir el micrófono {label}. Comprueba que esté conectado y habilitado en Windows.") from exc
    name = str(device["name"])
    options = {"device": preferred, "channels": 1, "dtype": "int16", "samplerate": rate}
    try:
        backend.check_input_settings(**options)
    except Exception as exc:
        if not allow_native:
            raise RuntimeError(f"El micrófono {name} no admite captura mono a {rate} Hz. Prueba Push To Talk.") from exc
        options["samplerate"] = int(device["default_samplerate"])
        try:
            backend.check_input_settings(**options)
        except Exception as native_error:
            raise RuntimeError(f"No se pudo abrir {name} en mono. Revisa los permisos y el dispositivo de audio de Windows.") from native_error
    return options, name
