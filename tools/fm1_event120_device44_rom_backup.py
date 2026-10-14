#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only device-44 ROM identity repeat: exact fixed loader and dual full dumps.

The receipt establishes only that two completed 1 MiB reads match the fixed
installed-image digest. It is not installation-history, boot, or recovery proof.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import types

TARGET_SHA = '145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657'
KIND = 'fm1-device44-event120-repeat-rom-read'
SNAPSHOT_KIND = 'fm1-passive-device44-rom'
USB = {'path': '1-1', 'busnum': '1', 'devnum': '44', 'vid': '4c4a', 'pid': '8057'}
MAX_AGE = 120
MAX_RUN_SECONDS = 180
SOURCES = {
    'fm1_fixed_loader_backup.py': '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb',
    'fm1_returned_rom_backup.py': 'afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be',
    'fm1_uboot_read.py': '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57',
}
INVENTORY_SHA = 'f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Duplicate JSON key')
        out[key] = value
    return out


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        with os.fdopen(fd, 'rb') as fp:
            if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
                raise ValueError('Regular evidence file required')
            data = fp.read(limit + 1)
    except BaseException:
        try: os.close(fd)
        except OSError: pass
        raise
    if len(data) > limit:
        raise ValueError('Evidence exceeds size bound')
    return data


