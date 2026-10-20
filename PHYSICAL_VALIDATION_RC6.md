# GAIA-AI v1.0-RC6 Physical Validation

La plantilla RC6 conserva exactamente doce controles y comienza con `PASS=0`, `FAIL=0`, `PENDING=12`, `NOT_MEASURED=0`, `BLOCKED=0`, `SKIP=0`. La ejecución Linux no produce evidencia física.

| ID | Control | Estado inicial |
|---|---|---|
| `windows_runtime` | Windows 11, Python 3.11 y extracción limpia | PENDING |
| `uia` | UI Automation read-only y frontera de interacción | PENDING |
| `smtc_display` | SMTC y una/tres pantallas | PENDING |
| `audio` | Audio frente al equipo | PENDING |
| `ollama_qwen` | Ollama/Qwen local | PENDING |
| `gpu_vram` | GPU/VRAM read-only | PENDING |
| `battery_thermal` | Batería y temperatura | PENDING |
| `lan_tls` | LAN/TLS | PENDING |
| `android_flutter` | Android/Flutter | PENDING |
| `signing` | Firma y verificación | PENDING |
| `long_session_soak` | Sesiones de 10/30 minutos | PENDING |
| `rollback_recovery` | Migración, snapshot y rollback | PENDING |

El equipo objetivo indicado para la futura comprobación es ASUS TUF Gaming F15, Intel Core i5-12500H, 48 GB RAM, RTX 3050 Laptop y Windows 11. Esa descripción no es evidencia y no autoriza ningún PASS.
