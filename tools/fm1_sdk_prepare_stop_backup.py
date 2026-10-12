#!/usr/bin/env python3
"""MIT. Distinct closed loader backup after canonical native-preparation-stop evidence.

No reset, NOR write, soft-key, RAM retry or arbitrary opcode/address.
Derived from the reviewed trace-admitted backup; its five-read proof is not used. Private
source adaptation reuses the reviewed inventory/SG mechanics, never the old
factory/worker/registry. Python/interpreter/ancestor directories are trusted.
ROM framing credit: kagaimiq/jl-uboot-tool via the pinned reviewed reader.
"""
import argparse
import ctypes as C
from dataclasses import dataclass
import fcntl
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import types
from weakref import WeakSet

BASE_SOURCE_SHA = 'afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be'
PROOF_SOURCE_SHA = None  # Closed until genuine preparation-stop composition is verified.
REHEARSAL_SHA = 'f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4'
TARGET_SHA = '5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d'
KIND = 'fm1-sdk-preparation-stop-fixed-loader-target-backup'
STATE = 'same-returned-rom-after-file-only-preparation-stop-no-loader-upload-no-later-commands'
MAX_WITNESS_AGE = 120
_AUTHORIZED = WeakSet()

def digest(data): return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def finite_time(value):
    return type(value) in (int, float) and math.isfinite(value)


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute(): raise ValueError('Absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try: fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd); raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode): raise ValueError('Regular evidence required')
        raw = fp.read(limit + 1)
    if len(raw) > limit: raise ValueError('Evidence exceeds bound')
    return raw


def load_source(path, expected, name):
    raw = read_file(path)
    if digest(raw) != expected: raise ValueError('Reviewed source differs')
    module = types.ModuleType(name); module.__file__ = str(path); sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__); return module


def marker_path(parent, proof):
    # One loader upload per original boot/preparation-stop lineage, even if a caller changes
    # admission JSON whitespace or its receipt name. Never consume the read again.
    boot_sha = proof.lineage.read_binding()['boot_campaign_sha256']
    if (not isinstance(boot_sha, str) or len(boot_sha) != 64 or
            any(ch not in '0123456789abcdef' for ch in boot_sha)):
        raise ValueError('Exact original boot campaign pin required')
    return parent / ('.sdk-preparation-stop-loader-' + boot_sha + '.consumed')


def validate_connection_witness(witness, snapshot, snapshot_sha256, evaluated_at):
    keys = {'schema', 'kind', 'observed_at', 'usb_binding', 'sg_binding',
            'original_rom_snapshot_sha256', 'preparation_stop_sha256', 'quiet_state'}
    if (set(witness) != keys or type(witness['schema']) is not int or witness['schema'] != 1 or
            witness['kind'] != 'fm1-passive-sdk-preparation-stop-backup-connection' or
            witness['quiet_state'] != STATE or not isinstance(snapshot_sha256, str) or len(snapshot_sha256) != 64 or
            any(ch not in '0123456789abcdef' for ch in snapshot_sha256) or
            witness['original_rom_snapshot_sha256'] != snapshot_sha256 or
            not finite_time(witness['observed_at']) or not finite_time(evaluated_at) or
            not snapshot['observed_at'] <= witness['observed_at'] <= evaluated_at or
            not 0 <= evaluated_at - witness['observed_at'] <= MAX_WITNESS_AGE or
            canonical(witness['usb_binding']) != canonical(snapshot['usb_binding']) or
            canonical(witness['sg_binding']) != canonical(snapshot['sg_binding'])):
        raise ValueError('Separate fresh unchanged ROM connection witness required')


@dataclass(frozen=True, eq=False)
class Prepared:
    campaign: bytes
    campaign_sha256: str
    snapshot: bytes
    evidence: tuple
    policies: tuple
    bridge: object
    header_type: type
    operations: tuple
    request_inventory_sha256: str
    original_manifest_sha256: str
    parent: Path
    provenance: object
    connection_witness: bytes
    native: object

    def check(self):
        require_prepared(self, check=False)
        check_evidence(self)


