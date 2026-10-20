# GAIA Visualizer

`VisualizerConsumer` is read-only and consumes normalized Event Bus states. It has no authority and cannot call Action Host. A future local WebSocket/SSE UI must preserve this boundary and redact metadata.
