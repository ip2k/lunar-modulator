"""MIT. Device-free SG model and exact private-file rehearsal acceptance.

Unit fixtures explicitly inject test-only Prepared authority. Actual-fixture
tests use the production factories, pinned ELF, backup inventory and images.
No test opens an SG device or submits a kernel SG_IO request.
"""
import binascii
import copy
import ctypes as C
from dataclasses import replace
import json
import os
from pathlib import Path
import stat
import sys
import shutil
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_sdk_rehearsal as rehearsal
import fm1_fixed_loader_backup as bridge
from fm1_uboot_read import SGHeader


def wire(op, address=0, payload=b''):
    if op == 0xFC0A:
        return bytes.fromhex('fc0a' + 'ff' * 14), b'', 16
    args = address.to_bytes(4, 'big')
    if op == 0xFD05:
        args += b'\x01\x00'
    elif op == 0xFB04:
        args += b'\x01\x00\x00' + binascii.crc_hqx(payload, 0).to_bytes(2, 'little')
    return (op.to_bytes(2, 'big') + args).ljust(16, b'\xff'), payload, 256 if op == 0xFD05 else 0 if payload else 16


class Policy:
    """Small explicit mock for wire tests, not a production authorization."""
    def __init__(self, direction):
        self.direction = direction
        self.baseline = b'\x66' * 0x100000
        self.target = b'\x99' * 0x100000
        self.sectors = tuple(range(0x4000, 0x22000, 4096))
        self.plan_bytes = rehearsal.canonical(dict(identity=dict(unit_id='mock-only')))
        self.binding_bytes = rehearsal.canonical(dict(usb_binding=dict(path='3-2', devnum='23'),
                                                     backup_manifest_sha256='mock-only'))
        self.journal = dict(state='running', direction=direction,
                            intent=dict(operation='erase', address=0x4000))
        self.checks = 0
        self.fault = False

    def check_files(self):
        self.checks += 1
        if self.fault:
            raise ValueError('Mock frozen artifact drift')
        return copy.deepcopy(self.journal)


class SGModel:
    """NOR + ioctl model. Fake device operations dispatch only on fd 98765."""
    FD = 98765

    def __init__(self, monkeypatch, mapping, baseline):
        self.mapping = copy.deepcopy(mapping)
        self.flash = bytearray(baseline)
        self.calls, self.events, self.opened, self.closed = [], [], [], []
        self.completion, self.response_fault = {}, None
        self.after_ioctl = None
        self.mode = stat.S_IFCHR | 0o600
        self.node_identity = tuple(mapping['node_identity'])
        self.lock_fault = False
        self.elapsed = 0
        self.real_open, self.real_close, self.real_fstat = os.open, os.close, os.fstat
        self.real_flock = rehearsal.fcntl.flock
        monkeypatch.setattr(rehearsal.os, 'open', self.open)
        monkeypatch.setattr(rehearsal.os, 'close', self.close)
        monkeypatch.setattr(rehearsal.os, 'fstat', self.fstat)
        monkeypatch.setattr(rehearsal.fcntl, 'flock', self.flock)
        monkeypatch.setattr(rehearsal.fcntl, 'ioctl', self.ioctl)
        monkeypatch.setattr(rehearsal.time, 'monotonic', lambda: self.elapsed)

    def open(self, path, flags, *args, **kwargs):
        if str(path) == self.mapping['node']:
            assert flags == os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
            self.opened.append(str(path))
            return self.FD
        # A discovered node changing its name must fail before any real open.
        assert not str(path).startswith('/dev/sg'), 'Test attempted a real SG open'
        return self.real_open(path, flags, *args, **kwargs)

    def close(self, fd):
        if fd == self.FD:
            self.closed.append(fd)
        else:
            self.real_close(fd)

    def fstat(self, fd):
        if fd != self.FD:
            return self.real_fstat(fd)
        return SimpleNamespace(st_mode=self.mode, st_dev=self.node_identity[0],
                               st_ino=self.node_identity[1], st_rdev=self.node_identity[2])

    def flock(self, fd, flags):
        if fd != self.FD:
            return self.real_flock(fd, flags)
        assert flags == rehearsal.fcntl.LOCK_EX | rehearsal.fcntl.LOCK_NB
        if self.lock_fault:
            raise BlockingIOError('Mock lock busy')

    def discover(self, usb):
        return copy.deepcopy(self.mapping)

    def ioctl(self, fd, code, h):
        assert fd == self.FD and code == 0x2285
        assert h.interface_id == ord('S') and h.cmd_len == 16 and h.sense_max == 32
        assert h.timeout == 3000 and h.iovec_count == h.flags == h.pack_id == 0
        cdb = C.string_at(h.cmd, h.cmd_len)
        op = int.from_bytes(cdb[:2], 'big')
        address = int.from_bytes(cdb[2:6], 'big')
        payload = C.string_at(h.data, h.data_len) if h.direction == -2 else b''
        assert op in (0xFC0A, 0xFD05, 0xFB01, 0xFB04)
        assert h.direction == (-2 if op == 0xFB04 else -3)
        assert h.data_len == (256 if op in (0xFD05, 0xFB04) else 16)
        assert (cdb, payload, 256 if op == 0xFD05 else 0 if payload else 16) == wire(op, address if op != 0xFC0A else 0, payload)
        self.calls.append(dict(op=op, address=address, payload=payload,
                               direction=h.direction, data_len=h.data_len))
        if op == 0xFC0A:
            answer = b'\xfc\x0a\x03\x00' + (0x856014).to_bytes(4, 'little') + b'\x00' * 8
        elif op == 0xFD05:
            answer = bytes(self.flash[address:address + 256])
        elif op == 0xFB01:
            assert address in range(0x4000, 0x22000, 4096)
            self.flash[address:address + 4096] = b'\xff' * 4096
            answer = cdb[:2] + b'\x00' * 14
        else:
            assert address // 4096 * 4096 in range(0x4000, 0x22000, 4096)
            self.flash[address:address + 256] = bytes(a & b for a, b in zip(self.flash[address:address + 256], payload))
            answer = b''
        if self.response_fault:
            answer = self.response_fault(answer)
        if answer:
            C.memmove(h.data, answer, len(answer))
        for key, value in self.completion.items():
            setattr(h, key, value)
        if self.after_ioctl:
            self.after_ioctl()
        return 0

    def log(self, event, **fields):
        self.events.append(dict(event=event, **fields))


