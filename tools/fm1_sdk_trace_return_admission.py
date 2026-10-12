"""MIT. Evidence-only successor for one owned fixed trace-read receipt.

No opener, new Prepared, marker creation, upload, reset or NOR operation. Literal
None gates keep this factory unavailable until the canonical boot/read/native
successors are independently accepted. Historical admission never refreshes the
original ROM snapshot. Python caller code is trusted, not a security sandbox.
"""
import ast
import builtins
from dataclasses import dataclass
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types
from weakref import WeakSet

BOOT_SHA = '49fdd29b11b1ba2a8dd2bade4f12c266843929da6cc7fff8ab217f3824d5ffe2'
READER_SHA = '6c9ed93284def1a95f60a42491b92acda0b116d26c224e2138643bd234fc5a43'
NATIVE_SHA = 'ac63fed2919f97649a508a5c3ae14760b330841451b2f78b5714daf1be92b9c6'
WIRE_SHA = '68abb2e35350fd0ca70e985d4a2cd9562a6540af6b023cd565ba1f9bda4ecadc'
KERNEL_SHA = '2e803c72e39f6310dee7040e5f3fa3c639d17648575d5f3b5a5e000d4e514648'
CAPTURE_SHA = 'c7b7af792c33efd341517383d10435be827f028b6d1f8b4bd10f22f4e99a9d4d'
CHILD_SHA = '554a38a319c0f224c48845d8c1cd0ea789be1ca87698cdd288dc8cd238ee814c'
AUDIT_SHA = '673daa193891462147e1aab1082e62f339508e801e14de80a4cfabcca9828252'
TARGET_SHA = '5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d'
_AUTHORIZED = WeakSet()
_NAMES = ('inquiry', 'trace-a', 'stage-a', 'trace-b', 'stage-b')
_WRAPPER_FIELDS = ('STAGE', 'RUN', 'PACKET_SHA', 'PACKET_MEMBERS', 'NATIVE_SHA',
                   'READER_SHA', 'BOOT_SHA', 'CHILD_SHA', 'CAMPAIGN_SHA', 'LINEAGE_SHA')
