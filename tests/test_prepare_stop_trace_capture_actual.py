"""MIT. Genuine V7 authority composition; modeled processes and SG syscalls only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.mark.parametrize('case', ['valid', 'status', 'ioctl', 'changed', 'close', 'hash', 'path', 'reader_pin'])
def test_actual_owned_stop_capture(monkeypatch, case):
    if os.environ.get('LUNAR_PREPARATION_STOP_DISPOSABLE') != '1':
        pytest.skip('Private V7 provenance in disposable Linux container required')
    root = Path(__file__).resolve().parents[1]
    assert root == Path('/tmp/packet-work') and sys.platform == 'linux'
    root.chmod(0o700)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    source = root / 'tools/fm1_sdk_prepare_stop_trace_read.py'
    before = source.read_text()
    assert before.count('PROOF_SOURCE_SHA = None') == 1
    proof_pin = sha(root / 'tools/fm1_sdk_trace_prepare_stop.py')
    source.write_text(before.replace('PROOF_SOURCE_SHA = None', 'PROOF_SOURCE_SHA = ' + repr(proof_pin)))
    import fm1_sdk_prepare_stop_trace_read as n
    import fm1_sdk_trace_prepare_stop as stop
    from test_sdk_trace_sg import mock_sg
    stage = Path('/home/claude/fm1-sdk-trace-campaign-20261012-v7')
    entry = Path('/home/claude/fm1-sdk-trace-entry-20261012-v7')
    lineage = stage / 'boot-lineage.json'
    chain = entry / 'automatic-trace-chain-v7'
    proof = stop.validate_preparation_stop(lineage, chain)
    historical = proof.snapshot
    snapshot = json.loads(historical)
    run = root / 'capture-run'
    run.mkdir(mode=0o700)
    sp = run / 'preparation-stop.json'
    sp.write_bytes(n.canonical(dict(schema=1, kind='fm1-native-preparation-stop-evidence',
        boot_lineage_path=str(lineage), boot_lineage_sha256=sha(lineage), chain_path=str(chain))))
    wp = run / 'witness.json'
    wp.write_bytes(n.canonical(dict(schema=1, kind='fm1-passive-sdk-preparation-stop-trace-connection',
        observed_at=time.time(), usb_binding=snapshot['usb_binding'], sg_binding=snapshot['sg_binding'],
        original_rom_snapshot_sha256=proof.snapshot_sha256, preparation_stop_sha256=sha(sp),
        quiet_state=n.STATE)))
    cp = run / 'campaign.json'
    receipt = proof.lineage.parent / 'modeled-owned-distinct-stop-trace'
    cp.write_bytes(n.canonical(dict(schema=1, kind=n.KIND, adapter_sha256=sha(source),
        preparation_stop_path=str(sp), preparation_stop_sha256=sha(sp),
        connection_witness_path=str(wp), connection_witness_sha256=sha(wp),
        elf_path=str(stage / 'assets/native/lunar-sdk-diagnostic.elf'),
        app_path=str(stage / 'assets/native/lunar-sdk-diagnostic.app.bin'),
        manifest_path=str(stage / 'assets/native/build-manifest.json'), receipt_path=str(receipt),
        active_session_state=n.STATE)))
    modules = []
    for i, name in enumerate(['fm1_prepare_stop_trace_capture.py', 'fm1_prepare_stop_trace_capture_child.py']):
        spec = importlib.util.spec_from_file_location('_actual_owned_stop_' + str(i), root / 'tools' / name)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        modules.append(m)
    w, child = modules
    for m in modules:
        m.STAGE, m.RUN = root, run
        m.NATIVE_SHA, m.READER_SHA, m.PROOF_SHA = sha(source), sha(root / 'tools/fm1_sdk_trace_read.py'), proof_pin
        m.CAMPAIGN_SHA, m.STOP_SHA = sha(cp), sha(sp)
    (run / 'execute-once.py').write_bytes(Path(w.__file__).read_bytes())
    (run / 'execute-child.py').write_bytes(Path(child.__file__).read_bytes())
    (run / 'preflight.json').write_text('{}')
    names = ['capture-run/' + x for x in ['execute-child.py', 'campaign.json', 'preparation-stop.json', 'preflight.json']]
    names += ['tools/' + x for x in ['fm1_sdk_prepare_stop_trace_read.py', 'fm1_sdk_trace_read.py', 'fm1_sdk_trace_prepare_stop.py', 'fm1_sdk_trace_sg.py']]
    pins = {name: sha(root / name) for name in names}
    (run / 'packet-pins.json').write_bytes(n.canonical(pins))
    w.PACKET_SHA, w.PACKET_MEMBERS, w.CHILD_SHA = sha(run / 'packet-pins.json'), len(pins), sha(run / 'execute-child.py')
    state = dict(captures=0, children=0, kills=0, sg=None)
    class Capture:
        pid = 435000
        returncode = None
        def wait(self, timeout):
            assert timeout == 5
            self.returncode = -15
    def popen(args, **kw):
        assert args == ['/usr/bin/timeout', '60', '/bin/cat', '/sys/kernel/debug/usb/usbmon/1u']
        assert kw['start_new_session'] is True
        state['captures'] += 1
        return Capture()
    def execute(args, **kw):
        assert args == ['/usr/bin/python3', '-B', '-E', '-s', '-S', str(run / 'execute-child.py')]
        assert kw['timeout'] == 40 and kw['cwd'] == root
        state['children'] += 1
        native = sys.modules['fm1_sdk_prepare_stop_trace_read']
        original_init = native.NativeSG.__init__
        def modeled_init(self, prepared, permit):
            state['sg'] = mock_sg(prepared, monkeypatch,
                fault=case if case in ['status', 'ioctl', 'changed', 'close'] else None)
            original_init(self, prepared, permit)
        monkeypatch.setattr(native.NativeSG, '__init__', modeled_init)
        try:
            child.main()
        except (ValueError, OSError):
            return SimpleNamespace(returncode=1)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(w.subprocess, 'Popen', popen)
    monkeypatch.setattr(w.subprocess, 'run', execute)
    monkeypatch.setattr(w, 'capture_alive', lambda p,b: dict(timeout_pid=p.pid, cat_pid=435001, process_group=p.pid, open_capture_fd=True))
    monkeypatch.setattr(w.os, 'killpg', lambda p,s: state.__setitem__('kills', state['kills'] + 1))
    if case in ['hash', 'path']:
        # Corrupt only the returned handoff in this rejection model; retain the real inner factory.
        original_load = w.load
        def load(*a):
            native = original_load(*a)
            factory = native.prepare_campaign
            def prepare(path):
                prepared = factory(path)
                if case == 'hash':
                    from dataclasses import replace
                    return replace(prepared, stop_sha256='0' * 64)
                from dataclasses import replace
                seal = json.loads(prepared.seal)
                seal['preparation_stop_path'] = str(run / 'other-stop.json')
                return replace(prepared, seal=n.canonical(seal))
            native.prepare_campaign = prepare
            return native
        monkeypatch.setattr(w, 'load', load)
    elif case == 'reader_pin':
        child.READER_SHA = '0' * 64
    if case in ['hash', 'path']:
        with pytest.raises(ValueError, match='must match canonical reader evidence'):
            w.main()
        assert state['captures'] == state['children'] == 0
    else:
        assert w.main() == (0 if case == 'valid' else 1)
        assert state['captures'] == state['children'] == state['kills'] == 1
        assert (run / 'owned-capture.json').is_file()
        calls = [] if state['sg'] is None else state['sg'].calls
        assert len(calls) == (5 if case in ['valid', 'changed', 'close'] else 0 if case == 'reader_pin' else 1)
        assert all(op in n.OPERATIONS for op in calls)
        assert (receipt / 'result.json').exists() == (case == 'valid')
        assert json.loads((run / 'execution-exit.json').read_bytes())['read_completion_attested'] is False
    assert proof.snapshot == historical
    assert Path(json.loads(lineage.read_bytes())['rom_snapshot_path']).read_bytes() == historical
