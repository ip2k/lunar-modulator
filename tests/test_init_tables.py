"""Derived tables computed at startup (tools/init_tables.py, engines/src/fm1_init_tables.cc).

The generated C++ is compiled on the host and every entry of each of the four
tables is compared with the stored table it replaces: kSinTab12 and kExp2Tab
from msfa_rom.cc, the kernel pairs exactly as the stored-table build defines
them (prepare-renderer-devkit.py resampler_slope_definition) and Plaits'
lut_sine from resources.cc. The dev-kit image checks the same hashes on the
target (notes/2026-11-10-init-tables.md).
"""
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]

DRIVER = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
namespace fm1_msfa { extern int16_t kSinTab12[4096]; extern int32_t kExp2Tab[2048]; }
namespace plaits { extern float lut_sine[641]; }
extern float fm1_resampler_kernel_pairs[1536];
extern "C" void lunar_init_tables(void);
extern "C" uint32_t lunar_init_tables_check(uint32_t out[4]);
static uint32_t bits(float x) { uint32_t w; memcpy(&w, &x, 4); return w; }
int main() {
  uint32_t h[4];
  printf("before %u\n", (unsigned)lunar_init_tables_check(h));
  lunar_init_tables();
  uint32_t bad = lunar_init_tables_check(h);
  printf("check %u %08x %08x %08x %08x\n", (unsigned)bad, (unsigned)h[0], (unsigned)h[1],
         (unsigned)h[2], (unsigned)h[3]);
  printf("sin12");
  for (int i = 0; i < 4096; i++) printf(" %d", fm1_msfa::kSinTab12[i]);
  printf("\nexp2");
  for (int i = 0; i < 2048; i++) printf(" %d", (int)fm1_msfa::kExp2Tab[i]);
  printf("\npairs");
  for (int i = 0; i < 1536; i++) printf(" %08x", (unsigned)bits(fm1_resampler_kernel_pairs[i]));
  printf("\nlut_sine");
  for (int i = 0; i < 641; i++) printf(" %08x", (unsigned)bits(plaits::lut_sine[i]));
  printf("\n");
  return 0;
}
'''


def generator():
    spec = importlib.util.spec_from_file_location('init_tables', ROOT / 'tools/init_tables.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def f32_bits(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


def test_generated_file_is_current():
    gen = generator()
    assert gen.OUT.read_text() == gen.source(), 'run tools/init_tables.py'


@pytest.mark.parametrize('table', ['sin12', 'exp2', 'lut_sine'])
def test_generator_refuses_a_table_that_is_not_derivable(tmp_path, table):
    gen = generator()
    for rel in ('engines/src/msfa_rom.cc', 'engines/include/fm1_resampler.h',
                'engines/third_party/mutable/plaits/resources.cc'):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tmp_path / rel)
    if table == 'lut_sine':
        # One mirrored point in the second quarter, changed in its third decimal.
        p = tmp_path / 'engines/third_party/mutable/plaits/resources.cc'
        text = p.read_text()
        start = text.index('const float lut_sine[] = {')
        old = gen.lut_sine_literals(text)[200]
        i = text.index(old, start + 1000)
        p.write_text(text[:i] + old[:4] + str((int(old[4]) + 1) % 10) + old[5:] + text[i + len(old):])
    else:
        p = tmp_path / 'engines/src/msfa_rom.cc'
        text = p.read_text()
        head = ('extern const int16_t kSinTab12[4096] = {\n  25,' if table == 'sin12'
                else 'extern const int32_t kExp2Tab[2048] = {\n  727064,')
        p.write_text(text.replace(head, head[:-3] + str(int(head.rsplit(' ', 1)[1][:-1]) + 1) + ',', 1))
    with pytest.raises(ValueError, match='not exactly derivable'):
        gen.tables(tmp_path)


def test_generator_refuses_kernel_pairs_that_are_not_derivable(monkeypatch):
    """The pairs are derived from the same kernel as the stored ones, so only the
    reference side can disagree: perturb one stored slope by one ulp."""
    gen = generator()
    stored = gen.stored_pairs

    def perturbed(header):
        v = stored(header)
        w = gen.f32_bits(v[101]) + 1
        v[101] = struct.unpack('<f', struct.pack('<I', w))[0]
        return v

    monkeypatch.setattr(gen, 'stored_pairs', perturbed)
    with pytest.raises(ValueError, match='fm1_resampler_kernel_pairs is not exactly derivable'):
        gen.tables()


@pytest.mark.parametrize('opt', ['-O0', '-O2', '-Os'])
def test_host_build_regenerates_every_entry(tmp_path, opt):
    cxx = shutil.which('c++') or shutil.which('clang++') or shutil.which('g++')
    if not cxx:
        pytest.skip('no host C++ compiler')
    gen = generator()
    t = gen.tables()
    driver = tmp_path / 'driver.cc'
    driver.write_text(DRIVER)
    exe = tmp_path / 'init-tables'
    subprocess.run([cxx, '-std=c++11', opt, '-ffp-contract=off', '-fno-exceptions', '-fno-rtti',
                    '-Wall', '-Wextra', '-Werror', '-DFM1_INIT_TABLES_SECTION=', '-DFM1_INIT_TABLES_CHECK=1',
                    str(ROOT / 'engines/src/fm1_init_tables.cc'), str(driver), '-o', str(exe)], check=True)
    lines = dict(line.split(' ', 1) for line in
                 subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.splitlines())
    # All four tables are zero before the call, so every hash differs from the stored one.
    assert lines['before'] == '15'
    check = lines['check'].split()
    assert check[0] == '0'
    assert [int(x, 16) for x in check[1:]] == t['hashes']
    assert [int(x) for x in lines['sin12'].split()] == t['sin12']
    assert [int(x) for x in lines['exp2'].split()] == t['exp2']
    assert [int(x, 16) for x in lines['pairs'].split()] == [f32_bits(x) for x in t['pairs']]
    assert [int(x, 16) for x in lines['lut_sine'].split()] == [f32_bits(x) for x in t['lut_sine']]


def test_stored_references_are_the_shipped_definitions():
    """The comparison targets are the stored tables themselves, not the generator's own derivation."""
    gen = generator()
    t = gen.tables()
    rom = (ROOT / 'engines/src/msfa_rom.cc').read_text()
    assert t['sin12'][:3] == [25, 75, 126] and len(t['sin12']) == 4096
    assert t['exp2'][:2] == [727064, 1073741824] and t['exp2'][-1] == 2146030505
    assert t['exp2'][-2] == (1 << 31) - 2146030505
    assert 'extern const int32_t kExp2Tab[2048] = {' in rom
    # Every pair comes from resampler_slope_definition's text, the stored-table build's.
    assert len(t['pairs']) == 1536 and t['pairs'][0] == struct.unpack('<f', struct.pack('<f', 0.959999979))[0]
    assert len(t['lut_sine']) == 641 and t['lut_sine'][0] == 0.0
    # Seed sizes: what stays in flash.
    assert len(t['quarter']) == 1024 and len(t['values']) == 1024
    assert len(t['kernel_literals']) == 769 and len(t['sine_seed_literals']) == 131
