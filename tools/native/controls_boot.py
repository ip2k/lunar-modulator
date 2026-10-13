"""MIT. One FC0C arg1 for the independently verified native controls image.

No upload, flash command or retry. Request success alone proves neither boot
nor recovery. Private trusted source tree and fresh operator observation apply.
"""
import argparse
import ctypes
from dataclasses import dataclass
import fcntl
import json
import math
import os
from pathlib import Path
import stat
import time
from weakref import WeakSet
from . import controls_install_proof as proof
from .controls_live import sources
from fm1_fixed_target_reset import canonical,digest,read_file,reset

_AUTHORIZED=WeakSet()
PROOF_SHA='6676f26ff8f0dedb7c74853d5f196c3f92607db1702f1c41f550e0c0324e470a'
USB=dict(path='1-1',busnum='1',devnum='27',vid='4c4a',pid='8057')

@dataclass(frozen=True,eq=False)
class Prepared:
    campaign: bytes
    campaign_sha256: str
    expected_mapping: bytes
    bridge: object
    header_type: type
    evidence: tuple

    def check(self):
        if self not in _AUTHORIZED:raise ValueError('Exact native boot instance required')
        for path,raw in self.evidence:
            if read_file(path,32*1048576)!=raw:raise ValueError('Frozen native boot evidence changed')
        sources()
        c=json.loads(self.campaign)
        if not 0<=time.time()-c['observed_at']<=120:raise ValueError('Native boot observation expired')


def prepare(path):
    path=Path(path).absolute();raw=read_file(path,65536);c=json.loads(raw)
    fields={'schema','kind','adapter_sha256','observed_at','evidence_root','sg_binding','usb_binding','receipt_path','active_session_state'}
    if (set(c)!=fields or type(c['schema']) is not int or c['schema']!=1
        or c['kind']!='fm1-native-controls-single-boot'
        or c['active_session_state']!='same-fixed-loader-native-installed-no-later-commands'
        or c['usb_binding']!=USB or type(c['observed_at']) not in (int,float)
        or not math.isfinite(c['observed_at']) or not 0<=time.time()-c['observed_at']<=120):
        raise ValueError('Exact fresh completed native boot campaign required')
    adapter=Path(__file__).resolve()
    if digest(read_file(adapter))!=c['adapter_sha256'] or digest(read_file(Path(proof.__file__).resolve()))!=PROOF_SHA:
        raise ValueError('Native boot source differs')
    root=Path(c['evidence_root']);out=Path(c['receipt_path'])
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
        or stat.S_IMODE(root.stat().st_mode)!=0o700 or path.parent!=root
        or not out.is_absolute() or out.parent!=root or os.path.lexists(out)
        or os.path.lexists(root/'.native-controls-boot.consumed')):
        raise ValueError('New private one-use native boot receipt required')
    proof.verify(root)
    install=json.loads(read_file(root/'native-install-campaign.json',65536))
    bridge,reader,_=sources()
    if canonical(c['sg_binding'])!=canonical(install['sg_binding']) or canonical(bridge.discover_sg(USB))!=canonical(c['sg_binding']):
        raise ValueError('Original native loader connection replaced')
    if ctypes.sizeof(reader.SGHeader)!=88:raise ValueError('Reviewed SG ABI required')
    paths=[path,adapter,Path(proof.__file__).resolve()]
    paths += [root/'native-install-campaign.json',root/'.native-native-install.consumed',
              root/'native-install-001/commands.jsonl',root/'native-install-001/result.json']
    paths += [root/'controls-plans/native'/name for name in ('plan.json','journal.json','backupA.bin','backupB.bin','target.bin')]
    paths += [proof.ROOT/name for name in dict(proof.SOURCES,**{'native/controls_live.py':proof.LIVE_SHA,'fm1_fixed_target_reset.py':proof.CURSOR_SHA})]
    paths += [proof.ROOT/'fm1_fixed_loader_reset.py']
    p=Prepared(raw,digest(raw),canonical(c['sg_binding']),bridge,reader.SGHeader,
               tuple((p,read_file(p,32*1048576)) for p in paths))
    _AUTHORIZED.add(p);p.check();return p

class ResetSG(reset.ResetSG):
    def __init__(self,p,log):
        p.check();self.prepared,self.log=p,log
        self.fd,self.consumed,self.failed,self.ioctl_attempts=None,False,False,0
        self.phase,self.started='native-installed-fixed-loader',time.monotonic()
        self.usb=USB
        try:
            self.mapping=p.bridge.discover_sg(self.usb)
            if canonical(self.mapping)!=p.expected_mapping:raise ValueError('Native loader replaced')
            self.fd=os.open(self.mapping['node'],os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
            fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.binding()
        except BaseException:
            self.failed=True;self.close();raise
    def binding(self):
        self.prepared.check();return super().binding()
    def request_reset(self):
        try:self.prepared.check()
        except BaseException:
            self.failed=True;self.close();raise
        return super().request_reset()


def run(p):
    p.check();c=json.loads(p.campaign);out=Path(c['receipt_path']);bridge=p.bridge
    out.mkdir(mode=0o700);bridge.sync_dir(out.parent)
    with bridge.private_file(out.parent/'.native-controls-boot.consumed') as fp:
        fp.write(p.campaign_sha256.encode());fp.flush();os.fsync(fp.fileno())
    bridge.sync_dir(out.parent)
    with bridge.private_file(out/'commands.jsonl','w') as events:
        def log(event,**fields):
            events.write(json.dumps(dict(time=time.time(),event=event,**fields),allow_nan=False)+'\n')
            events.flush();os.fsync(events.fileno())
        transport=None
        try:
            log('native_boot_prepared',campaign_sha256=p.campaign_sha256,target_sha256=proof.NATIVE_SHA,
                commands=1,flash_operations=0,upload_operations=0,retry=False,boot_observed=False)
            transport=ResetSG(p,log);result=transport.request_reset()
            log('native_boot_request_completed',**result,retry=False,physical_recovery_verified=False)
            return result
        except BaseException as exc:
            log('native_boot_stopped_ambiguous',error=type(exc).__name__,detail=str(exc),retry=False,boot_observed=False)
            raise
        finally:
            if transport is not None:transport.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--campaign',type=Path,required=True);parser.add_argument('--preflight',action='store_true')
    a=parser.parse_args();os.umask(0o077);p=prepare(a.campaign)
    print(json.dumps(dict(preflight=True,hardware_operations=0) if a.preflight else run(p)))
