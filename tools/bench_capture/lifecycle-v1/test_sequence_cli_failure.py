"""Actual sequence main/first real child, temporary source-closure binding only."""
import hashlib,json,os,sys
from pathlib import Path
import pytest
from test_outer_lifecycle import load,put,j

def test_actual_sequence_main_consumes_and_stops_after_first_real_child(tmp_path,monkeypatch):
    m=load('sequence-once.py');stage=tmp_path/'stage';entry=tmp_path/'entry';stage.mkdir(mode=0o700);entry.mkdir(mode=0o700);run=entry/'run';run.mkdir(mode=0o700)
    for key,value in [('STAGE',stage),('ENTRY',entry),('RUN',run)]:monkeypatch.setattr(m,key,value)
    for name in ('install-run','boot-run','returned-backup-run','returned-restore-run'):(stage/name).mkdir(mode=0o700)
    # These deliberately harmless exact-bound source files are not hardware wrappers.
    child=entry/'orchestrate-entry-backup-v3.py';child.write_text("print('first-child-stopped',flush=True)\nraise SystemExit(23)\n")
    for name in ('wire.py','root-launch-acceptance.json','partial-recovery-plan.json'):(entry/name).write_text('{}\n')
    monkeypatch.setattr(m,'WIRE_PATH',entry/'wire.py')
    c=dict(entry_root=str(entry),unchanged_stage=str(stage),stage_files={},entry_files={},entry_derivatives={child.name:m.digest(child.read_bytes())},inputs={});put(entry/'source-closure.json',c)
    for key,file in [('WIRE_SHA','wire.py'),('CLOSURE_SHA','source-closure.json'),('ROOT_ACCEPTANCE_SHA','root-launch-acceptance.json'),('RECOVERY_PLAN_SHA','partial-recovery-plan.json')]:monkeypatch.setattr(m,key,m.digest((entry/file).read_bytes()))
    monkeypatch.setattr(sys,'argv',[str(m.__file__),'--reviewed-self-sha256',m.digest(Path(m.__file__).read_bytes())])
    # No command/factory/Prepared/registry substitution; actual pipeline calls its first command.
    with pytest.raises(RuntimeError,match='entry-backup stopped; no retry'):m.main()
    assert j(entry/'.automatic-trace-chain.consumed')['retry'] is False
    stopped=j(run/'chain-stopped.json');assert stopped['capture_cleanup_not_assumed'] and not stopped['automatic_recovery']
    intents=list(run.glob('*.intent.json'));assert [v.name for v in intents]==['00-entry-backup.intent.json']
    assert j(run/'00-entry-backup.exit.json')['exit_status']==23
    assert (run/'00-entry-backup.stdout').read_text()=='first-child-stopped\n'
    assert not (run/'chain-completed.json').exists()
    with pytest.raises(ValueError,match='run must be empty'):m.main()
    assert len(list(run.glob('*.intent.json')))==1 and len(list(run.glob('*.exit.json')))==1
