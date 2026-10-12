"""Sixteen native-fixture model containers; immutable ELF input, no devices."""
import ast, concurrent.futures, hashlib, json, subprocess, sys
from pathlib import Path
IMAGE='sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'
SOURCE=Path('/home/claude/mvave-fm1/owned-restore-v6k-resumed-20261012/heavy-model-proposal-v6k/source-extracted-v6b-heavy')
OUT=SOURCE.parent/'native-16m';OUT.mkdir(mode=0o700)
FILES=['tests/test_sdk_trace_sg.py','tests/test_sdk_trace_read.py']
NATIVE=Path('/home/claude/mvave-fm1/sdk-trace-install-20261012/emitter-source-v1/build/sdk-recovery-trace-hera/native-enabled')
NATIVE_NAMES=('lunar-sdk-diagnostic.elf','lunar-sdk-diagnostic.app.bin','build-manifest.json')
SESSION='lunar-v6m-native-current-reader-16-20261012'
def save(path,obj):
 with path.open('x') as f:json.dump(obj,f,sort_keys=True,indent=2);f.write('\n')
def command(name,pytest_args):
 # No host evidence mounts are writable; stdout is retained by the host runner.
 code="import os,shutil,subprocess,sys;shutil.copytree('/source','/shard-work');os.chdir('/shard-work');os.environ['PYTHONPATH']='/shard-work/tests:/shard-work/tools';sys.exit(subprocess.call(['/tmp/check-venv/bin/python','-m','pytest','-q','-o','addopts=','-p','no:cacheprovider',*sys.argv[1:]]))"
 return ['docker','run','--name',name,'--network=none','--cpus=1','--memory=1g','--memory-swap=2g',
 '--cgroup-parent=docker-batch.slice','--label','lan.project=lunar-modulator','--label','lan.session='+SESSION,
 '-e','PYTHONDONTWRITEBYTECODE=1','-e','LUNAR_REQUIRE_PRIVATE_FIXTURES=1',
 '-e','LUNAR_TRACE_NATIVE=/native','-v',str(NATIVE)+':/native:ro','-v',str(SOURCE)+':/source:ro',IMAGE,
 '/tmp/check-venv/bin/python','-c',code,*pytest_args]
def run(index,args):
 name=SESSION+'-'+str(index);argv=command(name,args)
 result=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (OUT/(str(index)+'.log')).write_bytes(result.stdout)
 inspect=subprocess.check_output(['docker','inspect',name]);(OUT/(str(index)+'.inspect.json')).write_bytes(inspect)
 info=json.loads(inspect)[0]
 assert not info['HostConfig']['Privileged'] and not info['HostConfig']['Devices']
 assert info['HostConfig']['NetworkMode']=='none'
 assert {m['Destination'] for m in info['Mounts']}=={'/source','/native'}
 assert all(m['RW'] is False for m in info['Mounts'])
 save(OUT/(str(index)+'.result.json'),dict(command=argv,exit_code=result.returncode,container_id=info['Id'],hardware_access=False))
 # Keep failed/stopped containers; cleanup successful exact owned containers only.
 if result.returncode==0:subprocess.run(['docker','rm',info['Id']],check=True,stdout=subprocess.DEVNULL)
 return result.returncode,result.stdout
assert SOURCE.is_dir() and NATIVE.is_dir()
native_before={n:hashlib.sha256((NATIVE/n).read_bytes()).hexdigest() for n in NATIVE_NAMES}
save(OUT/'native-input-before.json',native_before)
snapshot=json.loads((SOURCE.parent/'snapshot-owned-restore-model-v6k-heavy.json').read_bytes())
actual={str(p.relative_to(SOURCE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()}
assert actual==snapshot['source_sha256']
assert subprocess.check_output(['docker','image','inspect',IMAGE,'--format={{.Id}}'],text=True).strip()==IMAGE
assert not subprocess.check_output(['docker','ps','-aq','--filter','label=lan.session='+SESSION],text=True).strip()
status,output=run('collect',['--collect-only',*FILES])
if status:raise SystemExit(status)
nodes=[line for line in output.decode().splitlines() if line.startswith(('tests/','tools/')) and '::' in line]
assert len(nodes)==len(set(nodes)) and len(nodes)>=16
# Follow only the fixture dependencies native -> read_prepared/prepared.
selected={}
for file in FILES:
 tree=ast.parse((SOURCE/file).read_bytes())
 selected[file]={n.name for n in tree.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_') and any(a.arg in ('native','prepared') for a in n.args.args)}
nodes=[n for n in nodes if n.split('::')[1].split('[')[0] in selected[n.split('::')[0]]]
assert len(nodes)==71, len(nodes)
chunks=[nodes[i::16] for i in range(16)]
save(OUT/'shards.json',dict(nodes=nodes,chunks=chunks,source_archive_sha256='5c4ae2e772e26ec8c5b33d47848c350eca93b702268dec74b02889dc5d43c584',hardware_access=False))
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
 results=list(pool.map(lambda item:run(*item),enumerate(chunks)))
native_after={n:hashlib.sha256((NATIVE/n).read_bytes()).hexdigest() for n in NATIVE_NAMES}
save(OUT/'native-input-after.json',native_after)
assert native_before==native_after
save(OUT/'summary.json',dict(native_inputs_unchanged=True,shards=16,nodes=len(nodes),exit_codes=[r[0] for r in results],hardware_access=False))
print((OUT/'summary.json').read_text())
raise SystemExit(0 if all(r[0]==0 for r in results) else 1)
