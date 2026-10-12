"""MIT. Exact private SDK trace capture, injected transport only.

No hardware opener, reset, loader upload or NOR operation. FD07 and WL82's
transfer-local MengLi cipher are reported by kagaimiq's jl-uboot-tool adb3f188.
The earlier physical old-stage read verifies that ABI at its old address only.
New-range acceptance, RAM retention and device-side mutation remain unverified.
Python injection is trusted caller code, not a security sandbox.
"""
import binascii
from dataclasses import dataclass
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import time
from weakref import WeakSet

APP_SHA = '76382f531491b63a9cb75258ae9299185219b55f201e5110a74eb03ab328bf44'
ELF_SHA = 'e9d54172bda7dd085fbd1a46ef35c353210f75ec5f621a3e352a075d7f2a6035'
MANIFEST_SHA = 'b58c49fed04efb4fc29eaf2602605a8e4ec197048bcd418c86a53276198cf86e'
NONCE = bytes.fromhex('6b5482dbb66b5f45ed73e2f26c4a4657')
INQUIRY = bytes.fromhex('120000002400')
MAX_AGE = 120
LIVE_SECONDS = 10
# Literal reviewed boot successor: exact canonical lineage is still required.
# An old image reset receipt or an injected verifier cannot replace it.
BOOT_POLICY_SHA = '49fdd29b11b1ba2a8dd2bade4f12c266843929da6cc7fff8ab217f3824d5ffe2'
_PLANS = WeakSet()
_PREPARED = WeakSet()
_STARTED = WeakSet()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Direct regular evidence required')
        with os.fdopen(fd, 'rb') as fp:
            fd = None
            data = fp.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Evidence exceeds bound')
        return data
    finally:
        if fd is not None:
            os.close(fd)


def _geometry(elf_data):
    # Import our MIT offline parser, never a vendor binary or disassembler.
    from jieli.audit_link import Elf
    elf = Elf(elf_data)
    if elf.e_type != 2 or elf.e_machine != 0xf1:
        raise ValueError('Native pi32v2 executable required')
    ranges = []
    for name, size, alignment, binding in (('lunar_sdk_recovery_trace_record', 64, 16, 1),
                                           ('lunar_sdk_stage', 4, 4, 0)):
        symbols = [s for s in elf.symbols if s['name'] == name]
        if len(symbols) != 1:
            raise ValueError('Unique ELF record symbol required')
        s = symbols[0]
        if (s['size'] != size or s['type'] != 1 or s['bind'] != binding or
                not 0 < s['shndx'] < len(elf.sections) or s['value'] % alignment):
            raise ValueError('ELF object size, binding or alignment differs')
        section = elf.sections[s['shndx']]
        if (section['type'] != 8 or section['flags'] != 3 or
                section['name'] != '.ram0_bss' or
                not 0x01c00000 <= section['addr'] <= s['value'] or
                not s['value'] + size <= section['addr'] + section['size'] <= 0x01c80000):
            raise ValueError('Owned writable allocated ordinary BSS required')
        ranges.append((s['value'], size))
    if ranges[0][0] + ranges[0][1] > ranges[1][0]:
        raise ValueError('Trace and stage overlap')
    if ranges != [(0x01c02880, 64), (0x01c03418, 4)]:
        raise ValueError('Exact native candidate ranges differ')
    return tuple(ranges)


@dataclass(frozen=True, eq=False)
class ReadPlan:
    ranges: tuple
    operations: tuple
    seal: bytes
    evidence: tuple = ()

    def check(self):
        if self not in _PLANS:
            raise ValueError('Exact ELF-derived plan instance required')
        ranges = ((0x01c02880, 64), (0x01c03418, 4))
        reads = tuple((b'\xfd\x07' + struct.pack('>IH', a, n) + b'\xff' * 8, b'', n)
                      for a, n in ranges)
        if self.ranges != ranges or self.operations != ((INQUIRY, b'', 36), *reads, *reads):
            raise ValueError('Frozen derived operations changed')
        seal = json.loads(self.seal)
        if (seal['ranges'] != [list(r) for r in ranges] or
                seal['app_sha256'] != APP_SHA or seal['elf_sha256'] != ELF_SHA or
                seal['manifest_sha256'] != MANIFEST_SHA or seal['nonce_hex'] != NONCE.hex() or
                seal['operations'] != [dict(cdb=c.hex(), out_len=0, in_len=n)
                                       for c, _, n in self.operations]):
            raise ValueError('Frozen plan seal changed')
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw:
                raise ValueError('Frozen actual native evidence changed')


