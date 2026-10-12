"""MIT. Evidence-only admission for V7's actual native-preparation stop.

Replays the canonical complete install and captured boot; admits no reader result,
loader upload, flash operation or reset. The original ROM snapshot is historical.
A later backup needs its own reviewed factory and fresh connection witness.
"""
from dataclasses import dataclass
import importlib
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
from weakref import WeakSet

BOOT_SHA = '49fdd29b11b1ba2a8dd2bade4f12c266843929da6cc7fff8ab217f3824d5ffe2'
PREPARER_SHA = 'c1e9080ff16dd93212ab4516cb36d7c3a4f2fc46e819d6f071193e3334e6461b'
STOP_PINS = {
    '08-native-prepare.intent.json': '03d334df93d1360d60b0a51f3f6f276744d68684c264d757dc44725f3851877b',
    '08-native-prepare.stdout': 'c6217613af8524c9ea5c93922565dd09472ac174b035adab9bf6c822f1e9b4e0',
    '08-native-prepare.exit.json': 'e3a321d49525241eb9b73537ca376f9d617702497627f226063b23c4bf38aa15',
    'chain-stopped.json': '2fa5475f0a7af426ba8d202a7aaab31ef4d3ae08f5bba6b991a4fc2f9a9c666c',
}
CONSUMED_SHA = '21bc1ecfa97b7f9ff9db77268ef01d7b6f1acd7f5ac19adc0129f41b1097be1a'
PARTIAL_PINS = {'inputs/app.bin': '76382f531491b63a9cb75258ae9299185219b55f201e5110a74eb03ab328bf44',
 'inputs/fm1.elf': 'e9d54172bda7dd085fbd1a46ef35c353210f75ec5f621a3e352a075d7f2a6035',
 'inputs/manifest.json': 'b58c49fed04efb4fc29eaf2602605a8e4ec197048bcd418c86a53276198cf86e',
 'run/lineage.json': 'fab20948e881e9874d1f9772c32acf8f8fd2b678047c12ef31e0e9c50745c95e',
 'tools/fm1_fixed_loader_backup.py': '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb',
 'tools/fm1_reset_wire.py': '9c81a30a7f8741a606961315d0689341d3ce2e29775d395e05e81d5dbdedfd92',
 'tools/fm1_sdk_trace_boot.py': '49fdd29b11b1ba2a8dd2bade4f12c266843929da6cc7fff8ab217f3824d5ffe2',
 'tools/fm1_sdk_trace_capture.py': 'c7b7af792c33efd341517383d10435be827f028b6d1f8b4bd10f22f4e99a9d4d',
 'tools/fm1_sdk_trace_capture_child.py': '554a38a319c0f224c48845d8c1cd0ea789be1ca87698cdd288dc8cd238ee814c',
 'tools/fm1_sdk_trace_read.py': '411d80186d47dc3786fe2ad48eca5b8fbf7295523c417931b89e75a64cf62051',
 'tools/fm1_sdk_trace_read_wire.py': '68abb2e35350fd0ca70e985d4a2cd9562a6540af6b023cd565ba1f9bda4ecadc',
 'tools/fm1_sdk_trace_recovery_evidence.py': '2e803c72e39f6310dee7040e5f3fa3c639d17648575d5f3b5a5e000d4e514648',
 'tools/fm1_sdk_trace_return_admission.py': '25f7395254c30b9ba063ef5cfdc1578e527af02424c671fae4b890c4114609e3',
 'tools/fm1_sdk_trace_sg.py': 'd682704bf272b4c924ab55caeb32a9f3e8c552bfd0ead3246c8c5feb10590f81',
 'tools/fm1_uboot_read.py': '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57',
 'tools/jieli/audit_link.py': '673daa193891462147e1aab1082e62f339508e801e14de80a4cfabcca9828252'}

_PROOFS = WeakSet()


def validate_stop_records(intent, exited, stopped, stdout_sha256, boot_terminal):
    """Check the original terminal chronology; never infer transport success."""
    times = [boot_terminal, intent.get('time'), exited.get('time'), stopped.get('time')]
    if (any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in times)
            or times != sorted(times)):
        raise ValueError('Preparation must follow the captured boot terminal')
    if (intent.get('retry') is not False or intent.get('source_sha256') != PREPARER_SHA
            or {k:v for k,v in exited.items() if k!='time'} !=
               {'exit_status':1,'nonzero_preserved':True,'retry':False,'stdout_sha256':stdout_sha256}
            or {k:v for k,v in stopped.items() if k!='time'} !=
               {'automatic_recovery':False,'capture_cleanup_not_assumed':True,
                'detail':'native-prepare stopped; no retry','error':'RuntimeError',
                'retry':False,'stock_unchanged_not_assumed':True}):
        raise ValueError('Exact file-only preparation stop required')


def require_absent(paths):
    for path in paths:
        if os.path.lexists(path):
            raise ValueError('Later worker, publication or missing dependency appeared')


def packet_inventory(packet):
    """Exact partial closure, including directory types and empty directories."""
    actual = set()
    expected_dirs = {'', 'inputs', 'run', 'tools', 'tools/jieli'}
    seen_dirs = set()
    for parent, dirs, files in os.walk(packet, followlinks=False):
        parent = Path(parent)
        if not stat.S_ISDIR(parent.lstat().st_mode):
            raise ValueError('Direct partial packet directories required')
        seen_dirs.add(str(parent.relative_to(packet)) if parent != packet else '')
        for name in dirs:
            if not stat.S_ISDIR((parent / name).lstat().st_mode):
                raise ValueError('Direct partial packet directories required')
        actual.update(str((parent / name).relative_to(packet)) for name in files)
    if actual != set(PARTIAL_PINS) or seen_dirs != expected_dirs:
        raise ValueError('Exact partial packet inventory required')


