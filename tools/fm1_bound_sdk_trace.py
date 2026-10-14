"""MIT. Offline exact trace-image policy; separate from frozen old image gates.

No physical opener. Pins awaiting independent acceptance remain closed. Python
caller code is not a security sandbox; exact-instance registries prevent ordinary
copied authority, while source/evidence pins establish this private experiment.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types
from weakref import WeakSet

REHEARSAL_SHA = '9d6f3f60e6a3922ef6a1e42be60ec4c68688937eea05a4cbc32551e6518576d4'
OLD_POLICY_SHA = '4718825ab07c05364d3141f9281554b22d3eb2c902af759f4bc68a83ca648847'
APP_SHA = '76382f531491b63a9cb75258ae9299185219b55f201e5110a74eb03ab328bf44'
ELF_SHA = 'e9d54172bda7dd085fbd1a46ef35c353210f75ec5f621a3e352a075d7f2a6035'
BASELINE_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
TRACE_NONCE = '6b5482dbb66b5f45ed73e2f26c4a4657'
TRACE_ADDRESS = 0x01c02880
TRACE_BYTES = 64
SCOPE = 'FM-1_092 exact private SDK recovery-trace application'
# Literal successor of the saved closed gate: independently accepted raw target,
# build manifest and native/allocation report. Physical admission stays separate.
TARGET_SHA = '5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d'
BUILD_MANIFEST_SHA = 'b58c49fed04efb4fc29eaf2602605a8e4ec197048bcd418c86a53276198cf86e'
TRACE_REVIEW_SHA = 'cf706b9c95ea0635a9d4521b04d3d42730b80b0dfd97070931892ae163c5d690'
_AUTHORIZED = WeakSet()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute evidence path required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Direct regular evidence required')
        fp = os.fdopen(fd, 'rb')
        fd = None
        with fp:
            data = fp.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Evidence exceeds size bound')
        return data
    finally:
        if fd is not None:
            os.close(fd)


def core_modules():
    """Pin before executing, then use frozen import/location/dependency checks."""
    root = Path(__file__).absolute().parent
    path = root / 'fm1_sdk_rehearsal.py'
    data = read_file(path)
    if digest(data) != REHEARSAL_SHA:
        raise ValueError('Frozen SG implementation changed')
    name = '_sdk_trace_rehearsal'
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(data, str(path), 'exec'), module.__dict__)
    modules = module.imports()
    if digest(read_file(root / 'fm1_bound_sdk_diagnostic.py')) != OLD_POLICY_SHA:
        raise ValueError('Frozen policy implementation changed')
    return module, modules


def require_candidate_pins():
    for pin in (TARGET_SHA, BUILD_MANIFEST_SHA, TRACE_REVIEW_SHA):
        if (not isinstance(pin, str) or len(pin) != 64
                or any(c not in '0123456789abcdef' for c in pin)):
            raise ValueError('Exact trace image/native/target acceptance has not frozen')


def check_trace_manifest(data, elf_data, modules):
    """Read allocated symbol geometry; native instruction review is separately pinned."""
    manifest = json.loads(data)
    if (digest(data) != BUILD_MANIFEST_SHA
            or manifest.get('application_sha256') != APP_SHA
            or manifest.get('elf_sha256') != ELF_SHA
            or manifest.get('application_bytes') != 120688
            or manifest.get('sdk_commit') != 'e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d'
            or manifest.get('device_operations_performed') is not False
            or manifest.get('flashable') is not False
            or manifest.get('recovery_trace') != dict(enabled=True, schema=1,
                nonce_hex=TRACE_NONCE, record_bytes=TRACE_BYTES,
                startup_reason='unavailable_sentinel')):
        raise ValueError('Exact private recovery-trace build manifest differs')
    elf = modules['audit_link'].Elf(elf_data)
    symbols = [s for s in elf.symbols if s['name'] == 'lunar_sdk_recovery_trace_record']
    if (len(symbols) != 1 or symbols[0]['value'] != TRACE_ADDRESS
            or symbols[0]['size'] != TRACE_BYTES or symbols[0]['shndx'] == 0):
        raise ValueError('Exact ELF-allocated trace record differs')
    sections = [s for s in elf.sections if s['flags'] & 2 and s['addr'] <= TRACE_ADDRESS
                and TRACE_ADDRESS + TRACE_BYTES <= s['addr'] + s['size']]
    if len(sections) != 1 or sections[0]['name'] != '.ram0_bss':
        raise ValueError('Trace must be entirely inside its one allocated RAM BSS section')


def prepare_transaction(directory, baseline_a, baseline_b, target, identity, writable_ranges):
    require_candidate_pins()
    r, modules = core_modules()
    if digest(baseline_a) != BASELINE_SHA or digest(target) != TARGET_SHA:
        raise ValueError('Exact complete stock and trace target required')
    return modules['fm1_flash_transaction'].create_transaction(directory, baseline_a,
        baseline_b, target, identity, writable_ranges, SCOPE, commit_sector=0x4000)


def load_policy(directory, *, direction, baseline_profile, manifest_path, identity_path,
                reference, app_path, elf_path, campaign_path, entry_log_path,
                backup_log_path, loader_path, profile_path, audit_path,
                build_manifest_path, trace_review_path):
    """Actual-file new-image admission; no old factory or constant override."""
    require_candidate_pins()
    if direction not in ('install', 'restore') or baseline_profile != 'fixed-loader':
        raise ValueError('Explicit fixed-loader install/restore required')
    r, modules = core_modules()
    old = modules['fm1_bound_sdk_diagnostic']
    sdk = modules['raw_sdk_diagnostic']
    tx = modules['fm1_flash_transaction']
    directory = Path(directory).absolute()
    plan, _, baseline, target = tx.load_transaction(directory)
    if (plan.get('commit_sector') != 0x4000 or plan['scope'] != SCOPE
            or digest(baseline) != BASELINE_SHA or digest(target) != TARGET_SHA):
        raise ValueError('Exact trace transaction/directory-last geometry required')
    evidence = []
    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path).absolute()
        data = read_file(path, limit)
        if expected is not None and digest(data) != expected:
            raise ValueError('Pinned trace evidence changed: ' + str(path))
        evidence.append((path, data, limit))
        return data
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute())
    freeze(root/'fm1_sdk_rehearsal.py', REHEARSAL_SHA)
    for name, pin in r.SOURCES.items(): freeze(root/name, pin)
    manifest_bytes, identity_bytes = freeze(manifest_path), freeze(identity_path)
    manifest, identity = json.loads(manifest_bytes), json.loads(identity_bytes)
    if identity != plan['identity']:
        raise ValueError('Trace identity differs from sealed transaction')
    old._identity(identity, baseline)
    app, elf = freeze(app_path, APP_SHA), freeze(elf_path, ELF_SHA)
    build_bytes = freeze(build_manifest_path, BUILD_MANIFEST_SHA)
    check_trace_manifest(build_bytes, elf, modules)
    repository = root.parent
    for name, pin in json.loads(build_bytes)['source_sha256'].items():
        if name.startswith('/source/'):
            freeze(repository / name.removeprefix('/source/'), pin)
    for name, pin in json.loads(build_bytes)['build_audit_sha256'].items():
        freeze(repository / name, pin)
    freeze(trace_review_path, TRACE_REVIEW_SHA)
    campaign_bytes, entry_bytes = freeze(campaign_path), freeze(entry_log_path)
    log_bytes = freeze(backup_log_path, limit=16 * 1048576)
    loader = freeze(loader_path, sdk.raw.FIXED_LOADER_SHA256)
    freeze(profile_path, sdk.raw.FIXED_PROFILE_SHA256)
    if len(loader) != 24064:
        raise ValueError('Exact fixed loader length required')
    for name in old._REFERENCES: freeze(Path(reference)/name)
    sdk.profile_dump(baseline, baseline, manifest, identity, reference, baseline_profile)
    old._provenance(manifest, campaign_bytes, entry_bytes, log_bytes)
    result = sdk.validate_target(baseline, read_file(directory/'backupB.bin'), target,
        manifest, identity, reference, app, elf, baseline_profile, json.loads(freeze(audit_path)))
    if plan['writable_ranges'] != result['writable_ranges']:
        raise ValueError('Sealed trace sectors differ from actual derived geometry')
    binding = dict(backup_manifest_sha256=digest(manifest_bytes),
        campaign_sha256=manifest['campaign_sha256'], adapter_sha256=old.ADAPTER_SHA256,
        entry_log_sha256=manifest['entry_log_sha256'], usb_binding=manifest['usb_binding'],
        request_inventory_sha256=sdk.raw.FIXED_REQUEST_INVENTORY_SHA256)
    result.update(transaction_plan_sha256=tx.digest(tx.encoded(plan)),
        command_direction=direction, command_scope=SCOPE,
        commit_sector=0x4000, sector_order=plan['sector_order'],
        trace_nonce=TRACE_NONCE, trace_address=TRACE_ADDRESS, trace_bytes=TRACE_BYTES,
        protocol_mock_only=True, hardware_validated=False, physical_recovery_verified=False,
        physical_loader_recovery_binding_proven=False, historical_entry_only=True,
        backup_log_replay_verified=False,
        supporting_evidence=[dict(path=str(path), sha256=digest(data)) for path, data, _ in evidence],
        required_injected_binding=binding)
    class Policy(old._Policy):
        def check_files(self):
            if self not in _AUTHORIZED:
                raise ValueError('Exact trace actual-file policy instance required')
            return super().check_files()
        def bind(self, transport):
            self.check_files()
            return super().bind(transport)
    policy = Policy(directory, direction, tx.encoded(plan), baseline, target,
        tx.encoded(result), tuple(result['allowed_sectors']), tuple(evidence),
        tx.encoded(binding), old._VALIDATED)
    _AUTHORIZED.add(policy)
    old._AUTHORIZED.add(policy)
    policy.check_files()
    return policy
