# Arquitectura de memoria de GAIA-AI v0.5.2

GAIA usa exclusivamente SQLite. No hay vector database. FTS5 se utiliza cuando está disponible y existe fallback textual para instalaciones sin FTS5. La base conserva el namespace histórico `lumen_memory.db` y el schema mayor 5.

## Capas

| Capa | Contenido | Persistencia |
|---|---|---|
| Conversación | Mensajes, sesiones, dispositivo y timestamp | `messages`, `sessions` |
| Semántica | Facts con categoría, fuente, confianza, estado, pin y uso | `user_facts`, FTS/fallback |
| Trabajo temporal | Tareas abiertas, notas de proyecto y sesiones | `open_tasks`, `project_notes`, `work_sessions` |
| Continuidad | Summaries, temas, decisiones y tareas derivadas | `session_summaries` |
| Acciones | Resultado aggregate, plan_id, step, status y duration | `action_history` |
| Administración | Tokens hashados, dispositivos y audit log | `device_tokens`, `devices`, `admin_audit` |

`open_tasks` no se promociona automáticamente a fact permanente. `GAIA_AUTO_MEMORY_ENABLED=false` conserva el comportamiento opt-in. La extracción de facts es una sugerencia validada por política, no una autoridad de persistencia.

## Context bundle

El Core prepara contexto jerárquico: resumen de sesión, proyecto activo registrado, notas relevantes, tareas abiertas, facts relevantes, mensajes recientes y acciones verificadas. El límite de caracteres se aplica antes del prompt. En `privacy=strict` se reducen título de ventana, rutas, sistema y contexto sensible.

La memoria recibida desde el cliente PC es telemetría read-only. No otorga permisos ni puede convertir texto de ventana, proyecto u Ollama en una acción.

## Migración y backup

La migración v4→v5 añade columnas y tablas de manera conservadora, incluyendo compatibilidad para `updated_at` heredado. No se cambia el schema mayor en v0.5.2. El snapshot SQLite y Brain Backup son independientes; ambos se pueden restaurar siguiendo `ROLLBACK.md` y `AUDIT.md`.

Las acciones se guardan después de que el cliente local envía un resultado validado. Para un plan se guarda una fila aggregate (`step=0`) y una fila por paso cuando existe resultado. Una cancelación antes de comenzar conserva aggregate `cancelled` y cero pasos ejecutados. El texto natural posterior no se guarda como nueva intención.
