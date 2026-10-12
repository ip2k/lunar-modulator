"""Assemble closed private bench inputs; never execute staged sources or hardware."""
import ast
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

BASE = Path.cwd()
OLD = BASE / 'build/sdk-trace-fresh-entry-bench-v1/next-campaign/automatic-trace-chain-v5'
OUT = OLD.with_name('automatic-trace-chain-v7')
MODEL = BASE / 'build/partial-stock-recovery-production/next-campaign-readiness-v1/hera-owned-restore-v1/hera-owned-restore-v6/heavy-model-proposal-v6r-proposal'
HISTORICAL = '7d2cec8584bc274c534046d490f3c319bd7e0c13dec6d1f654323e9c9aa8dd8b'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
encode = lambda obj: (json.dumps(obj, indent=2, sort_keys=True) + '\n').encode()

def load_archive(path, expected):
    raw = path.read_bytes()
    assert sha(raw) == expected
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        members = archive.getmembers()
        assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
        result = {m.name: archive.extractfile(m).read() for m in members}
        assert len(result) == len(members)
        return result

def archive(path, payload):
    with tarfile.open(path, 'x', format=tarfile.USTAR_FORMAT) as out:
        for name, raw in sorted(payload.items()):
            member = tarfile.TarInfo(name)
            member.size = len(raw); member.mode = 0o600
            out.addfile(member, io.BytesIO(raw))

def metadata(payload):
    return {n: dict(sha256=sha(b), size=len(b), mode='0600') for n, b in sorted(payload.items())}

def save(name, raw):
    with (OUT / name).open('xb') as stream:
        stream.write(raw)

