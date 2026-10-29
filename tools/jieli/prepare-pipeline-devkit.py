#!/usr/bin/env python3
"""Prepare the tracked continuous dev-board DAC pipeline, offline only.

Private AC79 e30b1ee SDK and reviewed scheduler archive are explicit inputs.
No downloading, flashing, backups or device operations. Preserve the small input
receipt and final evidence; remove this lane's reproducible SDK after its run.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

SYSTEM = Path('cpu/wl82/liba/system.a')
ORIGINAL_SYSTEM_SHA256 = 'a71bdc75e5afbcffaf7d79bc2b27f2b65fec63d94d2261b584744d3e9b9098ea'
PIPELINE_SYSTEM_SHA256 = '792c7599e76e52a2cac9cd3a69d1d99bf301912ba941840d1dc819300484c7ee'
SELECTOR_CORRECTION = 'ac79-e30b1ee-affinity-early-selected-tail-v132'
# Named fixed-polyphony workload policies; adaptive-three stays a separate flag.
POLICIES = {'fixed12': '', 'cap8': 'CFLAGS += -DLUNAR_RENDERER_POLICY_CAP8=1\n'}
WORST_BLOCK_FLAGS = 'CFLAGS += -DLUNAR_PIPELINE_WORST_BLOCK=1 -DFM1_APP_PIPELINE_MARKS=1\n'
# Timing-only: the dev board runs its host at 44,100 Hz, where Plaits'
# 47,872.34 Hz is +400 ppm off 51/47, so the 51/47 fast path's 10 ppm gate
# (engines/include/fm1_resampler.h) never engages and a board run would time
# the two-stage converter. 5e-4 admits it; Plaits-rate engines then sound
# 0.69 cent flat on the dev board. Never for the FM-1 (44,118 Hz is -7.9 ppm).
POLY47_AT_44100_TOLERANCE = '5e-4'
POLY47_AT_44100_FLAGS = 'CFLAGS += -DFM1_RESAMPLER_POLY47_TOLERANCE=' + POLY47_AT_44100_TOLERANCE + '\n'

# Owner, 2026-10-28: time the dev board at the FM-1's stock clock tree and
# power profile. App-only and at run time (firmware/devkit/clock360.c): the
# kit's flash head, isd_config and SPL are unchanged. Rails go up to the
# FM-1's levels [reported: fm1-nes board_power.c], then system_clock_set
# moves 320 -> 360 MHz, keeping HSB /2 and LSB /3 (180 and 60 MHz). Default
# off: the 320 MHz build inputs are byte-identical when it is not asked for.
SYS_CLOCKS = (320, 360)
SFC_BAUD = {60: 2, 90: 1}  # SFC = HSB 180 MHz / (BAUD + 1)
STOCK_POWER = {'sysvdd': '1.38 V', 'vdc14': '1.60 V', 'vdc14_dcdc': True,
               'vddiom': '3.2 V', 'vddiow': '3.2 V', 'lvd': '2.6 V'}

# Exact-PCM transformations/placement used by the successful private pipeline.
# Internal timing-only setup suppresses the old DAC demo and all observers;
# adapt_pipeline below replaces that worker mode with the tracked DAC driver.
PRESET = dict(timing_only=True, profile=True, hot_ram=True, sine_ram=True,
              resampler_ram=True, cache_tables=True, fx_ram=True,
              filter_process_ram=True, control_ram=True, plaits_cache=True,
              resampler_slopes=True, resampler_unroll=True, renderer_o3=True,
              mixer_ram=True, dispatch_ram=True, msfa_narrow_adds=True,
              msfa_sine32=True, msfa_pure_unroll=True, ui_ram=True,
              prep_profile=True, hook_ram=True, module_ram=True, kind_ram=True,
              event_ram=True, external_pixels=True, vcf_unroll=True,
              oscillator_slopes=True, outer_timing_only=True, metadata_ram=True,
              msfa_sine_pair=True, drums_ready_convert=True)

# The FM6 sine switch (engines/Makefile FM1_DX7_SINE). trunc12 compiles its
# own sin.h, which has no interpolation for the signed32 product and paired
# loads to change, so those two preset entries are off with it; every other
# entry, the sine table's SRAM placement included, stays as it is.
TRUNC12_PRESET = dict(msfa_sine32=False, msfa_sine_pair=False)


def renderer_preset(dx7_sine):
    if dx7_sine not in ('msfa', 'trunc12'):
        raise ValueError('Unknown DX7 sine; choose msfa or trunc12')
    return dict(PRESET, dx7_sine=dx7_sine, **(TRUNC12_PRESET if dx7_sine == 'trunc12' else {}))

PIPELINE_APP_HOT = (
    b'static int pipeline_record', b'static void pipeline_validate_stream',
    b'static void pipeline_execute', b'static void post_capture',
    b'static void post_fx_run', b'static void post_amp_run', b'static void post_run',
    b'static void pipeline_preflight', b'static void pipeline_capture_drive',
    b'static void pipeline_level_apply', b'static void pipeline_finish_sound_slot',
    b'static void pipeline_render_sounds', b'static const float *pipeline_consume_block',
    b'static void pipeline_retire_block', b'static void pipeline_produce_block',
    b'int fm1_app_pipeline_produce', b'const float *fm1_app_pipeline_consume',
    b'int fm1_app_pipeline_retire',
)


# Match the retained successful pipeline's exact placement, not intermediate
# cold-constructor experiments. Keep DX7 initialization/allocation/budget paths
# in XIP while the actual synthesis loops remain startup-copied SRAM code.
PIPELINE_XIP = (
    '  void Init(const fm1_host_t *host)',
    '  void NoteOn(uint8_t key, uint8_t velocity)',
    '  Voice *Allocate(uint8_t key)',
    '  unsigned SetVoiceLimit(unsigned limit)',
    '  void BudgetStats(fm1_dx7_budget_stats_t &out) const',
    '  void EnforceVoiceLimit()',
    'extern "C" int fm1_dx7_set_voice_limit(void *self, unsigned limit)',
    'extern "C" int fm1_dx7_get_budget_stats(const void *self, fm1_dx7_budget_stats_t *out)',
)


# Engine constructors run once, when renderer_live.c selects the fixed units
# before the first block (fm1_app_select), never from a render or note path.
# The hot-source pragmas put them in SRAM with the rest of their files; back in
# XIP they free SRAM for the heap. Each one's init-only callee goes with it:
# the vendor compiler does not inline across the two sections, so leaving
# Instance::Init in SRAM would only outline it there. Shared helpers that hot
# code also inlines (DriveOnePoleG, CompPole, ...) stay where they are.
# Placement only: no source body, coefficient or arithmetic flag changes.
PIPELINE_INIT_XIP = (
    ('engines/src/drums.cc', 'void *Create(void *mem, const fm1_host_t *host) {'),
    ('engines/src/drums.cc', '  bool Init(const fm1_host_t *host) {'),
    ('engines/src/mi_macro.cc', 'void *Create(void *mem, const fm1_host_t *host) {'),
    ('engines/src/mi_macro.cc', '  bool Init(const fm1_host_t *host) {'),
    ('engines/src/fx_echo.cc', 'void *Create(void *mem, const fm1_host_t *host) {'),
    ('engines/src/fx_echo.cc', '  void Init(const fm1_host_t *host) {'),
    ('engines/src/msfa_dx7.cc', 'void *Create(void *mem, const fm1_host_t *host) {'),
    ('engines/src/msfa_dx7.cc', 'bool SharedInit(float rate) {'),
    ('engines/src/fx_drive.cc', 'static void *DriveCreate(void *mem, const fm1_host_t *host) {'),
    ('engines/src/fx_comp.cc', 'static void *CompCreate(void *mem, const fm1_host_t *host) {'),
)
INIT_XIP_ATTRIBUTE = '__attribute__((noinline, section(".text"))) '

# The writer and heap bounds every pipeline image must meet, and the check of a
# linked ELF against them, live in tools/jieli/pipeline_bounds.py.
_bounds_spec = importlib.util.spec_from_file_location('pipeline_bounds', Path(__file__).resolve().parent / 'pipeline_bounds.py')
BOUNDS = importlib.util.module_from_spec(_bounds_spec)
_bounds_spec.loader.exec_module(BOUNDS)


def place_init_xip(staging):
    for name, anchor in PIPELINE_INIT_XIP:
        path = staging / name
        indent = anchor[:len(anchor) - len(anchor.lstrip())]
        path.write_text(checked_replace(path.read_text(), '\n' + anchor,
                                        '\n' + indent + INIT_XIP_ATTRIBUTE + anchor.lstrip()))


def unlist_resampler_benchmark(makefile_text):
    """Pipeline images never call lunar_devkit_benchmark (sdk_worker.c calls it
    only in the resampler-only build), but listing it linked its own copy of
    the resampler tables in XIP (the 51/47 table among them, 4,608 B) and its
    1,432 B resampler state in SRAM .bss."""
    text = checked_replace(makefile_text, '\t../../../../../apps/demo/demo_hello/benchmark.c \\\n', '')
    return checked_replace(text, '\nobjs/apps/demo/demo_hello/benchmark.c.o: CFLAGS := '
                           '$(filter-out -Oz -flto,$(CFLAGS)) -O2 -ffp-contract=off -fno-data-sections\n', '\n')


def place_pipeline_xip(staging, burst_hot=False):
    path = staging / 'engines/src/msfa_dx7.cc'
    text = path.read_text()
    attribute = '__attribute__((noinline, section(".text"))) '
    for anchor in PIPELINE_XIP:
        if burst_hot and anchor in ('  void NoteOn(uint8_t key, uint8_t velocity)', '  Voice *Allocate(uint8_t key)'):
            text = checked_replace(text, anchor, '  __attribute__((noinline, section(".volatile_ram_code"))) ' + anchor.lstrip())
            continue
        if anchor.startswith('extern "C" '):
            replacement = 'extern "C" ' + attribute + anchor[len('extern "C" '):]
        else:
            replacement = '  ' + attribute + anchor.lstrip()
        text = checked_replace(text, anchor, replacement)
    path.write_text(text)


def vcf_main_output(header, body, macro):
    """Keep full VCF API; omit only discarded aux finishing in Macro model0.

    Identical zero-resonance coefficients share their original rounded g/r/h.
    Both filters still advance. Nonzero or transitioning resonance uses the
    original independent coefficient path. Main-only leaves aux workspace live
    for the sub oscillator/input, skipping only its final unused SoftClip/store.
    """
    header = checked_replace(header, ' private:\n  stmlib::Svf svf_[2];',
        '  void RenderMain(const EngineParameters& parameters, float* out, float* aux,\n'
        '      size_t size, bool* already_enveloped);\n private:\n'
        '  void RenderImpl(const EngineParameters& parameters, float* out, float* aux,\n'
        '      size_t size, bool* already_enveloped, bool main_only);\n  stmlib::Svf svf_[2];')
    body = checked_replace(body, 'void VirtualAnalogVCFEngine::Render(\n',
        'void VirtualAnalogVCFEngine::Render(\n'
        '    const EngineParameters& p, float* out, float* aux, size_t n, bool* enveloped) {\n'
        '  RenderImpl(p, out, aux, n, enveloped, false);\n}\n'
        'void VirtualAnalogVCFEngine::RenderMain(\n'
        '    const EngineParameters& p, float* out, float* aux, size_t n, bool* enveloped) {\n'
        '  RenderImpl(p, out, aux, n, enveloped, true);\n}\n\n'
        'void VirtualAnalogVCFEngine::RenderImpl(\n')
    body = checked_replace(body, '    bool* already_enveloped) {',
        '    bool* already_enveloped, bool main_only) {')
    q = '  const float q = resonance_sqr * resonance_sqr * 48.0f;'
    body = checked_replace(body, q, q + '\n  const bool shared_coefficients = previous_q_ == 0.0f && q == 0.0f;')
    body = checked_replace(body,
        '    svf_[0].set_f_q<FREQUENCY_FAST>(cutoff, 0.5f + q);\n'
        '    svf_[1].set_f_q<FREQUENCY_FAST>(cutoff, 0.5f + 0.025f * q);',
        '    if (shared_coefficients) {\n'
        '      const float g = OnePole::tan<FREQUENCY_FAST>(cutoff);\n'
        '      const float r = 2.0f;\n'
        '      const float h = 1.0f / (1.0f + r * g + g * g);\n'
        '      svf_[0].set_g_r_h(g, r, h);\n'
        '      svf_[1].set_g_r_h(g, r, h);\n'
        '    } else {\n'
        '      svf_[0].set_f_q<FREQUENCY_FAST>(cutoff, 0.5f + q);\n'
        '      svf_[1].set_f_q<FREQUENCY_FAST>(cutoff, 0.5f + 0.025f * q);\n    }')
    body = checked_replace(body, '    aux[i] = SoftClip(hp * gain);',
        '    if (!main_only) aux[i] = SoftClip(hp * gain);')
    macro = checked_replace(macro,
        '      v.engine->Render(p, v.out, v.aux, kBlockSize, &already_enveloped);',
        '      if (model_ == MODEL_VA_VCF) {\n'
        '        static_cast<VirtualAnalogVCFEngine *>(v.engine)->RenderMain(\n'
        '            p, v.out, v.aux, kBlockSize, &already_enveloped);\n'
        '      } else {\n'
        '        v.engine->Render(p, v.out, v.aux, kBlockSize, &already_enveloped);\n      }')
    return header, body, macro


def prepare_vcf_main(staging):
    base = staging / 'engines/third_party/mutable/plaits/dsp/engine2/virtual_analog_vcf_engine'
    paths = (base.with_suffix('.h'), base.with_suffix('.cc'), staging/'engines/src/mi_macro.cc')
    result = vcf_main_output(*(path.read_text() for path in paths))
    for path, text in zip(paths, result):
        path.write_text(text)


def dx7_block_controls(s):
    """Cache only identical global controls within one native render block."""
    def once(a,b):
        nonlocal s
        s=checked_replace(s,a,b)
    if 'BlockControls' in s:
        raise ValueError('DX7 block controls already prepared')
    once('  void RenderBlock() {', '''  struct BlockControls {
    unsigned valid;
    uint32_t speed, env_speed;
    int32_t bright;
    int feedback;
  };

  void RenderBlock() {
    BlockControls common = {};''')
    once('RenderPair(v, voice_[next], lfo_val, lfo_delay, mix);','RenderPair(v, voice_[next], lfo_val, lfo_delay, mix, common);')
    once('RenderVoice(&v, lfo_val, lfo_delay);','RenderVoice(&v, lfo_val, lfo_delay, common);')
    once('int32_t lfo_delay, int32_t *mix) {','int32_t lfo_delay, int32_t *mix, BlockControls &common) {')
    once('PrepareVoice(&first, lfo_val, lfo_delay),','PrepareVoice(&first, lfo_val, lfo_delay, common),')
    once('PrepareVoice(&second, lfo_val, lfo_delay) };','PrepareVoice(&second, lfo_val, lfo_delay, common) };')
    once('void RenderVoice(Voice *v, int32_t lfo_val, int32_t lfo_delay) {','void RenderVoice(Voice *v, int32_t lfo_val, int32_t lfo_delay, BlockControls &common) {')
    once('PrepareVoice(v, lfo_val, lfo_delay));','PrepareVoice(v, lfo_val, lfo_delay, common));')
    once('int PrepareVoice(Voice *v, int32_t lfo_val, int32_t lfo_delay) {','int PrepareVoice(Voice *v, int32_t lfo_val, int32_t lfo_delay, BlockControls &common) {')
    once('''    const float bright = v->note.Value(kParams, P_BRIGHTNESS, value_[P_BRIGHTNESS]);
    const float env_time = v->note.Value(kParams, P_ENV_TIME, value_[P_ENV_TIME]);
    const float fb_offset = v->note.Value(kParams, P_FEEDBACK, value_[P_FEEDBACK]);
''','')
    once('''    const uint32_t speed = static_cast<uint32_t>(Exp2::lookup(ToQ24(0.5f - env_time, kEnvTimeQ24)));
    const uint32_t env_speed =
        static_cast<uint32_t>((static_cast<uint64_t>(speed) * env_rate_q24_) >> 24);''','''    uint32_t speed, env_speed;
    if (v->note.has(P_ENV_TIME)) {
      const float env_time = v->note.Value(kParams, P_ENV_TIME, value_[P_ENV_TIME]);
      speed = static_cast<uint32_t>(Exp2::lookup(ToQ24(0.5f - env_time, kEnvTimeQ24)));
      env_speed = static_cast<uint32_t>((static_cast<uint64_t>(speed) * env_rate_q24_) >> 24);
    } else {
      if (!(common.valid & 1u)) {
        common.speed = static_cast<uint32_t>(Exp2::lookup(ToQ24(0.5f - value_[P_ENV_TIME], kEnvTimeQ24)));
        common.env_speed = static_cast<uint32_t>((static_cast<uint64_t>(common.speed) * env_rate_q24_) >> 24);
        common.valid |= 1u;
      }
      speed = common.speed; env_speed = common.env_speed;
    }''')
    once('''    const int32_t bright_q24 = ToQ24(bright - 0.5f, kBrightnessQ24);''','''    int32_t bright_q24;
    if (v->note.has(P_BRIGHTNESS)) {
      const float bright = v->note.Value(kParams, P_BRIGHTNESS, value_[P_BRIGHTNESS]);
      bright_q24 = ToQ24(bright - 0.5f, kBrightnessQ24);
    } else {
      if (!(common.valid & 2u)) {
        common.bright = ToQ24(value_[P_BRIGHTNESS] - 0.5f, kBrightnessQ24);
        common.valid |= 2u;
      }
      bright_q24 = common.bright;
    }''')
    once('''    int fb = v->feedback + Round(fb_offset);''','''    int fb_offset;
    if (v->note.has(P_FEEDBACK)) {
      fb_offset = Round(v->note.Value(kParams, P_FEEDBACK, value_[P_FEEDBACK]));
    } else {
      if (!(common.valid & 4u)) {
        common.feedback = Round(value_[P_FEEDBACK]);
        common.valid |= 4u;
      }
      fb_offset = common.feedback;
    }
    int fb = v->feedback + fb_offset;''')
    return s


def pipeline_sound_frontier(text):
    """Fixed sound1 geometry only; never move insert or master processing."""
    if 'cur[1] < 8' in text:
        raise ValueError('Pipeline frontier already prepared')
    text = checked_replace(text,
        '  const uint32_t nw = hk->tick(hk->ctx, tf, &w, &next);',
        '  /* Publish sound1 first eight frames before later control hooks. */\n'
        '  if (n > 1 && slots[1].sink && cur[1] < 8 && tf >= 8)\n'
        '    slot_upto(h, &slots[1], &cur[1], 8);\n'
        '  const uint32_t nw = hk->tick(hk->ctx, tf, &w, &next);')
    return checked_replace(text,
        '    hk->event(hk->ctx, f, e, sl ? 1 + (int)(sl - slots) : 0);',
        '    if (n > 1 && slots[1].sink && cur[1] < 8 && f >= 8)\n'
        '      slot_upto(h, &slots[1], &cur[1], 8);\n'
        '    hk->event(hk->ctx, f, e, sl ? 1 + (int)(sl - slots) : 0);')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_replace(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected pipeline preparation anchor: ' + before)
    return text.replace(before, after, 1)


def clock360_worker(text):
    """Switch after the recovery window, before the probe and the DAC."""
    text = checked_replace(text, '#include "benchmark.h"\n', '#include "benchmark.h"\n#include "clock360.h"\n')
    anchor = ('    os_time_dly(200);\n#endif\n'
              '#if defined(LUNAR_DEVKIT_RENDERER_TIMING) || defined(LUNAR_DEVKIT_RENDERER_PIPELINE_DAC)\n')
    return checked_replace(text, anchor, anchor.replace('#endif\n', '#endif\n'
        '    /* FM-1 clock and power (prepare-pipeline-devkit.py --sys-clk 360).\n'
        '     * Fail closed: no arithmetic probe and no DAC after a FAIL. */\n'
        '    if (!lunar_clock360_apply(now)) {\n'
        '        for (;;) os_time_dly(100);\n'
        '    }\n', 1))


def clock360_dac(text):
    """Measure the DAC rate after the switch; the preroll window gates audio."""
    if 'clock360' in text:
        raise ValueError('DAC clock check already prepared')
    text = checked_replace(text, '#include "voice_budget.h"\n', '#include "voice_budget.h"\n#include "clock360.h"\n')
    # Kept small: the 360 MHz image has under 1 KB to spare in the writer
    # region. One outlined snapshot; one window, the preroll's (about 260 ms,
    # some 180 callbacks timed by TIMER4 at 24 MHz, far finer than the 0.5 %
    # gate). A rate tied to the system clock is off by 12.5 % from the first
    # callback, so a second window at the end of the soak would add nothing the
    # analog capture does not already show; it was also skipped on every soak
    # longer than TIMER4's 178 s wrap.
    run = 'int lunar_pipeline_dac_run(uint32_t (*now)(void)) {\n'
    text = checked_replace(text, run,
        '/* The callback count and the TIMER4 start stamp of the last callback, together. */\n'
        'static __attribute__((noinline)) uint32_t clock360_snap(uint32_t *t)'
        '{unsigned f;uint32_t cb;local_irq_save(f);fence103();cb=transport.callbacks;*t=transport.previous;'
        'local_irq_restore(f);return cb;}\n\n' + run)
    wait = '    while((uint32_t)(timer_get_ms()-pre)<50u && !transport.fault && !lunar_pipeline_error())os_time_dly(1);\n'
    text = checked_replace(text, wait, wait +
        '    /* Callback start stamps (TIMER4) bracket whole 64-frame callbacks. */\n'
        '    uint32_t clock360_t0,clock360_t1,clock360_cb0=clock360_snap(&clock360_t0);\n')
    # A failed window raises transport fault 36001, so the driver's own fault
    # check fails the run before the music starts. No new failure exit.
    preroll = '    preroll_ms=timer_get_ms()-pre;\n'
    check = '    if(transport.fault||lunar_pipeline_error())return v110_failure(__LINE__);\n'
    return checked_replace(text, preroll + check,
        preroll +
        '    uint32_t clock360_cb1=clock360_snap(&clock360_t1);\n'
        '    if(!lunar_clock360_audio_rate("preroll",clock360_cb1-clock360_cb0,clock360_t1-clock360_t0))'
        'task_fault103(36001);\n' + check)


def adapt_clock360(out, source, sfc_mhz):
    app = out / 'apps/demo/demo_hello'
    for name in ('clock360.c', 'clock360.h'):
        shutil.copyfile(source / 'firmware/devkit' / name, app / name)
    worker = app / 'sdk_worker.c'
    worker.write_text(clock360_worker(worker.read_text()))
    dac = out / 'lunar-source/firmware/devkit/renderer_pipeline_dac.c'
    dac.write_text(clock360_dac(dac.read_text()))
    return ('CFLAGS += -DLUNAR_DEVKIT_SYS_CLK=360000000 -DLUNAR_DEVKIT_STOCK_POWER=1 '
            f'-DLUNAR_DEVKIT_SFC_BAUD={SFC_BAUD[sfc_mhz]}\n')


def adapt_pipeline(out, source, renderer, adaptive_three, cycles, burst_hot=False,
                   policy='fixed12', worst_block=False, poly47_at_44100=False,
                   sys_clk=320, stock_power=False, sfc_mhz=60):
    """Replace legacy worker mode, never its recovery or lifecycle bodies."""
    app = out / 'apps/demo/demo_hello'
    main = app / 'app_main.c'
    main.write_text(checked_replace(main.read_text(),
        'os_task_create(lunar_devkit_worker, NULL, 10, 2048, 0, "lunar_devkit");',
        'os_task_create(lunar_devkit_worker, NULL, 16, 2048, 0, "#C0lunar_parent");'))
    staging = out / 'lunar-source'
    flags = ('CFLAGS += -DLUNAR_DEVKIT_RENDERER_PIPELINE=1 '
             '-DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1 -DFM1_APP_RENDER_PIPELINE=1\n'
             f'CFLAGS += -DLUNAR_PIPELINE_CYCLES={cycles}\n'
             f'CFLAGS += -I{staging / "firmware/devkit"}\n')
    if adaptive_three:
        flags += 'CFLAGS += -DLUNAR_PIPELINE_ADAPTIVE_THREE=1\n'
    flags += POLICIES[policy]
    if worst_block:
        flags += WORST_BLOCK_FLAGS
    if poly47_at_44100:
        flags += POLY47_AT_44100_FLAGS
    if sys_clk == 360:
        flags += adapt_clock360(out, source, sfc_mhz)
    makefile = app / 'board/wl82/Makefile'
    text = checked_replace(makefile.read_text(), 'CFLAGS += -DLUNAR_DEVKIT_RENDERER_TIMING=1\n', flags)
    if sys_clk == 360:
        text = checked_replace(text, 'c_SRC_FILES := \\\n',
                               'c_SRC_FILES := \\\n\t../../../../../apps/demo/demo_hello/clock360.c \\\n')
    makefile.write_text(unlist_resampler_benchmark(text))
    (app / 'benchmark.c').unlink()
    # The pinned compiler's code_seg pragma is retained only in private copies.
    # Original functions remain unchanged; newly split hot paths need placement.
    place_pipeline_xip(staging, burst_hot)
    place_init_xip(staging)
    prepare_vcf_main(staging)
    dx7 = staging / 'engines/src/msfa_dx7.cc'
    dx7.write_text(dx7_block_controls(dx7.read_text()))
    seq = staging / 'engines/seq/seq_host.c'
    seq.write_text(pipeline_sound_frontier(seq.read_text()))
    app_source = staging / 'sim/web/src/fm1_app.c'
    app_source.write_bytes(renderer.place_hook_ram(app_source.read_bytes(), PIPELINE_APP_HOT))
    live = staging / 'firmware/devkit/renderer_live.c'
    live.write_bytes(renderer.place_hook_ram(live.read_bytes(), (b'static int pipeline_convert',)))
    shutil.copyfile(source / 'firmware/devkit/renderer_pipeline_dac.h', app / 'renderer_pipeline_dac.h')
    receipt_path = out / 'lunar-devkit-input.json'
    receipt = json.loads(receipt_path.read_text())
    receipt.update({
        'measurement': 'tracked pipelined shared renderer through dev-board internal DAC',
        'timing_only': False, 'outer_timing_only': False,
        'renderer_pipeline': True, 'renderer_pipeline_dac': True,
        'pipeline_cycles': cycles,
        'pipeline_polyphony': 'adaptive65/60-floor3' if adaptive_three else policy,
        'pipeline_worst_block': worst_block,
        'pipeline_poly47_at_44100': poly47_at_44100,
        'pipeline_poly47_tolerance': POLY47_AT_44100_TOLERANCE if poly47_at_44100 else '1e-5',
        'parent_task_priority': 16, 'uart_task_priority': 18,
        'worker_stack_words': 2048, 'worker_stack_bytes': 8192,
        'pipeline_worker_stack_words': 1536, 'pipeline_worker_priority': 16,
        'pipeline_work_slots': 2, 'pipeline_output_slots': 8,
        'pipeline_deadline_ticks': 34829,
        'pipeline_protocol_budget_ticks': 2400000,
        'pipeline_system_correction': SELECTOR_CORRECTION,
        'pipeline_system_original_sha256': ORIGINAL_SYSTEM_SHA256,
        'pipeline_system_sha256': PIPELINE_SYSTEM_SHA256,
        'pipeline_xip_functions': [x for x in PIPELINE_XIP if not (burst_hot and ('NoteOn(' in x or 'Allocate(' in x))],
        'pipeline_burst_hot': burst_hot,
        'pipeline_init_xip_functions': [f'{name}: {anchor.strip()[:-2]}' for name, anchor in PIPELINE_INIT_XIP],
        'pipeline_resampler_benchmark_linked': False,
        'pipeline_app_bytes_limit': BOUNDS.APP_BYTES_LIMIT,
        'pipeline_heap_min_after_open': BOUNDS.HEAP_MIN_AFTER_OPEN,
        'pipeline_vcf_main_output': True,
        'pipeline_dx7_block_controls': True,
        'pipeline_sound1_frontier_frames': 8,
        'pipeline_hot_functions': [x.decode() for x in PIPELINE_APP_HOT] + ['static int pipeline_convert'],
        'prepared_app_main_sha256': sha256(main),
        'prepared_board_makefile_sha256': sha256(makefile),
        'renderer_integration_complete': False, 'hardware_acceptance': False,
        'cleanup': 'Remove only this generated SDK after evidence export and process exit; retain logs/receipts.',
    })
    if sys_clk == 360:
        # Only when asked for, so a 320 MHz receipt keeps its exact keys.
        receipt.update({
            'sys_clk_hz': 360000000, 'hsb_hz': 180000000, 'lsb_hz': 60000000,
            'sfc_hz': sfc_mhz * 1000000, 'sfc_baud': SFC_BAUD[sfc_mhz],
            'stock_power': stock_power, 'stock_power_levels': STOCK_POWER,
            'clock_switch': 'app-only at run time: rails, then system_clock_set(360 MHz), then SFC; '
                            'fail closed before the DAC opens',
            'prepared_sdk_worker_sha256': sha256(app / 'sdk_worker.c'),
            'prepared_renderer_pipeline_dac_sha256': sha256(staging / 'firmware/devkit/renderer_pipeline_dac.c'),
        })
    for directory in ('engines', 'sim/web/src', 'sim/web/mk', 'firmware/devkit'):
        for path in sorted((staging / directory).rglob('*')):
            if path.is_file():
                receipt['inputs'][str(path.relative_to(staging))] = sha256(path)
    receipt['inputs']['tools/jieli/prepare-pipeline-devkit.py'] = sha256(source / 'tools/jieli/prepare-pipeline-devkit.py')
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')


def prepare_pipeline(sdk, source, out, system_archive, adaptive_three=False, cycles=3, burst_hot=False,
                     policy='fixed12', worst_block=False, *, dx7_sine='msfa', poly47_at_44100=False,
                     sys_clk=320, stock_power=False, sfc_mhz=60):
    preset = renderer_preset(dx7_sine)
    if sys_clk not in SYS_CLOCKS:
        raise ValueError('System clock must be 320 or 360 MHz')
    if sys_clk == 360 and not stock_power:
        raise ValueError('360 MHz needs --stock-power: the rails go up before the clock')
    if stock_power and sys_clk != 360:
        raise ValueError('--stock-power is reviewed only with --sys-clk 360')
    if sfc_mhz not in SFC_BAUD or (sfc_mhz != 60 and sys_clk != 360):
        raise ValueError('SFC 90 MHz is a 360 MHz choice; default 60')
    if isinstance(cycles, bool) or not 1 <= cycles <= 57:
        raise ValueError('Pipeline cycles must be 1..57')
    if policy not in POLICIES:
        raise ValueError('Unknown polyphony policy: ' + str(policy))
    if adaptive_three and policy != 'fixed12':
        raise ValueError('Adaptive-three is its own policy; do not combine it with ' + policy)
    if out.exists() or out.is_symlink():
        raise ValueError('Output must be a new private build directory')
    # Refuse any unreviewed scheduler input before copying a large SDK. Exact
    # archive hashes also pin all 46 members; vendor IR never enters this repo.
    if sha256(sdk / SYSTEM) != ORIGINAL_SYSTEM_SHA256:
        raise ValueError('Expected original pinned SDK system.a')
    corrected_bytes = system_archive.read_bytes()
    if hashlib.sha256(corrected_bytes).hexdigest() != PIPELINE_SYSTEM_SHA256:
        raise ValueError('Expected reviewed pipeline scheduler archive')
    spec = importlib.util.spec_from_file_location('renderer_prepare', source / 'tools/jieli/prepare-renderer-devkit.py')
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.prepare_renderer(sdk, source, out, **preset)
    target = out / SYSTEM
    if target.is_symlink() or sha256(target) != ORIGINAL_SYSTEM_SHA256:
        raise ValueError('Prepared scheduler must be a separate original SDK file')
    target.write_bytes(corrected_bytes)
    if sha256(target) != PIPELINE_SYSTEM_SHA256:
        raise ValueError('Prepared scheduler copy mismatch')
    adapt_pipeline(out, source, renderer, adaptive_three, cycles, burst_hot, policy, worst_block,
                   poly47_at_44100, sys_clk, stock_power, sfc_mhz)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pipeline-system-archive', type=Path, required=True,
                        help='Private reviewed scheduler archive; copied only to output SDK')
    parser.add_argument('--adaptive-three', action='store_true', help='Explicit adaptive65/60 floor3 experiment; default fixed12')
    parser.add_argument('--cycles', type=int, default=3, help='Four-case cycles, 1..57; 57 is about 30.4 minutes')
    parser.add_argument('--policy', choices=sorted(POLICIES), default='fixed12',
                        help='Named fixed DX7 polyphony: fixed12 (default) or cap8 (eight voices per DX7 at init)')
    parser.add_argument('--worst-block', action='store_true',
                        help='Record each case\'s worst producer block stage vector (six extra timer reads per block)')
    parser.add_argument('--burst-hot', action='store_true', help='Experiment: move DX7 NoteOn/Allocate from XIP into SRAM; no DSP changes')
    parser.add_argument('--dx7-sine', choices=('msfa', 'trunc12'), default='msfa',
                        help="FM6 sine (engines/Makefile FM1_DX7_SINE); trunc12 drops the msfa-only sine32/sine-pair entries")
    parser.add_argument('--poly47-at-44100', action='store_true',
                        help='Timing-only: let the 51/47 resampler fast path engage at the dev board\'s 44,100 Hz '
                             '(+400 ppm; Plaits-rate engines 0.69 cent flat). Never for the FM-1')
    parser.add_argument('--sys-clk', type=int, choices=SYS_CLOCKS, default=320,
                        help='Dev-board system clock in MHz. 360 is the FM-1\'s (HSB 180, LSB 60), switched at run '
                             'time by the app; needs --stock-power. Default 320, unchanged')
    parser.add_argument('--stock-power', action='store_true',
                        help='Raise the rails to the FM-1\'s stock levels (SYSVDD 1.38 V, VDC14 1.60 V with DCDC, '
                             'VDDIO 3.2 V, LVD 2.6 V) before the clock goes to 360 MHz')
    parser.add_argument('--sfc-mhz', type=int, choices=sorted(SFC_BAUD), default=60,
                        help='Flash clock at 360 MHz: 60 (default; the kit\'s flash is not shown to run at 90) '
                             'or 90 (as the FM-1 is thought to run)')
    args = parser.parse_args()
    prepare_pipeline(args.sdk.resolve(), args.source.resolve(), args.out.absolute(),
                     args.pipeline_system_archive.resolve(), args.adaptive_three, args.cycles, args.burst_hot,
                     args.policy, args.worst_block, dx7_sine=args.dx7_sine,
                     poly47_at_44100=args.poly47_at_44100, sys_clk=args.sys_clk,
                     stock_power=args.stock_power, sfc_mhz=args.sfc_mhz)
