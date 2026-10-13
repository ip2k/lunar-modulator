"""MIT. Sixteen native boot admission/one-request mock faults; no device I/O."""
import argparse
import ctypes
from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native import returned_boot as boot

def refuses(fn):
    try:fn()
    except (ValueError,OSError):return
    raise AssertionError('Fault accepted')

def check(inputs,shard):
    assert 0<=shard<16
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)/'evidence';shutil.copytree(inputs,root);root.chmod(0o700)
        install=json.loads((root/'native-returned-rom-029/manifest.json').read_text())
        c=dict(schema=1,kind='fm1-native-returned-single-boot',adapter_sha256=boot.digest(Path(boot.__file__).read_bytes()),observed_at=time.time(),evidence_root=str(root),sg_binding=install['sg_binding'],usb_binding=boot.USB,receipt_path=str(root/'boot-001'),active_session_state='same-native-dual-read-loader-no-later-commands')
        path=root/'boot-campaign.json';path.write_text(json.dumps(c))
        bridge,_,_=boot.sources()
        with patch.object(bridge,'discover_sg',return_value=c['sg_binding']):
            p=boot.prepare(path);p.check()
            if shard<12:
                if shard==0:c['schema']=True
                elif shard==1:c['kind']='sdk'
                elif shard==2:c['adapter_sha256']='0'*64
                elif shard==3:c['observed_at']-=121
                elif shard==4:c['observed_at']+=10
                elif shard==5:c['observed_at']=True
                elif shard==6:c['observed_at']=float('nan')
                elif shard==7:c['usb_binding']=dict(boot.USB,devnum='14')
                elif shard==8:c['active_session_state']='unknown'
                elif shard==9:c['receipt_path']=str(root.parent/'escape')
                elif shard==10:(root/'.native-returned-boot.consumed').touch()
                else:c['unexpected']=1
                path.write_text(json.dumps(c));refuses(lambda:boot.prepare(path))
            elif shard==12:
                with patch.object(boot.time,'time',return_value=c['observed_at']+121):refuses(p.check)
            elif shard==13:refuses(replace(p).check)
            elif shard==14:
                (root/'native-returned-rom-029/manifest.json').write_text('{}');refuses(p.check)
            else:
                # Exercise the exact inherited request method without opening SG.
                transport=object.__new__(boot.ResetSG)
                transport.prepared=p;transport.log=lambda *a,**kw:None
                transport.fd=999;transport.consumed=False;transport.failed=False
                transport.ioctl_attempts=0;transport.phase='mock'
                with patch.object(transport,'binding'),patch.object(transport,'close') as close:
                    def ioctl(fd,op,h):
                        assert fd==999 and op==0x2285
                        assert ctypes.string_at(h.cmd,h.cmd_len)==bytes.fromhex('fc0c00000001ffffffffffffffffffff')
                        ctypes.memmove(h.data,bytes.fromhex('fc0c')+bytes(14),16)
                    with patch.object(boot.reset.fcntl,'ioctl',side_effect=ioctl) as io:
                        assert transport.request_reset()['request_completion'] is True
                        refuses(transport.request_reset)
                        assert io.call_count==1 and transport.ioctl_attempts==1
                # Failed open consumes the durable boot marker as well.
                with patch.object(boot,'ResetSG',side_effect=OSError('injected open failure')) as opener:
                    refuses(lambda:boot.run(p));assert opener.call_count==1
                assert (root/'.native-returned-boot.consumed').is_file()
                refuses(lambda:boot.prepare(path))
    return dict(shard=shard,passed=True,hardware_operations=0,simulation_only=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--shard',type=int,required=True)
    a=p.parse_args();print(json.dumps(check(a.inputs,a.shard)))