_CHILD_FIELDS = ('STAGE', 'RUN', 'NATIVE_SHA', 'READER_SHA', 'BOOT_SHA', 'CAMPAIGN_SHA', 'LINEAGE_SHA')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def pin(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Closed: independently accepted trace lineage sources required')
    return value


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Original absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
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


def private_directory(path):
    path = Path(path)
    if (not path.is_absolute() or not stat.S_ISDIR(path.lstat().st_mode)
            or stat.S_IMODE(path.stat().st_mode) != 0o700):
        raise ValueError('Original direct private directory required')
    return path


class FrozenFiles:
    """Positive and negative evidence, both retained across later callbacks."""
    def __init__(self):
        self.evidence = []
        self.absent = []

    def freeze(self, path, expected=None, limit=2 * 1048576):
        path = Path(path); raw = read_file(path, limit)
        if expected is not None and digest(raw) != pin(expected):
            raise ValueError('Exact accepted evidence differs')
        self.evidence.append((path, raw, limit)); return raw

    def optional(self, path, limit=65536):
        path = Path(path)
        if os.path.lexists(path):
            return self.freeze(path, limit=limit)
        self.absent.append(path); return None

    def missing(self, path):
        path = Path(path)
        if os.path.lexists(path):
            raise ValueError('Unexpected publication or ambiguity artifact')
        self.absent.append(path)

    def check(self):
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw:
                raise ValueError('Frozen trace admission evidence changed')
        if any(os.path.lexists(p) for p in self.absent):
            raise ValueError('Frozen absent trace admission evidence appeared')


def verify_derivative(template, actual, values):
    """Permit only exact top-level None-to-literal assignment substitutions."""
    before, after = ast.parse(template), ast.parse(actual)
    seen = set()
    if len(before.body) != len(after.body):
        raise ValueError('Reviewed template structure differs')
    for original, bound in zip(before.body, after.body):
        if (isinstance(original, ast.Assign) and len(original.targets) == 1
                and isinstance(original.targets[0], ast.Name)
                and original.targets[0].id in values):
            name = original.targets[0].id
            if name in seen or not isinstance(original.value, ast.Constant) or original.value.value is not None:
                raise ValueError('Unique closed template assignment required')
            seen.add(name)
            expected = ast.parse('Path(' + repr(str(values[name])) + ')' if isinstance(values[name], Path)
                                 else repr(values[name]), mode='eval').body
            wanted = ast.Assign(targets=original.targets, value=expected)
            if ast.dump(bound, include_attributes=False) != ast.dump(wanted, include_attributes=False):
                raise ValueError('Exact reviewed literal assignment required')
        elif ast.dump(original, include_attributes=False) != ast.dump(bound, include_attributes=False):
            raise ValueError('Executable template body changed')
    if seen != set(values):
        raise ValueError('Complete closed assignment inventory required')


def load_source(path, expected, name, elf_parser=None):
    raw = read_file(path)
    if digest(raw) != pin(expected):
        raise ValueError('Accepted executable source changed')
    module = types.ModuleType(name); module.__file__ = str(path)
    sys.modules[name] = module
    if elf_parser is not None:
        def exact_import(import_name, globals=None, locals=None, fromlist=(), level=0):
            if import_name == 'jieli.audit_link':
                if fromlist != ('Elf',) or level != 0:
                    raise ValueError('Only reviewed private Elf parser permitted')
                return elf_parser
            return builtins.__import__(import_name, globals, locals, fromlist, level)
        module.__dict__['__builtins__'] = dict(vars(builtins), __import__=exact_import)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    if read_file(path) != raw:
        raise ValueError('Source drift during exact import')
    return module


@dataclass(frozen=True, eq=False)
class ReturnedProof:
    snapshot: bytes
    snapshot_sha256: str
    original_inputs: bytes
    manifest_sha256: str
    private_parent: str
    evidence: tuple
    policies: tuple
    original_install_campaign_sha256: str
    install_journal_sha256: str
    terminal_at: float
    read_outcome: str
    absent: tuple
    lineage: object

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact replay-created returned proof required')
        self.lineage.check()
        frozen = FrozenFiles(); frozen.evidence = self.evidence; frozen.absent = self.absent
        frozen.check()
        for policy in self.policies:
            policy.check_files()


def validate_returned_state(path, *, install_journal_path=None):
    """Reconstruct original lineage and owned five-read evidence, offline only."""
    for value in (BOOT_SHA, READER_SHA, NATIVE_SHA, WIRE_SHA):
        pin(value)  # Before any evidence read/import; None is an explicit closure.
    f = FrozenFiles(); root = Path(__file__).absolute().parent
    own = f.freeze(Path(__file__).absolute())
    raw = f.freeze(path, limit=65536); c = json.loads(raw)
    fields = {'schema', 'kind', 'adapter_sha256', 'boot_lineage_path', 'boot_lineage_sha256',
              'native_campaign_path', 'native_campaign_sha256', 'owned_capture_path', 'owned_capture_sha256'}
    if (type(c) is not dict or set(c) != fields or type(c['schema']) is not int or c['schema'] != 1
            or c['kind'] != 'fm1-exact-owned-sdk-trace-returned-state' or c['adapter_sha256'] != digest(own)):
        raise ValueError('Exact distinct returned trace admission required')
    sources = {'fm1_sdk_trace_boot.py': BOOT_SHA, 'fm1_sdk_trace_read.py': READER_SHA,
               'fm1_sdk_trace_sg.py': NATIVE_SHA, 'fm1_sdk_trace_read_wire.py': WIRE_SHA,
               'fm1_sdk_trace_recovery_evidence.py': KERNEL_SHA,
               'fm1_sdk_trace_capture.py': CAPTURE_SHA, 'fm1_sdk_trace_capture_child.py': CHILD_SHA,
               'jieli/audit_link.py': AUDIT_SHA}
    source_bytes = {n: f.freeze(root / n, sha) for n, sha in sources.items()}
    boot = importlib.import_module('fm1_sdk_trace_boot')
    if (Path(boot.__file__).absolute() != root / 'fm1_sdk_trace_boot.py'
            or boot.IMPORTED_SOURCE_SHA256 != BOOT_SHA):
        raise ValueError('Canonical pinned boot lineage module required')
    lineage_raw = f.freeze(c['boot_lineage_path'], c['boot_lineage_sha256'], 65536)
    lineage = boot.prepare_read_lineage(c['boot_lineage_path'], install_journal_path=install_journal_path)
    boot.require_read_lineage(lineage)
    installed = lineage.installed
    native_raw = f.freeze(c['native_campaign_path'], c['native_campaign_sha256'], 65536)
    native = json.loads(native_raw)
    if (type(native) is not dict or set(native) != {'schema','kind','adapter_sha256','inputs','receipt_path'}
            or type(native['schema']) is not int or native['schema'] != 1
            or native['kind'] != 'fm1-exact-native-sdk-trace-read' or native['adapter_sha256'] != NATIVE_SHA
            or type(native['inputs']) is not dict
            or set(native['inputs']) != {'elf_path','app_path','manifest_path','snapshot_path'}):
        raise ValueError('Original exact native trace campaign required')
    inputs = native['inputs']
    original_lineage = json.loads(lineage_raw)
    if inputs['snapshot_path'] != original_lineage['rom_snapshot_path']:
        raise ValueError('Original boot-observed ROM snapshot path required')
    snapshot_raw = f.freeze(inputs['snapshot_path'], limit=65536)
    snapshot = json.loads(snapshot_raw)
    stage = private_directory(root.parent); run = private_directory(Path(c['native_campaign_path']).parent)
    parent = private_directory(lineage.read_receipt_parent())
    receipt = private_directory(native['receipt_path'])
    if (run.parent != stage or Path(c['native_campaign_path']) != run / 'campaign.json'
            or Path(c['boot_lineage_path']) != run / 'lineage.json'
            or Path(c['owned_capture_path']) != run / 'owned-capture.json' or receipt.parent != parent):
        raise ValueError('Original direct stage/run/receipt relationship required')
    audit = load_source(root / 'jieli/audit_link.py', AUDIT_SHA, '_trace_admission_elf')
    reader = load_source(root / 'fm1_sdk_trace_read.py', READER_SHA, '_trace_admission_reader', audit)
    if reader.BOOT_POLICY_SHA != BOOT_SHA:
        raise ValueError('Exact accepted reader/boot pairing required')
    # Native activation is checked as source AST without constructing its opener.
    native_ast = ast.parse(source_bytes['fm1_sdk_trace_sg.py'])
    assignments = [n for n in native_ast.body if isinstance(n,ast.Assign)
                   and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)
                   and n.targets[0].id=='READ_POLICY_SHA']
    if len(assignments)!=1 or ast.literal_eval(assignments[0].value)!=READER_SHA:
        raise ValueError('Exact accepted native/reader pairing required')
    plan = reader.derive_plan_files(*(inputs[n] for n in ('elf_path','app_path','manifest_path')))
    f.evidence.extend(plan.evidence)
    published_plan = f.optional(receipt / 'plan.json')
    if published_plan is not None and published_plan != plan.seal:
        raise ValueError('Original ELF-derived published plan differs')
    seal = canonical(dict(schema=1,plan_sha256=digest(plan.seal),snapshot_sha256=digest(snapshot_raw),
                          lineage=lineage.read_binding(),receipt_path=str(receipt)))
    published_seal = f.optional(receipt / 'campaign.json')
    if published_seal is not None and published_seal != seal:
        raise ValueError('Original published reader seal differs')
    marker = parent / ('.sdk-trace-read-' + lineage.read_binding()['boot_campaign_sha256'] + '.consumed')
    if f.freeze(marker, limit=64) != digest(seal).encode('ascii'):
        raise ValueError('Original consumed reader marker differs')
    kernel = load_source(root/'fm1_sdk_trace_recovery_evidence.py',KERNEL_SHA,'_trace_admission_kernel')
    wire = load_source(root/'fm1_sdk_trace_read_wire.py',WIRE_SHA,'_trace_admission_wire')
    capture_raw = f.freeze(c['owned_capture_path'],c['owned_capture_sha256'],65536)
    capture_files = {n:f.freeze(run/n,limit=16*1048576 if n=='usbmon.txt' else 2*1048576)
                     for n in kernel._CAPTURE_FILES}
    for name in ('wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json'):
        f.missing(run/name)
    packet_raw = f.freeze(run/'packet-pins.json',limit=65536); packet = json.loads(packet_raw)
    if type(packet) is not dict or len(packet)<7:
        raise ValueError('Exact original packet source/input inventory required')
    required = {'tools/'+n for n in ('fm1_sdk_trace_boot.py','fm1_sdk_trace_read.py','fm1_sdk_trace_sg.py')}
    required.update(str((run/n).relative_to(stage)) for n in
                    ('execute-child.py','campaign.json','lineage.json','preflight.json'))
    if not required <= set(packet):
        raise ValueError('Complete owned packet required')
    for name,sha in packet.items():
        p = Path(name)
        if p.is_absolute() or '..' in p.parts or not p.parts:
            raise ValueError('Bounded original stage-relative packet path required')
        f.freeze(stage/p,sha,32*1048576)
    values=dict(STAGE=stage,RUN=run,NATIVE_SHA=NATIVE_SHA,READER_SHA=READER_SHA,BOOT_SHA=BOOT_SHA,
                CAMPAIGN_SHA=c['native_campaign_sha256'],LINEAGE_SHA=c['boot_lineage_sha256'])
    verify_derivative(source_bytes['fm1_sdk_trace_capture_child.py'],capture_files['execute-child.py'],values)
    wrapper_values=dict(values,PACKET_SHA=digest(packet_raw),PACKET_MEMBERS=len(packet),
                        CHILD_SHA=digest(capture_files['execute-child.py']))
    verify_derivative(source_bytes['fm1_sdk_trace_capture.py'],capture_files['execute-once.py'],wrapper_values)
    commands=f.optional(receipt/'commands.jsonl'); native_log=f.optional(receipt/'native.jsonl')
    raw_files={n:v for n in _NAMES if (v:=f.optional(receipt/(n+'.raw.bin'),64)) is not None}
    result=f.optional(receipt/'result.json'); pending=f.optional(receipt/'.result.json.pending')
    stop=json.loads(capture_files['capture-stop.json']); terminal=stop.get('time')
    if type(terminal) not in (int,float) or not math.isfinite(terminal) or terminal > time.time():
        raise ValueError('Finite original owned terminal required')
    if not commands:
        if raw_files or result is not None or pending is not None:
            raise ValueError('Consumed pretransport cannot publish reader results')
        parsed=dict(outcome='consumed-pretransport-zero-cbw',started_at=None,terminal_at=None)
    else:
        if published_plan is None or published_seal is None:
            raise ValueError('Logged read requires original plan/seal publication')
        parsed=kernel.verify_read_receipt(commands,seal,plan.seal,plan.operations,raw_files,
            interpret=reader.interpret_repeated,result_raw=result,pending_raw=pending,evaluated_at=terminal)
    expected=dict(wrapper_sha256=digest(capture_files['execute-once.py']),
        child_sha256=digest(capture_files['execute-child.py']),native_campaign_path=c['native_campaign_path'],
        native_campaign_sha256=c['native_campaign_sha256'],boot_lineage_path=c['boot_lineage_path'],
        boot_lineage_sha256=c['boot_lineage_sha256'],native_sha256=NATIVE_SHA,reader_sha256=READER_SHA,
        boot_sha256=BOOT_SHA,usb_binding=snapshot['usb_binding'])
    lifecycle=kernel.verify_capture_lifecycle(capture_raw,capture_files,expected,read_outcome=parsed['outcome'],
        read_started=parsed['started_at'],read_terminal=parsed['terminal_at'])
    # The owned wrapper's first attempt follows its original native preparation.
    admission=json.loads(capture_files['wrapper-attempt.json'])['time']
    reader.verify_snapshot(snapshot_raw,lineage.read_binding(),admission)
    if parsed['started_at'] is not None:
        reader.verify_snapshot(snapshot_raw,lineage.read_binding(),parsed['started_at'])
    replay=wire.verify_native_receipt(native_log or b'',commands or b'',snapshot['sg_binding'],outcome=parsed['outcome'])
    wire.verify_read_wire(capture_files['usbmon.txt'],snapshot['usb_binding'],ioctl_intents=replay['ioctl_intents'],
        outcome=parsed['outcome'],raw_replies={i:raw_files[n] for i,n in enumerate(_NAMES) if n in raw_files})
    config=json.loads(installed.config)
    journal_sha=json.loads(f.freeze(json.loads(lineage_raw)['boot_campaign_path'],limit=65536))['journal_sha256']
    proof=ReturnedProof(canonical(snapshot),digest(snapshot_raw),canonical(config['policy_inputs']),
        installed.manifest_sha256,str(parent),tuple(f.evidence),installed.policies,
        installed.campaign_sha256,journal_sha,lifecycle['terminal_at'],parsed['outcome'],tuple(f.absent),lineage)
    _AUTHORIZED.add(proof); proof.check(); return proof
