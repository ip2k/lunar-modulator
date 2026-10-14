"""Run thirty independent catalogue/profile requests in bounded Hera containers."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012')
SOURCE = ROOT / 'image-catalogue-source-v1'
OUT = ROOT / 'out/image-catalogue-v1'
IMAGE = 'sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'


def run(case):
    name = f'lunar-image-catalogue-v1-{case:02d}'
    cmd = ['docker', 'run', '--name', name, '--user', '1001:1001',
           '--network', 'none', '--cgroup-parent', 'docker-batch.slice',
           '--label', 'lan.project=lunar-modulator', '--cpus', '1',
           '--memory', '256m', '--memory-swap', '256m',
           '-v', str(SOURCE) + ':/src:ro,z',
           '-v', str(ROOT / 'out') + ':/out:ro,z',
           '-e', 'PYTHONDONTWRITEBYTECODE=1', '-w', '/src', IMAGE,
           '/out/pytest-venv/bin/python', '-m', 'pytest', '-q',
           '-p', 'no:cacheprovider',
           f'tests/test_native_image_catalogue.py::test_exported_builder_requests[{case}]']
    result = subprocess.run(cmd, capture_output=True, text=True)
    log = result.stdout + result.stderr
    (OUT / f'{case:02d}.log').write_text(log)
    state = json.loads(subprocess.check_output(
        ['docker', 'inspect', name, '--format', '{{json .State}}'], text=True))
    receipt = dict(case=case, command=cmd, exit=result.returncode,
                   state_exit=state['ExitCode'], oom=state['OOMKilled'],
                   log_sha256=hashlib.sha256(log.encode()).hexdigest())
    (OUT / f'{case:02d}.json').write_text(json.dumps(receipt, indent=2) + '\n')
    subprocess.run(['docker', 'rm', name], check=True, capture_output=True)
    return receipt


if __name__ == '__main__':
    OUT.mkdir(exist_ok=False)
    paths = ['tools/native/export_image_catalogue.py', 'tools/native/module_selection.py',
             'tools/native/prepare_image_profile.py', 'tests/test_native_image_catalogue.py',
             'engines/Makefile', 'engines/modules/catalogue.mk']
    hashes = {p: hashlib.sha256((SOURCE / p).read_bytes()).hexdigest() for p in paths}
    (OUT / 'source-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
        receipts = list(pool.map(run, range(30)))
    (OUT / 'campaign.json').write_text(json.dumps(receipts, indent=2) + '\n')
    assert all(r['exit'] == r['state_exit'] == 0 and not r['oom'] for r in receipts)
    print('PASS: 30 production catalogue/request checks')
