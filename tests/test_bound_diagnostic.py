"""Offline injected protocol tests; no physical identity/loader attestation."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_bound_diagnostic as bound  # noqa: E402
from fm1_flash_transaction import create_transaction, load_transaction, save_journal, encoded, digest  # noqa: E402
from fm1_simulated_device import SimulatedDevice, SimulatedDisconnect  # noqa: E402
from fm1_uboot_read import LOADER_SIZE, LOADER_SHA  # noqa: E402
from tests.test_raw_flash_profile import sample  # noqa: E402,F401

LOADER = bytes((i * 31 + 7) & 255 for i in range(LOADER_SIZE))


class ModelTransport:
    """Synthetic loader oracle plus injected binding claims, never hardware."""
    def __init__(self, device, identity):
        self.device, self.identity_evidence = device, copy.deepcopy(identity)
        self.session = device.recovery_session(LOADER)
        self.session_id = 'mock-enumeration-' + str(self.session.generation)
        self.calls, self.closed = [], False
        self.reply_fault = None
        self.binding_fault = None

    def binding(self):
        self.session._check()
        result = dict(phase=self.session.phase, session_id=self.session_id,
                      loader_sha256=LOADER_SHA, identity=copy.deepcopy(self.identity_evidence))
        if self.binding_fault:
            self.binding_fault(result)
        return result

    def exchange(self, cdb, payload, size):
        self.calls.append((cdb, payload, size))
        result = self.session.execute(cdb, payload, size)
        return self.reply_fault(result, cdb) if self.reply_fault else result

    def close(self):
        self.closed = True
        self.session.close()


@pytest.fixture
def prepared(sample, tmp_path):
    s = sample
    identity = dict(s['identity'], flash_size=0x100000, sector_size=4096,
                    page_size=256, jedec=0x856014, usb_port='mock-1-2',
                    usb_topology='/mock/controller/1-2', baseline_sha256=digest(s['baseline']))
    directory = tmp_path / 'transaction'
    bound.prepare_transaction(directory, s['baseline'], s['baseline'], s['target'], identity,
                              ((0x4000, 0x5000),))
    manifest, identity_file, app, elf = (tmp_path / name for name in ('manifest.json', 'identity.json', 'app', 'elf'))
    manifest.write_text(json.dumps(s['manifest']))
    identity_file.write_text(json.dumps(identity))
    app.write_bytes(s['app'])
    elf.write_bytes(s['elf'])
    arguments = dict(manifest_path=manifest, identity_path=identity_file,
                     reference=s['reference'], app_path=app, elf_path=elf)
    device_path = tmp_path / 'nor'
    device = SimulatedDevice(s['baseline'], path=device_path, writable_ranges=((0x4000, 0x5000),),
                             protected_ranges=((0, 0x4000), (bound.raw.CFG_TOOL_OFFSET, 0x100000)),
                             simulator_loader_sha256=hashlib.sha256(LOADER).hexdigest())
    device.register_bootable_image(s['target'])
    return dict(sample=s, directory=directory, arguments=arguments, identity=identity,
                device=device, device_path=device_path)


def policy(p, direction='install', **changes):
    return bound.load_policy(p['directory'], direction=direction, **dict(p['arguments'], **changes))


def session(p, direction='install'):
    transport = ModelTransport(p['device'], p['identity'])
    return policy(p, direction).bind(transport), transport


def rewrite_plan(p, change):
    path = p['directory'] / 'plan.json'
    plan = json.loads(path.read_text())
    change(plan)
    path.write_bytes(encoded(plan))
    journal = json.loads((p['directory'] / 'journal.json').read_text())
    journal['plan_sha256'] = digest(encoded(plan))
    save_journal(p['directory'], journal)


def test_install_restore_completed_readback(prepared):
    p = prepared
    installed, t = session(p)
    receipt = installed.run()
    assert p['device'].flash == p['sample']['target'] and t.closed
    assert receipt['verified_sha256'] == digest(p['sample']['target'])
    assert receipt['commit_sector'] == bound.raw.APP_BASE
    assert receipt['sector_order'][-1] == bound.raw.APP_BASE
    assert receipt['protocol_mock_only'] and not receipt['hardware_validated']
    assert not receipt['physical_loader_recovery_binding_proven']
    checked, t2 = session(p)
    assert checked.run()['sectors_written'] == 0
    assert all(int.from_bytes(cdb[:2], 'big') not in (0xFB01, 0xFB04) for cdb, _, _ in t2.calls)
    restored, _ = session(p, 'restore')
    assert restored.run()['verified_sha256'] == digest(p['sample']['baseline'])
    assert p['device'].flash == p['sample']['baseline']
    with pytest.raises(OSError, match='stopped'):
        installed.online()


@pytest.mark.parametrize('kind', ['scope', 'ranges', 'simulated', 'firmware', 'port', 'topology',
                                 'content_hash', 'unit', 'manifest', 'app', 'elf', 'target', 'backup', 'journal'])
def test_actual_files_rejected_before_transport(prepared, kind):
    p = prepared
    if kind in ('scope', 'ranges'):
        rewrite_plan(p, lambda plan: plan.update({kind if kind == 'scope' else 'writable_ranges':
                                                'other scope' if kind == 'scope' else [[0x4000, 0x6000]]}))
    elif kind in ('simulated', 'firmware', 'port', 'topology', 'content_hash', 'unit'):
        key, value = {'simulated': ('simulated', True), 'firmware': ('firmware', 'FM-1_015'),
                      'port': ('usb_port', ''), 'topology': ('usb_topology', ''),
                      'content_hash': ('baseline_sha256', '0' * 64), 'unit': ('unit_id', 'other')}[kind]
        rewrite_plan(p, lambda plan: plan['identity'].update({key: value}))
        if kind != 'unit':
            identity = dict(p['identity'], **{key: value})
            p['arguments']['identity_path'].write_text(json.dumps(identity))
    elif kind == 'manifest':
        p['arguments']['manifest_path'].write_text('{}')
    elif kind in ('app', 'elf'):
        p['arguments'][kind + '_path'].write_bytes(b'invalid')
    else:
        path = p['directory'] / {'target': 'target.bin', 'backup': 'backupA.bin', 'journal': 'journal.json'}[kind]
        data = path.read_bytes()
        path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    with pytest.raises((ValueError, KeyError, json.JSONDecodeError)):
        policy(p)
    assert not any(e.get('operation') in ('erase', 'program') for e in p['device'].events)


@pytest.mark.parametrize('kind', ['rom', 'loader', 'identity', 'session'])
def test_wrong_injected_binding_rejected_without_commands(prepared, kind):
    p = prepared
    transport = ModelTransport(p['device'], p['identity'])
    key, value = {'rom': ('phase', 'rom'), 'loader': ('loader_sha256', '0' * 64),
                  'identity': ('identity', dict(p['identity'], usb_port='other')),
                  'session': ('session_id', '')}[kind]
    transport.binding_fault = lambda b: b.update({key: value})
    with pytest.raises(ValueError, match='binding'):
        policy(p).bind(transport)
    assert transport.closed and transport.calls == []


def test_frozen_snapshot_and_detached_receipt(prepared):
    p = prepared
    pol = policy(p)
    receipt = pol.receipt()
    receipt['profile']['identity']['unit_id'] = 'different'
    assert pol.receipt()['profile']['identity']['unit_id'] == p['identity']['unit_id']
    rewrite_plan(p, lambda plan: plan.update(scope='different'))
    class Untouched:
        def binding(self):
            pytest.fail('Changed actual files must be rejected before touching transport')
    with pytest.raises(ValueError, match='changed'):
        pol.bind(Untouched())


@pytest.mark.parametrize('op,address,payload', [(0x12, 0, b''), (0xFB06, 0x01C02000, bytes(512)),
                                              (0xFB08, 0x01C02000, b''), (0xFB02, 0, b''),
                                              (0xFC12, 0, b''), (0xA1, 0, b''),
                                              (0xFC0A, 1, b''), (0xFD05, 1, b''),
                                              (0xFB01, 0, b''), (0xFB04, 0xD8000, bytes(256))])
def test_lowest_cmd_rejects_forbidden_operations(prepared, op, address, payload):
    reader, transport = session(prepared)
    with pytest.raises(ValueError):
        reader.cmd(op, address=address, payload=payload)
    assert transport.calls == []


def test_direct_valid_mutation_cannot_bypass_durable_run(prepared):
    reader, t = session(prepared)
    with pytest.raises(ValueError, match='durable'):
        reader.erase(0x4000)
    with pytest.raises(ValueError, match='durable'):
        reader.program(0x4100, prepared['sample']['target'][0x4100:0x4200])
    assert t.calls == []


def test_wrong_pages_direction_crc_and_intent_during_run(prepared):
    p = prepared
    reader, t = session(p)
    checked = []
    def check(event, **fields):
        if event != 'durable_intent' or fields['operation'] != 'program' or checked:
            return
        a = fields['address']
        expected = p['sample']['target'][a:a + 256]
        calls = len(t.calls)
        with pytest.raises(ValueError):
            reader.program(a, bytes([expected[0] ^ 1]) + expected[1:])
        with pytest.raises(ValueError):
            reader.program(a + 1, expected)
        other = a + 256 if a == 0x4000 else 0x4000
        with pytest.raises(ValueError, match='intent'):
            reader.program(other, p['sample']['target'][other:other + 256])
        cdb, payload, size = reader.build_request(0xFB04, address=a, payload=expected)
        malformed = bytearray(cdb)
        malformed[9] ^= 1
        with pytest.raises(ValueError, match='Malformed'):
            reader.execute(bytes(malformed), payload, size)
        assert len(t.calls) == calls
        checked.append(True)
    reader.run(checkpoint=check)
    assert checked
    restored, t2 = session(p, 'restore')
    def wrong_restore(event, **fields):
        if event == 'durable_intent' and fields['operation'] == 'program' and fields['address'] == 0x4000:
            before = len(t2.calls)
            with pytest.raises(ValueError, match='direction'):
                restored.program(0x4000, p['sample']['target'][0x4000:0x4100])
            assert len(t2.calls) == before
    restored.run(checkpoint=wrong_restore)


@pytest.mark.parametrize('kind', ['short', 'echo', 'jedec', 'buffer'])
def test_response_ambiguity_latches_handle(prepared, kind):
    reader, t = session(prepared)
    def fault(result, cdb):
        if kind == 'short':
            return result[:-1]
        if kind == 'echo':
            return b'??' + result[2:]
        if kind == 'jedec':
            return result[:4] + b'????' + result[8:]
        return result[:2] + bytes(4) + result[6:]
    t.reply_fault = fault
    with pytest.raises(ValueError):
        reader.cmd(0xFC14 if kind == 'buffer' else 0xFC0A)
    count = len(t.calls)
    with pytest.raises(OSError, match='stopped'):
        reader.online()
    assert t.closed and len(t.calls) == count


def test_binding_change_and_stale_session_latch(prepared):
    reader, t = session(prepared)
    t.session_id += '-different'
    with pytest.raises(ValueError, match='changed'):
        reader.online()
    assert t.closed and t.calls == []
    fresh, t2 = session(prepared)
    prepared['device'].power_loss()
    with pytest.raises(SimulatedDisconnect):
        fresh.online()
    assert t2.closed and t2.calls == []


def test_changed_binding_after_response_is_ambiguous(prepared):
    reader, t = session(prepared)
    def changed(result, cdb):
        t.session_id += '-reenumerated'
        return result
    t.reply_fault = changed
    with pytest.raises(ValueError, match='changed'):
        reader.online()
    assert t.closed and len(t.calls) == 1
    with pytest.raises(OSError, match='stopped'):
        reader.online()
    assert len(t.calls) == 1


def test_audit_and_wrong_recovery_directory_rejected(prepared, tmp_path):
    audit_file = tmp_path / 'audit.json'
    audit_file.write_text(json.dumps(dict(passed=True, runtime='sdk-free', n_pending=0)))
    with pytest.raises(ValueError, match='audit'):
        policy(prepared, audit_path=audit_file)
    with pytest.raises(FileNotFoundError):
        bound.load_policy(tmp_path / 'other-recovery-directory', direction='restore', **prepared['arguments'])
    with pytest.raises(ValueError, match='direction'):
        policy(prepared, direction='other')


@pytest.mark.parametrize('operation,kind,prefix,direction', [
    ('program', 'torn', 0, 'install'), ('program', 'torn', 127, 'install'),
    ('program', 'torn', 256, 'restore'), ('program', 'ack_loss', 0, 'install'),
    ('erase', 'torn', 1, 'install'), ('erase', 'torn', 4096, 'restore'),
    ('erase', 'ack_loss', 0, 'install')])
def test_persisted_protocol_fault_resume_requires_fresh_adapter(prepared, operation, kind, prefix, direction):
    p = prepared
    if direction == 'restore':
        session(p)[0].run()
    reader, t = session(p, direction)
    p['device'].inject_failure(operation=operation, kind=kind, after_bytes=prefix)
    with pytest.raises(SimulatedDisconnect):
        reader.run()
    assert t.closed
    assert load_transaction(p['directory'])[1]['state'] == 'recovery_required'
    calls = len(t.calls)
    with pytest.raises(OSError, match='stopped'):
        reader.run()
    assert len(t.calls) == calls
    p['device'] = SimulatedDevice(path=p['device_path'])
    resumed, _ = session(p, direction)
    expected = p['sample']['target' if direction == 'install' else 'baseline']
    assert resumed.run()['verified_sha256'] == digest(expected)
    assert p['device'].flash == expected


def test_corrupt_read_and_changed_files_stop_without_retry(prepared):
    p = prepared
    reader, t = session(p)
    p['device'].inject_failure(operation='read', kind='corrupt_read')
    with pytest.raises(ValueError, match='outside'):
        reader.run()
    assert t.closed and all(int.from_bytes(c[:2], 'big') not in (0xFB01, 0xFB04) for c, _, _ in t.calls)
    fresh, t2 = session(p)
    def changed(event, **fields):
        if event == 'durable_intent':
            rewrite_plan(p, lambda plan: plan.update(scope='changed after bind'))
    with pytest.raises(ValueError, match='changed'):
        fresh.run(checkpoint=changed)
    assert t2.closed and all(int.from_bytes(c[:2], 'big') not in (0xFB01, 0xFB04) for c, _, _ in t2.calls)


def test_corrupt_post_program_read_requires_fresh_recovery(prepared):
    p = prepared
    reader, t = session(p)
    # Full baseline read, current sector, erased sector, then verification.
    p['device'].inject_failure(operation='read', kind='corrupt_read', occurrence=4096 + 16 + 16 + 1)
    with pytest.raises(ValueError, match='Program readback'):
        reader.run()
    assert p['device'].flash == p['sample']['target'] and t.closed
    assert load_transaction(p['directory'])[1]['state'] == 'recovery_required'
    fresh, _ = session(p)
    assert fresh.run()['sectors_written'] == 0


@pytest.mark.parametrize('event', ['durable_intent', 'operation_returned'])
def test_host_checkpoint_crash_preserves_journal_and_requires_fresh_bind(prepared, event):
    class HostCrash(BaseException):
        pass
    p = prepared
    reader, t = session(p)
    def crash(observed, **fields):
        if observed == event:
            raise HostCrash()
    with pytest.raises(HostCrash):
        reader.run(checkpoint=crash)
    assert t.closed and load_transaction(p['directory'])[1]['state'] == 'recovery_required'
    p['device'] = SimulatedDevice(path=p['device_path'])
    fresh, _ = session(p)
    assert fresh.run()['verified_sha256'] == digest(p['sample']['target'])


def test_keepalive_and_wire_read_shapes(prepared, monkeypatch):
    reader, t = session(prepared)
    clock = iter(range(20))
    monkeypatch.setattr(bound.time, 'monotonic', lambda: next(clock))
    assert reader.read(0, 512) == prepared['sample']['baseline'][:512]
    assert [int.from_bytes(c[:2], 'big') for c, _, _ in t.calls] == [0xFC0A, 0xFD05, 0xFC0A, 0xFD05]
    for cdb, payload, size in t.calls:
        assert len(cdb) == 16 and not payload and size in (16, 256)


@pytest.mark.parametrize('kind', ['missing', 'null', 'wrong', 'order'])
def test_diagnostic_requires_sealed_directory_last_before_transport(prepared, kind):
    p = prepared
    def change(plan):
        if kind == 'missing':
            plan.pop('commit_sector')
        elif kind == 'null':
            plan['commit_sector'] = None
        elif kind == 'wrong':
            plan['commit_sector'] = 0x5000
        else:
            plan['sector_order'] = []
    rewrite_plan(p, change)
    with pytest.raises(ValueError):
        policy(p)
    assert not any(e.get('operation') in ('erase', 'program') for e in p['device'].events)