def derive_plan(elf_data, app_data, manifest_data):
    """Offline exact bytes -> two owned ranges -> five immutable requests."""
    if any(type(d) is not bytes for d in (elf_data, app_data, manifest_data)):
        raise ValueError('Immutable actual candidate bytes required')
    if (digest(elf_data) != ELF_SHA or digest(app_data) != APP_SHA or
            len(app_data) != 120688 or digest(manifest_data) != MANIFEST_SHA):
        raise ValueError('Exact native image and build manifest required')
    manifest = json.loads(manifest_data)
    if (manifest['application_sha256'] != APP_SHA or manifest['elf_sha256'] != ELF_SHA or
            manifest['flashable'] is not False or
            manifest['device_operations_performed'] is not False or
            manifest['recovery_trace'] != dict(enabled=True, schema=1,
                nonce_hex=NONCE.hex(), record_bytes=64, startup_reason='unavailable_sentinel')):
        raise ValueError('Exact trace manifest schema required')
    ranges = _geometry(elf_data)
    reads = tuple((b'\xfd\x07' + struct.pack('>IH', address, count) + b'\xff' * 8,
                   b'', count) for address, count in ranges)
    operations = ((INQUIRY, b'', 36), *reads, *reads)
    seal = canonical(dict(schema=1, kind='fm1-exact-sdk-trace-read-plan',
        app_sha256=APP_SHA, elf_sha256=ELF_SHA, manifest_sha256=MANIFEST_SHA,
        nonce_hex=NONCE.hex(), ranges=ranges,
        operations=[dict(cdb=c.hex(), out_len=0, in_len=n) for c, _, n in operations],
        scope='initial-ROM-before-any-loader-upload', hardware_opener=False))
    plan = ReadPlan(ranges, operations, seal)
    _PLANS.add(plan)
    return plan


def derive_plan_files(elf_path, app_path, manifest_path):
    evidence = tuple((Path(p), read_file(p), 2 * 1048576)
                     for p in (elf_path, app_path, manifest_path))
    memory_plan = derive_plan(*(raw for _, raw, _ in evidence))
    plan = ReadPlan(memory_plan.ranges, memory_plan.operations, memory_plan.seal, evidence)
    _PLANS.add(plan)
    plan.check()
    return plan


def decode_transfer(raw, count):
    """One fixed transfer, cipher restarted with FFFFFFFF each time."""
    if type(count) is not int or count not in (4, 64) or type(raw) is not bytes or len(raw) != count:
        raise ValueError('Exactly one trace64 or stage4 transfer required')
    magic = bytes.fromhex('c3cfc0e8ced2b0aec4e3a3acd3f1c1d6')
    crc = binascii.crc_hqx(b'\xff\xff', 0xffff)
    out = bytearray()
    for i, value in enumerate(raw):
        crc = binascii.crc_hqx(magic[i % 16:i % 16 + 1], crc)
        out.append(value ^ (crc & 255))
    return bytes(out)


