#!/usr/bin/env python3
"""One FC0C argument-1 request from the reviewed fixed-loader backup session.

Baseline stock-return policy only. The bench owner seals the campaign after
checking backup exit status and absence of later commands. No upload, status
probe, flash operation, retry, enumeration or boot-success claim is provided.
MIT; SG layout/framing credits kagaimiq (Andrey Grigoryev), jl-uboot-tool.
"""
import argparse
import ctypes as C
from dataclasses import dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import types
from weakref import WeakSet

BACKUP_SOURCE_SHA = '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb'
READER_SHA = '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57'
INVENTORY_SHA = 'f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017'
RESET_CDB = bytes.fromhex('fc0c00000001ffffffffffffffffffff')
LIVE_SECONDS = 10
_PREPARED = object()
_AUTHORIZED = WeakSet()  # Exact factory instances only, including frozen dataclasses.


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def bounded_file(path, limit):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute direct file required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Regular file required')
        data = fp.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Evidence exceeds bounded size')
    return data


def pinned_file(path, expected, limit=2 * 1024 * 1024):
    data = bounded_file(path, limit)
    if digest(data) != expected:
        raise ValueError('Pinned evidence differs: ' + str(path))
    return data


def load_bridge(path):
    source = pinned_file(path, BACKUP_SOURCE_SHA)
    bridge = types.ModuleType('_fm1_reset_verified_backup')
    bridge.__file__ = str(path)
    exec(compile(source, str(path), 'exec'), bridge.__dict__)
    reader_path = Path(path).with_name('fm1_uboot_read.py')
    source = pinned_file(reader_path, READER_SHA)
    reader = types.ModuleType('_fm1_reset_verified_reader')
    exec(compile(source, str(reader_path), 'exec'), reader.__dict__)
    if C.sizeof(reader.SGHeader) != 88:
        raise ValueError('Reviewed 64-bit Linux SG_IO layout required')
    return bridge, reader.SGHeader


@dataclass(frozen=True, eq=False)
class PreparedReset:
    token: object
    campaign: bytes
    campaign_sha256: str
    backup_manifest_sha256: str
    expected_mapping: bytes
    bridge: object
    header_type: type


def validate_commands(raw, manifest, campaign, bridge):
    events = [json.loads(line) for line in raw.decode('utf8').splitlines()]
    if (len(events) != 17516 or events[0].get('event') != 'campaign_prepared' or
            events[-1].get('event') != 'campaign_completed'):
        raise ValueError('Exact successful backup log required')
    times = [e.get('time') for e in events]
    if (not all(type(t) in (int, float) and math.isfinite(t) for t in times) or
            times != sorted(times) or times[-1] > time.time()):
        raise ValueError('Invalid backup chronology')
    first = events[0]
    expected = dict(campaign_sha256=manifest['campaign_sha256'],
        adapter_sha256=BACKUP_SOURCE_SHA, loader_sha256=bridge.LOADER_SHA,
        profile_sha256=bridge.PROFILE_SHA, profile_source_sha256=bridge.PROFILE_SOURCE_SHA,
        reader_sha256=READER_SHA, entry_log_sha256=manifest['entry_log_sha256'],
        usb_binding=manifest['usb_binding'], commands=8757,
        request_inventory_sha256=INVENTORY_SHA,
        kernel_exclusivity=False, physical_recovery_verified=False)
    if any(first.get(k) != v for k, v in expected.items()):
        raise ValueError('Backup prepared event differs')
    inventory = []
    for index in range(8757):
        intent, completion = events[1 + 2 * index:3 + 2 * index]
        if (intent.get('event') != 'sg_submit_intent' or completion.get('event') != 'sg_completion' or
                intent.get('index') != index or completion.get('index') != index or
                intent.get('retry') is not False or completion.get('retry') is not False or
                any(type(completion.get(k)) is not int or completion[k] != 0 for k in
                    ('status', 'masked', 'msg', 'host', 'driver', 'resid', 'info', 'sense_len')) or
                completion.get('sense_hex') != ''):
            raise ValueError('Backup command completion differs')
        inventory.append({k: intent.get(k) for k in
            ('phase', 'cdb', 'label', 'payload_sha256', 'out_len', 'in_len')})
    if digest(canonical(inventory)) != INVENTORY_SHA:
        raise ValueError('Backup request inventory differs')
    last = events[-1]
    if (last.get('identical') is not True or last.get('bytes_per_dump') != 1048576 or
            last.get('physical_recovery_verified') is not False or last.get('retry') is not False):
        raise ValueError('Backup completion claim differs')
    bridge.validate_entry(bridge.pinned_file(campaign['entry_log_path'],
        manifest['entry_log_sha256']), manifest['usb_binding'], times[-1])
    return times[-1]


