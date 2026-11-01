# GAIA 2.0 Windows Complete RC2 — Dependency Isolation

RC2 fixes two dependency conflicts discovered during a real Windows Full-Computer install.

## Main runtime: Python 3.11

`.venv` contains GAIA Core/Desktop/Voice/Browser/Computer Use. Browser Use remains isolated from Mem0's incompatible PostHog range.

## Mem0 sidecar: Python 3.11

`.venv-memory` installs `mem0ai==2.2.1`. GAIA invokes it through `tools/sidecars/mem0_worker.py` over JSON stdin/stdout. This prevents Mem0's `posthog>=7.14.0` from conflicting with Browser Use's pinned `posthog==7.7.0`.

## OpenHands sidecar: Python 3.12

`.venv-coding` installs matching `openhands-sdk==1.58.1` and `openhands-tools==1.58.1`. GAIA invokes it through `tools/sidecars/openhands_worker.py`. Python 3.12 is installed through winget when needed; GAIA Core remains on Python 3.11.

## Recovery from RC1

Do not reuse an RC1 `.venv` that already installed Mem0 into the main environment. Use RC2 in a new folder for the cleanest installation. RC2 also removes `mem0ai`, `openhands-sdk` and `openhands-tools` from the main venv before resolving the main profile, so reruns can repair older partial environments.
