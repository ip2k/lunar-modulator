#!/usr/bin/env python3
"""Bind one future native-read packet from actual retained boot lineage.

File-only preparer. It does not discover USB, refresh a snapshot, open SG_IO,
run the capture wrapper, or create physical evidence. Invoke only after the
actual boot wrapper has retained its original lineage and ROM snapshot. Every
output is new, private, exclusive, and intentionally non-reusable.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL_PINS = {
    'fm1_bound_diagnostic.py': '25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36',
    'fm1_bound_sdk_diagnostic.py': '4718825ab07c05364d3141f9281554b22d3eb2c902af759f4bc68a83ca648847',
    'fm1_bound_sdk_trace.py': '139df5d9adcb6c3fe946fb4feb5f9e814b4a928ba230a739a1f3e07774c294d1',
    'fm1_fixed_loader_backup.py': '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb',
    'fm1_fixed_loader_reset.py': 'dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116',
    'fm1_fixed_target_reset.py': 'b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a',
    'fm1_flash_transaction.py': 'd0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908',
    'fm1_reset_wire.py': '9c81a30a7f8741a606961315d0689341d3ce2e29775d395e05e81d5dbdedfd92',
    'fm1_sdk_rehearsal.py': '9d6f3f60e6a3922ef6a1e42be60ec4c68688937eea05a4cbc32551e6518576d4',
    'fm1_sdk_trace_boot.py': '49fdd29b11b1ba2a8dd2bade4f12c266843929da6cc7fff8ab217f3824d5ffe2',
    'fm1_sdk_trace_capture.py': 'c7b7af792c33efd341517383d10435be827f028b6d1f8b4bd10f22f4e99a9d4d',
    'fm1_sdk_trace_capture_child.py': '554a38a319c0f224c48845d8c1cd0ea789be1ca87698cdd288dc8cd238ee814c',
    'fm1_sdk_trace_install.py': '6be77170f28fff7d7ca9c794ac44592a9c4bd4bae2cc2affd22a1cebf0936720',
    'fm1_sdk_trace_read.py': '411d80186d47dc3786fe2ad48eca5b8fbf7295523c417931b89e75a64cf62051',
    'fm1_sdk_trace_read_wire.py': '68abb2e35350fd0ca70e985d4a2cd9562a6540af6b023cd565ba1f9bda4ecadc',
    'fm1_sdk_trace_recovery_evidence.py': '2e803c72e39f6310dee7040e5f3fa3c639d17648575d5f3b5a5e000d4e514648',
    'fm1_sdk_trace_return_admission.py': '25f7395254c30b9ba063ef5cfdc1578e527af02424c671fae4b890c4114609e3',
    'fm1_sdk_trace_sg.py': 'd682704bf272b4c924ab55caeb32a9f3e8c552bfd0ead3246c8c5feb10590f81',
    'fm1_uboot_read.py': '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57',
    'jieli/audit_link.py': 'c53c79006090d7d3a7b0ea2383d3fa4c52950eb5cf3921807925708f76453103',
    'jieli/audit_sdk_diagnostic.py': 'e8ce7a43e43ef127ecaf87db55578b7cad7bb1a926f2be3ce92b8688ae7dff8b',
    'jieli/diagnostic_report.py': 'd85f2ca1dd70adc015b724b46d3c332c307509ad91fa6faa86adc5fc45e755cf',
    'jieli/inspect_fwsc.py': '2c7a3b61d41366755d457b03d6029c7d9b331b07961335e67e1892fe6168b820',
    'jieli/inspect_stock_flash.py': 'de68a7d862e18adcce066bc6309364830ecfeb9dac6147fe9178384aae98e34b',
    'jieli/loader_config_profile.py': '9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8',
    'jieli/package_guard.py': '78643b8a13114293afc1b3b0880e56858371669cf42a4cadbb31a7bb7557dc51',
    'jieli/raw_flash_profile.py': '43e4d23f665fac1a73dee2b5ae6e05bc5c3d0ab9bee04b886abad34c6289ae8f',
    'jieli/raw_sdk_diagnostic.py': '8c59b67da2c5b66d48dacadf4d90e48bd80272d1868fab21b2a3a80eb1496f07',
}
REPOSITORY_PINS = {
    'firmware/display/panel_probe.c': 'ba622076f9134080139b56e7a549769e2baa0f1e4039d55e87095cfae2d94643',
    'firmware/display/spi1_transport.c': 'eaade38b9d835174174e2756ce8a32fcc6808dc11c88a44d3693ae37915933fd',
    'firmware/recovery/request.c': 'f032ea0f93e2f25b3bf98f3cdcad8b2cc23087a8825ca102fa7fb311194e7c21',
    'firmware/sdk-diagnostic/app_config.h': 'cb90015a63c2768bbacd7fdc021eed2222f58c7ce9ed98ffc1edc5e9a10cc695',
    'firmware/sdk-diagnostic/app_main.c': '6a6d9682edc435811cef27573d3ddbc7ee5da3f1acc533b91401aa8b78c6f62c',
    'firmware/sdk-diagnostic/board.c': 'c96147a5d1bd97d914ffd77f05e49cb0afd9b02771c76877d5dd41af272ffe71',
    'firmware/sdk-diagnostic/recovery_trace.c': 'f538f3d16de0f1132648c7ee565760dcf8e4a42275f48895205a26ca15c8b7fb',
    'firmware/sdk-diagnostic/recovery_trace.h': 'fa969a75033663150f2782d57e2f51f8b96f5b78b41e79e561b4d8bd40ca809d',
    'firmware/sdk-diagnostic/third_party/fm1-nes/board_power.c': '14169a95059831c890a5aa19b20fd30dba9d1148db9a05ea0549afe8522bb1fb',
    'firmware/sdk-diagnostic/third_party/fm1-nes/board_power.h': '722383cd779ed38ed481101e558edb7f2478de4a975f9b67cc37b52f33727248',
    'firmware/third_party/fm1-nes/boot_compat.c': '22869d006494c3b3b5a6ac3f54fa41e3814a1af10709ec571adbc813b03c3287',
    'tools/jieli/audit_link.py': 'c53c79006090d7d3a7b0ea2383d3fa4c52950eb5cf3921807925708f76453103',
    'tools/jieli/audit_sdk_diagnostic.py': 'e8ce7a43e43ef127ecaf87db55578b7cad7bb1a926f2be3ce92b8688ae7dff8b',
    'tools/jieli/build-sdk-diagnostic.py': '2885d948adf438000fafdfa72163fd321f70421a6c0550dfcd3dc9551303d425',
}
INPUT_PINS = {
    'app.bin': '76382f531491b63a9cb75258ae9299185219b55f201e5110a74eb03ab328bf44',
    'fm1.elf': 'e9d54172bda7dd085fbd1a46ef35c353210f75ec5f621a3e352a075d7f2a6035',
    'manifest.json': 'b58c49fed04efb4fc29eaf2602605a8e4ec197048bcd418c86a53276198cf86e',
}
MAX_SOURCE = 32 * 1048576


def read_regular(path, limit=MAX_SOURCE):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('absolute input path required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('direct regular file required')
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('input exceeds fixed bound')
        return raw
    finally:
        if fd is not None:
            os.close(fd)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def mkdir_private(path):
    path = Path(path)
    os.mkdir(path, 0o700)
    os.chmod(path, 0o700, follow_symlinks=False)
    if (not stat.S_ISDIR(path.lstat().st_mode) or stat.S_IMODE(path.stat().st_mode) != 0o700
            or path.stat().st_uid != os.geteuid()):
        raise ValueError('new owner-private directory required')
    sync_dir(path.parent)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def exclusive_bytes(path, raw, mode=0o600):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    try:
        with os.fdopen(fd, 'wb') as stream:
            fd = None
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if fd is not None:
            os.close(fd)
    sync_dir(path.parent)


def exclusive_json(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')
    exclusive_bytes(path, raw)
    return raw


def campaign_envelope(inputs, snapshot_path, receipt_path):
    """Pure construction for the pinned canonical native-read campaign."""
    return {'schema': 1, 'kind': 'fm1-exact-native-sdk-trace-read',
        'adapter_sha256': TOOL_PINS['fm1_sdk_trace_sg.py'],
        'inputs': {'elf_path': str(inputs / 'fm1.elf'), 'app_path': str(inputs / 'app.bin'),
                   'manifest_path': str(inputs / 'manifest.json'), 'snapshot_path': str(snapshot_path)},
        'receipt_path': str(receipt_path)}


def preflight_envelope(lineage_raw, campaign_raw, snapshot_path, snapshot_sha,
                       receipt_path, operations):
    """Pure serializer for expected reader calls; performs no reader I/O."""
    return {'schema': 1, 'kind': 'fm1-native-read-file-only-preflight',
        'native_sha256': TOOL_PINS['fm1_sdk_trace_sg.py'],
        'reader_sha256': TOOL_PINS['fm1_sdk_trace_read.py'],
        'boot_sha256': TOOL_PINS['fm1_sdk_trace_boot.py'],
        'lineage_sha256': digest(lineage_raw), 'campaign_sha256': digest(campaign_raw),
        'snapshot_path': str(snapshot_path), 'snapshot_sha256': snapshot_sha,
        'receipt_path': str(receipt_path), 'operation_count': len(operations),
        'operations': [{'cdb_hex': cdb.hex(), 'data_out_bytes': len(out), 'data_in_bytes': size}
                       for cdb, out, size in operations],
        'prepared': True, 'hardware_access': False}


def pinned_copy(source, destination, expected, limit=MAX_SOURCE):
    raw = read_regular(source, limit)
    if digest(raw) != expected:
        raise ValueError(f'pinned input mismatch: {Path(source).name}')
    exclusive_bytes(destination, raw)
    return digest(raw)


def load_canonical(name, path, expected):
    actual = digest(read_regular(path))
    if actual != expected:
        raise ValueError(f'{name} source pin mismatch')
    if name in sys.modules:
        current = Path(getattr(sys.modules[name], '__file__', '')).absolute()
        if current != Path(path).absolute():
            raise ValueError(f'{name} already imported from a different source')
        module = sys.modules[name]
    else:
        module = importlib.import_module(name)
    if Path(module.__file__).absolute() != Path(path).absolute() or digest(read_regular(path)) != expected:
        raise ValueError(f'{name} canonical module identity mismatch')
    return module


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage', required=True, type=Path)
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--lineage', required=True, type=Path, help='actual retained boot lineage JSON')
    ap.add_argument('--elf', required=True, type=Path)
    ap.add_argument('--app', required=True, type=Path)
    ap.add_argument('--manifest', required=True, type=Path)
    ap.add_argument('--receipt', required=True, type=Path, help='new direct-child receipt under canonical lineage parent')
    a = ap.parse_args()
    stage, run = a.stage, a.run
    if (not all(p.is_absolute() and '..' not in p.parts for p in (stage, run))
            or run.parent != stage or stage == Path('/')
            or stage.parent.resolve(strict=True) != stage.parent):
        raise ValueError('new absolute direct sibling stage/run paths required')
    if os.path.lexists(stage) or os.path.lexists(run):
        raise ValueError('stage and run must both be new; no replacement or reuse')
    for source in (a.lineage, a.elf, a.app, a.manifest):
        if not source.is_absolute():
            raise ValueError('all retained source paths must be absolute')
    if not a.receipt.is_absolute() or os.path.lexists(a.receipt):
        raise ValueError('new absolute unused receipt path required')

    # The caller supplies the fresh actual paths; this helper never searches for
    # or substitutes a modeled/historical snapshot.
    lineage_raw = read_regular(a.lineage, 65536)
    lineage_json = json.loads(lineage_raw)
    if (type(lineage_json) is not dict or lineage_json.get('kind') != 'fm1-exact-sdk-trace-boot-read-lineage'
            or type(lineage_json.get('rom_snapshot_path')) is not str
            or type(lineage_json.get('rom_snapshot_sha256')) is not str):
        raise ValueError('canonical original boot lineage envelope required')
    snapshot_path = Path(lineage_json['rom_snapshot_path'])
    if not snapshot_path.is_absolute() or digest(read_regular(snapshot_path, 65536)) != lineage_json['rom_snapshot_sha256']:
        raise ValueError('original boot-observed snapshot hash/path required')

    mkdir_private(stage)
    mkdir_private(run)
    tools = stage / 'tools'
    inputs = stage / 'inputs'
    mkdir_private(tools)
    mkdir_private(tools / 'jieli')
    mkdir_private(inputs)

    staged = {}
    for rel, expected in TOOL_PINS.items():
        src = ROOT / 'tools' / rel
        dst = tools / rel
        dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Reassert every created parent as a direct owner-private directory.
        cursor = dst.parent
        while cursor != tools.parent:
            if not stat.S_ISDIR(cursor.lstat().st_mode) or stat.S_IMODE(cursor.stat().st_mode) != 0o700:
                raise ValueError('private staged source directory required')
            cursor = cursor.parent
        staged['tools/' + rel] = pinned_copy(src, dst, expected)
    for name, expected in INPUT_PINS.items():
        staged['inputs/' + name] = pinned_copy(
            {'app.bin': a.app, 'fm1.elf': a.elf, 'manifest.json': a.manifest}[name],
            inputs / name, expected)

    # The boot validator replays the completed install using source hashes from
    # the pinned build manifest. Its packet-relative repository must retain
    # those firmware/build inputs as well as Python import dependencies.
    for rel, expected in REPOSITORY_PINS.items():
        if rel in staged:
            if staged[rel] != expected:
                raise ValueError('conflicting repository and tool source pins')
            continue
        dst = stage / rel
        dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        staged[rel] = pinned_copy(ROOT / rel, dst, expected)

    lineage_out = run / 'lineage.json'
    exclusive_bytes(lineage_out, lineage_raw)
    sys.path.insert(0, str(tools))
    boot = load_canonical('fm1_sdk_trace_boot', tools / 'fm1_sdk_trace_boot.py',
                          TOOL_PINS['fm1_sdk_trace_boot.py'])
    native = load_canonical('fm1_sdk_trace_sg', tools / 'fm1_sdk_trace_sg.py',
                            TOOL_PINS['fm1_sdk_trace_sg.py'])
    load_canonical('fm1_sdk_trace_read', tools / 'fm1_sdk_trace_read.py',
                   TOOL_PINS['fm1_sdk_trace_read.py'])
    admission = load_canonical('fm1_sdk_trace_return_admission', tools / 'fm1_sdk_trace_return_admission.py',
                               TOOL_PINS['fm1_sdk_trace_return_admission.py'])
    lineage = boot.prepare_read_lineage(lineage_out)
    lineage_binding = lineage.read_binding()
    if a.receipt.parent != lineage.read_receipt_parent():
        raise ValueError('new read receipt must be a direct child of canonical original parent')

    campaign = run / 'campaign.json'
    campaign_obj = campaign_envelope(inputs, snapshot_path, a.receipt)
    exclusive_json(campaign, campaign_obj)
    prepared = native.prepare_campaign(campaign, lineage)
    if len(prepared.read.plan.operations) != 5:
        raise ValueError('canonical exact five-read campaign required')

    preflight = run / 'preflight.json'
    campaign_raw = read_regular(campaign, 65536)
    exclusive_json(preflight, preflight_envelope(lineage_raw, campaign_raw, snapshot_path,
        lineage_json['rom_snapshot_sha256'], a.receipt, prepared.read.plan.operations))

    child_source = read_regular(tools / 'fm1_sdk_trace_capture_child.py')
    child_values = {'STAGE': stage, 'RUN': run, 'NATIVE_SHA': TOOL_PINS['fm1_sdk_trace_sg.py'],
        'READER_SHA': TOOL_PINS['fm1_sdk_trace_read.py'], 'BOOT_SHA': TOOL_PINS['fm1_sdk_trace_boot.py'],
        'CAMPAIGN_SHA': digest(read_regular(campaign, 65536)), 'LINEAGE_SHA': digest(lineage_raw)}
    child_module = admission
    template_child = read_regular(tools / 'fm1_sdk_trace_capture_child.py').decode('utf-8')
    # verify_derivative is the accepted literal-only AST verifier.
    bound_child = bind_with_admission(child_module, template_child, child_values)
    child_path = run / 'execute-child.py'
    exclusive_bytes(child_path, bound_child.encode('utf-8'))

    members = dict(staged)
    members.update({'run/lineage.json': digest(lineage_raw),
        'run/campaign.json': digest(read_regular(campaign, 65536)),
        'run/preflight.json': digest(read_regular(preflight, 65536)),
        'run/execute-child.py': digest(read_regular(child_path))})
    packet_raw = (json.dumps(members, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
    exclusive_bytes(run / 'packet-pins.json', packet_raw)
    wrapper_source = read_regular(tools / 'fm1_sdk_trace_capture.py').decode('utf-8')
    wrapper_values = {'STAGE': stage, 'RUN': run, 'PACKET_SHA': digest(packet_raw),
        'PACKET_MEMBERS': len(members), 'NATIVE_SHA': TOOL_PINS['fm1_sdk_trace_sg.py'],
        'READER_SHA': TOOL_PINS['fm1_sdk_trace_read.py'], 'BOOT_SHA': TOOL_PINS['fm1_sdk_trace_boot.py'],
        'CHILD_SHA': digest(read_regular(child_path)), 'CAMPAIGN_SHA': digest(read_regular(campaign, 65536)),
        'LINEAGE_SHA': digest(lineage_raw)}
    bound_wrapper = bind_with_admission(admission, wrapper_source, wrapper_values)
    wrapper_path = run / 'execute-once.py'
    exclusive_bytes(wrapper_path, bound_wrapper.encode('utf-8'), 0o700)
    sync_dir(run)
    print(json.dumps({'stage': str(stage), 'run': str(run), 'lineage_sha256': digest(lineage_raw),
        'campaign_sha256': wrapper_values['CAMPAIGN_SHA'], 'packet_sha256': digest(packet_raw),
        'packet_members': len(members), 'child_sha256': wrapper_values['CHILD_SHA'],
        'wrapper_sha256': digest(read_regular(wrapper_path)), 'native_operations': 5,
        'hardware_access': False, 'bound_to_actual_paths': True}, sort_keys=True))


def bind_with_admission(admission, template, values):
    """Create literal-only derivative and make canonical verifier accept it."""
    import ast
    before = ast.parse(template)
    names = set(values)
    # Build output by replacing only RHS text of the named top-level None assignments.
    lines = template.splitlines(keepends=True)
    tree = ast.parse(template)
    spans = []
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in names):
            if not isinstance(node.value, ast.Constant) or node.value.value is not None:
                raise ValueError('template assignment must remain a top-level None literal')
            line = lines[node.lineno - 1]
            prefix, sep, _rhs = line.partition('=')
            if not sep:
                raise ValueError('malformed template assignment')
            val = values[node.targets[0].id]
            literal = 'Path(' + repr(str(val)) + ')' if isinstance(val, Path) else repr(val)
            lines[node.lineno - 1] = prefix + '= ' + literal + ('\n' if line.endswith('\n') else '')
            spans.append(node.targets[0].id)
    if set(spans) != names or len(spans) != len(names):
        raise ValueError('exact assignment inventory mismatch')
    actual = ''.join(lines)
    admission.verify_derivative(template, actual, values)
    return actual


if __name__ == '__main__':
    main()