def prepare_campaign(path):
    """Read/hash all review inputs before any sysfs discovery or device open."""
    raw = bounded_file(Path(path).absolute(), 65536)
    config = json.loads(raw)
    required = {'schema', 'kind', 'adapter_sha256', 'backup_adapter_path',
        'backup_manifest_path', 'backup_manifest_sha256', 'backup_campaign_path',
        'backup_campaign_sha256', 'backup_commands_sha256', 'backup_exit_status',
        'active_session_state', 'usb_binding', 'sg_binding', 'receipt_path'}
    if (set(config) != required or config['schema'] != 1 or
            config['kind'] != 'fm1-fixed-loader-baseline-reset-campaign' or
            type(config['backup_exit_status']) is not int or config['backup_exit_status'] != 0 or
            config['active_session_state'] != 'matching-backup-no-later-commands'):
        raise ValueError('Exact baseline reset policy required')
    pinned_file(Path(__file__).absolute(), config['adapter_sha256'])
    bridge, header = load_bridge(config['backup_adapter_path'])
    manifest_path = Path(config['backup_manifest_path'])
    manifest = json.loads(pinned_file(manifest_path, config['backup_manifest_sha256'], 65536))
    campaign = json.loads(pinned_file(config['backup_campaign_path'], config['backup_campaign_sha256'], 65536))
    bridge.validate_usb(config['usb_binding'])
    expected = dict(schema=1, kind='fm1-fixed-loader-backup', loader_sha256=bridge.LOADER_SHA,
        original_loader_sha256=bridge.ORIGINAL_SHA, loader_profile_sha256=bridge.PROFILE_SHA,
        profile_source_sha256=bridge.PROFILE_SOURCE_SHA, adapter_sha256=BACKUP_SOURCE_SHA,
        dependency_sha256={'fm1_uboot_read.py': READER_SHA},
        campaign_sha256=config['backup_campaign_sha256'], request_inventory_sha256=INVENTORY_SHA,
        unit_identity='FM-1_092', usb_binding=config['usb_binding'], sg_binding=config['sg_binding'],
        flash_bytes=1048576, identical=True, command_completions=True, commands=8757,
        flash_readback_only=True, physical_recovery_verified=False, kernel_exclusivity=False)
    if (set(manifest) != set(expected) | {'dumps', 'entry_log_sha256'} or
            any(canonical(manifest[k]) != canonical(v) for k, v in expected.items())):
        raise ValueError('Exact fixed-loader backup manifest required')
    campaign_keys = {'schema', 'kind', 'adapter_sha256', 'loader_path', 'profile_path',
        'profile_source_path', 'entry_log_path', 'entry_log_sha256', 'usb_binding', 'receipt_path'}
    if (set(campaign) != campaign_keys or campaign['schema'] != 1 or
            campaign['kind'] != 'fm1-fixed-loader-backup-campaign' or
            campaign['adapter_sha256'] != BACKUP_SOURCE_SHA or
            campaign['usb_binding'] != config['usb_binding'] or
            campaign['entry_log_sha256'] != manifest['entry_log_sha256'] or
            Path(campaign['receipt_path']) != manifest_path.parent):
        raise ValueError('Backup campaign binding differs')
    if len(bridge.pinned_file(campaign['loader_path'], bridge.LOADER_SHA)) != 24064:
        raise ValueError('Candidate length differs')
    bridge.pinned_file(campaign['profile_path'], bridge.PROFILE_SHA)
    bridge.pinned_file(campaign['profile_source_path'], bridge.PROFILE_SOURCE_SHA)
    dumps = manifest['dumps']
    if not isinstance(dumps, list) or len(dumps) != 2:
        raise ValueError('Two complete dumps required')
    for entry, name in zip(dumps, ('dumpA.bin', 'dumpB.bin')):
        if (set(entry) != {'file', 'bytes', 'sha256', 'complete'} or
                entry['file'] != name or entry['bytes'] != 1048576 or entry['complete'] is not True or
                len(bridge.pinned_file(manifest_path.parent / name, entry['sha256'])) != 1048576):
            raise ValueError('Complete private dump differs')
    if dumps[0]['sha256'] != dumps[1]['sha256']:
        raise ValueError('Backup dumps differ')
    validate_commands(pinned_file(manifest_path.parent / 'commands.jsonl',
        config['backup_commands_sha256'], 8 * 1024 * 1024), manifest, campaign, bridge)
    destination = Path(config['receipt_path'])
    if (not destination.is_absolute() or destination.exists() or
            destination.parent != manifest_path.parent or
            not stat.S_ISDIR(destination.parent.lstat().st_mode) or
            destination.parent.stat().st_mode & 0o777 != 0o700):
        raise ValueError('New reset receipt must be under the pinned private backup receipt')
    # JSON normalization makes sysfs stat tuples comparable to recorded lists.
    prepared = PreparedReset(_PREPARED, canonical(config), digest(raw),
        config['backup_manifest_sha256'], canonical(config['sg_binding']), bridge, header)
    _AUTHORIZED.add(prepared)
    return prepared


