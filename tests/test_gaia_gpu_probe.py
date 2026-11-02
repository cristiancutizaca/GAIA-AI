"""Read-only GPU probe never overclaims AMD metrics/VRAM."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lumen-pc'))
import gpu_probe


def test_linux_reports_unavailable(monkeypatch):
    monkeypatch.setattr(gpu_probe.platform,'system',lambda:'Linux')
    assert gpu_probe.windows_gpu_inventory()['gpu_available'] is False


def test_windows_cim_reports_detected_name_not_false_vram(monkeypatch):
    monkeypatch.setattr(gpu_probe.platform,'system',lambda:'Windows')
    monkeypatch.setattr(gpu_probe.shutil,'which',lambda _: 'powershell.exe')
    payload={'Name':'AMD Radeon RX 9060 XT','AdapterRAM':4294967295,'DriverVersion':'32.0'}
    monkeypatch.setattr(gpu_probe.subprocess,'run',lambda *a,**k: SimpleNamespace(returncode=0,stdout=json.dumps(payload)))
    result=gpu_probe.windows_gpu_inventory()
    assert result['gpu_available'] is True
    assert result['gpu_name'] == 'AMD Radeon RX 9060 XT'
    assert result['gpu_metrics_available'] is False
    assert 'gpu_memory_total_mb' not in result
