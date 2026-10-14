from pathlib import Path
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('case', range(30))
def test_readout(case, tmp_path):
    source = tmp_path / 'readout.c'
    source.write_text(r'''#include "stack_readout.h"
#include "fm1_tft.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static fm1_tft_t t;
int main(void) {
    struct { char a; char margins[20]; char samples[19]; char b; } s;
    s.a = 'A'; s.b = 'B';
    for (unsigned u = CASE; u <= 24320; u += 30) {
        char expected[20];
        unsigned sys = u % 7937;
        lunar_stack_readout(s.margins, s.samples, u, sys, UINT32_MAX);
        snprintf(expected, sizeof expected, "OBS U %05u S %05u", u, sys);
        assert(!strcmp(s.margins, expected));
        assert(!strcmp(s.samples, "SAMPLES 4294967295"));
        assert(s.a == 'A' && s.b == 'B');
    }
    lunar_stack_readout(s.margins, s.samples, UINT32_MAX, UINT32_MAX, 0);
    assert(!strcmp(s.margins, "OBS U ----- S -----"));
    assert(!strcmp(s.samples, "SAMPLES 0000000000"));
    lunar_stack_readout(s.margins, s.samples, 24320, 7936, 20);
    fm1_tft_begin(&t, 0x4208);
    fm1_tft_fill(&t, 0, 208, 240, 32, 0);
    int a = fm1_tft_text(&t, 4, 212, s.margins, 19, 1, 0xffff);
    int b = fm1_tft_text(&t, 4, 224, s.samples, 18, 1, 0xffff);
    assert(a + 4 <= 236 && b + 4 <= 236);
    assert(fm1_tft_pixels_valid(&t));
    for (unsigned y = 0; y < 208; ++y)
        for (unsigned x = 0; x < 240; ++x)
            assert(fm1_tft_pixel(&t, y * 240 + x) == 0x4208);
    for (unsigned y = 212; y < 233; ++y)
        for (unsigned x = 0; x < 240; ++x)
            if (x < 4 || x >= 236 || (y >= 221 && y < 224))
                assert(fm1_tft_pixel(&t, y * 240 + x) == 0);
    return 0;
}
''')
    binary = tmp_path / 'readout'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-DCASE=' + str(case),
        '-DFM1_TFT_INDEXED=1', '-I', str(ROOT / 'firmware/native'),
        '-I', str(ROOT / 'sim/web/src'), str(source),
        str(ROOT / 'sim/web/src/fm1_tft.c'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
