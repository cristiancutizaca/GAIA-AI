#!/usr/bin/env python3
"""GAIA Operator: durable, bounded PC workflows via the existing ActionHost.

No LLM output is executable. Every action comes from a code-owned template;
non-observational actions need explicit local approval. State survives restarts.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
import time
from pathlib import Path
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lumen-pc'))
from action_host import ActionHost
from preflight import preflight_contract

OBSERVE = frozenset({'system_status', 'system_ram', 'system_cpu', 'system_gpu',
                     'system_disk', 'system_processes', 'system_network',
                     'list_projects', 'show_project', 'git_status', 'file_list'})
PERMITTED_EFFECTS = frozenset({'open_vscode', 'open_project', 'run_tests'})
MAX_STEPS = 10


def now():
    return datetime.now(timezone.utc).isoformat()


def select_template(goal: str, project: str = '') -> list[dict]:
    """Reject unknown requests rather than inventing unverified autonomy."""
    low = goal.casefold().strip()
    def step(name, args=None):
        return {'action': name, 'args': args or {}, 'state': 'PENDING',
                'result': None, 'started_at': None, 'completed_at': None}
    if not low:
        raise ValueError('Falta el objetivo.')
    if any(word in low for word in ('comfyui', 'rocm', 'amdhip', 'pytorch')):
        return [step('system_status'), step('system_gpu'), step('system_processes')]
    if any(word in low for word in ('hardware', 'temperatura', 'vram', 'gpu', 'memoria ram')):
        return [step('system_cpu'), step('system_ram'), step('system_gpu'), step('system_disk')]
    if any(word in low for word in ('red', 'internet', 'conexión', 'conexion', 'network')):
        return [step('system_network'), step('system_processes')]
    if any(word in low for word in ('proyecto', 'código', 'codigo', 'tests', 'pruebas', 'vscode')):
        if not project:
            raise ValueError('Los proyectos requieren --project NOMBRE registrado en projects.json.')
        # Project name never becomes a shell command; ActionEngine enforces trust.
        if any(word in low for word in ('prueba', 'test', 'error', 'corrige', 'repara')):
            return [step('show_project', {'project': project}),
                    step('run_tests', {'path': project})]
        return [step('show_project', {'project': project}), step('open_project', {'project': project})]
    if any(word in low for word in ('equipo', 'sistema', 'diagnóstico', 'diagnostico', 'pc', 'ordenador', 'procesos')):
        return [step('system_status'), step('system_processes'), step('system_network')]
    raise ValueError('Objetivo no soportado por una plantilla segura. No ejecutaré acciones inventadas.')


class Operator:
    def __init__(self, workdir: Path, db: Path | None = None):
        self.workdir = Path(workdir).expanduser().resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.db = Path(db or (Path.home() / '.gaia' / 'operator.sqlite3')).expanduser().resolve()
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.host = ActionHost(project_dir=self.workdir)
        with self._connect() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, goal TEXT NOT NULL, spec TEXT NOT NULL,
              state TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT '')''')

    def _connect(self):
        con = sqlite3.connect(self.db, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA busy_timeout=10000')
        return con

    def _get(self, con, task_id):
        row = con.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row is None:
            raise ValueError('Tarea inexistente.')
        doc = dict(row)
        doc['steps'] = json.loads(doc.pop('spec'))
        doc['approved'] = bool(doc['approved'])
        return doc

    def get(self, task_id):
        with self._connect() as con:
            return self._get(con, task_id)

    def create(self, goal, project=''):
        steps = select_template(goal, project)
        if any(s['action'] in ('run_tests', 'open_project') for s in steps):
            from project_registry import ProjectRegistryError
            try:
                registered = self.host.engine.registry.resolve(project)
            except ProjectRegistryError as exc:
                raise ValueError(str(exc)) from exc
            if not registered.trusted:
                raise ValueError('El proyecto no está marcado trusted.')
            for item in steps:
                if item['action'] == 'run_tests':
                    if 'tests' not in registered.commands:
                        raise ValueError('Falta el comando tests registrado.')
                    item['args']['path'] = str(registered.path)
        if not 1 <= len(steps) <= MAX_STEPS:
            raise ValueError('Demasiados pasos.')
        unknown = [s['action'] for s in steps if s['action'] not in OBSERVE | PERMITTED_EFFECTS]
        if unknown:
            raise ValueError('Acciones fuera del catálogo seguro: ' + ','.join(unknown))
        status = 'WAITING_PERMISSION' if any(s['action'] not in OBSERVE for s in steps) else 'READY'
        task_id = 'job_' + uuid.uuid4().hex
        with self._connect() as con:
            con.execute('INSERT INTO tasks (id,goal,spec,state,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                        (task_id, goal[:1500], json.dumps(steps), status, now(), now()))
        return self.get(task_id)

    def list(self):
        with self._connect() as con:
            return [self._get(con, row['id']) for row in con.execute('SELECT id FROM tasks ORDER BY created_at DESC LIMIT 40')]

    def approve(self, task_id):
        """Approval is local and explicit, never inferred from the goal text."""
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            doc = self._get(con, task_id)
            if doc['state'] not in ('WAITING_PERMISSION', 'PAUSED'):
                raise ValueError('La tarea no está esperando permiso.')
            con.execute("UPDATE tasks SET approved=1,state='READY',updated_at=? WHERE id=?", (now(), task_id))
        return self.get(task_id)

    def cancel(self, task_id):
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            doc = self._get(con, task_id)
            if doc['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED'):
                return doc
            con.execute("UPDATE tasks SET state='CANCELLED',updated_at=? WHERE id=?", (now(), task_id))
        return self.get(task_id)

    def recover(self, task_id):
        """Manually resume only an interrupted read-only observation."""
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            doc = self._get(con, task_id)
            if doc['state'] not in ('RUNNING', 'NEEDS_REVIEW'):
                raise ValueError('La tarea no necesita recuperación.')
            active = [s for s in doc['steps'] if s['state'] == 'RUNNING']
            if len(active) != 1 or active[0]['action'] not in OBSERVE:
                raise ValueError('La tarea pudo producir efectos; requiere revisión externa, sin repetición automática.')
            active[0]['state'] = 'PENDING'
            active[0]['started_at'] = None
            con.execute('UPDATE tasks SET spec=?,state=?,updated_at=? WHERE id=?',
                        (json.dumps(doc['steps']), 'READY', now(), task_id))
        return self.get(task_id)

    def run(self, task_id):
        """Execute one step at a time with journal checkpoints and no blind replay."""
        while True:
            if os.getenv('GAIA_OPERATOR_HALT', '').lower() in ('1', 'true', 'yes'):
                raise RuntimeError('Kill switch GAIA_OPERATOR_HALT activo.')
            with self._connect() as con:
                con.execute('BEGIN IMMEDIATE')
                doc = self._get(con, task_id)
                if doc['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED', 'NEEDS_REVIEW'):
                    return doc
                if doc['state'] == 'RUNNING':
                    raise RuntimeError('La ejecución está en curso o fue interrumpida. Revisión manual obligatoria.')
                steps = doc['steps']
                idx = next((i for i, item in enumerate(steps) if item['state'] != 'SUCCEEDED'), None)
                if idx is None:
                    con.execute("UPDATE tasks SET state='SUCCEEDED',updated_at=? WHERE id=?", (now(), task_id))
                    return {**doc, 'state': 'SUCCEEDED'}
                step = steps[idx]
                action = step['action']
                if action not in OBSERVE | PERMITTED_EFFECTS:
                    raise ValueError('Acción no autorizada.')
                if action not in OBSERVE and os.getenv('GAIA_SAFE_MODE', '').lower() in ('1','true','yes'):
                    raise RuntimeError('GAIA_SAFE_MODE impide acciones con efectos.')
                if action not in OBSERVE and not doc['approved']:
                    con.execute("UPDATE tasks SET state='WAITING_PERMISSION',updated_at=? WHERE id=?", (now(), task_id))
                    return {**doc, 'state': 'WAITING_PERMISSION'}
                if step['state'] == 'RUNNING':
                    con.execute("UPDATE tasks SET state='NEEDS_REVIEW',updated_at=? WHERE id=?", (now(), task_id))
                    return {**doc, 'state': 'NEEDS_REVIEW'}
                step['state'] = 'RUNNING'
                step['started_at'] = now()
                con.execute('UPDATE tasks SET spec=?,state=?,updated_at=? WHERE id=?',
                            (json.dumps(steps), 'RUNNING', now(), task_id))
            contract = {'kind': 'action', 'action_id': f'{task_id}_{idx}',
                        'session_id': 'operator-local', 'request_id': task_id,
                        'confirmation_required': action not in OBSERVE,
                        'action': {'name': action, 'args': step['args'], 'risk_level': self.host.engine.SAFE_ACTIONS[action][0]}}
            try:
                pf = preflight_contract(self.host.engine, contract)
                if pf['status'] != 'READY':
                    result = {'success': False, 'status': pf['status'], 'message': pf['message'],
                              'execution_verified': False, 'execution_attempted': False}
                else:
                    result = self.host.execute(contract, confirmed=True).as_dict()
            except Exception as exc:
                result = {'success': False, 'status': 'FAILED', 'message': f'{type(exc).__name__}: {exc}',
                          'execution_verified': False}
            # Do not save raw tool payloads, tokens, full paths, or private file contents.
            safe_result = {key: result.get(key) for key in ('success', 'status', 'execution_verified',
                                                             'execution_attempted', 'audit_digest')}
            safe_result['message'] = str(result.get('message') or '')[:450]
            verified = bool(result.get('success') and result.get('execution_verified'))
            with self._connect() as con:
                con.execute('BEGIN IMMEDIATE')
                fresh = self._get(con, task_id)
                if fresh['state'] == 'CANCELLED':
                    return fresh
                steps = fresh['steps']
                steps[idx]['state'] = 'SUCCEEDED' if verified else 'FAILED'
                steps[idx]['result'] = safe_result
                steps[idx]['completed_at'] = now()
                state = ('READY' if verified else 'FAILED')
                con.execute('UPDATE tasks SET spec=?,state=?,error=?,updated_at=? WHERE id=?',
                            (json.dumps(steps), state, '' if verified else safe_result['message'], now(), task_id))
            if not verified:
                return self.get(task_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description='GAIA Operator: tareas locales verificadas')
    parser.add_argument('command', choices=['plan', 'run', 'approve', 'cancel', 'show', 'list', 'recover'])
    parser.add_argument('value', nargs='?', default='')
    parser.add_argument('--project', default='')
    parser.add_argument('--workdir', default=str(ROOT))
    parser.add_argument('--db', default='')
    args = parser.parse_args(argv)
    try:
        op = Operator(Path(args.workdir), Path(args.db) if args.db else None)
        if args.command == 'plan': out = op.create(args.value, args.project)
        elif args.command == 'run': out = op.run(args.value)
        elif args.command == 'approve': out = op.approve(args.value)
        elif args.command == 'cancel': out = op.cancel(args.value)
        elif args.command == 'recover': out = op.recover(args.value)
        elif args.command == 'show': out = op.get(args.value)
        else: out = op.list()
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({'status': 'DENIED', 'error': str(exc)}, ensure_ascii=False))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
