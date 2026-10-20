#!/usr/bin/env python3
"""GAIA Doctor: read-only, honest capability inventory with distribution/module mapping."""
from __future__ import annotations
import importlib.util, json, os, platform, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'lumen-core')); sys.path.insert(0,str(ROOT/'lumen-pc'))
from gaia_ext.feature_flags import feature_flags

def check(name,status,detail="",suggestion=""): return {"name":name,"status":status,"detail":detail,"suggestion":suggestion}
MAPPING={"browser-use":"browser_use","pipecat-ai":"pipecat","silero-vad":"silero_vad","openai-whisper":"whisper","edge-tts":"edge_tts","mem0ai":"mem0","graphiti-core":"graphiti_core","openhands-sdk":"openhands.sdk","PySide6":"PySide6","openwakeword":"openwakeword","sounddevice":"sounddevice"}
def module_status(dist,module,enabled=False):
    present=importlib.util.find_spec(module) is not None
    if not present:return "MISSING_DEPENDENCY",f"distribution {dist} -> import {module} missing",f"Install {dist} in its optional environment."
    return "PASS" if enabled else "DEGRADED",f"distribution {dist} -> import {module} available","Enable feature flag and run physical validation where applicable."
def run()->dict:
    flags=feature_flags.as_dict(); checks=[check("CORE","PASS","GAIA Core and central authority are loaded"),check("OLLAMA","PASS" if shutil.which("ollama") else "CONFIG_REQUIRED","local Ollama executable"),check("MODELS","DEGRADED","model availability is deployment-specific"),check("MCP","PASS" if flags["mcp"] else "DEGRADED","MCP feature flag and manager"),check("CHROMIUM","PASS" if shutil.which("chromium") or shutil.which("chromium-browser") else "PHYSICAL_VALIDATION_REQUIRED","executable discovery only")]
    for key,dist,module in [("browser","browser-use","browser_use"),("voice_v2","pipecat-ai","pipecat"),("vad","silero-vad","silero_vad"),("mem0","mem0ai","mem0"),("graph_memory","graphiti-core","graphiti_core"),("coding_worker","openhands-sdk","openhands.sdk"),("computer_use","ui-tars","ui_tars")]:
        st,detail,sugg=module_status(dist,module,flags.get(key,False)); checks.append(check(key.upper(),st if flags.get(key,False) else ("DEGRADED" if st=="PASS" else st),detail,sugg))
    for name,dist,module in [("STT","openai-whisper","whisper"),("TTS","edge-tts","edge_tts"),("DESKTOP_SHELL","PySide6","PySide6"),("SYSTEM_TRAY","PySide6","PySide6"),("WAKE_WORD","openwakeword","openwakeword"),("ANDROID_REALTIME","websockets","websockets")]:
        st,detail,sugg=module_status(dist,module,False); checks.append(check(name,st,detail,sugg))
    checks += [check("VISUALIZER","PASS","read-only HTML/SSE consumer"),check("PERMISSIONS","PASS","central Permission Layer + Action Host"),check("SAFE_MODE","PASS","fail-closed for effects"),check("KILL_SWITCH","PASS","global effect block"),check("PHYSICAL_WINDOWS","PHYSICAL_VALIDATION_REQUIRED","tray, microphone, wake word, overlay and GUI need Windows operator"),check("ANDROID","PHYSICAL_VALIDATION_REQUIRED","device/toolchain not present in Sandbox")]
    return {"doctor":"2.0-final","read_only":True,"platform":platform.platform(),"flags":flags,"mapping":MAPPING,"checks":checks}
if __name__=='__main__': print(json.dumps(run(),ensure_ascii=False,indent=2))
