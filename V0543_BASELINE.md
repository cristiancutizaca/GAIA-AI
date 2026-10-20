# GAIA-AI v0.5.4.3 — Baseline de v0.5.4.2

## Alcance

La base de trabajo se extrajo de `GAIA-AI-v0.5.4.2-project.zip` y su documentación se contrastó con `GAIA-AI-v0.5.4.2-docs.zip`. El Core reporta `0.5.4.2-pc`. Esta evidencia se conserva antes de modificar la implementación para que el release v0.5.4.3 pueda demostrar qué fallos corrigió.

## Reproducción de Bug A

En v0.5.4.2, los siguientes marcos naturales de una petición externa no se clasifican como `ACTION_REQUEST` mediante `_is_action_request()`:

| Solicitud | Estado observado |
|---|---|
| `Te encargo que abras Photoshop.` | `CONVERSATION` |
| `Cuando puedas, abre Photoshop.` | `CONVERSATION` |
| `Si tienes un momento, abre Photoshop.` | `CONVERSATION` |
| `En cuanto puedas, abre Photoshop.` | `CONVERSATION` |
| `No te olvides de abrir Photoshop.` | `CONVERSATION` |

Cuando el modelo devuelve `Listo, ya abrí Photoshop.` en ese estado conversacional, `_ground_conversation_response()` de v0.5.4.2 permite el texto porque la defensa de claims está condicionada a `ACTION_REQUEST`. Por tanto, el baseline demuestra que la seguridad no puede depender únicamente de que el classifier lingüístico acierte.

## Reproducción de Bug B

Con un `VerifiedActionResult` exitoso para `open_calculator`, v0.5.4.2 pasa sin sanitizar los siguientes claims adicionales:

| Respuesta no soportada | Estado observado |
|---|---|
| `Calculadora abierta. También detuve Spotify.` | Pasa completa |
| `Calculadora abierta. También lancé Spotify.` | Pasa completa |
| `Calculadora abierta. También creé prueba.txt.` | Pasa completa |
| `Calculadora abierta. También renombré archivo.txt.` | Pasa completa |
| `Calculadora abierta. También activé el Wi-Fi.` | Pasa completa |
| `Calculadora abierta. También bloqueé la pantalla.` | Pasa completa |

La prueba de reproducción es `tests/v0543_baseline_repro.py`. La salida observada fue:

```text
V0543 BASELINE REPRO PASS: five natural frames fell to CONVERSATION, conversation claim passed, six unsupported post-action claims passed.
```

El texto `PASS` identifica que la reproducción coincide con el fallo esperado del baseline; no significa que v0.5.4.2 sea seguro frente a esos escenarios.

## Criterio de corrección v0.5.4.3

El parche debe sustituir la confianza en regex enumerativas por una combinación de marcos lingüísticos negativos/externos, estado seguro cuando existe una intención potencial de efecto sin resultado verificado y una respuesta factual determinista. Un `VerifiedActionResult` solo autoriza hechos dentro del alcance de su capability; no autoriza otro proceso, aplicación, archivo, red, pantalla o estado del sistema. El post-action no puede añadir efectos fuera de scope aunque el modelo use verbos o nombres no incluidos en una lista previa.
