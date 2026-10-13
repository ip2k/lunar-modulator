"""MIT. Sixteen native live-admission faults; mocks never open a device."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native.controls_transactions import prepare as plans, digest
from native import controls_live as live
from native_controls_policy import refuses


def campaign(inputs,shard):
    assert 0 <= shard < 16
    inputs=Path(inputs)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        import shutil
        shutil.copytree(inputs/'receipt',root/'backup')
        plans(root/'plans',root/'backup',inputs/'stockA.bin',inputs/'stockB.bin',inputs/'native.bin')
        manifest=json.loads((root/'backup/manifest.json').read_text())
        c=dict(schema=1,kind=live.KIND,adapter_sha256=digest(Path(live.__file__).read_bytes()),
               observed_at=time.time(),receipt=str(root/'backup'),plan=str(root/'plans/native'),
               direction='install',variant='native',output=str(root/'install-001'),sg_binding=manifest['sg_binding'])
        path=root/'campaign.json'
        bridge,_,sg=live.sources()
        mapping={k:tuple(v) if k.endswith('_identity') else v for k,v in manifest['sg_binding'].items()}
        with patch.object(bridge,'discover_sg',return_value=mapping), patch.object(sg.os,'open', wraps=sg.os.open) as opened:
            path.write_text(json.dumps(c)); p=live.prepare(path);p.check()
            assert all(str(call.args[0]) != '/dev/sg0' for call in opened.call_args_list)
            if shard < 12:
                if shard==0:c['schema']=True
                elif shard==1:c['kind']='sdk'
                elif shard==2:c['observed_at']-=121
                elif shard==3:c['observed_at']+=10
                elif shard==4:c['observed_at']=True
                elif shard==5:c['observed_at']=float('nan')
                elif shard==6:c['adapter_sha256']='0'*64
                elif shard==7:c['sg_binding']['node']='/dev/sg99'
                elif shard==8:c['output']=str(root/'nested/output')
                elif shard==9:(root/'.native-native-install.consumed').touch()
                elif shard==10:del c['variant']
                else:c['unexpected']=1
                path.write_text(json.dumps(c));refuses(lambda:live.prepare(path))
            elif shard==12:refuses(replace(p).check)
            elif shard==13:
                path.write_text(json.dumps(dict(c,variant='stock')));refuses(p.check)
            elif shard==14:
                with patch.object(live.time,'time',return_value=c['observed_at']+121):refuses(lambda:live.run(p))
                assert not Path(c['output']).exists()
            else:
                with patch.object(sg,'RehearsalSG',side_effect=OSError('injected open failure')) as opener:
                    refuses(lambda:live.run(p));assert opener.call_count==1
                    assert (root/'.native-native-install.consumed').is_file()
                    assert not (Path(c['output'])/'result.json').exists()
                    c['output']=str(root/'renamed-install');path.write_text(json.dumps(c))
                    refuses(lambda:live.prepare(path));assert opener.call_count==1
        return dict(shard=shard,passed=True,hardware_operations=0,simulation_only=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--inputs',type=Path,required=True);a.add_argument('--shard',type=int,required=True)
    args=a.parse_args();print(json.dumps(campaign(args.inputs,args.shard),sort_keys=True))
