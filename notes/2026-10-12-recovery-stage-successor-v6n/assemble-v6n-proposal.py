"""Close the current RAM reader into an offline recovery-model successor."""
import ast, hashlib, io, json, re, tarfile
from pathlib import Path, PurePosixPath
BASE=Path.cwd()
OLD=BASE/'build/partial-stock-recovery-production/next-campaign-readiness-v1/hera-owned-restore-v1/hera-owned-restore-v6/heavy-model-proposal-v6g-proposal'
NEW=OLD.parent/'heavy-model-proposal-v6n-proposal'
def sha(raw):return hashlib.sha256(raw).hexdigest()
raw=(OLD/'source-full-tree-v6.tar').read_bytes()
assert sha(raw)=='8935647033aa4fd03ef90f0f6c4a0744f0a694c23c785e048e66e6799f0a5ac3'
snap=json.loads((OLD/'snapshot-owned-restore-model-v6g-heavy.json').read_bytes())
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 members=archive.getmembers()
 assert all(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts for m in members)
 base={m.name:archive.extractfile(m).read() for m in members}
assert len(base)==len(members) and {n:sha(b) for n,b in base.items()}==snap['source_sha256']
extras=[str(p.relative_to(BASE)) for p in sorted((BASE/'tools/bench_capture/lifecycle-v1').glob('*.py'))]
for extra in extras:
 if extra not in base:
  base[extra]=(BASE/extra).read_bytes()
  m=tarfile.TarInfo(extra);m.mode=0o755;members.append(m)
extra='tools/bench_capture/lifecycle-v1/owned-install-boot-once.py'
HISTORICAL=b'7d2cec8584bc274c534046d490f3c319bd7e0c13dec6d1f654323e9c9aa8dd8b'
SUCCESSOR=b'59b8e8c23f494f0ac6c89585786f72a9b408d5692e2a5fbf66c2c0376945c52d'
assert sha(base['tools/bench_capture/lifecycle-v1/historical-install-7d2.py']).encode()==HISTORICAL
assert sha(base[extra]).encode()==SUCCESSOR

seed=dict(base)
for name in ('tools/fm1_sdk_trace_read.py','tests/retained_partial_fixture.py'):
 assert name in base
 seed[name]=(BASE/name).read_bytes()
assert sha(seed['tools/fm1_sdk_trace_read.py'])=='411d80186d47dc3786fe2ad48eca5b8fbf7295523c417931b89e75a64cf62051'
# The installed capture is an independently hashed source input, not a runtime override.
seed['capture-pins/owned-install-boot-once.py']=base[extra]
current=dict(seed)
for iteration in range(40):
 mapping={sha(base[n]).encode():sha(current[n]).encode() for n in base
          if current[n]!=base[n] and sha(base[n]).encode()!=HISTORICAL}
 # Historical evidence identity is policy, never a transitive dependency pin.
 assert HISTORICAL not in mapping
 revised={n:re.sub(rb'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',lambda m:mapping.get(m[0],m[0]),b) if n.endswith(('.py','.json')) else b for n,b in seed.items()}
 if revised==current:break
 current=revised
else:raise ValueError('dependency hash closure did not converge')
changes={n:dict(before=sha(base[n]),after=sha(b)) for n,b in current.items() if b!=base[n]}
for n,b in current.items():
 if n.endswith('.py'):ast.parse(b)
for name in ('source-inventory.json','tests/source-inventory.json'):
 inv=json.loads(current[name]);assert all(sha(current[n])==pin for n,pin in inv['source_pins'].items())
assert sha(current['tools/fm1_sdk_trace_read.py'])=='411d80186d47dc3786fe2ad48eca5b8fbf7295523c417931b89e75a64cf62051'
adapter=ast.parse(current['tools/fm1_retained_partial_recovery.py'])
constants={n.targets[0].id:ast.literal_eval(n.value) for n in adapter.body
           if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
           and n.targets[0].id in ('INSTALL_CAPTURE_SHA','INSTALL_CAPTURE_SUCCESSOR_SHA')}
assert constants==dict(INSTALL_CAPTURE_SHA=HISTORICAL.decode(),INSTALL_CAPTURE_SUCCESSOR_SHA=SUCCESSOR.decode())
assert HISTORICAL!=SUCCESSOR
for name in ('tests/test_retained_partial_recovery.py','tests/retained_partial_fixture.py',
             'tools/bench_capture/lifecycle-v1/test_install_capture_allowlist.py'):
 assert HISTORICAL in current[name] and SUCCESSOR in current[name],name
NEW.mkdir(mode=0o700)
with tarfile.open(NEW/'source-full-tree-v6.tar','x',format=tarfile.USTAR_FORMAT) as out:
 for m in members:
  b=current[m.name];entry=tarfile.TarInfo(m.name);entry.size=len(b);entry.mode=m.mode;entry.mtime=entry.uid=entry.gid=0;out.addfile(entry,io.BytesIO(b))
runner=(OLD/'run-owned-restore-model-v6g-heavy-proposal.py').read_bytes().replace(b'v6g',b'v6n')
(NEW/'run-owned-restore-model-v6n-heavy-proposal.py').write_bytes(runner)
snap.update(archive_sha256=sha((NEW/'source-full-tree-v6.tar').read_bytes()),archive_bytes=(NEW/'source-full-tree-v6.tar').stat().st_size,runner_sha256=sha(runner),session_label='partial-stock-restore-wrapper-model-v6n-heavy-proposal',source_sha256={n:sha(b) for n,b in current.items()},source_scope='V6g plus current panel-error RAM reader, strict current private fixture, current install capture, transitive source-pin closure protecting historical capture identity; complete lifecycle regression sources; no hardware activation')
(NEW/'snapshot-owned-restore-model-v6n-heavy.json').write_text(json.dumps(snap,sort_keys=True,indent=2)+'\n')
delta=dict(iterations=iteration,changes=changes,added_sources={n:sha(current[n]) for n in extras if n not in snap["source_sha256"]},capture_identities=constants,hardware_access=False,bench_activation=False,archive_sha256=snap['archive_sha256'],runner_sha256=snap['runner_sha256'])
(NEW/'source-delta.json').write_text(json.dumps(delta,sort_keys=True,indent=2)+'\n')
(BASE/'notes/2026-10-12-recovery-stage-successor-v6n/source-delta.json').write_text(json.dumps(delta,sort_keys=True,indent=2)+'\n')
print(json.dumps(dict(archive_sha256=snap['archive_sha256'],runner_sha256=snap['runner_sha256'],files=len(current),changes=len(changes),iterations=iteration),indent=2))
