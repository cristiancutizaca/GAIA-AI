from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'lumen-core'))
from gaia_version import PRODUCT_VERSION, RELEASE, PROTOCOL_VERSION
assert PRODUCT_VERSION=='2.0.0' and RELEASE=='2.0-RESIDENT-DESKTOP-ASSISTANT'
assert PROTOCOL_VERSION=='1.0-RC6'
config=(ROOT/'lumen-core/config.py').read_text(); assert 'PRODUCT_VERSION' in config
launcher=(ROOT/'lumen-pc/gaia_desktop_launcher.py').read_text(); assert 'uvicorn' in launcher and 'health' in launcher and 'SingleInstance' in launcher
startup=(ROOT/'tools/gaia_startup.py').read_text(); assert 'gaia_desktop_launcher.py' in startup
builder=(ROOT/'tools/build_v20_release.py').read_text(); assert 'GAIA-AI-v2.0-RESIDENT-DESKTOP-ASSISTANT' in builder and "release':'1.0-RC6'" not in builder
manifest=json.loads((ROOT/'release_manifest.json').read_text()); assert manifest['version']=='2.0.0' and manifest['release']=='2.0-RESIDENT-DESKTOP-ASSISTANT'
print('V20 RELEASE CONTRACT PASS')
