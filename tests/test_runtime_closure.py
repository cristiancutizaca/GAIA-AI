from __future__ import annotations
import json, os, sys, threading, time, tomllib
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'lumen-core'),str(ROOT/'lumen-pc'),str(ROOT/'tools')]

def test_full_profile_is_actually_full():
    data=tomllib.loads((ROOT/'gaia_dependencies.toml').read_text(encoding='utf-8'))
    reqs=set(data['profiles']['full']['requirements'])
    assert {'requirements-desktop.txt','requirements-voice.txt'} <= reqs
    assert 'requirements-browser.txt' not in reqs
    assert 'requirements-memory.txt' not in reqs and 'requirements-coding.txt' not in reqs
    assert set(data['profiles']['full']['sidecars']) == {'browser','memory','coding'}
    reqs2=set(data['profiles']['full_computer']['requirements']); assert 'requirements-computer.txt' in reqs2
    from gaia_dependencies import expand_profile
    assert 'requirements-desktop.txt' in expand_profile('full')
    assert 'requirements-computer.txt' in expand_profile('full-computer')
    installer=(ROOT/'install-gaia.ps1').read_text(encoding='utf-8')
    assert 'gaia_dependencies.py' in installer and '.venv-browser' in installer and "playwright','install','chromium" in installer

def test_computer_dependencies_are_declared_honestly():
    text=(ROOT/'requirements-computer.txt').read_text(encoding='utf-8').lower()
    assert 'pyautogui' in text and 'pywinauto' in text
    from gaia_platform.real_backends import PyAutoGUIComputerUseBackend, WindowsUIAutomationBackend, UITARSComputerUseBackend
    assert UITARSComputerUseBackend is PyAutoGUIComputerUseBackend
    assert hasattr(PyAutoGUIComputerUseBackend,'double_click') and hasattr(PyAutoGUIComputerUseBackend,'drag') and hasattr(WindowsUIAutomationBackend,'invoke')

def test_hotkey_parser_and_dispatch_are_behavioral():
    import desktop_shell
    events=[]
    h=desktop_shell.GlobalHotkey(lambda:events.append('down'),lambda:events.append('up'),'Ctrl+Space')
    assert h.modifiers & 0x2 and h.vk==0x20
    assert h.dispatch('down') and h.dispatch('up')
    assert events==['down','up']
    q=desktop_shell.GlobalHotkey(lambda:None,lambda:None,'Win+Shift+G')
    assert q.modifiers & 0x8 and q.modifiers & 0x4 and q.vk==ord('G')

def test_audio_capture_finalizes_wav_and_calls_callback(monkeypatch,tmp_path):
    import desktop_shell
    if desktop_shell.np is None: pytest.skip('numpy unavailable')
    called=[]; done=threading.Event()
    class Stream:
        def stop(self): pass
        def close(self): pass
    cap=desktop_shell.AudioCapture(lambda p:(called.append(Path(p)),done.set()))
    cap.recording=True; cap._stream=Stream(); cap._frames=[desktop_shell.np.ones((320,1),dtype='int16')]
    result=cap.stop(); assert result['status']=='FINALIZED'; assert done.wait(2); assert called and called[0].is_file() and called[0].suffix=='.wav'; called[0].unlink(missing_ok=True)

def test_no_fake_pipecat_placeholder_pipeline():
    text=(ROOT/'lumen-core/gaia_platform/real_backends.py').read_text(encoding='utf-8')
    assert 'class AudioInputStage(FrameProcessor): pass' not in text
    assert "empty placeholder pipeline is forbidden" in text

def test_local_voice_prefers_faster_whisper_and_piper():
    text=(ROOT/'lumen-core/voice.py').read_text(encoding='utf-8')
    assert 'from faster_whisper import WhisperModel' in text
    assert 'LUMEN_STT_ENGINE' in text and 'faster-whisper' in text
    assert 'piper' in text and 'python -m piper' not in text  # runtime invokes sys.executable -m piper, not a fragile PATH binary
    assert "es_MX-claude-high" in text

def test_wakeword_is_truthful_not_jarvis_fallback():
    wake=(ROOT/'lumen-pc/wake_word.py').read_text(encoding='utf-8').lower()
    assert 'custom_model_missing' in wake
    assert not ('hey jarvis detector as an acoustic gate' in wake)
    prep=(ROOT/'assets/wakeword/gaia_training.yml').read_text(encoding='utf-8').lower()
    assert 'target_phrase' in prep and '"gaia"' in prep

def test_restart_protocol_is_supervised():
    shell=(ROOT/'lumen-pc/desktop_shell.py').read_text(encoding='utf-8'); launcher=(ROOT/'lumen-pc/gaia_desktop_launcher.py').read_text(encoding='utf-8')
    assert 'RESTART_EXIT_CODE = 75' in shell and 'RESTART_EXIT_CODE=75' in launcher
    assert "rc!=RESTART_EXIT_CODE" in launcher and 'stop_process(core_proc); core_proc=start_core()' in launcher

def test_doctor_and_dependency_status_execute():
    from gaia_dependencies import load, component_status
    assert load()['schema']==2; rows=component_status(); assert any(r['name']=='desktop' for r in rows)
    import gaia_doctor_v2
    report=gaia_doctor_v2.run(); assert report['read_only'] is True and report['doctor'].startswith('2.1')

def test_browser_executable_discovery_is_cross_platform(monkeypatch,tmp_path):
    from gaia_platform import browser_real
    fake=tmp_path/'browser.exe'; fake.write_bytes(b'fake')
    monkeypatch.setenv('GAIA_BROWSER_EXECUTABLE',str(fake))
    assert browser_real._discover_browser_executable()==str(fake.resolve())
    source=(ROOT/'lumen-core/gaia_platform/browser_real.py').read_text(encoding='utf-8')
    assert 'executable_path="/usr/bin/chromium"' not in source


def test_physical_validator_tracks_current_release():
    import physical_validation
    report=physical_validation.new_report()
    assert report['product_version']=='2.0.0'
    assert report['release']=='2.0-WINDOWS-COMPLETE-RC3'
    ids={row['id'] for row in report['checks']}
    assert {'tray','orb','quick_hotkey','ptt_hotkey','gaia_wake','barge_in','restart','startup_login'} <= ids


def test_coding_profile_contains_only_connected_worker_stack():
    text=(ROOT/'requirements-coding.txt').read_text(encoding='utf-8').lower()
    assert 'openhands-sdk' in text
    assert 'smolagents' not in text