@pytest.fixture
def unit(monkeypatch, tmp_path):
    policies = tuple(Policy(d) for d in ('install', 'restore'))
    mapping = dict(node='/dev/sgMOCK', node_identity=[1, 2, 3], sysfs='/mock/usb/3-2')
    model = SGModel(monkeypatch, mapping, policies[0].baseline)
    fakebridge = SimpleNamespace(discover_sg=model.discover, LOADER_SHA=bridge.LOADER_SHA,
                                 private_file=bridge.private_file, sync_dir=bridge.sync_dir)
    parent = tmp_path / 'backup'; parent.mkdir(mode=0o700)
    config = dict(receipt_path=str(parent / 'rehearsal'), adapter_sha256='mock-only', sg_binding=mapping)
    prepared = rehearsal.Prepared(rehearsal.canonical(config), 'mock-only', policies,
                                   rehearsal.canonical(mapping), fakebridge, SGHeader)
    rehearsal._AUTHORIZED.add(prepared)
    monkeypatch.setattr(rehearsal, 'check_sources', lambda: Path(rehearsal.__file__).parent)
    return SimpleNamespace(prepared=prepared, policy=policies[0], model=model, parent=parent)


def transport(unit, direction='install', log=None):
    policy = unit.prepared.policies[0 if direction == 'install' else 1]
    return rehearsal.RehearsalSG(unit.prepared, policy, log or unit.model.log)


def assert_stopped(t, model):
    attempts = len(model.calls)
    assert t.failed and t.fd is None and model.closed
    with pytest.raises(ValueError):
        t.exchange(*wire(0xFC0A))
    assert len(model.calls) == attempts  # No automatic or caller retry on this handle.


@pytest.mark.parametrize('field', ['config', 'campaign_sha256', 'policies', 'mapping', 'bridge', 'header_type'])
def test_copied_prepared_has_no_authority(unit, field):
    values = dict(config=b'{}', campaign_sha256='changed', policies=(), mapping=b'{}',
                  bridge=object(), header_type=object)
    copied = replace(unit.prepared, **{field: values[field]})
    with pytest.raises(ValueError, match='Exact prepared'):
        copied.check()
    with pytest.raises(ValueError):
        rehearsal.RehearsalSG(copied, unit.policy, unit.model.log)
    assert not unit.model.opened


def test_copied_direction_policy_rejected_before_open(unit):
    with pytest.raises(ValueError, match='direction policy'):
        rehearsal.RehearsalSG(unit.prepared, copy.copy(unit.policy), unit.model.log)
    assert not unit.model.opened


