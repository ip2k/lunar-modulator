#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One bounded FC0C arg1 after fresh matching device-40 dual ROM reads.

This authorizes only a request against the exact current flash digest. It does
not prove installation history, processor reset, app boot, or recovery.
"""
import argparse
import ctypes
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

ROOT = Path(__file__).resolve().parents[1]
READ_ADAPTER_SHA = '6bffb25e2f55184219baca5007a16fe05a3568c2f911a86fc6e6981ab7874342'
INVENTORY_SHA = 'f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017'
READ_KIND = 'fm1-device40-event120-repeat-rom-read'
MAX_AGE = 120
TARGET_SHA = '145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657'
USB = {'path': '1-1', 'busnum': '1', 'devnum': '40', 'vid': '4c4a', 'pid': '8057'}
READ_SOURCES = {
    'fm1_fixed_loader_backup.py': '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb',
    'fm1_returned_rom_backup.py': 'afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be',
    'fm1_uboot_read.py': '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57',
}


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
        try:
            os.close(fd)
        except OSError:
            pass
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


KIND = 'fm1-device40-event120-repeat-boot'
BOOT_SNAPSHOT_KIND = 'fm1-passive-device40-boot-same-connection'
ACTIVE_SESSION = 'same-device40-rom-connection-after-matching-read-no-later-commands'
TARGET_RESET_SHA = 'b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a'
RESET_BASE_SHA = 'dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116'
COMPLETION_RESET_SHA = 'f7b75e3448fe30babaed23b70340bab76db1e2c8815d13d22c6bdb00116a770c'
RESET_CDB = bytes.fromhex('fc0c00000001ffffffffffffffffffff')
_AUTHORIZED = WeakSet()


def _json(raw):
    return json.loads(raw, object_pairs_hook=unique_object,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON number')))


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _hash_pin(path, expected, limit=32 * 1048576):
    raw = read_file(path, limit)
    if digest(raw) != expected:
        raise ValueError('Pinned evidence hash differs: ' + str(path))
    return raw


def _rom_marker_path(parent, usb_binding, sg_binding):
    identity = digest(canonical({'usb_binding': usb_binding, 'sg_binding': sg_binding}))
    return Path(parent) / ('.event12040-rom-' + identity + '.consumed')


def _read_snapshot_fresh_at_start(observed_at, prepared_at):
    return (_finite(observed_at) and _finite(prepared_at) and
            prepared_at - MAX_AGE <= observed_at <= prepared_at)


def _snapshot(raw, *, now, earliest):
    value = _json(raw)
    keys = {'schema', 'kind', 'observed_at', 'usb_binding', 'sg_binding'}
    if (not isinstance(value, dict) or set(value) != keys or type(value['schema']) is not int or
            value['schema'] != 1 or value['kind'] != BOOT_SNAPSHOT_KIND or
            not _finite(value['observed_at']) or not earliest <= value['observed_at'] <= now or
            not 0 <= now - value['observed_at'] <= MAX_AGE or value['usb_binding'] != USB or
            not isinstance(value['sg_binding'], dict)):
        raise ValueError('Fresh exact same-session device-40 snapshot required')
    return value


def _source_modules(root):
    target_path = root / 'fm1_fixed_target_reset.py'
    target = load_source(target_path, TARGET_RESET_SHA, '_event12040_fixed_target_reset')
    previous = sys.modules.get('fm1_fixed_target_reset')
    sys.modules['fm1_fixed_target_reset'] = target
    try:
        completion_path = root / 'native/event120_reset.py'
        completion = load_source(completion_path, COMPLETION_RESET_SHA, '_event12040_completion_reset')
    finally:
        if previous is None:
            sys.modules.pop('fm1_fixed_target_reset', None)
        else:
            sys.modules['fm1_fixed_target_reset'] = previous
    fixed_reset_path = root / 'fm1_fixed_loader_reset.py'
    if digest(read_file(fixed_reset_path)) != RESET_BASE_SHA:
        raise ValueError('Reviewed fixed-loader reset source differs')
    return target, completion


def _live_mapping(bridge, usb):
    return bridge.discover_sg(usb)


def verify_read_bundle(manifest_path, manifest_sha, commands_sha, *, now=None):
    """Replay fixed inventory and verify both durable full-image reads."""
    now = time.time() if now is None else now
    manifest_path = Path(manifest_path).absolute()
    manifest_raw = _hash_pin(manifest_path, manifest_sha, 65536)
    manifest = _json(manifest_raw)
    fields = {'schema', 'kind', 'campaign_path', 'campaign_sha256', 'adapter_sha256',
        'source_sha256', 'snapshot_path', 'snapshot_sha256', 'usb_binding', 'sg_binding',
        'loader_sha256', 'loader_profile_sha256', 'profile_source_sha256', 'reader_sha256',
        'request_inventory_sha256', 'commands', 'flash_bytes', 'expected_current_flash_sha256',
        'current_flash_sha256', 'commands_sha256', 'dumps', 'identical', 'flash_operations',
        'reset_operations', 'install_history_proven', 'boot_observed',
        'physical_recovery_verified', 'kernel_exclusivity'}
    if not isinstance(manifest, dict) or set(manifest) != fields:
        raise ValueError('Exact fresh read manifest fields required')
    if (type(manifest['schema']) is not int or manifest['schema'] != 1 or manifest['kind'] != READ_KIND or
            manifest['source_sha256'] != READ_SOURCES or manifest['usb_binding'] != USB or
            manifest['loader_sha256'] != 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c' or
            manifest['loader_profile_sha256'] != '3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe' or
            manifest['profile_source_sha256'] != '9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8' or
            manifest['reader_sha256'] != READ_SOURCES['fm1_uboot_read.py'] or
            manifest['request_inventory_sha256'] != INVENTORY_SHA or type(manifest['commands']) is not int or
            manifest['commands'] != 8757 or type(manifest['flash_bytes']) is not int or
            manifest['flash_bytes'] != 1048576 or manifest['expected_current_flash_sha256'] != TARGET_SHA or
            manifest['current_flash_sha256'] != TARGET_SHA or manifest['identical'] is not True or
            manifest['commands_sha256'] != commands_sha or manifest['flash_operations'] != 0 or
            manifest['reset_operations'] != 0 or manifest['install_history_proven'] is not False or
            manifest['boot_observed'] is not False or manifest['physical_recovery_verified'] is not False or
            manifest['kernel_exclusivity'] is not False):
        raise ValueError('Read manifest policy, identity or source binding differs')
    receipt = manifest_path.parent
    campaign_path = Path(manifest['campaign_path'])
    if (not campaign_path.is_absolute() or campaign_path.parent != receipt.parent or
            campaign_path.name != 'read-campaign.json'):
        raise ValueError('Read campaign must be a direct evidence-root member')
    campaign_raw = read_file(campaign_path, 65536)
    campaign = _json(campaign_raw)
    campaign_keys = {'schema','kind','adapter_sha256','snapshot_path','snapshot_sha256',
        'loader_path','profile_path','profile_source_path','usb_binding','receipt_path'}
    if (not isinstance(campaign,dict) or set(campaign) != campaign_keys or
            type(campaign['schema']) is not int or campaign['schema'] != 1 or
            digest(campaign_raw) != manifest['campaign_sha256'] or campaign['kind'] != READ_KIND or
            campaign['adapter_sha256'] != manifest['adapter_sha256'] or
            campaign['snapshot_path'] != manifest['snapshot_path'] or
            campaign['snapshot_sha256'] != manifest['snapshot_sha256'] or
            campaign['usb_binding'] != USB or campaign['receipt_path'] != str(receipt)):
        raise ValueError('Read campaign linkage differs')
    adapter_path = ROOT / 'fm1_event120_rom_backup.py'
    adapter_raw = read_file(adapter_path, 65536)
    if (manifest['adapter_sha256'] != READ_ADAPTER_SHA or
            digest(adapter_raw) != manifest['adapter_sha256']):
        raise ValueError('Fresh reader adapter source changed')
    snapshot_raw = _hash_pin(manifest['snapshot_path'], manifest['snapshot_sha256'], 65536)
    snapshot = _json(snapshot_raw)
    snapshot_keys = {'schema','kind','observed_at','usb_binding','sg_binding'}
    if (not isinstance(snapshot,dict) or set(snapshot) != snapshot_keys or
            type(snapshot['schema']) is not int or snapshot['schema'] != 1 or
            snapshot['kind'] != 'fm1-passive-device40-rom' or snapshot['usb_binding'] != USB or
            canonical(snapshot['sg_binding']) != canonical(manifest['sg_binding']) or
            not _finite(snapshot['observed_at'])):
        raise ValueError('Read snapshot mapping or freshness differs')

    bridge = load_source(adapter_path.parent / 'fm1_fixed_loader_backup.py',
        READ_SOURCES['fm1_fixed_loader_backup.py'], '_event12040_verify_bridge')
    reader = load_source(adapter_path.parent / 'fm1_uboot_read.py',
        READ_SOURCES['fm1_uboot_read.py'], '_event12040_verify_reader')
    loader = bridge.pinned_file(campaign['loader_path'], bridge.LOADER_SHA)
    profile = _json(bridge.pinned_file(campaign['profile_path'], bridge.PROFILE_SHA))
    bridge.pinned_file(campaign['profile_source_path'], bridge.PROFILE_SOURCE_SHA)
    returned = load_source(adapter_path.parent / 'fm1_returned_rom_backup.py',
        READ_SOURCES['fm1_returned_rom_backup.py'], '_event12040_verify_inventory')
    ops = returned.inventory(bridge, reader, loader, profile)
    if len(ops) != 8757 or bridge.inventory_digest(ops) != INVENTORY_SHA:
        raise ValueError('Fixed read inventory differs')
    commands_path = receipt / 'commands.jsonl'
    raw_commands = _hash_pin(commands_path, commands_sha, 16 * 1048576)
    rows = [_json(line) for line in raw_commands.splitlines()]
    if len(rows) != 2 + 2 * len(ops):
        raise ValueError('Exact complete read transcript required')
    times = [row.get('time') for row in rows]
    if not all(_finite(t) for t in times) or times != sorted(times) or times[-1] > now:
        raise ValueError('Read transcript chronology invalid')
    if not _read_snapshot_fresh_at_start(snapshot['observed_at'], times[0]):
        raise ValueError('Read snapshot was not fresh when the dual-read campaign began')
    expected_first = {'event':'device40_rom_read_prepared', 'campaign_sha256':manifest['campaign_sha256'],
        'adapter_sha256':manifest['adapter_sha256'], 'snapshot_sha256':manifest['snapshot_sha256'],
        'usb_binding':USB, 'sg_binding':manifest['sg_binding'], 'loader_sha256':bridge.LOADER_SHA,
        'profile_sha256':bridge.PROFILE_SHA, 'profile_source_sha256':bridge.PROFILE_SOURCE_SHA,
        'reader_sha256':READ_SOURCES['fm1_uboot_read.py'], 'commands':8757,
        'request_inventory_sha256':INVENTORY_SHA, 'expected_current_flash_sha256':TARGET_SHA,
        'flash_operations':0, 'reset_operations':0, 'upload_operations':47,
        'install_history_proven':False, 'boot_observed':False,
        'physical_recovery_verified':False, 'retry':False}
    expected_last = {'event':'device40_rom_read_completed', 'identical':True,
        'current_flash_sha256':TARGET_SHA, 'dumps':manifest['dumps'], 'commands':8757,
        'request_inventory_sha256':INVENTORY_SHA, 'flash_operations':0, 'reset_operations':0,
        'install_history_proven':False, 'boot_observed':False,
        'physical_recovery_verified':False, 'retry':False}
    if (canonical({k:v for k,v in rows[0].items() if k != 'time'}) != canonical(expected_first) or
            canonical({k:v for k,v in rows[-1].items() if k != 'time'}) != canonical(expected_last)):
        raise ValueError('Read transcript boundary events differ')
    hashes = []
    for name in ('dumpA.bin', 'dumpB.bin'):
        data = read_file(receipt / name, 1048576)
        if len(data) != 1048576 or digest(data) != TARGET_SHA:
            raise ValueError('Durable full read does not match fixed current-image SHA')
        hashes.append(digest(data))
    expected_dumps = [{'file':n,'bytes':1048576,'sha256':TARGET_SHA,'complete':True}
                      for n in ('dumpA.bin','dumpB.bin')]
    if hashes != [TARGET_SHA, TARGET_SHA] or canonical(manifest['dumps']) != canonical(expected_dumps):
        raise ValueError('Exact two-dump manifest required')
    for index, op in enumerate(ops):
        intent, completion = rows[1 + 2*index:3 + 2*index]
        wanted_intent = {'event':'sg_submit_intent','index':index,'phase':op.phase,'label':op.label,
            'cdb':op.cdb.hex(),'payload_sha256':digest(op.payload) if op.payload else None,
            'out_len':len(op.payload),'in_len':op.read_size,'retry':False}
        wanted_completion = {'event':'sg_completion','index':index,'status':0,'masked':0,'msg':0,
            'host':0,'driver':0,'resid':0,'info':0,'sense_len':0,'sense_hex':'','retry':False}
        if (canonical({k:v for k,v in intent.items() if k != 'time'}) != canonical(wanted_intent) or
                canonical({k:v for k,v in completion.items() if k != 'time'}) != canonical(wanted_completion)):
            raise ValueError('Read command/completion differs at index ' + str(index))
    marker = _rom_marker_path(receipt.parent, manifest['usb_binding'], manifest['sg_binding'])
    if read_file(marker, 256) != manifest['campaign_sha256'].encode('ascii'):
        raise ValueError('Fresh read one-use marker absent or changed')
    evidence = [(manifest_path, manifest_raw, 65536), (campaign_path, campaign_raw, 65536),
        (commands_path, raw_commands, 16*1048576), (Path(manifest['snapshot_path']), snapshot_raw, 65536),
        (adapter_path, adapter_raw, 65536),
        *[(adapter_path.parent/name, read_file(adapter_path.parent/name), 2*1048576)
          for name in READ_SOURCES],
        (receipt/'dumpA.bin', read_file(receipt/'dumpA.bin',1048576),1048576),
        (receipt/'dumpB.bin', read_file(receipt/'dumpB.bin',1048576),1048576),
        (marker, read_file(marker,256),256)]
    return {'manifest':manifest,'manifest_sha256':manifest_sha,'commands_sha256':commands_sha,
        'completed_at':times[-1],'receipt':receipt,'bridge':bridge,'reader':reader,
        'campaign':campaign,'snapshot':snapshot,'evidence':evidence}


def _target_modules(root):
    target = load_source(root/'fm1_fixed_target_reset.py', TARGET_RESET_SHA,
                         '_event12040_fixed_target_reset')
    previous = sys.modules.get('fm1_fixed_target_reset')
    sys.modules['fm1_fixed_target_reset'] = target
    try:
        completion = load_source(root/'native/event120_reset.py', COMPLETION_RESET_SHA,
                                 '_event12040_completion_reset')
    finally:
        if previous is None: sys.modules.pop('fm1_fixed_target_reset', None)
        else: sys.modules['fm1_fixed_target_reset'] = previous
    if digest(read_file(root/'fm1_fixed_loader_reset.py')) != RESET_BASE_SHA:
        raise ValueError('Reviewed reset base changed')
    return target, completion


@dataclass(frozen=True, eq=False)
class Prepared:
    campaign: bytes
    campaign_sha256: str
    expected_mapping: bytes
    target_prepared: object
    bridge: object
    header_type: type
    evidence: tuple
    snapshot_observed_at: float
    boot_marker: Path

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact factory-created device-40 reset required')
        if not 0 <= time.time()-self.snapshot_observed_at <= MAX_AGE:
            raise ValueError('Same-session passive connection evidence expired')
        for path, data, limit in self.evidence:
            if read_file(path, limit) != data:
                raise ValueError('Frozen reset evidence changed')
        self.target_prepared.check()


def prepare(path, *, now=None):
    now = time.time() if now is None else now
    campaign_path = Path(path).absolute()
    raw = read_file(campaign_path, 65536)
    c = _json(raw)
    keys = {'schema','kind','adapter_sha256','read_manifest_path','read_manifest_sha256',
        'read_commands_sha256','snapshot_path','snapshot_sha256','snapshot_observed_at',
        'usb_binding','sg_binding','active_session_state','no_later_commands_attested','receipt_path'}
    if (not isinstance(c,dict) or set(c)!=keys or type(c['schema']) is not int or c['schema']!=1 or
            c['kind']!=KIND or c['active_session_state']!=ACTIVE_SESSION or
            c['no_later_commands_attested'] is not True):
        raise ValueError('Exact same-session device-40 reset policy required')
    own = Path(__file__).absolute()
    if digest(read_file(own)) != c['adapter_sha256']:
        raise ValueError('Boot adapter source differs')
    read = verify_read_bundle(c['read_manifest_path'],c['read_manifest_sha256'],
                              c['read_commands_sha256'],now=now)
    if campaign_path.parent != read['receipt'].parent:
        raise ValueError('Boot campaign must share the private read evidence root')
    snap_raw = _hash_pin(c['snapshot_path'],c['snapshot_sha256'],65536)
    snap = _snapshot(snap_raw,now=now,earliest=read['completed_at'])
    if (c['usb_binding'] != USB or c['usb_binding'] != snap['usb_binding'] or
            canonical(c['sg_binding']) != canonical(snap['sg_binding']) or
            canonical(snap['sg_binding']) != canonical(read['manifest']['sg_binding']) or
            c['snapshot_observed_at'] != snap['observed_at']):
        raise ValueError('Boot snapshot differs from completed read connection')
    receipt = Path(c['receipt_path'])
    parent = read['receipt'].parent
    if (receipt.parent != parent or not receipt.is_absolute() or os.path.lexists(receipt) or
            not stat.S_ISDIR(parent.lstat().st_mode) or stat.S_IMODE(parent.stat().st_mode)!=0o700):
        raise ValueError('New boot receipt must share the private evidence root')
    marker = parent / ('.event12040-boot-' + c['read_manifest_sha256'] + '.consumed')
    if os.path.lexists(marker):
        raise ValueError('Fresh-read reset authorization already consumed')
    target, completion = _target_modules(own.parent)
    if ctypes.sizeof(read['reader'].SGHeader) != 88:
        raise ValueError('Reviewed 64-bit Linux SG ABI required')
    mapping = _live_mapping(read['bridge'],USB)
    if canonical(mapping) != canonical(snap['sg_binding']):
        raise ValueError('Live USB/SG mapping differs from the fresh passive snapshot')
    evidence = list(read['evidence']) + [(campaign_path,raw,65536),
        (Path(c['snapshot_path']),snap_raw,65536),(own,read_file(own),65536),
        (own.parent/'fm1_fixed_target_reset.py',read_file(own.parent/'fm1_fixed_target_reset.py'),2*1048576),
        (own.parent/'fm1_fixed_loader_reset.py',read_file(own.parent/'fm1_fixed_loader_reset.py'),2*1048576),
        (own.parent/'native/event120_reset.py',read_file(own.parent/'native/event120_reset.py'),2*1048576)]
    underlying = target.Prepared(canonical(c),digest(raw),c['read_manifest_sha256'],canonical(mapping),
        read['bridge'],read['reader'].SGHeader,tuple(evidence),())
    target._AUTHORIZED.add(underlying)
    underlying.check()
    p = Prepared(raw,digest(raw),canonical(mapping),underlying,read['bridge'],
                 read['reader'].SGHeader,tuple(evidence),snap['observed_at'],marker)
    _AUTHORIZED.add(p)
    p.check()
    return p,completion


def session_class(completion):
    class Device40Reset(completion.CompletionFirstReset):
        def __init__(self,prepared,log):
            prepared.check()
            self.prepared,self.log=prepared,log
            self.fd,self.consumed,self.failed,self.ioctl_attempts=None,False,False,0
            self.phase,self.started='device40-fresh-read-no-later-commands',time.monotonic()
            self.usb=USB
            try:
                self.mapping=_live_mapping(prepared.bridge,self.usb)
                if canonical(self.mapping)!=prepared.expected_mapping:
                    raise ValueError('Device-40 SG mapping changed')
                self.fd=os.open(self.mapping['node'],os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
                fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.binding()
            except BaseException:
                self.failed=True
                self.close()
                raise

        def binding(self):
            self.prepared.check()
            if not 0 <= time.monotonic()-self.started <= 10:
                raise ValueError('Reset descriptor lifetime exceeded')
            current=_live_mapping(self.prepared.bridge,self.usb)
            if canonical(current)!=self.prepared.expected_mapping:
                raise ValueError('Device-40 connection changed before reset')
            opened=os.fstat(self.fd)
            if canonical((opened.st_dev,opened.st_ino,opened.st_rdev)) != canonical(self.mapping['node_identity']):
                raise ValueError('Opened SG descriptor identity changed')
            return None
    return Device40Reset


def run(path):
    p, completion = prepare(path)
    c = _json(p.campaign)
    parent = Path(c['receipt_path']).parent
    out = Path(c['receipt_path'])
    out.mkdir(mode=0o700,exist_ok=False)
    p.bridge.sync_dir(parent)
    with p.bridge.private_file(p.boot_marker) as fp:
        fp.write(p.campaign_sha256.encode('ascii'));fp.flush();os.fsync(fp.fileno())
    p.bridge.sync_dir(parent)
    Session = session_class(completion)
    with p.bridge.private_file(out/'commands.jsonl','w') as events:
        def log(event,**fields):
            events.write(json.dumps(dict(time=time.time(),event=event,**fields),allow_nan=False)+'\n')
            events.flush();os.fsync(events.fileno())
        session=None
        try:
            log('device40_boot_prepared',campaign_sha256=p.campaign_sha256,
                read_manifest_sha256=c['read_manifest_sha256'],target_sha256=TARGET_SHA,
                commands=1,flash_operations=0,upload_operations=0,install_history_proven=False,
                boot_observed=False,physical_recovery_verified=False,retry=False)
            session=Session(p,log)
            result=session.request_reset()
            log('device40_boot_request_completed',**result,retry=False,
                install_history_proven=False,physical_recovery_verified=False)
            return result
        except BaseException as exc:
            try: log('device40_boot_stopped_ambiguous',error=type(exc).__name__,retry=False,
                     boot_observed=False,physical_recovery_verified=False)
            except OSError: pass
            raise
        finally:
            if session is not None: session.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--preflight',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    if args.preflight:
        prepare(args.campaign)
        print(json.dumps({'preflight':True,'hardware_operations':0}))
    else:
        print(json.dumps(run(args.campaign)))

if __name__=='__main__':
    if sys.platform!='linux':raise SystemExit('Linux SG_IO only')
    main()
