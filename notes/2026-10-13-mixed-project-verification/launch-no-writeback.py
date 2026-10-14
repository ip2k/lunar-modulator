"""Hera-only formatter campaign and full native relink; retain every terminal state."""
import concurrent.futures
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012')
SOURCE = ROOT / 'mixed-project-no-writeback-source-v4'
OUT = ROOT / 'out/formatter-no-writeback-v2'
IMAGE = 'sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'


def run(name, command, target=False):
    args = ['docker', 'run', '--name', name, '--user', '1001:1001',
            '--network', 'none', '--cgroup-parent', 'docker-batch.slice',
            '--label', 'lan.project=lunar-modulator', '--cpus', '2',
            '--memory', '4096m' if target else '256m',
            '--memory-swap', '4096m' if target else '256m',
            '-v', str(SOURCE) + ':/src:ro,z',
            '-v', str(ROOT / 'out') + ':/out:rw,z', '-w', '/src']
    if target:
        args += ['-v', '/home/claude/mvave-fm1/native-catalogue-16-20261012/out-mod-cold-v1:/catalogue:ro,z',
                 '-v', '/home/claude/mvave-fm1/sdk-v1213/toolchain/current:/opt/jieli:ro,z']
    result = subprocess.run(args + [IMAGE] + command, capture_output=True, text=True)
    log = result.stdout + result.stderr
    (OUT / (name + '.log')).write_text(log)
    state = json.loads(subprocess.check_output(['docker', 'inspect', name, '--format', '{{json .State}}'], text=True))
    receipt = dict(name=name, command=args + [IMAGE] + command,
                   exit=result.returncode, state_exit=state['ExitCode'],
                   oom=state['OOMKilled'], log_sha256=hashlib.sha256(log.encode()).hexdigest())
    (OUT / (name + '.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    subprocess.run(['docker', 'rm', name], check=True, capture_output=True)
    return receipt


def host(shard):
    code = '''import subprocess
subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DPRINTF_SUPPORT_WRITEBACK_SPECIFIER=0','-I/src/firmware/third_party/printf','/src/tests/native_printf_check.c','/src/firmware/third_party/printf/printf/printf.c','-o','/tmp/check'],check=True)
subprocess.run(['/tmp/check',SHARD],check=True)
print('PASS', SHARD)
'''.replace('SHARD', repr(str(shard)))
    return run('lunar-formatter-no-writeback-v2-%02d' % shard, ['python3', '-c', code])


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
        receipts = list(pool.map(host, range(30)))
    (OUT / 'host-campaign.json').write_text(json.dumps(receipts, indent=2) + '\n')
    assert all(r['exit'] == r['state_exit'] == 0 and not r['oom'] for r in receipts)
    target = run('lunar-all13-no-writeback-v4', ['python3', '/src/notes/2026-10-13-mixed-project-verification/all13-no-writeback-driver.py'], True)
    assert target['exit'] == target['state_exit'] == 0 and not target['oom']
    print('PASS 30 sanitizer chunks and all13 native relink')
