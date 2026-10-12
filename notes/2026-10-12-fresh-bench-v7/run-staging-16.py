"""Sixteen independent, device-free actual staging guard scenarios on Hera."""
import concurrent.futures
import json
import subprocess
from pathlib import Path

SOURCE = Path('/home/claude/mvave-fm1/staging-v7b-16-20261012/inputs')
OUT = SOURCE.parent/'evidence'
IMAGE = 'sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'
SESSION = 'lunar-v7b-staging-16-20261012'

def run(index):
    name = SESSION+'-'+str(index)
    command = ['docker','run','--name',name,'--network=none','--cpus=1','--memory=1g',
               '--cgroup-parent=docker-batch.slice','--label','lan.project=lunar-modulator',
               '--label','lan.session='+SESSION,'-v',str(SOURCE)+':/inputs:ro',IMAGE,
               '/tmp/check-venv/bin/python','-B','/inputs/check-staging-scenario.py',str(index)]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (OUT/(str(index)+'.log')).write_bytes(result.stdout)
    raw = subprocess.check_output(['docker','inspect',name])
    (OUT/(str(index)+'.inspect.json')).write_bytes(raw)
    info = json.loads(raw)[0]; host = info['HostConfig']
    assert not host['Privileged'] and not host['Devices'] and host['NetworkMode']=='none'
    assert len(info['Mounts'])==1 and info['Mounts'][0]['RW'] is False
    (OUT/(str(index)+'.result.json')).write_text(json.dumps(dict(exit_code=result.returncode,command=command,container_id=info['Id'],hardware_access=False),indent=2)+'\n')
    if result.returncode==0: subprocess.run(['docker','rm',info['Id']],check=True,stdout=subprocess.DEVNULL)
    return result.returncode

OUT.mkdir(mode=0o700)
assert not subprocess.check_output(['docker','ps','-aq','--filter','label=lan.session='+SESSION],text=True).strip()
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
    results = list(pool.map(run, range(16)))
summary = dict(shards=16,exit_codes=results,hardware_access=False)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
raise SystemExit(0 if all(code==0 for code in results) else 1)