def main():
    old = load_archive(OLD / 'closed-entry-stage-proposal.tar', '5a176f20bf7a765ce317e078a81ab60830523a2b39c1b8e5967ec5a5738e606b')
    model = load_archive(MODEL / 'source-full-tree-v6.tar', 'c5ba02fd379516f4bc63614fd93adccc870aa617fabe5c2fa16d3a737d321fef')
    snapshot = json.loads((MODEL / 'snapshot-owned-restore-model-v6r-heavy.json').read_bytes())
    assert {n: sha(b) for n, b in model.items()} == snapshot['source_sha256']
    pins = json.loads(model['source-inventory.json'])['source_pins']
    assert len(pins) == 38 and all(sha(model[n]) == pin for n, pin in pins.items())
    assert sha(model['tools/bench_capture/lifecycle-v1/historical-install-7d2.py']) == HISTORICAL
    payload = dict(old)
    for name in pins:
        payload['stage/' + name] = model[name]
    restore_capture = 'stage/build/sdk-trace-fresh-entry-bench-v1/next-campaign/owned-admitted-backup-restore-once-v1.py'
    payload[restore_capture] = model['capture-pins/owned-admitted-backup-restore-once-v1.py']
    support = 'stage/build/sdk-trace-fresh-entry-bench-v1/next-campaign/partial-recovery-v5/'
    assets = {'prepare-file-only.py': model['prepare-file-only.py'],
              'source-inventory.json': model['source-inventory.json'],
              'owned-acquire-once-v1.py': model['capture-pins/owned-acquire-once-v1.py'],
              'owned-partial-stock-restore-once.py': model['tests/owned-partial-stock-restore-once-v3.py']}
    for name, raw in assets.items():
        payload[support + name] = raw
    seed = dict(payload)
    for name, raw in seed.items():
        if name.endswith(('.py', '.json')) and not name.startswith('entry/identity-once/'):
            raw = raw.replace(b'-v5', b'-v7')
            seed[name] = raw
    current = dict(seed)
    for iteration in range(40):
        mapping = {sha(old[n]).encode(): sha(current[n]).encode() for n in old if current[n] != old[n] and sha(old[n]) != HISTORICAL}
        assert HISTORICAL.encode() not in mapping
        revised = {n: re.sub(rb'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])', lambda m: mapping.get(m[0], m[0]), raw)
                   if n.endswith(('.py', '.json')) and not n.startswith('entry/identity-once/') else raw for n, raw in seed.items()}
        if revised == current: break
        current = revised
    else: raise ValueError('source closure did not converge')
    assert all(current['stage/' + name] == model[name] for name in pins)
    assert all(current[support + name] == raw for name, raw in assets.items())
    assert current[restore_capture] == model['capture-pins/owned-admitted-backup-restore-once-v1.py']
    payload = {n.replace('partial-recovery-v5/', 'partial-recovery-v7/'): raw for n, raw in current.items()}
    manifest_raw = payload['stage/assets/native/build-manifest.json']
    assert sha(manifest_raw) == 'b58c49fed04efb4fc29eaf2602605a8e4ec197048bcd418c86a53276198cf86e'
    firmware = {n.removeprefix('/source/'): pin for n, pin in json.loads(manifest_raw)['source_sha256'].items() if n.startswith('/source/')}
    assert len(firmware) == 11 and all(n.startswith('firmware/') and sha(payload['stage/' + n]) == pin for n, pin in firmware.items())
    closure = json.loads(payload['entry/source-closure.json'])
    closure['stage_files'] = {n[6:]: sha(raw) for n, raw in payload.items() if n.startswith('stage/')}
    closure['entry_derivatives'] = {n: sha(payload['entry/' + n]) for n in closure['entry_derivatives']}
    closure['inputs'] = {n[13:]: sha(raw) for n, raw in payload.items() if n.startswith('entry/inputs/')}
    closure['entry_files'] = {n[6:]: sha(raw) for n, raw in payload.items() if n.startswith('entry/') and n[6:] not in closure['entry_derivatives'] and n not in ('entry/sequence-once.py', 'entry/source-closure.json') and not n.startswith('entry/inputs/')}
    dep = closure['partial_recovery_dependency']
    dep.update(adapter_source_sha256=pins['tools/fm1_retained_partial_recovery.py'], source_inventory_sha256=sha(assets['source-inventory.json']), prepare_helper_sha256=sha(assets['prepare-file-only.py']), owned_acquire_wrapper_sha256=sha(assets['owned-acquire-once-v1.py']), owned_restore_wrapper_sha256=sha(assets['owned-partial-stock-restore-once.py']))
    spec_raw = (OLD / 'prospective-path-spec.json').read_bytes()
    assert sha(spec_raw) == 'f33e1a45314615608c0a52c80a0c06f4061e7bc7fa1a597c679a7852053218b8'
    spec = json.loads(spec_raw.replace(b'-v5', b'-v7'))
    spec_raw = encode(spec)
    dep['prospective_path_spec_sha256'] = sha(spec_raw)
    assert [spec['partial_acquire_stage'], spec['partial_restore_stage']] == dep['independent_recovery_roots']
    assert spec['entry_root'] == closure['entry_root'] and spec['stage_root'] == closure['unchanged_stage']
    closure.update(execution_authorized=False, proposal_only=True, root_launch_acceptance_sha256=None)
    assert dep['reviewed_recovery_plan_sha256'] is None
    payload['entry/source-closure.json'] = encode(closure)
    for name, raw in payload.items():
        if name.endswith('.py'): ast.parse(raw)
    gates = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(payload['entry/sequence-once.py']).body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('WIRE_SHA', 'CLOSURE_SHA', 'ROOT_ACCEPTANCE_SHA', 'RECOVERY_PLAN_SHA')}
    assert len(gates) == 4 and all(pin is None for pin in gates.values())
    recovery_sources = {n: model[n] for n in pins}
    recovery_sources.update({n: assets[n] for n in ('prepare-file-only.py', 'source-inventory.json')})
    recovery_sources.update({n: payload['stage/' + n] for n in firmware})
    assert len(recovery_sources) == 51
    recovery = {side + '/' + n: raw for side in ('acquire', 'restore') for n, raw in recovery_sources.items()}
    OUT.mkdir(mode=0o700)
    archive(OUT / 'closed-entry-stage-proposal.tar', payload)
    archive(OUT / 'closed-recovery-source-proposal.tar', recovery)
    save('source-closure.json', encode(closure))
    save('prospective-path-spec.json', spec_raw)
    inv = json.loads((OLD / 'closed-entry-stage-inventory.json').read_bytes())
    inv.update(kind='fm1-closed-new-entry-and-trace-stage-v7', root=closure['entry_root'], stage=closure['unchanged_stage'], files=metadata(payload), archive_sha256=sha((OUT/'closed-entry-stage-proposal.tar').read_bytes()), archive_size=(OUT/'closed-entry-stage-proposal.tar').stat().st_size, partial_recovery_dependency=dep)
    for field in ('empty_directories', 'required_absent'):
        inv[field] = json.loads(encode(inv[field]).replace(b'-v5', b'-v7'))
    inv['changes'] = {n: dict(before=sha(old[n]) if n in old else None, after=sha(raw)) for n, raw in payload.items() if old.get(n) != raw}
    main_inventory = encode(inv)
    save('closed-entry-stage-inventory.json', main_inventory)
    recovery_inv = json.loads((OLD/'closed-recovery-source-inventory.json').read_bytes())
    recovery_inv.update(kind='fm1-v7-two-exclusive-recovery-source-roots', roots=dict(acquire=spec['partial_acquire_stage'], restore=spec['partial_restore_stage']), files=metadata(recovery), file_count=102, files_per_root=51, source_pins=pins, firmware_source_pins=firmware, manifest_sha256=sha(manifest_raw), helper_sha256=sha(assets['prepare-file-only.py']), source_inventory_sha256=sha(assets['source-inventory.json']), archive_sha256=sha((OUT/'closed-recovery-source-proposal.tar').read_bytes()), archive_size=(OUT/'closed-recovery-source-proposal.tar').stat().st_size)
    recovery_inventory = encode(recovery_inv)
    save('closed-recovery-source-inventory.json', recovery_inventory)
    main_stager = (OLD/'stage-closed-files-proposal.py').read_bytes()
    assert sha(main_stager) == '88db668ec6bad704ba02c66411ff9e366a129dcb85a8770902f06891e651587e'
    main_stager = main_stager.replace(b'-v5', b'-v7').replace(b'4b870848dbd1f7389f5897f06fa6509377bfd368e14afea1927802ab17471126', sha(main_inventory).encode()).replace(b'5a176f20bf7a765ce317e078a81ab60830523a2b39c1b8e5967ec5a5738e606b', inv['archive_sha256'].encode())
    ast.parse(main_stager)
    save('stage-closed-files-proposal.py', main_stager)
    recovery_stager = (OLD/'stage-recovery-source-files-proposal.py').read_bytes()
    assert sha(recovery_stager) == '57a7d0f162a4347f48154b4aff2c92f62181459a6c5efdfc88035c3089049e16'
    recovery_stager = recovery_stager.decode().replace('-v5', '-v7').replace('58c72b7f5823d00ec663390320bf17a960d22b5af05f41807ca966c165423bfc', sha(recovery_inventory)).replace('fa76d3d230af9be4a08bf87f6c5b471b6e201a9a79127238592d034b894ba542', recovery_inv['archive_sha256'])
    recovery_stager = recovery_stager.replace("inv['file_count'] != 80 or len(inv['files']) != 80", "inv['file_count'] != 102 or len(inv['files']) != 102").replace("inv['files_per_root'] != 40", "inv['files_per_root'] != 51").replace('file_count=80, source_tools_per_root=38', 'file_count=102, source_tools_per_root=38')
    recovery_stager = recovery_stager.replace("for name, pin in inv['source_pins'].items():", "for name, pin in {**inv['source_pins'], **inv['firmware_source_pins']}.items():")
    recovery_stager = recovery_stager.replace("expected = {k + '/' + n for k in ROOTS for n in inv['source_pins']}", "expected = {k + '/' + n for k in ROOTS for n in {**inv['source_pins'], **inv['firmware_source_pins']}}")
    recovery_stager = recovery_stager.replace("for n in inv['source_pins']:", "for n in {**inv['source_pins'], **inv['firmware_source_pins']}:")
    recovery_stager = recovery_stager.replace("!= inv['source_pins'][n]", "!= {**inv['source_pins'], **inv['firmware_source_pins']}[n]")
    recovery_stager = recovery_stager.replace("[*inv['source_pins'], 'prepare-file-only.py', 'source-inventory.json']", "[*inv['source_pins'], *inv['firmware_source_pins'], 'prepare-file-only.py', 'source-inventory.json']")
    recovery_stager = recovery_stager.replace("{*inv['source_pins'], 'prepare-file-only.py', 'source-inventory.json'}", "{*inv['source_pins'], *inv['firmware_source_pins'], 'prepare-file-only.py', 'source-inventory.json'}")
    needle = '    check_main_stage(inv)  # Read-only; never mutate already staged main assets.'
    assert recovery_stager.count(needle) == 1
    provenance_check = '''    manifest_raw = read(MAIN_STAGE / 'assets/native/build-manifest.json', private=True)
    manifest_sources = {n.removeprefix('/source/'): pin for n, pin in json.loads(manifest_raw)['source_sha256'].items() if n.startswith('/source/')}
    if (digest(manifest_raw) != inv['manifest_sha256'] or len(manifest_sources) != 11
            or any(not n.startswith('firmware/') for n in manifest_sources)
            or manifest_sources != inv['firmware_source_pins']):
        raise ValueError('exact native manifest provenance differs')
'''
    recovery_stager = recovery_stager.replace(needle, provenance_check + needle)
    ast.parse(recovery_stager)
    save('stage-recovery-source-files-proposal.py', recovery_stager.encode())
    result = dict(schema=1, files=len(payload), recovery_files=len(recovery), model_archive_sha256=snapshot['archive_sha256'], main_archive_sha256=inv['archive_sha256'], recovery_archive_sha256=recovery_inv['archive_sha256'], main_stager_sha256=sha(main_stager), recovery_stager_sha256=sha(recovery_stager.encode()), four_gates=gates, source_execution=False, hardware_opened=False, terminal_model_acceptance_pending=True, staging_helper_review_pending=True)
    save('assembly-review.json', encode(result))
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
