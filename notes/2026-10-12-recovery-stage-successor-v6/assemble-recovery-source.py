"""Assemble exact modeled recovery sources only; never execute staged code."""
import ast
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath

BASE = Path.cwd()
MODEL = BASE / 'build/partial-stock-recovery-production/next-campaign-readiness-v1/hera-owned-restore-v1/hera-owned-restore-v6/heavy-model-proposal-v6g-proposal/source-full-tree-v6.tar'
OUTPUT = BASE / 'build/sdk-trace-fresh-entry-bench-v1/next-campaign/automatic-trace-chain-v6'
MODEL_SHA = '8935647033aa4fd03ef90f0f6c4a0744f0a694c23c785e048e66e6799f0a5ac3'
HELPER_SHA = '009686b741a4b9beea9cda80cd71712079b729107847ede9de86394d911e9abf'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()

def save(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(0o600)

raw = MODEL.read_bytes()
assert sha(raw) == MODEL_SHA
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
    members = archive.getmembers()
    assert all(m.isfile() and not PurePosixPath(m.name).is_absolute()
               and '..' not in PurePosixPath(m.name).parts for m in members)
    assert len({m.name for m in members}) == len(members)
    source = {m.name: archive.extractfile(m).read() for m in members}

inventory = json.loads(source['source-inventory.json'])
pins = inventory['source_pins']
assert len(pins) == 38
assert sha(source['prepare-file-only.py']) == HELPER_SHA
historical = {}
selected = {'prepare-file-only.py': source['prepare-file-only.py'],
            'source-inventory.json': source['source-inventory.json']}
for name, pin in pins.items():
    assert name.startswith('tools/') and '..' not in PurePosixPath(name).parts
    assert sha(source[name]) == pin
    checkout_sha = sha((BASE / name).read_bytes())
    if checkout_sha != pin:
        assert name == 'tools/fm1_sdk_trace_read.py'
        assert pin == '6c9ed93284def1a95f60a42491b92acda0b116d26c224e2138643bd234fc5a43'
        assert checkout_sha == '411d80186d47dc3786fe2ad48eca5b8fbf7295523c417931b89e75a64cf62051'
        historical[name] = dict(modeled_sha256=pin, checkout_sha256=checkout_sha,
                               physical_successor_verification_pending=True)
    selected[name] = source[name]
for name, data in selected.items():
    if name.endswith('.py'):
        ast.parse(data)

roots = {name: '/home/claude/fm1-sdk-trace-partial-' + name + '-20261012-v6'
         for name in ('acquire', 'restore')}
payload = {group + '/' + name: data for group in roots
           for name, data in selected.items()}
assert len(payload) == 80
OUTPUT.mkdir(mode=0o700)
with tarfile.open(OUTPUT / 'closed-recovery-source-proposal.tar', 'x',
                  format=tarfile.USTAR_FORMAT) as archive:
    for name, data in sorted(payload.items()):
        entry = tarfile.TarInfo(name)
        entry.size = len(data)
        entry.mode = 0o600
        entry.uid = entry.gid = entry.mtime = 0
        archive.addfile(entry, io.BytesIO(data))
record = dict(schema=1, kind='fm1-v6-exclusive-recovery-source-only-proposal',
              roots=roots, file_count=len(payload), files_per_root=len(selected),
              source_pins=pins, helper_sha256=HELPER_SHA,
              source_inventory_sha256=sha(source['source-inventory.json']),
              model_source_archive_sha256=MODEL_SHA,
              archive_sha256=sha((OUTPUT / 'closed-recovery-source-proposal.tar').read_bytes()),
              files={name: dict(sha256=sha(data), size=len(data), mode='0600')
                     for name, data in sorted(payload.items())},
              historical_source_boundaries=historical,
              execution_authorized=False, source_execution=False,
              hardware_opened=False, physical_recovery_verified=False,
              required_absent=['request.json', 'witness.json', 'preparation-intent.json',
                               'stopped.json', 'campaign.json', 'packet.json',
                               'file-only-preflight.json', 'partial-to-stock-transaction'])
save(OUTPUT / 'closed-recovery-source-inventory.json', encoded(record))
print(json.dumps({key: record[key] for key in
                  ('archive_sha256', 'file_count', 'files_per_root', 'roots')}, indent=2))
