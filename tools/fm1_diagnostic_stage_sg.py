"""MIT. Exact Linux SG transport for the separately pinned stage-probe policy.

The bench owner must review a concrete campaign before using --campaign or
calling run_campaign. No upload, reset, flash I/O, or retry.
SG structure/discovery reuse our own pinned MIT reader/backup implementation.
The reported WL82 codec and actual SRAM retention remain physical uncertainties.
"""
import argparse
import ctypes as C
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types
from weakref import WeakSet

PROBE_SHA = 'ff5938530de5b9ca62c2361bfad024d64073168bc4c3bfedb77ea7c9eca56007'
BRIDGE_SHA = '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb'
READER_SHA = '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57'
OPERATIONS = ((bytes.fromhex('120000002400'), b'', 36),
              (bytes.fromhex('fd0701c033d80020ffffffffffffffff'), b'', 32))
_AUTHORIZED = WeakSet()
_OPENING = WeakSet()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path=Path(path)
    if not path.is_absolute():raise ValueError('Absolute evidence required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
    try:fp=os.fdopen(fd,'rb')
    except BaseException:os.close(fd);raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):raise ValueError('Regular evidence required')
        data=fp.read(limit+1)
    if len(data)>limit:raise ValueError('Evidence exceeds bound')
    return data


def load_source(path, expected, name):
    source=read_file(path)
    if digest(source)!=expected:raise ValueError('Reviewed executable source differs')
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(source,str(path),'exec'),module.__dict__)
    if read_file(path)!=source:raise ValueError('Source changed during import')
    return module


@dataclass(frozen=True,eq=False)
class Prepared:
    campaign: bytes
    campaign_sha256: str
    probe: object
    module: object
    bridge: object
    header_type: type
    evidence: tuple

    def check(self):
        if self not in _AUTHORIZED:raise ValueError('Exact native stage Prepared required')
        for path,data,limit in self.evidence:
            if read_file(path,limit)!=data:raise ValueError('Frozen native stage evidence changed')
        self.probe.check()


def prepare_campaign(path):
    """Device-free factory; imports only exact reviewed local source bytes."""
    evidence=[]
    def freeze(path,expected=None,limit=2*1048576):
        path=Path(path);data=read_file(path,limit)
        if expected is not None and digest(data)!=expected:raise ValueError('Native stage evidence differs')
        evidence.append((path,data,limit));return data
    raw=freeze(Path(path).absolute(),limit=65536);c=json.loads(raw)
    if (set(c)!={'schema','kind','adapter_sha256','probe_campaign_path','probe_campaign_sha256'} or
            type(c['schema']) is not int or c['schema']!=1 or c['kind']!='fm1-exact-native-diagnostic-stage-probe'):
        raise ValueError('Exact native stage envelope required')
    root=Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(),c['adapter_sha256'])
    probe_path=root/'fm1_diagnostic_stage_probe.py';freeze(probe_path,PROBE_SHA)
    bridge_path=root/'fm1_fixed_loader_backup.py';freeze(bridge_path,BRIDGE_SHA)
    reader_path=root/'fm1_uboot_read.py';freeze(reader_path,READER_SHA)
    p=load_source(probe_path,PROBE_SHA,'_fm1_native_stage_verified_probe')
    bridge=load_source(bridge_path,BRIDGE_SHA,'_fm1_native_stage_verified_bridge')
    reader=load_source(reader_path,READER_SHA,'_fm1_native_stage_verified_reader')
    if C.sizeof(reader.SGHeader)!=88 or C.sizeof(C.c_void_p)!=8:
        raise ValueError('Reviewed 64-bit Linux SG layout required')
    freeze(c['probe_campaign_path'],c['probe_campaign_sha256'],65536)
    probe=p.prepare_campaign(c['probe_campaign_path'])
    if probe.campaign_sha256!=c['probe_campaign_sha256'] or p.OPERATIONS!=OPERATIONS:
        raise ValueError('Exact underlying fixed read policy required')
    obj=Prepared(canonical(c),digest(raw),probe,p,bridge,reader.SGHeader,tuple(evidence))
    _AUTHORIZED.add(obj);obj.check();return obj


