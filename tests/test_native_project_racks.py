"""Compare native rack planning with actual selected module construction."""
import os
from pathlib import Path
import subprocess

import pytest

from tools.native.module_selection import resolve_modules

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "project_mod.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char bytes[98304];
static size_t length;
static size_t sound_size(const fm1_host_t *h) { (void)h; return 16; }
static const fm1_engine_t sound = { .id = "trio", .kind = FM1_KIND_SOUND,
    .instance_size = sound_size };
static const fm1_engine_t *const engines[] = { &sound };
static void put(void *ctx, const char *s, size_t n) {
    (void)ctx; if (n > sizeof bytes - length) abort();
    memcpy(bytes + length, s, n); length += n;
}
int main(int argc, char **argv) {
    unsigned k = argc == 2 ? (unsigned)atoi(argv[1]) : 99;
    fm1_host_t host = { .api_version = FM1_ENGINE_API_VERSION,
        .sample_rate = 44118, .max_frames = 64 };
    fm1_state_names_t names = { .engines = engines, .n_engines = 1,
        .kinds = fm1_mod_kinds, .n_kinds = fm1_mod_kind_count };
    if (fm1_mod_kind_count != 16 || k >= fm1_mod_kind_count) return 1;
    for (unsigned mode = 0; mode < 8; ++mode) {
        const unsigned count = mode == 1 || mode == 2 ? 8 : 1;
        const uint8_t version[3] = {0, 1, 0};
        fm1_state_report_t rep;
        fm1_rec_t r = {0};
        lunar_project_units_t plan, before;
        void *writer = calloc(1, fm1_state_bin_writer_size());
        void *memory = malloc(fm1_mod_size() + 15);
        fm1_mod_t *mod;
        fm1_state_writer_t *w;
        int actual = 1, planned;
        if (!writer || !memory) return 2;
        mod = fm1_mod_create((void *)(((uintptr_t)memory + 15) & ~(uintptr_t)15), &host, 123);
        if (!mod) return 3;
        length = 0; fm1_state_report_init(&rep);
        w = fm1_state_bin_writer(writer, 0, FM1_STATE_WRITER_DESKTOP,
            version, put, NULL, &rep);
        if (!w) return 4;
        r.type = FM1_REC_HEAD; r.u.head.kind = FM1_STATE_PROJECT; r.u.head.major = 1;
        if (!fm1_state_bin_write(w, &r)) return 5;
        memset(&r, 0, sizeof r); r.type = FM1_REC_UNIT; r.role = FM1_ROLE_SOUND;
        strcpy(r.u.unit.id, "trio"); if (!fm1_state_bin_write(w, &r)) return 6;
        r.type = FM1_REC_MOD; if (!fm1_state_bin_write(w, &r)) return 7;
        r.type = FM1_REC_SEED; r.u.seed = 123; if (!fm1_state_bin_write(w, &r)) return 8;
        for (unsigned pos = 0; pos < count; ++pos) {
            unsigned kind = mode == 2 ? (k + pos) % fm1_mod_kind_count : k;
            memset(&r, 0, sizeof r); r.type = FM1_REC_MODULE; r.role = FM1_ROLE_MODULE;
            r.slot = (uint8_t)pos;
            strcpy(r.u.unit.id, fm1_mod_kinds[kind]->id);
            if (!fm1_state_bin_write(w, &r)) return 9;
            if (actual && fm1_mod_set_kind(mod, pos, (int)kind) < 0) actual = 0;
        }
        if (mode >= 3 && mode <= 6) {
            memset(&r, 0, sizeof r); r.type = FM1_REC_CABLE;
            r.u.cable.s.src = mode == 4 ? FM1_MOD_SRC_MODULE + 8 : FM1_MOD_SRC_VEL;
            r.u.cable.s.via = FM1_MOD_NONE;
            r.u.cable.s.dst_unit = FM1_MOD_HOST;
            r.u.cable.s.dst = mode == 5 || mode == 6 ? 99 : FM1_MOD_HOST_PITCH_UID;
            r.u.cable.s.flags = mode == 6 ? 0 : FM1_MOD_SLOT_ON;
            r.u.cable.s.amount = 8192;
            if (!fm1_state_bin_write(w, &r)) return 17;
        }
        if (mode == 7) {
            static const uint8_t bad_data = 0;
            memset(&r, 0, sizeof r); r.type = FM1_REC_DATA;
            r.piece = FM1_REC_FIRST | FM1_REC_LAST;
            r.u.data.version = 255; r.u.data.n = 1; r.u.data.b = &bad_data;
            if (!fm1_state_bin_write(w, &r)) return 18;
        }
        r.type = FM1_REC_END; if (!fm1_state_bin_write(w, &r)) return 10;
        memset(&plan, 0x73, sizeof plan); memcpy(&before, &plan, sizeof plan);
        planned = lunar_project_units_plan(bytes, (uint32_t)length,
            &names, &host, &plan, &rep);
        if (planned != actual) {
            fprintf(stderr, "%s mode%u planned%d actual%d: %s\n",
                fm1_mod_kinds[k]->id, mode, planned, actual, rep.what); return 11;
        }
        if (!planned && (rep.code != FM1_STATE_RAM || memcmp(&plan, &before, sizeof plan))) return 12;
        if (planned) {
            if (plan.modules_given != (1u << count) - 1u) return 13;
            for (unsigned pos = 0; pos < count; ++pos) {
                int kind = fm1_mod_kind_at(mod, pos);
                if (kind < 0 || plan.module[pos] != fm1_mod_kinds[kind]) return 14;
            }
        }
        fm1_mod_destroy(mod);
        mod = lunar_project_mod_stage(bytes, (uint32_t)length, &names, &host,
            (void *)(((uintptr_t)memory + 15) & ~(uintptr_t)15), fm1_mod_size(), &rep);
        if (!!mod != (actual && mode != 4 && mode != 5 && mode != 7)) {
            fprintf(stderr, "stage %s mode%u: %u %s\n", fm1_mod_kinds[k]->id,
                mode, rep.code, rep.what); return 15;
        }
        if (!mod && rep.code == FM1_STATE_OK) return 19;
        if (mod) fm1_mod_destroy(mod);
        if (lunar_project_mod_stage(bytes, (uint32_t)length, &names, &host,
            memory, 1, &rep) || rep.code == FM1_STATE_OK) return 16;
        free(memory); free(writer);
    }
    return 0;
}
'''


@pytest.fixture(scope='session')
def rack_probe(tmp_path_factory):
    probes = {}

    def build(opt):
        if opt in probes:
            return probes[opt]
        tmp = tmp_path_factory.mktemp('native-racks-' + opt[1:])
        resolve_modules(ROOT, tmp / 'catalogue', 'all')
        source = tmp / 'probe.c'
        source.write_text(HARNESS)
        sources = [ROOT / 'firmware/native/project_units.c', ROOT / 'firmware/native/project_mod.c', source]
        sources += [ROOT / 'engines/state' / (s + '.c') for s in
                    ('state_bin', 'state_names', 'state_movy1', 'fm1_num', 'fm1_deflate', 'state_mod')]
        # Production runtime and every registered kind, including its primitives.
        mod = ROOT / 'engines/mod'
        sources += [p for p in sorted(mod.glob('mp_*.c')) if p.name != 'mp_tool.c']
        sources += [mod / (s + '.c') for s in
                    ('mod_core', 'mod_plan', 'mod_registry', 'mod_curves', 'mod_mi', 'mod_mi_tables')]
        sources += sorted((mod / 'kinds').glob('*.c'))
        inc = [arg for path in (ROOT / 'firmware/native', ROOT / 'engines/include',
                               ROOT / 'engines/state', mod, tmp / 'catalogue/gen')
               for arg in ('-I', str(path))]
        exe = tmp / 'probe'
        subprocess.run(['cc', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                        '-ffp-contract=off', '-ffunction-sections', '-fdata-sections',
                        '-fsanitize=address,undefined', '-fno-pie', '-no-pie', *inc,
                        *map(str, sources), '-Wl,--gc-sections', '-lm', '-o', str(exe)], check=True)
        tc = Path(os.environ['FM1_NATIVE_TOOLCHAIN'])
        subprocess.run([str(tc / 'common/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
                        '-mfprev1', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                        '-ffreestanding', '-fno-builtin', *inc, '-isystem', str(tc / 'pi32v2/include'),
                        '-c', str(ROOT / 'firmware/native/project_mod.c'),
                        '-o', str(tmp / 'project_mod.o')], check=True)
        probes[opt] = exe
        return exe

    return build


@pytest.mark.parametrize('kind', range(16))
@pytest.mark.parametrize('opt', ['-Os', '-Oz'])
def test_native_project_racks(kind, opt, rack_probe):
    subprocess.run([str(rack_probe(opt)), str(kind)], check=True)