@pytest.mark.parametrize('direction', ['install', 'restore'])
def test_exact_wire_and_direction_page(unit, direction):
    t = transport(unit, direction)
    p = t.policy
    assert t.exchange(*wire(0xFC0A))[2] == 3
    assert t.exchange(*wire(0xFD05, 0x4000)) == p.baseline[0x4000:0x4100]
    p.journal['intent'] = dict(operation='erase', address=0x4000)
    assert t.exchange(*wire(0xFB01, 0x4000))[:2] == b'\xfb\x01'
    p.journal['intent'] = dict(operation='program', address=0x4000)
    desired = p.target if direction == 'install' else p.baseline
    assert t.exchange(*wire(0xFB04, 0x4000, desired[0x4000:0x4100])) == b''
    assert bytes(unit.model.flash[0x4000:0x4100]) == desired[0x4000:0x4100]
    assert [c['data_len'] for c in unit.model.calls] == [16, 256, 16, 256]
    assert [(e['out_len'], e['in_len']) for e in unit.model.events if e['event'] == 'sg_submit_intent'] == [(0, 16), (0, 256), (0, 16), (256, 0)]
    completions=[e for e in unit.model.events if e['event']=='sg_completion']
    assert [e['response_sha256'] for e in completions] == [
        rehearsal.digest(b'\xfc\x0a\x03\x00'+(0x856014).to_bytes(4,'little')+b'\x00'*8),
        rehearsal.digest(p.baseline[0x4000:0x4100]),
        rehearsal.digest(b'\xfb\x01'+b'\x00'*14), None]
    t.close(); t.close()
    assert unit.model.closed == [unit.model.FD]


@pytest.mark.parametrize('op', [0xFC14, 0xFC0C, 0xFB06, 0xFB08, 0xFC12, 0x00A1, 0x0012, 0xFFFF])
def test_forbidden_commands_close_without_ioctl(unit, op):
    t = transport(unit)
    with pytest.raises(ValueError):
        t.exchange(*wire(op))
    assert not unit.model.calls
    assert_stopped(t, unit.model)


@pytest.mark.parametrize('fault', ['padding', 'crc', 'payload', 'short_payload', 'out_len',
    'in_len', 'bool_in_len', 'mutable_cdb', 'mutable_payload', 'short_cdb', 'unaligned',
    'protected', 'outside', 'wrong_intent', 'wrong_direction', 'not_running'])
def test_mutation_shape_intent_and_bounds_fail_before_ioctl(unit, fault):
    t = transport(unit)
    p = unit.policy
    p.journal['intent'] = dict(operation='program', address=0x4000)
    cdb, payload, size = wire(0xFB04, 0x4000, p.target[0x4000:0x4100])
    if fault == 'padding': cdb = cdb[:-1] + b'\x00'
    elif fault == 'crc': cdb = cdb[:9] + bytes([cdb[9] ^ 1]) + cdb[10:]
    elif fault == 'payload': cdb, payload, size = wire(0xFB04, 0x4000, p.baseline[0x4000:0x4100])
    elif fault == 'short_payload': cdb, payload, size = wire(0xFB04, 0x4000, payload[:-1])
    elif fault == 'out_len': payload = b''
    elif fault == 'in_len': size = 16
    elif fault == 'bool_in_len': size = False
    elif fault == 'mutable_cdb': cdb = bytearray(cdb)
    elif fault == 'mutable_payload': payload = bytearray(payload)
    elif fault == 'short_cdb': cdb = cdb[:-1]
    elif fault in ('unaligned', 'protected', 'outside'):
        address = {'unaligned': 0x4001, 'protected': 0x3000, 'outside': 0x100000}[fault]
        p.journal['intent']['address'] = address
        cdb, payload, size = wire(0xFB04, address, payload)
    elif fault == 'wrong_intent': p.journal['intent']['operation'] = 'erase'
    elif fault == 'wrong_direction': p.journal['direction'] = 'restore'
    elif fault == 'not_running': p.journal['state'] = 'prepared'
    with pytest.raises(ValueError): t.exchange(cdb, payload, size)
    assert not unit.model.calls
    assert_stopped(t, unit.model)


@pytest.mark.parametrize('wire_request', [wire(0xFD05, 1), wire(0xFD05, 0x100000),
    (wire(0xFD05)[0], b'x', 256), (wire(0xFD05)[0], b'', 255),
    (wire(0xFC0A)[0], b'x', 16), (wire(0xFC0A)[0], b'', 17),
    (wire(0xFC0A)[0][:-1]+b'\x00', b'', 16), wire(0xFB01, 0x3000)])
def test_read_query_and_erase_shapes(unit, wire_request):
    t = transport(unit)
    with pytest.raises(ValueError): t.exchange(*wire_request)
    assert not unit.model.calls
    assert_stopped(t, unit.model)


@pytest.mark.parametrize('field,value', [('status', 1), ('masked', 1), ('msg', 1),
    ('host', 1), ('driver', 1), ('resid', 1), ('resid', -1), ('info', 1),
    ('sense_len', 1), ('sense_len', 32), ('sense_len', 255)])
