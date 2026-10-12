"""MIT. Actual-file one-shot faults, then injected NOR recovery; no hardware.

The frozen 26f factory/SG worker supplies the failed attempt. Recovery uses the
exact sealed SDK policy through an explicitly injected loader/connection oracle,
NOT a new production partial-NOR admission or an emulated CPU/SPL boot.
"""
import copy
import ctypes
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil

import pytest

import fm1_bound_sdk_diagnostic as sdk
from fm1_flash_transaction import check_outside, digest, encoded, load_transaction
from fm1_simulated_device import SimulatedDevice
from fm1_uboot_read import SGHeader
from test_bound_diagnostic import LOADER, ModelTransport
from test_diagnostic_stage_resume import actual_tree as original_actual_tree
from test_stopped_choice_restore_actual import successor_factory
from test_returned_rom_actual import ReturnedSGModel
from test_sdk_rehearsal import wire


@pytest.fixture
def actual_tree():
    # A fresh disposable exact-path tree per case; never reset a physical or
    # shared fixture. Strict env guards in the original fixture apply first.
    value = original_actual_tree.__wrapped__()
    try:
        yield value
    finally:
        assert os.environ.get('LUNAR_STAGE_RESUME_DISPOSABLE') == '1'
        shutil.rmtree('/home/claude/fm1-diagnostic-boot-20261011')
        shutil.rmtree('/home/claude/fm1-fixed-backups-20261011')


class FaultNOR(ReturnedSGModel):
    """Real SG ABI shape and NOR AND programming; deterministic fault oracle."""
    def __init__(self, *args):
        super().__init__(*args)
        self.fault = None
        self.triggered = False

    def ioctl(self, fd, request, raw):
        h = SGHeader.from_buffer(raw)
        cdb = ctypes.string_at(h.cmd, h.cmd_len)
        op = int.from_bytes(cdb[:2], 'big')
        address = int.from_bytes(cdb[2:6], 'big')
        wanted = 0x4000 if self.fault == 'directory-erase-prefix' else 0x5000
        program = self.fault and self.fault.startswith('program-')
        trigger = (self.fault != 'intent' and not self.triggered
                   and address == wanted and op == (0xFB04 if program else 0xFB01))
        old = bytes(self.flash[address:address + (256 if program else 4096)])
        answer = super().ioctl(fd, request, raw)
        if not trigger:
            return answer
        self.triggered = True
        if self.fault in ('erase-prefix', 'directory-erase-prefix'):
            self.flash[address + 127:address + 4096] = old[127:]
        elif self.fault in ('program-prefix-13', 'program-prefix-127'):
            count = int(self.fault.rsplit('-', 1)[1])
            self.flash[address + count:address + 256] = old[count:]
        elif self.fault == 'program-bit-corruption':
            # Additional 1->0 transition despite successful SG status; the
            # genuine sector readback, not the acknowledgment, must detect it.
            offset = next(i for i, b in enumerate(self.flash[address:address + 256]) if b)
            b = self.flash[address + offset]
            self.flash[address + offset] = b & (b - 1)
            return answer
        raise OSError('modeled NOR interruption or acknowledgment loss')


@pytest.fixture
def restore_attempt(successor_factory, monkeypatch):
    backup, restore, prepared, cp, proof, stage = successor_factory
    mapping = json.loads(prepared.snapshot)['sg_binding']
    model = FaultNOR(monkeypatch, mapping, prepared.policies[0].target)
    monkeypatch.setattr(prepared.bridge, 'discover_sg', model.discover)
    backup.run_campaign(prepared)
    receipt = Path(json.loads(prepared.campaign)['receipt_path'])
    candidates = {p for p, raw, _ in proof.evidence
                  if digest(raw) == proof.original_rehearsal_campaign_sha256}
    assert len(candidates) == 1
    campaign = dict(schema=1, kind="fm1-stopped-choice-stock-restore-only",
        adapter_sha256=digest(Path(restore.__file__).read_bytes()),
        returned_backup_campaign_path=str(cp), returned_backup_campaign_sha256=digest(cp.read_bytes()),
        returned_backup_manifest_sha256=digest((receipt/'manifest.json').read_bytes()),
        returned_backup_commands_sha256=digest((receipt/'commands.jsonl').read_bytes()), returned_backup_exit_status=0,
        original_rehearsal_campaign_path=str(next(iter(candidates))),
        original_rehearsal_campaign_sha256=proof.original_rehearsal_campaign_sha256,
        install_journal_sha256=proof.install_journal_sha256,
        active_session_state="stopped-choice-fixed-loader-dual-target-backup-no-later-commands", receipt_path=str(receipt/'faulted-stock-restore'))
    rc = stage/'faulted-restore.json'; rc.write_bytes(restore.canonical(campaign))
    accepted = restore.prepare_campaign(rc)
    return restore, accepted, rc, model, receipt