def chain_inventory(chain):
    names = tuple(sorted(child.name for child in chain.iterdir()))
    if any(name.split('-', 1)[0].isdigit() and int(name.split('-', 1)[0]) > 8
           for name in names):
        raise ValueError('Later automatic-chain child appeared')
    return names


@dataclass(frozen=True, eq=False)
class PreparationStopProof:
    lineage: object
    evidence: tuple
    absent: tuple
    packet: Path
    chain: Path
    chain_names: tuple
    snapshot: bytes
    snapshot_sha256: str
    terminal_at: float

    def check(self):
        if self not in _PROOFS:
            raise ValueError('Canonical preparation-stop factory instance required')
        self.lineage.check()
        boot = canonical_boot()
        for path, raw, limit in self.evidence:
            if boot.read_file(path, limit) != raw:
                raise ValueError('Frozen preparation-stop evidence changed')
        require_absent(self.absent)
        packet_inventory(self.packet)
        if chain_inventory(self.chain) != self.chain_names:
            raise ValueError('Frozen preparation chain inventory changed')


def canonical_boot():
    own = Path(__file__).resolve().parent
    source = own / 'fm1_sdk_trace_boot.py'
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Direct regular canonical boot source required')
        raw = fp.read(2 * 1048576 + 1)
    if len(raw) > 2 * 1048576 or hashlib.sha256(raw).hexdigest() != BOOT_SHA:
        raise ValueError('Canonical boot source changed')
    module = importlib.import_module('fm1_sdk_trace_boot')
    if Path(module.__file__).absolute() != source:
        raise ValueError('Canonical boot imported from another packet')
    return module


def validate_preparation_stop(lineage_path, chain_path, *, install_journal_path=None):
    """No file writes, device discovery or hardware callbacks on this path."""
    boot = canonical_boot()
    lineage_path, chain = Path(lineage_path), Path(chain_path)
    if not lineage_path.is_absolute() or not chain.is_absolute():
        raise ValueError('Original absolute evidence paths required')
    if (not stat.S_ISDIR(chain.lstat().st_mode)
            or stat.S_IMODE(chain.stat().st_mode) != 0o700):
        raise ValueError('Original direct private chain directory required')
    lineage = boot.prepare_read_lineage(lineage_path, install_journal_path=install_journal_path)
    evidence = []
    def freeze(path, expected=None, limit=2*1048576):
        raw = boot.read_file(path, limit)
        if expected is not None and boot.digest(raw) != expected:
            raise ValueError('Exact physical preparation-stop evidence changed')
        evidence.append((Path(path), raw, limit)); return raw
    records = {name:freeze(chain/name,pin,65536) for name,pin in STOP_PINS.items()}
    freeze(chain.parent/'.automatic-trace-chain.consumed',CONSUMED_SHA,256)
    intent = json.loads(records['08-native-prepare.intent.json'])
    args = intent['argv']
    if len(args)!=20 or args[:5]!=['/usr/bin/python3','-B','-E','-s','-S']:
        raise ValueError('Original isolated file-only preparer invocation required')
    source = Path(args[5]); freeze(source,PREPARER_SHA)
    stage = Path(intent['cwd']); packet=stage/'native-read-stage'
    expected = ['/usr/bin/python3','-B','-E','-s','-S',str(source),
        '--stage',str(packet),'--run',str(packet/'run'),
        '--lineage',str(lineage_path),'--elf',str(stage/'assets/native/lunar-sdk-diagnostic.elf'),
        '--app',str(stage/'assets/native/lunar-sdk-diagnostic.app.bin'),
        '--manifest',str(stage/'assets/native/build-manifest.json'),
        '--receipt',str(lineage.parent/'sdk-trace-read-001')]
    if args!=expected or intent['env']!={'LC_ALL':'C.UTF-8','PATH':'/usr/bin:/bin'}:
        raise ValueError('Original source paths and unused read receipt required')
    originals = json.loads(freeze(lineage_path,PARTIAL_PINS['run/lineage.json'],65536))
    snapshot = freeze(originals['rom_snapshot_path'],originals['rom_snapshot_sha256'],65536)
    terminal = json.loads(freeze(originals['capture_stop_path'],originals['capture_stop_sha256'],65536))['time']
    validate_stop_records(intent,json.loads(records['08-native-prepare.exit.json']),
        json.loads(records['chain-stopped.json']),boot.digest(records['08-native-prepare.stdout']),terminal)
    packet_inventory(packet)
    for name,pin in PARTIAL_PINS.items():freeze(packet/name,pin)
    absent = [lineage.parent/'sdk-trace-read-001',packet/'tools/fm1_fixed_target_reset.py']
    absent.extend(packet/'run'/name for name in ('campaign.json','preflight.json','execute-once.py',
        'execute-child.py','packet-pins.json','wrapper-attempt.json','owned-capture.json'))
    for number,name in ((9,'native-worker'),(10,'returned-admission'),(11,'recovery-prepare'),(12,'recovery-worker')):
        absent.extend(chain/('%02d-%s.%s'%(number,name,suffix)) for suffix in ('intent.json','exit.json','stdout'))
    chain_names = chain_inventory(chain)
    require_absent(absent)
    proof=PreparationStopProof(lineage,tuple(evidence),tuple(absent),packet,chain,chain_names,snapshot,
        boot.digest(snapshot),json.loads(records['chain-stopped.json'])['time'])
    _PROOFS.add(proof);proof.check();return proof