def test_ambiguous_status_residual_or_sense_never_retried(unit, field, value):
    t = transport(unit)
    unit.model.completion[field] = value
    with pytest.raises(OSError): t.exchange(*wire(0xFD05))
    assert len(unit.model.calls) == 1
    assert unit.model.events[-1][field] == value
    assert_stopped(t, unit.model)


@pytest.mark.parametrize('fault', ['echo', 'type', 'jedec'])
def test_protocol_query_response_failure(unit, fault):
    def corrupt(answer):
        answer = bytearray(answer)
        answer[{'echo': 0, 'type': 2, 'jedec': 4}[fault]] ^= 1
        return bytes(answer)
    unit.model.response_fault = corrupt
    t = transport(unit)
    with pytest.raises(ValueError): t.exchange(*wire(0xFC0A))
    assert_stopped(t, unit.model)


@pytest.mark.parametrize('fault', ['node', 'sysfs', 'identity', 'regular', 'lock'])
def test_connection_or_lock_failure_at_open(unit, fault):
    if fault in ('node', 'sysfs'): unit.model.mapping[fault] += '-changed'
    elif fault == 'identity': unit.model.node_identity = (1, 2, 4)
    elif fault == 'regular': unit.model.mode = stat.S_IFREG | 0o600
    else: unit.model.lock_fault = True
    with pytest.raises((ValueError, BlockingIOError)): transport(unit)
    assert not unit.model.calls
    if unit.model.opened: assert unit.model.closed == [unit.model.FD]


@pytest.mark.parametrize('phase', ['before', 'intent', 'completion'])
def test_mapping_drift_on_every_exchange_boundary(unit, phase):
    def mutate(): unit.model.mapping['sysfs'] += '-reconnected'
    def log(event, **fields):
        unit.model.log(event, **fields)
        if phase == 'intent' and event == 'sg_submit_intent': mutate()
        if phase == 'completion' and event == 'sg_completion': mutate()
    t = transport(unit, log=log)
    if phase == 'before': mutate()
    with pytest.raises(ValueError): t.exchange(*wire(0xFD05))
    assert len(unit.model.calls) == (1 if phase == 'completion' else 0)
    assert_stopped(t, unit.model)


@pytest.mark.parametrize('phase', ['before', 'intent'])
def test_frozen_artifact_drift_prevents_mutation(unit, phase):
    def log(event, **fields):
        unit.model.log(event, **fields)
        if event == 'sg_submit_intent' and phase == 'intent': unit.policy.fault = True
    t = transport(unit, log=log)
    if phase == 'before': unit.policy.fault = True
    with pytest.raises(ValueError): t.exchange(*wire(0xFB01, 0x4000))
    assert not unit.model.calls
    assert_stopped(t, unit.model)


@pytest.mark.parametrize('reason', ['clock_backwards', 'expired', 'limit', 'ioctl_exception', 'log_exception'])
def test_bounded_session_and_exception_fail_closed(unit, monkeypatch, reason):
    t = transport(unit)
    if reason == 'clock_backwards': unit.model.elapsed = -1
    elif reason == 'expired': unit.model.elapsed = rehearsal.LIVE_SECONDS + 1
    elif reason == 'limit': t.attempts = rehearsal.COMMAND_LIMIT
    elif reason == 'ioctl_exception':
        monkeypatch.setattr(rehearsal.fcntl, 'ioctl', lambda *a: (_ for _ in ()).throw(OSError('Mock disconnect')))
    else: t.log = lambda *a, **k: (_ for _ in ()).throw(OSError('Mock receipt failure'))
    with pytest.raises((ValueError, OSError)): t.exchange(*wire(0xFD05))
    assert not unit.model.calls
    assert_stopped(t, unit.model)


def test_input_paths_size_type_and_no_follow(tmp_path):
    p = tmp_path/'input'; p.write_bytes(b'1234')
    assert rehearsal.read_file(p, 4) == b'1234'
    with pytest.raises(ValueError): rehearsal.read_file(p, 3)
    with pytest.raises(ValueError): rehearsal.read_file('relative')
    link = tmp_path/'link'; link.symlink_to(p)
    with pytest.raises(OSError): rehearsal.read_file(link)
    with pytest.raises((OSError, ValueError)): rehearsal.read_file(tmp_path)
    fifo = tmp_path/'fifo'; os.mkfifo(fifo)
    with pytest.raises(ValueError): rehearsal.read_file(fifo)


def test_fdopen_failure_closes_raw_fd(tmp_path, monkeypatch):
    p=tmp_path/'input'; p.write_bytes(b'x')
    closed=[]; real_close=os.close
    monkeypatch.setattr(rehearsal.os, 'close', lambda fd: (closed.append(fd), real_close(fd))[1])
    monkeypatch.setattr(rehearsal.os, 'fdopen', lambda *a: (_ for _ in ()).throw(OSError('fdopen')))
    with pytest.raises(OSError): rehearsal.read_file(p)
    assert len(closed) == 1
    with pytest.raises(OSError): os.fstat(closed[0])


