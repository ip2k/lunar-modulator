"""Actual private SDK ELF plus synthetic NOR/provenance; never hardware."""
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_bound_sdk_diagnostic as bound
import fm1_bound_diagnostic as old
from fm1_flash_transaction import load_transaction, encoded, digest
from fm1_simulated_device import SimulatedDevice, SimulatedDisconnect
from fm1_softkey_probe import KNOWN_092
from tests.test_bound_diagnostic import ModelTransport, LOADER, rewrite_plan
from tests.test_raw_sdk_diagnostic import actual_sdk, fixed_inputs
from tests.test_raw_flash_profile import sample, repair_app, encode


class Transport(ModelTransport):
    def __init__(self, p):
        super().__init__(p['device'], p['identity'])
        self.provenance = copy.deepcopy(p['binding'])

    def binding(self):
        result = super().binding()
        result.update(self.provenance)
        result['loader_sha256'] = bound.raw.FIXED_LOADER_SHA256
        if self.binding_fault:
            self.binding_fault(result)
        return result


@pytest.fixture
def prepared(sample, actual_sdk, tmp_path):
    s = sample
    elf, app = actual_sdk
    assert digest(elf) == bound.ELF_SHA256 and digest(app) == bound.APP_SHA256
    decoded = bytearray(s['decoded']); repair_app(decoded, app)
    target = encode(decoded)
    manifest, identity = fixed_inputs(s)
    manifest.update(adapter_sha256=bound.ADAPTER_SHA256,
                    physical_recovery_verified=False, kernel_exclusivity=False)
    usb = manifest['usb_binding']
    entry = [dict(time=100, event='before', usb_path=usb['path'], usb=[dict(usb, pid='c755')]),
             dict(time=101, event='sending_identity', hex='f0 00 32 45 00 00 00 40 7f f7'),
             dict(time=102, event='identity', reply=KNOWN_092.hex(' '), decoded={'identity': 'FM-1_092'}),
             dict(time=103, event='sending_soft_key', hex='f0 22 24 35 7d f7'),
             dict(time=104, event='uboot_enumerated', elapsed=1, usb=[usb])]
    paths = {k: tmp_path / n for k, n in dict(manifest_path='manifest.json', identity_path='identity.json',
        app_path='app', elf_path='elf', campaign_path='campaign.json', entry_log_path='entry.jsonl',
        backup_log_path='commands.jsonl', loader_path='loader.bin', profile_path='profile.json').items()}
    for key, env in (('loader_path', 'LUNAR_FIXED_LOADER'), ('profile_path', 'LUNAR_FIXED_PROFILE')):
        if not os.environ.get(env):
            pytest.skip('Set ' + env + ' to actual private fixed-loader evidence')
        paths[key].write_bytes(Path(os.environ[env]).read_bytes())
    paths['entry_log_path'].write_bytes(b'\n'.join(encoded(e) for e in entry))
    manifest['entry_log_sha256'] = digest(paths['entry_log_path'].read_bytes())
    campaign = dict(schema=1, kind='fm1-fixed-loader-backup-campaign',
        adapter_sha256=bound.ADAPTER_SHA256, loader_path='/mock/historical-loader.bin',
        profile_path='/mock/historical-profile.json', profile_source_path='/mock/loader_config_profile.py',
        entry_log_path=str(paths['entry_log_path']), entry_log_sha256=manifest['entry_log_sha256'],
        usb_binding=usb, receipt_path='/mock/completed-backup')
    paths['campaign_path'].write_bytes(encoded(campaign))
    manifest['campaign_sha256'] = digest(paths['campaign_path'].read_bytes())
    start = dict(event='campaign_prepared', campaign_sha256=manifest['campaign_sha256'],
        adapter_sha256=bound.ADAPTER_SHA256, loader_sha256=bound.raw.FIXED_LOADER_SHA256,
        profile_sha256=bound.raw.FIXED_PROFILE_SHA256,
        profile_source_sha256=bound.raw.FIXED_PROFILE_SOURCE_SHA256,
        reader_sha256=bound.raw.FIXED_READER_SHA256, entry_log_sha256=manifest['entry_log_sha256'],
        usb_binding=usb, commands=8757, request_inventory_sha256=bound.raw.FIXED_REQUEST_INVENTORY_SHA256,
        kernel_exclusivity=False, physical_recovery_verified=False)
    # Only receipt envelopes are mocked here; this fixture makes no claim that
    # the backup command inventory was actually executed or physically attested.
    end = dict(event='campaign_completed', identical=True, bytes_per_dump=0x100000,
               physical_recovery_verified=False, retry=False)
    paths['backup_log_path'].write_bytes(encoded(start) + b'\n' + encoded(end))
    identity.update(flash_size=0x100000, sector_size=4096, page_size=256, jedec=0x856014,
        usb_port='mock-3-2', usb_topology='/mock/controller/3-2', baseline_sha256=digest(s['baseline']),
        entry_log_sha256=manifest['entry_log_sha256'])
    paths['manifest_path'].write_bytes(encoded(manifest))
    paths['identity_path'].write_bytes(encoded(identity))
    paths['app_path'].write_bytes(app); paths['elf_path'].write_bytes(elf)
    sectors = [a for a in range(0, 0x100000, 4096) if s['baseline'][a:a+4096] != target[a:a+4096]]
    ranges = [[address, address+4096] for address in sectors]
    directory = tmp_path / 'transaction'
    bound.prepare_transaction(directory, s['baseline'], s['baseline'], target, identity, ranges)
    device_path = tmp_path / 'nor'
    device = SimulatedDevice(s['baseline'], path=device_path, writable_ranges=ranges,
        protected_ranges=((0, 0x4000), (bound.raw.CFG_TOOL_OFFSET, 0x100000)),
        simulator_loader_sha256=hashlib.sha256(LOADER).hexdigest())
    binding = dict(backup_manifest_sha256=digest(paths['manifest_path'].read_bytes()),
        campaign_sha256=manifest['campaign_sha256'], adapter_sha256=bound.ADAPTER_SHA256,
        entry_log_sha256=manifest['entry_log_sha256'], usb_binding=usb,
        request_inventory_sha256=bound.raw.FIXED_REQUEST_INVENTORY_SHA256)
    return dict(sample=dict(s, target=target), directory=directory, device=device, device_path=device_path,
                arguments=dict(paths, reference=s['reference']), identity=identity, binding=binding,
                manifest=manifest, campaign=campaign, entry=entry)


