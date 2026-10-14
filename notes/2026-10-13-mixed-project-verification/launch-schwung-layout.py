"""Run the single, nonparallel ABI measurement on Hera and retain its exit."""
import json
import pathlib
import subprocess

root = pathlib.Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012')
name = 'lunar-schwung-layout-v2'
command = ['docker', 'run', '--name', name, '--user', '1001:1001',
    '--network', 'none', '--cgroup-parent', 'docker-batch.slice',
    '--label', 'lan.project=lunar-modulator', '--cpus', '1', '--memory', '512m',
    '--memory-swap', '512m',
    '-v', str(root / 'mixed-project-production-source-v3') + ':/src:ro,z',
    '-v', str(root) + ':/work:rw,z',
    '-v', '/home/claude/mvave-fm1/sdk-v1213/toolchain/current:/opt/jieli:ro,z',
    'sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d',
    'python3', '/work/measure-schwung-layout.py', '/src', '/opt/jieli',
    '/work/out/schwung-layout-v2']
result = subprocess.run(command, capture_output=True, text=True)
(root / 'out/schwung-layout-v2.log').write_text(result.stdout + result.stderr)
state = json.loads(subprocess.check_output(
    ['docker', 'inspect', name, '--format', '{{json .State}}'], text=True))
receipt = dict(command=command, exit=result.returncode,
    state_exit=state['ExitCode'], oom=state['OOMKilled'])
(root / 'out/schwung-layout-v2-container.json').write_text(json.dumps(receipt, indent=2) + '\n')
assert not state['Running'], 'owned container is still running'
subprocess.run(['docker', 'rm', name], check=True, capture_output=True)
print(json.dumps(receipt))
print(result.stdout)
print(result.stderr)
assert result.returncode == 0 and state['ExitCode'] == 0 and not state['OOMKilled']