@pytest.mark.parametrize('name', list(rehearsal.SOURCES))
def test_each_dependency_hash_is_checked(monkeypatch, name):
    # Mutation coverage must start from a matching snapshot of every dependency.
    # Otherwise an unrelated historical pin drift masks the selected corruption.
    root = Path(rehearsal.__file__).parent
    good_hashes = {key: rehearsal.digest(rehearsal.read_file(root / key))
                   for key in rehearsal.SOURCES}
    monkeypatch.setattr(rehearsal, 'SOURCES', good_hashes)
    read = rehearsal.read_file
    changed_path = root / name
    monkeypatch.setattr(rehearsal, 'read_file', lambda path, *args: read(path, *args) +
                        (b'changed' if Path(path) == changed_path else b''))
    with pytest.raises(ValueError, match='Reviewed implementation changed: ' + name):
        rehearsal.check_sources()


def test_current_reviewed_source_set_matches_its_pins():
    # The previously documented historical drift was resolved by a later
    # coordinator review. Negative pin-drift behavior is covered by the
    # synthetic mutation cases in test_each_dependency_hash_is_checked.
    assert rehearsal.check_sources() == Path(rehearsal.__file__).absolute().parent


def test_ambient_import_is_rejected(monkeypatch):
    root = Path(rehearsal.__file__).parent
    monkeypatch.setattr(rehearsal, 'check_sources', lambda: root)
    monkeypatch.setattr(rehearsal.importlib, 'import_module', lambda name: SimpleNamespace(__file__='/ambient/'+name+'.py'))
    with pytest.raises(ValueError, match='Ambient'): rehearsal.imports()


@pytest.mark.parametrize('failure', [None, 'install', 'restore', 'install_hash', 'restore_hash'])
def test_one_use_and_direction_result_acceptance(unit, monkeypatch, failure):
    started=[]
    class Session:
        def __init__(self, p): self.p=p
        def run(self, checkpoint):
            started.append(self.p.direction)
            if failure == self.p.direction: raise OSError('Mock ambiguous interruption')
            expected = rehearsal.TARGET_SHA if self.p.direction == 'install' else rehearsal.BASELINE_SHA
            return dict(verified_sha256='wrong' if failure == self.p.direction+'_hash' else expected, sectors_written=30)
    for p in unit.prepared.policies: p.bind=lambda t, p=p: Session(p)
    if failure:
        with pytest.raises((OSError, ValueError)): rehearsal.run_campaign(unit.prepared)
        assert not (unit.parent/'rehearsal/result.json').exists()
        events=[json.loads(l) for l in (unit.parent/'rehearsal/commands.jsonl').read_text().splitlines()]
        assert events[-1]['event']=='rehearsal_stopped_ambiguous' and events[-1]['retry'] is False
    else:
        results=rehearsal.run_campaign(unit.prepared)
        assert [r['direction'] for r in results] == ['install', 'restore']
        saved=json.loads((unit.parent/'rehearsal/result.json').read_bytes())
        assert saved['stock_baseline_restored'] is True and saved['boot_observed'] is False
        assert saved['physical_recovery_verified'] is False
        assert all(r['full_flash_readback_verified'] and not r['kernel_exclusivity'] for r in results)
    assert started == (['install'] if failure in ('install', 'install_hash') else ['install', 'restore'])
    assert (unit.parent/'.sdk-rehearsal.consumed').read_text() == unit.prepared.campaign_sha256
    config=json.loads(unit.prepared.config); config['receipt_path']=str(unit.parent/'second-name')
    second=replace(unit.prepared, config=rehearsal.canonical(config)); rehearsal._AUTHORIZED.add(second)
    before=list(started)
    with pytest.raises(FileExistsError): rehearsal.run_campaign(second)
    assert started == before and not unit.model.calls


def env_path(name):
    assert os.environ.get(name), 'Required exact private Hera fixture: ' + name
    return Path(os.environ[name])


PRIVATE_REHEARSAL_PATHS = (
    'LUNAR_REHEARSAL_FRESH', 'LUNAR_REHEARSAL_BACKUP', 'LUNAR_REHEARSAL_RAW_FINAL',
)


def private_rehearsal_paths():
    """Public CI can omit private files; a requested private gate cannot."""
    required = os.environ.get('LUNAR_REQUIRE_PRIVATE_FIXTURES', '0')
    assert required in ('0', '1'), 'LUNAR_REQUIRE_PRIVATE_FIXTURES must be 0 or 1'
    if required == '0' and not any(name in os.environ for name in PRIVATE_REHEARSAL_PATHS):
        pytest.skip('Exact private rehearsal fixtures unavailable; set LUNAR_REQUIRE_PRIVATE_FIXTURES=1 to require them')
    return tuple(env_path(name) for name in PRIVATE_REHEARSAL_PATHS)