class ResetSG:
    """Only the literal reset CDB, consumed before any binding/log/syscall."""
    def __init__(self, prepared, log):
        if not isinstance(prepared, PreparedReset) or prepared.token is not _PREPARED or prepared not in _AUTHORIZED:
            raise ValueError('Prepared baseline reset required')
        self.prepared, self.log = prepared, log
        self.fd, self.consumed, self.failed, self.ioctl_attempts = None, False, False, 0
        self.phase = 'active-fixed-loader'
        self.started = time.monotonic()
        config = json.loads(prepared.campaign)
        self.usb = config['usb_binding']
        try:
            self.mapping = prepared.bridge.discover_sg(self.usb)
            if canonical(self.mapping) != prepared.expected_mapping:
                raise ValueError('Backup SG connection replaced')
            self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.binding()
        except BaseException:
            self.failed = True
            self.close()
            raise

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)

    def binding(self):
        if self.fd is None or not 0 <= time.monotonic() - self.started <= LIVE_SECONDS:
            raise ValueError('Closed or stale active binding')
        opened = os.fstat(self.fd)
        if (not stat.S_ISCHR(opened.st_mode) or
                canonical((opened.st_dev, opened.st_ino, opened.st_rdev)) != canonical(self.mapping['node_identity']) or
                canonical(self.prepared.bridge.discover_sg(self.usb)) != self.prepared.expected_mapping):
            raise ValueError('Bound SG/sysfs/USB connection replaced')

    def request_reset(self):
        try:
            if self.consumed or self.failed or self.fd is None:
                raise ValueError('Reset attempt already consumed or closed')
            self.consumed = True
            command, sense, data = C.create_string_buffer(RESET_CDB), C.create_string_buffer(32), C.create_string_buffer(16)
            h = self.prepared.header_type(interface_id=ord('S'), direction=-3, cmd_len=16,
                sense_max=32, data_len=16, data=C.addressof(data), cmd=C.addressof(command),
                sense=C.addressof(sense), timeout=3000)
            self.log('reset_submit_intent', phase=self.phase, cdb=RESET_CDB.hex(),
                     in_len=16, out_len=0, retry=False, boot_observed=False)
            self.binding()
            self.ioctl_attempts += 1
            fcntl.ioctl(self.fd, 0x2285, h)
            self.binding()
            self.log('reset_sg_completion', status=h.status, masked=h.masked, msg=h.msg,
                host=h.host, driver=h.driver, resid=h.resid, info=h.info, sense_len=h.sense_len,
                sense_hex=sense.raw[:min(h.sense_len, 32)].hex(), retry=False, boot_observed=False)
            if (h.status or h.masked or h.msg or h.host or h.driver or h.resid or h.info & 1 or
                    h.sense_len or data.raw[:2] != RESET_CDB[:2]):
                raise OSError('Reset reply incomplete or ambiguous')
            self.phase = 'request-completed-boot-unobserved'
            return {'request_completion': True, 'core_reset_observed': False, 'boot_observed': False}
        except BaseException:
            self.failed = True
            self.phase = 'reset-ambiguous-closed'
            raise
        finally:
            try:
                self.close()
            except BaseException:
                self.failed = True
                self.phase = 'reset-ambiguous-closed'
                raise


def run_campaign(prepared):
    if not isinstance(prepared, PreparedReset) or prepared.token is not _PREPARED or prepared not in _AUTHORIZED:
        raise ValueError('Prepared baseline reset required')
    config, bridge = json.loads(prepared.campaign), prepared.bridge
    receipt = Path(config['receipt_path'])
    receipt.mkdir(mode=0o700, exist_ok=False)
    bridge.sync_dir(receipt.parent)
    # Marker lives in the backup receipt, so changing reset receipt names or
    # campaign destination cannot reuse the same active baseline session.
    with bridge.private_file(receipt.parent / '.baseline-core-reset.consumed') as fp:
        fp.write(prepared.campaign_sha256.encode('ascii')); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(receipt.parent)
    with bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields)) + '\n')
            events.flush(); os.fsync(events.fileno()); bridge.sync_dir(receipt)

        transport = None
        try:
            log('reset_campaign_prepared', campaign_sha256=prepared.campaign_sha256,
                backup_manifest_sha256=prepared.backup_manifest_sha256,
                adapter_sha256=config['adapter_sha256'], backup_adapter_sha256=BACKUP_SOURCE_SHA,
                usb_binding=config['usb_binding'], sg_binding=config['sg_binding'], commands=1,
                flash_operations=0, upload_operations=0, kernel_exclusivity=False,
                core_reset_observed=False, boot_observed=False)
            transport = ResetSG(prepared, log)
            result = transport.request_reset()
            log('reset_request_completed', **result, retry=False)
            return result
        except BaseException as exc:
            try:
                log('reset_stopped_ambiguous', error=type(exc).__name__, detail=str(exc),
                    retry=False, core_reset_observed=False, boot_observed=False)
            except OSError:
                pass
            raise
        finally:
            if transport is not None:
                transport.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__ == '__main__':
    main()
