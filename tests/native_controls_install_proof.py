"""MIT. Sixteen offline faults against the actual native-install receipt."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native.controls_install_proof import verify


def check(inputs,shard):
    assert 0 <= shard < 16
    assert verify(inputs)['commands']==10747
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)/'evidence';shutil.copytree(inputs,root)
        transcript=root/'native-install-001/commands.jsonl'
        events=[json.loads(line) for line in transcript.read_text().splitlines()]
        if shard<10:
            if shard==0:events.pop()
            elif shard==1:events.append(events[-1])
            elif shard==2:events[1]['cdb']='00'*16
            elif shard==3:events[2]['host']=1
            elif shard==4:
                e=next(e for e in events if e.get('in_len')==256);e['index']+=1
            elif shard==5:
                e=next(e for e in events if e.get('out_len')==256);e['payload_sha256']='0'*64
            elif shard==6:
                e=next(e for e in events if e.get('response_sha256') is not None and e['event']=='sg_completion');e['response_sha256']='x'*64
            elif shard==7:events[0]['time']=float('nan')
            elif shard==8:events[1]['time']=events[0]['time']-1
            else:
                i=next(i for i,e in enumerate(events) if e['event']=='sector_verified');events.pop(i)
            transcript.write_text(''.join(json.dumps(e)+'\n' for e in events))
        elif shard==10:
            (root/'native-install-001/result.json').write_text('{}')
        elif shard==11:
            (root/'.native-native-install.consumed').write_text('0'*64)
        elif shard==12:
            p=root/'controls-plans/native/journal.json';j=json.loads(p.read_text());j['state']='pending';p.write_text(json.dumps(j))
        elif shard==13:
            p=root/'controls-plans/native/target.bin';data=bytearray(p.read_bytes());data[0]^=1;p.write_bytes(data)
        elif shard==14:
            p=root/'controls-plans/native/backupB.bin';data=bytearray(p.read_bytes());data[0x5000]^=1;p.write_bytes(data)
        else:
            p=root/'native-install-campaign.json';c=json.loads(p.read_text());c['sg_binding']['node']='/dev/sg99';p.write_text(json.dumps(c))
        try:verify(root)
        except (ValueError,KeyError):pass
        else:raise AssertionError('Corrupted evidence accepted')
    return dict(shard=shard,passed=True,hardware_operations=0,physical_receipt_replay=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--shard',type=int,required=True)
    a=p.parse_args();print(json.dumps(check(a.inputs,a.shard)))
