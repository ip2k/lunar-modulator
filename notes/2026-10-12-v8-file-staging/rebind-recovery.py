"""Rebind closed source-only recovery plan; no campaign imports or USB access."""
import ast,hashlib,io,json,tarfile
from pathlib import Path
BASE=Path('build/sdk-trace-fresh-entry-bench-v1/next-campaign/automatic-trace-chain-v7')
OLD=Path('build/fresh-diagnostic-v8-proposal-20261012');OUT=OLD/'rebound-v2';OUT.mkdir(mode=0o700)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(obj):return (json.dumps(obj,sort_keys=True,indent=2)+'\n').encode()
def save(name,raw):
 with (OUT/name).open('xb') as s:s.write(raw)
def paths(raw):return raw.replace('-v7','-v8')
spec=encode(json.loads(paths((BASE/'prospective-path-spec.json').read_text())))
save('prospective-path-spec.json',spec)
with tarfile.open(OLD/'closed-main-proposal.tar') as t:files={m.name:t.extractfile(m).read() for m in t}
closure=json.loads(files['entry/source-closure.json']);closure['partial_recovery_dependency']['prospective_path_spec_sha256']=sha(spec)
files['entry/source-closure.json']=encode(closure)
with (OUT/'closed-main-proposal.tar').open('xb') as stream:
 with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as t:
  for name,raw in sorted(files.items()):
   m=tarfile.TarInfo(name);m.size=len(raw);m.mode=0o600;t.addfile(m,io.BytesIO(raw))
archive=(OUT/'closed-main-proposal.tar').read_bytes()
inv=json.loads((OLD/'closed-entry-stage-inventory.json').read_text());inv['archive_sha256']=sha(archive);inv['archive_size']=len(archive)
inv['files']={k:{'mode':'0600','size':len(v),'sha256':sha(v)} for k,v in sorted(files.items())}
inv['partial_recovery_dependency']=closure['partial_recovery_dependency']
raw=encode(inv);save('closed-entry-stage-inventory.json',raw)
s=(OLD/'stage-closed-files-proposal.py').read_text().replace(sha((OLD/'closed-entry-stage-inventory.json').read_bytes()),sha(raw)).replace(sha((OLD/'closed-main-proposal.tar').read_bytes()),sha(archive));ast.parse(s);save('stage-closed-files-proposal.py',s.encode())
for name in ['closed-recovery-source-inventory.json','closed-recovery-source-proposal.tar','stage-recovery-source-files-proposal.py']:save(name,(OLD/name).read_bytes())
plan=json.loads(paths((BASE/'partial-recovery-plan-proposal.json').read_text()));plan['source_archive_sha256']=sha(archive)
save('partial-recovery-plan-proposal.json',encode(plan))
assert b'-v7' not in spec and b'-v7' not in encode(plan)
assert plan['failure_inputs']==json.loads(spec)['failure_inputs']
assert plan['hardware_execution_authorized_by_this_file'] is False
assert closure['partial_recovery_dependency']['reviewed_recovery_plan_sha256'] is None
save('assembly-check.json',encode({'main_files':len(files),'recovery_files':102,'archive_sha256':sha(archive),'prospective_spec_sha256':sha(spec),'four_activation_pins_bound':False,'source_execution':False,'hardware_commands':0,'matching_failure_paths':True}))
print((OUT/'assembly-check.json').read_text())
