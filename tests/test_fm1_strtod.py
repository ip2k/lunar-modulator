"""firmware/fm1/fm1_strtod.c, the FM-1 size lever's strtod/strtof, against the
host C library: every value it returns must be bit-identical to strtod's or
strtof's with the same end pointer, and everything else must be refused
(0, *end == s). notes/2026-11-10-size-levers.md."""
from pathlib import Path
import random
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
double lunar_fm1_strtod(const char *s, char **end);
float lunar_fm1_strtof(const char *s, char **end);
int main(void) {
    char line[256];
    unsigned long accepted_d = 0, accepted_f = 0, total = 0;
    while (fgets(line, sizeof line, stdin)) {
        char *a, *b;
        double x, y;
        float f, g;
        line[strcspn(line, "\n")] = 0;
        ++total;
        x = lunar_fm1_strtod(line, &a);
        y = strtod(line, &b);
        if (a == line) {
            if (x != 0.0) { printf("BAD refuse-value d [%s]\n", line); return 1; }
        } else {
            ++accepted_d;
            if (a != b || memcmp(&x, &y, sizeof x)) { printf("BAD d [%s] %.17g %.17g %d %d\n", line, x, y, (int)(a - line), (int)(b - line)); return 1; }
        }
        f = lunar_fm1_strtof(line, &a);
        g = strtof(line, &b);
        if (a == line) {
            if (f != 0.0f) { printf("BAD refuse-value f [%s]\n", line); return 1; }
        } else {
            ++accepted_f;
            if (a != b || memcmp(&f, &g, sizeof f)) { printf("BAD f [%s] %.9g %.9g %d %d\n", line, f, g, (int)(a - line), (int)(b - line)); return 1; }
        }
    }
    printf("OK %lu %lu %lu\n", total, accepted_d, accepted_f);
    return 0;
}
"""

FIXED = """0
-0
+0.0
1
-1
1.
.5
-.25
.
-
+
e5
1e
1e+
1e-
1e5
1E+05
1e-5
2.5e-3x
12 dB
1.2k
1.2 kHz
  42
\t-7.75
0x10
inf
-INFINITY
nan
1e22
1e23
1e30
9007199254740992
9007199254740993
123456789012345678901
1000000000000000000000
0.1
0.2
0.3
3.14159265358979
0.70710677
16777217
16777216
0.000001
1e-22
1e-23
3.4028235e38
3.4028236e38
1e39
1e-38
1e-45
4.9406564584124654e-324
0.000000000000000000001
00000000000000000000000000001
1.00000000000000000000
""".split('\n')


def cases(seed=20261110, count=60000):
    rnd = random.Random(seed)
    out = [c for c in FIXED if c]
    for _ in range(count):
        kind = rnd.random()
        if kind < 0.4:
            v = rnd.uniform(-1e4, 1e4)
            out.append(('%.' + str(rnd.randint(0, 9)) + 'f') % v)
        elif kind < 0.6:
            out.append(repr(rnd.uniform(-2, 2) * 10 ** rnd.randint(-30, 30)))
        elif kind < 0.75:
            out.append('%.9g' % rnd.uniform(-1, 1))
        elif kind < 0.9:
            digits = ''.join(rnd.choice('0123456789') for _ in range(rnd.randint(1, 24)))
            point = rnd.randint(0, len(digits))
            text = digits[:point] + '.' + digits[point:]
            if rnd.random() < 0.4:
                text += 'e' + str(rnd.randint(-40, 40))
            out.append(rnd.choice(['', '-', '+']) + text + rnd.choice(['', '', 'k', ' Hz', 'e', 'x']))
        else:
            out.append(''.join(rnd.choice('0123456789.+-eE x') for _ in range(rnd.randint(1, 12))))
    return out


@pytest.mark.skipif(shutil.which('cc') is None, reason='needs a C compiler')
def test_strtod_matches_libc_or_refuses(tmp_path):
    src = tmp_path/'harness.c'
    src.write_text(HARNESS)
    exe = tmp_path/'harness'
    subprocess.run(['cc', '-std=c99', '-O2', '-ffp-contract=off', '-o', str(exe), str(src),
                    str(ROOT/'firmware/fm1/fm1_strtod.c')], check=True)
    lines = cases()
    result = subprocess.run([str(exe)], input='\n'.join(lines) + '\n', capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    total, accepted_d, accepted_f = map(int, result.stdout.split()[1:])
    assert total == len(lines)
    # The fast path must carry the ordinary inputs, not refuse its way to a pass.
    assert accepted_d > 0.6 * total and accepted_f > 0.6 * total, result.stdout


@pytest.mark.skipif(shutil.which('cc') is None, reason='needs a C compiler')
def test_ordinary_values_are_accepted(tmp_path):
    src = tmp_path/'probe.c'
    src.write_text(r"""
