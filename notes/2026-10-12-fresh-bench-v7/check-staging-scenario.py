"""One isolated Linux-container staging scenario; no firmware/tool execution."""
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

SOURCE = Path('/inputs')
ROOT = Path('/test')
SCENARIOS = ['success', 'main-archive-corrupt', 'recovery-archive-corrupt',
             'main-inventory-corrupt', 'recovery-inventory-corrupt', 'self-pin-wrong',
             'main-root-reused', 'recovery-root-reused', 'old-stage-corrupt',
             'main-tool-corrupt', 'provenance-missing', 'main-archive-symlink',
             'recovery-archive-symlink', 'main-inventory-symlink',
             'recovery-inventory-symlink', 'provenance-symlink']
sha = lambda raw: hashlib.sha256(raw).hexdigest()
encode = lambda obj: (json.dumps(obj, indent=2, sort_keys=True) + '\n').encode()

def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    for p in [path.parent, *path.parent.parents]:
        if p.is_relative_to(ROOT): p.chmod(0o700)
    path.chmod(0o600)

def payload(path):
    with tarfile.open(path) as archive:
        return {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}

def main():
    index = int(sys.argv[1]); scenario = SCENARIOS[index]
    assert sys.platform == 'linux' and os.geteuid() == 0
    os.umask(0o077); ROOT.mkdir(mode=0o700)
    main_inv = json.loads((SOURCE/'closed-entry-stage-inventory.json').read_bytes())
    rec_inv = json.loads((SOURCE/'closed-recovery-source-inventory.json').read_bytes())
    replacements = {main_inv['root']: str(ROOT/'entry'), main_inv['stage']: str(ROOT/'stage'),
                    main_inv['preserved_original_stage']: str(ROOT/'old'),
                    rec_inv['roots']['acquire']: str(ROOT/'acquire'), rec_inv['roots']['restore']: str(ROOT/'restore')}
    old = payload(SOURCE/'predecessor-v5.tar')
    for name, pin in main_inv['preserved_stage_required_files'].items():
        raw = old['stage/' + name]
        if name in ('build/sdk-trace-fresh-entry-bench-v1/next-campaign/owned-campaign-once-v2.py',
                    'build/sdk-trace-fresh-entry-bench-v1/next-campaign/owned-install-boot-once.py'):
            assert pin['sha256'] == '7d2cec8584bc274c534046d490f3c319bd7e0c13dec6d1f654323e9c9aa8dd8b'
            raw = (SOURCE/'historical-install-7d2.py').read_bytes()
        assert sha(raw) == pin['sha256']
        write(ROOT/'old'/name, raw)
    paths = {}
    for kind, inv, prefix in [('main', main_inv, 'entry-stage'), ('recovery', rec_inv, 'recovery-source')]:
        original_raw = (SOURCE/f'closed-{prefix}-inventory.json').read_bytes()
        raw = original_raw
        stager = (SOURCE/('stage-closed-files-proposal.py' if kind=='main' else 'stage-recovery-source-files-proposal.py')).read_bytes()
        for before, after in replacements.items():
            raw = raw.replace(before.encode(), after.encode())
            stager = stager.replace(before.encode(), after.encode())
        stager = stager.replace(sha(original_raw).encode(), sha(raw).encode())
        paths[kind] = (ROOT/(kind+'.py'), ROOT/(kind+'.json'), ROOT/(kind+'.tar'))
        for path, content in zip(paths[kind], [stager, raw, (SOURCE/f'closed-{prefix}-proposal.tar').read_bytes()]): write(path, content)
    def corrupt(path):
        raw = path.read_bytes(); path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    def symlink(path):
        target = path.with_name(path.name+'.real'); path.rename(target); path.symlink_to(target)
    main_fail = scenario in {'main-archive-corrupt','main-inventory-corrupt','self-pin-wrong','main-root-reused','old-stage-corrupt','main-archive-symlink','main-inventory-symlink'}
    if scenario.startswith('main-archive-'): (corrupt if scenario.endswith('corrupt') else symlink)(paths['main'][2])
    if scenario.startswith('main-inventory-'): (corrupt if scenario.endswith('corrupt') else symlink)(paths['main'][1])
    if scenario=='main-root-reused': (ROOT/'entry').mkdir(mode=0o700)
    if scenario=='old-stage-corrupt': corrupt(ROOT/'old'/next(iter(main_inv['preserved_stage_required_files'])))
    def run(kind, wrong=False):
        script, inventory, archive = paths[kind]
        proc = subprocess.run([sys.executable,'-B','-E','-s','-S',str(script),'--archive',str(archive),'--inventory',str(inventory),'--expected-self-sha256','0'*64 if wrong else sha(script.read_bytes())], capture_output=True, text=True)
        print(json.dumps(dict(kind=kind, exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)))
        return proc.returncode
    status = run('main', scenario=='self-pin-wrong')
    if main_fail:
        assert status != 0 and not (ROOT/'stage').exists() and not (ROOT/'acquire').exists()
    else:
        assert status == 0
        if scenario.startswith('recovery-archive-'): (corrupt if scenario.endswith('corrupt') else symlink)(paths['recovery'][2])
        if scenario.startswith('recovery-inventory-'): (corrupt if scenario.endswith('corrupt') else symlink)(paths['recovery'][1])
        if scenario=='recovery-root-reused': (ROOT/'acquire').mkdir(mode=0o700)
        if scenario=='main-tool-corrupt': corrupt(ROOT/'stage'/next(iter(rec_inv['source_pins'])))
        source = ROOT/'stage'/next(iter(rec_inv['firmware_source_pins']))
        if scenario=='provenance-missing': source.unlink()
        if scenario=='provenance-symlink': symlink(source)
        status = run('recovery')
        if scenario=='success':
            assert status == 0
            expected = set(rec_inv['source_pins']) | set(rec_inv['firmware_source_pins']) | {'prepare-file-only.py','source-inventory.json'}
            for side in ('acquire','restore'):
                assert all((ROOT/side/n).is_file() for n in expected)
                assert not any((ROOT/side/n).exists() for n in rec_inv['required_absent'])
            assert json.loads((ROOT/'acquire/source-stage-receipt.json').read_bytes())['hardware_opened'] is False
        else:
            assert status != 0 and not (ROOT/'restore').exists()
            if scenario!='recovery-root-reused': assert not (ROOT/'acquire').exists()
    print(json.dumps(dict(scenario=scenario, passed=True, hardware_opened=False, staged_source_executed=False)))

if __name__ == '__main__': main()
