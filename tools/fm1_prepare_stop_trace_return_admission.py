"""MIT. Offline admission of the completed preparation-stop trace capture.

Preserves the original consumed reader and historical boot snapshot. This
factory opens evidence files only; it grants no loader, reset or NOR authority.
An explicit recovery adapter must require this registered proof and a separate
fresh connection witness before constructing its native worker.
"""
from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import time
from weakref import WeakSet

from fm1_sdk_trace_return_admission import (
    FrozenFiles, canonical, digest, load_source, private_directory,
    verify_derivative,
)

SOURCES = {
    'fm1_sdk_trace_return_admission.py': '25f7395254c30b9ba063ef5cfdc1578e527af02424c671fae4b890c4114609e3',
    'fm1_sdk_trace_prepare_stop.py': 'c7059e10fb2b6c808cfb8cb3c4247f535be6ce9a459df953dc2dc9c378249515',
    'fm1_sdk_prepare_stop_trace_read.py': 'efb1902a442602fa6097730f4e8a4ebce46e9b02e24b3f2ec1bda834e9e5ca2e',
    'fm1_prepare_stop_trace_receipt.py': '45118fbe8191a495479df3e8cff5b8d91a4c4504bb1d60db53f6b476a15bb52c',
    'fm1_prepare_stop_capture_receipt.py': 'acf09db048ba3f690680c832046ac9886e35a3491510104c28366e6f38bd6b05',
    'fm1_prepare_stop_trace_capture.py': 'b14383ebc52c002a4630170415d7a3e45f3ed38e05d1b8338ab7a42cf854f90d',
    'fm1_prepare_stop_trace_capture_child.py': 'd21656182b59ecfa0272c4939c4f5faec39078e03c8c359ccd1ea22e18e0b7a3',
    'fm1_sdk_trace_sg.py': 'd682704bf272b4c924ab55caeb32a9f3e8c552bfd0ead3246c8c5feb10590f81',
    'fm1_sdk_trace_read.py': '411d80186d47dc3786fe2ad48eca5b8fbf7295523c417931b89e75a64cf62051',
    'fm1_sdk_trace_read_wire.py': '68abb2e35350fd0ca70e985d4a2cd9562a6540af6b023cd565ba1f9bda4ecadc',
    'jieli/audit_link.py': '673daa193891462147e1aab1082e62f339508e801e14de80a4cfabcca9828252',
}
_AUTHORIZED = WeakSet()


@dataclass(frozen=True, eq=False)
class CompletedStopTraceProof:
    stop: object
    plan: object
    evidence: tuple
    absent: tuple
    terminal_at: float
    read_outcome: str

    @property
    def lineage(self):
        return self.stop.lineage

    def check(self):
        require_completed_stop_trace(self)
        self.stop.check()
        self.plan.check()
        frozen = FrozenFiles()
        frozen.evidence, frozen.absent = self.evidence, self.absent
        frozen.check()


def require_completed_stop_trace(proof):
    if type(proof) is not CompletedStopTraceProof or proof not in _AUTHORIZED:
        raise ValueError('Canonical completed stop-trace factory instance required')


