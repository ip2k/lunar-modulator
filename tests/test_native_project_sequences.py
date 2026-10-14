"""Project sequence staging preserves live state and validates selected bindings."""
import os
from pathlib import Path
import subprocess

import pytest
from tests.native_test_toolchain import configured_target_toolchain
from tests.native_test_flags import native_host_flags

from tools.native.module_selection import resolve_modules

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "project_seq.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char binary[4096];
static size_t length;
static size_t sized(const fm1_host_t *h) { (void)h; return 16; }
static fm1_param_t params[] = {{.name="Decay", .uid=12}};
static fm1_engine_t engine = {.id="trio", .kind=FM1_KIND_SOUND,
    .params=params, .n_params=1, .instance_size=sized};
static const fm1_engine_t *const engines[] = {&engine};
static void put(void *ctx, const char *s, size_t n) {
    (void)ctx; if (n > sizeof binary-length) abort();
    memcpy(binary+length,s,n); length+=n;
}
int main(int argc, char **argv) {
    unsigned test=argc==2?(unsigned)atoi(argv[1]):99;
    fm1_host_t host={.api_version=FM1_ENGINE_API_VERSION,.sample_rate=44118,.max_frames=64};
    fm1_state_names_t names={.engines=engines,.n_engines=1};
    fm1_seq_limits_t lim;
    fm1_state_report_t report;
    fm1_rec_t r={0};
    const uint8_t version[3]={0,1,0};
    char text[512], staged[4096], reference[4096];
    unsigned has_set=73;
    int expected=test==0 || test==1 || test==6 || test==9 || test==11 || test==14;
    void *writer=calloc(1,fm1_state_bin_writer_size());
    fm1_seq_limits_default(&lim,4);
    size_t n=fm1_seq_size(&lim);
    void *scratch=calloc(1,n), *oracle=calloc(1,n), *live=calloc(1,n), *before=malloc(n);
    if (!writer||!scratch||!oracle||!live||!before||test>15) return 1;
    fm1_seq_t *seq=fm1_seq_create(scratch,&lim,44118);
    fm1_seq_t *ref=fm1_seq_create(oracle,&lim,44118);
    if (!seq||!ref||!fm1_seq_create(live,&lim,44118)) return 2;
    memcpy(before,live,n);
    fm1_state_report_init(&report);
    fm1_state_writer_t *w=fm1_state_bin_writer(writer,0,FM1_STATE_WRITER_DESKTOP,version,put,NULL,&report);
    r.type=FM1_REC_HEAD;r.u.head.kind=FM1_STATE_PROJECT;r.u.head.major=1;
    if (!w||!fm1_state_bin_write(w,&r)) return 3;
    memset(&r,0,sizeof r);r.type=FM1_REC_UNIT;r.role=FM1_ROLE_SOUND;strcpy(r.u.unit.id,"trio");
    if (!fm1_state_bin_write(w,&r)) return 4;
    const char *route=test==2?"rt 0 1 1":test==6?"rt 0 0 16":test==7?"rt 0 0 0":"rt 0 1 0";
    const char *label=test==3?"unknown":test==9?"synth:dEcAy":test==11?"prefix:Decay":"synth:Decay";
    snprintf(text,sizeof text,"movy1\nbpm 12000\n%s\nau 0 0 64 %s\ncl 0 0 16 0 0:12:60:100:0\nlk 0 0 0:0:64\n",route,label);
    if (test==4) params[0].flags=FM1_PARAM_NOLOCK;
    if (test==5) strcat(text,"bpm 999999\n");
    if (test==8) strcat(text,"future-field unsupported\n");
    if (test==10) strcpy(text,"no-tag\n");
    if (test==12) engine.params=NULL;
    if (test==13) params[0].uid=0;
    if (test==15) strcat(text,"rt 0 1 99\n");
    if (test!=1) {
        for (const char *line=text;*line;) {
            const char *end=strchr(line,'\n');if (!end) return 5;
            memset(&r,0,sizeof r);r.type=FM1_REC_LINE;r.piece=FM1_REC_FIRST|FM1_REC_LAST;
            r.u.line.which=FM1_LINES_SET;r.u.line.s=line;r.u.line.n=(uint16_t)(end-line);
            if (!fm1_state_bin_write(w,&r)) return 6;
            line=end+1;
        }
    }
    r.type=FM1_REC_END;if (!fm1_state_bin_write(w,&r)) return 7;
    if (test==14) { /* no output pointer must refuse before scratch mutation */
        memcpy(before,scratch,n);
        if (lunar_project_seq_stage(binary,(uint32_t)length,&names,&host,seq,NULL,&report)||
            report.code==FM1_STATE_OK||memcmp(before,scratch,n)) return 8;
        memcpy(before,live,n);
    }
    int ok=lunar_project_seq_stage(binary,(uint32_t)length,&names,&host,seq,&has_set,&report);
    if (ok!=expected || memcmp(before,live,n) ||
        (!ok && (has_set!=73 || report.code==FM1_STATE_OK))) {
        fprintf(stderr,"case%u ok%d expected%d: %u %s\n",test,ok,expected,report.code,report.what);return 9;
    }
    if (ok) {
        if (has_set!=(test!=1) || report.code!=FM1_STATE_OK) return 10;
        if (test!=1) {
            if (!fm1_seq_import_movy1(ref,text,strlen(text))) return 11;
            size_t a=fm1_seq_export_movy1(seq,staged,sizeof staged),b=fm1_seq_export_movy1(ref,reference,sizeof reference);
            if (a>=sizeof staged||a!=b||memcmp(staged,reference,a)) return 12;
        } else if (memcmp(scratch,oracle,n)) return 13;
    }
    free(writer);free(scratch);free(oracle);free(live);free(before);return 0;
}
'''


@pytest.fixture(scope='session')
def sequence_probe(tmp_path_factory):
    probes = {}

    def build(opt):
        if opt in probes:
            return probes[opt]
        tmp = tmp_path_factory.mktemp('native-project-seq-' + opt[1:])
        resolve_modules(ROOT, tmp / 'catalogue', 'trio')
        source = tmp / 'probe.c'
        source.write_text(HARNESS)
        sources = [ROOT / 'firmware/native/project_units.c', ROOT / 'firmware/native/project_seq.c',
                   ROOT / 'firmware/native/content_set.c', source]
        sources += [ROOT / 'engines/state' / (s + '.c') for s in
                    ('state_bin', 'state_names', 'state_movy1', 'fm1_num', 'fm1_deflate')]
        sources += [ROOT / 'engines/seq' / (s + '.c') for s in
                    ('seq_clip', 'seq_engine', 'seq_cmd', 'seq_persist', 'seq_capture', 'seq_host')]
        inc = [arg for path in (ROOT / 'firmware/native', ROOT / 'engines/include',
                               ROOT / 'engines/state', ROOT / 'sim/web/src', tmp / 'catalogue/gen')
               for arg in ('-I', str(path))]
        exe = tmp / 'probe'
        subprocess.run(['cc', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                        '-ffunction-sections', '-fdata-sections', *native_host_flags(), '-Wl,--gc-sections',
                        *inc, *map(str, sources), '-lm', '-o', str(exe)], check=True)
        probes[opt] = exe
        return exe
    return build


@pytest.mark.parametrize('opt', ['-Os', '-Oz'])
def test_native_project_sequences_target_compile(opt, tmp_path):
    tc = configured_target_toolchain()
    catalogue = tmp_path / 'catalogue'
    resolve_modules(ROOT, catalogue, 'trio')
    inc = ['-I' + str(ROOT / p) for p in ('firmware/native', 'engines/include', 'engines/state')]
    inc += ['-I', str(catalogue / 'gen')]
    subprocess.run([str(tc / 'common/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
                    '-mfprev1', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                    '-ffreestanding', '-fno-builtin', *inc,
                    '-isystem', str(tc / 'pi32v2/include'), '-c', str(ROOT / 'firmware/native/project_seq.c'),
                    '-o', str(tmp_path / 'target.o')], check=True, capture_output=True)


@pytest.mark.parametrize('case', range(16))
@pytest.mark.parametrize('opt', ['-Os', '-Oz'])
def test_native_project_sequence(case, opt, sequence_probe):
    subprocess.run([str(sequence_probe(opt)), str(case)], check=True)
