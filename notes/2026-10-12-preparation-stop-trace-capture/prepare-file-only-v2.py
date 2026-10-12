"""Private file-only preparation. Never invokes a transport or capture runner."""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

stage = Path('/home/claude/fm1-stop-trace-capture-v2-20261012')
run = stage / 'run'
original = Path('/home/claude/fm1-sdk-trace-campaign-20261012-v7')
entry = Path('/home/claude/fm1-sdk-trace-entry-20261012-v7')
assert sys.platform == 'linux' and os.geteuid() == 0
assert stage.is_dir() and not run.exists()
os.umask(0o077)
stage.chmod(0o700)
run.mkdir(mode=0o700)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
canonical = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def save(path, value):
    with path.open('xb') as f:
        f.write(canonical(value)); f.flush(); os.fsync(f.fileno())

inventory = json.loads((stage / 'source-sha256.json').read_bytes())
assert all(sha(stage / name) == pin for name, pin in inventory.items())
proof_pin = sha(stage / 'tools/fm1_sdk_trace_prepare_stop.py')
source = stage / 'tools/fm1_sdk_prepare_stop_trace_read.py'
raw = source.read_text()
assert raw.count('PROOF_SOURCE_SHA = None') == 1
source.write_text(raw.replace('PROOF_SOURCE_SHA = None', 'PROOF_SOURCE_SHA = ' + repr(proof_pin)))
sys.path.insert(0, str(stage / 'tools'))
native = importlib.import_module('fm1_sdk_prepare_stop_trace_read')
proof_module = importlib.import_module('fm1_sdk_trace_prepare_stop')
lineage = original / 'boot-lineage.json'
chain = entry / 'automatic-trace-chain-v7'
proof = proof_module.validate_preparation_stop(lineage, chain)
proof.check()
historical = json.loads(proof.snapshot)
bridge = importlib.import_module('fm1_fixed_loader_backup')
usb = bridge.usb_snapshot(Path('/sys/bus/usb/devices') / historical['usb_binding']['path'])
sg = bridge.discover_sg(usb)
assert canonical(usb) == canonical(historical['usb_binding'])
assert canonical(sg) == canonical(historical['sg_binding'])
stop = run / 'preparation-stop.json'
save(stop, dict(schema=1, kind='fm1-native-preparation-stop-evidence', boot_lineage_path=str(lineage),
    boot_lineage_sha256=sha(lineage), chain_path=str(chain)))
witness = run / 'witness.json'
observed = time.time()
save(witness, dict(schema=1, kind='fm1-passive-sdk-preparation-stop-trace-connection', observed_at=observed,
    usb_binding=usb, sg_binding=sg, original_rom_snapshot_sha256=proof.snapshot_sha256,
    preparation_stop_sha256=sha(stop), quiet_state=native.STATE))
campaign = run / 'campaign.json'
save(campaign, dict(schema=1, kind=native.KIND, adapter_sha256=sha(source), preparation_stop_path=str(stop),
    preparation_stop_sha256=sha(stop), connection_witness_path=str(witness), connection_witness_sha256=sha(witness),
    elf_path=str(original / 'assets/native/lunar-sdk-diagnostic.elf'),
    app_path=str(original / 'assets/native/lunar-sdk-diagnostic.app.bin'),
    manifest_path=str(original / 'assets/native/build-manifest.json'),
    receipt_path=str(proof.lineage.parent / 'physical-distinct-preparation-stop-trace-v2'), active_session_state=native.STATE))
prepared = native.prepare_campaign(campaign)
prepared.check()
save(run / 'preflight.json', dict(schema=1, file_only=True, device_commands=0, observed_at=observed,
    witness_expires_at=observed + 120, historical_snapshot_sha256=proof.snapshot_sha256,
    preparation_stop_sha256=sha(stop), campaign_sha256=sha(campaign), native_sha256=sha(source),
    operations=[dict(cdb=cdb.hex(), output_bytes=len(out), length=length) for cdb, out, length in native.OPERATIONS],
    ci_sha='08f43679255668a5bda9e99453c0313aabb2a541', execution_authorized_by_this_receipt=False))
base = dict(STAGE='Path(' + repr(str(stage)) + ')', RUN='Path(' + repr(str(run)) + ')',
    NATIVE_SHA=repr(sha(source)), READER_SHA=repr(sha(stage / 'tools/fm1_sdk_trace_read.py')),
    PROOF_SHA=repr(proof_pin), CAMPAIGN_SHA=repr(sha(campaign)), STOP_SHA=repr(sha(stop)))
def bind(template, destination, values):
    text = template.read_text()
    for name, value in values.items():
        token = name + ' = None'
        assert text.count(token) == 1
        text = text.replace(token, name + ' = ' + value)
    compile(text, str(destination), 'exec')
    with destination.open('x') as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
bind(stage / 'tools/fm1_prepare_stop_trace_capture_child.py', run / 'execute-child.py', base)
names = sorted(set(inventory) | {'run/' + x for x in ('campaign.json', 'preparation-stop.json', 'witness.json', 'preflight.json', 'execute-child.py')})
pins = {name: sha(stage / name) for name in names}
save(run / 'packet-pins.json', pins)
bind(stage / 'tools/fm1_prepare_stop_trace_capture.py', run / 'execute-once.py', dict(base,
    CHILD_SHA=repr(sha(run / 'execute-child.py')), PACKET_SHA=repr(sha(run / 'packet-pins.json')),
    PACKET_MEMBERS=str(len(pins))))
wrapper_spec = importlib.util.spec_from_file_location('_file_only_packet', run / 'execute-once.py')
wrapper = importlib.util.module_from_spec(wrapper_spec)
wrapper_spec.loader.exec_module(wrapper)
wrapper.require_frozen(); wrapper.packet_check(); prepared.check()
assert proof.snapshot == proof_module.validate_preparation_stop(lineage, chain).snapshot
print(json.dumps(dict(file_only=True, device_commands=0, packet_members=len(pins),
    wrapper_sha256=sha(run / 'execute-once.py'), preflight=json.loads((run / 'preflight.json').read_bytes())), sort_keys=True))
