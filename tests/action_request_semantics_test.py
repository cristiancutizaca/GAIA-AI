from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'lumen-core'
sys.path.insert(0, str(CORE))

with tempfile.TemporaryDirectory(prefix='gaia_action_request_semantics_') as tmp:
    os.environ.update({
        'LUMEN_DATA_DIR': tmp,
        'GAIA_MEMORY_DB': str(Path(tmp) / 'memory' / 'lumen_memory.db'),
        'LUMEN_LLM_BACKEND': 'mock',
        'LUMEN_SECRET': 'action-request-semantics-secret',
        'LUMEN_BACKUP_ENABLED': 'false',
        'LUMEN_PROACTIVE_ENABLED': 'false',
    })
    from fastapi.testclient import TestClient
    import routes.api as api_routes
    from main import app

    action_requests = (
        'abre Photoshop',
        '¿puedes abrir Photoshop?',
        'me abres Photoshop',
        'quiero que abras Photoshop',
        'por favor abre Photoshop',
        'necesito que abras Photoshop',
        'podrías abrir Photoshop',
        'hazme el favor de abrir Chrome',
        'serías tan amable de abrir Discord',
        'quiero Spotify abierto',
        'quiero que inicies Blender',
        'me puedes cerrar Steam',
        'puedes eliminar este archivo',
        '¿PUEDES ABRIR PHOTOSHOP?',
        'gaia puedes abrir photoshop?',
        'GAIA, ¿me abres Photoshop?',
        'por favor, abre Photoshop.',
        'Te encargo que abras Photoshop.',
        'Cuando puedas, abre Photoshop.',
        'Si tienes un momento, abre Photoshop.',
        'En cuanto puedas, abre Photoshop.',
        'No te olvides de abrir Photoshop.',
    )
    for message in action_requests:
        assert api_routes._is_action_request(message), message

    from action_intent import detect_action
    allowlisted_natural = {
        '¿puedes abrir Spotify?': 'open_spotify',
        'me abres la calculadora': 'open_calculator',
        'quiero que abras el bloc de notas': 'open_notepad',
        'quiero Spotify abierto': 'open_spotify',
        'por favor, abre VS Code.': 'open_vscode',
        'cuando puedas, abre la calculadora': 'open_calculator',
        'no te olvides de abrir Spotify': 'open_spotify',
    }
    for message, expected in allowlisted_natural.items():
        intent = detect_action(message)
        assert intent is not None and intent.name == expected, (message, intent)

    capability_questions = (
        '¿Puedes abrir Spotify actualmente?',
        '¿Tienes capacidad para abrir Spotify?',
        '¿Qué aplicaciones puedes abrir?',
        '¿Cómo funciona tu acción para abrir Spotify?',
        '¿Por qué no puedes abrir Photoshop?',
        '¿Qué pasaría si abrieras Spotify?',
    )
    for message in capability_questions:
        assert not api_routes._is_action_request(message), message

    non_action_questions = (
        '¿Es seguro abrir Photoshop?',
        '¿Conviene abrir Photoshop?',
        '¿Para qué abrir Photoshop?',
        '¿Qué pasa si abres Photoshop?',
        '¿Qué ocurre si abres Photoshop?',
        '¿Cómo abro Photoshop?',
    )
    for message in non_action_questions:
        assert not api_routes._is_action_request(message), message

    negations = ('No abras Spotify.', 'No cierres VS Code.', 'No lo hagas.')
    for message in negations:
        assert not api_routes._is_action_request(message), message

    unverified_claims = (
        'Listo, ya abrí Photoshop.',
        'He creado prueba.txt.',
        'También activé el Wi-Fi.',
    )
    for claim in unverified_claims:
        grounded = api_routes._ground_conversation_response(claim, user_message='hola', request_state='CONVERSATION')
        assert grounded == api_routes._UNAVAILABLE_ACTION_FALLBACK, (claim, grounded)

    async def fake_classifier(_message: str, _structured=None):
        return None

    original = api_routes._allowed_intent_with_llm
    api_routes._allowed_intent_with_llm = fake_classifier
    try:
        with TestClient(app) as client:
            for message in ('¿puedes abrir Photoshop?', 'me abres Chrome', 'quiero que abras Discord', 'necesito que abras Blender', 'por favor abre Steam'):
                response = client.post('/api/chat', headers={'Authorization': 'Bearer action-request-semantics-secret'}, json={'message': message, 'device': 'semantics'})
                assert response.status_code == 200, response.text
                payload = response.json()
                assert payload['request_state'] == 'ACTION_REQUEST', payload
                assert payload['response'] == api_routes._UNAVAILABLE_ACTION_FALLBACK
                assert payload.get('action_id') is None
    finally:
        api_routes._allowed_intent_with_llm = original

print('ACTION REQUEST SEMANTICS TEST OK: natural requests, capability questions, unsupported actions and no free-chat fallback.')
