# GAIA-AI v0.6.2 — Baseline audit v0.6.1

## Evidencia de entrada

La base se obtuvo de `/home/ubuntu/GAIA-AI-v0.6.1-final.zip`. El checksum verificado fue `99547643c97aeefc0e7fd70d16fd5603be9d4731ec0b60a32d41ad4785d46514`; `unzip -tq` pasó y el package gate se ejecutó antes de crear bytecode o datos runtime.

La extracción limpia contiene **49 tests directos no-gate**, todos pasaron, y `compileall` de Core/PC/tests/tools pasó. La reproducción independiente de los hallazgos A–C se ejecutó antes de crear este worktree.

## Hallazgos reproducidos

| ID | Hallazgo | Evidencia baseline | Riesgo | Prioridad |
|---|---|---|---|---|
| A | El host filtra pending por `item["device"] == self.device_id`; Android solicitante y PC ejecutor quedan confundidos. | `RemoteActionHost.pending()` devuelve cero para `device=android-owner,target_host=pc-main`. | Crítico: Android→PC no funciona de forma confiable. | P0 |
| B | Una acción con `confirmation_required=false` se guarda con `approved=false`. | `/api/chat` devuelve auto-policy, pero el estado pending conserva `approved=false`. | Crítico: `ALWAYS_ALLOW` no llega al host. | P1 |
| C | Android puede entrar al diálogo ante cualquier action event sin respetar `confirmation_required=false`. | `ChatScreen` llama `_confirmRemoteAction` desde la rama de action sin guard correcto. | Crítico: popup repetido y UX inconsistente. | P1 |
| D | El classifier no deriva su catálogo directamente del Capability Registry completo. | `action_intent.py` y classifier mantienen rutas históricas; muchas capabilities no tienen lenguaje natural usable. | Alto: capacidades declaradas no son accesibles. | P2 |
| E | `pycaw`/`comtypes` son imports opcionales pero no están en requirements PC. | `lumen-pc/requirements.txt` no incluye dependencias de audio Windows. | Medio/alto: instalación limpia degrada audio. | P4 |
| F | `display_list()` devuelve solo monitor sintético primary. | Adapter usa métricas globales, no enumera monitores reales. | Alto: multi-display no funciona. | P4/P7 |
| G | App discovery solo conoce cuatro apps code-owned. | `discover_installed_apps()` no enumera Start Menu/registry completo y no persiste trust. | Alto: Chrome/Discord/Steam no son descubribles. | P5 |
| H | Files están limitados a proyectos trusted, sin trusted folders personales. | No existe modelo persistente de carpetas autorizadas. | Alto: operaciones personales no son usables con scope seguro. | P6 |
| I | Android no es un proyecto Flutter build-ready completo. | Falta scaffold Android/Gradle/Manifest/tests estándar. | Alto: no se puede validar APK. | P8 |
| J | El botón Scan QR es decorativo. | `PairingScreen` muestra mensaje de futura habilitación. | Medio/alto: onboarding no es real. | P9 |
| K | El host guarda token local en archivo plaintext best-effort. | `.gaia_remote_host.token` depende de chmod y no usa DPAPI/Credential Manager. | Alto: exposición local del token. | P8 |

## Gates críticos para esta versión

No se declarará PASS si el flujo Android autenticado no puede crear una acción con `requesting_device` separado de `target_host`, si un grant `ALWAYS_ALLOW` sigue generando una pending no aprobada, si Android muestra popup con `confirmation_required=false`, si una capability desconocida ejecuta algo, si un path escapa de trusted folders, si un host puede ejecutar dos veces o si los tests de instalación limpia fallan.

La validación física de Windows/Flutter continúa separada. Si Flutter no está disponible, se debe entregar scaffold completo y marcar **STATIC ONLY — FLUTTER TOOLCHAIN NOT AVAILABLE**, nunca fabricar APK o `BUILD VERIFIED`.
