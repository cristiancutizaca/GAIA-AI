"""Read-only Windows GPU identity fallback when nvidia-smi is not present.

Win32_VideoController.AdapterRAM can overflow/truncate above 4GiB: never
present it as confirmed VRAM. AMD performance/sensors require vendor backends.
"""
from __future__ import annotations
import json
import platform
import shutil
import subprocess


def windows_gpu_inventory() -> dict:
    if platform.system() != 'Windows':
        return {'gpu_available': False, 'gpu_probe': 'windows-only'}
    exe = shutil.which('powershell.exe') or shutil.which('powershell') or shutil.which('pwsh')
    if not exe:
        return {'gpu_available': False, 'gpu_probe': 'powershell-unavailable'}
    script = ('Get-CimInstance Win32_VideoController -ErrorAction Stop | '
              'Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID | ConvertTo-Json -Compress -Depth 3')
    try:
        proc = subprocess.run([exe, '-NoProfile', '-NonInteractive', '-Command', script],
                              capture_output=True, text=True, timeout=12, shell=False)
        if proc.returncode != 0 or not proc.stdout.strip():
            return {'gpu_available': False, 'gpu_probe': 'cim-unavailable'}
        raw = json.loads(proc.stdout.strip())
        items = raw if isinstance(raw, list) else [raw]
        cards = []
        for row in items:
            if not isinstance(row, dict):
                continue
            name = str(row.get('Name') or '').strip()
            if not name:
                continue
            vram = row.get('AdapterRAM')
            cards.append({'name': name, 'driver': str(row.get('DriverVersion') or ''),
                          'adapter_ram_reported_mb': round(int(vram)/1048576) if str(vram).isdigit() else None})
        if not cards:
            return {'gpu_available': False, 'gpu_probe': 'no-video-adapters'}
        preferred = next((v for v in cards if 'radeon' in v['name'].casefold() or 'nvidia' in v['name'].casefold()), cards[0])
        return {'gpu_available': True, 'gpu_name': preferred['name'],
                'gpu_probe': 'windows-cim-inventory', 'gpu_adapters': cards,
                'gpu_metrics_available': False,
                'gpu_metrics_note': 'Uso, temperatura y VRAM real no disponibles: AdapterRAM puede truncarse en >4 GiB.'}
    except (subprocess.TimeoutExpired, OSError, ValueError, TypeError, json.JSONDecodeError):
        return {'gpu_available': False, 'gpu_probe': 'cim-failed'}