def require_prepared(prepared, *, check=True):
    if type(prepared) is not Prepared or prepared not in _AUTHORIZED:
        raise ValueError('Exact distinct prepared backup instance required')
    if check:
        prepared.check()


def check_evidence(prepared):
    for path, data, limit in prepared.evidence:
        if read_file(path, limit) != data:
            raise ValueError('Frozen trace-target backup evidence changed')
    for policy in prepared.policies:
        policy.check_files()
    prepared.provenance.check()
    if prepared.request_inventory_sha256 != prepared.bridge.inventory_digest(prepared.operations):
        raise ValueError('Frozen exact backup inventory changed')


def _validate_campaign(path, *, evaluated_at, completed=False, install_journal_path=None):
    if PROOF_SOURCE_SHA is None:
        raise ValueError('Closed: verified preparation-stop composition required')
    if (not finite_time(evaluated_at) or evaluated_at > time.time() or
            (install_journal_path is not None and not completed)):
        raise ValueError('Historical journal cannot grant fresh backup authority')
    evidence = []
    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path); raw = read_file(path, limit)
        if expected is not None and digest(raw) != expected:
            raise ValueError('Pinned trace-target backup input differs')
        evidence.append((path, raw, limit)); return raw
    raw = freeze(Path(path).absolute(), limit=65536); c = json.loads(raw)
    keys = {'schema', 'kind', 'adapter_sha256', 'preparation_stop_path',
            'preparation_stop_sha256', 'connection_witness_path', 'connection_witness_sha256',
            'loader_path', 'profile_path', 'profile_source_path', 'active_session_state', 'receipt_path'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != KIND or c['active_session_state'] != STATE):
        raise ValueError('Exact distinct trace-target backup envelope required')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    base_path = root / 'fm1_returned_rom_backup.py'; freeze(base_path, BASE_SOURCE_SHA)
    base = load_source(base_path, BASE_SOURCE_SHA, '_preparation_stop_backup_native')
    proof_path = root / 'fm1_sdk_trace_prepare_stop.py'; freeze(proof_path, PROOF_SOURCE_SHA)
    proof_module = importlib.import_module('fm1_sdk_trace_prepare_stop')
    if (Path(proof_module.__file__).absolute() != proof_path or
            digest(read_file(proof_path)) != PROOF_SOURCE_SHA):
        raise ValueError('Exact canonical preparation-stop evidence module required')
    freeze(c['preparation_stop_path'], c['preparation_stop_sha256'], 65536)
    stop_raw = read_file(c['preparation_stop_path'], 65536)
    stop = json.loads(stop_raw)
    if (set(stop) != {'schema', 'kind', 'boot_lineage_path', 'boot_lineage_sha256', 'chain_path'}
            or type(stop['schema']) is not int or stop['schema'] != 1
            or stop['kind'] != 'fm1-native-preparation-stop-evidence'):
        raise ValueError('Exact distinct preparation-stop envelope required')
    freeze(stop['boot_lineage_path'], stop['boot_lineage_sha256'], 65536)
    proof = proof_module.validate_preparation_stop(stop['boot_lineage_path'], stop['chain_path'],
        install_journal_path=install_journal_path)
    if type(proof) is not proof_module.PreparationStopProof:
        raise ValueError('Canonical registered preparation-stop proof required')
    proof.check()
    # Include the canonical install/boot evidence in callers' frozen inventory,
    # not merely the read receipt. Restore later excludes only the live journal.
    for p, b, n in (proof.evidence + proof.lineage.evidence +
                    proof.lineage.installed.evidence):
        freeze(p, digest(b), n)
    policies = proof.lineage.installed.policies
    for policy in policies:
        for p, b, n in policy.evidence:
            freeze(p, digest(b), n)
        for name in ('plan.json', 'backupA.bin', 'backupB.bin', 'target.bin'):
            freeze(policy.directory / name)
        policy.check_files()
    snapshot = json.loads(proof.snapshot)
    witness_raw = freeze(c['connection_witness_path'], c['connection_witness_sha256'], 65536)
    witness = json.loads(witness_raw)
    validate_connection_witness(witness, snapshot, proof.snapshot_sha256, evaluated_at)
    if (witness['preparation_stop_sha256'] != c['preparation_stop_sha256'] or
            witness['observed_at'] < proof.terminal_at):
        raise ValueError('Current witness must follow the exact file-only preparation stop')
    rehearsal_path = root / 'fm1_sdk_rehearsal.py'; freeze(rehearsal_path, REHEARSAL_SHA)
    rehearsal = load_source(rehearsal_path, REHEARSAL_SHA, '_preparation_stop_backup_dependencies')
    for name, pin in rehearsal.SOURCES.items():
        freeze(root / name, pin)
    modules = rehearsal.imports(); bridge = modules['fm1_fixed_loader_backup']
    loader = freeze(c['loader_path'], bridge.LOADER_SHA)
    profile = json.loads(freeze(c['profile_path'], bridge.PROFILE_SHA))
    freeze(c['profile_source_path'], bridge.PROFILE_SOURCE_SHA)
    if len(loader) != bridge.LOADER_SIZE:
        raise ValueError('Exact fixed loader size required')
    operations = base.inventory(bridge, modules['fm1_uboot_read'], loader, profile)
    if len(operations) != 8757:
        raise ValueError('Exact reviewed dual-read command inventory required')
    parent = Path(proof.lineage.parent); destination = Path(c['receipt_path'])
    marker = marker_path(parent, proof)
    if (not destination.is_absolute() or destination.parent != parent or
            not stat.S_ISDIR(parent.lstat().st_mode) or stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('Direct private original parent required')
    if not completed:
        if os.path.lexists(destination) or os.path.lexists(marker):
            raise ValueError('Distinct backup already consumed or partially prepared')
    elif (not stat.S_ISDIR(destination.lstat().st_mode) or
            stat.S_IMODE(destination.stat().st_mode) != 0o700 or
            freeze(marker, limit=256) != digest(raw).encode('ascii')):
        raise ValueError('Exact distinct consumed backup evidence required')
    # Only this private module instance is adapted. Original afeefe source and
    # registry remain unchanged. __file__ rebinding makes its source drift check
    # refer to this exact new adapter; binding below also pins the original body.
    base.Prepared = Prepared; base.require_prepared = require_prepared
    base.validate_connection_witness = validate_connection_witness
    base.__file__ = __file__
    p = Prepared(canonical(c), digest(raw), canonical(snapshot), tuple(evidence), policies,
        bridge, modules['fm1_uboot_read'].SGHeader, operations, bridge.inventory_digest(operations),
        proof.lineage.installed.manifest_sha256, parent, proof, canonical(witness), base)
    if C.sizeof(p.header_type) != 88:
        raise ValueError('Reviewed Linux SG structure required')
    lineage_config = json.loads(read_file(stop['boot_lineage_path'], 65536))
    boot_config = json.loads(read_file(lineage_config['boot_campaign_path'], 65536))
    return p, dict(original_install_campaign_sha256=proof.lineage.installed.campaign_sha256,
        policy_inputs=json.loads(proof.lineage.installed.config)['policy_inputs'],
        install_journal_sha256=boot_config['journal_sha256'])


def prepare_campaign(path):
    p, _ = _validate_campaign(path, evaluated_at=time.time())
    _AUTHORIZED.add(p); p.check(); return p


def FixedSG(prepared, log):
    require_prepared(prepared)
    if sys.platform != 'linux':
        raise ValueError('Linux SG_IO only')
    base = prepared.native
    class Session(base.FixedSG):
        def __init__(self, p, log):
            # New schema ctor; inherited exchange/close are exact afeefe.
            require_prepared(p)
            self.prepared, self.log = p, log
            self.fd, self.next, self.ioctl_attempts, self.phase = None, 0, 0, 'rom'
            self.failed, self.close_error = False, None
            self.started = time.monotonic()
            snapshot = json.loads(p.snapshot); self.usb = snapshot['usb_binding']
            try:
                validate_connection_witness(json.loads(p.connection_witness), snapshot, p.provenance.snapshot_sha256, time.time())
                self.mapping = p.bridge.discover_sg(self.usb)
                if canonical(self.mapping) != canonical(snapshot['sg_binding']):
                    raise ValueError('Actual returned SG mapping changed')
                self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                opened = os.fstat(self.fd)
                self.fd_identity = opened.st_dev, opened.st_ino, opened.st_rdev
                if not stat.S_ISCHR(opened.st_mode) or canonical(self.fd_identity) != canonical(self.mapping['node_identity']):
                    raise ValueError('Opened actual SG descriptor differs')
                self.binding()
            except BaseException:
                self.failed = True; self.close(); raise

        def binding(self):
            require_prepared(self.prepared, check=False)
            self.prepared.provenance.check_pending()
            super().binding()
            root = Path(__file__).absolute().parent
            for name, pin in (('fm1_returned_rom_backup.py', BASE_SOURCE_SHA),
                              ('fm1_sdk_trace_prepare_stop.py', PROOF_SOURCE_SHA)):
                if digest(read_file(root / name)) != pin:
                    raise ValueError('Reviewed private native/proof source changed')
    return Session(prepared, log)


def manifest(prepared, dumps, mapping):
    c = json.loads(prepared.campaign); snapshot = json.loads(prepared.snapshot)
    return dict(schema=1, kind=KIND, campaign_sha256=prepared.campaign_sha256,
        adapter_sha256=c['adapter_sha256'], preparation_stop_sha256=c['preparation_stop_sha256'],
        connection_witness_sha256=c['connection_witness_sha256'], original_rom_snapshot_sha256=prepared.provenance.snapshot_sha256,
        provenance_source_sha256=PROOF_SOURCE_SHA, preparation_outcome='failed-before-native-worker',
        original_manifest_sha256=prepared.original_manifest_sha256,
        loader_sha256=prepared.bridge.LOADER_SHA, original_loader_sha256=prepared.bridge.ORIGINAL_SHA,
        loader_profile_sha256=prepared.bridge.PROFILE_SHA, profile_source_sha256=prepared.bridge.PROFILE_SOURCE_SHA,
        dependency_sha256=dict(native_backup=BASE_SOURCE_SHA, fixed_loader_backup=prepared.native.BACKUP_SOURCE_SHA,
            reader=prepared.bridge.READER_SHA), request_inventory_sha256=prepared.request_inventory_sha256,
        usb_binding=snapshot['usb_binding'], sg_binding=mapping, flash_bytes=1048576, dumps=dumps,
        identical=True, command_completions=True, commands=8757, flash_readback_only=True,
        historical_unit_identity='FM-1_092', current_flash_sha256=TARGET_SHA,
        physical_recovery_verified=False, boot_observed=False, display_observed=False, kernel_exclusivity=False)


def first_event(prepared):
    c = json.loads(prepared.campaign)
    return dict(event='preparation_stop_backup_prepared', campaign_sha256=prepared.campaign_sha256,
        adapter_sha256=c['adapter_sha256'], preparation_stop_sha256=c['preparation_stop_sha256'],
        connection_witness_sha256=c['connection_witness_sha256'], original_rom_snapshot_sha256=prepared.provenance.snapshot_sha256,
        original_manifest_sha256=prepared.original_manifest_sha256,
        usb_binding=json.loads(prepared.snapshot)['usb_binding'], commands=8757,
        request_inventory_sha256=prepared.request_inventory_sha256, loader_sha256=prepared.bridge.LOADER_SHA,
        profile_sha256=prepared.bridge.PROFILE_SHA, kernel_exclusivity=False, physical_recovery_verified=False)


def validate_read_receipt(raw, prepared, dump_a, dump_b):
    rows = [json.loads(line) for line in raw.splitlines()]
    times = [row.get('time') for row in rows]
    if (len(rows) != 17516 or len(prepared.operations) != 8757 or
            not all(finite_time(t) for t in times) or times != sorted(times) or times[-1] > time.time() or
            times[-1] - times[0] > 900 or len(dump_a) != 1048576 or dump_a != dump_b or
            digest(dump_a) != TARGET_SHA):
        raise ValueError('Exact full chronological dual-target reads required')
    def same(row, expected):
        return canonical({k: v for k, v in row.items() if k != 'time'}) == canonical(expected)
    last = dict(event='preparation_stop_backup_completed', identical=True, bytes_per_dump=1048576,
        target_sha256=TARGET_SHA, physical_recovery_verified=False, retry=False)
    if not same(rows[0], first_event(prepared)) or not same(rows[-1], last):
        raise ValueError('Exact distinct backup terminal envelope required')
    for index, op in enumerate(prepared.operations):
        intent, completed = rows[1+index*2:3+index*2]
        wanted = dict(event='sg_submit_intent', index=index, phase=op.phase, label=op.label,
            cdb=op.cdb.hex(), payload_sha256=digest(op.payload) if op.payload else None,
            out_len=len(op.payload), in_len=op.read_size, retry=False)
        response = completed.get('response_sha256')
        if op.label in ('dumpA.bin', 'dumpB.bin'):
            address = int.from_bytes(op.cdb[2:6], 'big')
            response = digest(dump_a[address:address+256])
        elif not op.read_size:
            response = None
        elif not isinstance(response, str) or len(response) != 64 or any(ch not in '0123456789abcdef' for ch in response):
            raise ValueError('Protocol response digest required')
        status = dict(event='sg_completion', index=index, status=0, masked=0, msg=0, host=0,
            driver=0, resid=0, info=0, sense_len=0, sense_hex='', response_sha256=response, retry=False)
        if not same(intent, wanted) or not same(completed, status):
            raise ValueError('Exact paired read command/completion/page hash required')
    return times[0], times[-1]


def validate_completed_backup(path, *, campaign_sha256, manifest_sha256, commands_sha256,
                              freeze, install_journal_path=None):
    if PROOF_SOURCE_SHA is None:
        raise ValueError('Closed: canonical preparation-stop evidence is not frozen')
    raw = freeze(Path(path), campaign_sha256, 65536); c = json.loads(raw)
    receipt = Path(c['receipt_path'])
    saved = json.loads(freeze(receipt / 'manifest.json', manifest_sha256, 65536))
    commands = freeze(receipt / 'commands.jsonl', commands_sha256, 8 * 1048576)
    p, lineage = _validate_campaign(path, evaluated_at=json.loads(commands.splitlines()[0]).get('time'),
        completed=True, install_journal_path=install_journal_path)
    dumps = [freeze(receipt / name, TARGET_SHA, 1048576) for name in ('dumpA.bin', 'dumpB.bin')]
    dump_records = [dict(file=name, bytes=1048576, sha256=TARGET_SHA, complete=True) for name in ('dumpA.bin', 'dumpB.bin')]
    snapshot = json.loads(p.snapshot)
    if canonical(saved) != canonical(manifest(p, dump_records, snapshot['sg_binding'])):
        raise ValueError('Exact completed distinct backup manifest required')
    started, ended = validate_read_receipt(commands, p, *dumps)
    if started < json.loads(p.connection_witness)['observed_at']:
        raise ValueError('Backup began before separate current witness')
    for evidence_path, data, limit in p.evidence:
        if freeze(evidence_path, digest(data), limit) != data:
            raise ValueError('Completed backup evidence changed')
    check_evidence(p)  # Evidence only: p is never added to opener registry.
    return dict(**lineage, usb_binding=snapshot['usb_binding'], sg_binding=snapshot['sg_binding'],
        request_inventory_sha256=p.request_inventory_sha256, loader_sha256=p.bridge.LOADER_SHA,
        receipt_path=str(receipt), completed_at=ended, _absent_paths=tuple(p.provenance.absent),
        _proof=p.provenance, target_sha256=TARGET_SHA, dumps=tuple(dumps))


def run_campaign(prepared):
    require_prepared(prepared)
    c = json.loads(prepared.campaign); receipt = Path(c['receipt_path'])
    marker = marker_path(prepared.parent, prepared.provenance)
    receipt.mkdir(mode=0o700, exist_ok=False); prepared.bridge.sync_dir(receipt.parent)
    with prepared.bridge.private_file(marker) as fp:
        fp.write(prepared.campaign_sha256.encode('ascii')); fp.flush(); os.fsync(fp.fileno())
    prepared.bridge.sync_dir(marker.parent)
    with prepared.bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields), allow_nan=False)+'\n')
            events.flush()
            if event != 'sg_completion' and (event != 'sg_submit_intent' or fields.get('phase') == 'rom'):
                os.fsync(events.fileno()); prepared.bridge.sync_dir(receipt)
        transport = None
        try:
            fields = first_event(prepared); name = fields.pop('event'); log(name, **fields)
            transport = FixedSG(prepared, log); dumps = []
            for name in ('dumpA.bin', 'dumpB.bin'):
                hasher, count = hashlib.sha256(), 0
                with prepared.bridge.private_file(receipt / name) as fp:
                    while transport.next < len(prepared.operations):
                        pending = prepared.operations[transport.next]
                        if pending.label not in ('inquiry', 'upload', 'jump', 'buffer', 'online', name, name+'.end'):
                            break
                        op, data = transport.exchange_next()
                        if op.label == name:
                            fp.write(data); hasher.update(data); count += len(data)
                        if op.label == name+'.end': break
                    fp.flush(); os.fsync(fp.fileno())
                prepared.bridge.sync_dir(receipt)
                if count != 1048576 or hasher.hexdigest() != TARGET_SHA:
                    raise ValueError('Complete exact target dump required')
                dumps.append(dict(file=name, bytes=count, sha256=hasher.hexdigest(), complete=True))
            transport.binding(); transport.close(); prepared.check()
            if transport.next != 8757 or any(digest(read_file(receipt / entry['file'])) != TARGET_SHA for entry in dumps):
                raise ValueError('Durable exact complete dual inventory required')
            result = manifest(prepared, dumps, transport.mapping)
            log('preparation_stop_backup_completed', identical=True, bytes_per_dump=1048576,
                target_sha256=TARGET_SHA, physical_recovery_verified=False, retry=False)
            with prepared.bridge.private_file(receipt / 'manifest.json', 'w') as fp:
                json.dump(result, fp, sort_keys=True, allow_nan=False); fp.write('\n'); fp.flush(); os.fsync(fp.fileno())
            prepared.bridge.sync_dir(receipt); return result
        except BaseException as exc:
            if transport is not None:
                transport.failed = True
                try: transport.close()
                except BaseException: pass
            try:
                (receipt / 'manifest.json').unlink(missing_ok=True); prepared.bridge.sync_dir(receipt)
                log('preparation_stop_backup_stopped_ambiguous', error=type(exc).__name__, retry=False)
            except BaseException: pass
            raise
        finally:
            if transport is not None: transport.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--campaign', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'linux': raise SystemExit('Linux SG_IO only')
    os.umask(0o077); run_campaign(prepare_campaign(args.campaign))


if __name__ == '__main__': main()
