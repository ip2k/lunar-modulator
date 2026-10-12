"""MIT. One private SDK candidate, fixed-loader provenance, injected transport.

Offline policy only: no physical opener, ROM entry/upload, or hardware CLI.
Historical backup receipts and injected binding assertions cannot establish live
hardware recovery. Python caller code is not a security sandbox. The inherited
wire/transaction implementation must receive independent review before a future
physical adapter can use this policy.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
from weakref import WeakSet

from fm1_bound_diagnostic import BoundDiagnosticSession, _identity
from fm1_flash_transaction import create_transaction, load_transaction, encoded, digest
import raw_sdk_diagnostic as sdk

raw = sdk.raw
SCOPE = 'FM-1_092 fixed-loader private SDK diagnostic application'
APP_SHA256 = '991b569df7d131320e42ef34c1b619de586d2a7ba6236c0ea1c089731eb61fa9'
ELF_SHA256 = '8832aa4677a7da3aa7871da58a092e5c3e69d766b31d5e67744301ce437979e2'
ADAPTER_SHA256 = '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb'
ENTRY_REPLY_SHA256 = '7679e7be907c6cc32b3c1f27c48cc8ce6daa865852e8021e2207cdeae223217d'
_VALIDATED = object()
_AUTHORIZED = WeakSet()  # Identity membership, not dataclass value equality.
_REFERENCES = ('top/uboot.boot', 'top/isd_config.ini', 'files/app.bin',
               'files/cfg_tool.bin', 'files/cfg', 'files/cfg-extracted/eq_cfg_hw.bin')


def _read(path, limit=2 * 0x100000):
    """Bounded regular-file read; reject final-component symlink replacement."""
    path = Path(path).absolute()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Evidence must be a regular file: ' + str(path))
        data = fp.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Evidence exceeds bounded size: ' + str(path))
    return data


def _historical_entry(data, usb):
    events = [json.loads(line) for line in data.decode('utf8').splitlines()]
    names = [e.get('event') for e in events]
    order = ('before', 'sending_identity', 'identity', 'sending_soft_key', 'uboot_enumerated')
    if (any(names.count(n) != 1 for n in order) or
            any(n in names for n in ('identity_failed', 'uboot_not_observed', 'stopped'))):
        raise ValueError('Successful fixed-backup entry evidence required')
    indices = [names.index(n) for n in order]
    if indices != sorted(indices):
        raise ValueError('Entry events out of order')
    before, requested, identity, soft, entered = [events[i] for i in indices]
    times = [e.get('time') for e in (before, requested, identity, soft, entered)]
    if (not all(type(t) in (int, float) for t in times) or times != sorted(times)
            or not 0 <= times[-1] - times[0] <= 600
            or not 0 <= entered.get('elapsed', -1) <= 5
            or before.get('usb_path') != usb['path']
            or sum((u.get('path'), u.get('vid'), u.get('pid')) ==
                   (usb['path'], '4c4a', 'c755') for u in before.get('usb', [])) != 1
            or requested.get('hex', '').lower() != 'f0 00 32 45 00 00 00 40 7f f7'
            or identity.get('decoded', {}).get('identity') != 'FM-1_092'
            or digest(bytes.fromhex(identity.get('reply', ''))) != ENTRY_REPLY_SHA256
            or soft.get('hex', '').lower() != 'f0 22 24 35 7d f7'
            or sum({k: u.get(k) for k in usb} == usb for u in entered.get('usb', [])) != 1):
        raise ValueError('Entry identity/key/timing/USB evidence differs')


def _provenance(manifest, campaign_bytes, entry_bytes, log_bytes):
    if (manifest.get('adapter_sha256') != ADAPTER_SHA256
            or manifest.get('physical_recovery_verified') is not False
            or manifest.get('kernel_exclusivity') is not False
            or digest(campaign_bytes) != manifest.get('campaign_sha256')
            or digest(entry_bytes) != manifest.get('entry_log_sha256')):
        raise ValueError('Exact fixed-adapter receipt provenance required')
    config = json.loads(campaign_bytes)
    required = {'schema', 'kind', 'adapter_sha256', 'loader_path', 'profile_path',
                'profile_source_path', 'entry_log_path', 'entry_log_sha256', 'usb_binding', 'receipt_path'}
    if (set(config) != required or type(config['schema']) is not int or config['schema'] != 1
            or config['kind'] != 'fm1-fixed-loader-backup-campaign'
            or config['adapter_sha256'] != ADAPTER_SHA256
            or config['entry_log_sha256'] != manifest['entry_log_sha256']
            or config['usb_binding'] != manifest['usb_binding']
            or any(not isinstance(config[k], str) or not Path(config[k]).is_absolute()
                   for k in ('loader_path', 'profile_path', 'profile_source_path',
                             'entry_log_path', 'receipt_path'))):
        raise ValueError('Campaign differs from fixed-backup manifest')
    _historical_entry(entry_bytes, manifest['usb_binding'])
    events = [json.loads(line) for line in log_bytes.decode('utf8').splitlines()]
    names = [e.get('event') for e in events]
    expected = dict(campaign_sha256=manifest['campaign_sha256'], adapter_sha256=ADAPTER_SHA256,
                    loader_sha256=raw.FIXED_LOADER_SHA256, profile_sha256=raw.FIXED_PROFILE_SHA256,
                    profile_source_sha256=raw.FIXED_PROFILE_SOURCE_SHA256,
                    reader_sha256=raw.FIXED_READER_SHA256, entry_log_sha256=manifest['entry_log_sha256'],
                    usb_binding=manifest['usb_binding'], commands=8757,
                    request_inventory_sha256=raw.FIXED_REQUEST_INVENTORY_SHA256,
                    kernel_exclusivity=False, physical_recovery_verified=False)
    if (names.count('campaign_prepared') != 1 or names.count('campaign_completed') != 1
            or not names or names[0] != 'campaign_prepared' or names[-1] != 'campaign_completed'
            or 'campaign_stopped_ambiguous' in names
            or any(encoded(events[0].get(k)) != encoded(v) for k, v in expected.items())
            or any(encoded(events[-1].get(k)) != encoded(v) for k, v in
                   dict(identical=True, bytes_per_dump=raw.FLASH_BYTES,
                        physical_recovery_verified=False, retry=False).items())):
        raise ValueError('Successful fixed-backup command-log envelope required')
    # The log envelope seals receipt provenance; it is not an independent
    # replay of all 8757 commands or proof that a process/hardware run succeeded.


def prepare_transaction(directory, baseline_a, baseline_b, target, identity, writable_ranges):
    """Create offline files, sealing sector 0x4000 last in both directions."""
    return create_transaction(directory, baseline_a, baseline_b, target, identity,
                              writable_ranges, SCOPE, commit_sector=raw.APP_BASE)


@dataclass(frozen=True, eq=False)
class _Policy:
    directory: Path
    direction: str
    plan_bytes: bytes
    baseline: bytes
    target: bytes
    receipt_bytes: bytes
    sectors: tuple
    evidence: tuple
    binding_bytes: bytes
    _authorization: object

    def check_files(self):
        if self._authorization is not _VALIDATED or self not in _AUTHORIZED:
            raise ValueError('Policy must be the exact actual-file validated instance')
        plan, journal, baseline, target = load_transaction(self.directory)
        if encoded(plan) != self.plan_bytes or baseline != self.baseline or target != self.target:
            raise ValueError('Frozen SDK transaction artifacts changed')
        for path, data, limit in self.evidence:
            if _read(path, limit) != data:
                raise ValueError('Frozen SDK supporting evidence changed: ' + str(path))
        return journal

    def bind(self, transport):
        if self._authorization is not _VALIDATED or self not in _AUTHORIZED:
            raise ValueError('Policy must come from actual-file validation')
        self.check_files()
        return BoundSDKDiagnosticSession(self, transport, _VALIDATED)

    def receipt(self):
        return json.loads(self.receipt_bytes)


def load_policy(directory, *, direction, baseline_profile, manifest_path, identity_path,
                reference, app_path, elf_path, campaign_path, entry_log_path,
                backup_log_path, loader_path, profile_path, audit_path=None):
    """Pin one experiment and recompute native/key/raw gates from actual files."""
    if direction not in ('install', 'restore') or baseline_profile != 'fixed-loader':
        raise ValueError('Explicit install/restore and fixed-loader baseline required')
    directory = Path(directory).resolve()
    plan, _, baseline, target = load_transaction(directory)
    if plan.get('commit_sector') != raw.APP_BASE or plan['scope'] != SCOPE:
        raise ValueError('SDK scope and sealed application directory-last order required')
    evidence = []

    def freeze(path, limit=2 * raw.FLASH_BYTES):
        path = Path(path).absolute()
        data = _read(path, limit)
        evidence.append((path, data, limit))
        return data

    manifest_bytes, identity_bytes = freeze(manifest_path), freeze(identity_path)
    manifest, identity = json.loads(manifest_bytes), json.loads(identity_bytes)
    if identity != plan['identity']:
        raise ValueError('SDK identity evidence differs from immutable plan')
    _identity(identity, baseline)
    app, elf = freeze(app_path), freeze(elf_path)
    if digest(app) != APP_SHA256 or digest(elf) != ELF_SHA256:
        raise ValueError('Only the exact independently reviewed private SDK candidate is permitted')
    campaign_bytes, entry_bytes = freeze(campaign_path), freeze(entry_log_path)
    log_bytes = freeze(backup_log_path, 16 * raw.FLASH_BYTES)
    loader, profile = freeze(loader_path), freeze(profile_path)
    if (len(loader) != 24064 or digest(loader) != raw.FIXED_LOADER_SHA256
            or digest(profile) != raw.FIXED_PROFILE_SHA256):
        raise ValueError('Exact reviewed fixed loader and profile bytes required')
    # Validate basic manifest/USB shape before the receipt envelope uses it.
    sdk.profile_dump(baseline, baseline, manifest, identity, reference, baseline_profile)
    _provenance(manifest, campaign_bytes, entry_bytes, log_bytes)
    root = Path(__file__).absolute().parent
    for path, expected in ((root / 'fm1_fixed_loader_backup.py', ADAPTER_SHA256),
                           (root / 'fm1_uboot_read.py', raw.FIXED_READER_SHA256),
                           (root / 'jieli/loader_config_profile.py', raw.FIXED_PROFILE_SOURCE_SHA256)):
        if digest(freeze(path)) != expected:
            raise ValueError('Reviewed fixed-backup source differs: ' + str(path))
    for name in _REFERENCES:
        freeze(Path(reference) / name)
    expected_audit = json.loads(freeze(audit_path)) if audit_path is not None else None
    result = sdk.validate_target(baseline, (directory / 'backupB.bin').read_bytes(), target,
                                 manifest, identity, reference, app, elf, baseline_profile,
                                 expected_audit)
    if plan['writable_ranges'] != result['writable_ranges']:
        raise ValueError('SDK plan ranges must exactly equal derived changed sectors')
    binding = dict(backup_manifest_sha256=digest(manifest_bytes),
                   campaign_sha256=manifest['campaign_sha256'], adapter_sha256=ADAPTER_SHA256,
                   entry_log_sha256=manifest['entry_log_sha256'], usb_binding=manifest['usb_binding'],
                   request_inventory_sha256=raw.FIXED_REQUEST_INVENTORY_SHA256)
    result.update(transaction_plan_sha256=digest(encoded(plan)), command_direction=direction,
                  command_scope=SCOPE, commit_sector=raw.APP_BASE, sector_order=plan['sector_order'],
                  protocol_mock_only=True, hardware_validated=False,
                  physical_loader_recovery_binding_proven=False,
                  historical_entry_only=True, backup_log_replay_verified=False,
                  supporting_evidence=[dict(path=str(p), sha256=digest(d)) for p, d, _ in evidence],
                  required_injected_binding=binding)
    policy = _Policy(directory, direction, encoded(plan), baseline, target, encoded(result),
                     tuple(result['allowed_sectors']), tuple(evidence), encoded(binding), _VALIDATED)
    _AUTHORIZED.add(policy)
    policy.check_files()  # Reject drift during validation itself.
    return policy


class BoundSDKDiagnosticSession(BoundDiagnosticSession):
    """New constructor/pin; inherit guarded framing, direction, journal and latch."""
    def __init__(self, policy, transport, authorization=None):
        if (authorization is not _VALIDATED or policy._authorization is not _VALIDATED
                or policy not in _AUTHORIZED):
            raise ValueError('Use validated_sdk_policy.bind(injected_transport)')
        self._policy, self._transport = policy, transport
        self._latched, self._running, self._binding = False, False, None
        try:
            binding = self._capture_binding()
            if (binding.get('phase') != 'loader'
                    or binding.get('loader_sha256') != raw.FIXED_LOADER_SHA256
                    or not isinstance(binding.get('session_id'), str) or not binding['session_id'].strip()
                    or binding.get('identity') != json.loads(policy.plan_bytes)['identity']
                    or any(encoded(binding.get(k)) != encoded(v)
                           for k, v in json.loads(policy.binding_bytes).items())):
                raise ValueError('Wrong fixed loader/session/identity/provenance binding')
            self._binding = encoded(binding)
        except BaseException:
            self._stop()
            raise
