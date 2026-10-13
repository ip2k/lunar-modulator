"""MIT. One-use device-27 native-controls transaction through reviewed SG_IO.

Uses only RehearsalSG's generic exact-wire transport, never SDK prepare/run.
No ROM entry, upload, reset, retry or boot claim. Trusted private source tree
and operator-reviewed campaign are required; this is not a security sandbox.
"""
import argparse
import ctypes
from dataclasses import dataclass
import importlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
from weakref import WeakSet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native.controls_policy import load_policy, SOURCES as POLICY_SOURCES
from native.controls_transactions import pinned, V8_SHA, NATIVE_SHA, STOCK_SHA, MANIFEST_SHA
from fm1_flash_transaction import digest, encoded

SOURCES = dict(POLICY_SOURCES, **{
    'native/controls_policy.py': 'b4fcba972eba0b4eeaf623136936bd4265e9d9533a19002d174018c95fda9ea1',
    'fm1_fixed_loader_backup.py': '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb',
    'fm1_sdk_rehearsal.py': 'f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4',
})
_AUTHORIZED = WeakSet()
KIND = 'fm1-fresh-native-controls-transaction'


def sources():
    for name, sha in SOURCES.items():
        pinned(ROOT / name, sha)
    for name in SOURCES:
        module = importlib.import_module(name[:-3].replace('/', '.'))
        if Path(module.__file__).resolve() != ROOT / name:
            raise ValueError('Ambient implementation module')
    return importlib.import_module('fm1_fixed_loader_backup'), importlib.import_module('fm1_uboot_read'), importlib.import_module('fm1_sdk_rehearsal')


@dataclass(frozen=True, eq=False)
class Prepared:
    config: bytes
    campaign_sha256: str
    policies: tuple
    mapping: bytes
    bridge: object
    header_type: type
    evidence: tuple
    source_sha256: str

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact prepared native instance required')
        sources()
        pinned(Path(__file__), self.source_sha256)
        for path, sha, limit in self.evidence:
            pinned(path, sha, limit)
        for policy in self.policies:
            policy.check_files()


def prepare(path):
    path = Path(path).absolute()
    fd = os.open(path,os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Direct regular campaign required')
        raw = fp.read(65537)
    if len(raw) > 65536:
        raise ValueError('Bounded campaign required')
    c = json.loads(raw)
    fields = {'schema','kind','adapter_sha256','observed_at','receipt','plan','direction','variant','output','sg_binding'}
    if set(c) != fields or type(c['schema']) is not int or c['schema'] != 1 or c['kind'] != KIND:
        raise ValueError('Exact native campaign required')
    if (type(c['observed_at']) not in (int,float) or not math.isfinite(c['observed_at'])
            or not 0 <= time.time()-c['observed_at'] <= 120):
        raise ValueError('Fresh passive loader observation required')
    pinned(Path(__file__), c['adapter_sha256'])
    bridge, reader, _ = sources()
    receipt, output, plan = (Path(c[name]) for name in ('receipt','output','plan'))
    if any(not p.is_absolute() for p in (receipt,output,plan)):
        raise ValueError('Absolute reviewed paths required')
    if (output.parent != receipt.parent or path.parent != receipt.parent
            or os.path.lexists(output) or stat.S_IMODE(output.parent.stat().st_mode) != 0o700
            or output.parent.is_symlink()):
        raise ValueError('New receipt in original private backup parent required')
    policy = load_policy(plan, direction=c['direction'], receipt=receipt, variant=c['variant'])
    manifest = json.loads(pinned(receipt/'manifest.json', MANIFEST_SHA, 65536))
    if (manifest['kind'] != 'fm1-fresh-observed-rom-fixed-loader-dual-read'
            or manifest['usb_binding'] != dict(path='1-1',busnum='1',devnum='27',vid='4c4a',pid='8057')
            or encoded(c['sg_binding']) != encoded(manifest['sg_binding'])
            or encoded(bridge.discover_sg(manifest['usb_binding'])) != encoded(c['sg_binding'])
            or ctypes.sizeof(reader.SGHeader) != 88):
        raise ValueError('Completed backup/current loader/SG mapping differs')
    marker = output.parent / ('.native-'+c['variant']+'-'+c['direction']+'.consumed')
    if os.path.lexists(marker):
        raise ValueError('Reviewed direction already consumed; no automatic retry')
    p = Prepared(raw,digest(raw),(policy,),encoded(c['sg_binding']),bridge,reader.SGHeader,
                 ((path,digest(raw),65536),),c['adapter_sha256'])
    _AUTHORIZED.add(p)
    p.check()
    return p


def run(p):
    p.check()
    c, policy = json.loads(p.config), p.policies[0]
    # Preparation expires even if a caller delays before invoking run().
    if not 0 <= time.time()-c['observed_at'] <= 120:
        raise ValueError('Prepared observation expired')
    out = Path(c['output']); out.mkdir(mode=0o700,exist_ok=False)
    p.bridge.sync_dir(out.parent)
    marker = out.parent / ('.native-'+c['variant']+'-'+c['direction']+'.consumed')
    with p.bridge.private_file(marker) as fp:
        fp.write(p.campaign_sha256.encode()); fp.flush(); os.fsync(fp.fileno())
    p.bridge.sync_dir(out.parent)
    transport = None
    with p.bridge.private_file(out/'commands.jsonl','w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(),event=event,**fields),allow_nan=False)+'\n')
            events.flush(); os.fsync(events.fileno())
        try:
            log('native_transaction_prepared',campaign_sha256=p.campaign_sha256,
                source_sha256=SOURCES,adapter_sha256=c['adapter_sha256'],
                backup_manifest_sha256=MANIFEST_SHA,sg_binding=c['sg_binding'],
                variant=c['variant'],direction=c['direction'],retry=False)
            _, _, sg = sources()
            transport = sg.RehearsalSG(p,policy,log)
            result = policy.bind(transport).run(checkpoint=log)
            expected = V8_SHA if c['direction']=='restore' else (NATIVE_SHA if c['variant']=='native' else STOCK_SHA)
            if result['verified_sha256'] != expected:
                raise ValueError('Complete native transaction readback differs')
            result = dict(campaign_sha256=p.campaign_sha256,direction=c['direction'],variant=c['variant'],
                          verified_sha256=expected,sectors_written=result['sectors_written'],
                          full_flash_readback_verified=True,boot_observed=False,
                          physical_recovery_verified=False,kernel_exclusivity=False)
            log('native_transaction_completed',**result)
            with p.bridge.private_file(out/'result.json','w') as fp:
                json.dump(result,fp,sort_keys=True);fp.write('\n');fp.flush();os.fsync(fp.fileno())
            p.bridge.sync_dir(out)
            return result
        except BaseException as exc:
            log('native_transaction_stopped',error=type(exc).__name__,detail=str(exc),retry=False)
            raise
        finally:
            if transport is not None: transport.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--preflight',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    p=prepare(args.campaign)
    print(json.dumps(dict(preflight=True,hardware_operations=0) if args.preflight else run(p)))
