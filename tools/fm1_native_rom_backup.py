#!/usr/bin/env python3
"""MIT. Fresh native-probe ROM -> audited fixed RAM loader -> two full reads.

No soft-key history is invented. Owner identity is historical; the fresh
INQUIRY establishes chip and ROM mode. No NOR write, reset or retry exists.
Protocol credit: kagaimiq/jl-uboot-tool through the pinned existing adapters.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time

from tools.fm1_repeat_rom_backup import load_source, read_file

SOURCES = {
    'fm1_fixed_loader_backup.py': '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb',
    'fm1_returned_rom_backup.py': 'afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be',
    'fm1_uboot_read.py': '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57',
}
TARGET_SHA = '770fd5f275110f017329dda30315343d766ff4a6c6beaa62f5a0060c629dc561'
KIND = 'fm1-native-probe-returned-rom-fixed-loader-dual-read'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_observation(c, now):
    required = {'schema', 'kind', 'adapter_sha256', 'observed_at', 'usb_binding',
                'loader_path', 'profile_path', 'profile_source_path', 'receipt_path'}
    if set(c) != required or type(c['schema']) is not int or c['schema'] != 1 or c['kind'] != KIND:
        raise ValueError('Exact fresh ROM read envelope required')
    observed = c['observed_at']
    if (type(observed) not in (float, int) or not math.isfinite(observed) or
            not 0 <= now - observed <= 120):
        raise ValueError('Fresh passive observation required')


def prepare(path):
    raw = read_file(Path(path).absolute(), 65536)
    c = json.loads(raw)
    validate_observation(c, time.time())
    root = Path(__file__).absolute().parent
    if digest(read_file(Path(__file__).absolute())) != c['adapter_sha256']:
        raise ValueError('Adapter source changed')
    modules = {name: load_source(root/name, pin, '_fresh_'+name[:-3])
               for name, pin in SOURCES.items()}
    bridge = modules['fm1_fixed_loader_backup.py']
    reader = modules['fm1_uboot_read.py']
    bridge.validate_usb(c['usb_binding'])
    mapping = bridge.discover_sg(c['usb_binding'])
    loader = bridge.pinned_file(c['loader_path'], bridge.LOADER_SHA)
    profile = json.loads(bridge.pinned_file(c['profile_path'], bridge.PROFILE_SHA))
    bridge.pinned_file(c['profile_source_path'], bridge.PROFILE_SOURCE_SHA)
    if len(loader) != bridge.LOADER_SIZE or ctypes.sizeof(reader.SGHeader) != 88:
        raise ValueError('Exact loader and Linux SG ABI required')
    ops = modules['fm1_returned_rom_backup.py'].inventory(bridge, reader, loader, profile)
    if len(ops) != 8757:
        raise ValueError('Exact dual-read inventory required')
    receipt = Path(c['receipt_path'])
    parent = receipt.parent
    if (not receipt.is_absolute() or os.path.lexists(receipt) or
            not stat.S_ISDIR(parent.lstat().st_mode) or stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('New receipt in direct private directory required')
    # Consumption is keyed to the physical enumeration, not a caller-selected
    # campaign hash or receipt name; changing JSON cannot authorize a retry.
    usb = c['usb_binding']
    marker = parent / ('.rom-'+usb['path']+'-'+usb['devnum']+'.consumed')
    if os.path.lexists(marker):
        raise ValueError('Enumeration already consumed')
    p = bridge.PreparedCampaign(c, digest(raw), loader, ops, reader.SGHeader,
                                c['observed_at'], bridge.inventory_digest(ops))
    return bridge, p, mapping, marker


def run(path):
    started = time.monotonic()
    bridge, p, mapping, marker = prepare(path)
    receipt = Path(p.config['receipt_path'])
    receipt.mkdir(mode=0o700, exist_ok=False)
    bridge.sync_dir(receipt.parent)
    with bridge.private_file(marker) as fp:
        fp.write(p.manifest_sha256.encode()); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(marker.parent)
    transport = None
    with bridge.private_file(receipt/'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields), allow_nan=False)+'\n')
            events.flush()
            if event != 'sg_completion' and (event != 'sg_submit_intent' or fields.get('phase') == 'rom'):
                os.fsync(events.fileno())
        try:
            log('fresh_rom_backup_prepared', campaign_sha256=p.manifest_sha256,
                inventory_sha256=p.request_inventory_sha256, commands=8757,
                loader_sha256=bridge.LOADER_SHA, flash_operations=0, reset_operations=0,
                historical_unit_identity='FM-1_092', retry=False)
            transport = bridge.FixedSG(p, log)
            if transport.mapping != mapping:
                raise ValueError('Mapping changed before open')
            dumps = []
            for name in ('dumpA.bin', 'dumpB.bin'):
                with bridge.private_file(receipt/name) as fp:
                    while transport.next < len(p.operations):
                        pending = p.operations[transport.next]
                        if pending.label not in ('inquiry','upload','jump','buffer','online',name,name+'.end'):
                            break
                        if time.monotonic()-started > 120:
                            raise ValueError('Read campaign time bound exceeded')
                        op, data = transport.exchange_next()
                        if op.label == name: fp.write(data)
                        if op.label == name+'.end': break
                    fp.flush(); os.fsync(fp.fileno())
                data = read_file(receipt/name)
                if len(data) != 1048576 or digest(data) != TARGET_SHA:
                    raise ValueError('Complete exact native controls read required')
                dumps.append(dict(file=name, bytes=len(data), sha256=digest(data)))
            transport.binding()
            if transport.next != len(p.operations):
                raise ValueError('Incomplete command sequence')
            transport.close()
            log('fresh_rom_backup_completed', flash_operations=0, reset_operations=0, retry=False)
            result = dict(schema=1, kind=KIND, campaign_sha256=p.manifest_sha256,
                adapter_sha256=p.config['adapter_sha256'], source_sha256=SOURCES,
                usb_binding=p.config['usb_binding'], sg_binding=mapping,
                loader_sha256=bridge.LOADER_SHA, request_inventory_sha256=p.request_inventory_sha256,
                commands=8757, current_flash_sha256=TARGET_SHA, dumps=dumps, identical=True,
                flash_operations=0, reset_operations=0, physical_recovery_verified=False)
            with bridge.private_file(receipt/'manifest.json','w') as fp:
                json.dump(result,fp,sort_keys=True); fp.write('\n'); fp.flush(); os.fsync(fp.fileno())
            bridge.sync_dir(receipt)
            return result
        except BaseException as exc:
            log('fresh_rom_backup_stopped', error=type(exc).__name__, retry=False)
            raise
        finally:
            if transport is not None: transport.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if args.preflight:
        _, p, _, _ = prepare(args.campaign)
        print(json.dumps(dict(commands=len(p.operations), flash_operations=0, reset_operations=0)))
    else:
        print(json.dumps(run(args.campaign)))
