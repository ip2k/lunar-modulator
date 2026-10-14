# SPDX-License-Identifier: MIT
"""Exercise actual C timer policy across wrap and continuous operation."""
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from runtime_mode import runtime_configuration


@pytest.mark.parametrize('mode', [None, '20', '120', '0'], ids=['default', 'diagnostic', 'song', 'continuous'])
@pytest.mark.parametrize('start,elapsed', [
    (0, 0), (0, 19999), (0, 20000), (0, 20001),
    (0xfffffff0, 0), (0xfffffff0, 19999),
    (0xfffffff0, 20000), (0xfffffff0, 20001),
    (0, 119999), (0, 120000), (0, 120001),
    (0xfffffff0, 119999), (0xfffffff0, 120000), (0xfffffff0, 120001),
    (0, 0xffffffff), (0xffffffff, 0xffffffff),
])
def test_actual_runtime_timer(tmp_path, mode, start, elapsed):
    source = tmp_path / 'timer.c'
    source.write_text('''#include "runtime_mode.h"
#include <stdlib.h>
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    uint32_t start = (uint32_t)strtoul(argv[1], 0, 10);
    uint32_t elapsed = (uint32_t)strtoul(argv[2], 0, 10);
    return lunar_runtime_expired(start + elapsed, start) ? 1 : 0;
}
''')
    executable = tmp_path / 'timer'
    flags = [] if mode is None else ['-DLUNAR_RETURN_TO_ROM_SECONDS=' + mode]
    subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-I', str(ROOT / 'firmware/native'), *flags,
                    str(source), '-o', str(executable)], check=True)
    result = subprocess.run([str(executable), str(start), str(elapsed)])
    expected = int(mode != '0' and elapsed >= (120000 if mode == '120' else 20000))
    assert result.returncode == expected


@pytest.mark.parametrize('mode,seconds', [('diagnostic', 20), ('song-diagnostic', 120), ('continuous', None)])
def test_configuration_binds_mode(mode, seconds):
    report = runtime_configuration(mode)
    assert report['runtime_mode'] == mode
    assert report['return_to_rom_seconds'] == seconds
    assert report['define'] == '-DLUNAR_RETURN_TO_ROM_SECONDS=' + str(seconds or 0)
    assert report['release_accepted'] is False


def test_unknown_mode_refused():
    with pytest.raises(ValueError):
        runtime_configuration('release')


@pytest.mark.parametrize('seconds', ['1', '21'])
def test_unsupported_compiler_mode_refused(tmp_path, seconds):
    source = tmp_path / 'bad.c'
    source.write_text('#include "runtime_mode.h"\n')
    result = subprocess.run(['cc', '-std=c99', '-I', str(ROOT / 'firmware/native'),
                             '-DLUNAR_RETURN_TO_ROM_SECONDS=' + seconds,
                             '-c', str(source), '-o', str(tmp_path / 'bad.o')],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'explicit continuous mode' in result.stderr