@pytest.mark.parametrize('mode', ['public', 'required', 'partial', 'empty', 'all_empty', 'complete', 'invalid'])
def test_private_rehearsal_fixture_selection(monkeypatch, tmp_path, mode):
    for name in (*PRIVATE_REHEARSAL_PATHS, 'LUNAR_REQUIRE_PRIVATE_FIXTURES'):
        monkeypatch.delenv(name, raising=False)
    if mode in ('required', 'partial'):
        monkeypatch.setenv('LUNAR_REQUIRE_PRIVATE_FIXTURES', '1' if mode == 'required' else '0')
    if mode in ('partial', 'complete'):
        names = PRIVATE_REHEARSAL_PATHS[:1] if mode == 'partial' else PRIVATE_REHEARSAL_PATHS
        for name in names:
            monkeypatch.setenv(name, str(tmp_path / name))
    if mode == 'invalid':
        monkeypatch.setenv('LUNAR_REQUIRE_PRIVATE_FIXTURES', 'yes')
    if mode in ('empty', 'all_empty'):
        names = PRIVATE_REHEARSAL_PATHS[:1] if mode == 'empty' else PRIVATE_REHEARSAL_PATHS
        for name in names:
            monkeypatch.setenv(name, '')
    if mode == 'public':
        with pytest.raises(pytest.skip.Exception, match='Exact private rehearsal fixtures unavailable'):
            private_rehearsal_paths()
    elif mode in ('required', 'partial', 'empty', 'all_empty', 'invalid'):
        with pytest.raises(AssertionError):
            private_rehearsal_paths()
    else:
        assert private_rehearsal_paths() == tuple(tmp_path / name for name in PRIVATE_REHEARSAL_PATHS)


@pytest.fixture
def actual(tmp_path):
    """Pinned actual files; no synthetic manifests, inventory, ELF or image."""
    import fm1_bound_sdk_diagnostic as bound
    fresh, backup, final = private_rehearsal_paths()
    campaign=json.loads((backup/'campaign.json').read_bytes())
    receipt_parent=backup/'attempt-001'
    assert receipt_parent == Path(campaign['receipt_path'])
    assert stat.S_IMODE(receipt_parent.stat().st_mode)==0o700
    identity=json.loads((fresh/'identity.json').read_bytes())
    identity.update(flash_size=0x100000, sector_size=4096, page_size=256, jedec=0x856014)
    identity_path=tmp_path/'identity.json'; identity_path.write_bytes(rehearsal.canonical(identity))
    target=(fresh/'target-fresh-offline/target.bin').read_bytes()
    baseline=(receipt_parent/'dumpA.bin').read_bytes()
    receipt=json.loads((fresh/'target-fresh-offline/receipt.json').read_bytes())
    directory=tmp_path/'transaction'
    bound.prepare_transaction(directory, baseline, (receipt_parent/'dumpB.bin').read_bytes(), target,
                              identity, receipt['writable_ranges'])
    inputs=dict(directory=directory, manifest_path=receipt_parent/'manifest.json', identity_path=identity_path,
        reference=final/'private/FM-1_092.fwsc_unpack', app_path=fresh/'lunar-sdk-diagnostic.app.bin',
        elf_path=fresh/'sdk.elf', campaign_path=backup/'campaign.json', entry_log_path=backup/'entry.jsonl',
        backup_log_path=receipt_parent/'commands.jsonl', loader_path=backup/'stage/candidate.encrypted.bin',
        profile_path=backup/'stage/profile.json', audit_path=final/'sdk-image-audit.json')
    manifest=json.loads(inputs['manifest_path'].read_bytes())
    config=dict(schema=1, kind='fm1-exact-sdk-install-restore-rehearsal',
        adapter_sha256=rehearsal.digest(Path(rehearsal.__file__).read_bytes()),
        policy_inputs={k:str(v) for k,v in inputs.items()}, backup_exit_status=0,
        backup_commands_sha256=rehearsal.digest(inputs['backup_log_path'].read_bytes()),
        active_session_state='matching-backup-no-later-commands', sg_binding=manifest['sg_binding'],
        receipt_path=str(receipt_parent/('test-rehearsal-'+tmp_path.name)))
    path=tmp_path/'campaign.json'; path.write_bytes(rehearsal.canonical(config))
    fixture=SimpleNamespace(path=path, config=config, inputs=inputs, baseline=baseline, target=target)
    yield fixture
    # Only the disposable container's modeled backup is changed. Never erase a
    # marker in a physical backup directory: these env paths are supplied only
    # by the device-free harness and the real host bench is not mounted.
    if os.environ.get('LUNAR_REHEARSAL_DISPOSABLE') == '1':
        (receipt_parent/'.sdk-rehearsal.consumed').unlink(missing_ok=True)
        shutil.rmtree(config['receipt_path'], ignore_errors=True)


