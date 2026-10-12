"""Replay retained physical V7/V2 evidence in disposable, device-free containers."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

CASES = ('valid', 'unregistered', 'marker', 'source', 'reply', 'result',
         'native-log', 'outer-log', 'capture-exit', 'wire', 'wrapper', 'witness',
         'plan', 'later-loader', 'pending-result', 'ambiguous-cleanup')


@pytest.mark.parametrize('case', CASES)
def test_completed_actual_stop_trace(monkeypatch, tmp_path, case):
    if os.environ.get('LUNAR_PREPARATION_STOP_DISPOSABLE') != '1':
        pytest.skip('Requires retained private V7/V2 evidence in disposable container')
    assert Path(__file__).resolve().parents[1] == Path('/tmp/packet-work')
    assert sys.platform == 'linux'
    import fm1_prepare_stop_trace_return_admission as admission
    import fcntl
    monkeypatch.setattr(fcntl, 'ioctl', lambda *a, **k: pytest.fail('Offline admission issued ioctl'))
    run = Path('/home/claude/fm1-stop-trace-capture-v2-20261012/run')
    campaign = json.loads((run / 'campaign.json').read_bytes())
    receipt = Path(campaign['receipt_path'])
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    path = tmp_path / 'completed-trace.json'
    path.write_bytes(admission.canonical(dict(schema=1,
        kind='fm1-completed-stop-trace-returned-state', adapter_sha256=sha(admission.__file__),
        native_campaign_path=str(run / 'campaign.json'), native_campaign_sha256=sha(run / 'campaign.json'),
        owned_capture_path=str(run / 'owned-capture.json'), owned_capture_sha256=sha(run / 'owned-capture.json'))))
    accepted = admission.validate_completed_stop_trace(path)
    accepted.check()
    assert accepted.read_outcome == 'completed'
    assert accepted.terminal_at == json.loads((run / 'capture-stop.json').read_bytes())['time']
    assert accepted.stop.snapshot_sha256 == '9afba13c12303476e2d6a9744eb43991ce81781437c45fdfcad5b9054f2b9b8d'
    assert 'observed_at' in json.loads(accepted.stop.snapshot)
    if case == 'valid':
        return
    if case == 'unregistered':
        with pytest.raises(ValueError, match='Canonical'):
            copy.copy(accepted).check()
        return
    boot_sha = accepted.lineage.read_binding()['boot_campaign_sha256']
    marker = receipt.parent / ('.sdk-preparation-stop-trace-' + boot_sha + '.consumed')
    paths = dict(marker=marker, source=Path(admission.__file__).parent / 'fm1_sdk_trace_prepare_stop.py',
        reply=receipt / 'trace-a.raw.bin', result=receipt / 'result.json',
        **{'native-log': receipt / 'native.jsonl', 'outer-log': receipt / 'commands.jsonl',
           'capture-exit': run / 'execution-exit.json', 'wire': run / 'usbmon.txt',
           'wrapper': run / 'execute-once.py', 'witness': run / 'witness.json',
           'plan': receipt / 'plan.json',
           'later-loader': receipt.parent / ('.sdk-preparation-stop-loader-' + boot_sha + '.consumed'),
           'pending-result': receipt / '.result.json.pending',
           'ambiguous-cleanup': run / 'wrapper-cleanup-ambiguous.json'})
    target = paths[case]
    target.write_bytes((target.read_bytes() if target.exists() else b'') + b'changed')
    with pytest.raises(ValueError):
        accepted.check()
    # Refusal also holds for a new factory invocation, not just the old object.
    with pytest.raises((ValueError, json.JSONDecodeError)):
        admission.validate_completed_stop_trace(path)
