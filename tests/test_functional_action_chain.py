"""Proof that Core-issued action contracts execute only in local read-only sandbox."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lumen-pc'))
from action_host import ActionHost

def test_action_host_end_to_end_read_only_file_listing(tmp_path):
    (tmp_path/'hello.txt').write_text('hello',encoding='utf-8')
    action={
        'kind':'action','action_id':'local-audit-001','session_id':'test','request_id':'r1',
        'confirmation_required':False,
        'action': {'type':'action','name':'file_list','args':{'path':str(tmp_path)},'risk_level':0},
    }
    result=ActionHost(project_dir=tmp_path).execute(action, confirmed=True)
    assert result.success and result.execution_verified and result.status == 'SUCCESS', result.as_dict()
    assert result.observation_completed and not result.side_effect_performed
    assert (tmp_path/'.gaia_action_audit.jsonl').exists()
