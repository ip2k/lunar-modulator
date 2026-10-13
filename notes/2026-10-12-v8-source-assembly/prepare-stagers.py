"""Derive file-only stagers; not executed here."""
import ast,hashlib,json,tarfile
from pathlib import Path
BASE=Path('build/sdk-trace-fresh-entry-bench-v1/next-campaign/automatic-trace-chain-v7')
OUT=Path('build/fresh-diagnostic-v8-proposal-20261012')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(obj):return (json.dumps(obj,sort_keys=True,indent=2)+'\n').encode()
def save(name,raw):
 with (OUT/name).open('xb') as stream:stream.write(raw)
def paths(raw):
 for a,b in [('20261012-v7','20261012-v8'),('automatic-trace-chain-v7','automatic-trace-chain-v8'),('initial-entry-backup-v7','initial-entry-backup-v8'),('partial-recovery-v7','partial-recovery-v8'),('fm1-v7-','fm1-v8-'),('trace-stage-v7','trace-stage-v8')]:raw=raw.replace(a,b)
 return raw
main=json.loads(paths((BASE/'closed-entry-stage-inventory.json').read_text()))
proposal=json.loads((OUT/'closed-main-inventory.json').read_text())
main.update(archive_sha256=proposal['archive_sha256'],archive_size=(OUT/'closed-main-proposal.tar').stat().st_size,file_count=108,stage_file_count=81,files={k:{**v,'mode':'0600'} for k,v in proposal['files'].items()})
main['changes']={k:{'before':None,'after':v['sha256']} for k,v in main['files'].items() if k not in json.loads((BASE/'closed-entry-stage-inventory.json').read_text())['files'] or v['sha256']!=json.loads((BASE/'closed-entry-stage-inventory.json').read_text())['files'][k]['sha256']}
raw=encode(main);save('closed-entry-stage-inventory.json',raw)
s=paths((BASE/'stage-closed-files-proposal.py').read_text()).replace("'5cbcde4508b995fb417da710a5ff7a591140a5cfb4301f5812ac14ccebe2d02e'",repr(sha(raw))).replace("'9b7d1b80fc1fef6e7114515397e3dcc08354c88e9634ecdfb563fe0d8e2e5607'",repr(proposal['archive_sha256']))
s=s.replace("!= 107","!= 108").replace("'file_count': 107","'file_count': 108").replace("!= 80","!= 81").replace("'stage_file_count': 80","'stage_file_count': 81")
ast.parse(s);save('stage-closed-files-proposal.py',s.encode())
# Recovery archive sources themselves have no V7-specific executable paths.
raw=(BASE/'closed-recovery-source-proposal.tar').read_bytes()
assert sha(raw)=='83cb64143b8130f4764e953f7ef15eaca1b12c8803e922555aad12c6af2bce13'
recovery=json.loads(paths((BASE/'closed-recovery-source-inventory.json').read_text()))
with tarfile.open(BASE/'closed-recovery-source-proposal.tar') as tar:
 members=tar.getmembers();assert len(members)==102 and len({m.name for m in members})==102
 for member in members:
  assert member.isfile();data=tar.extractfile(member).read();assert sha(data)==recovery['files'][member.name]['sha256']
  if member.name.endswith('.py'):assert b'-v7' not in data;ast.parse(data)
save('closed-recovery-source-proposal.tar',raw)
raw=encode(recovery);save('closed-recovery-source-inventory.json',raw)
s=paths((BASE/'stage-recovery-source-files-proposal.py').read_text()).replace("'1239f21dbed4246aabf56298a91d2367fea049e90c1dd9e085384ff2db13a570'",repr(sha(raw)))
ast.parse(s);save('stage-recovery-source-files-proposal.py',s.encode())
print(json.dumps({'main_files':108,'recovery_files':102,'stagers_executed':False,'hardware_commands':0}))
