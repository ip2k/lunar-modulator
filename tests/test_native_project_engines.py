"""Owned candidate construction, reverse cleanup and live allocation stability."""
import os
from pathlib import Path
import subprocess
import pytest

from tests.native_test_flags import native_host_link_flags, native_no_pie_flags
from tests.native_test_toolchain import configured_target_toolchain
from tools.native.module_selection import resolve_modules

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "project_engines.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static unsigned char arena[216064] __attribute__((aligned(16)));
static unsigned char binary[4096];
static size_t length, want;
static unsigned attempts, destroyed, fail_at;
static void *handles[4];
typedef struct { float focus, pad[2], ordinary; } state_t;
static fm1_param_t params[]={
    {.name="Pad",.uid=1,.type=FM1_PARAM_ENUM,.min=1,.max=2,.def=1,.flags=FM1_PARAM_FOCUS},
    {.name="Decay",.uid=2,.min=0,.max=1,.def=0.5f,.flags=FM1_PARAM_PER_FOCUS},
    {.name="Gain",.uid=3,.min=0,.max=1,.def=0.5f}};
static void set_param(void *self,uint16_t i,float value) {
    state_t *s=self;assert(i<3);
    if (i==0) {assert(value==1||value==2);s->focus=value;}
    else if (i==1) s->pad[(unsigned)s->focus-1]=value;
    else s->ordinary=value;
}
static float get_param(const void *self,uint16_t i,uint8_t focus) {
    const state_t *s=self;
    return i==0?s->focus:i==2?s->ordinary:s->pad[focus<2?focus:(unsigned)s->focus-1];
}
static size_t sized(const fm1_host_t *host) { (void)host; return want; }
static void *create(void *memory, const fm1_host_t *host) {
    unsigned i=attempts++; (void)host;
    assert(i<4);
    if (i==fail_at) return NULL;
    handles[i]=(unsigned char *)memory+16;
    memset(handles[i],0x72,want-16);
    *(state_t *)handles[i]=(state_t){1,{0.5f,0.5f},0.5f};
    return handles[i];
}
static void destroy(void *self) {
    unsigned successes=attempts-(fail_at<attempts);
    assert(destroyed<successes && self==handles[successes-1-destroyed]);
    destroyed++;
}
static fm1_engine_t engine={.magic=FM1_ENGINE_MAGIC,.api_version=FM1_ENGINE_API_VERSION,
    .id="trio",.kind=FM1_KIND_SOUND,.instance_size=sized,.create=create,.destroy=destroy,
    .params=params,.n_params=3,.set_param=set_param,.get_param=get_param};
