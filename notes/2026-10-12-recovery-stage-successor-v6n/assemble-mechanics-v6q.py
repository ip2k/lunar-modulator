"""Add the omitted outer-test manifest without changing the heavy model source."""
import hashlib,io,json,tarfile
from pathlib import Path
BASE=Path.cwd()
OLD=BASE/'build/partial-stock-recovery-production/next-campaign-readiness-v1/hera-owned-restore-v1/hera-owned-restore-v6/heavy-model-proposal-v6n-proposal'
OUT=OLD.parent/'mechanics-v6q-proposal';OUT.mkdir(mode=0o700)
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=(OLD/'source-full-tree-v6.tar').read_bytes()
assert sha(raw)=='4592dc9faeedc28915d8ac7c1e8330ff7c03f388750de446018514d6365c3e85'
with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
 members=tf.getmembers();sources={m.name:tf.extractfile(m).read() for m in members}
snapshot=json.loads((OLD/'snapshot-owned-restore-model-v6n-heavy.json').read_text())
assert {n:sha(b) for n,b in sources.items()}==snapshot['source_sha256']
name='tools/bench_capture/lifecycle-v1/source-pins.json';assert name not in sources
pins=json.loads((BASE/name).read_text())
for n,pin in pins.items():assert sha((BASE/'tools/bench_capture/lifecycle-v1'/n).read_bytes())==pin
pins={n:sha(sources['tools/bench_capture/lifecycle-v1/'+n]) for n in pins}
sources[name]=(json.dumps(pins,sort_keys=True,indent=2)+'\n').encode()
m=tarfile.TarInfo(name);m.mode=0o644;members.append(m)
with tarfile.open(OUT/'source.tar','x',format=tarfile.USTAR_FORMAT) as tf:
 for m in members:
  b=sources[m.name];entry=tarfile.TarInfo(m.name);entry.size=len(b);entry.mode=m.mode;entry.mtime=entry.uid=entry.gid=0;tf.addfile(entry,io.BytesIO(b))
manifest=dict(base_archive_sha256=snapshot['archive_sha256'],archive_sha256=sha((OUT/'source.tar').read_bytes()),source_sha256={n:sha(b) for n,b in sources.items()},added_sources={name:sha(sources[name])},hardware_access=False)
(OUT/'source-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
(BASE/'notes/2026-10-12-recovery-stage-successor-v6n/mechanics-v6q-extension.json').write_text(json.dumps({k:v for k,v in manifest.items() if k!='source_sha256'},sort_keys=True,indent=2)+'\n')
print(manifest['archive_sha256'])
