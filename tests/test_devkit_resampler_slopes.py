"""Private preparation comparison: preserve float32 kernel and stream results."""
import importlib.util
from pathlib import Path
import re
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def preparer():
    spec = importlib.util.spec_from_file_location(
        'renderer_prepare', ROOT / 'tools/jieli/prepare-renderer-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def kernel():
    header = (ROOT / 'engines/include/fm1_resampler.h').read_text()
    definition = re.search(r'static const float fm1_resampler_kernel\[[^\]]+\] = \{.*?\n\};',
                           header, re.S).group()
    return header, definition


def floats(definition):
    return [float(x.strip()[:-1]) for x in
            definition.split(' = {', 1)[1].rsplit('};', 1)[0].split(',') if x.strip()]


def bits(value):
    return struct.pack('<f', value)


def test_pairs_preserve_bases_and_rounded_differences():
    _, original = kernel()
    values = [struct.unpack('<f', bits(x))[0] for x in floats(original)]
    pairs = floats(preparer().resampler_slope_definition(original))
    assert len(pairs) == 768 * 2
    for i in range(768):
        rounded_difference = struct.unpack('<f', bits(values[i + 1] - values[i]))[0]
        assert bits(pairs[2 * i]) == bits(values[i])
        assert bits(pairs[2 * i + 1]) == bits(rounded_difference / 65536)
    # Replaces 769 floats with 768 pairs, rather than retaining both copies.
    assert 24360 - 769 * 4 + len(pairs) * 4 == 27428 < 28 * 1024


def test_changed_kernel_shape_refuses_comparison():
    _, original = kernel()
    with pytest.raises(ValueError, match='coefficients'):
        preparer().resampler_slope_definition(original.replace('0.959999979f, ', '', 1))


def test_prescaled_kernel_preserves_complete_streams(tmp_path):
    if not shutil.which('cc'):
        pytest.skip('C compiler unavailable')
    header, definition = kernel()
    (tmp_path / 'original.h').write_text(header)
    changed = header.replace(definition, preparer().resampler_slope_definition(definition), 1)
    anchor = ('  const float *k = &fm1_resampler_kernel[t >> 16];\n'
              '  return k[0] + (float)(t & 0xFFFFu) * (1.0f / 65536.0f) * (k[1] - k[0]);')
    assert changed.count(anchor) == 1
    changed = changed.replace(anchor,
        '  const float *k = &fm1_resampler_kernel_pairs[(t >> 16) * 2];\n'
        '  return k[0] + (float)(t & 0xFFFFu) * k[1];', 1)
    (tmp_path / 'changed.h').write_text(changed)
    harness = tmp_path / 'stream.c'
    harness.write_text(r'''
#include HEADER
#include <assert.h>
#include <stdio.h>
int main(void) {
  const double rates[][2] = {{48000,44118}, {96000,44118}, {47872.34,44118},
                            {176472,44118}, {44118,44118}};
  for (unsigned c = 0; c < 5; ++c) {
    fm1_resampler_t r;
    assert(fm1_resampler_init(&r, rates[c][0], rates[c][1]));
    uint32_t rng = 0x12345678u;
    float input[257], output[97];
    uint32_t at = 257, n = 0;
    while (n < 16384) {
      if (at == 257) {
        for (unsigned i = 0; i < 257; ++i) {
          rng = rng * 1664525u + 1013904223u;
          input[i] = (float)(int32_t)(rng >> 8) / 8388608.0f - 1.0f;
        }
        at = 0;
      }
      uint32_t used = 0;
      uint32_t limit = n % 97 + 1;
      if (limit > 16384 - n) limit = 16384 - n;
      uint32_t made = fm1_resampler_process(&r, input + at, 257 - at,
                                            &used, output, limit);
      assert(used || made);
      at += used; n += made;
      assert(fwrite(output, sizeof(float), made, stdout) == made);
    }
  }
  return 0;
}
''')
    outputs = []
    for name in ('original', 'changed'):
        exe = tmp_path / name
        subprocess.run(['cc', '-std=c99', '-O2', '-ffp-contract=off', '-fno-fast-math',
                        '-DHEADER="' + name + '.h"', str(harness), '-lm', '-o', str(exe)], check=True)
        outputs.append(subprocess.run([str(exe)], check=True, capture_output=True).stdout)
    assert len(outputs[0]) == 5 * 16384 * 4
    assert outputs[0] == outputs[1]