static const fm1_engine_t *const engines[]={&engine};
static void put(void *ctx,const char *s,size_t n) {
    (void)ctx;assert(n<=sizeof binary-length);memcpy(binary+length,s,n);length+=n;
}
int main(int argc,char **argv) {
    assert(argc==2);unsigned shard=(unsigned)atoi(argv[1]);assert(shard<16);
    static const size_t sizes[]={1248,5984,7648,19872};
    unsigned count=shard%4+1;
    fm1_host_t host={.api_version=FM1_ENGINE_API_VERSION,.sample_rate=44118,.max_frames=64};
    fm1_state_names_t names={.engines=engines,.n_engines=1};
    for (unsigned mode=0;mode<10;mode++) {
        lunar_instance_pool_t pool={0};lunar_project_engines_t candidate={0},saved;
        fm1_state_report_t report;fm1_rec_t r={0};const uint8_t version[3]={0,1,0};
        size_t requests[4];void *fill[6]={0};
        want=mode==3?206904:sizes[(shard/4)%4];
        attempts=destroyed=0;fail_at=mode==1?0:mode==2?count-1:99;
        memset(handles,0,sizeof handles);engine.create=create;engine.get_param=get_param;
        assert(lunar_instance_pool_init(&pool,arena,sizeof arena)==0);
        unsigned char *live=lunar_instance_pool_alloc(&pool,4096);assert(live);memset(live,0xa5,4096);
        if (mode==7) {
            for (unsigned i=0;i<6;i++) {fill[i]=lunar_instance_pool_alloc(&pool,24000);assert(fill[i]);}
            for (unsigned i=0;i<6;i+=2) {assert(!lunar_instance_pool_free(&pool,fill[i]));fill[i]=NULL;}
        }
        size_t before_bytes=pool.live_bytes;unsigned before_count=pool.live_allocations;
        void *writer=calloc(1,fm1_state_bin_writer_size());assert(writer);
        length=0;fm1_state_report_init(&report);
        fm1_state_writer_t *w=fm1_state_bin_writer(writer,0,FM1_STATE_WRITER_DESKTOP,version,put,NULL,&report);assert(w);
        r.type=FM1_REC_HEAD;r.u.head.kind=FM1_STATE_PROJECT;r.u.head.major=1;assert(fm1_state_bin_write(w,&r));
        for (unsigned i=0;i<count;i++) {
            memset(&r,0,sizeof r);r.type=FM1_REC_UNIT;r.role=FM1_ROLE_SOUND;r.sound=(uint8_t)i;
            strcpy(r.u.unit.id,"trio");assert(fm1_state_bin_write(w,&r));requests[i]=want;
            for (unsigned p=0;p<4;p++) {
                float value=p==0?2.0f:p==1?0.25f:p==2?0.75f:0.875f;
                memset(&r,0,sizeof r);r.type=FM1_REC_PARAM;r.role=FM1_ROLE_SOUND;r.sound=(uint8_t)i;
                r.u.param.uid=(uint16_t)(p==0?1:p==3?3:2);r.u.param.focus=(uint8_t)(p==1?0:p==2?1:FM1_FOCUS_NONE);
                r.u.param.vtype=p==0?FM1_VAL_INDEX:FM1_VAL_F32;
                if (p==0) r.u.param.bits=1; else memcpy(&r.u.param.bits,&value,4);
                assert(fm1_state_bin_write(w,&r));
            }
        }
        r.type=FM1_REC_END;assert(fm1_state_bin_write(w,&r));
        int fits=lunar_instance_pool_can_fit(&pool,requests,count);
        if (mode==4) engine.create=NULL;
        if (mode==6) host.api_version=0;
        if (mode==8) engine.get_param=NULL;
        int expected=fits && mode!=1 && mode!=2 && mode!=4 && mode!=6 && mode!=8;
        int ok=lunar_project_engines_stage(binary,(uint32_t)length,&names,&host,&pool,&candidate,&report);
        assert(ok==expected);
        if (ok) {
            assert(report.code==FM1_STATE_OK && attempts==count && !destroyed && candidate.pool==&pool);
            assert(pool.live_allocations==before_count+count && pool.live_bytes==before_bytes+count*want);
            for (unsigned i=0;i<count;i++) assert(candidate.unit[i].self==(unsigned char *)candidate.unit[i].memory+16);
            if (mode==5) {
                saved=candidate;
                assert(!lunar_project_engines_stage(binary,(uint32_t)length,&names,&host,&pool,&candidate,&report));
                assert(!memcmp(&saved,&candidate,sizeof saved) && attempts==count);
            }
            assert(lunar_project_engines_apply(binary,(uint32_t)length,&names,&host,&candidate,&report));
            for (unsigned i=0;i<count;i++) {
                const state_t *s=candidate.unit[i].self;
                assert(s->focus==2 && s->pad[0]==0.25f && s->pad[1]==0.75f && s->ordinary==0.875f);
                assert(candidate.unit[i].value[0]==2 && candidate.unit[i].value[1]==0.75f && candidate.unit[i].value[2]==0.875f);
            }
            if (mode==9) {
                binary[length-1]^=1;
                assert(!lunar_project_engines_apply(binary,(uint32_t)length,&names,&host,&candidate,&report));
                for (unsigned i=0;i<count;i++) assert(((state_t *)candidate.unit[i].self)->pad[0]==0.25f);
            }
            lunar_project_engines_release(&candidate);
            assert(destroyed==count);
        } else {
            lunar_project_engines_t empty={0};assert(!memcmp(&empty,&candidate,sizeof empty));
            assert(report.code!=FM1_STATE_OK);
            if (!fits || mode==4 || mode==6 || mode==8) assert(!attempts && !destroyed);
            else assert(destroyed==attempts-1);
        }
        lunar_project_engines_release(&candidate); /* idempotent empty cleanup */
        assert(pool.live_bytes==before_bytes && pool.live_allocations==before_count);
        for (unsigned i=0;i<4096;i++) assert(live[i]==0xa5);
        for (unsigned i=0;i<6;i++) if (fill[i]) assert(!lunar_instance_pool_free(&pool,fill[i]));
        assert(!lunar_instance_pool_free(&pool,live));assert(!pool.live_bytes && !pool.live_allocations);
        host.api_version=FM1_ENGINE_API_VERSION;free(writer);
    }
    return 0;
}
'''

@pytest.fixture(scope='session')
def engine_candidate_probe(tmp_path_factory):
    probes = {}
    def build(opt):
        if opt in probes:
            return probes[opt]
        tmp = tmp_path_factory.mktemp('native-project-engine-' + opt[1:])
        resolve_modules(ROOT, tmp / 'catalogue', 'trio')
        source = tmp / 'probe.c'
        source.write_text(HARNESS)
        vendor = ROOT / 'firmware/third_party/tlsf'
        sources = [ROOT / 'firmware/native' / (s + '.c') for s in
                   ('project_units', 'project_engines', 'instance_pool')]
        sources += [source, vendor / 'tlsf.c']
        sources += [ROOT / 'engines/state' / (s + '.c') for s in
                    ('state_bin', 'state_names', 'state_movy1', 'fm1_num', 'fm1_deflate')]
        inc = [arg for path in (ROOT / 'firmware/native', ROOT / 'engines/include',
                               ROOT / 'engines/state', vendor, tmp / 'catalogue/gen')
               for arg in ('-I', str(path))]
        exe = tmp / 'probe'
        subprocess.run(['cc', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                        '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                        *native_no_pie_flags(), *inc, *map(str, sources),
                        *native_host_link_flags(), '-lm', '-o', str(exe)], check=True)
        probes[opt] = exe
        return exe
    return build

@pytest.mark.parametrize('opt', ['-Os', '-Oz'])
def test_native_project_engines_target_compile(opt, tmp_path):
    tc = configured_target_toolchain()
    catalogue = tmp_path / 'catalogue'
    resolve_modules(ROOT, catalogue, 'trio')
    inc = ['-I' + str(ROOT / p) for p in ('firmware/native', 'engines/include', 'engines/state')]
    inc += ['-I', str(catalogue / 'gen')]
    subprocess.run([str(tc / 'common/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
                    '-mfprev1', '-std=c99', opt, '-Wall', '-Wextra', '-Werror',
                    '-ffreestanding', '-fno-builtin', *inc,
                    '-isystem', str(tc / 'pi32v2/include'), '-c', str(ROOT / 'firmware/native/project_engines.c'),
                    '-o', str(tmp_path / 'target.o')], check=True, capture_output=True)


@pytest.mark.parametrize('case', range(16))
@pytest.mark.parametrize('opt', ['-Os', '-Oz'])
def test_native_project_engines(case, opt, engine_candidate_probe):
    subprocess.run([str(engine_candidate_probe(opt)), str(case)], check=True)
