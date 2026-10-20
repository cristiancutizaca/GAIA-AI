#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, platform, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NAME="GAIA Desktop Assistant"
def command():
    interpreter = os.environ.get("GAIA_PYTHON", sys.executable)
    if platform.system()=="Windows" and interpreter.lower().endswith("python.exe"):
        candidate = str(Path(interpreter).with_name("pythonw.exe"))
        if Path(candidate).exists(): interpreter = candidate
    return f'"{interpreter}" "{ROOT / "lumen-pc" / "gaia_desktop_launcher.py"}"'
def enable():
    if platform.system()=="Windows":
        import winreg
        key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Run",0,winreg.KEY_SET_VALUE); winreg.SetValueEx(key,"GAIA",0,winreg.REG_SZ,command()); winreg.CloseKey(key); return {"status":"ENABLED","scope":"HKCU","command":command()}
    path=Path.home()/".config/autostart/gaia.desktop"; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(f"[Desktop Entry]\nType=Application\nName={NAME}\nExec={command()}\nHidden=false\nX-GNOME-Autostart-enabled=true\n",encoding="utf-8"); return {"status":"ENABLED","path":str(path)}
def disable():
    if platform.system()=="Windows":
        import winreg
        try:
            key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Run",0,winreg.KEY_SET_VALUE); winreg.DeleteValue(key,"GAIA"); winreg.CloseKey(key); return {"status":"DISABLED"}
        except FileNotFoundError:return {"status":"DISABLED"}
    path=Path.home()/".config/autostart/gaia.desktop"; path.unlink(missing_ok=True); return {"status":"DISABLED","path":str(path)}
def status():
    if platform.system()=="Windows":
        import winreg
        try:
            key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Run"); value,_=winreg.QueryValueEx(key,"GAIA"); return {"status":"ENABLED","command":value}
        except Exception:return {"status":"DISABLED"}
    path=Path.home()/".config/autostart/gaia.desktop"; return {"status":"ENABLED" if path.exists() else "DISABLED","path":str(path)}
def main():
    p=argparse.ArgumentParser(); p.add_argument("action",choices=["enable","disable","status","test"]); a=p.parse_args()
    if a.action=="enable": print(enable())
    elif a.action=="disable": print(disable())
    elif a.action=="status": print(status())
    else: raise SystemExit(subprocess.run([os.environ.get("GAIA_PYTHON",sys.executable), str(ROOT/"lumen-pc"/"gaia_desktop_launcher.py"), "--once"], check=False).returncode)
if __name__=='__main__': main()