def test_actual_campaign_preflight_without_transport(actual, monkeypatch):
    monkeypatch.setattr(rehearsal, 'RehearsalSG', lambda *a: pytest.fail('Factory opened transport'))
    prepared=rehearsal.prepare_campaign(actual.path)
    assert prepared.campaign_sha256==rehearsal.digest(actual.path.read_bytes())
    assert [p.direction for p in prepared.policies]==['install', 'restore']
    assert all(p.sectors==tuple(range(0x4000,0x22000,4096)) for p in prepared.policies)
    assert all(p.receipt()['hardware_validated'] is False for p in prepared.policies)
    assert not Path(actual.config['receipt_path']).exists()


@pytest.mark.parametrize('field', ['schema', 'kind', 'adapter_sha256', 'backup_exit_status',
    'backup_commands_sha256', 'active_session_state', 'sg_binding', 'receipt_path', 'extra', 'policy_inputs'])
def test_actual_campaign_envelope_fail_closed(actual, field):
    config=copy.deepcopy(actual.config)
    changes=dict(schema=True, kind='other', adapter_sha256='0'*64, backup_exit_status=True,
        backup_commands_sha256='0'*64, active_session_state='old-session', sg_binding={},
        receipt_path=str(actual.path.parent/'wrong-parent'), extra=1, policy_inputs={})
    config[field]=changes[field]
    actual.path.write_bytes(rehearsal.canonical(config))
    with pytest.raises((ValueError, KeyError)): rehearsal.prepare_campaign(actual.path)


@pytest.mark.parametrize('key', ['manifest_path', 'identity_path', 'app_path', 'elf_path',
    'campaign_path', 'entry_log_path', 'backup_log_path', 'loader_path', 'profile_path', 'audit_path'])
def test_actual_input_corruption_rejected_before_open(actual, key, tmp_path):
    # Never alter shared private fixtures; relocate only the deliberately corrupt
    # selected file. Actual other campaign hashes and evidence remain unchanged.
    original=actual.inputs[key].read_bytes()
    changed=tmp_path/('corrupt-'+key); changed.write_bytes(original[:-1]+bytes([original[-1]^1]))
    config=copy.deepcopy(actual.config); config['policy_inputs'][key]=str(changed)
    actual.path.write_bytes(rehearsal.canonical(config))
    with pytest.raises((ValueError, KeyError, json.JSONDecodeError)): rehearsal.prepare_campaign(actual.path)


def test_actual_campaign_mock_sg_install_full_readback_restore(actual, monkeypatch):
    prepared=rehearsal.prepare_campaign(actual.path)  # All real gates, no gate monkeypatch.
    mapping=json.loads(prepared.mapping)
    model=SGModel(monkeypatch, mapping, actual.baseline)
    monkeypatch.setattr(prepared.bridge, 'discover_sg', model.discover)
    results=rehearsal.run_campaign(prepared)
    assert [r['verified_sha256'] for r in results] == [rehearsal.TARGET_SHA, rehearsal.BASELINE_SHA]
    assert bytes(model.flash)==actual.baseline
    assert bytes(model.flash[:0x4000])==actual.baseline[:0x4000]
    assert bytes(model.flash[0x22000:])==actual.baseline[0x22000:]
    erases=[r['address'] for r in model.calls if r['op']==0xFB01]
    order=list(range(0x5000,0x22000,4096))+[0x4000]
    assert erases==order+order  # Directory/commit sector is last in both directions.
    assert all(r['op'] in (0xFC0A,0xFD05,0xFB01,0xFB04) for r in model.calls)
    assert sum(r['op']==0xFD05 for r in model.calls)>=4*4096
    assert model.closed==[model.FD,model.FD]
    receipt=Path(actual.config['receipt_path'])
    saved=json.loads((receipt/'result.json').read_bytes())
    assert saved['stock_baseline_restored'] and saved['boot_observed'] is False
    assert saved['physical_recovery_verified'] is False
    # Transport logs represent this model, not physical SG execution.
    assert all(p.receipt()['hardware_validated'] is False for p in prepared.policies)
    if os.environ.get('LUNAR_REHEARSAL_EVIDENCE'):
        evidence=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])
        shutil.copyfile(receipt/'result.json', evidence/'actual-modeled-result.json')
        shutil.copyfile(receipt/'commands.jsonl', evidence/'actual-modeled-commands.jsonl')
        (evidence/'actual-modeled-summary.json').write_bytes(rehearsal.canonical(dict(
            hardware_access=False, mocked_sg=True, factory_source_checks_mocked=False,
            baseline_sha256=rehearsal.digest(actual.baseline), target_sha256=rehearsal.digest(actual.target),
            final_sha256=rehearsal.digest(bytes(model.flash)), command_count=len(model.calls),
            erases=erases, campaign_sha256=prepared.campaign_sha256,
            result_sha256=rehearsal.digest((receipt/'result.json').read_bytes()),
            log_sha256=rehearsal.digest((receipt/'commands.jsonl').read_bytes()))))


