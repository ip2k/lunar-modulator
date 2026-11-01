"""Actual SDK-free adapter/core ownership tests; no CPU1 target admission."""
from pathlib import Path
import os
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
MODES = ('stream', 'missing_irq', 'wrong_core', 'stale_ack', 'launch_fail',
         'late_entry', 'timeout', 'setup_fail', 'late_ready',
         'entered_before_ready', 'clock_wrap', 'irq_reinit', 'bad_argument',
         'late_launch_fail', 'deadline', 'prepoison_before_irq',
         'prepoison_after_irq', 'invalid_api_before_start', 'poison_direct_core_start',
         'hook_poison_ready', 'hook_abort_ready')

@pytest.mark.parametrize('sanitize', [False, True])
def test_native_lifecycle(tmp_path, sanitize):
    cc = os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
    if not cc:
        pytest.skip('C compiler unavailable')
    fixture = ROOT / 'tests/fixtures/renderer_pipeline'
    exe = tmp_path / 'native-lifecycle'
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else []
    subprocess.run([cc, '-std=c11', '-O1', '-g', '-pthread', '-Wall', '-Wextra',
                    '-Werror', '-Wno-unused-function', *flags,
                    '-I'+str(fixture), '-I'+str(ROOT/'firmware/native'),
                    str(fixture/'native_lifecycle.c'), '-o', str(exe)], check=True)
    env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    for mode in MODES:
        result = subprocess.run([str(exe), mode], check=True, env=env, timeout=8,
                                capture_output=True, text=True)
        assert f'NATIVE_LIFECYCLE PASS {mode} ' in result.stdout


def test_native_default_refuses_without_clock_or_hardware(tmp_path):
    cc = os.environ.get('CC') or shutil.which('clang') or shutil.which('cc')
    if not cc:
        pytest.skip('C compiler unavailable')
    source = ROOT/'firmware/native/renderer_pipeline_native.c'
    client = tmp_path/'client.c'
    client.write_text('#include "renderer_pipeline_native.h"\n#include <assert.h>\n'
                      'static unsigned clock_calls;\n'
                      'static uint32_t ticks(void) {++clock_calls; return 0;}\n'
                      'int main(void) {\n'
                      'assert(!lunar_pipeline_native_hardware_admitted());\n'
                      'assert(lunar_pipeline_native_primary_irq_ready());\n'
                      'assert(!lunar_pipeline_native_start(ticks));\n'
                      'assert(!clock_calls);\n'
                      'lunar_pipeline_native_status_t s; lunar_pipeline_native_status(&s);\n'
                      'assert(s.refused && !s.published && !s.entered && !s.ready);\n'
                      'assert(!lunar_pipeline_native_start(ticks)); return 0;}\n')
    exe = tmp_path/'disabled'
    command = [cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
               '-I'+str(ROOT/'firmware/native'), str(source), str(client), '-o', str(exe)]
    subprocess.run(command, check=True)
    subprocess.run([str(exe)], check=True, timeout=3)
    result = subprocess.run(command+['-DLUNAR_NATIVE_PIPELINE_ENABLE=1'], capture_output=True, text=True)
    assert result.returncode and 'have not been admitted' in result.stderr
