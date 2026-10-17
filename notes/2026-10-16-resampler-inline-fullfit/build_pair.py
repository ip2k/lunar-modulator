#!/usr/bin/env python3
"""Run matched offline thirteen-engine baseline/candidate builds on Aeon.

Execute only after the named coordination claim has been acquired. Uses the
reviewed stage-7 runner, identical frozen toolchain/profile and exact source
commits; no package construction or device access. Each build uses 16 bounded
catalogue shards and then one bounded link. Builds are sequential.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

BASE = '86154bc7843d7b1965d346af78620917fd2836f1'
CANDIDATE = 'e75335164423dead395213373bcf221a4d962ea3'
ORIGINAL_CANDIDATE = 'fd853c5c05b61818281daa1427c73355dbf1da00'
RUNNER_SHA = '60448560af6f6bbe479a1510b1af4e4cd84e6186f3d01fdd0e0f61425915f446'
RECEIPT_SHA = '6db18a773eeb48cd18b64d1d01ad184b6a691182f5800bf9e727f2cafcc0fd56'
STAGE7 = Path('/home/claude/mvave-fm1/resampler-fullfit-frozen-20261016')
EXCHANGE = Path('/home/claude/.local/share/codex-repos/lunar.git')
CLAIM = Path('/home/claude/.local/share/codex-coordination/claims/lunar--resampler-inline-fullfit-aeon-20261016')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or not (CLAIM / 'owner').is_file():
        raise RuntimeError('Aeon Linux and an acquired named coordination claim are required')
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    original_runner = STAGE7 / 'run-build.py'
    runner = Path(__file__).with_name('run_aeon.py')
    receipt_path = STAGE7 / 'output/frozen-build-input-receipt.json'
    if sha(original_runner) != RUNNER_SHA or sha(runner) != '41d1b44b5f7dd303f5d44b4c19fa693b076d26d88abd5d93eaa4d778e661c808' or sha(receipt_path) != RECEIPT_SHA:
        raise RuntimeError('stage-7 runner or receipt differs from reviewed external pin')
    original = json.loads(receipt_path.read_text())
    frozen = Path('/home/claude/mvave-fm1/resampler-fullfit-exact-snapshots-20261016')
    for name, digest in original['outputs'].items():
        if sha(STAGE7 / 'output' / name) != digest:
            raise RuntimeError('stage-7 retained output hash mismatch: ' + name)
    profile_sha = original['prepared_profile_sha256']
    selection_sha = original['selection_sha256']
    if sha(frozen / 'prepared/profile.json') != profile_sha or sha(frozen / 'selection.json') != selection_sha:
        raise RuntimeError('stage-7 prepared content changed')
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('matched_stage7_runner', runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.sha_bytes(module.tree_manifest(frozen / 'toolchain')) != original['toolchain_snapshot_tree_manifest_sha256']:
        raise RuntimeError('toolchain snapshot differs from original target compiler')
    if module.link_args(profile_sha) != original['link_command']:
        raise RuntimeError('runner no longer matches retained current-profile link command')
    expected_compile = ['python3', 'tools/native/compile_catalogue.py', '--toolchain', '/toolchain',
        '--cxx-headers', '/headers', '--out', '/out/shard-00', '--shard', '0', '--opt', 'z',
        '--lto', '--shared-resampler', '--shapes-voices', '8', '--indexed-tft', '--hot-dsp-os',
        '--hot-dsp-ram', '--engine-render-profile', '--hall-o2']
    if module.catalogue_args(0) != expected_compile:
        raise RuntimeError('catalogue command differs from explicit current-profile contract')
    git = ['git', '--git-dir=' + str(EXCHANGE)]
    candidate_header = subprocess.check_output(git + ['show', CANDIDATE + ':engines/include/fm1_resampler.h'])
    original_candidate_header = subprocess.check_output(git + ['show', ORIGINAL_CANDIDATE + ':engines/include/fm1_resampler.h'])
    if candidate_header != original_candidate_header:
        raise RuntimeError('candidate resampler differs from previously verified experiment')
    source_delta = subprocess.check_output(git + ['diff', '--name-only', BASE, CANDIDATE], text=True).splitlines()
    expected_delta = ['engines/include/fm1_resampler.h', 'notes/2026-10-16-resampler-inline-experiment.md',
        'notes/2026-10-16-resampler-inline/codegen.py', 'tests/test_resampler_stage1_placement.py',
        'tools/native/compare_resampler_inline.py']
    if source_delta != expected_delta:
        raise RuntimeError('source delta differs from reviewed experiment paths')
    pair = {'baseline_commit': BASE, 'candidate_commit': CANDIDATE,
        'original_experiment_commit': ORIGINAL_CANDIDATE, 'source_delta': source_delta,
        'host': 'aeon', 'stage7_runner_sha256': sha(original_runner), 'aeon_runner_sha256': sha(runner), 'stage7_receipt_sha256': sha(receipt_path),
        'profile_sha256': profile_sha, 'selection_sha256': selection_sha,
        'hardware_tested': False, 'runtime_performance_proven': False, 'results': {}}
    (output / 'pair-input.json').write_text(json.dumps(pair, indent=2) + '\n')
    for label, commit in [('baseline', BASE), ('candidate', CANDIDATE)]:
        checkout = output / (label + '-checkout')
        subprocess.run(git + ['worktree', 'add', '--detach', str(checkout), commit], check=True)
        command = [sys.executable, str(runner), '--checkout', str(checkout), '--commit', commit,
            '--toolchain', str(frozen / 'toolchain'), '--headers', str(frozen / 'headers'),
            '--prepared-profile', str(frozen / 'prepared'), '--selection', str(frozen / 'selection.json'),
            '--expected-profile-sha256', profile_sha, '--expected-selection-sha256', selection_sha,
            '--output', str(output / label)]
        (output / (label + '-command.json')).write_text(json.dumps(command, indent=2) + '\n')
        with (output / (label + '-runner.log')).open('wb') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=5400)
        receipt = output / label / 'frozen-build-input-receipt.json'
        data = json.loads(receipt.read_text())
        if data['source_commit'] != commit or data['link_command'] != original['link_command']:
            raise RuntimeError('result source or link command mismatch')
        pair['results'][label] = {'receipt_sha256': sha(receipt), 'outputs': data['outputs']}
        (output / 'pair-result.json').write_text(json.dumps(pair, indent=2) + '\n')


if __name__ == '__main__':
    main()
