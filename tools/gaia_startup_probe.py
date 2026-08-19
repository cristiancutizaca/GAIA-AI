#!/usr/bin/env python3
"""Sonda read-only para start-gaia; no inicia ni detiene procesos."""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    url = f"http://{args.host}:{args.port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"OFFLINE: {url} ({exc})")
        return 1
    if payload.get("name") == "GAIA" and payload.get("status") == "online":
        print(f"ACTIVE: GAIA Core {payload.get('version', 'unknown')} en {url}")
        return 0
    print(f"FOREIGN: el puerto responde, pero no es GAIA Core: {payload.get('name', 'desconocido')}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
