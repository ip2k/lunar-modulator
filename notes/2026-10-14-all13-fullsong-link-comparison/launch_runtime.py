#!/usr/bin/env python3
"""Run supported -Oz runtime/watermark variants against the retained e435 catalogue."""
import json
import pathlib
import subprocess

ROOT = pathlib.Path('/home/claude/mvave-fm1/all13-fullsong-link-comparison-v1/runtime-followup-v2')
SRC = pathlib.Path('/home/claude/.local/share/codex-worktrees/lunar-fullsong-link-comparison')
IMAGE = 'lunar-recovery-pytest:20261011'
PROFILE = '/home/claude/.local/share/codex-worktrees/lunar-demo-packed-validation/out/demo-packed-validation-v1/production-prepared-afterglow-relay'
TC = '/home/claude/mvave-fm1/sdk-v1213/toolchain/current'
CXX = '/home/claude/mvave-fm1/sdk-v1213/source-sdk/include_lib/c++/include'
EVIDENCE = '/home/claude/.local/share/codex-worktrees/lunar-fullsong-link-comparison/notes/2026-10-14-all13-fullsong-link-comparison'
CATALOGUE = '/home/claude/mvave-fm1/all13-fullsong-link-comparison-v1/catalogue-z'
VARIANTS = (('diagnostic-no-watermark', 'diagnostic', '0'),
            ('continuous-watermark', 'continuous', '1'),
            ('continuous-no-watermark', 'continuous', '0'))


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, runtime, watermark in VARIANTS:
        out = ROOT / label
        out.mkdir(parents=True, exist_ok=False)
        cmd = ['docker', 'run', '--name', 'lunar-runtime-' + label, '--user', '1001:1001',
               '--network', 'none', '--cgroup-parent', 'docker-batch.slice',
               '--label', 'lan.project=lunar-modulator', '--cpus', '1', '--memory', '1536m',
               '--memory-swap', '1536m', '-v', f'{SRC}:/src:ro,z',
               '-v', f'{CATALOGUE}:/catalogue:ro,z', '-v', f'{out}:/out:rw,z',
               '-v', f'{TC}:/opt/jieli:ro,z', '-v', f'{CXX}:/cxx:ro,z',
               '-v', f'{PROFILE}:/prepared:ro,z', '-v', f'{EVIDENCE}:/evidence:ro,z',
               '-w', '/src', IMAGE, 'env', 'LUNAR_OPT=z', 'LUNAR_RUNTIME=' + runtime,
               'LUNAR_WATERMARK=' + watermark, 'python3', '/evidence/run_probe.py',
               '--toolchain', '/opt/jieli', '--catalogue', '/catalogue', '--build', '/out/build',
               '--flash-layout', 'expanded-d9000', '--prepared-profile', '/prepared',
               '--expected-profile-sha256', '173d4a377a36da99d53fe23b0ba7963c9c41355eea2ce8e9730a77410a4f4fb9',
               '--link-project-loader', '--startup-project-index', '0', '--indexed-tft',
               '--compressed-wavetables', '--flash-plaits-wavetables']
        process = subprocess.run(cmd, capture_output=True, text=True)
        state = json.loads(subprocess.check_output(
            ['docker', 'inspect', 'lunar-runtime-' + label, '--format', '{{json .State}}'], text=True))
        subprocess.run(['docker', 'rm', 'lunar-runtime-' + label], check=True,
                       capture_output=True)
        result = dict(label=label, runtime=runtime, stack_watermark=bool(int(watermark)),
                      exit=process.returncode, state_exit=state['ExitCode'], oom=state['OOMKilled'],
                      output=process.stdout + process.stderr)
        (out / 'container-result.json').write_text(json.dumps(result, indent=2) + '\n')
        results[label] = result
        print(label, 'exit', result['exit'], 'state', result['state_exit'],
              'oom', result['oom'], result['output'][-500:])
    (ROOT / 'runtime-launch-receipt.json').write_text(json.dumps(results, indent=2) + '\n')
    if any(v['state_exit'] != 0 or v['oom'] for v in results.values()):
        raise SystemExit('one or more runtime variants did not complete; inspect per-variant output')


if __name__ == '__main__':
    main()