def policy(p, direction='install', **changes):
    return bound.load_policy(p['directory'], direction=direction, baseline_profile='fixed-loader',
                             **dict(p['arguments'], **changes))


def session(p, direction='install'):
    t = Transport(p)
    return policy(p, direction).bind(t), t


def test_profile_and_constructor_require_validation_without_files(tmp_path):
    with pytest.raises(ValueError, match='fixed-loader'):
        bound.load_policy(tmp_path, direction='install', baseline_profile='recorded-original-loader',
            manifest_path=None, identity_path=None, reference=None, app_path=None, elf_path=None,
            campaign_path=None, entry_log_path=None, backup_log_path=None, loader_path=None, profile_path=None)
    with pytest.raises(ValueError, match='validated_sdk_policy'):
        bound.BoundSDKDiagnosticSession(None, None)


def test_failed_file_wrapper_closes_raw_descriptor(tmp_path, monkeypatch):
    path = tmp_path / 'evidence'; path.write_bytes(b'fixture')
    opened = []
    def fail(fd, mode):
        opened.append(fd)
        raise OSError('injected wrapper failure')
    monkeypatch.setattr(bound.os, 'fdopen', fail)
    with pytest.raises(OSError, match='wrapper'):
        bound._read(path)
    with pytest.raises(OSError):
        os.fstat(opened[0])


