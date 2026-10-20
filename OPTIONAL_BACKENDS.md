# Optional backend installation

GAIA Core starts without heavy providers. Install optional groups in isolated virtual environments when their dependency graphs conflict with FastAPI/Core:

```bash
python3 -m venv .venv-browser && . .venv-browser/bin/activate
pip install -r requirements-browser.txt
playwright install chromium
```

Voice:

```bash
python3 -m venv .venv-voice && . .venv-voice/bin/activate
pip install -r requirements-voice.txt
```

Mem0 and Graphiti must be configured explicitly. Mem0 requires `MEM0_CONFIG_JSON` with a local embedding/vector configuration; Graphiti requires `GRAPHITI_NEO4J_URI`, `GRAPHITI_NEO4J_USER`, and `GRAPHITI_NEO4J_PASSWORD`. GAIA does not silently send personal memory to cloud services.

OpenHands requires an SDK-compatible isolated coding runtime and is only invoked in a temporary workspace. UI-TARS requires a real display/model runtime and remains blocked in the headless Sandbox.

Enable providers only after installation:

```bash
export GAIA_FEATURE_BROWSER=true
export GAIA_FEATURE_VOICE_V2=true
export GAIA_FEATURE_VAD=true
export GAIA_FEATURE_MEM0=true
export GAIA_FEATURE_GRAPH_MEMORY=true
export GAIA_FEATURE_CODING_WORKER=true
export GAIA_FEATURE_COMPUTER_USE=true
```