class RecoveryOracle(ModelTransport):
    """Explicit simulated ROM/loader entry with injected historical provenance."""
    def __init__(self, device, policy):
        super().__init__(device, json.loads(policy.plan_bytes)['identity'])
        self.provenance = json.loads(policy.binding_bytes)

    def binding(self):
        result = super().binding()
        result.update(copy.deepcopy(self.provenance))
        result['loader_sha256'] = sdk.raw.FIXED_LOADER_SHA256
        return result


def stop_attempt(attempt, monkeypatch, fault):
    restore, accepted, rc, model, parent = attempt
    policy = accepted.policies[0].original
    before = len(model.calls); model.fault = fault
    if fault == 'intent':
        original_sync = accepted.bridge.sync_dir
        def sync(path):
            original_sync(path)
            log = Path(json.loads(accepted.config)['receipt_path'])/'commands.jsonl'
            if log.exists():
                with log.open('rb') as fp:
                    fp.seek(0, 2); size = fp.tell(); fp.seek(max(0, size - 4096))
                    tail = fp.read().splitlines()
                if tail and json.loads(tail[-1]).get('event') == 'durable_intent':
                    raise KeyboardInterrupt('after durable intent, before ioctl')
        monkeypatch.setattr(accepted.bridge, 'sync_dir', sync)
    with pytest.raises((OSError, ValueError, KeyboardInterrupt)):
        restore.run_campaign(accepted)
    if fault != 'intent': assert model.triggered
    else: assert not any(c['op'] in (0xFB01, 0xFB04) for c in model.calls[before:])
    _, journal, _, _ = load_transaction(policy.directory)
    assert journal['state'] == 'recovery_required' and journal['intent'] is not None
    assert journal['direction'] == 'restore'
    initial = model.calls[before + 1:before + 4097]
    assert len(initial) == 4096 and all(c['op'] == 0xFD05 for c in initial)
    assert [c['address'] for c in initial] == list(range(0, 1048576, 256))
    check_outside(bytes(model.flash), policy.baseline, json.loads(policy.plan_bytes)['writable_ranges'])
    rr = Path(json.loads(accepted.config)['receipt_path'])
    assert not (rr/'result.json').exists()
    assert (parent/'.stopped-choice-stock-restore.consumed').exists()
    frozen = {p: p.read_bytes() for p in rr.iterdir() if p.is_file()}
    frozen[parent/'.stopped-choice-stock-restore.consumed'] = (parent/'.stopped-choice-stock-restore.consumed').read_bytes()
    calls = len(model.calls)
    with pytest.raises((ValueError, OSError)): restore.run_campaign(accepted)
    with pytest.raises((ValueError, OSError)): restore.prepare_campaign(rc)
    assert len(model.calls) == calls
    # No successful completed-helper proof may be manufactured for the failed
    # attempt even when supplied hashes accurately describe its current files.
    with pytest.raises((ValueError, OSError)):
        restore.validate_completed_restore(rc, campaign_sha256=digest(rc.read_bytes()),
            commands_sha256=digest((rr/'commands.jsonl').read_bytes()), result_sha256='0'*64,
            journal_sha256=digest((policy.directory/'journal.json').read_bytes()),
            freeze=lambda p, expected=None, limit=2*1048576: Path(p).read_bytes())
    return policy, bytes(model.flash), frozen, journal


def acquire(device, policy, directory, fault=None):
    transport = RecoveryOracle(device, policy)
    dumps = []
    try:
        for iteration in range(2):
            data = b''.join(transport.exchange(*wire(0xFD05, a)) for a in range(0, 1048576, 256))
            if fault == 'second-dump-drift' and iteration == 1:
                data = data[:0x5000] + bytes([data[0x5000] ^ 1]) + data[0x5001:]
            (directory/('fresh-dump-' + str(iteration) + '.bin')).write_bytes(data)
            dumps.append(data)
        assert len(transport.calls) == 8192
        if dumps[0] != dumps[1]: raise ValueError('Fresh acquisitions disagree; no mutation')
        check_outside(dumps[0], policy.baseline, json.loads(policy.plan_bytes)['writable_ranges'])
        assert not any(int.from_bytes(c[0][:2], 'big') in (0xFB01, 0xFB04) for c in transport.calls)
        return dumps[0]
    finally:
        transport.close()


FAULTS = ['intent', 'erase-prefix', 'erase-ack-loss', 'program-prefix-13',
          'program-prefix-127', 'program-ack-loss', 'program-bit-corruption', 'directory-erase-prefix']


