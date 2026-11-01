# GAIA 2.0 Windows Complete RC3 — Dependency Isolation

RC3 fixes conflicts discovered during a real Windows `full-computer` installation.

## Main runtime — `.venv`, Python 3.11

Contains GAIA Core, Desktop, Voice and deterministic Computer Use. It does **not** install Browser Use, Mem0 or OpenHands.

## Browser sidecar — `.venv-browser`, Python 3.11

Installs `browser-use==0.13.10` and Playwright in isolation. Browser Use 0.13.10 exact-pins several shared packages (including Click, HTTPX, Pydantic, python-dotenv, psutil and Pillow), so installing it in the Core environment can mutate Core/Voice dependencies. GAIA talks to the browser sidecar through `tools/browser_sidecar.py` using a JSON-lines subprocess protocol. URL policy, authority and untrusted-content handling remain in GAIA Core.

## Mem0 sidecar — `.venv-memory`, Python 3.11

Installs `mem0ai==2.2.1` separately, avoiding its PostHog range conflicting with Browser Use's exact PostHog pin.

## OpenHands sidecar — `.venv-coding`, Python 3.12

Installs the OpenHands SDK/tools separately because current OpenHands requires Python 3.12+. GAIA Core remains Python 3.11.

## Clean-install rule

Do not reuse a partially installed RC1/RC2 environment. Extract RC3 to a new folder so `.venv`, `.venv-browser`, `.venv-memory` and `.venv-coding` are created from clean interpreters.