def interpret(trace, stage):
    """Reject inconsistent bytes; report publication progress, never CPU cause."""
    if type(trace) is not bytes or len(trace) != 64 or type(stage) is not bytes or len(stage) != 4:
        raise ValueError('Exact decoded trace and stage lengths required')
    magic, version, length = struct.unpack_from('<IHH', trace)
    if (magic, version, length) != (0x4c525431, 1, 64) or trace[8:24] != NONCE:
        raise ValueError('Unknown trace schema or stale image nonce')
    names = ('phase', 'phase_complement', 'mailbox_verified', 'panel_result',
             'elapsed_ms', 'heartbeat', 'startup_reason', 'sys_hz', 'lsb_hz', 'sequence')
    fields = dict(zip(names, struct.unpack_from('<IIIiIIIIII', trace, 24)))
    phase, seq, mailbox = fields['phase'], fields['sequence'], fields['mailbox_verified']
    if (phase not in range(1, 8) or fields['phase_complement'] != phase ^ 0xffffffff or
            seq == 0 or seq & 1 or fields['startup_reason'] != 0xffffffff):
        raise ValueError('Torn or unknown trace publication')
    expected = {1: (2,), 2: (4,), 3: (6,), 4: (8,), 5: (10,), 6: (12,), 7: (8, 10, 12)}
    if seq not in expected[phase] or mailbox != int(phase >= 4 and (phase != 7 or seq >= 10)):
        raise ValueError('Phase, sequence and mailbox relationship differs')
    stage_word, = struct.unpack('<I', stage)
    stages = {1: (0, 1, 2, 3, 4, 5, 6, 8, 0xff), 2: (6,), 3: (6,),
              4: (6,), 5: (6,), 6: (6, 7), 7: (6, 8)}
    if stage_word not in stages[phase]:
        raise ValueError('Stage and trace publication contradict native write order')
    panel = fields['panel_result']
    clock_ok = 24000000 <= fields['sys_hz'] <= 480000000 and 0 < fields['lsb_hz'] <= 60000000
    if phase == 1:
        if any(fields[n] != 0 for n in ('panel_result', 'elapsed_ms', 'heartbeat', 'sys_hz', 'lsb_hz')):
            raise ValueError('Initialized trace contains an unrecorded cache')
    elif (panel not in (-4, -3, -2, -1, 0) or (not clock_ok and panel != -1) or
          (panel == 0 and fields['elapsed_ms'] < 20000) or
          (panel == -4 and (fields['elapsed_ms'] >= 20000 or fields['heartbeat'] < 2000))):
        raise ValueError('Cached diagnostic fields contradict native control flow')
    labels = {1: 'initialized', 2: 'before-sdk-lock', 3: 'sdk-lock-acquired',
              4: 'mailbox-verified', 5: 'final-start-intent',
              6: 'request-returned-success', 7: 'request-returned-failure'}
    return dict(fields=fields, stage=stage_word, progress=labels[phase],
        classification='conditional-coherent-trace-publication',
        stage_update_pending=phase in (6, 7) and stage_word == 6,
        startup_reason='unavailable', nonce_identifies_boot=False,
        retention_verified=False, rom_handler_verified=False, new_ranges_hardware_verified=False,
        native_packet_operand_semantics_verified=False, device_mutation_free_verified=False,
        recovery_cause_verified=False, display_observed=False, physical_recovery_verified=False)


