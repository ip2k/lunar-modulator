#!/usr/bin/env python3
"""Bounded Hera launcher for fresh all-catalogue -Oz/-Os probes."""
import concurrent.futures
import json
import pathlib
import subprocess

ROOT = pathlib.Path('/home/claude/mvave-fm1/all13-fullsong-link-comparison-v1')
SRC = pathlib.Path('/home/claude/.local/share/codex-worktrees/lunar-fullsong-link-comparison')
IMAGE = 'sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'
PROFILE = '/home/claude/.local/share/codex-worktrees/lunar-demo-packed-validation/out/demo-packed-validation-v1/production-prepared-afterglow-relay'
TC = '/home/claude/mvave-fm1/sdk-v1213/toolchain/current'
CXX = '/home/claude/mvave-fm1/sdk-v1213/source-sdk/include_lib/c++/include'


def docker_run(name, mounts, args, cpus='1', memory='1536m'):
    cmd = ['docker', 'run', '--name', name, '--user', '1001:1001', '--network', 'none',
           '--cgroup-parent', 'docker-batch.slice', '--label', 'lan.project=lunar-modulator',
           '--cpus', cpus, '--memory', memory, '--memory-swap', memory]
    for host, guest, mode in mounts:
        cmd += ['-v', f'{host}:{guest}:{mode},z']
    cmd += ['-w', '/src', IMAGE, *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    state = json.loads(subprocess.check_output(
        ['docker', 'inspect', name, '--format', '{{json .State}}'], text=True))
    subprocess.run(['docker', 'rm', name], check=True, capture_output=True)
    return dict(exit=result.returncode, state_exit=state['ExitCode'], oom=state['OOMKilled'],
                output=result.stdout + result.stderr)


def build_catalogue(opt):
    out = ROOT / ('catalogue-' + opt)
    if out.exists() and (out / 'launcher-verification.json').is_file():
        results = json.loads((out / 'launcher-verification.json').read_text())
        if all(r['exit'] == 0 and r['state_exit'] == 0 and not r['oom'] for r in results):
            return
        raise SystemExit('existing catalogue verification contains failures')
    out.mkdir(parents=True, exist_ok=False)
    mounts = [(str(SRC), '/src', 'ro'), (str(out), '/out', 'rw'),
              (TC, '/opt/jieli', 'ro'), (CXX, '/cxx', 'ro')]

    def shard(i):
        name = f'lunar-fullsong-{opt}-{i:02d}'
        report = docker_run(name, mounts, [
            'python3', 'tools/native/compile_catalogue.py', '--toolchain', '/opt/jieli',
            '--cxx-headers', '/cxx', '--out', f'/out/shard-{i:02d}', '--shard', str(i),
            '--opt', opt, '--shared-resampler', '--indexed-tft', '--shapes-voices', '12', '--lto'])
        (out / f'shard-{i:02d}.log').write_text(report.pop('output'))
        return dict(shard=i, **report)

    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        results = list(pool.map(shard, range(16)))
    (out / 'launcher-verification.json').write_text(json.dumps(results, indent=2) + '\n')
    if not all(r['exit'] == 0 and r['state_exit'] == 0 and not r['oom'] for r in results):
        raise SystemExit('catalogue shard failure; inspect launcher-verification.json')


def build_probe(opt):
    out = ROOT / ('probe-' + opt)
    if out.exists() and (out / 'launcher-result.json').is_file():
        return json.loads((out / 'launcher-result.json').read_text())
    out.mkdir(parents=True, exist_ok=False)
    cat = ROOT / ('catalogue-' + opt)
    mounts = [(str(SRC), '/src', 'ro'), (str(cat), '/catalogue', 'ro'),
              (str(out), '/out', 'rw'), (TC, '/opt/jieli', 'ro'), (CXX, '/cxx', 'ro'),
              (PROFILE, '/prepared', 'ro'),
              (str(pathlib.Path(__file__).parent), '/evidence', 'ro')]
    name = 'lunar-fullsong-probe-' + opt
    result = docker_run(name, mounts, [
        'env', 'LUNAR_OPT=' + opt, 'python3', '/evidence/run_probe.py', '--toolchain', '/opt/jieli',
        '--catalogue', '/catalogue', '--build', '/out/build', '--runtime-mode', 'diagnostic',
        '--stack-watermark', '--flash-layout', 'expanded-d9000', '--prepared-profile', '/prepared',
        '--expected-profile-sha256', '173d4a377a36da99d53fe23b0ba7963c9c41355eea2ce8e9730a77410a4f4fb9',
        '--link-project-loader', '--startup-project-index', '0', '--indexed-tft',
        '--compressed-wavetables', '--flash-plaits-wavetables'])
    (out / 'launcher-result.json').write_text(json.dumps(result, indent=2) + '\n')
    if result['exit'] != 0 or result['state_exit'] != 0 or result['oom']:
        print(opt, 'probe exit', result['exit'], 'state', result['state_exit'],
              'oom', result['oom'], 'output', result['output'][-400:])
    return result


def collect():
    out = ROOT / 'receipts'
    out.mkdir(exist_ok=True)
    mounts = [(str(SRC), '/src', 'ro'), (str(ROOT), '/research', 'ro'),
              (str(out), '/out', 'rw'), (TC, '/opt/jieli', 'ro'),
              (PROFILE, '/prepared', 'ro'),
              (str(pathlib.Path(__file__).parent), '/evidence', 'ro')]
    result = docker_run('lunar-fullsong-receipt', mounts,
                        ['python3', '/evidence/collect_receipt.py'])
    if result['exit'] != 0 or result['state_exit'] != 0 or result['oom']:
        raise SystemExit('receipt collection failed: ' + result['output'])
    print(result['output'])


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    final = {}
    for variant in ('z', 's'):
        build_catalogue(variant)
        final[variant] = build_probe(variant)
    (ROOT / 'comparison-launch-verification.json').write_text(
        json.dumps({k: {a: v for a, v in r.items() if a != 'output'} for k, r in final.items()},
                   indent=2) + '\n')
    collect()
    if not all(r['state_exit'] == 0 and not r['oom'] for r in final.values()):
        raise SystemExit('one or more build containers failed; see per-variant receipts')
