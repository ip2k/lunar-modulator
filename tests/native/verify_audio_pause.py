#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run on Hera: exact-source target compile plus 30 ASan/UBSan test shards."""
import concurrent.futures
import hashlib
import json
import pathlib
import subprocess
import sys

src, out, toolchain = map(lambda s: pathlib.Path(s).resolve(), sys.argv[1:])
out.mkdir(exist_ok=False)
image = 'sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'
base = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '1',
        '--memory', '512m', '--cgroup-parent', 'docker-batch.slice',
        '--label', 'lan.project=lunar-modulator', '--user', '1001:1001',
        '-v', f'{src}:/src:ro,z', '-v', f'{out}:/out:rw,z']
commands = []
def run(name, argv):
    result = subprocess.run(argv, capture_output=True, text=True)
    (out / f'{name}.log').write_text(result.stdout + result.stderr)
    return {'name': name, 'exit': result.returncode, 'command': argv}

host = run('host-compile', base + [image, 'gcc', '-std=c11', '-O1', '-g',
    '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
    '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
    '-I/src/firmware/native', '/src/tests/native/audio_pause_test.c',
    '-o', '/out/audio-pause-test'])
commands.append(host)
target = run('target-compile', base + ['-v', f'{toolchain}:/opt/jieli:ro,z', image,
    '/opt/jieli/common/bin/clang', '-target', 'pi32v2', '-mcpu=r3', '-mfprev1',
    '-Oz', '-ffreestanding', '-fno-builtin', '-Wall', '-Wextra', '-Werror',
    '-Wno-unused-function', # Existing header-only IRQ startup, unused by harness.
    '-I/src/firmware/native', '-I/src/firmware/third_party/dinghy/hal',
    '-isystem', '/opt/jieli/pi32v2/include', '-c',
    '/src/tests/native/audio_pause_target.c', '-o', '/out/audio-pause-target.o'])
commands.append(target)
if not host['exit'] and not target['exit']:
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
        futures = [pool.submit(run, f'shard-{i:02}', base + [image,
            '/out/audio-pause-test', str(i)]) for i in range(30)]
        commands.extend(f.result() for f in futures)
files = ['firmware/native/audio_pause.h', 'firmware/native/audio_queue.h',
         'tests/native/audio_pause_test.c', 'tests/native/audio_pause_target.c',
         'tests/native/verify_audio_pause.py']
files += sorted(str(p.relative_to(src)) for p in
                (src / 'firmware/third_party/dinghy/hal').glob('*.h')
                if not p.name.startswith('.'))
receipt = {'schema': 'lunar-audio-pause-verification-v1', 'image': image,
    'hardware_tested': False, 'save_scheduler_integrated': False,
    'source_hashes': {p: hashlib.sha256((src / p).read_bytes()).hexdigest() for p in files},
    'runs': commands, 'success': len(commands) == 32 and all(not c['exit'] for c in commands)}
(out / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'success': receipt['success'], 'runs': len(commands)}))
sys.exit(0 if receipt['success'] else 1)
