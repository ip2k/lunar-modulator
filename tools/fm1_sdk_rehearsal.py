#!/usr/bin/env python3
"""MIT. Exact private SDK install/readback/restore rehearsal on Linux SG_IO.

No ROM entry, upload, reset, automatic retry or boot-success claim. A bench
operator must attest the reviewed fixed-loader backup is still the active
connection. This is one private candidate on one recorded NOR layout, not a
general flasher. Native command review remains a separate execution gate.
"""
import argparse
import binascii
import ctypes as C
from dataclasses import dataclass
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from weakref import WeakSet

BASELINE_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
TARGET_SHA = 'df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db'
SOURCES = {
    'fm1_bound_sdk_diagnostic.py': '4718825ab07c05364d3141f9281554b22d3eb2c902af759f4bc68a83ca648847',
    'fm1_bound_diagnostic.py': '25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36',
    'fm1_flash_transaction.py': 'd0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908',
    'fm1_uboot_read.py': '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57',
    'fm1_fixed_loader_backup.py': '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb',
    'fm1_fixed_loader_reset.py': 'dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116',
    'jieli/raw_flash_profile.py': '43e4d23f665fac1a73dee2b5ae6e05bc5c3d0ab9bee04b886abad34c6289ae8f',
    'jieli/raw_sdk_diagnostic.py': '8c59b67da2c5b66d48dacadf4d90e48bd80272d1868fab21b2a3a80eb1496f07',
    'jieli/audit_sdk_diagnostic.py': 'e8ce7a43e43ef127ecaf87db55578b7cad7bb1a926f2be3ce92b8688ae7dff8b',
    'jieli/audit_link.py': '673daa193891462147e1aab1082e62f339508e801e14de80a4cfabcca9828252',
    'jieli/diagnostic_report.py': 'd85f2ca1dd70adc015b724b46d3c332c307509ad91fa6faa86adc5fc45e755cf',
    'jieli/inspect_fwsc.py': '2c7a3b61d41366755d457b03d6029c7d9b331b07961335e67e1892fe6168b820',
    'jieli/inspect_stock_flash.py': 'de68a7d862e18adcce066bc6309364830ecfeb9dac6147fe9178384aae98e34b',
    'jieli/package_guard.py': '78643b8a13114293afc1b3b0880e56858371669cf42a4cadbb31a7bb7557dc51',
    'jieli/loader_config_profile.py': '9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8',
}
_AUTHORIZED = WeakSet()
LIVE_SECONDS = 900
COMMAND_LIMIT = 20000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute input path required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Direct regular input required')
        data = fp.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Input exceeds size bound')
    return data


def check_sources():
    root = Path(__file__).absolute().parent
    for name, expected in SOURCES.items():
        if digest(read_file(root / name)) != expected:
            raise ValueError('Reviewed implementation changed: ' + name)
    return root


def imports():
    root = check_sources()
    sys.path[:0] = [str(root), str(root / 'jieli')]
    modules = {}
    for name in SOURCES:
        if name == 'jieli/loader_config_profile.py':
            continue  # Profile generation is pinned evidence, not executable here.
        module = importlib.import_module(Path(name).stem)
        if Path(module.__file__).absolute() != root / name:
            raise ValueError('Ambient implementation module: ' + name)
        modules[Path(name).stem] = module
    check_sources()
    return modules


@dataclass(frozen=True, eq=False)
class Prepared:
    config: bytes
    campaign_sha256: str
    policies: tuple
    mapping: bytes
    bridge: object
    header_type: type

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact prepared rehearsal instance required')
        check_sources()
        for policy in self.policies:
            policy.check_files()


