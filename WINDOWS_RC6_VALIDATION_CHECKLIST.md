# GAIA-AI v1.0-RC6 Windows Validation Checklist

Ejecute esta checklist únicamente en el equipo Windows objetivo y registre evidencia redacted fuera del proyecto. Cada control permanece PENDING hasta que el operador confirme método, limitaciones y evidencia suficiente.

| Área | Comprobación |
|---|---|
| Integridad | Hash, raíz única, miembros, duplicados, Zip Slip y archivos prohibidos. |
| Venv/Core | Python 3.11, venv privado, manifest RC6, schema 8–9 y health. |
| Cliente | GUI, conversación, memoria, permisos, ownership y provenance. |
| Ollama | Disponibilidad local comprobada sin descarga ni arranque automático. |
| Acción | Action Host, Safe Mode, kill switch, no doble ejecución y shutdown. |
| Pantallas/audio | Una y tres pantallas, SMTC y audio frente al equipo. |
| Hardware | GPU/VRAM y temperatura solo read-only; sensor ausente no equivale a cero. |
| Duración | Sesiones de 10 y 30 minutos sin crecimiento ilimitado ni tasks huérfanas. |
| Migración | Inspect, snapshot externo, apply aprobado y rollback aprobado. |
| Android/LAN | Flutter, límites, reconexión, LAN/TLS y errores. |
| Firma | Artefacto firmado real y verificación; un keystore existente no basta. |

No copie tokens, conversaciones, audio, bases, capturas completas, modelos, keystores ni rutas privadas a la evidencia distribuible.
