"""Resident GAIA supervisor: Core first, health gate, then Desktop Shell."""
from __future__ import annotations
import argparse, atexit, os, signal, subprocess, sys, time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'lumen-core'; SHELL=ROOT/'lumen-pc'/'desktop_shell.py'
URL=os.getenv('LUMEN_CORE_URL', 'http://127.0.0.1:'+os.getenv('LUMEN_PORT','8090')).rstrip('/')
LOCK=Path(os.getenv('GAIA_LAUNCHER_LOCK', str(Path.home()/'.gaia'/'launcher.lock'))).expanduser()
class SingleInstance:
    def __enter__(self):
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        self.handle=LOCK.open('a+')
        try:
            if os.name=='nt':
                import msvcrt; msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl; fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
        except (OSError, BlockingIOError): raise SystemExit('GAIA launcher already running')
        self.handle.seek(0); self.handle.truncate(); self.handle.write(str(os.getpid())); self.handle.flush(); return self
    def __exit__(self,*args):
        try:
            if os.name=='nt':
                import msvcrt; self.handle.seek(0); msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl; fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close(); LOCK.unlink(missing_ok=True)
        except OSError: pass

def healthy() -> bool:
    try:
        r=httpx.get(URL+'/api/health',timeout=1.5); return r.status_code==200 and r.json().get('status') in {'online','ok','healthy'}
    except Exception: return False

def launch(*, shell=True, wait=30, once=False) -> int:
    with SingleInstance():
        core_proc=None; shell_proc=None
        if not healthy():
            core_proc=subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host',os.getenv('LUMEN_HOST','127.0.0.1'),'--port',os.getenv('LUMEN_PORT','8090')],cwd=CORE, env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+wait
        while not healthy() and time.monotonic()<deadline: time.sleep(.25)
        if not healthy():
            if core_proc: core_proc.terminate()
            raise RuntimeError('GAIA Core failed health readiness')
        if shell and not once:
            shell_proc=subprocess.Popen([sys.executable,str(SHELL)],cwd=ROOT,env={**os.environ,'GAIA_LAUNCHER_ACTIVE':'1','PYTHONDONTWRITEBYTECODE':'1'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0), close_fds=(os.name!='nt'))
            try: return shell_proc.wait()
            finally:
                if shell_proc.poll() is None: shell_proc.terminate()
                if core_proc and core_proc.poll() is None: core_proc.terminate()
        if core_proc and once:
            if core_proc.poll() is None: core_proc.terminate()
            return 0
        return 0

def main():
    p=argparse.ArgumentParser(); p.add_argument('--once',action='store_true'); p.add_argument('--no-shell',action='store_true'); p.add_argument('--wait',type=int,default=30); a=p.parse_args(); return launch(shell=not a.no_shell,wait=a.wait,once=a.once)
if __name__=='__main__': raise SystemExit(main())
