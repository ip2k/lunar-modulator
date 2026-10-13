"""Bounded project unit planning uses the real codec and preserves failed output."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "project_units.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned calls;
static size_t sized(const fm1_host_t *host) {
    if (host->sample_rate != 44118) abort();
    ++calls; return 1248;
}
static size_t zero(const fm1_host_t *host) { (void)host; return 0; }
static const fm1_param_t params[] = {
    { .uid = 10, .type = FM1_PARAM_FLOAT, .min = 0, .max = 1 },
    { .uid = 11, .type = FM1_PARAM_ENUM, .min = 1, .max = 3 },
    { .uid = 12, .type = FM1_PARAM_ENUM, .min = 0, .max = 3, .flags = FM1_PARAM_FOCUS },
    { .uid = 13, .type = FM1_PARAM_FLOAT, .min = 0, .max = 1, .flags = FM1_PARAM_PER_FOCUS }
};
static fm1_engine_t sound = { .id = "trio", .kind = FM1_KIND_SOUND, .instance_size = sized,
    .params = params, .n_params = 4 };
static const fm1_engine_t fx = { .id = "plate", .kind = FM1_KIND_AUDIO_FX, .instance_size = sized };
static const fm1_midi_fx_t midi = { .engine = { .id = "arp", .kind = FM1_KIND_MIDI_FX, .instance_size = sized } };
static const fm1_mod_kind_t mod = { .id = "lfo", .params = params, .n_params = 4 };
static const fm1_engine_t *const engines[] = { &sound, &fx };
static const fm1_midi_fx_t *const mfx[] = { &midi };
static const fm1_mod_kind_t *const mods[] = { &mod };
static unsigned char bytes[98304];
static size_t length;
static int mod_started;
static void put(void *ctx, const char *data, size_t n) {
    (void)ctx; if (n > sizeof bytes - length) abort();
    memcpy(bytes + length, data, n); length += n;
}
static void emit(fm1_state_writer_t *w, unsigned role, unsigned snd, unsigned slot,
                 const char *id, int module) {
    fm1_rec_t r = {0}; r.type = module ? FM1_REC_MODULE : FM1_REC_UNIT;
    if (module && !mod_started) {
        fm1_rec_t begin = { .type = FM1_REC_MOD };
        if (!fm1_state_bin_write(w, &begin)) abort();
        begin.type = FM1_REC_SEED; begin.u.seed = 1;
        if (!fm1_state_bin_write(w, &begin)) abort();
        mod_started = 1;
    }
    r.role = role; r.sound = snd; r.slot = slot;
    strncpy(r.u.unit.id, id, sizeof r.u.unit.id - 1);
    if (!fm1_state_bin_write(w, &r)) abort();
}
int main(int argc, char **argv) {
    int c = argc == 2 ? atoi(argv[1]) : -1, expected = 0, ok;
    fm1_state_names_t names = { .engines = engines, .n_engines = 2,
        .mfx = mfx, .n_mfx = 1, .kinds = mods, .n_kinds = 1 };
    fm1_host_t host = { .sample_rate = 44118 };
    fm1_state_report_t rep; fm1_rec_t r = {0};
    lunar_project_units_t plan, before;
    void *mem = calloc(1, fm1_state_bin_writer_size());
    const uint8_t version[3] = {0, 1, 0};
    fm1_state_writer_t *w;
    if (!mem || c < 0 || c >= 32) return 1;
    fm1_state_report_init(&rep);
    w = fm1_state_bin_writer(mem, c == 15 ? FM1_STATE_BIN_DEFLATE : 0,
                              FM1_STATE_WRITER_DESKTOP, version, put, NULL, &rep);
    if (!w) return 2;
    r.type = FM1_REC_HEAD; r.u.head.kind = c == 1 ? FM1_STATE_SET : FM1_STATE_PROJECT;
    r.u.head.major = 1;
    if (!fm1_state_bin_write(w, &r)) return 3;
    if (c == 0 || c == 15) {
        for (unsigned i = 0; i < 4; ++i) {
            emit(w, FM1_ROLE_SOUND, i, 0, "trio", 0);
            for (unsigned j = 0; j < 2; ++j) emit(w, FM1_ROLE_INSERT, i, j, "plate", 0);
            emit(w, FM1_ROLE_MFX, i, 0, "arp", 0);
        }
        for (unsigned i = 0; i < 2; ++i) emit(w, FM1_ROLE_MASTER, 0, i, "plate", 0);
        for (unsigned i = 0; i < 8; ++i) emit(w, 0, 0, i, "lfo", 1);
        expected = 1;
    } else if (c == 2) emit(w, FM1_ROLE_SOUND, 0, 0, "absent", 0);
    else if (c == 3) emit(w, FM1_ROLE_SOUND, 0, 0, "plate", 0);
    else if (c == 4) emit(w, FM1_ROLE_MFX, 3, 1, "arp", 0);
    else if (c == 5) {
        emit(w, FM1_ROLE_SOUND, 0, 0, "trio", 0);
        emit(w, FM1_ROLE_SOUND, 0, 0, "trio", 0);
    } else if (c == 6) emit(w, 0, 0, 0, "absent", 1);
    else if (c == 7) {
        emit(w, 0, 0, 0, "lfo", 1); emit(w, 0, 0, 0, "lfo", 1);
    } else if (c == 8) {
        emit(w, FM1_ROLE_SOUND, 0, 0, "trio", 0);
        emit(w, FM1_ROLE_SOUND, 3, 0, "", 0); emit(w, 0, 0, 7, "lfo", 1);
        expected = 1;
    } else if (c >= 9 && c <= 14) emit(w, FM1_ROLE_SOUND, 0, 0, "trio", 0);
    else if (c >= 16) {
        float value = 0.5f;
        emit(w, FM1_ROLE_SOUND, 0, 0, "trio", 0);
        memset(&r, 0, sizeof r); r.type = FM1_REC_PARAM; r.role = FM1_ROLE_SOUND;
        r.u.param.uid = 10; r.u.param.focus = FM1_FOCUS_NONE;
        if (c == 16) r.u.param.uid = 99;
        if (c == 17) value = -0.01f;
        if (c == 18) {
            emit(w, FM1_ROLE_SOUND, 3, 0, "", 0); r.sound = 3;
        }
        if (c == 19) value = 1.01f;
        if (c == 20) { r.u.param.uid = 11; value = 4; }
        if (c == 21) { r.u.param.uid = 11; value = 1.5f; }
        if (c == 23) r.u.param.focus = 0;
        if (c >= 24 && c <= 26) {
            r.u.param.uid = 13;
            r.u.param.focus = c == 24 ? FM1_FOCUS_NONE : c == 25 ? 4 : 3;
        }
        if (c == 28) value = 1;
        if (c == 29 || c == 30) {
            emit(w, 0, 0, 0, "lfo", 1); r.role = FM1_ROLE_MODULE;
            if (c == 29) r.u.param.uid = 99;
        }
        if (c == 31) { r.u.param.uid = 11; value = 3; }
        memcpy(&r.u.param.bits, &value, sizeof value);
        if (c == 22 || c == 27) {
            r.u.param.vtype = FM1_VAL_INDEX; r.u.param.bits = 2;
            if (c == 27) r.u.param.uid = 11;
        }
        if (!fm1_state_bin_write(w, &r)) return 17;
        expected = c == 26 || c == 27 || c == 28 || c == 30 || c == 31;
    }
    r.type = FM1_REC_END;
    if (!fm1_state_bin_write(w, &r)) return 4;
    free(mem);
    if (c == 9) bytes[length - 1] ^= 1;
    if (c == 10) --length;
    if (c == 11) sound.instance_size = zero;
    if (c == 12) sound.instance_size = NULL;
    if (c == 13) names.n_engines = 0;
    memset(&plan, 0x73, sizeof plan); memcpy(&before, &plan, sizeof plan);
    ok = lunar_project_units_plan(c == 14 ? NULL : bytes, (uint32_t)length,
                                  &names, &host, &plan, &rep);
    if (ok != expected) { fprintf(stderr, "case %d ok=%d code=%u %s\n", c, ok, rep.code, rep.what); return 5; }
    if (!ok) {
        if (rep.code == FM1_STATE_OK || memcmp(&plan, &before, sizeof plan)) return 6;
        if ((c < 11 || c >= 16) && calls) return 7;
    } else if (c == 8) {
        if (plan.given != ((1u << 3) | 1) || plan.modules_given != 128 || calls != 1) return 8;
        if (plan.module[7] != &mod) return 15;
        if (plan.engine[0] != &sound || plan.size[0] != 1248) return 16;
        for (unsigned i = 1; i < LUNAR_PROJECT_UNITS; ++i)
            if (plan.engine[i] || plan.size[i]) return 9;
    } else if (c >= 16) {
        if (plan.given != 1 || plan.engine[0] != &sound || plan.size[0] != 1248 || calls != 1) return 18;
        if (c == 30 && plan.module[0] != &mod) return 19;
    } else {
        if (plan.given != (1u << 18) - 1 || plan.modules_given != 255 || calls != 18) return 10;
        for (unsigned i = 0; i < LUNAR_PROJECT_UNITS; ++i) {
            const fm1_engine_t *e = i < 4 ? &sound : i < 14 ? &fx : &midi.engine;
            if (plan.engine[i] != e || plan.size[i] != 1248) return 11;
        }
        for (unsigned i = 0; i < 8; ++i) if (plan.module[i] != &mod) return 12;
    }
    memcpy(&before, &plan, sizeof plan);
    if (lunar_project_units_plan(bytes, FM1_STATE_BIN_MAX + 1, &names, &host, &plan, &rep) ||
        rep.code != FM1_STATE_TOO_BIG || memcmp(&plan, &before, sizeof plan)) return 13;
    if (lunar_project_units_plan(bytes, (uint32_t)length, NULL, &host, &plan, &rep) ||
        lunar_project_units_plan(bytes, (uint32_t)length, &names, NULL, &plan, &rep) ||
        lunar_project_units_plan(bytes, (uint32_t)length, &names, &host, NULL, &rep) ||
        lunar_project_units_plan(bytes, (uint32_t)length, &names, &host, &plan, NULL) ||
        memcmp(&plan, &before, sizeof plan)) return 14;
    return 0;
}
'''


@pytest.fixture(scope='session')
def project_probe(tmp_path_factory):
    probes = {}

    def build(opt):
        if opt in probes:
            return probes[opt]
        tmp = tmp_path_factory.mktemp('native-project-' + opt[1:])
        source = tmp / 'probe.c'
        source.write_text(HARNESS)
        sources = [ROOT / 'firmware/native/project_units.c', source]
        sources += [ROOT / 'engines/state' / (name + '.c') for name in
                    ('state_bin', 'state_names', 'state_movy1', 'fm1_num', 'fm1_deflate')]
        inc = [arg for path in ('firmware/native', 'engines/include', 'engines/state')
               for arg in ('-I', str(ROOT / path))]
        exe = tmp / 'probe'
        subprocess.run(['cc', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                        '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                        '-fno-pie', '-no-pie', *inc, *map(str, sources),
                        '-Wl,--gc-sections', '-lm', '-o', str(exe)], check=True)
        tc = Path(os.environ['FM1_NATIVE_TOOLCHAIN'])
        subprocess.run([str(tc / 'common/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
                        '-mfprev1', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                        '-ffreestanding', '-fno-builtin', *inc, '-isystem', str(tc / 'pi32v2/include'),
                        '-c', str(ROOT / 'firmware/native/project_units.c'),
                        '-o', str(tmp / 'project_units.o')], check=True)
        size_check = tmp / 'size_check.c'
        size_check.write_text('#include "project_units.h"\n'
                              'typedef char plan_size[(sizeof(lunar_project_units_t) == 184) ? 1 : -1];\n')
        subprocess.run([str(tc / 'common/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
                        '-mfprev1', '-std=c99', opt, *inc, '-isystem', str(tc / 'pi32v2/include'),
                        '-c', str(size_check), '-o', str(tmp / 'size_check.o')], check=True)
        probes[opt] = exe
        return exe

    return build


@pytest.mark.parametrize('case', range(32))
@pytest.mark.parametrize('opt', ['-Os', '-Oz'])
def test_native_project_units(case, opt, project_probe):
    subprocess.run([str(project_probe(opt)), str(case)], check=True)