def validate_completed_stop_trace(path, *, install_journal_path=None):
    """Compose original install/boot/stop, fixed IN reads and owned capture."""
    root = Path(__file__).absolute().parent
    f = FrozenFiles()
    own = f.freeze(Path(__file__).absolute())
    c = json.loads(f.freeze(path, limit=65536))
    keys = {'schema', 'kind', 'adapter_sha256', 'native_campaign_path',
            'native_campaign_sha256', 'owned_capture_path', 'owned_capture_sha256'}
    if (type(c) is not dict or set(c) != keys or type(c['schema']) is not int
            or c['schema'] != 1 or c['kind'] != 'fm1-completed-stop-trace-returned-state'
            or c['adapter_sha256'] != digest(own)):
        raise ValueError('Exact completed stop-trace admission envelope required')
    source = {n: f.freeze(root / n, sha) for n, sha in SOURCES.items()}

    def canonical_module(name):
        module = importlib.import_module(name)
        if Path(module.__file__).absolute() != root / (name + '.py'):
            raise ValueError('Canonical source module from this closure required')
        return module

    # Source pins are checked before invoking any evidence factory.
    stop_module = canonical_module('fm1_sdk_trace_prepare_stop')
    native = canonical_module('fm1_sdk_prepare_stop_trace_read')
    kernel = canonical_module('fm1_prepare_stop_trace_receipt')
    capture = canonical_module('fm1_prepare_stop_capture_receipt')
    wire = canonical_module('fm1_sdk_trace_read_wire')
    primitives = canonical_module('fm1_sdk_trace_sg')
    if native.PROOF_SOURCE_SHA is not None:
        raise ValueError('Closed native template must remain unchanged')
    campaign_raw = f.freeze(c['native_campaign_path'], c['native_campaign_sha256'], 65536)
    campaign = json.loads(campaign_raw)
    campaign_keys = {'schema', 'kind', 'adapter_sha256', 'preparation_stop_path',
        'preparation_stop_sha256', 'connection_witness_path', 'connection_witness_sha256',
        'elf_path', 'app_path', 'manifest_path', 'receipt_path', 'active_session_state'}
    if (type(campaign) is not dict or set(campaign) != campaign_keys
            or type(campaign['schema']) is not int or campaign['schema'] != 1
            or campaign['kind'] != native.KIND or campaign['active_session_state'] != native.STATE):
        raise ValueError('Original distinct native campaign required')
    stop_raw = f.freeze(campaign['preparation_stop_path'], campaign['preparation_stop_sha256'], 65536)
    stop_c = json.loads(stop_raw)
    if (type(stop_c) is not dict or set(stop_c) != {'schema', 'kind', 'boot_lineage_path',
            'boot_lineage_sha256', 'chain_path'} or type(stop_c['schema']) is not int
            or stop_c['schema'] != 1 or stop_c['kind'] != 'fm1-native-preparation-stop-evidence'):
        raise ValueError('Exact original preparation-stop envelope required')
    f.freeze(stop_c['boot_lineage_path'], stop_c['boot_lineage_sha256'], 65536)
    stop = stop_module.validate_preparation_stop(stop_c['boot_lineage_path'], stop_c['chain_path'],
                                                install_journal_path=install_journal_path)
    if type(stop) is not stop_module.PreparationStopProof:
        raise ValueError('Canonical original stop proof required')
    stop.check()
    installed = stop.lineage.installed
    for p, raw, limit in stop.evidence + stop.lineage.evidence + installed.evidence:
        f.freeze(p, digest(raw), limit)
    for policy in installed.policies:
        for p, raw, limit in policy.evidence:
            f.freeze(p, digest(raw), limit)
        for name in ('plan.json', 'backupA.bin', 'backupB.bin', 'target.bin'):
            f.freeze(policy.directory / name)
        policy.check_files()
    run = private_directory(Path(c['native_campaign_path']).parent)
    stage = private_directory(run.parent)
    receipt = private_directory(campaign['receipt_path'])
    if (Path(c['native_campaign_path']) != run / 'campaign.json'
            or Path(campaign['preparation_stop_path']) != run / 'preparation-stop.json'
            or Path(campaign['connection_witness_path']) != run / 'witness.json'
            or Path(c['owned_capture_path']) != run / 'owned-capture.json'
            or receipt.parent != stop.lineage.parent):
        raise ValueError('Original direct stage/run/receipt relationship required')
    witness = json.loads(f.freeze(campaign['connection_witness_path'],
                                 campaign['connection_witness_sha256'], 65536))
    audit = load_source(root / 'jieli/audit_link.py', SOURCES['jieli/audit_link.py'], '_stop_return_elf')
    reader = load_source(root / 'fm1_sdk_trace_read.py', SOURCES['fm1_sdk_trace_read.py'],
                         '_stop_return_reader', audit)
    plan = reader.derive_plan_files(*(campaign[n] for n in ('elf_path', 'app_path', 'manifest_path')))
    if plan.operations != primitives.OPERATIONS:
        raise ValueError('Original ELF-derived fixed operations required')
    f.evidence.extend(plan.evidence)
    if (f.freeze(receipt / 'plan.json') != plan.seal
            or f.freeze(receipt / 'campaign.json', limit=65536) != canonical(campaign)):
        raise ValueError('Original published native plan/campaign differs')
    boot_sha = stop.lineage.read_binding()['boot_campaign_sha256']
    marker = receipt.parent / ('.sdk-preparation-stop-trace-' + boot_sha + '.consumed')
    if f.freeze(marker, limit=64) != digest(canonical(campaign)).encode('ascii'):
        raise ValueError('Original consumed stop-trace marker required')
    for prefix in ('.sdk-trace-read-', '.sdk-preparation-stop-loader-'):
        f.missing(receipt.parent / (prefix + boot_sha + '.consumed'))
    files = {n: f.freeze(run / n, limit=16*1048576 if n == 'usbmon.txt' else 2*1048576)
             for n in capture.FILES}
    for name in ('wrapper-stopped-ambiguous.json', 'wrapper-cleanup-ambiguous.json'):
        f.missing(run / name)
    packet_raw = f.freeze(run / 'packet-pins.json', limit=65536)
    packet = json.loads(packet_raw)
    required = {'tools/' + n for n in ('fm1_sdk_prepare_stop_trace_read.py',
                'fm1_sdk_trace_read.py', 'fm1_sdk_trace_prepare_stop.py')}
    required.update('run/' + n for n in ('execute-child.py', 'campaign.json',
                                       'preparation-stop.json', 'preflight.json'))
    if type(packet) is not dict or not required <= set(packet):
        raise ValueError('Complete owned source/input packet required')
    for name, sha in packet.items():
        p = Path(name)
        if p.is_absolute() or '..' in p.parts or not p.parts:
            raise ValueError('Bounded stage-relative packet path required')
        f.freeze(stage / p, sha, 32*1048576)
    actual_native = f.freeze(stage / 'tools/fm1_sdk_prepare_stop_trace_read.py', campaign['adapter_sha256'])
    proof_sha = SOURCES['fm1_sdk_trace_prepare_stop.py']
    verify_derivative(source['fm1_sdk_prepare_stop_trace_read.py'], actual_native,
                      dict(PROOF_SOURCE_SHA=proof_sha))
    values = dict(STAGE=stage, RUN=run, NATIVE_SHA=digest(actual_native),
        READER_SHA=SOURCES['fm1_sdk_trace_read.py'], PROOF_SHA=proof_sha,
        CAMPAIGN_SHA=c['native_campaign_sha256'], STOP_SHA=campaign['preparation_stop_sha256'])
    verify_derivative(source['fm1_prepare_stop_trace_capture_child.py'], files['execute-child.py'], values)
    verify_derivative(source['fm1_prepare_stop_trace_capture.py'], files['execute-once.py'],
        dict(values, PACKET_SHA=digest(packet_raw), PACKET_MEMBERS=len(packet),
             CHILD_SHA=digest(files['execute-child.py'])))
    envelope = f.freeze(c['owned_capture_path'], c['owned_capture_sha256'], 65536)
    terminal = json.loads(files['capture-stop.json'])['time']
    if not capture.finite(terminal) or terminal > time.time():
        raise ValueError('Historical finite capture terminal required')
    f.missing(receipt / '.result.json.pending')
    raw_files = {n: f.freeze(receipt / (n + '.raw.bin'), limit=64) for n in kernel.NAMES}
    parsed = kernel.verify_receipt(f.freeze(receipt / 'commands.jsonl', limit=65536),
        f.freeze(receipt / 'native.jsonl', limit=65536), canonical(campaign), raw_files,
        witness['sg_binding'], interpret=reader.interpret_repeated, evaluated_at=terminal,
        result_raw=f.freeze(receipt / 'result.json', limit=65536))
    lifecycle = capture.verify_capture(envelope, files,
        dict(wrapper_sha256=digest(files['execute-once.py']), child_sha256=digest(files['execute-child.py']),
            native_campaign_path=c['native_campaign_path'], native_campaign_sha256=c['native_campaign_sha256'],
            preparation_stop_path=campaign['preparation_stop_path'],
            preparation_stop_sha256=campaign['preparation_stop_sha256'],
            native_sha256=digest(actual_native), reader_sha256=SOURCES['fm1_sdk_trace_read.py'],
            proof_sha256=proof_sha, usb_binding=witness['usb_binding']),
        read_outcome=parsed['outcome'], read_started=parsed['started_at'], read_terminal=parsed['terminal_at'])
    for original_time in (json.loads(files['wrapper-attempt.json'])['time'], parsed['started_at']):
        native.validate_witness(witness, stop, campaign['preparation_stop_sha256'], original_time)
    wire.verify_read_wire(files['usbmon.txt'], witness['usb_binding'],
        ioctl_intents=parsed['native']['ioctl_intents'], outcome=parsed['outcome'],
        raw_replies={i: raw_files[n] for i, n in enumerate(kernel.NAMES)})
    proof = CompletedStopTraceProof(stop, plan, tuple(f.evidence), tuple(f.absent),
                                   lifecycle['terminal_at'], parsed['outcome'])
    _AUTHORIZED.add(proof)
    proof.check()
    return proof