def load_source(path, expected, name):
    raw = read_file(Path(path).absolute())
    if digest(raw) != expected:
        raise ValueError('Pinned source differs: ' + str(path))
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def _snapshot(raw, now):
    value = json.loads(raw, object_pairs_hook=unique_object,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON number')))
    keys = {'schema', 'kind', 'observed_at', 'usb_binding', 'sg_binding'}
    if (not isinstance(value, dict) or set(value) != keys or type(value['schema']) is not int or
            value['schema'] != 1 or value['kind'] != SNAPSHOT_KIND or
            type(value['observed_at']) not in (int, float) or not math.isfinite(value['observed_at']) or
            not 0 <= now - value['observed_at'] <= MAX_AGE or value['usb_binding'] != USB or
            not isinstance(value['sg_binding'], dict)):
        raise ValueError('Fresh exact passive device-44 ROM snapshot required')
    return value


def _private_destination(receipt):
    receipt = Path(receipt)
    parent = receipt.parent
    if (not receipt.is_absolute() or os.path.lexists(receipt) or
            not stat.S_ISDIR(parent.lstat().st_mode) or stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('New receipt under direct mode-0700 directory required')
    return receipt


def marker_path(parent, usb_binding, sg_binding):
    identity = digest(canonical({'usb_binding': usb_binding, 'sg_binding': sg_binding}))
    return Path(parent) / ('.event12044-rom-' + identity + '.consumed')


def prepare(path, *, now=None):
    now = time.time() if now is None else now
    campaign_path = Path(path).absolute()
    raw = read_file(campaign_path, 65536)
    c = json.loads(raw, object_pairs_hook=unique_object,
                   parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON number')))
    fields = {'schema', 'kind', 'adapter_sha256', 'snapshot_path', 'snapshot_sha256',
              'loader_path', 'profile_path', 'profile_source_path', 'usb_binding', 'receipt_path'}
    if (not isinstance(c, dict) or set(c) != fields or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != KIND):
        raise ValueError('Exact device-44 read campaign required')
    own = Path(__file__).absolute()
    if digest(read_file(own)) != c['adapter_sha256']:
        raise ValueError('Adapter source hash differs')
    snapshot_path = Path(c['snapshot_path'])
    snapshot_raw = read_file(snapshot_path, 65536)
    if digest(snapshot_raw) != c['snapshot_sha256']:
        raise ValueError('Passive snapshot hash differs')
    snapshot = _snapshot(snapshot_raw, now)
    if c['usb_binding'] != snapshot['usb_binding']:
        raise ValueError('Campaign USB binding differs from passive snapshot')
    receipt = _private_destination(c['receipt_path'])
    if (snapshot_path.parent != receipt.parent or campaign_path.parent != receipt.parent or
            campaign_path.name != 'read-campaign.json'):
        raise ValueError('Snapshot, campaign and receipt must share the private evidence root')

    root = own.parent
    modules = {name: load_source(root / name, sha, '_event12044_' + name[:-3])
               for name, sha in SOURCES.items()}
    bridge = modules['fm1_fixed_loader_backup.py']
    reader = modules['fm1_uboot_read.py']
    bridge.validate_usb(snapshot['usb_binding'])
    mapping = bridge.discover_sg(snapshot['usb_binding'])
    if canonical(mapping) != canonical(snapshot['sg_binding']):
        raise ValueError('Live passive SG mapping differs from frozen snapshot')
    loader = bridge.pinned_file(c['loader_path'], bridge.LOADER_SHA)
    profile = json.loads(bridge.pinned_file(c['profile_path'], bridge.PROFILE_SHA))
    bridge.pinned_file(c['profile_source_path'], bridge.PROFILE_SOURCE_SHA)
    if len(loader) != bridge.LOADER_SIZE or ctypes.sizeof(reader.SGHeader) != 88:
        raise ValueError('Exact fixed loader or reviewed Linux SG ABI required')
    operations = modules['fm1_returned_rom_backup.py'].inventory(bridge, reader, loader, profile)
    inventory_sha = bridge.inventory_digest(operations)
    if len(operations) != 8757 or inventory_sha != INVENTORY_SHA:
        raise ValueError('Exact reviewed 8,757-command inventory required')
    marker = marker_path(receipt.parent, snapshot['usb_binding'], mapping)
    if os.path.lexists(marker):
        raise ValueError('This passive enumeration is already consumed')
    prepared = bridge.PreparedCampaign(c, digest(raw), loader, operations, reader.SGHeader,
                                       snapshot['observed_at'], inventory_sha)
    evidence = {'campaign': raw, 'snapshot': snapshot_raw,
                'source_sha256': SOURCES, 'loader_sha256': bridge.LOADER_SHA,
                'profile_sha256': bridge.PROFILE_SHA,
                'profile_source_sha256': bridge.PROFILE_SOURCE_SHA}
    return bridge, prepared, mapping, marker, evidence


def run(path):
    started = time.monotonic()
    bridge, p, mapping, marker, evidence = prepare(path)
    c = p.config
    receipt = Path(c['receipt_path'])
    receipt.mkdir(mode=0o700, exist_ok=False)
    bridge.sync_dir(receipt.parent)
    with bridge.private_file(marker) as fp:
        fp.write(p.manifest_sha256.encode('ascii')); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(receipt.parent)
    transport = None
    with bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields), allow_nan=False) + '\n')
            events.flush()
            if event != 'sg_completion':
                os.fsync(events.fileno())
        try:
            log('device44_rom_read_prepared', campaign_sha256=p.manifest_sha256,
                adapter_sha256=c['adapter_sha256'], snapshot_sha256=c['snapshot_sha256'],
                usb_binding=USB, sg_binding=mapping, loader_sha256=bridge.LOADER_SHA,
                profile_sha256=bridge.PROFILE_SHA, profile_source_sha256=bridge.PROFILE_SOURCE_SHA,
                reader_sha256=SOURCES['fm1_uboot_read.py'], commands=len(p.operations),
                request_inventory_sha256=p.request_inventory_sha256,
                expected_current_flash_sha256=TARGET_SHA, flash_operations=0,
                reset_operations=0, upload_operations=47, install_history_proven=False,
                boot_observed=False, physical_recovery_verified=False, retry=False)
            transport = bridge.FixedSG(p, log)
            if canonical(transport.mapping) != canonical(mapping):
                raise ValueError('SG mapping changed before opener')
            dumps = []
            for name in ('dumpA.bin', 'dumpB.bin'):
                hasher, count = hashlib.sha256(), 0
                with bridge.private_file(receipt / name) as fp:
                    while transport.next < len(p.operations):
                        if time.monotonic() - started > MAX_RUN_SECONDS:
                            raise ValueError('Bounded read deadline exceeded')
                        pending = p.operations[transport.next]
                        if pending.label not in ('inquiry', 'upload', 'jump', 'buffer', 'online', name, name + '.end'):
                            break
                        op, data = transport.exchange_next()
                        if op.label == name:
                            fp.write(data); hasher.update(data); count += len(data)
                        if op.label == name + '.end':
                            break
                    fp.flush(); os.fsync(fp.fileno())
                bridge.sync_dir(receipt)
                record = {'file': name, 'bytes': count, 'sha256': hasher.hexdigest(), 'complete': count == bridge.FLASH_SIZE}
                if count != bridge.FLASH_SIZE or record['sha256'] != TARGET_SHA:
                    raise ValueError('Full dump differs count=' + str(count) + ' sha=' + record['sha256'] + ' expected=' + TARGET_SHA)
                dumps.append(record)
            transport.binding()
            if transport.next != len(p.operations) or dumps[0]['sha256'] != dumps[1]['sha256']:
                raise ValueError('Incomplete command sequence or nonidentical full reads')
            transport.close(); transport = None
            log('device44_rom_read_completed', identical=True, current_flash_sha256=TARGET_SHA,
                dumps=dumps, commands=len(p.operations), request_inventory_sha256=p.request_inventory_sha256,
                flash_operations=0, reset_operations=0, install_history_proven=False,
                boot_observed=False, physical_recovery_verified=False, retry=False)
            commands_path = receipt / 'commands.jsonl'
            events.flush(); os.fsync(events.fileno())
            commands_sha256 = digest(read_file(commands_path, 16 * 1048576))
            manifest = {'schema': 1, 'kind': KIND, 'campaign_path': str(Path(path).absolute()),
                'campaign_sha256': p.manifest_sha256, 'adapter_sha256': c['adapter_sha256'],
                'source_sha256': SOURCES, 'snapshot_path': c['snapshot_path'],
                'snapshot_sha256': c['snapshot_sha256'], 'usb_binding': USB,
                'sg_binding': mapping, 'loader_sha256': bridge.LOADER_SHA,
                'loader_profile_sha256': bridge.PROFILE_SHA,
                'profile_source_sha256': bridge.PROFILE_SOURCE_SHA,
                'reader_sha256': SOURCES['fm1_uboot_read.py'],
                'request_inventory_sha256': p.request_inventory_sha256,
                'commands': len(p.operations), 'flash_bytes': bridge.FLASH_SIZE,
                'expected_current_flash_sha256': TARGET_SHA,
                'current_flash_sha256': TARGET_SHA, 'commands_sha256': commands_sha256,
                'dumps': dumps, 'identical': True,
                'flash_operations': 0, 'reset_operations': 0, 'install_history_proven': False,
                'boot_observed': False, 'physical_recovery_verified': False,
                'kernel_exclusivity': False}
            with bridge.private_file(receipt / 'manifest.json', 'w') as fp:
                json.dump(manifest, fp, sort_keys=True, allow_nan=False); fp.write('\n'); fp.flush(); os.fsync(fp.fileno())
            bridge.sync_dir(receipt)
            return manifest
        except BaseException as exc:
            if transport is not None:
                transport.failed = True; transport.close()
            try:
                (receipt / 'manifest.json').unlink(missing_ok=True); bridge.sync_dir(receipt)
            except OSError:
                pass
            try:
                log('device44_rom_read_stopped', error=type(exc).__name__, retry=False,
                    install_history_proven=False, boot_observed=False)
            except OSError:
                pass
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args(); os.umask(0o077)
    if args.preflight:
        _, p, _, _, _ = prepare(args.campaign)
        print(json.dumps({'commands': len(p.operations), 'flash_operations': 0, 'reset_operations': 0}))
    else:
        print(json.dumps(run(args.campaign), sort_keys=True))


if __name__ == '__main__':
    if sys.platform != 'linux':
        raise SystemExit('Linux SG_IO only')
    main()
