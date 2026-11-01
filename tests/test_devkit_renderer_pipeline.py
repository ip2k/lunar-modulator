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
         'guard_park', 'finish_pending', 'work_full', 'double_start', 'double_bind',
         'wrong_core', 'tag_wrap', 'clock_wrap', 'lifetime', 'result_tag',
         'finish_leased', 'finish_done_pending', 'start_stopped_clock_poison', 'finish_stopped_clock_poison')

CLOCK_MODES = ('poison_worker_clock_start', 'poison_worker_clock_end', 'poison_wait_clock',
               'poison_publish_clock', 'poison_direct_step')
HOST_CLOCK_MODES = ('poison_worker_ms', 'poison_wait_ms', 'poison_start_ms')

@pytest.mark.parametrize('sanitize', [False, True])
@pytest.mark.parametrize('adapter', ['sdk', 'host'])
def test_native_pipeline_protocol(tmp_path, sanitize, adapter):
    cc = os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
    if not cc:
        pytest.skip('C compiler unavailable')
    # Compile actual shared source, never a rewritten/duplicated state machine.
    fixture = ROOT / 'tests/fixtures/renderer_pipeline'
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else []
    exe = tmp_path / 'protocol'
    subprocess.run([cc, '-std=c11', '-O1', '-g', '-pthread', '-Wall', '-Wextra', '-Werror',
                    *flags, '-Wno-unknown-pragmas', '-Wno-unused-function',
                    '-DLUNAR_PIPELINE_SDK_PLATFORM_HEADER="sdk_shim.h"',
                    *(['-DLUNAR_PIPELINE_TEST_HOST_CORE=1'] if adapter == 'host' else []),
                    '-I'+str(fixture), '-I'+str(ROOT/'firmware/devkit'),
                    '-I'+str(ROOT/'firmware/common'), str(fixture/'protocol.c'), '-o', str(exe)], check=True)
    env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    for mode in MODES + CLOCK_MODES + (HOST_CLOCK_MODES if adapter == 'host' else ()):
        result = subprocess.run([str(exe), mode], check=True, env=env, timeout=2 if 'stopped_clock_poison' in mode else 15,
                                capture_output=True, text=True)
        assert f'LUNAR_PIPELINE_HOST PASS mode={mode} ' in result.stdout
        if adapter == 'sdk' and mode in ('stream', 'work_full', 'output_full', 'output_full_descheduled'):
            assert 'LUNAR_PIPELINE ready=1 lifetime_ms=2100000 stack_words=1536 priority=16 outputs=8' in result.stdout
            assert 'LUNAR_PIPELINE final=1 ' in result.stdout
            assert result.stdout.count('LUNAR_PIPELINE_WAKE core=') == 2

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


def test_core_requires_an_explicit_port(tmp_path):
    cc = os.environ.get('CC') or shutil.which('cc')
    if not cc:
        pytest.skip('C compiler unavailable')
    result = subprocess.run([cc, '-std=c11', '-fsyntax-only',
                             str(ROOT/'firmware/common/renderer_pipeline_core.c')],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Supply an explicit pipeline port' in result.stderr