def interpret_repeated(raw_trace_a, raw_stage_a, raw_trace_b, raw_stage_b):
    values = tuple(decode_transfer(d, n) for d, n in
        ((raw_trace_a, 64), (raw_stage_a, 4), (raw_trace_b, 64), (raw_stage_b, 4)))
    if values[:2] != values[2:]:
        raise ValueError('Repeated trace or stage changed; no coherent result')
    return interpret(*values[:2])


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def verify_snapshot(raw, lineage, now):
    """Offline fresh enumeration + quiet pre-upload assertion, not ROM proof.

    lineage must come from the separately reviewed trace installation/boot gate.
    This verifier cannot turn caller assertions into actual installation proof.
    """
    s = json.loads(raw)
    if (set(lineage) != {'boot_campaign_sha256', 'boot_completed_at', 'usb_binding', 'sg_binding',
                         'app_sha256', 'elf_sha256', 'nonce_hex'} or
            lineage['app_sha256'] != APP_SHA or lineage['elf_sha256'] != ELF_SHA or
            lineage['nonce_hex'] != NONCE.hex() or
            not isinstance(lineage['boot_campaign_sha256'], str) or
            not re.fullmatch('[0-9a-f]{64}', lineage['boot_campaign_sha256']) or
            set(s) != {'schema', 'kind', 'observed_at', 'usb_binding', 'sg_binding',
                  'target_boot_campaign_sha256', 'quiet_state'} or
            type(s['schema']) is not int or s['schema'] != 1 or
            s['kind'] != 'fm1-passive-post-trace-boot-rom' or
            s['quiet_state'] != 'initial-rom-no-later-commands-no-loader-upload' or
            s['target_boot_campaign_sha256'] != lineage['boot_campaign_sha256'] or
            not _finite(now) or not _finite(s['observed_at']) or
            not _finite(lineage['boot_completed_at']) or
            not lineage['boot_completed_at'] <= s['observed_at'] <= now or
            now - s['observed_at'] > MAX_AGE):
        raise ValueError('Fresh quiet initial-ROM snapshot after exact trace boot required')
    usb, old = s['usb_binding'], lineage['usb_binding']
    if (set(usb) != {'path', 'busnum', 'devnum', 'vid', 'pid'} or
            type(usb['path']) is not str or not re.fullmatch(r'[1-9][0-9]*-[1-9][0-9]*(?:\.[1-9][0-9]*)*', usb['path']) or
            any(type(usb[n]) is not str or not re.fullmatch('[1-9][0-9]*', usb[n]) for n in ('busnum', 'devnum')) or
            usb['path'].split('-')[0] != usb['busnum'] or
            usb['vid'] != '4c4a' or usb['pid'] != '8057' or
            any(usb[n] != old[n] for n in ('path', 'busnum', 'vid', 'pid')) or
            usb['devnum'] == old['devnum']):
        raise ValueError('Fresh original-port ROM enumeration required')
    sg, old_sg = s['sg_binding'], lineage['sg_binding']
    paths = ('node', 'class', 'device', 'usb')
    identities = ('node_identity', 'class_identity', 'device_identity', 'usb_identity')
    if (set(sg) != set(paths + identities) or
            any(type(sg[n]) is not str or not Path(sg[n]).is_absolute() for n in paths) or
            any(type(sg[n]) is not list or len(sg[n]) != 3 or
                any(type(v) is not int or v < 0 for v in sg[n]) for n in identities) or
            Path(sg['usb']).name != usb['path'] or sg['usb_identity'] == old_sg['usb_identity'] or
            sg['node_identity'] == old_sg['node_identity']):
        raise ValueError('Fresh full SG/sysfs mapping required')
    return canonical(s)


@dataclass(frozen=True, eq=False)
class Prepared:
    plan: ReadPlan
    snapshot: bytes
    seal: bytes
    evidence: tuple
    lineage: object
    receipt: Path
    marker: Path

    def check(self):
        if self not in _PREPARED:
            raise ValueError('Exact prepared trace-read instance required')
        self.plan.check()
        self.lineage.check()
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw:
                raise ValueError('Frozen read evidence changed')
        verify_snapshot(self.snapshot, self.lineage.read_binding(), time.time())