def prepare_campaign(path):
    """Validate actual files and both directions before any hardware open."""
    raw = read_file(Path(path).absolute(), 65536)
    config = json.loads(raw)
    required = {'schema', 'kind', 'adapter_sha256', 'policy_inputs',
                'backup_exit_status', 'backup_commands_sha256', 'active_session_state',
                'sg_binding', 'receipt_path'}
    if (set(config) != required or type(config['schema']) is not int or config['schema'] != 1
            or config['kind'] != 'fm1-exact-sdk-install-restore-rehearsal'
            or type(config['backup_exit_status']) is not int or config['backup_exit_status'] != 0
            or config['active_session_state'] != 'matching-backup-no-later-commands'
            or digest(read_file(Path(__file__).absolute())) != config['adapter_sha256']):
        raise ValueError('Exact reviewed active-loader rehearsal campaign required')
    inputs = config['policy_inputs']
    expected = {'directory', 'manifest_path', 'identity_path', 'reference', 'app_path',
                'elf_path', 'campaign_path', 'entry_log_path', 'backup_log_path',
                'loader_path', 'profile_path', 'audit_path'}
    if (not isinstance(inputs, dict) or set(inputs) != expected
            or any(not isinstance(p, str) or not Path(p).is_absolute() for p in inputs.values())):
        raise ValueError('Exact absolute policy input paths required')
    modules = imports()
    sdk = modules['fm1_bound_sdk_diagnostic']
    policies = tuple(sdk.load_policy(**inputs, direction=d, baseline_profile='fixed-loader')
                     for d in ('install', 'restore'))
    install, restore = policies
    plan, journal, baseline, target = modules['fm1_flash_transaction'].load_transaction(inputs['directory'])
    if (digest(baseline) != BASELINE_SHA or digest(target) != TARGET_SHA
            or journal['state'] != 'prepared' or journal['direction'] is not None
            or plan['writable_ranges'] != [[a, a + 4096] for a in range(0x4000, 0x22000, 4096)]
            or install.sectors != tuple(range(0x4000, 0x22000, 4096))
            or install.plan_bytes != restore.plan_bytes):
        raise ValueError('Only the exact new 30-sector diagnostic rehearsal is permitted')
    manifest = json.loads(read_file(inputs['manifest_path'], 65536))
    campaign = json.loads(read_file(inputs['campaign_path'], 65536))
    bridge = modules['fm1_fixed_loader_backup']
    log = read_file(inputs['backup_log_path'], 8 * 1048576)
    if (digest(log) != config['backup_commands_sha256']
            or canonical(manifest['sg_binding']) != canonical(config['sg_binding'])
            or manifest['dumps'][0]['sha256'] != BASELINE_SHA
            or manifest['dumps'][1]['sha256'] != BASELINE_SHA):
        raise ValueError('Actual backup log/content/connection differs')
    # Original campaign path names describe the bench run. The policy above
    # already seals the original bytes and actual relocated entry hash; replay
    # its chronology using that independently frozen entry file.
    replay_campaign = dict(campaign, entry_log_path=inputs['entry_log_path'])
    modules['fm1_fixed_loader_reset'].validate_commands(log, manifest, replay_campaign, bridge)
    header = modules['fm1_uboot_read'].SGHeader
    if C.sizeof(header) != 88:
        raise ValueError('Reviewed 64-bit Linux SG_IO layout required')
    destination = Path(config['receipt_path'])
    parent = Path(inputs['manifest_path']).parent
    if (not destination.is_absolute() or destination.exists() or destination.parent != parent
            or Path(campaign['receipt_path']) != parent
            or not stat.S_ISDIR(parent.lstat().st_mode) or parent.stat().st_mode & 0o777 != 0o700):
        raise ValueError('New rehearsal receipt must be inside the actual private backup receipt')
    result = Prepared(canonical(config), digest(raw), policies,
                      canonical(config['sg_binding']), bridge, header)
    _AUTHORIZED.add(result)
    result.check()
    return result


