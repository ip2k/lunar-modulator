"""Packed-set bridge matches the existing importer; failures stay in scratch."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "content_set.h"
#include "instance_pool.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned offs;
static void note_off(void *self, uint8_t key) { (void)self; if (key == 60) ++offs; }
static const fm1_param_t params[] = { { .name = "Decay", .uid = 12 } };
static const fm1_engine_t engine = { .params = params, .n_params = 1, .note_off = note_off };
static unsigned char *file(const char *name, size_t *size) {
    FILE *f = fopen(name, "rb"); unsigned char *p;
    if (!f || fseek(f, 0, SEEK_END)) exit(10);
    *size = (size_t)ftell(f); rewind(f);
    p = malloc(*size + 1);
    if (!p || fread(p, 1, *size, f) != *size) exit(11);
    fclose(f); return p;
}
int main(int argc, char **argv) {
    fm1_seq_limits_t lim; fm1_state_report_t report;
    size_t nb, nt, bytes, n1, n2; unsigned char *bin, *text;
    void *a, *b, *live, *snapshot; fm1_seq_t *sa, *sb;
    char *e1 = malloc(131072), *e2 = malloc(131072);
    int ok;
    fm1_app_t *app = calloc(1, sizeof(*app)), *app_before = malloc(sizeof(*app));
    if (!app || !app_before) return 24;
    if (argc != 5 || !e1 || !e2) return 12;
    bin = file(argv[1], &nb); text = file(argv[2], &nt);
    fm1_seq_limits_default(&lim, 4); bytes = fm1_seq_size(&lim);
    a = calloc(1, bytes); b = calloc(1, bytes);
    live = calloc(1, bytes); snapshot = malloc(bytes);
    if (!a || !b || !live || !snapshot) return 13;
    sa = fm1_seq_create(a, &lim, 44118); sb = fm1_seq_create(b, &lim, 44118);
    if (!sa || !sb || !fm1_seq_create(live, &lim, 44118)) return 14;
    app->seq = live;
    fm1_seq_host_init(&app->seq_host, app->seq, app->seq_ev, FM1_APP_SEQ_EVENTS);
    app->unit[0].e = &engine;
    fm1_seq_host_bind(&app->seq_host, &engine);
    app->seq_note_count[0][60] = 2;
    app->seq_pending = 1; app->seq_gen = 7;
    app->seq_host.lane_uid[0][0] = 999;
    memcpy(snapshot, live, bytes); memcpy(app_before, app, sizeof(*app));
    if (fm1_seq_can_replace(sa, sa) || fm1_seq_replace(sa, sa) ||
        fm1_seq_can_replace(NULL, sa) || fm1_seq_can_replace(sa, NULL)) return 25;
    fm1_seq_create(b, &lim, 48000);
    if (fm1_seq_replace(sa, sb)) return 26;
    fm1_seq_create(b, &lim, 44118);
    { fm1_seq_limits_t other = lim; ++other.clip_notes;
      fm1_seq_create(b, &other, 44118);
      if (fm1_seq_replace(sa, sb)) return 27;
      fm1_seq_create(b, &lim, 44118); }
    { fm1_seq_ev_t events[72];
      fm1_seq_apply_text(sb, "play", 4, events, 72);
      if (fm1_seq_replace(sa, sb)) return 31;
      fm1_seq_create(b, &lim, 44118); }
    if (fm1_seq_can_replace((const fm1_seq_t *)((char *)a + 1), sb)) return 32;
    ok = lunar_content_activate_set(app, bin, (uint32_t)nb, sa, &report);
    if (atoi(argv[3]) && !atoi(argv[4])) {
        if (!ok || offs != 2 || app->seq_note_count[0][60] || app->seq_pending ||
            app->seq_gen != 8 || app->seq_host.lane_uid[0][0] != 12 ||
            memcmp(live, sa, bytes)) return 28;
    } else if (ok || offs || memcmp(snapshot, live, bytes) ||
               memcmp(app_before, app, sizeof(*app))) return 29;
    /* The live arena must be rejected before the container can mutate it. */
    memcpy(snapshot, live, bytes); memcpy(app_before, app, sizeof(*app));
    if (lunar_content_activate_set(app, bin, (uint32_t)nb, app->seq, &report) ||
        memcmp(snapshot, live, bytes) || memcmp(app_before, app, sizeof(*app))) return 30;
    ok = lunar_content_load_set(bin, (uint32_t)nb, sa, &report);
    if (memcmp(snapshot, live, bytes)) return 15;
    if (atoi(argv[3])) {
        if (!ok || report.code != FM1_STATE_OK) return 16;
        if (!fm1_seq_import_movy1(sb, (const char *)text, nt)) return 17;
        n1 = fm1_seq_export_movy1(sa, e1, 131072);
        n2 = fm1_seq_export_movy1(sb, e2, 131072);
        if (n1 >= 131072 || n1 != n2 || memcmp(e1, e2, n1)) return 18;
        fm1_seq_import_t diag;
        fm1_seq_import_begin(&diag, sb);
        for (size_t off = 0; off < nt; off += 7) {
            size_t count = nt - off < 7 ? nt - off : 7;
            if (!fm1_seq_import_feed(&diag, (const char *)text + off, count)) return 41;
        }
        if (!fm1_seq_import_end(&diag) || diag.loss_flags != (unsigned)atoi(argv[4])) return 42;
    } else if (ok || report.code == FM1_STATE_OK) return 19;
    if (lunar_content_load_set_checked(bin, (uint32_t)nb, sa, &report) !=
        (atoi(argv[3]) && !atoi(argv[4]))) return 43;
    if (memcmp(snapshot, live, bytes)) return 44;
    if (lunar_content_load_set(NULL, 32, sa, &report) || report.code != FM1_STATE_BAD) return 20;
    if (lunar_content_load_set(bin, FM1_STATE_BIN_MAX + 1, sa, &report) ||
        report.code != FM1_STATE_TOO_BIG) return 21;
    if (lunar_content_load_set(bin, (uint32_t)nb, NULL, &report)) return 22;
    if (lunar_content_load_set(bin, (uint32_t)nb, sa, NULL)) return 23;
    /* Startup ordering: stage the real eight-track size, then reclaim it for
     * the measured Shapes-12 allocation. This is allocator evidence, not a
     * complete engine/project startup or target ABI footprint assertion. */
    {
        unsigned char *raw = malloc(216064 + 15);
        void *pool_mem = (void *)(((uintptr_t)raw + 15u) & ~(uintptr_t)15u);
        lunar_instance_pool_t pool;
        fm1_seq_limits_t boot_lim;
        if (!raw || lunar_instance_pool_init(&pool, pool_mem, 216064)) return 33;
        fm1_seq_limits_default(&boot_lim, 8);
        size_t boot_bytes = fm1_seq_size(&boot_lim);
        if (boot_bytes > sizeof app->seq_mem) return 34;
        void *staging = lunar_instance_pool_alloc(&pool, boot_bytes);
        fm1_seq_t *boot_seq = staging ? fm1_seq_create(staging, &boot_lim, 44118) : NULL;
        if (!boot_seq || pool.live_allocations != 1) return 35;
        if (lunar_content_load_set(bin, (uint32_t)nb, boot_seq, &report) != atoi(argv[3])) return 36;
        if (lunar_instance_pool_free(&pool, staging) || pool.live_allocations || pool.live_bytes) return 37;
        void *shapes_budget = lunar_instance_pool_alloc(&pool, 206904);
        if (!shapes_budget) return 38;
        if (lunar_instance_pool_alloc(&pool, boot_bytes)) return 39;
        if (lunar_instance_pool_free(&pool, shapes_budget) || pool.live_allocations || pool.live_bytes) return 40;
        free(raw);
    }
    free(app); free(app_before); free(bin); free(text); free(a); free(b); free(live); free(snapshot); free(e1); free(e2);
    return 0;
}
'''


@pytest.mark.parametrize('case', range(16))
@pytest.mark.parametrize('opt', ['-Os', '-Oz'])
def test_native_packed_set(tmp_path, case, opt):
    text = (ROOT / 'tests/fixtures/state/1.0/orbit.set.movy1').read_bytes()
    if case == 1:
        # A recognized note-list line crosses many 64-byte decoder fragments.
        text += b'cl 2 0 256 0 ' + b';'.join(
            f'{i * 24}:12:{48 + i % 24}:100:{i}'.encode() for i in range(256)) + b'\n'
    elif case == 2:
        text += b'future-field ignored-by-the-established-importer\n'
    elif case == 3:
        # Track beyond the destination's capacity retains the core's truncation semantics.
        text += b'tk 15 0 0\ncl 15 0 16 0 0:12:60:100:0\ncp 15 0 1 1 0 0\n'
    elif case == 8:
        text += b'sg ' + b'0 ' * 65 + b'\n'
    elif case == 9:
        text += b'au 0 0 64 ' + b'x' * 80 + b'\n'
    elif case == 10:
        text += b'cl 2 0 256 0 6144:12:60:100:256\n'
    elif case == 11:
        text += b'cl 2 0 16 0 0:65536:60:100:0\n'
    elif case == 12:
        text += b'cl 2 0 16 0 ' + b';'.join([b'0:12:60:100:0'] * 513) + b'\n'
    elif case == 13:
        text += b'lk 2 0 ' + b';'.join(f'{i // 256}:{i % 256}:64'.encode() for i in range(800)) + b'\n'
    elif case == 14:
        text += b'tg 2 0 256:-1:50:1:1:0\n'
    elif case == 15:
        text += b'rt 0 1 99\n'
    loss = {2: 4, 3: 1, 8: 8, 9: 2, 10: 1, 11: 1, 12: 8, 13: 8, 14: 9, 15: 8}.get(case, 0)
    valid = case not in (4, 5, 6, 7)
    movy = tmp_path / 'set.movy1'
    movy.write_bytes(text)
    packed = tmp_path / 'set.lunarb'
    tool = os.environ['FM1_STATE_TOOL']
    subprocess.run([tool, 'from-movy1', str(movy), '-o', str(packed)],
                   check=True, capture_output=True)
    payload = packed.read_bytes()
    if case == 4:
        payload = payload[:-1]
    elif case == 5:
        payload = bytearray(payload)
        payload[-1] ^= 1
    elif case == 6:
        payload = (ROOT / 'tests/fixtures/state/1.0/first-orbit.lunarb').read_bytes()
    elif case == 7:
        payload = b'not a Lunar container'
    packed.write_bytes(payload)
    source = tmp_path / 'probe.c'
    source.write_text(HARNESS)
    sources = [ROOT / 'firmware/native/content_set.c', ROOT / 'firmware/native/instance_pool.c',
               ROOT / 'firmware/third_party/tlsf/tlsf.c', ROOT / 'sim/web/src/fm1_app.c',
               source]
    sources += sorted(p for p in (ROOT / 'engines/mod').rglob('*.c')
                      if p.name != 'mp_tool.c')
    sources += [ROOT / 'engines/seq' / f'{name}.c' for name in
                ('seq_clip', 'seq_engine', 'seq_cmd', 'seq_persist', 'seq_capture', 'seq_host', 'mfx_host')]
    sources += [ROOT / 'engines/state' / f'{name}.c' for name in
                ('state_bin', 'state_names', 'state_movy1', 'fm1_num', 'fm1_deflate')]
    includes = [ROOT / 'firmware/native', ROOT / 'firmware/third_party/tlsf', ROOT / 'engines/include', ROOT / 'engines/state', ROOT / 'sim/web/src', ROOT / 'engines/mod', ROOT / 'engines/host', tmp_path / 'gen']
    import sys
    sys.path.insert(0, str(ROOT / 'tools/native'))
    from module_selection import resolve_modules
    resolve_modules(ROOT, tmp_path, 'trio')
    inc = [arg for p in includes for arg in ('-I', str(p))]
    executable = tmp_path / 'probe'
    subprocess.run(['cc', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                    '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                    '-fno-pie', '-no-pie', *inc, *map(str, sources),
                    '-Wl,--gc-sections', '-lm', '-o', str(executable)],
                   check=True)
    subprocess.run([str(executable), str(packed), str(movy), str(int(valid)), str(loss)],
                   check=True, capture_output=True)
    tc = Path(os.environ['FM1_NATIVE_TOOLCHAIN'])
    subprocess.run([str(tc / 'common/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
                    '-mfprev1', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                    '-ffreestanding', '-fno-builtin', *inc,
                    '-isystem', str(tc / 'pi32v2/include'), '-c',
                    str(ROOT / 'firmware/native/content_set.c'),
                    '-o', str(tmp_path / 'content_set.o')], check=True, capture_output=True)
