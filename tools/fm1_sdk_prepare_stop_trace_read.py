"""MIT. Closed, distinct trace preservation after V7's file-only preparation stop.

Five fixed IN requests only; no loader upload, NOR, reset or retry. Reuses the
unchanged reviewed NativeSG mechanical class below, with this module's own
factory/registry/permit. Never forges the old reader's authority or rewrites its
historical snapshot. Native FD07 facts credit kagaimiq/jl-uboot-tool.
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
from weakref import WeakSet
import fm1_sdk_trace_sg as primitives

PROOF_SOURCE_SHA = None  # Closed pending genuine composition and review.
SG_SOURCE_SHA = 'd682704bf272b4c924ab55caeb32a9f3e8c552bfd0ead3246c8c5feb10590f81'
READ_SOURCE_SHA = '411d80186d47dc3786fe2ad48eca5b8fbf7295523c417931b89e75a64cf62051'
KIND = 'fm1-sdk-preparation-stop-native-trace-read'
STATE = 'same-returned-rom-after-file-only-preparation-stop-no-loader-upload-no-later-commands'
OPERATIONS = primitives.OPERATIONS
_AUTHORIZED = WeakSet()
_OPENING = WeakSet()
read_file = primitives.read_file
canonical = primitives.canonical
digest = primitives.digest


def validate_witness(witness, proof, stop_sha256, now):
    snapshot = json.loads(proof.snapshot)
    keys = {'schema', 'kind', 'observed_at', 'usb_binding', 'sg_binding',
            'original_rom_snapshot_sha256', 'preparation_stop_sha256', 'quiet_state'}
    finite = lambda x: type(x) in (int, float) and math.isfinite(x)
    if (type(witness) is not dict or set(witness) != keys or
            type(witness['schema']) is not int or witness['schema'] != 1 or
            witness['kind'] != 'fm1-passive-sdk-preparation-stop-trace-connection' or
            witness['quiet_state'] != STATE or
            witness['original_rom_snapshot_sha256'] != proof.snapshot_sha256 or
            witness['preparation_stop_sha256'] != stop_sha256 or
            not finite(now) or not finite(witness['observed_at']) or
            not proof.terminal_at <= witness['observed_at'] <= now or
            not 0 <= now - witness['observed_at'] <= 120 or
            canonical(witness['usb_binding']) != canonical(snapshot['usb_binding']) or
            canonical(witness['sg_binding']) != canonical(snapshot['sg_binding'])):
        raise ValueError('Separate fresh unchanged preparation-stop trace witness required')


@dataclass(frozen=True, eq=False)
class Prepared:
    seal: bytes
    plan: object
    snapshot: bytes
    evidence: tuple
    provenance: object
    stop_sha256: str
    module: object
    bridge: object
    header_type: type
    receipt: Path
    marker: Path
    absent: tuple

    @property
    def read(self):
        # Unchanged NativeSG mechanics need snapshot/receipt, not old read authority.
        return self

    def check(self):
        if type(self) is not Prepared or self not in _AUTHORIZED:
            raise ValueError('Canonical distinct stop-trace factory required')
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw:
                raise ValueError('Frozen distinct stop-trace evidence changed')
        self.plan.check()
        self.provenance.check_pending()
        for path in self.absent:
            if os.path.lexists(path):
                raise ValueError('Old read or recovery-loader authority appeared')
        validate_witness(json.loads(self.snapshot), self.provenance, self.stop_sha256, time.time())
        if self.plan.operations != OPERATIONS:
            raise ValueError('Exact unchanged five IN requests required')


def prepare_campaign(path):
    if PROOF_SOURCE_SHA is None:
        raise ValueError('Closed: genuine stop-trace composition required')
    evidence = []
    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path); raw = read_file(path, limit)
        if expected is not None and digest(raw) != expected:
            raise ValueError('Exact stop-trace source or evidence pin differs')
        evidence.append((path, raw, limit)); return raw
    raw = freeze(Path(path).absolute(), limit=65536); c = json.loads(raw)
    keys = {'schema', 'kind', 'adapter_sha256', 'preparation_stop_path',
        'preparation_stop_sha256', 'connection_witness_path', 'connection_witness_sha256',
        'elf_path', 'app_path', 'manifest_path', 'receipt_path', 'active_session_state'}
    if (type(c) is not dict or set(c) != keys or type(c['schema']) is not int or
            c['schema'] != 1 or c['kind'] != KIND or c['active_session_state'] != STATE):
        raise ValueError('Exact distinct preparation-stop trace envelope required')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    sg_path = root / 'fm1_sdk_trace_sg.py'; freeze(sg_path, SG_SOURCE_SHA)
    if Path(primitives.__file__).absolute() != sg_path:
        raise ValueError('Canonical pinned SG primitives required')
    proof_path = root / 'fm1_sdk_trace_prepare_stop.py'; freeze(proof_path, PROOF_SOURCE_SHA)
    proof_module = importlib.import_module('fm1_sdk_trace_prepare_stop')
    if Path(proof_module.__file__).absolute() != proof_path:
        raise ValueError('Canonical preparation-stop source required')
    stop = json.loads(freeze(c['preparation_stop_path'], c['preparation_stop_sha256'], 65536))
    if (type(stop) is not dict or set(stop) != {'schema', 'kind', 'boot_lineage_path',
            'boot_lineage_sha256', 'chain_path'} or type(stop['schema']) is not int or
            stop['schema'] != 1 or stop['kind'] != 'fm1-native-preparation-stop-evidence'):
        raise ValueError('Exact preparation-stop evidence envelope required')
    freeze(stop['boot_lineage_path'], stop['boot_lineage_sha256'], 65536)
    proof = proof_module.validate_preparation_stop(stop['boot_lineage_path'], stop['chain_path'])
    proof.check()
    if type(proof) is not proof_module.PreparationStopProof:
        raise ValueError('Canonical registered stop proof required')
    for p, data, limit in proof.evidence + proof.lineage.evidence + proof.lineage.installed.evidence:
        freeze(p, digest(data), limit)
    for policy in proof.lineage.installed.policies:
        for p, data, limit in policy.evidence:
            freeze(p, digest(data), limit)
        for name in ('plan.json', 'backupA.bin', 'backupB.bin', 'target.bin'):
            freeze(policy.directory / name)
        policy.check_files()
    reader_path = root / 'fm1_sdk_trace_read.py'; freeze(reader_path, READ_SOURCE_SHA)
    audit_path = root / 'jieli/audit_link.py'; freeze(audit_path, primitives.AUDIT_SHA)
    audit = primitives.load_source(audit_path, primitives.AUDIT_SHA, '_stop_trace_elf')
    reader = primitives.load_source(reader_path, READ_SOURCE_SHA, '_stop_trace_decode', elf_parser=audit)
    plan = reader.derive_plan_files(c['elf_path'], c['app_path'], c['manifest_path'])
    plan.check()
    if plan.operations != OPERATIONS:
        raise ValueError('Exact ELF-derived native requests required')
    bridge_path = root / 'fm1_fixed_loader_backup.py'; freeze(bridge_path, primitives.BRIDGE_SHA)
    header_path = root / 'fm1_uboot_read.py'; freeze(header_path, primitives.HEADER_SHA)
    bridge = primitives.load_source(bridge_path, primitives.BRIDGE_SHA, '_stop_trace_mapping')
    header = primitives.load_source(header_path, primitives.HEADER_SHA, '_stop_trace_header')
    if C.sizeof(C.c_void_p) != 8 or C.sizeof(header.SGHeader) != 88:
        raise ValueError('Reviewed 64-bit SG layout required')
    witness = freeze(c['connection_witness_path'], c['connection_witness_sha256'], 65536)
    validate_witness(json.loads(witness), proof, c['preparation_stop_sha256'], time.time())
    parent = proof.lineage.parent
    boot_sha = proof.lineage.read_binding()['boot_campaign_sha256']
    marker = parent / ('.sdk-preparation-stop-trace-' + boot_sha + '.consumed')
    absent = (parent / ('.sdk-trace-read-' + boot_sha + '.consumed'),
              parent / ('.sdk-preparation-stop-loader-' + boot_sha + '.consumed'))
    receipt = Path(c['receipt_path'])
    if (not receipt.is_absolute() or receipt.parent != parent or
            not stat.S_ISDIR(parent.lstat().st_mode) or stat.S_IMODE(parent.stat().st_mode) != 0o700 or
            any(os.path.lexists(p) for p in (receipt, marker, *absent))):
        raise ValueError('New private receipt and unconsumed trace lineage required')
    result = Prepared(canonical(c), plan, witness, tuple(evidence), proof,
        c['preparation_stop_sha256'], reader, bridge, header.SGHeader, receipt, marker, absent)
    _AUTHORIZED.add(result); result.check(); return result


@dataclass(frozen=True, eq=False)
class _OpenPermit:
    prepared: Prepared


class NativeSG:
    """One FD/one fixed sequence, advisory flock plus full mapping checks."""
    def __init__(self, prepared, permit=None):
        if sys.platform != 'linux':
            raise ValueError('Linux SG_IO only')
        if permit not in _OPENING or permit.prepared is not prepared:
            raise ValueError('Open only inside durable consumed reader runner')
        _OPENING.discard(permit)
        if type(prepared) is not Prepared:
            raise ValueError('Exact native trace Prepared required')
        prepared.check()
        self.prepared, self.fd, self.journal = prepared, None, None
        self.next, self.failed, self.close_error = 0, False, None
        self.started = time.monotonic()
        s = json.loads(prepared.read.snapshot)
        self.usb, self.mapping = s['usb_binding'], s['sg_binding']
        try:
            path = prepared.read.receipt / 'native.jsonl'
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            try:
                self.journal = os.fdopen(fd, 'w')
            except BaseException:
                os.close(fd); raise
            self.log('native_open_intent', advisory_lock=True, commands=5)
            if canonical(prepared.bridge.discover_sg(self.usb)) != canonical(self.mapping):
                raise ValueError('Initial-ROM full mapping changed')
            self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.binding()
            self.log('native_opened', fd_identity=self.mapping['node_identity'])
        except BaseException as exc:
            self.failed = True
            try:
                self.log('native_open_failed', error=type(exc).__name__, errno=getattr(exc, 'errno', None))
            finally:
                self.close()
            raise

    def log(self, event, **fields):
        if self.journal is not None:
            self.journal.write(json.dumps(dict(time=time.time(), event=event, **fields), allow_nan=False) + '\n')
            self.journal.flush(); os.fsync(self.journal.fileno())
            fd = os.open(self.prepared.read.receipt, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def close(self):
        errors = []
        if self.fd is not None:
            fd, self.fd = self.fd, None
            try:
                os.close(fd)
            except BaseException as exc:
                errors.append(exc); self.failed = True
                try:
                    self.log('native_close_failed', error=type(exc).__name__, errno=getattr(exc, 'errno', None))
                except BaseException as log_exc:
                    errors.append(log_exc)
        if self.journal is not None:
            fp, self.journal = self.journal, None
            try:
                fp.close()
            except BaseException as exc:
                errors.append(exc); self.failed = True
        if errors and self.close_error is None:
            self.close_error = errors[0]
        if self.close_error is not None:
            raise self.close_error

    def binding(self):
        try:
            self.prepared.check()
            if self.failed or self.fd is None or not 0 <= time.monotonic() - self.started <= 10:
                raise ValueError('Closed, failed or expired native reader')
            opened = os.fstat(self.fd)
            identity = [opened.st_dev, opened.st_ino, opened.st_rdev]
            if (not stat.S_ISCHR(opened.st_mode) or identity != self.mapping['node_identity'] or
                    canonical(self.prepared.bridge.discover_sg(self.usb)) != canonical(self.mapping)):
                raise ValueError('Full SG/sysfs/USB/FD binding changed')
            return dict(usb_binding=self.usb, sg_binding=self.mapping,
                        fd_identity=identity, fd_mode=opened.st_mode)
        except BaseException as exc:
            self.failed = True
            try:
                self.log('native_binding_failed', error=type(exc).__name__)
            finally:
                self.close()
            raise

    def exchange(self, cdb, out=b'', count=None):
        try:
            if self.failed or self.fd is None or self.next >= 5:
                raise ValueError('Failed, closed or consumed native reader')
            index = self.next; self.next += 1
            if (type(cdb) is not bytes or type(out) is not bytes or type(count) is not int or
                    (cdb, out, count) != OPERATIONS[index]):
                raise ValueError('Only five exact ordered IN requests permitted')
            self.binding()
            command = C.create_string_buffer(cdb); sense = C.create_string_buffer(32); data = C.create_string_buffer(count)
            h = self.prepared.header_type(interface_id=ord('S'), direction=-3, cmd_len=len(cdb),
                sense_max=32, data_len=count, data=C.addressof(data), cmd=C.addressof(command),
                sense=C.addressof(sense), timeout=3000)
            self.log('native_ioctl_intent', index=index, cdb=cdb.hex(), in_len=count, out_len=0, retry=False)
            self.binding()
            try:
                fcntl.ioctl(self.fd, 0x2285, h)
            except BaseException as exc:
                self.log('native_ioctl_exception', index=index, error=type(exc).__name__,
                         errno=getattr(exc, 'errno', None), completion_valid=False, retry=False)
                raise
            fields = {n: getattr(h, n) for n in ('status', 'masked', 'msg', 'host', 'driver', 'resid', 'info', 'sense_len')}
            length = count - h.resid if 0 <= h.resid <= count else count
            reply = self.prepared.module.Completion(data.raw[:length], **fields,
                                                    sense=sense.raw[:min(h.sense_len, 32)])
            if any(fields.values()) or len(reply.data) != count or reply.sense:
                self.failed = True  # Still return actual evidence for outer logging.
            # Outer Session records actual completion before its post-I/O full
            # binding check and strict acceptance; no further command can pass.
            return reply
        except BaseException:
            self.failed = True; self.close(); raise



def run_campaign(prepared):
    if type(prepared) is not Prepared:
        raise ValueError('Exact distinct stop-trace campaign required')
    prepared.check(); prepared.provenance.check()
    reader = prepared.module
    prepared.receipt.mkdir(mode=0o700, exist_ok=False)
    reader._sync_dir(prepared.receipt.parent)
    reader._exclusive(prepared.marker, digest(prepared.seal).encode('ascii'))
    reader._exclusive(prepared.receipt / 'campaign.json', prepared.seal)
    reader._exclusive(prepared.receipt / 'plan.json', prepared.plan.seal)
    native = None
    fd = os.open(prepared.receipt / 'commands.jsonl',
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'w') as fp:
        def log(event, **fields):
            fp.write(json.dumps(dict(time=time.time(), event=event, **fields), allow_nan=False) + '\n')
            fp.flush(); os.fsync(fp.fileno()); reader._sync_dir(prepared.receipt)
        try:
            log('read_prepared', campaign_sha256=digest(prepared.seal),
                commands=5, upload_operations=0, reset_operations=0, flash_operations=0)
            prepared.check()
            permit = _OpenPermit(prepared); _OPENING.add(permit)
            try:
                native = NativeSG(prepared, permit)
            finally:
                _OPENING.discard(permit)
            replies = []
            for index, (cdb, out, count) in enumerate(OPERATIONS):
                log('submit_intent', index=index, cdb=cdb.hex(), in_len=count, out_len=0, retry=False)
                prepared.check()
                r = native.exchange(cdb, out, count)
                if type(r) is not reader.Completion:
                    raise ValueError('Exact structured native completion required')
                fields = {n: getattr(r, n) for n in
                    ('status', 'masked', 'msg', 'host', 'driver', 'resid', 'info', 'sense_len')}
                log('completion', index=index, **fields, response_sha256=digest(r.data),
                    actual_response_bytes=len(r.data), sense_hex=r.sense.hex(), retry=False)
                # Retain actual raw input even when later interpretation is inconclusive.
                name = ('inquiry', 'trace-a', 'stage-a', 'trace-b', 'stage-b')[index]
                reader._exclusive(prepared.receipt / (name + '.raw.bin'), r.data)
                native.binding()
                if (any(type(v) is not int or v != 0 for v in fields.values()) or
                        type(r.data) is not bytes or len(r.data) != count or
                        type(r.sense) is not bytes or r.sense):
                    raise OSError('Incomplete or failed stop-trace native completion')
                if index == 0 and (r.data[8:16].strip() != b'WL82' or
                        r.data[16:32].strip() != b'UBOOT1.00'):
                    raise ValueError('Original ROM inquiry required')
                replies.append(r.data)
            native.close(); prepared.check()
            result = reader.interpret_repeated(*replies[1:])
            result.update(campaign_sha256=digest(prepared.seal),
                preparation_outcome='failed-before-original-native-worker',
                raw_sha256=[digest(r) for r in replies])
            log('coherent_capture_completed', **result, retry=False)
            pending = prepared.receipt / '.result.json.pending'
            reader._exclusive(pending, canonical(result))
            os.link(pending, prepared.receipt / 'result.json', follow_symlinks=False)
            pending.unlink(); reader._sync_dir(prepared.receipt)
            return result
        except BaseException as exc:
            (prepared.receipt / 'result.json').unlink(missing_ok=True)
            reader._sync_dir(prepared.receipt)
            log('capture_stopped_ambiguous', error=type(exc).__name__, retry=False, classification='inconclusive')
            raise
        finally:
            if native is not None:
                native.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    args = parser.parse_args(); os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__ == '__main__':
    main()