#include <stdio.h>
double lunar_fm1_strtod(const char *s, char **end);
float lunar_fm1_strtof(const char *s, char **end);
int main(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        char *a, *b;
        lunar_fm1_strtod(argv[i], &a);
        lunar_fm1_strtof(argv[i], &b);
        printf("%d %d\n", (int)(a - argv[i]), (int)(b - argv[i]));
    }
    return 0;
}
""")
    exe = tmp_path/'probe'
    subprocess.run(['cc', '-std=c99', '-o', str(exe), str(src), str(ROOT/'firmware/fm1/fm1_strtod.c')], check=True)
    texts = ['1', '-12.5', '0.70710677', '440', '1.2k', '120 bpm', '1e3', '0.000001', '16777217', '1000000000000000000000']
    out = subprocess.run([str(exe), *texts], capture_output=True, text=True, check=True).stdout.split('\n')
    used = {t: tuple(map(int, line.split())) for t, line in zip(texts, out)}
    for t in texts:
        number = len(t.split(' ')[0].rstrip('k'))
        assert used[t] == (number, number), (t, used[t])
    # Refused rather than approximated: hexadecimal and inf/nan spellings.
    out = subprocess.run([str(exe), '0x10', 'inf', 'nan'], capture_output=True, text=True, check=True).stdout
    assert out.split('\n')[:3] == ['0 0', '0 0', '0 0']


WRITERS = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
double lunar_fm1_strtod(const char *s, char **end);
float lunar_fm1_strtof(const char *s, char **end);
/* One line per input, "d TEXT" or "f TEXT"; prints A (accepted, identical to
 * the C library), R (refused) or X (accepted but different). */
int main(void) {
    char line[256];
    while (fgets(line, sizeof line, stdin)) {
        char *s = line + 2, *a, *b;
        line[strcspn(line, "\n")] = 0;
        if (line[0] == 'd') {
            double x = lunar_fm1_strtod(s, &a), y = strtod(s, &b);
            putchar(a == s ? 'R' : (a == b && !memcmp(&x, &y, sizeof x)) ? 'A' : 'X');
        } else {
            float x = lunar_fm1_strtof(s, &a), y = strtof(s, &b);
            putchar(a == s ? 'R' : (a == b && !memcmp(&x, &y, sizeof x)) ? 'A' : 'X');
        }
    }
    putchar('\n');
    return 0;
}
"""


@pytest.mark.skipif(shutil.which('cc') is None, reason='needs a C compiler')
def test_device_writer_formats_and_limits(tmp_path):
    # The formats the panel writes for these parsers (sim/web/src/fm1_mod_ui.c,
    # fm1_edit.c): amt=/ofs= with %.12g of a Q1.14 value x100/16384, and %.9g
    # floats. The documented limits of the fast path are pinned here as well
    # (notes/2026-11-10-size-levers.md §2): %.9g text is refused below about
    # 1e-14 in magnitude and %.12g text below about 1e-11, because the power
    # of ten falls under 10^-22.
    import struct
    src = tmp_path/'writers.c'
    src.write_text(WRITERS)
    exe = tmp_path/'writers'
    subprocess.run(['cc', '-std=c99', '-O2', '-ffp-contract=off', '-o', str(exe), str(src),
                    str(ROOT/'firmware/fm1/fm1_strtod.c')], check=True)

    def run(lines):
        out = subprocess.run([str(exe)], input='\n'.join(lines) + '\n', capture_output=True,
                             text=True, check=True).stdout.strip()
        assert len(out) == len(lines)
        return out

    amounts = ['d %.12g' % (q * 100 / 16384) for q in range(-32768, 32768)]
    assert set(run(amounts)) == {'A'}
    rnd = random.Random(20261110)
    floats = []
    while len(floats) < 20000:
        x = struct.unpack('<f', struct.pack('<I', rnd.getrandbits(32)))[0]
        if 1e-14 <= abs(x) <= 1e37:
            floats.append('%.9g' % x)
    assert set(run(['f ' + t for t in floats] + ['d ' + t for t in floats])) == {'A'}
    # Just outside: refused, never approximated.
    assert run(['f 1.23456789e-15', 'd 1.23456789e-15', 'd 1.23456789012e-12',
                'f 3.40282347e+38', 'f 1.17549435e-38']) == 'RRRRR'
