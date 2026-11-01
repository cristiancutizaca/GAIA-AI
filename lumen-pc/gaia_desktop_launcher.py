"""Resident GAIA supervisor: Core first, health gate, then Desktop Shell."""
from __future__ import annotations
import argparse, ctypes, os, subprocess, sys, time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]; CORE=ROOT/'lumen-core'; SHELL=ROOT/'lumen-pc'/'desktop_shell.py'
URL=os.getenv('LUMEN_CORE_URL','http://127.0.0.1:'+os.getenv('LUMEN_PORT','8090')).rstrip('/')
LOCK=Path(os.getenv('GAIA_LAUNCHER_LOCK',str(Path.home()/'.gaia'/'launcher.lock'))).expanduser(); RESTART_EXIT_CODE=75

class SingleInstance:
    def __enter__(self):
        if os.name=='nt':
            self.kernel32=ctypes.windll.kernel32; self.mutex=self.kernel32.CreateMutexW(None,False,'Local\\GAIA_Resident_Desktop_Assistant')
            if not self.mutex: raise OSError('CreateMutexW failed')
            if int(self.kernel32.GetLastError())==183:
                self.kernel32.CloseHandle(self.mutex); raise SystemExit('GAIA launcher already running')
            return self
        LOCK.parent.mkdir(parents=True,exist_ok=True); self.handle=LOCK.open('a+'); self.handle.seek(0)
        if self.handle.read(1)=='': self.handle.seek(0); self.handle.write('0'); self.handle.flush()
        self.handle.seek(0)
        try:
            import fcntl; fcntl.flock(self.handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except (OSError,BlockingIOError): raise SystemExit('GAIA launcher already running')
        self.handle.seek(0); self.handle.truncate(); self.handle.write(str(os.getpid())); self.handle.flush(); return self
    def __exit__(self,*args):
        try:
            if os.name=='nt': self.kernel32.CloseHandle(self.mutex)
            else:
                import fcntl; fcntl.flock(self.handle.fileno(),fcntl.LOCK_UN); self.handle.close(); LOCK.unlink(missing_ok=True)
        except OSError: pass

def healthy()->bool:
    try:
        r=httpx.get(URL+'/api/health',timeout=1.5); return r.status_code==200 and str(r.json().get('status','')).lower() in {'online','ok','healthy'}
    except Exception:return False

def start_core():
    return subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host',os.getenv('LUMEN_HOST','127.0.0.1'),'--port',os.getenv('LUMEN_PORT','8090')],cwd=CORE,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=(os.name!='nt'))

def stop_process(proc,timeout=8):
    if not proc or proc.poll() is not None:return
    proc.terminate()
    try: proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=3)

def wait_healthy(wait):
    deadline=time.monotonic()+wait
    while time.monotonic()<deadline:
        if healthy(): return True
        time.sleep(.25)
    return healthy()

def launch(*,shell=True,wait=30,once=False)->int:
    with SingleInstance():
        core_proc=None
        if not healthy(): core_proc=start_core()
        if not wait_healthy(wait): stop_process(core_proc); raise RuntimeError('GAIA Core failed health readiness')
        if once:
            stop_process(core_proc); return 0
        if not shell:return 0
        while True:
            shell_proc=subprocess.Popen([sys.executable,str(SHELL)],cwd=ROOT,env={**os.environ,'GAIA_LAUNCHER_ACTIVE':'1','PYTHONDONTWRITEBYTECODE':'1'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=(os.name!='nt'))
            rc=shell_proc.wait()
            if rc!=RESTART_EXIT_CODE:
                stop_process(core_proc); return rc
            # A normal launcher owns the Core. Restart it together with Desktop.
            if core_proc is not None:
                stop_process(core_proc); core_proc=start_core()
                if not wait_healthy(wait): stop_process(core_proc); raise RuntimeError('GAIA Core failed restart readiness')
            elif not healthy():
                core_proc=start_core()
                if not wait_healthy(wait): stop_process(core_proc); raise RuntimeError('GAIA Core failed restart readiness')

def main():
    p=argparse.ArgumentParser(); p.add_argument('--once',action='store_true'); p.add_argument('--no-shell',action='store_true'); p.add_argument('--wait',type=int,default=30); a=p.parse_args(); return launch(shell=not a.no_shell,wait=a.wait,once=a.once)
if __name__=='__main__': raise SystemExit(main())