@pytest.mark.parametrize('fault', FAULTS)
def test_actual_one_shot_fault_then_fresh_acquisition_and_sealed_restore(restore_attempt, monkeypatch, tmp_path, fault):
    policy, damaged, frozen, failed = stop_attempt(restore_attempt, monkeypatch, fault)
    plan = json.loads(policy.plan_bytes)
    ranges = plan['writable_ranges']
    out = Path(os.environ['LUNAR_ADMISSION_EVIDENCE'])/('case-' + fault)
    out.mkdir(mode=0o700)
    failed_dir = out/'failed-one-shot'; failed_dir.mkdir(mode=0o700)
    for path, raw in frozen.items(): (failed_dir/path.name).write_bytes(raw)
    (failed_dir/'journal-at-interruption.json').write_bytes((policy.directory/'journal.json').read_bytes())
    (out/'damaged-nor.bin').write_bytes(damaged)
    (out/'sealed-plan.json').write_bytes(policy.plan_bytes)
    device_path = tmp_path/'persistent-nor'
    device = SimulatedDevice(damaged, path=device_path, writable_ranges=ranges,
        protected_ranges=((0, 0x4000), (0x22000, 1048576)),
        simulator_loader_sha256=hashlib.sha256(LOADER).hexdigest())
    assert acquire(device, policy, out) == damaged
    # Explicit modeled reconnect, not proof that CPU/SPL can re-enter on the
    # hardware. Persistent NOR bytes survive; stale session generation does not.
    device = SimulatedDevice(path=device_path)
    transport = RecoveryOracle(device, policy)
    result = policy.bind(transport).run()
    assert transport.closed and device.flash == policy.baseline
    assert result['verified_sha256'] == digest(policy.baseline)
    assert digest(device.flash) == '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
    erases = [int.from_bytes(c[2:6], 'big')
              for c, _, _ in transport.calls if c[:2] == b'\xfb\x01']
    assert erases == sorted(a for a in erases if a != 0x4000) + ([0x4000] if 0x4000 in erases else [])
    assert result['sector_order'] == list(range(0x5000, 0x22000, 4096)) + [0x4000]
    assert all(p.read_bytes() == raw for p, raw in frozen.items())
    check_outside(device.flash, policy.baseline, ranges)
    (out/'final-journal.json').write_bytes((policy.directory/'journal.json').read_bytes())
    (out/('fault-' + fault + '.json')).write_bytes(encoded(dict(
        fault=fault, failed_intent=failed['intent'], damaged_sha256=digest(damaged),
        fresh_dump_sha256=digest((out/'fresh-dump-0.bin').read_bytes()),
        final_stock_sha256=digest(device.flash), recovery_commands=len(transport.calls),
        preserved_failed_receipt={str(p): digest(raw) for p, raw in frozen.items()},
        acquisition_commands=8192, production_partial_nor_admission=False,
        cpu_spl_emulated=False, physical_recovery_verified=False, hardware_access=False)))


@pytest.mark.parametrize('fault', ['second-dump-drift', 'protected-spl', 'protected-tail'])
def test_fresh_acquisition_rejects_inconsistency_and_protected_damage(restore_attempt, monkeypatch, tmp_path, fault):
    policy, damaged, frozen, _ = stop_attempt(restore_attempt, monkeypatch, 'erase-prefix')
    if fault.startswith('protected-'):
        address = 0 if fault == 'protected-spl' else 0x22000
        raw = bytearray(damaged); raw[address] ^= 1; damaged = bytes(raw)
    device = SimulatedDevice(damaged, writable_ranges=json.loads(policy.plan_bytes)['writable_ranges'],
        protected_ranges=((0, 0x4000), (0x22000, 1048576)),
        simulator_loader_sha256=hashlib.sha256(LOADER).hexdigest())
    with pytest.raises(ValueError): acquire(device, policy, tmp_path, fault)
    assert device.flash == damaged and all(p.read_bytes() == raw for p, raw in frozen.items())
    assert not any(e.get('operation') in ('erase', 'program') for e in device.events)


@pytest.mark.parametrize('fault', ['plan', 'target', 'baseline', 'copied-policy', 'foreign-binding'])
def test_sealed_recovery_policy_rejects_unreviewed_artifacts_or_authority(restore_attempt, tmp_path, fault):
    _, accepted, _, _, _ = restore_attempt
    policy = accepted.policies[0].original
    device = SimulatedDevice(policy.target, writable_ranges=json.loads(policy.plan_bytes)['writable_ranges'],
        simulator_loader_sha256=hashlib.sha256(LOADER).hexdigest())
    transport = RecoveryOracle(device, policy)
    if fault in ('plan', 'target', 'baseline'):
        name = {'plan': 'plan.json', 'target': 'target.bin', 'baseline': 'backupA.bin'}[fault]
        path = policy.directory/name; old = path.read_bytes(); path.write_bytes(old + b'\x00')
    elif fault == 'copied-policy': policy = replace(policy)
    else: transport.provenance['backup_manifest_sha256'] = '0'*64
    with pytest.raises((ValueError, OSError, json.JSONDecodeError)): policy.bind(transport)
    assert not transport.calls and device.flash == accepted.policies[0].target