def prepare(plan, snapshot_path, lineage, receipt):
    """No hardware authority: accept only independently registered boot lineage.

    The trace boot successor owns acceptance and its exact-instance registry.
    Until it supplies this interface, this factory is deliberately unavailable.
    """
    if not isinstance(BOOT_POLICY_SHA, str) or not re.fullmatch('[0-9a-f]{64}', BOOT_POLICY_SHA):
        raise ValueError('Reviewed exact trace boot lineage successor not accepted')
    source_path = Path(__file__).absolute().parent / 'fm1_sdk_trace_boot.py'
    source = read_file(source_path)
    if digest(source) != BOOT_POLICY_SHA:
        raise ValueError('Reviewed boot lineage source changed')
    module = importlib.import_module('fm1_sdk_trace_boot')
    if (Path(module.__file__).absolute() != source_path or
            getattr(module, 'IMPORTED_SOURCE_SHA256', None) != BOOT_POLICY_SHA or
            read_file(source_path) != source):
        raise ValueError('Canonical pinned boot lineage module required')
    module.require_read_lineage(lineage)
    plan.check()
    if not plan.evidence:
        raise ValueError('Actual-file ELF-derived plan required for campaign')
    lineage.check()
    snapshot_path, receipt = Path(snapshot_path), Path(receipt)
    raw = read_file(snapshot_path, 65536)
    snapshot = verify_snapshot(raw, lineage.read_binding(), time.time())
    parent = lineage.read_receipt_parent()
    marker = parent / ('.sdk-trace-read-' + lineage.read_binding()['boot_campaign_sha256'] + '.consumed')
    if (not receipt.is_absolute() or receipt.parent != parent or receipt.exists() or marker.exists() or
            not stat.S_ISDIR(parent.lstat().st_mode) or stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('New private receipt and unconsumed exact boot required')
    seal = canonical(dict(schema=1, plan_sha256=digest(plan.seal), snapshot_sha256=digest(raw),
        lineage=lineage.read_binding(), receipt_path=str(receipt)))
    own = Path(__file__).absolute()
    prepared = Prepared(plan, snapshot, seal,
        ((snapshot_path, raw, 65536), (own, read_file(own), 2 * 1048576),
         (source_path, source, 2 * 1048576)), lineage, receipt, marker)
    _PREPARED.add(prepared)
    prepared.check()
    return prepared


@dataclass(frozen=True)
class Completion:
    data: bytes
    status: int = 0
    masked: int = 0
    msg: int = 0
    host: int = 0
    driver: int = 0
    resid: int = 0
    info: int = 0
    sense_len: int = 0
    sense: bytes = b''


class Session:
    """Five exact commands on one injected binding, no retry or reopening."""
    def __init__(self, prepared, transport, log):
        self.prepared, self.transport, self.log = prepared, transport, log
        self.next, self.failed, self.closed = 0, False, False
        self.started, self.close_error = time.monotonic(), None
        try:
            if type(prepared) is not Prepared or prepared in _STARTED:
                raise ValueError('Copied or consumed read authority')
            _STARTED.add(prepared)
            self.binding()
        except BaseException:
            self.failed = True
            self.close()
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.transport.close()
            except BaseException as exc:
                self.close_error = exc
                self.failed = True
        if self.close_error is not None:
            raise self.close_error

    def binding(self):
        self.prepared.check()
        if self.closed or not 0 <= time.monotonic() - self.started <= LIVE_SECONDS:
            raise ValueError('Closed or expired read session')
        actual, s = self.transport.binding(), json.loads(self.prepared.snapshot)
        if (set(actual) != {'usb_binding', 'sg_binding', 'fd_identity', 'fd_mode'} or
                canonical(actual['usb_binding']) != canonical(s['usb_binding']) or
                canonical(actual['sg_binding']) != canonical(s['sg_binding']) or
                actual['fd_identity'] != s['sg_binding']['node_identity'] or
                type(actual['fd_mode']) is not int or not stat.S_ISCHR(actual['fd_mode'])):
            raise ValueError('Foreign or changed opened binding')

    def exchange(self, cdb, out, count):
        try:
            if self.failed or self.closed or self.next >= 5:
                raise ValueError('Failed, closed or consumed session')
            index = self.next
            self.next += 1
            if (type(cdb) is not bytes or type(out) is not bytes or type(count) is not int or
                    (cdb, out, count) != self.prepared.plan.operations[index]):
                raise ValueError('Only exact ELF-derived ordered requests permitted')
            self.log('submit_intent', index=index, cdb=cdb.hex(), in_len=count, out_len=0, retry=False)
            self.binding()
            r = self.transport.exchange(cdb, out, count)
            if type(r) is not Completion:
                raise ValueError('Exact structured completion required')
            values = {n: getattr(r, n) for n in
                ('status', 'masked', 'msg', 'host', 'driver', 'resid', 'info', 'sense_len')}
            # Preserve bounded actual status even when completion or post-I/O
            # binding is rejected. Do not publish a coherent decoded result.
            self.log('completion', index=index,
                **{n: v if type(v) is int else None for n, v in values.items()},
                sense_hex=r.sense[:252].hex() if type(r.sense) is bytes else None,
                actual_sense_bytes=len(r.sense) if type(r.sense) is bytes else None,
                actual_response_bytes=len(r.data) if type(r.data) is bytes else None,
                response_sha256=digest(r.data) if type(r.data) is bytes else None, retry=False)
            self.binding()
            if (any(type(v) is not int or v != 0 for v in values.values()) or
                    type(r.data) is not bytes or len(r.data) != count or type(r.sense) is not bytes or r.sense):
                raise OSError('Incomplete or failed read completion')
            if index == 0 and (r.data[8:16].strip() != b'WL82' or r.data[16:32].strip() != b'UBOOT1.00'):
                raise ValueError('Original ROM inquiry required')
            return r.data
        except BaseException:
            self.failed = True
            self.close()
            raise


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _exclusive(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        fp = os.fdopen(fd, 'wb')
    except BaseException:
        os.close(fd)
        raise
    with fp:
        fp.write(raw)
        fp.flush()
        os.fsync(fp.fileno())
    _sync_dir(path.parent)


def run(prepared, transport_factory):
    """Consume durably before injected I/O; preserve ambiguity, never retry."""
    if type(prepared) is not Prepared:
        raise ValueError('Exact prepared read required')
    prepared.check()
    prepared.receipt.mkdir(mode=0o700, exist_ok=False)
    _sync_dir(prepared.receipt.parent)
    _exclusive(prepared.marker, digest(prepared.seal).encode('ascii'))
    _exclusive(prepared.receipt / 'plan.json', prepared.plan.seal)
    _exclusive(prepared.receipt / 'campaign.json', prepared.seal)
    session = None
    events = prepared.receipt / 'commands.jsonl'
    fd = os.open(events, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        fp = os.fdopen(fd, 'w')
    except BaseException:
        os.close(fd)
        raise
    with fp:
        def log(event, **fields):
            fp.write(json.dumps(dict(time=time.time(), event=event, **fields), allow_nan=False) + '\n')
            fp.flush()
            os.fsync(fp.fileno())
            _sync_dir(prepared.receipt)
        try:
            log('read_prepared', campaign_sha256=digest(prepared.seal), plan_sha256=digest(prepared.plan.seal),
                commands=5, upload_operations=0, reset_operations=0, flash_operations=0)
            prepared.check()
            session = Session(prepared, transport_factory(prepared), log)
            replies = [session.exchange(*op) for op in prepared.plan.operations]
            session.close()
            result = interpret_repeated(*replies[1:])
            for name, raw in zip(('inquiry', 'trace-a', 'stage-a', 'trace-b', 'stage-b'), replies):
                _exclusive(prepared.receipt / (name + '.raw.bin'), raw)
            result.update(campaign_sha256=digest(prepared.seal), plan_sha256=digest(prepared.plan.seal),
                          raw_sha256=[digest(d) for d in replies])
            log('coherent_capture_completed', **result, retry=False)
            pending = prepared.receipt / '.result.json.pending'
            _exclusive(pending, canonical(result))
            os.link(pending, prepared.receipt / 'result.json', follow_symlinks=False)
            pending.unlink()
            _sync_dir(prepared.receipt)
            return result
        except BaseException as exc:
            (prepared.receipt / 'result.json').unlink(missing_ok=True)
            _sync_dir(prepared.receipt)
            log('capture_stopped_ambiguous', error=type(exc).__name__, retry=False, classification='inconclusive')
            raise
        finally:
            if session is not None:
                session.close()
