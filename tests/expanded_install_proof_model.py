"""MIT. Actual transaction on a NOR model; strict replay faults, no device I/O.

Private candidate bytes are required. Model transcripts are test data, never
physical installation evidence. Generate once on Hera, then shard the faults.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'),
                str(Path(__file__).resolve().parent)]
from native import expanded_install_proof as proof
from native.expanded_bench_transactions import prepare
from native.expanded_bench_policy import load_policy
from native.expanded_bench_live import KIND
from native_controls_policy import Wire


PLAN = 'build/native-current-candidate-20261013/device36-plans'


def rebase(root):
    path = root/'native-install-campaign.json'
    c = json.loads(path.read_text())
    c.update(receipt=str(root/'native-returned-rom-036'),
             plan=str(root/PLAN/'native'),output=str(root/'native-install-v1'))
    raw = proof.canonical(c); path.write_bytes(raw); sha = proof.digest(raw)
    (root/'.expanded36-native-install.consumed').write_text(sha)
    transcript = root/'native-install-v1/commands.jsonl'
    events = [json.loads(line) for line in transcript.read_text().splitlines()]
    events[0]['campaign_sha256'] = events[-1]['campaign_sha256'] = sha
    transcript.write_text(''.join(json.dumps(e)+'\n' for e in events))
    result = root/'native-install-v1/result.json'
    r = json.loads(result.read_text()); r['campaign_sha256'] = sha
    result.write_text(json.dumps(r))
    return sha


def generate(inputs, root):
    root.mkdir(mode=0o700)
    shutil.copytree(inputs/'fresh',root/'native-returned-rom-036')
    prepare(root/PLAN,root/'native-returned-rom-036',inputs/'target.bin',
            inputs/'stockA.bin',inputs/'stockB.bin')
    p = load_policy(root/PLAN/'native',direction='install',variant='native',
                    receipt=root/'native-returned-rom-036')
    mapping=json.loads((root/'native-returned-rom-036/manifest.json').read_text())['sg_binding']
    c=dict(schema=1,kind=KIND,adapter_sha256=proof.LIVE_SHA,observed_at=time.time(),
           receipt=str(root/'native-returned-rom-036'),plan=str(p.directory),
           output=str(root/'native-install-v1'),direction='install',variant='native',sg_binding=mapping)
    raw=proof.canonical(c);sha=proof.digest(raw)
    (root/'native-install-campaign.json').write_bytes(raw)
    (root/'.expanded36-native-install.consumed').write_text(sha)
    out=root/'native-install-v1';out.mkdir(mode=0o700)
    events=[]
    def log(event,**fields):events.append(dict(time=time.time(),event=event,**fields))
    class LoggedWire(Wire):
        def exchange(self,cdb,payload,size):
            index=self.calls
            log('sg_submit_intent',index=index,direction='install',cdb=cdb.hex(),
                out_len=len(payload),in_len=size,payload_sha256=proof.digest(payload) if payload else None,retry=False)
            response=super().exchange(cdb,payload,size)
            log('sg_completion',index=index,direction='install',status=0,masked=0,msg=0,
                host=0,driver=0,resid=0,info=0,sense_len=0,sense_hex='',retry=False,
                response_sha256=proof.digest(response) if size else None)
            return response
    log('native_transaction_prepared',campaign_sha256=sha,source_sha256=proof.SOURCES,
        adapter_sha256=proof.LIVE_SHA,backup_manifest_sha256=proof.MANIFEST_SHA,
        sg_binding=mapping,variant='native',direction='install',retry=False)
    wire=LoggedWire(p,bytearray(p.baseline))
    r=p.bind(wire).run(checkpoint=log)
    assert proof.digest(bytes(wire.nor.flash))==proof.NATIVE_SHA
    accepted=dict(campaign_sha256=sha,direction='install',variant='native',
        verified_sha256=proof.NATIVE_SHA,sectors_written=r['sectors_written'],
        full_flash_readback_verified=True,boot_observed=False,
        physical_recovery_verified=False,kernel_exclusivity=False)
    log('native_transaction_completed',**accepted)
    (out/'commands.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    (out/'result.json').write_text(json.dumps(accepted))
    verified=proof.verify(root,sha)
    assert 25572 <= verified['commands'] <= 32768 and verified['sectors']==213
    return dict(verified,simulation_only=True,physical_installation=False)


def check(inputs,shard):
    assert 0<=shard<16
    original=proof.digest((inputs/'native-install-campaign.json').read_bytes())
    assert 25572 <= proof.verify(inputs,original)['commands'] <= 32768
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)/'evidence';shutil.copytree(inputs,root)
        sha=rebase(root)
        assert proof.verify(root,sha)['sectors']==213
        transcript=root/'native-install-v1/commands.jsonl'
        events=[json.loads(line) for line in transcript.read_text().splitlines()]
        if shard<10:
            if shard==0:events.pop()
            elif shard==1:events.append(events[-1])
            elif shard==2:events[1]['cdb']='00'*16
            elif shard==3:events[2]['host']=1
            elif shard==4:next(e for e in events if e.get('in_len')==256)['index']+=1
            elif shard==5:next(e for e in events if e.get('out_len')==256)['payload_sha256']='0'*64
            elif shard==6:
                i=next(i for i,e in enumerate(events) if e.get('in_len')==256)
                events[i+1]['response_sha256']='0'*64
            elif shard==7:events[0]['time']=float('nan')
            elif shard==8:events[1]['time']=events[0]['time']-1
            else:events.pop(next(i for i,e in enumerate(events) if e['event']=='sector_verified'))
            transcript.write_text(''.join(json.dumps(e)+'\n' for e in events))
        elif shard==10:(root/'native-install-v1/result.json').write_text('{}')
        elif shard==11:(root/'.expanded36-native-install.consumed').write_text('0'*64)
        elif shard==12:
            path=root/PLAN/'native/journal.json';j=json.loads(path.read_text());j['state']='pending';path.write_text(json.dumps(j))
        elif shard in (13,14):
            path=root/PLAN/'native'/('target.bin' if shard==13 else 'backupB.bin')
            data=bytearray(path.read_bytes());data[0x5000]^=1;path.write_bytes(data)
        else:sha='0'*64
        try:proof.verify(root,sha)
        except (ValueError,KeyError):pass
        else:raise AssertionError('Corrupted evidence accepted')
    return dict(shard=shard,passed=True,simulation_only=True,hardware_operations=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--generate',type=Path)
    p.add_argument('--shard',type=int)
    a=p.parse_args()
    print(json.dumps(generate(a.inputs,a.generate) if a.generate else check(a.inputs,a.shard)))
