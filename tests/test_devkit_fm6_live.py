"""Live bridge: real FM6 PCM, schedule coverage and bounded DAC conversion."""
import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_live_real_engine_matches_independent_render(tmp_path):
    spec = importlib.util.spec_from_file_location('prepare', ROOT/'tools/jieli/prepare-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    main = tmp_path/'main.cc'
    main.write_text(r'''
#include "fm6_live.h"
#include "fm1_engine.h"
#include <cassert>
#include <cmath>
extern "C" const fm1_engine_t fm1_engine_dx7;
int main() {
    alignas(16) unsigned char arena[65536];
    float expected[128]; int16_t guarded[258];
    guarded[0] = guarded[257] = 12345;
    assert(lunar_devkit_fm6_live_init());
    const fm1_host_t host = {FM1_ENGINE_API_VERSION, 44100.f, 64};
    const fm1_engine_t *e = &fm1_engine_dx7;
    void *s = e->create(arena, &host); assert(s);
    e->set_param(s, 0, 0); e->note_on(s, 36, 100);
    unsigned nonzero = 0;
    uint32_t expected_hash = 2166136261u;
    for (unsigned b=0; b<5513; ++b) {
        if (b*64 < 6*44100u && (b+1)*64 >= 6*44100u) e->note_off(s, 36);
        e->render(s, expected, 64);
        lunar_devkit_fm6_live_render(guarded+1);
        assert(guarded[0] == 12345 && guarded[257] == 12345);
        for (unsigned i=0; i<64; ++i) for (unsigned ch=0; ch<2; ++ch) {
            float x=expected[2*i+ch]*4096.f;
            if (b*64+i<2205) x*=float(b*64+i+1)/2205.f;
            assert(std::isfinite(x) && x>=-32768 && x<=32767);
            assert(guarded[1+4*i+ch] == int16_t(x));
            const uint16_t word = uint16_t(int16_t(x));
            expected_hash = (expected_hash ^ (word & 255u)) * 16777619u;
            expected_hash = (expected_hash ^ (word >> 8)) * 16777619u;
            assert(guarded[1+4*i+ch+2] == guarded[1+4*i+ch]);
            nonzero += guarded[1+4*i+ch] != 0;
        }
    }
    struct lunar_fm6_live_status status; lunar_devkit_fm6_live_status(&status);
    assert(nonzero && status.patch==0 && status.voices==1);
    assert(status.test_case==1 && status.note_batches==2 && !status.invalid && !status.clipped);
    assert(status.completed_cases==1 && status.completed_case==0);
    assert(status.completed_hash==expected_hash);
    e->destroy(s);
    assert(lunar_devkit_fm6_live_init());
}
''')
    units = []
    for unit in module.MSFA_UNITS:
        path = tmp_path/(unit+'.cc')
        path.write_text('#define FM1_MSFA_UNIT "'+unit+'.cc"\n#include "msfa_unit.cc"\n')
        units.append(path)
    binary = tmp_path/'live-real'
    subprocess.run(['c++', '-std=c++11', '-O2', '-ffp-contract=off', '-fwrapv',
                    '-fno-exceptions', '-fno-rtti', '-fsanitize=address,undefined',
                    '-I'+str(ROOT/'firmware/devkit'), '-I'+str(ROOT/'engines/include'),
                    '-I'+str(ROOT/'engines/src'), '-isystem', str(ROOT/'engines/third_party/msfa'),
                    str(main), str(ROOT/'firmware/devkit/fm6_live.cc'),
                    *(str(ROOT/'engines/src'/p) for p in module.FM6_SOURCES),
                    *(str(p) for p in units), '-lm', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_live_schedule_and_nonfinite_conversion(tmp_path):
    main = tmp_path/'main.cc'
    main.write_text(r'''
#include "fm6_live.h"
#include "fm1_engine.h"
#include <cassert>
#include <cmath>
static unsigned creates, destroys, ons, offs, patch;
static size_t size(const fm1_host_t *) { return 16; }
static void *create(void *p, const fm1_host_t *) { ++creates; return p; }
static void destroy(void *) { ++destroys; }
static void param(void *, uint16_t i, float x) { assert(i==0); patch=unsigned(x); }
static void on(void *, uint8_t k, uint8_t v) { assert(k>=36 && k<=69 && v==100); ++ons; }
static void off(void *, uint8_t k) { assert(k>=36 && k<=69); ++offs; }
static void render(void *, float *out, uint32_t n) {
    assert(n==64);
    for (unsigned i=0;i<128;++i) out[i] = i==0 ? NAN : i==1 ? INFINITY : i==2 ? 100.f : -100.f;
}
extern "C" const fm1_engine_t fm1_engine_dx7 = {
    FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND, "test", "test", "test", 0, 0, 12,
    size, create, destroy, on, off, 0, param, render
};
int main() {
    int16_t out[256]; struct lunar_fm6_live_status s;
    lunar_devkit_fm6_live_render(out);
    for (int x:out) assert(x==0);
    assert(lunar_devkit_fm6_live_init());
    const unsigned patches[]={0,19,25}, voices[]={1,4,8,12};
    for(unsigned c=0;c<12;++c) {
        lunar_devkit_fm6_live_render(out);
        lunar_devkit_fm6_live_status(&s);
        assert(s.test_case==c && s.patch==patches[c/4] && s.voices==voices[c%4]);
        assert(patch==s.patch);
        for(unsigned b=1;b<5513;++b) lunar_devkit_fm6_live_render(out);
    }
    lunar_devkit_fm6_live_status(&s);
    assert(s.cycles==1 && s.test_case==0 && s.note_batches==24);
    assert(s.completed_cases==12 && s.completed_case==11 && s.completed_hash!=0);
    assert(ons==75 && offs==75 && creates==1 && !destroys);
    assert(s.invalid==2*5513*12 && s.clipped>0);
    assert(out[0]==0 && out[1]==0 && out[2]==0 && out[3]==0);
    assert(out[4]==32767 && out[5]==-32768 && out[6]==32767 && out[7]==-32768);
    assert(lunar_devkit_fm6_live_init());
    assert(creates==2 && destroys==1);
}
''')
    binary = tmp_path/'live-schedule'
    subprocess.run(['c++', '-std=c++11', '-O2', '-fsanitize=address,undefined',
                    '-I'+str(ROOT/'firmware/devkit'), '-I'+str(ROOT/'engines/include'),
                    str(main), str(ROOT/'firmware/devkit/fm6_live.cc'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
