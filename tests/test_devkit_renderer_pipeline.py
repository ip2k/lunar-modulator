"""Native-derived protocol ownership/refusal proof; no target timing claim."""
# Keep the ASan leak-detection default: enabled on Linux, unsupported on macOS.
from pathlib import Path
import os
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
MODES = ('stream', 'output_full', 'output_full_descheduled', 'reserve_twice', 'publish_wrong', 'acquire_twice',
         'retire_wrong', 'callback_failure', 'retire_failure', 'timeout_late',
         'guard_park', 'finish_pending')

@pytest.mark.parametrize('sanitize', [False, True])
def test_native_pipeline_protocol(tmp_path, sanitize):
    cc = os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
    if not cc:
        pytest.skip('C compiler unavailable')
    text = (ROOT / 'firmware/devkit/renderer_pipeline_sdk.c').read_text()
    for name in ('app_config.h', 'system/includes.h', 'os/os_api.h', 'asm/includes.h'):
        anchor = f'#include "{name}"'
        assert text.count(anchor) == 1
        text = text.replace(anchor, '/* SDK provided by host shim. */')
    assert text.count('volatile uint32_t') == 9
    text = text.replace('volatile uint32_t', '_Atomic uint32_t')
    text = text.replace('volatile int', '_Atomic int')
    fence = '__asm__ volatile("csync;" ::: "memory");'
    assert text.count(fence) == 2
    text = text.replace(fence, 'atomic_thread_fence(memory_order_seq_cst);')
    text = '\n'.join(x for x in text.splitlines() if not x.startswith('#pragma code_seg'))
    (tmp_path / 'backend.c').write_text(text)
    for name in ('protocol.c', 'sdk_shim.h'):
        shutil.copyfile(ROOT / 'tests/fixtures/renderer_pipeline' / name, tmp_path / name)
    shutil.copyfile(ROOT / 'firmware/devkit/renderer_pipeline_sdk.h', tmp_path / 'renderer_pipeline_sdk.h')
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else []
    exe = tmp_path / 'protocol'
    subprocess.run([cc, '-std=c11', '-O1', '-g', '-pthread', '-Wall', '-Wextra', '-Werror',
                    *flags, str(tmp_path / 'protocol.c'), '-o', str(exe)], check=True)
    env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    for mode in MODES:
        subprocess.run([str(exe), mode], check=True, env=env, timeout=15)

@pytest.mark.parametrize('worker', ['', 'LUNAR_DEVKIT_FM6_PAIR', 'LUNAR_DEVKIT_FM6_SDK', 'LUNAR_DEVKIT_QUEUE_SDK', 'LUNAR_DEVKIT_ENGINE_QUEUE'])
def test_pipeline_build_owns_one_worker(worker):
    make = shutil.which('make')
    if not make:
        pytest.skip('make unavailable')
    flags = '-DLUNAR_DEVKIT_RENDERER_PIPELINE=1'
    if worker:
        flags += f' -D{worker}=1'
    result = subprocess.run([make, '--no-print-directory', '-f', str(ROOT / 'tools/jieli/renderer.mk'),
                             'print-devkit-renderer-objs', 'BUILD=/lane/build', 'SIM=/lane/sim',
                             f'EXTRA={flags}'], capture_output=True, text=True)
    if worker:
        assert result.returncode != 0 and 'must not nest another SDK worker' in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert '/lane/build/devkit/renderer_pipeline_sdk.o' in result.stdout
        assert '/lane/build/devkit/renderer_queue_sdk.o' not in result.stdout


@pytest.mark.parametrize('language', ['c', 'c++'])
def test_pipeline_public_header(tmp_path, language):
    compiler = shutil.which('clang++' if language == 'c++' else 'clang')
    if not compiler:
        pytest.skip('C/C++ compiler unavailable')
    client = tmp_path / ('client.cc' if language == 'c++' else 'client.c')
    client.write_text('#include "renderer_pipeline_sdk.h"\nint client(unsigned cpu) {\n    int (*drain)(unsigned) = lunar_pipeline_wake_drain;\n    int (*wait)(unsigned) = lunar_pipeline_wake_wait;\n    void (*done)(void) = lunar_pipeline_wake_drain_done;\n    unsigned (*ready)(void) = lunar_pipeline_ready_outputs;\n    done();\n    return drain(cpu) + wait(cpu) + (int)ready();\n}\n')
    subprocess.run([compiler, '-std=c++11' if language == 'c++' else '-std=c11',
                    '-Wall', '-Wextra', '-Werror', '-fsyntax-only',
                    '-I' + str(ROOT / 'firmware/devkit'), str(client)], check=True)