def test_install_restore_directory_last_and_protected_bytes(prepared):
    p = prepared
    for direction in ('install', 'restore'):
        s, t = session(p, direction)
        receipt = s.run()
        expected = p['sample']['target' if direction == 'install' else 'baseline']
        assert p['device'].flash == expected and t.closed
        mutations = [(int.from_bytes(c[:2], 'big'), int.from_bytes(c[2:6], 'big'))
                     for c, _, _ in t.calls if int.from_bytes(c[:2], 'big') in (0xFB01, 0xFB04)]
        sectors = [a // 4096 * 4096 for _, a in mutations]
        first_directory = sectors.index(0x4000)
        assert all(a != 0x4000 for a in sectors[:first_directory])
        assert all(a == 0x4000 for a in sectors[first_directory:])
        assert p['device'].flash[:0x4000] == p['sample']['baseline'][:0x4000]
        assert p['device'].flash[bound.raw.CFG_TOOL_OFFSET:] == p['sample']['baseline'][bound.raw.CFG_TOOL_OFFSET:]
        assert receipt['sector_order'][-1] == 0x4000 and receipt['protocol_mock_only']
        assert not receipt['hardware_validated'] and not receipt['physical_loader_recovery_binding_proven']
        with pytest.raises(OSError, match='stopped'):
            s.online()
    complete, t = session(p, 'restore')
    assert complete.run()['sectors_written'] == 0
    assert not any(int.from_bytes(c[:2], 'big') in (0xFB01, 0xFB04) for c, _, _ in t.calls)


@pytest.mark.parametrize('kind', ['app', 'elf', 'loader', 'profile', 'adapter', 'inventory', 'source', 'entry', 'campaign',
                                 'log_stopped', 'log_missing', 'scope', 'order', 'ranges', 'identity'])
def test_rejects_changed_candidate_provenance_or_seal_before_transport(prepared, kind, monkeypatch):
    p = prepared
    if kind in ('app', 'elf', 'loader', 'profile'):
        path = p['arguments'][kind + '_path']; data = path.read_bytes()
        path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    elif kind in ('adapter', 'inventory'):
        m = dict(p['manifest']); m[kind + '_sha256' if kind == 'adapter' else 'request_inventory_sha256'] = 'a'*64
        p['arguments']['manifest_path'].write_bytes(encoded(m))
    elif kind == 'source':
        monkeypatch.setattr(bound, 'ADAPTER_SHA256', 'a'*64)
    elif kind in ('entry', 'campaign'):
        p['arguments'][kind + ('_log_path' if kind == 'entry' else '_path')].write_bytes(b'{}')
    elif kind.startswith('log_'):
        path = p['arguments']['backup_log_path']
        path.write_bytes(path.read_bytes() + b'\n' + encoded({'event': 'campaign_stopped_ambiguous'})
                         if kind == 'log_stopped' else b'{}')
    elif kind == 'scope':
        rewrite_plan(p, lambda plan: plan.update(scope=old.SCOPE))
    elif kind == 'order':
        rewrite_plan(p, lambda plan: plan.update(commit_sector=None, sector_order=sorted(plan['sector_order'])))
    elif kind == 'ranges':
        rewrite_plan(p, lambda plan: plan.update(writable_ranges=[[0x4000, 0x23000]]))
    else:
        p['arguments']['identity_path'].write_bytes(encoded(dict(p['identity'], unit_id='other')))
    with pytest.raises((ValueError, KeyError)):
        policy(p)


def test_old_policy_still_rejects_sdk_fixed_loader_and_tokens(prepared):
    p = prepared
    with pytest.raises(ValueError):
        old.load_policy(p['directory'], direction='install', **{k: v for k, v in p['arguments'].items()
                        if k in ('manifest_path', 'identity_path', 'reference', 'app_path', 'elf_path')})
    pol = policy(p)
    with pytest.raises(ValueError, match='actual-file'):
        replace(pol, _authorization=object()).bind(Transport(p))
    with pytest.raises(ValueError, match='validated_policy'):
        old.BoundDiagnosticSession(pol, Transport(p))


@pytest.mark.parametrize('field,value', [('direction', 'restore'), ('sectors', (0,)),
                                      ('binding_bytes', b'{}'), ('receipt_bytes', b'{}')])
def test_copied_policy_cannot_reuse_factory_authorization(prepared, field, value):
    pol = policy(prepared)
    copied = replace(pol, **{field: value})
    with pytest.raises(ValueError, match='actual-file'):
        copied.check_files()
    t = Transport(prepared)
    with pytest.raises(ValueError, match='actual-file'):
        copied.bind(t)
    with pytest.raises(ValueError, match='validated_sdk_policy'):
        bound.BoundSDKDiagnosticSession(copied, t, pol._authorization)
    assert not t.calls


@pytest.mark.parametrize('name', ['plan.json', 'backupA.bin', 'backupB.bin', 'target.bin', 'journal.json'])
def test_transaction_artifact_corruption_rejected_at_bind(prepared, name):
    p = prepared; pol = policy(p)
    path = p['directory'] / name; data = path.read_bytes()
    path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    t = Transport(p)
    with pytest.raises((ValueError, KeyError)):
        pol.bind(t)
    assert not t.calls


@pytest.mark.parametrize('field', ['loader_sha256', 'phase', 'session_id', 'identity', 'adapter_sha256',
    'backup_manifest_sha256', 'campaign_sha256', 'entry_log_sha256', 'request_inventory_sha256', 'usb_binding'])
def test_wrong_binding_fails_without_exchange(prepared, field):
    p = prepared; t = Transport(p)
    t.binding_fault = lambda b: b.update({field: None})
    with pytest.raises(ValueError, match='binding'):
        policy(p).bind(t)
    assert t.closed and not t.calls


@pytest.mark.parametrize('path', ['manifest_path', 'identity_path', 'app_path', 'elf_path',
                                 'campaign_path', 'entry_log_path', 'backup_log_path', 'loader_path',
                                 'profile_path', 'reference'])
def test_supporting_files_frozen_at_bind_and_mutation(prepared, path):
    p = prepared; pol = policy(p)
    receipt = pol.receipt(); receipt['required_injected_binding']['adapter_sha256'] = 'fake'
    assert pol.receipt()['required_injected_binding']['adapter_sha256'] == bound.ADAPTER_SHA256
    changed = (p['arguments']['reference'] / 'files/cfg_tool.bin' if path == 'reference' else p['arguments'][path])
    before = changed.read_bytes(); changed.write_bytes(before + b' ')
    t = Transport(p)
    with pytest.raises(ValueError, match='changed'):
        pol.bind(t)
    assert not t.calls  # No transport accepted.
    changed.write_bytes(before)
    s = pol.bind(t)
    def alter(event, **fields):
        if event == 'durable_intent':
            changed.write_bytes(before + b' ')
    with pytest.raises(ValueError, match='changed'):
        s.run(checkpoint=alter)
    assert t.closed and not any(int.from_bytes(c[:2], 'big') in (0xFB01, 0xFB04) for c, _, _ in t.calls)


def test_arbitrary_commands_pages_and_missing_intents_fail(prepared):
    p = prepared; s, t = session(p)
    for op in (0x12, 0xFB06, 0xFB08, 0xFC12, 0xA1, 0x1234):
        with pytest.raises(ValueError):
            s.cmd(op)
    for op in (0xFB01, 0xFB04):
        with pytest.raises(ValueError):
            s.cmd(op, address=0x5000, payload=p['sample']['target'][0x5000:0x5100] if op == 0xFB04 else b'')
    assert not t.calls
    def probe(event, **fields):
        if event != 'durable_intent':
            return
        address = fields['address']
        desired = p['sample']['target'][address:address+256]
        wrong = bytes([desired[0] ^ 1]) + desired[1:]
        for payload in (wrong, desired[:-1]):
            with pytest.raises(ValueError):
                s.cmd(0xFB04, address=address, payload=payload)
        with pytest.raises(ValueError):
            s.cmd(0xFB01, address=0)
        with pytest.raises(ValueError):
            s.cmd(0xFB04, address=address+1, payload=p['sample']['target'][address:address+256])
        if fields['operation'] == 'program':
            cdb, data, size = s.build_request(0xFB04, address=address, payload=desired)
            with pytest.raises(ValueError, match='Malformed'):
                s.execute(cdb[:9] + bytes([cdb[9] ^ 1]) + cdb[10:], data, size)
            with pytest.raises(ValueError, match='intent'):
                s.cmd(0xFB01, address=address // 4096 * 4096)
    s.run(checkpoint=probe)


@pytest.mark.parametrize('kind', ['short', 'pre_binding', 'post_binding', 'reconnect'])
def test_ambiguous_exchange_latches_without_retry(prepared, kind):
    p = prepared; s, t = session(p)
    if kind == 'short':
        t.reply_fault = lambda result, cdb: result[:-1]
    elif kind == 'pre_binding':
        t.session_id += '-changed'
    elif kind == 'post_binding':
        def changed(result, cdb):
            t.session_id += '-changed'
            return result
        t.reply_fault = changed
    else:
        p['device'].generation += 1
    with pytest.raises((ValueError, OSError, SimulatedDisconnect)):
        s.online()
    assert t.closed
    count = len(t.calls)
    with pytest.raises(OSError, match='stopped'):
        s.online()
    assert len(t.calls) == count


@pytest.mark.parametrize('operation,kind,direction', [('program', 'torn', 'install'),
    ('program', 'ack_loss', 'restore'), ('erase', 'torn', 'restore'), ('erase', 'ack_loss', 'install')])
def test_interrupted_install_restore_resume_from_actual_nor(prepared, operation, kind, direction):
    p = prepared
    if direction == 'restore':
        session(p)[0].run()
    s, t = session(p, direction)
    p['device'].inject_failure(operation=operation, kind=kind, after_bytes=127 if operation == 'program' else 1)
    with pytest.raises(SimulatedDisconnect):
        s.run()
    assert t.closed and load_transaction(p['directory'])[1]['state'] == 'recovery_required'
    p['device'] = SimulatedDevice(path=p['device_path'])
    fresh, _ = session(p, direction)
    expected = p['sample']['target' if direction == 'install' else 'baseline']
    assert fresh.run()['verified_sha256'] == digest(expected) and p['device'].flash == expected


@pytest.mark.parametrize('direction', ['install', 'restore'])
def test_directory_last_host_crash_preserves_durable_intent(prepared, direction):
    class HostCrash(BaseException):
        pass
    p = prepared
    if direction == 'restore':
        session(p)[0].run()
    s, t = session(p, direction)
    seen = []
    def crash(event, **fields):
        if event == 'durable_intent':
            seen.append(fields['address'])
            if fields['address'] == 0x4000:
                raise HostCrash()
    with pytest.raises(HostCrash):
        s.run(checkpoint=crash)
    assert seen[-1] == 0x4000 and seen[0] != 0x4000 and t.closed
    journal = load_transaction(p['directory'])[1]
    assert journal['state'] == 'recovery_required' and journal['intent']['address'] == 0x4000
    p['device'] = SimulatedDevice(path=p['device_path'])
    assert session(p, direction)[0].run()['sector_order'][-1] == 0x4000


@pytest.mark.parametrize('when', ['initial', 'readback'])
def test_corrupted_actual_flash_never_trusts_progress(prepared, when):
    p = prepared; s, t = session(p)
    occurrence = 1 if when == 'initial' else 4096 + 16 + 16 + 1
    p['device'].inject_failure(operation='read', kind='corrupt_read', occurrence=occurrence)
    with pytest.raises(ValueError, match='outside' if when == 'initial' else 'Program readback'):
        s.run()
    assert t.closed
    if when == 'initial':
        assert not any(int.from_bytes(c[:2], 'big') in (0xFB01, 0xFB04) for c, _, _ in t.calls)
    else:
        assert load_transaction(p['directory'])[1]['state'] == 'recovery_required'
        assert session(p)[0].run()['verified_sha256'] == digest(p['sample']['target'])
