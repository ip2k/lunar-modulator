#!/usr/bin/env python3
"""File-only closed proposal assembly. Never imports campaign code or opens USB."""
import ast, hashlib, io, json, re, tarfile
from pathlib import Path
BASE=Path('build/sdk-trace-fresh-entry-bench-v1/next-campaign/automatic-trace-chain-v7')
OUT=Path('build/fresh-diagnostic-v8-proposal-20261012')
def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(obj): return (json.dumps(obj,sort_keys=True,indent=2)+'\n').encode()
def archive(path,pin):
 raw=path.read_bytes();assert sha(raw)==pin
 with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
  members=tar.getmembers();assert len({m.name for m in members})==len(members)
  assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
  return {m.name:tar.extractfile(m).read() for m in members}
a=archive(BASE/'closed-entry-stage-proposal.tar','9b7d1b80fc1fef6e7114515397e3dcc08354c88e9634ecdfb563fe0d8e2e5607')
b=archive(OUT/'closed-native-inputs.tar','a2d0be59b94cc9a6895c1a279b67e8bb9b0161d8f3fae2bdf2ab08c90779b538')
inv=json.loads((BASE/'closed-entry-stage-inventory.json').read_bytes())
assert set(a)==set(inv['files'])
for name,raw in a.items():assert sha(raw)==inv['files'][name]['sha256'] and len(raw)==inv['files'][name]['size']
assert [name for name in sorted(a.keys()&b.keys()) if a[name]!=b[name]]==['entry/sequence-once.py']
original={**a,**b}
# Rebind operational paths only. Historical evidence and native build receipts stay byte-identical.
renames={'20261012-v7':'20261012-v8','automatic-trace-chain-v7':'automatic-trace-chain-v8','initial-entry-backup-v7':'initial-entry-backup-v8','partial-recovery-v7':'partial-recovery-v8'}
def paths(s):
 for before,after in renames.items():s=s.replace(before,after)
 return s
original={paths(k):v for k,v in original.items()}
texts={k:v.decode() for k,v in original.items() if (k.endswith('.py') and '/identity-once/' not in k) or (k.endswith('.json') and (k.startswith('entry/inputs/') or k in ('entry/source-closure.json','entry/pins.json','stage/bundle-manifest.json') or k.endswith('/source-inventory.json')))}
base_text={k:paths(v) for k,v in texts.items()}
files=dict(original)
for k,v in base_text.items():files[k]=v.encode()
# Propagate source hashes from original sources to derivatives, using original text each round.
for round_number in range(20):
 replacements={sha(original[k]):sha(files[k]) for k in original if original[k]!=files[k]}
 updated=dict(files)
 for k,s in base_text.items():
  s=re.sub(r'\b[0-9a-f]{64}\b',lambda m:replacements.get(m[0],m[0]),s)
  updated[k]=s.encode()
 if updated==files:break
 files=updated
else:raise ValueError('Source pin propagation did not converge; no staging')
# The manifest's sizes must follow its rebound source bytes.
name='stage/bundle-manifest.json';manifest=json.loads(files[name])
for row in manifest['files']:
 raw=files['stage/'+row['staged']];row['sha256']=sha(raw);row['size']=len(raw)
files[name]=encoded(manifest)
name='entry/source-closure.json';closure=json.loads(files[name])
for field,prefix in [('entry_files','entry/'),('entry_derivatives','entry/'),('stage_files','stage/'),('inputs','entry/inputs/')]:
 for relative in closure[field]:closure[field][relative]=sha(files[prefix+relative])
closure['stage_files']['tools/fm1_prepare_native_read_packet.py']=sha(files['stage/tools/fm1_prepare_native_read_packet.py'])
files[name]=encoded(closure)
for k,raw in files.items():
 if k.endswith('.py'):ast.parse(raw,filename=k)
for k in a:
 if '/identity-once/' in k or k.startswith('stage/assets/'):
  assert files[paths(k)]==a[k],k
assert all(pin is None for pin in [next(n.value.value for n in ast.parse(files['entry/sequence-once.py']).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==key for t in n.targets)) for key in ['WIRE_SHA','CLOSURE_SHA','ROOT_ACCEPTANCE_SHA','RECOVERY_PLAN_SHA']])
with (OUT/'closed-main-proposal.tar').open('xb') as stream:
 with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as tar:
  for k,raw in sorted(files.items()):
   member=tarfile.TarInfo(k);member.size=len(raw);member.mode=0o600;tar.addfile(member,io.BytesIO(raw))
receipt={'schema':1,'file_count':len(files),'archive_sha256':sha((OUT/'closed-main-proposal.tar').read_bytes()),'execution_authorized':False,'hardware_commands':0,'activation_pins_bound':False,'historical_identity_fresh':False,'source_pin_rounds':round_number+1,'entry_root':closure['entry_root'],'stage_root':closure['unchanged_stage'],'files':{k:{'sha256':sha(v),'size':len(v)} for k,v in sorted(files.items())},'pending':['separate recovery source staging closure','exact staging helper and model verification','fresh identity binding and source acceptance review']}
with (OUT/'closed-main-inventory.json').open('xb') as stream:stream.write(encoded(receipt))
print(json.dumps({k:v for k,v in receipt.items() if k!='files'},indent=2))
