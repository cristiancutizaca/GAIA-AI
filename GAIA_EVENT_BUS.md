# GAIA Event Bus

`gaia_ext.event_bus.EventBus` carries bounded metadata-only events with timestamp, source, correlation/session/device IDs, severity and safe redaction. Supported states include IDLE, LISTENING, THINKING, PLANNING, WAITING_PERMISSION, EXECUTING, BROWSING, CODING, SPEAKING, INTERRUPTED, ERROR and SAFE_MODE.

The bus is observational. It does not execute tools, grant permissions or bypass the existing Event Engine/Action Host.
