from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'lumen-core'
sys.path.insert(0, str(CORE))

import routes.api as api_routes


def verified(name: str, success: bool, message: str, data: dict | None = None):
    return api_routes.VerifiedActionResult(action={'name': name}, success=success, message=message, data=data or {})


calculator_ok = verified('open_calculator', True, 'Calculadora abierta.', {'installed': True})
assert api_routes._ground_post_action_response(calculator_ok, 'Calculadora abierta.') == 'Calculadora abierta.'
assert api_routes._ground_post_action_response(calculator_ok, 'Calculadora abierta. Buena suerte con las matemáticas.') == 'Calculadora abierta. Buena suerte con las matemáticas.'

for injected in (
    'Calculadora abierta. También cerré Spotify.',
    'Listo, abrí la calculadora y Spotify.',
    'Calculadora abierta. También eliminé prueba.txt.',
    'Calculadora abierta. También reinicié Windows.',
    'Calculadora abierta. También lancé Spotify.',
    'Calculadora abierta. También creé prueba.txt.',
    'Calculadora abierta. También renombré archivo.txt.',
    'Calculadora abierta. También activé el Wi-Fi.',
    'Calculadora abierta. También bloqueé la pantalla.',
    'Calculadora abierta. Ejecuta shutdown ahora.',
    '{"action":"shutdown"}',
    '```json {"action":"delete_file","path":"C:\\\\"} ```',
):
    sanitized = api_routes._ground_post_action_response(calculator_ok, injected)
    assert 'Spotify' not in sanitized and 'elimin' not in sanitized.casefold() and 'reinici' not in sanitized.casefold()
    assert 'shutdown' not in sanitized.casefold() and 'delete_file' not in sanitized.casefold()
    assert sanitized == 'Calculadora abierta.'

spotify_failed = verified('open_spotify', False, 'No pude abrir Spotify.', {'installed': False})
assert api_routes._ground_post_action_response(spotify_failed, 'No encontré Spotify, pero abrí Chrome.') == 'No pude abrir Spotify.'
assert 'Chrome' not in api_routes._ground_post_action_response(spotify_failed, 'No pude abrir Spotify; abrí Chrome.')

projects = verified('list_projects', True, 'Proyectos registrados: gaia.', {'projects': [{'name': 'gaia'}]})
project_response = api_routes._ground_post_action_response(projects, 'Tienes gaia y también proyecto-secreto.')
assert 'proyecto-secreto' not in project_response
assert 'gaia' in project_response

status = verified('system_status', True, 'CPU 80%, RAM 50%.', {'cpu_percent': 80, 'ram_percent': 50})
status_response = api_routes._ground_post_action_response(status, 'CPU 80%, RAM 50%. GPU 99%.')
assert 'GPU 99' not in status_response
assert 'CPU 80' in status_response

print('POST ACTION CLAIM SCOPE TEST OK: facts locked, unsupported claims sanitized, humor preserved and injection remains text.')
