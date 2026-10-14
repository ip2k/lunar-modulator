from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_full_range_readout_and_footer_layout(tmp_path):
    source = tmp_path / 'readout.c'
    source.write_text(r'''#include "realtime_readout.h"
#include "fm1_tft.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static fm1_tft_t t;
int main(int argc, char **argv) {
    const uint32_t cases[] = {0, 1, 9, 10, 1450, 11605, 999999999, UINT32_MAX};
    struct { char before; char line[36]; char after; } s;
    s.before = 'A'; s.after = 'B';
    for (unsigned i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        char expected[36];
        uint32_t r = cases[i], d = cases[7 - i], u = cases[(i + 3) % 8];
        lunar_realtime_readout(s.line, r, d, u);
        snprintf(expected, sizeof expected, "R%010u D%010u U%010u", r, d, u);
        assert(!strcmp(s.line, expected));
        assert(s.before == 'A' && s.after == 'B');
    }
    lunar_realtime_readout(s.line, UINT32_MAX, UINT32_MAX, UINT32_MAX);
    fm1_tft_begin(&t, 0x4208);
    fm1_tft_fill(&t, 0, 208, 240, 32, 0);
    int a = fm1_tft_text(&t, 4, 212, "OBS U 24320 S 07936", 19, 1, 0xffff);
    int b = fm1_tft_text(&t, 128, 212, "R/D us", 6, 1, 0xffff);
    int c = fm1_tft_text(&t, 4, 224, s.line, 35, 1, 0xffff);
    assert(4 + a + 4 <= 128 && 128 + b <= 236 && 4 + c <= 236);
    assert(!t.truncated && fm1_tft_pixels_valid(&t));
    for (unsigned y = 0; y < 240; ++y)
        for (unsigned x = 0; x < 240; ++x) {
            uint16_t pixel = fm1_tft_pixel(&t, y * 240 + x);
            if (y < 208) assert(pixel == 0x4208);
            else if (x < 4 || x >= 236 || (y >= 221 && y < 224) || y >= 233)
                assert(pixel == 0);
        }
    if (argc == 2) {
        FILE *f = fopen(argv[1], "wb"); assert(f);
        fprintf(f, "P6\n240 240\n255\n");
        for (unsigned i = 0; i < 240 * 240; ++i) {
            uint16_t p = fm1_tft_pixel(&t, i);
            unsigned char rgb[] = {(p >> 11) * 255 / 31,
                ((p >> 5) & 63) * 255 / 63, (p & 31) * 255 / 31};
            fwrite(rgb, 1, 3, f);
        }
        assert(!fclose(f));
    }
    return 0;
}
''')
    binary = tmp_path / 'readout'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
        '-DFM1_TFT_INDEXED=1', '-I', str(ROOT / 'firmware/native'),
        '-I', str(ROOT / 'sim/web/src'), str(source),
        str(ROOT / 'sim/web/src/fm1_tft.c'), '-o', str(binary)], check=True)
    subprocess.run([str(binary), str(tmp_path / 'footer.ppm')], check=True)