class RehearsalSG:
    """Exact policy direction, live FD/sysfs binding and fail-closed SG status."""
    def __init__(self, prepared, policy, log):
        prepared.check()
        if not any(policy is p for p in prepared.policies):
            raise ValueError('Exact prepared direction policy required')
        self.prepared, self.policy, self.log = prepared, policy, log
        self.fd, self.failed, self.attempts = None, False, 0
        self.close_error = None
        self.started = time.monotonic()
        self.usb = json.loads(policy.binding_bytes)['usb_binding']
        self.expected = json.loads(policy.binding_bytes)
        self.session_id = prepared.campaign_sha256 + ':' + policy.direction
        try:
            self.mapping = prepared.bridge.discover_sg(self.usb)
            if canonical(self.mapping) != prepared.mapping:
                raise ValueError('Backup connection replaced')
            self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.binding()
        except BaseException:
            self.failed = True
            self.close()
            raise

    def close(self):
        if self.close_error is not None:
            raise self.close_error
        if self.fd is not None:
            fd, self.fd = self.fd, None
            try:
                os.close(fd)
            except BaseException as exc:
                self.failed = True
                self.close_error = exc
                raise

    def binding(self):
        if self.failed or self.fd is None or not 0 <= time.monotonic() - self.started <= LIVE_SECONDS:
            raise ValueError('Closed, failed or stale rehearsal connection')
        opened = os.fstat(self.fd)
        if (not stat.S_ISCHR(opened.st_mode)
                or canonical((opened.st_dev, opened.st_ino, opened.st_rdev)) != canonical(self.mapping['node_identity'])
                or canonical(self.prepared.bridge.discover_sg(self.usb)) != self.prepared.mapping):
            self.failed = True
            self.close()
            raise ValueError('Bound SG/sysfs/USB connection replaced')
        return dict(self.expected, phase='loader', loader_sha256=self.prepared.bridge.LOADER_SHA,
                    session_id=self.session_id, identity=json.loads(self.policy.plan_bytes)['identity'])

    def validate_wire(self, cdb, payload, in_size):
        if not isinstance(cdb, bytes) or len(cdb) != 16 or not isinstance(payload, bytes) or type(in_size) is not int:
            raise ValueError('Exact immutable wire request required')
        op, address = int.from_bytes(cdb[:2], 'big'), int.from_bytes(cdb[2:6], 'big')
        if op == 0xFC0A:
            expected = bytes.fromhex('fc0a' + 'ff' * 14), b'', 16
        elif op == 0xFD05:
            if address % 256 or not 0 <= address <= 1048576 - 256:
                raise ValueError('Aligned full-flash read only')
            expected = (b'\xfd\x05' + address.to_bytes(4, 'big') + b'\x01\x00').ljust(16, b'\xff'), b'', 256
        elif op in (0xFB01, 0xFB04):
            # Read requests cannot mutate NOR. Before each mutation, recheck
            # every actual-file gate and reviewed implementation source.
            self.prepared.check()
            journal = self.policy.check_files()
            operation = 'erase' if op == 0xFB01 else 'program'
            if (journal.get('state') != 'running' or journal.get('direction') != self.policy.direction
                    or journal.get('intent') != dict(operation=operation, address=address)):
                raise ValueError('Exact durable direction/mutation intent required')
            if op == 0xFB01:
                if address not in self.policy.sectors:
                    raise ValueError('Derived 4 KiB erase sector only')
                expected = (b'\xfb\x01' + address.to_bytes(4, 'big')).ljust(16, b'\xff'), b'', 16
            else:
                desired = self.policy.target if self.policy.direction == 'install' else self.policy.baseline
                if (address % 256 or address // 4096 * 4096 not in self.policy.sectors
                        or len(payload) != 256 or payload != desired[address:address + 256]):
                    raise ValueError('Exact direction-bound page only')
                prefix = (b'\xfb\x04' + address.to_bytes(4, 'big') + b'\x01\x00\x00'
                          + binascii.crc_hqx(payload, 0).to_bytes(2, 'little'))
                expected = prefix.ljust(16, b'\xff'), payload, 0
        else:
            raise ValueError('No other command is permitted in a rehearsal')
        if (cdb, payload, in_size) != expected:
            raise ValueError('CDB, CRC, padding, payload or response shape differs')

    def exchange(self, cdb, payload=b'', in_size=0):
        try:
            self.binding()
            self.validate_wire(cdb, payload, in_size)
            if self.attempts >= COMMAND_LIMIT:
                raise ValueError('Rehearsal command limit reached')
            index = self.attempts
            self.attempts += 1  # An attempted command is never retried on this handle.
            command, sense = C.create_string_buffer(cdb), C.create_string_buffer(32)
            data = C.create_string_buffer(payload) if payload else C.create_string_buffer(in_size)
            h = self.prepared.header_type(interface_id=ord('S'), direction=-2 if payload else -3,
                cmd_len=16, sense_max=32, data_len=len(payload) or in_size,
                data=C.addressof(data), cmd=C.addressof(command), sense=C.addressof(sense), timeout=3000)
            self.log('sg_submit_intent', index=index, direction=self.policy.direction, cdb=cdb.hex(),
                     out_len=len(payload), in_len=in_size, payload_sha256=digest(payload) if payload else None,
                     retry=False)
            self.binding()
            self.validate_wire(cdb, payload, in_size)
            fcntl.ioctl(self.fd, 0x2285, h)
            self.log('sg_completion', index=index, direction=self.policy.direction, status=h.status,
                     masked=h.masked, msg=h.msg, host=h.host, driver=h.driver, resid=h.resid, info=h.info,
                     sense_len=h.sense_len, sense_hex=sense.raw[:min(h.sense_len, 32)].hex(),
                     response_sha256=digest(data.raw[:in_size]) if in_size else None, retry=False)
            self.binding()
            if (h.status or h.masked or h.msg or h.host or h.driver or h.resid or h.info or h.sense_len):
                raise OSError('Incomplete or ambiguous SG completion')
            result = data.raw[:in_size]
            if (in_size == 16 and result[:2] != cdb[:2]
                    or cdb[:2] == b'\xfc\x0a' and (result[2], int.from_bytes(result[4:8], 'little')) != (3, 0x856014)):
                raise ValueError('Protocol response differs')
            return result
        except BaseException:
            self.failed = True
            self.close()
            raise