@pytest.mark.parametrize('fault', ['initial_mismatch', 'protected_mismatch', 'first_erase',
    'first_program', 'program_readback', 'install_close', 'install_close_interrupt',
    'result_write', 'result_sync', 'final_log'])
def test_actual_inherited_worker_failure_never_auto_restores(actual, monkeypatch, fault):
    prepared=rehearsal.prepare_campaign(actual.path)
    model=SGModel(monkeypatch, json.loads(prepared.mapping), actual.baseline)
    monkeypatch.setattr(prepared.bridge, 'discover_sg', model.discover)
    if fault in ('initial_mismatch', 'protected_mismatch'):
        model.flash[0x5000 if fault=='initial_mismatch' else 0] ^= 1
    real_ioctl=model.ioctl
    if fault in ('first_erase','first_program','program_readback'):
        def ioctl(fd, code, h):
            op=int.from_bytes(C.string_at(h.cmd,2),'big')
            if op==({'first_erase':0xFB01, 'first_program':0xFB04}.get(fault)):
                raise OSError('Mock ambiguous device interruption')
            result=real_ioctl(fd,code,h)
            if fault=='program_readback' and op==0xFB04:
                address=int.from_bytes(C.string_at(h.cmd+2,4),'big')
                model.flash[address] ^= 1
            return result
        monkeypatch.setattr(rehearsal.fcntl,'ioctl',ioctl)
    if fault in ('install_close','install_close_interrupt'):
        real_close=model.close
        def close(fd):
            if fd==model.FD:
                real_close(fd)
                error=KeyboardInterrupt if fault=='install_close_interrupt' else OSError
                raise error('Mock close failure after complete install')
            return real_close(fd)
        monkeypatch.setattr(rehearsal.os,'close',close)
    if fault=='result_write':
        def dump(value, fp, **kw):
            assert value['stock_baseline_restored'] is True
            fp.write('{"partial":')
            raise OSError('Mock final receipt write failure')
        monkeypatch.setattr(rehearsal.json,'dump',dump)
    if fault=='result_sync':
        real_sync=prepared.bridge.sync_dir
        def sync(path):
            if (Path(path)/'result.json').exists(): raise OSError('Mock final receipt fsync failure')
            return real_sync(path)
        monkeypatch.setattr(prepared.bridge,'sync_dir',sync)
    if fault=='final_log':
        real_private=prepared.bridge.private_file
        class FinalLogFault:
            def __init__(self, fp): self.fp=fp
            def __enter__(self): return self
            def __exit__(self,*args): return self.fp.__exit__(*args)
            def write(self,value):
                if '"event": "rehearsal_completed"' in value: raise OSError('Mock final log write failure')
                return self.fp.write(value)
            def flush(self): return self.fp.flush()
            def fileno(self): return self.fp.fileno()
        def private(path, mode='wb'):
            fp=real_private(path,mode)
            return FinalLogFault(fp) if Path(path).name=='commands.jsonl' else fp
        monkeypatch.setattr(prepared.bridge,'private_file',private)
    with pytest.raises((OSError,ValueError,KeyboardInterrupt)): rehearsal.run_campaign(prepared)
    receipt=Path(actual.config['receipt_path'])
    assert not (receipt/'result.json').exists()
    events=[json.loads(l) for l in (receipt/'commands.jsonl').read_text().splitlines()]
    assert events[-1]['event']=='rehearsal_stopped_ambiguous' and events[-1]['retry'] is False
    assert (receipt.parent/'.sdk-rehearsal.consumed').exists()
    if fault in ('initial_mismatch','protected_mismatch'):
        assert not any(c['op'] in (0xFB01,0xFB04) for c in model.calls)
    if fault not in ('result_write','result_sync','final_log'):
        assert len(model.opened)==1  # No automatic restore after partial/ambiguous install.
        assert not any(e.get('direction')=='restore' for e in events)
    if fault in ('install_close','install_close_interrupt'):
        assert bytes(model.flash)==actual.target
        assert model.closed==[model.FD]  # Sticky error prevents a second close/retry.