class NativeSG:
    """One exclusive FD, exactly two IN requests, fail closed on any uncertainty.

    flock is advisory; the caller must attest no competing commands. Full USB/
    sysfs discovery and opened FD identity are checked before and after ioctl.
    """
    def __init__(self,prepared,_permit=None):
        if sys.platform!='linux':raise ValueError('Linux SG_IO only')
        if _permit not in _OPENING or _permit.prepared is not prepared:
            raise ValueError('Open only inside the durable one-use probe runner')
        _OPENING.discard(_permit)
        if not isinstance(prepared,Prepared):raise ValueError('Native stage Prepared required')
        prepared.check()  # Never discover/open for a copied or stale authority.
        self.prepared=prepared;self.fd=None;self.next=0;self.failed=False
        self.close_error=None;self.started=time.monotonic()
        snap=json.loads(prepared.probe.snapshot)
        self.usb=snap['usb_binding'];self.mapping=snap['sg_binding']
        try:
            actual=prepared.bridge.discover_sg(self.usb)
            if canonical(actual)!=canonical(self.mapping):raise ValueError('Initial-ROM mapping changed')
            self.fd=os.open(self.mapping['node'],os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
            fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.binding()
        except BaseException:
            self.failed=True;self.close();raise

    def close(self):
        if self.close_error is not None:raise self.close_error
        if self.fd is not None:
            fd,self.fd=self.fd,None
            try:os.close(fd)
            except BaseException as exc:
                self.failed=True;self.close_error=exc;raise

    def binding(self):
        try:
            self.prepared.check()
            if self.failed or self.fd is None or not 0<=time.monotonic()-self.started<=10:
                raise ValueError('Closed, failed, or stale native probe')
            opened=os.fstat(self.fd)
            identity=(opened.st_dev,opened.st_ino,opened.st_rdev)
            if (not stat.S_ISCHR(opened.st_mode) or
                    canonical(identity)!=canonical(self.mapping['node_identity']) or
                    canonical(self.prepared.bridge.discover_sg(self.usb))!=canonical(self.mapping)):
                raise ValueError('Opened SG/USB/sysfs identity changed')
            return dict(usb_binding=self.usb,sg_binding=self.mapping,
                        fd_identity=identity,fd_mode=opened.st_mode)
        except BaseException:
            self.failed=True;self.close();raise

    def exchange(self,cdb,payload=b'',in_len=None):
        try:
            if self.failed or self.fd is None or self.next>=2:raise ValueError('Native probe consumed/closed')
            index=self.next;self.next+=1  # Invalid/failed attempts cannot be retried.
            if (type(cdb) is not bytes or type(payload) is not bytes or type(in_len) is not int or
                    (cdb,payload,in_len)!=OPERATIONS[index]):
                raise ValueError('Only exact ordered INQUIRY/FD07 permitted')
            self.binding()  # Source and FD check immediately before ioctl.
            command,sense,data=C.create_string_buffer(cdb),C.create_string_buffer(32),C.create_string_buffer(in_len)
            h=self.prepared.header_type(interface_id=ord('S'),direction=-3,cmd_len=len(cdb),
                sense_max=32,data_len=in_len,data=C.addressof(data),cmd=C.addressof(command),
                sense=C.addressof(sense),timeout=3000)
            fcntl.ioctl(self.fd,0x2285,h)
            self.binding()
            fields={name:getattr(h,name) for name in ('status','masked','msg','host','driver','resid','info','sense_len')}
            reply=self.prepared.module.Completion(data.raw,**fields,sense=sense.raw[:min(h.sense_len,32)])
            # Return exact status/sense/data for durable outer-policy logging.
            # The runner-only permit confines this transport to the pinned
            # ProbeSession, which rejects any SG error or changed inquiry and
            # closes before another request. It never exposes a reopen handle.
            return reply
        except BaseException:
            self.failed=True;self.close();raise


def run_campaign(prepared):
    """No automatic run or retry; concrete campaign approval is the caller's job."""
    if not isinstance(prepared,Prepared):raise ValueError('Native stage Prepared required')
    prepared.check()
    def factory(probe):
        if probe is not prepared.probe:raise ValueError('Exact underlying prepared instance required')
        prepared.check()
        permit=_OpenPermit(prepared);_OPENING.add(permit)
        try:return NativeSG(prepared,permit)
        finally:_OPENING.discard(permit)
    return prepared.module.run_campaign(prepared.probe,factory)


@dataclass(frozen=True,eq=False)
class _OpenPermit:
    prepared: Prepared


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!='linux':raise SystemExit('Linux SG_IO only')
    result=run_campaign(prepare_campaign(args.campaign))
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