def run_campaign(prepared):
    prepared.check()
    config, bridge = json.loads(prepared.config), prepared.bridge
    receipt = Path(config['receipt_path'])
    receipt.mkdir(mode=0o700, exist_ok=False)
    bridge.sync_dir(receipt.parent)
    # A different receipt name cannot reuse this backup's rehearsal authority.
    with bridge.private_file(receipt.parent / '.sdk-rehearsal.consumed') as fp:
        fp.write(prepared.campaign_sha256.encode('ascii')); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(receipt.parent)
    with bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields)) + '\n')
            events.flush()
            os.fsync(events.fileno()); bridge.sync_dir(receipt)

        results = []
        try:
            log('rehearsal_prepared', campaign_sha256=prepared.campaign_sha256,
                adapter_sha256=config['adapter_sha256'], source_sha256=SOURCES,
                sg_binding=config['sg_binding'], kernel_exclusivity=False,
                boot_observed=False, physical_recovery_verified=False)
            for policy in prepared.policies:
                transport = RehearsalSG(prepared, policy, log)
                try:
                    result = policy.bind(transport).run(checkpoint=log)
                finally:
                    transport.close()
                expected = TARGET_SHA if policy.direction == 'install' else BASELINE_SHA
                if result['verified_sha256'] != expected:
                    raise ValueError('Final complete NOR verification differs')
                # These separate SG receipts record actual execution. Offline
                # policy flags remain untouched and are not promoted in place.
                result = dict(direction=policy.direction, verified_sha256=expected,
                              full_flash_readback_verified=True, sectors_written=result['sectors_written'],
                              boot_observed=False, kernel_exclusivity=False)
                results.append(result)
                log('direction_verified', **result)
            log('rehearsal_completed', directions=results, stock_baseline_restored=True,
                boot_observed=False, physical_recovery_verified=False)
            with bridge.private_file(receipt / 'result.json', 'w') as fp:
                json.dump(dict(campaign_sha256=prepared.campaign_sha256, directions=results,
                               stock_baseline_restored=True, boot_observed=False,
                               physical_recovery_verified=False), fp, indent=2)
                fp.write('\n'); fp.flush(); os.fsync(fp.fileno())
            bridge.sync_dir(receipt)
            return results
        except BaseException as exc:
            try:
                (receipt / 'result.json').unlink(missing_ok=True)
                bridge.sync_dir(receipt)
            except OSError:
                pass  # Exit failure and log acceptance still forbid success.
            try:
                log('rehearsal_stopped_ambiguous', error=type(exc).__name__, detail=str(exc), retry=False,
                    stock_baseline_restored=False, boot_observed=False)
            except OSError:
                pass
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__ == '__main__':
    main()
