"""MIT. Exact SDK trace SG successor; no upload, reset, NOR or retry.

Only the runner can grant a single-use open permit, after durable consumption.
Old reviewed MIT source supplies SGHeader and full mapping, not its factories.
No implicit command-line opener. Python caller injection is trusted code.
"""
import builtins
import ctypes as C
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import types
from weakref import WeakSet

# Exact reader accepted by the independent activated V2 Hera review.
READ_POLICY_SHA = '6c9ed93284def1a95f60a42491b92acda0b116d26c224e2138643bd234fc5a43'
BRIDGE_SHA = '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb'
HEADER_SHA = '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57'
AUDIT_SHA = '673daa193891462147e1aab1082e62f339508e801e14de80a4cfabcca9828252'
OPERATIONS = ((bytes.fromhex('120000002400'), b'', 36),
    (bytes.fromhex('fd0701c028800040ffffffffffffffff'), b'', 64),
    (bytes.fromhex('fd0701c034180004ffffffffffffffff'), b'', 4),
    (bytes.fromhex('fd0701c028800040ffffffffffffffff'), b'', 64),
    (bytes.fromhex('fd0701c034180004ffffffffffffffff'), b'', 4))
_AUTHORIZED = WeakSet()
_OPENING = WeakSet()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Direct regular evidence required')
        fp = os.fdopen(fd, 'rb'); fd = None
        with fp:
            raw = fp.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('Evidence exceeds bound')
        return raw
    finally:
        if fd is not None:
            os.close(fd)


def load_source(path, expected, name, elf_parser=None):
    raw = read_file(path)
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected) or digest(raw) != expected:
        raise ValueError('Reviewed executable source differs or activation closed')
    module = types.ModuleType(name); module.__file__ = str(path); sys.modules[name] = module
    if elf_parser is not None:
        # Frozen reader imports only Elf from this dependency. Its private
        # builtins dictionary supplies the exact-byte private parser without
        # replacing the shared canonical jieli.audit_link module cache.
        def exact_import(import_name, globals=None, locals=None, fromlist=(), level=0):
            if import_name == 'jieli.audit_link':
                if fromlist != ('Elf',) or level != 0:
                    raise ValueError('Only reviewed private Elf dependency permitted')
                return elf_parser
            return builtins.__import__(import_name, globals, locals, fromlist, level)
        private_builtins = dict(vars(builtins)); private_builtins['__import__'] = exact_import
        module.__dict__['__builtins__'] = private_builtins
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    if read_file(path) != raw:
        raise ValueError('Source changed during exact-byte import')
    return module


@dataclass(frozen=True, eq=False)
class Prepared:
    campaign: bytes
    read: object
    module: object
    bridge: object
    header_type: type
    evidence: tuple

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact registered native trace campaign required')
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw:
                raise ValueError('Frozen native trace evidence changed')
        self.read.check()
        if self.read.plan.operations != OPERATIONS:
            raise ValueError('Exact five fixed reader requests required')


def prepare_campaign(path, lineage):
    """Device-free preparation; lineage supplied by canonical accepted boot gate."""
    if not isinstance(READ_POLICY_SHA, str) or not re.fullmatch('[0-9a-f]{64}', READ_POLICY_SHA):
        raise ValueError('Reviewed reader and boot activation closed')
    evidence = []
    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path); raw = read_file(path, limit)
        if expected is not None and digest(raw) != expected:
            raise ValueError('Exact campaign evidence differs')
        evidence.append((path, raw, limit)); return raw
    raw = freeze(Path(path).absolute(), limit=65536); c = json.loads(raw)
    if (set(c) != {'schema', 'kind', 'adapter_sha256', 'inputs', 'receipt_path'} or
            type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != 'fm1-exact-native-sdk-trace-read' or
            set(c['inputs']) != {'elf_path', 'app_path', 'manifest_path', 'snapshot_path'}):
        raise ValueError('Exact native trace read envelope required')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    reader_path = root / 'fm1_sdk_trace_read.py'; freeze(reader_path, READ_POLICY_SHA)
    bridge_path = root / 'fm1_fixed_loader_backup.py'; freeze(bridge_path, BRIDGE_SHA)
    header_path = root / 'fm1_uboot_read.py'; freeze(header_path, HEADER_SHA)
    audit_path = root / 'jieli' / 'audit_link.py'; freeze(audit_path, AUDIT_SHA)
    audit = load_source(audit_path, AUDIT_SHA, '_fm1_trace_private_elf_parser')
    reader = load_source(reader_path, READ_POLICY_SHA, '_fm1_trace_native_policy', elf_parser=audit)
    if not isinstance(reader.BOOT_POLICY_SHA, str) or not re.fullmatch('[0-9a-f]{64}', reader.BOOT_POLICY_SHA):
        raise ValueError('Reviewed canonical boot lineage activation closed')
    bridge = load_source(bridge_path, BRIDGE_SHA, '_fm1_trace_mapping_primitives')
    header = load_source(header_path, HEADER_SHA, '_fm1_trace_sg_header')
    if C.sizeof(C.c_void_p) != 8 or C.sizeof(header.SGHeader) != 88:
        raise ValueError('Reviewed 64-bit SG layout required')
    inputs = c['inputs']
    plan = reader.derive_plan_files(*(inputs[n] for n in ('elf_path', 'app_path', 'manifest_path')))
    read = reader.prepare(plan, inputs['snapshot_path'], lineage, c['receipt_path'])
    result = Prepared(canonical(c), read, reader, bridge, header.SGHeader, tuple(evidence))
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
        raise ValueError('Exact registered native trace campaign required')
    prepared.check()
    def factory(read):
        if read is not prepared.read:
            raise ValueError('Exact private reader instance required')
        prepared.check()
        permit = _OpenPermit(prepared); _OPENING.add(permit)
        try:
            return NativeSG(prepared, permit)
        finally:
            _OPENING.discard(permit)
    return prepared.module.run(prepared.read, factory)
