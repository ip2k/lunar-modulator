"""Exercise the native RAM map with real ELF section allocation (GNU ld)."""
import shutil
import subprocess
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPACITY = 0x6C000


@pytest.mark.parametrize('case', range(16), ids=lambda i: f'boundary-{i:02d}')
def test_native_ram_boundary(tmp_path, case):
    toolchain = os.environ.get('FM1_PI32_TOOLCHAIN')
    flags = []
    if toolchain:
        tc = Path(toolchain)
        cc = str(tc / 'common/bin/clang')
        ld = str(tc / 'pi32v2/bin/ld')
        nm = str(tc / 'pi32v2/bin/nm')
        flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1']
    else:
        cc, ld, nm = shutil.which('cc'), shutil.which('ld'), shutil.which('nm')
    if not cc or not ld:
        pytest.skip('GNU ELF tools required')
    version = subprocess.run([ld, '--version'], capture_output=True, text=True)
    if 'GNU ld' not in version.stdout:
        pytest.skip('GNU ELF linker required')
    # Eight distinct global sizes, each with an exactly full or overflowing pool.
    # These cover the old global/pool boundary and the actual stack guard boundary.
    globals_size = (case // 2 + 1) * 8192
    overflow = case % 2
    pool_size = CAPACITY - globals_size + overflow * 16
    source = tmp_path / 'sections.S'
    source.write_text(f'''
.section .text.crt0,"ax",@progbits
.global _start
_start:
.byte 0
.section .bss,"aw",@nobits
.balign 16
.space {globals_size}
.section .pool,"aw",@nobits
.balign 16
.space {pool_size}
''')
    obj, elf = tmp_path / 'sections.o', tmp_path / 'sections.elf'
    subprocess.run([cc, *flags, '-c', str(source), '-o', str(obj)], check=True,
                   capture_output=True)
    result = subprocess.run([ld, '-T', str(ROOT / 'firmware/native/app.ld'),
                             str(obj), '-o', str(elf)], capture_output=True, text=True)
    if overflow:
        assert result.returncode != 0
        assert 'Lunar globals and arenas overlap stack guard' in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        symbols = subprocess.check_output([nm, '-n', str(elf)], text=True)
        values = {line.split()[-1]: int(line.split()[0], 16)
                  for line in symbols.splitlines() if len(line.split()) == 3}
        assert values['_pool_end'] == values['_guard0'] == 0x01C74000
        assert values['_bss_end'] <= values['_pool_start']
        assert values['_pool_start'] % 16 == 0
        assert values['_ustack_lo'] == 0x01C74100
        assert values['_sstack_top'] == 0x01C7C000
