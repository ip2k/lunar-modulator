"""Bounded diagnostic scans: every stack depth, untouched guards, read-only RAM."""
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from stack_watermark import PAINTER_BYTES, instrument_entry, verify_instrumentation


@pytest.mark.parametrize('case', range(30))
def test_stack_margin(case, tmp_path):
    source = tmp_path / 'scan.c'
    source.write_text(r'''
#include "stack_watermark.h"
#include <assert.h>
#include <string.h>
int main(void) {
    /* Model both reserved stack sizes, with guard words at either end. */
    const unsigned counts[2] = {24320 / 4, 7936 / 4};
    uint32_t memory[6082], before[6082];
    for (unsigned region = 0; region < 2; ++region) {
        unsigned count = counts[region];
        for (unsigned depth = CASE; depth <= count; depth += 30) {
            memory[0] = 0xBAD0; memory[count + 1] = 0xBAD1;
            for (unsigned i = 0; i < count; ++i)
                memory[i + 1] = i < count - depth ? LUNAR_STACK_PATTERN : i;
            memcpy(before, memory, sizeof memory);
            assert(lunar_stack_pattern_margin(memory + 1, count) ==
                   (count - depth) * 4u);
            assert(!memcmp(before, memory, sizeof memory));
        }
    }
    assert(lunar_stack_pattern_margin(0, 0) == 0);
    uint32_t gap[] = {LUNAR_STACK_PATTERN, 0, LUNAR_STACK_PATTERN};
    assert(lunar_stack_pattern_margin(gap, 3) == 4);
    return 0;
}
''')
    binary = tmp_path / 'scan'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-DCASE=' + str(case), '-I', str(ROOT / 'firmware/native'),
                    str(source), '-o', str(binary)], check=True, capture_output=True)
    subprocess.run([str(binary)], check=True, capture_output=True)


def test_entry_instrumentation_preserves_guard_layout():
    source = (ROOT / 'firmware/third_party/dinghy/crt0.S').read_text()
    source += '\nlunar_entry_rejected:\n\tgoto lunar_entry_rejected\n'
    output = instrument_entry(source)
    prefix, painter = output.split('\t.section .text.lunar_stack_watermark,"ax",@progbits', 1)
    assert prefix == source.replace('\tcall fm1_cstart\n',
                                    '\tcall lunar_stack_watermark_begin\n') + '\n'
    assert painter.count('\tcall ') == 1
    assert painter.index('_ustack_lo') < painter.index('_ustack_top')
    assert painter.index('_sstack_lo') < painter.index('_sstack_top')
    assert 'r0' not in painter and 'sp =' not in painter
    with pytest.raises(ValueError):
        instrument_entry(output)
    with pytest.raises(ValueError):
        instrument_entry(source + source)


def test_compiled_watermark_rejects_changed_store_and_call():
    class Image:
        symbols = {'lunar_stack_watermark_begin': 0x2069e04,
                   'lunar_stack_watermark_end': 0x2069e32, 'fm1_cstart': 0x205ef4e}
        regions = {0x2069e04: PAINTER_BYTES,
                   0x2000158: bytes.fromhex('eeff00a0c701 edff00c0c701'),
                   0x2000164: bytes.fromhex('83ea4e4e'),
                   0x2069e32: bytes.fromhex('bfea8ca8')}

        def symbol_value(self, name):
            return self.symbols[name]

        def read(self, address, count):
            return self.regions[address][:count]

    dis = (' 2000164:    83 ea 4e 4e       \tcall 433308 '
           '<lunar_stack_watermark_begin : 2069e04 >\n'
           ' 2069e32:    bf ea 8c a8       \tcall -44776 <fm1_cstart : 205ef4e >\n')
    image = Image()
    assert verify_instrumentation(image, dis)['worst_case_stack_bound'] is False
    for i in range(len(PAINTER_BYTES)):
        image.regions = dict(Image.regions)
        changed = bytearray(PAINTER_BYTES)
        changed[i] ^= 1
        image.regions[0x2069e04] = bytes(changed)
        with pytest.raises(ValueError, match='painter bytes'):
            verify_instrumentation(image, dis)
    image.regions = dict(Image.regions)
    with pytest.raises(ValueError, match='Missing compiled'):
        verify_instrumentation(image, dis.replace('fm1_cstart', 'unsafe_target'))
    image.regions[0x2000164] = bytes(4)
    with pytest.raises(ValueError, match='match ELF'):
        verify_instrumentation(image, dis)
