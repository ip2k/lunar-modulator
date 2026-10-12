"""Offline successor source closure: literal pins, no runtime overrides."""
import ast, hashlib, io, json, re, tarfile
from pathlib import Path
ROOT=Path(__file__).absolute().parent
OLD=ROOT/'heavy-model-proposal-v6d-proposal'
NEW=ROOT/'heavy-model-proposal-v6g-proposal'
NEW.mkdir(mode=0o700)
def sha(b):return hashlib.sha256(b).hexdigest()
old_snap=json.loads((OLD/'snapshot-owned-restore-model-v6d-heavy.json').read_bytes())
archive=(OLD/'source-full-tree-v6.tar').read_bytes()
assert sha(archive)==old_snap['archive_sha256']
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
 members=tf.getmembers()
 assert all(m.isfile() for m in members)
 base={m.name:tf.extractfile(m).read() for m in members}
assert {n:sha(b) for n,b in base.items()}==old_snap['source_sha256']
seed=dict(base)
name='tools/fm1_sdk_trace_return_admission.py'
seed[name]=(Path.cwd()/name).read_bytes()
assert sha(seed[name])=='6eb30cfd770a596c838b454bd2e79a4a39f4929274477aed193da24a036dd60e'
seed['tools/fm1_retained_partial_recovery.py']=(Path.cwd()/'tools/fm1_retained_partial_recovery.py').read_bytes()
assert sha(seed['tools/fm1_retained_partial_recovery.py'])=='068fd62cf80666b39ee3e1ca041df8ddd4271d512ab8ff4b5374a3fd0894f32e'
seed['tests/test_retained_partial_recovery.py']=(Path.cwd()/'tests/test_retained_partial_recovery.py').read_bytes()
launcher_name='tests/model-owned-restore-launcher.py'
launcher=base[launcher_name]
old=b"from test_sdk_rehearsal import SGModel"
new=b"""# Load only the device model definitions; importing the entire test module
# would cache outer-tree production modules before the staged factory imports.
import ast, binascii, copy, ctypes as C, importlib, stat
staged_tools = Path(req['stage']) / 'tools'
sys.path.insert(0, str(staged_tools))
rehearsal = importlib.import_module('fm1_sdk_rehearsal')
if Path(rehearsal.__file__).absolute() != staged_tools / 'fm1_sdk_rehearsal.py':
    raise ValueError('Model requires the real staged rehearsal module')
model_source = Path(req['tests_path']) / 'test_sdk_rehearsal.py'
model_tree = ast.parse(model_source.read_bytes(), filename=str(model_source))
model_nodes = [n for n in model_tree.body if
    isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in ('wire', 'SGModel')]
if len(model_nodes) != 2 or {n.name for n in model_nodes} != {'wire', 'SGModel'}:
    raise ValueError('Exact two model definitions required')
model_namespace = dict(rehearsal=rehearsal, binascii=binascii, copy=copy, C=C,
    stat=stat, os=os, SimpleNamespace=SimpleNamespace)
exec(compile(ast.Module(body=model_nodes, type_ignores=[]), str(model_source), 'exec'), model_namespace)
SGModel = model_namespace['SGModel']"""
assert launcher.count(old)==1
seed[launcher_name]=launcher.replace(old,new)

# Compute the transitive literal dependency closure from the immutable baseline.
# Historical docs/captures are not rewritten; only executable/source inventories.
current=dict(seed)
for iteration in range(40):
 mapping={sha(base[n]).encode():sha(current[n]).encode() for n in base if current[n]!=base[n]}
 revised={}
 for n,b in seed.items():
  if n.endswith(('.py','.json')):
   b=re.sub(rb'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',lambda m:mapping.get(m[0],m[0]),b)
  revised[n]=b
 if revised==current:break
 current=revised
else:raise ValueError('source dependency hash cycle or nonconvergence')
changes={n:dict(before=sha(base[n]),after=sha(b)) for n,b in current.items() if b!=base[n]}
for n in changes:
 if n.endswith('.py'):ast.parse(current[n])
for invname in ('source-inventory.json','tests/source-inventory.json'):
 inv=json.loads(current[invname])
 assert all(sha(current[n])==pin for n,pin in inv['source_pins'].items())
with tarfile.open(NEW/'source-full-tree-v6.tar','w',format=tarfile.USTAR_FORMAT) as out:
 for m in members:
  b=current[m.name];info=tarfile.TarInfo(m.name);info.size=len(b);info.mode=m.mode;info.mtime=0;info.uid=info.gid=0
  out.addfile(info,io.BytesIO(b))
runner=(OLD/'run-owned-restore-model-v6d-heavy-proposal.py').read_bytes().replace(b'v6d',b'v6g')
(NEW/'run-owned-restore-model-v6g-heavy-proposal.py').write_bytes(runner)
snap=dict(old_snap,archive_sha256=sha((NEW/'source-full-tree-v6.tar').read_bytes()),archive_bytes=(NEW/'source-full-tree-v6.tar').stat().st_size,
 runner_sha256=sha(runner),session_label='partial-stock-restore-wrapper-model-v6g-heavy-proposal',
 source_sha256={n:sha(b) for n,b in current.items()},source_scope='V6d plus original capture-stage derivation, current 068fd recovery adapter and its tracked tests, staged-model import isolation, exact transitive literal-pin successor proposal')
(NEW/'snapshot-owned-restore-model-v6g-heavy.json').write_text(json.dumps(snap,sort_keys=True,indent=2)+'\n')
(NEW/'source-delta.json').write_text(json.dumps(dict(iterations=iteration,changes=changes,hardware_access=False,bench_activation=False),sort_keys=True,indent=2)+'\n')
print(json.dumps(dict(archive_sha256=snap['archive_sha256'],runner_sha256=snap['runner_sha256'],iterations=iteration,changes=changes),indent=2))
