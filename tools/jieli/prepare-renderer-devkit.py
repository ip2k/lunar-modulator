#!/usr/bin/env python3
"""Prepare the private shared-renderer SDK build. No USB access or downloader.

Input must be the verified private AC79 V1.2.13 e30b1ee archive. This prepares
an offline candidate only, not an admitted image or a performance result.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import struct
from pathlib import Path
import shutil


HOT_RAM_SOURCES = (
    "engines/src/msfa_dx7.cc", "engines/src/dx7_voice.cc",
    "engines/src/dx7_loop.cc", "engines/src/msfa_unit.cc",
    "engines/src/mi_macro.cc", "engines/src/drums.cc",
    "engines/third_party/mutable/plaits/dsp/engine/virtual_analog_engine.cc",
    # The fixed workload selects model 0 (VA+Filter), not model 4 (VA Pair).
    "engines/third_party/mutable/plaits/dsp/engine2/virtual_analog_vcf_engine.cc",
)



def narrow_msfa_adds(text, kind):
    """Keep the low 32 result bits without a dead 64-bit carry addition.

    Only private prepared copies change. Unsigned addition preserves the
    original int64 sum's final int32 conversion, including wraparound.
    """
    if kind == "sin.h":
        pairs = [("return y0 + (" + expr + ");",
                  "return (int32_t)((uint32_t)y0 + (uint32_t)(" + expr + "));")
                 for expr in ("((int64_t)dy * (int64_t)lowbits) >> SHIFT",
                              "((int64_t)(y1 - y0) * (int64_t)lowbits) >> SHIFT")]
    elif kind == "fm_op_kernel.cc":
        old = "output[i] += ((int64_t)y * (int64_t)gain) >> 24;"
        pairs = [(old, "output[i] = (int32_t)((uint32_t)output[i] + "
                       "(uint32_t)(((int64_t)y * (int64_t)gain) >> 24));")]
    else:
        raise ValueError("Unexpected msfa source; review narrow-add comparison")
    for old, new in pairs:
        expected = 2 if kind == "fm_op_kernel.cc" else 1
        if text.count(old) != expected:
            raise ValueError("Unexpected msfa addition; review exact arithmetic")
        text = text.replace(old, new)
    return text


def narrow_msfa_sine_multiply(text, rom):
    """Use signed32 only after proving the fixed delta-table product bound."""
    if not all(re.search(r"^" + re.escape(line) + r"$", text, re.M) for line in (
            "#define SIN_LG_N_SAMPLES 10", "#define SIN_DELTA")):
        raise ValueError("Unexpected sine lookup dimensions; review product bound")
    table = re.search(r"kSinTab\[2048\] = \{(.*?)\n\};", rom, re.S)
    if not table:
        raise ValueError("Unexpected sine table; review signed32 product bound")
    literals = [x.strip() for x in table[1].split(",") if x.strip()]
    if len(literals) != 2048 or any(not re.fullmatch(r"-?\d+", x) for x in literals):
        raise ValueError("Unexpected sine coefficients; review signed32 product bound")
    values = [int(x) for x in literals]
    if any(not -(1 << 31) <= x < (1 << 31) for x in values) or any(
            abs(x) * 16383 > (1 << 31) - 1 for x in values[::2]):
        raise ValueError("Sine interpolation product exceeds signed32 bound")
    old = "((int64_t)dy * (int64_t)lowbits) >> SHIFT"
    if text.count(old) != 1:
        raise ValueError("Unexpected sine product; review exact arithmetic")
    return text.replace(old, "(dy * lowbits) >> SHIFT")


def pair_msfa_sine_load(text):
    """Read the adjacent signed delta/base words without aliasing casts.

    The target's little-endian pi32v2 compiler lowers this fixed memcpy to
    one paired load. Preserve the alternative byte order for host checks.
    Only the private prepared header changes; interpolation is untouched.
    """
    anchors = ('#define SIN_LG_N_SAMPLES 10', '#define SIN_DELTA',
               '  int phase_int = (phase >> (SHIFT - 1)) & ((SIN_N_SAMPLES - 1) << 1);')
    old = '  int dy = sintab[phase_int];\n  int y0 = sintab[phase_int + 1];'
    if text.count(old) != 1 or any(
            not re.search(r"^" + re.escape(anchor) + r"$", text, re.M) for anchor in anchors):
        raise ValueError("Unexpected sine pair layout; review exact word loads")
    new = """  uint64_t pair;
  __builtin_memcpy(&pair, &sintab[phase_int], sizeof(pair));
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  int dy = static_cast<int32_t>(pair >> 32);
  int y0 = static_cast<int32_t>(pair);
#else
  int dy = static_cast<int32_t>(pair);
  int y0 = static_cast<int32_t>(pair >> 32);
#endif"""
    return text.replace(old, new, 1)


def unroll_msfa_pure(text):
    """Annotate only the reviewed pure operator; preserve every sample operation."""
    start = text.find("void FmOpKernel::compute_pure(")
    end = text.find("\n}\n#endif", start)
    if end >= 0:
        end += 2
    if start < 0 or end < 0:
        raise ValueError("Unexpected pure FM kernel; review unrolling")
    body = text[start:end]
    if hashlib.sha256(body.encode()).hexdigest() != "394dd29bcb8f63fcf87f8d37e1feb2cbbbeb4dfb99ab548ebe4cb8d76484d335":
        raise ValueError("Unexpected pure FM kernel; review unrolling")
    loop = "      for (int i = 0; i < N; i++) {"
    if body.count(loop) != 2:
        raise ValueError("Unexpected pure FM loops; review unrolling")
    body = body.replace(loop, "#if defined(__clang__)\n#pragma clang loop unroll_count(2)\n#endif\n" + loop)
    return text[:start] + body + text[end:]


def resampler_slope_definition(definition):
    """Encode float32 base/slope pairs for the existing 768 tap intervals."""
    body = definition.split(" = {", 1)[1].rsplit("};", 1)[0]
    literals = [x.strip() for x in body.split(",") if x.strip()]
    if len(literals) != 769 or any(not re.fullmatch(r"[-+0-9.eE]+f", x) for x in literals):
        raise ValueError("Unexpected kernel coefficients; review slope comparison")
    f32 = lambda x: struct.unpack("<f", struct.pack("<f", x))[0]
    values = [f32(float(x[:-1])) for x in literals]
    pairs = []
    for i, base in enumerate(literals[:-1]):
        # Round the subtraction exactly as the original target expression does.
        slope = f32(f32(values[i + 1] - values[i]) * (1.0 / 65536.0))
        literal = format(slope, ".9g")
        if not any(x in literal for x in ".eE"):
            literal += ".0"
        if f32(float(literal)) != slope:
            raise ValueError("Slope literal failed float32 round trip")
        pairs.append("  " + base + ", " + literal + "f,")
    return ("static const float fm1_resampler_kernel_pairs[(FM1_RESAMPLER_KERNEL_LEN - 1) * 2] = {\n"
            + "\n".join(pairs) + "\n};")

def unroll_resampler_lowpass(text):
    """Expand only the fixed FIR loop, preserving its four float sum chains."""
    pattern = (r'  for \(j = 0; j \+ 4 <= FM1_RESAMPLER_LP_PAIRS; j \+= 4\) \{\n'
               r'(.*?)\n  \}\n'
               r'  for \(; j < FM1_RESAMPLER_LP_PAIRS; \+\+j\) y0 \+= h\[j\] \* '
               r'\(e\[j\] \+ e\[FM1_RESAMPLER_LP_LEN - 1 - j\]\);')
    matches = list(re.finditer(pattern, text, re.S))
    if len(matches) != 1 or any(not re.search(r'^' + re.escape(anchor) + r'\s*(?:/\*.*\*/)?$', text, re.M) for anchor in (
            '#define FM1_RESAMPLER_DELAY 30',
            '#define FM1_RESAMPLER_LP_LEN (4 * FM1_RESAMPLER_DELAY + 3)',
            '#define FM1_RESAMPLER_LP_PAIRS (2 * FM1_RESAMPLER_DELAY + 1)')):
        raise ValueError("Unexpected lowpass loop; review fixed unrolling")
    body = matches[0].group(1)
    expected = '\n'.join(
        f'    y{i} += h[j' + (f' + {i}' if i else '') + '] * (e[j' +
        (f' + {i}' if i else '') + f'] + e[FM1_RESAMPLER_LP_LEN - {i + 1} - j]);'
        for i in range(4))
    if body != expected:
        raise ValueError("Unexpected lowpass sums; preserve evaluation order")
    lines = [f'  y{i % 4} += h[{i}] * (e[{i}] + e[{122 - i}]);'
             for i in range(61)]
    return text[:matches[0].start()] + '\n'.join(lines) + text[matches[0].end():]



def schedule_resampler_intermediate(text):
    """Overlap the two interpolation chains without reassociating either sum."""
    anchor = ("    sb += fm1_resampler_tap_(tb) * *before;\n"
              "    sa += fm1_resampler_tap_(ta) * *after;")
    if text.count(anchor) != 1 or "fm1_resampler_kernel_pairs[(t >> 16) * 2]" not in text:
        raise ValueError("Unexpected intermediate taps; requires exact pre-scaled pairs")
    body = '''    const float *kb = &fm1_resampler_kernel_pairs[(tb >> 16) * 2];
    const float *ka = &fm1_resampler_kernel_pairs[(ta >> 16) * 2];
    float wb = (float)(tb & 0xFFFFu), wa = (float)(ta & 0xFFFFu);
    __asm__ volatile("" : "+r"(wb), "+r"(wa));
    wb = wb * kb[1]; wa = wa * ka[1];
    __asm__ volatile("" : "+r"(wb), "+r"(wa));
    wb = kb[0] + wb; wa = ka[0] + wa;
    __asm__ volatile("" : "+r"(wb), "+r"(wa));
    wb = wb * *before; wa = wa * *after;
    __asm__ volatile("" : "+r"(wb), "+r"(wa));
    sb += wb; sa += wa;
    __asm__ volatile("" : "+r"(sb), "+r"(sa));'''
    return text.replace(anchor, body, 1)


def schedule_resampler_lowpass(text):
    """Group independent FIR work; preserve coefficients and four sum chains."""
    expected = "\n".join(f"  y{i % 4} += h[{i}] * (e[{i}] + e[{122-i}]);" for i in range(61))
    if text.count(expected) != 1:
        raise ValueError("Unexpected expanded lowpass; review scheduling")
    lines = []
    for j in range(0, 60, 4):
        lines.append("  {")
        for k in range(4):
            lines.append(f"    float p{k} = e[{j+k}] + e[{122-j-k}];")
        # Empty read/write operands constrain scheduling without CPU operations.
        # Consume each group before the next to avoid retaining/spilling all taps.
        lines.append('    __asm__ volatile("" : "+r"(p0), "+r"(p1), "+r"(p2), "+r"(p3));')
        for k in range(4):
            lines.append(f"    float m{k} = h[{j+k}] * p{k};")
        lines.append('    __asm__ volatile("" : "+r"(m0), "+r"(m1), "+r"(m2), "+r"(m3));')
        for k in range(4):
            lines.append(f"    y{k} += m{k};")
        lines.append('    __asm__ volatile("" : "+r"(y0), "+r"(y1), "+r"(y2), "+r"(y3));')
        lines.append("  }")
    lines.append("  y0 += h[60] * (e[60] + e[62]);")
    return text.replace(expected, "\n".join(lines), 1)


def unroll_vcf_samples(text):
    """Request two-way scheduling without changing sample/filter operations."""
    anchor = "  for (size_t i = 0; i < size; ++i) {"
    if (text.count("void VirtualAnalogVCFEngine::Render(") != 1 or
            text.count(anchor) != 1 or "#pragma clang loop" in text or "#pragma GCC unroll" in text):
        raise ValueError("Unexpected VCF sample loop; review unroll comparison")
    directive = ("#if defined(__clang__)\n#pragma clang loop unroll_count(2)\n"
                 "#elif defined(__GNUC__)\n#pragma GCC unroll 2\n#endif\n")
    return text.replace(anchor, directive + anchor, 1)


def reuse_oscillator_slopes(s):
    """Split private oscillator loops; retain every rounded PWM step."""
    signature='''  template<bool enable_sync, bool output_phase>
  void Render(
      float master_frequency,
      float frequency,
      float pw,
      float waveshape,
      float phase_modulation_amount,
      float* out,
      size_t size) {'''
    if s.count(signature) != 1 or "RenderWithPW" in s:
        raise ValueError("Unexpected oscillator loop; review reciprocal reuse")
    dispatch='''
    float limited_frequency = std::min(frequency, kMaxFrequency);
    float target_pw = pw;
    if (limited_frequency >= 0.25f) target_pw = 0.5f;
    else CONSTRAIN(target_pw, limited_frequency * 2.0f,
                   1.0f - 2.0f * limited_frequency);
    const float step = size ? (target_pw - pw_) / static_cast<float>(size) : 0.0f;
    if (size && pw_ > 0.0f && pw_ < 1.0f && pw_ + step == pw_) {
      RenderWithPW<enable_sync, output_phase, true>(master_frequency, frequency,
          pw, waveshape, phase_modulation_amount, out, size);
    } else {
      RenderWithPW<enable_sync, output_phase, false>(master_frequency, frequency,
          pw, waveshape, phase_modulation_amount, out, size);
    }
  }

'''
    body=signature.replace('template<bool enable_sync, bool output_phase>',
                           'template<bool enable_sync, bool output_phase, bool fixed_pw>').replace('  void Render(', '  void RenderWithPW(')
    s=s.replace(signature,signature+dispatch+body,1)
    anchor='    float next_sample = next_sample_;'
    divisions='      const float slope_up = 1.0f / (pw);\n      const float slope_down = 1.0f / (1.0f - pw);'
    if s.count(anchor) != 1 or s.count(divisions) != 1:
        raise ValueError("Unexpected oscillator loop; review reciprocal reuse")
    setup='''    const float fixed_up = fixed_pw ? 1.0f / pw_ : 0.0f;
    const float fixed_down = fixed_pw ? 1.0f / (1.0f - pw_) : 0.0f;

'''
    return s.replace(anchor,setup+anchor,1).replace(divisions,'''      const float slope_up = fixed_pw ? fixed_up : 1.0f / (pw);
      const float slope_down = fixed_pw ? fixed_down : 1.0f / (1.0f - pw);''',1)


def instrument_vcf_profile(text):
    """Observe oscillator/filter sections in the private VCF copy only."""
    first = "  oscillator_.Render(f0, pw, shape, out, size);"
    last = "  sub_oscillator_.Render(f0 * 0.501f, 0.5f, 1.0f, aux, size);"
    end = "    aux[i] = SoftClip(hp * gain);\n  }\n}"
    if (text.count("void VirtualAnalogVCFEngine::Render(") != 1 or
            any(text.count(a) != 1 for a in (first, last, end)) or
            "lunar_devkit_engine_profile" in text):
        raise ValueError("Unexpected VCF sections; review detail profiling")
    text = text.replace(first, "  lunar_devkit_engine_profile(4, size, 1);\n" + first, 1)
    text = text.replace(last, last + "\n  lunar_devkit_engine_profile(4, size, 0);\n"
                        "  lunar_devkit_engine_profile(5, size, 1);", 1)
    text = text.replace(end, end[:-1] + "  lunar_devkit_engine_profile(5, size, 0);\n}", 1)
    return ('extern "C" void lunar_devkit_engine_profile(unsigned, unsigned, int);\n' + text)


def instrument_engine_profile(text, engine):
    """Observe generation/pop in private copies without changing their math."""
    if engine not in (0, 1):
        raise ValueError("Unexpected engine profile ID")
    anchors = ("          RenderBlock();", "fm1_resampler_pop(&resampler_);")
    if any(text.count(anchor) != 1 for anchor in anchors):
        raise ValueError("Unexpected engine render loop; review detail profiling")
    text = text.replace(anchors[0],
        f"          lunar_devkit_engine_profile({engine * 2}, kBlockSize, 1);\n" + anchors[0] +
        f"\n          lunar_devkit_engine_profile({engine * 2}, kBlockSize, 0);", 1)
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if anchors[1] in line:
            lines[i] = (f"      lunar_devkit_engine_profile({engine * 2 + 1}, 1, 1);\n" + line +
                        f"      lunar_devkit_engine_profile({engine * 2 + 1}, 1, 0);\n")
            break
    return ('extern "C" void lunar_devkit_engine_profile(unsigned, unsigned, int);\n'
            + ''.join(lines))



def instrument_prep_profile(text, planner=False):
    """Observe existing C calls in private copies, preserving their order."""
    signature = "void mod_plan_build(" if planner else "static void play_on("
    functions = re.findall(re.escape(signature) + r"[^\n]+\{.*?\n\}", text, re.S)
    if len(functions) != 1:
        raise ValueError("Unexpected note/planner definition; review preparation profiling")
    original = functions[0]
    body = original
    if planner:
        if re.search(r"\breturn\b", body):
            raise ValueError("Planner has an early return; review preparation profiling")
        at = body.index("{") + 1
        body = body[:at] + "\n  lunar_devkit_prep_profile(7, 1);" + body[at:]
        body = body[:-2] + "\n  lunar_devkit_prep_profile(7, 0);\n}"
    else:
        anchors = (
            (4, "if (s->e && s->e->note_on) s->e->note_on(s->self, (uint8_t)note, (uint8_t)velocity);"),
            (5, "fm1_mod_live_sound_note(a->mod, (unsigned)sound, (uint8_t)note, (uint8_t)velocity);"),
            (6, "n = fm1_mod_voice_start(a->mod, (unsigned)sound, (uint8_t)note, w, FM1_MOD_VDESTS + 1u);"),
        )
        for region, call in anchors:
            if body.count(call) != 1:
                raise ValueError("Unexpected note call; review preparation profiling")
            # Region4 includes the original null guard; calls/order unchanged.
            wrapped = (f"lunar_devkit_prep_profile({region}, 1);\n    " + call +
                       f"\n    lunar_devkit_prep_profile({region}, 0);")
            body = body.replace(call, wrapped, 1)
    text = text.replace(original, body, 1)
    if not planner:
        functions = re.findall(r"static void render_sounds\([^\n]+\{.*?\n\}", text, re.S)
        if len(functions) != 1 or re.search(r"\breturn\b", functions[0]):
            raise ValueError("Unexpected sound dispatch definition; review preparation profiling")
        original = functions[0]
        body = original
        for region, call in (
            (8, "seq_flush(a);"),
            (9, "a->seq_last_n = fm1_seq_host_advance(&a->seq_host, n);"),
            (10, "fm1_seq_host_dispatch_slots_ticks(&a->seq_host, n, slot, FM1_APP_SOUNDS, &hook);"),
        ):
            if body.count(call) != 1:
                raise ValueError("Unexpected sound dispatch call; review preparation profiling")
            body = body.replace(call,
                f"lunar_devkit_prep_profile({region}, 1);\n    " + call +
                f"\n    lunar_devkit_prep_profile({region}, 0);", 1)
        anchor = "  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {\n    float *b = a->mix[k];"
        if body.count(anchor) != 1:
            raise ValueError("Unexpected sound mixing loop; review preparation profiling")
        body = body.replace(anchor, "  lunar_devkit_prep_profile(11, 1);\n" + anchor, 1)
        body = body[:-2] + "\n  lunar_devkit_prep_profile(11, 0);\n}"
        text = text.replace(original, body, 1)
    return "extern void lunar_devkit_prep_profile(unsigned, int);\n" + text


DISPATCH_PROFILE_CALLS = {
    "engines/seq/seq_host.c": (
        ("void fm1_seq_host_dispatch_slots_ticks", ((12, "mfx_begin(h, frames, 0);"),)),
        ("static void play_slots_hook", ((13, "tf = hk->begin(hk->ctx, frames, n && slots[0].sink ? slots[0].sink->engine : NULL, bpm, playing);"),)),
        ("static uint32_t run_tick_slots", ((14, "const uint32_t nw = hk->tick(hk->ctx, tf, &w, &next);"),)),
    ),
    "engines/mod/mod_glue.c": (
        ("static uint32_t glue_tick", (
            (15, "const uint32_t n = fm1_mod_tick(g->mod, frame, &wr);"),
            (16, "nv = fm1_mod_voice_writes(g->mod, g->vw, sizeof(g->vw) / sizeof(g->vw[0]));"),
            (21, "if (nv && g->voiced) g->voiced(g->ctx, frame, g->vw, nv);"),
            (22, "if (g->ticked) g->ticked(g->ctx, frame, wr, n);"),
            (23, "k = voice_hook_writes(g, nv, k);"),
        )),
    ),
    "engines/mod/mod_core.c": (
        ("uint32_t fm1_mod_tick", (
            (17, "take_system(m);"),
            (18, "for (i = 0; i < m->plan.n_order; ++i) run_module(m, m->plan.order[i], &tp);"),
            (19, "write_sinks(m);"),
            (20, "run_voices(m, &tp);"),
        )),
    ),
}


def instrument_dispatch_profile(text, functions):
    """Observe original calls in private sources; never reorder their work."""
    for signature, calls in functions:
        matches = re.findall(r'^' + re.escape(signature) + r'\([^;]*?\) \{.*?^\}', text, re.M | re.S)
        if len(matches) != 1:
            raise ValueError("Unexpected dispatch definition; review profiling: " + signature)
        original = matches[0]
        body = original
        for region, call in calls:
            if body.count(call) != 1:
                raise ValueError("Unexpected dispatch call; review profiling: " + call)
            body = body.replace(call, f"lunar_devkit_prep_profile({region}, 1);\n  " + call +
                                f"\n  lunar_devkit_prep_profile({region}, 0);", 1)
        text = text.replace(original, body, 1)
    return "extern void lunar_devkit_prep_profile(unsigned, int);\n" + text


HOOK_RAM_FUNCTIONS = {
    "sim/web/src/fm1_app.c": (b"static uint32_t seq_auto_begin", b"static uint32_t seq_auto_tick"),
    "engines/mod/mod_glue.c": (b"static uint32_t glue_begin", b"static uint32_t glue_tick"),
    "engines/mod/mod_core.c": (b"uint32_t fm1_mod_begin", b"static void run_voices", b"static uint32_t voice_out"),
}


MODULE_RAM_FUNCTIONS = {
    "engines/mod/mod_core.c": (b"static void run_module", b"static void module_params",
                               b"static void module_gates", b"static int module_outputs"),
}


KIND_RAM_FUNCTIONS = {
    "engines/mod/kinds/mod_lfo.c": (b"static void lfo_run", b"static void lfo_process"),
    "engines/mod/kinds/mod_env.c": (b"static void env_run", b"static void env_process"),
    "engines/mod/kinds/mod_chance.c": (b"static void clock_run", b"static void chance_process"),
    "engines/mod/mp_lfo.c": (b"float fm1_mp_lfo_process", b"float fm1_mp_lfo_value"),
    "engines/mod/mp_env.c": (b"float fm1_mp_env_process", b"float fm1_mp_env_value"),
}


EVENT_RAM_FUNCTIONS = {
    "sim/web/src/fm1_app.c": (b"static int seq_auto_target", b"static void seq_auto_base",
                             b"void fm1_app_set_param", b"void fm1_app_unit_set_level",
                             b"static void play_on"),
    "engines/mod/mod_core.c": (b"static void feed_edge", b"static void feed_cv",
                               b"static void note_at",
                               b"static __attribute__((noinline)) void note_window_edge",
                               b"uint32_t fm1_mod_voice_start"),
}


PLAN_RAM_FUNCTIONS = {
    "engines/mod/mod_core.c": (b"static unsigned window_of", b"static void feed_level",
                               b"static void feed_trigger", b"static void feed_rtrg",
                               b"float fm1_mod_set_base"),
    "engines/mod/mod_plan.c": (b"void mod_plan_build",),
}


def place_hook_ram(text, signatures):
    """Place exact existing definitions; refuse drift instead of changing bodies."""
    for signature in signatures:
        matches = re.findall(rb'^' + re.escape(signature) + rb'\([^;]*?\) \{.*?^\}', text, re.M | re.S)
        if len(matches) != 1:
            raise ValueError("Unexpected hook definition; review placement: " + signature.decode())
        wrapped = b'#pragma code_seg(".volatile_ram_code")\n' + matches[0] + b'\n#pragma code_seg()'
        text = text.replace(matches[0], wrapped, 1)
    return text



def queue_insert_callbacks(text, caller_post=False):
    """Move reviewed per-sound post work to its explicitly selected owner."""
    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError("Unexpected queue insert boundary; review: " + old)
        text = text.replace(old, new, 1)
    support = r'''
#if !defined(LUNAR_QUEUE_POST) || defined(LUNAR_QUEUE_DETAIL) || defined(LUNAR_QUEUE_MICRO) || defined(LUNAR_QUEUE_WORKER_DRUMS) || defined(FM1_APP_RENDER_PROFILE)
#error Queue insert scheduling requires its isolated outer-profile-only mode
#endif
struct lunar_post_context { fm1_app_t *app; uint32_t frames; };
static struct lunar_post_context lunar_post;
static void lunar_post_sound(void *context, unsigned sound);
static int lunar_post_layout_full(const fm1_app_t *a) {
  /* Mix buffers are distinct inline arrays. Only these three instance arenas
   * move to CPU1; no selected arena may overlap any other live unit. */
  const int selected[3] = {fm1_app_sound_unit(1), fm1_app_insert_unit(1, 0), fm1_app_insert_unit(1, 1)};
  for (unsigned w = 0; w < 3; ++w) {
    const fm1_app_unit_t *u = &a->unit[selected[w]];
    if (!u->e) { if (!w) return 0; else continue; }
    if (!w && u->value[0] != 0.0f) return 0;
    if (w && (!u->e->id || strcmp(u->e->id, "drive") ||
              u->e->kind != FM1_KIND_AUDIO_FX || !u->e->render || !u->e->set_param || u->e->render_ext)) return 0;
    const uintptr_t p = (uintptr_t)u->self;
    if (!p || u->self != u->mem || !u->bytes || u->bytes > u->cap || u->bytes > UINTPTR_MAX - p) return 0;
    for (unsigned k = 0; k < FM1_APP_UNITS; ++k) {
      const fm1_app_unit_t *v = &a->unit[k];
      if ((int)k == selected[w] || !v->e) continue;
      const uintptr_t q = (uintptr_t)v->self;
      if (!q || !v->bytes || v->bytes > UINTPTR_MAX - q ||
          (p < q + v->bytes && q < p + u->bytes)) return 0;
    }
  }
  return 1;
}
'''
    if caller_post:
        start = support.index("  /* Mix buffers")
        end = support.index("    const uintptr_t p", start)
        support = support[:start] + r'''  /* Fixed fixture only: validate every moved arena before publication.
   * Sound order and shared master effects remain on CPU0 after ACK. */
  const int selected[12] = {
    fm1_app_sound_unit(0), fm1_app_sound_unit(1), fm1_app_sound_unit(2), fm1_app_sound_unit(3),
    fm1_app_insert_unit(0,0), fm1_app_insert_unit(0,1),
    fm1_app_insert_unit(1,0), fm1_app_insert_unit(1,1),
    fm1_app_insert_unit(2,0), fm1_app_insert_unit(2,1),
    fm1_app_insert_unit(3,0), fm1_app_insert_unit(3,1)};
  static const char *const ids[4] = {"dx7", "macro", "drums", "dx7"};
  for (unsigned w = 0; w < 12; ++w) {
    const fm1_app_unit_t *u = &a->unit[selected[w]];
    if (!u->e) { if (w < 4) return 0; else continue; }
    if (w < 4) {
      if (!u->e->id || strcmp(u->e->id, ids[w]) || u->e->kind != FM1_KIND_SOUND) return 0;
      if (w == 1 && u->value[0] != 0.0f) return 0;
    } else {
      const char *id = w < 6 ? "filter" : w < 8 ? "drive" : 0;
      if (!id || !u->e->id || strcmp(u->e->id, id) ||
          u->e->kind != FM1_KIND_AUDIO_FX || !u->e->render || !u->e->set_param || u->e->render_ext) return 0;
    }
''' + support[end:]
        # Compare complete allocated arenas, not only currently used prefixes.
        support = support.replace("u->bytes > UINTPTR_MAX - p", "u->cap > UINTPTR_MAX - p")
        support = support.replace("!v->bytes || v->bytes > UINTPTR_MAX - q", "!v->bytes || v->bytes > v->cap || v->cap > UINTPTR_MAX - q")
        support = support.replace("q + v->bytes && q < p + u->bytes", "q + v->cap && q < p + u->cap")
    support += r"""
/* Engine descriptors are immutable. Cache only the geometry checked above;
 * compare every live unit, including masters that can alias a moved arena.
 * This queue has one active app/owner; a different app never inherits a seal. */
struct lunar_layout_unit {
  const fm1_engine_t *engine;
  void *self;
  unsigned char *mem;
  size_t bytes, cap;
};
static const fm1_app_t *lunar_layout_app;
static struct lunar_layout_unit lunar_layout_units[FM1_APP_UNITS];
static int lunar_post_layout_valid(const fm1_app_t *a) {
  /* Model changes do not alter geometry, so keep this refusal live. */
  if (a->unit[fm1_app_sound_unit(1)].value[0] != 0.0f) return 0;
  if (lunar_layout_app == a) {
    unsigned k;
    for (k = 0; k < FM1_APP_UNITS; ++k) {
      const fm1_app_unit_t *u = &a->unit[k];
      const struct lunar_layout_unit *v = &lunar_layout_units[k];
      if (u->e != v->engine || (u->e && (u->self != v->self ||
          u->mem != v->mem || u->bytes != v->bytes || u->cap != v->cap))) break;
    }
    if (k == FM1_APP_UNITS) return 1;
  }
  /* Invalidate before checking: a failed replacement cannot retain approval. */
  lunar_layout_app = 0;
  if (!lunar_post_layout_full(a)) return 0;
  for (unsigned k = 0; k < FM1_APP_UNITS; ++k) {
    const fm1_app_unit_t *u = &a->unit[k];
    struct lunar_layout_unit *v = &lunar_layout_units[k];
    v->engine = u->e; v->self = u->self; v->mem = u->mem;
    v->bytes = u->bytes; v->cap = u->cap;
  }
  lunar_layout_app = a;
  return 1;
}
"""
    support = ("#ifndef LUNAR_QUEUE_CALLER_POST\n" if caller_post else "#ifdef LUNAR_QUEUE_CALLER_POST\n") + "#error Generated post scheduling and compile flags disagree\n#endif\n" + support
    replace("static unsigned lunar_queue_recording;", "static unsigned lunar_queue_recording;\n" + support)
    replace("  if (!lunar_renderer_queue_begin()) return 0;", """  if (!lunar_renderer_queue_begin()) return 0;
  if (!lunar_post_layout_valid(a)) {
    lunar_renderer_queue_push(4,0,0,99,0,0,0,0,0,0);
    return 0;
  }""")
    replace("static int lunar_queue_dispatch(void) {", """static int lunar_queue_dispatch(fm1_app_t *a, uint32_t n) {
  lunar_post.app = a;
  lunar_post.frames = n;
  if (!lunar_renderer_queue_post(1, lunar_post_sound, &lunar_post)) return 0;""")
    replace("if (!lunar_queue_dispatch()) return;", "if (!lunar_queue_dispatch(a, n)) return;")
    begin = text.index("    if (a->edit) fm1_edit_meter(a, 3u * (unsigned)k, b, n);")
    end = text.index("    if (!(a->export_sound_mask", begin)
    original = text[begin:end]
    # Detail profiling is rejected above: do not move its CPU0 storage writes.
    body = "\n".join(line for line in original.splitlines() if "QUEUE_DETAIL(" not in line) + "\n"
    body = body.replace("(unsigned)k", "sound").replace("fm1_app_insert_unit(k, j)", "fm1_app_insert_unit((int)sound, j)")
    helper = """static void lunar_post_sound(void *context, unsigned sound) {
  struct lunar_post_context *p = (struct lunar_post_context *)context;
  fm1_app_t *a = p->app;
  const uint32_t n = p->frames;
  float *b = a->mix[sound];
""" + body + "}\n\n"
    text = text[:begin] + ("" if caller_post else "    if (k != 1) {\n" + original + "    }\n") + text[end:]
    replace("static void render_sounds(fm1_app_t *a, uint32_t n, float *out) {", helper + "static void render_sounds(fm1_app_t *a, uint32_t n, float *out) {")
    return text


def queue_engine_callbacks(text):
    """Private fixed-arrangement transformation; all failures retain buffers."""
    anchor = "static void sink_render(void *ctx, float *lr, uint32_t n) {"
    if text.count(anchor) != 1:
        raise ValueError("Unexpected sink structure; review whole-engine queue")
    support = r"""
#include "renderer_queue_bridge.h"
static unsigned lunar_queue_recording;
static int lunar_queue_record(const fm1_app_sink_ctx_t *c, unsigned kind,
    float *lr, unsigned n, unsigned index, unsigned key, unsigned velocity, float value) {
  if (!lunar_queue_recording) return 0;
  const fm1_app_unit_t *u = sound_of(c->a, c->sound);
  /* Once recording, never fall back to a direct engine write on refusal. */
  if (c->sound == 1 && kind == LUNAR_QUEUE_SET_PARAM && index == 0 && value != 0.0f)
    kind = 99;
  lunar_renderer_queue_push(c->sound, u->e, u->self, kind, lr, n, index, key, velocity, value);
  return 1;
}
static int lunar_queue_begin(fm1_app_t *a) {
  static const char *const ids[4] = {"dx7", "macro", "drums", "dx7"};
  if (!lunar_renderer_queue_begin()) return 0;
  for (unsigned s = 0; s < 4; ++s) {
    const fm1_app_unit_t *u = sound_of(a, s);
    if (!u->e || !u->e->id || strcmp(u->e->id, ids[s])) {
      lunar_renderer_queue_push(4, u->e, u->self, 99, 0, 0, 0, 0, 0, 0);
      return 0;
    }
  }
  lunar_queue_recording = 1;
  return 1;
}
static int lunar_queue_dispatch(void) {
  lunar_queue_recording = 0;
  return lunar_renderer_queue_dispatch();
}
"""
    text = text.replace(anchor, support + "\n" + anchor, 1)
    start = text.index(anchor)
    end = text.index("/* An effect over the block", start)
    block = text[start:end]
    # These are alternative callback owners, never nested schedulers. Select the
    # original sink branch before matching queue callbacks, retaining exact drift
    # checks for both the pipeline wrappers and their direct-call fallbacks.
    pipeline_calls = (
        "if(!pipeline_record(c,PIPELINE_RENDER,lr,n,0,0,0,0)) ",
        "if(!pipeline_record(c,PIPELINE_ON,0,0,0,note,velocity,0)) ",
        "if(!pipeline_record(c,PIPELINE_OFF,0,0,0,note,0,0)) ",
        "if(!pipeline_record(c,PIPELINE_PARAM,0,0,index,0,0,value)) ",
        "if(!pipeline_record(c,PIPELINE_BEND,0,0,0,0,0,semitones) && u->e->pitch_bend) ",
        "if(!pipeline_record(c,PIPELINE_NOTE,0,0,index,key,0,offset) && u->e->set_param_note) ",
    )
    replacements = [
        ("u->e->render(u->self, lr, n);",
         "if (!lunar_queue_record(c,LUNAR_QUEUE_RENDER,lr,n,0,0,0,0)) u->e->render(u->self, lr, n);"),
        ("u->e->note_on(u->self, note, velocity);",
         "if (!lunar_queue_record(c,LUNAR_QUEUE_NOTE_ON,0,0,0,note,velocity,0)) u->e->note_on(u->self, note, velocity);"),
        ("u->e->note_off(u->self, note);",
         "if (!lunar_queue_record(c,LUNAR_QUEUE_NOTE_OFF,0,0,0,note,0,0)) u->e->note_off(u->self, note);"),
        ("u->e->set_param(u->self, index, value);",
         "if (!lunar_queue_record(c,LUNAR_QUEUE_SET_PARAM,0,0,index,0,0,value)) u->e->set_param(u->self, index, value);"),
        ("if (u->e->pitch_bend) u->e->pitch_bend(u->self, semitones);",
         "if (!lunar_queue_record(c,LUNAR_QUEUE_BEND,0,0,0,0,0,semitones) && u->e->pitch_bend) u->e->pitch_bend(u->self, semitones);"),
        ("if (u->e->set_param_note) u->e->set_param_note(u->self, key, index, offset);",
         "if (!lunar_queue_record(c,LUNAR_QUEUE_SET_NOTE,0,0,index,key,0,offset) && u->e->set_param_note) u->e->set_param_note(u->self, key, index, offset);")]
    for (old, new), pipeline in zip(replacements, pipeline_calls):
        direct = old
        if old.startswith("if ("):
            direct = old.split(") ", 1)[1]
        wrapped = "#ifdef FM1_APP_RENDER_PIPELINE\n  " + pipeline + direct + "\n#else\n  " + old + "\n#endif"
        if block.count(wrapped) != 1:
            raise ValueError("Unexpected pipeline callback; review queue: " + old)
        block = block.replace(wrapped, old, 1)
        if block.count(old) != 1:
            raise ValueError("Unexpected engine callback; review queue: " + old)
        block = block.replace(old, new, 1)
    text = text[:start] + block + text[end:]
    # Retain the ordinary mutation guard when excluding the pipeline header.
    header_start = text.index("#ifdef FM1_APP_RENDER_PIPELINE\n")
    header_end = text.index("#endif\n\n#include <limits.h>", header_start) + len("#endif\n")
    header = text[header_start:header_end]
    if not header.endswith("#else\n#define PIPELINE_GUARD(x) ((void)0)\n#endif\n"):
        raise ValueError("Unexpected pipeline guard; review queue")
    text = text[:header_start] + "#define PIPELINE_GUARD(x) ((void)0)\n" + text[header_end:]
    # Remove the three pipeline-only declarations/bodies too: they contain
    # intentionally duplicated dispatch/profiling anchors that are not queue code.
    lines, selected, depth, removed = text.splitlines(keepends=True), [], 0, 0
    for line in lines:
        directive = line.strip()
        if not depth and directive == "#ifdef FM1_APP_RENDER_PIPELINE":
            depth, removed = 1, removed + 1
        elif depth:
            if re.match(r"#if(?:def|ndef)?\b", directive):
                depth += 1
            elif directive == "#endif":
                depth -= 1
            elif depth == 1 and re.match(r"#(?:else|elif)\b", directive):
                raise ValueError("Unexpected pipeline alternative; review queue")
        else:
            selected.append(line)
    if depth or removed != 3:
        raise ValueError("Unexpected pipeline bodies; review queue")
    text = "".join(selected)
    text = ("#ifdef FM1_APP_RENDER_PIPELINE\n"
            "#error Whole-engine queue cannot share pipeline callback ownership\n"
            "#endif\n" + text)
    old = "    fm1_seq_host_dispatch_slots_ticks(&a->seq_host, n, slot, FM1_APP_SOUNDS, &hook);"
    if text.count(old) != 1:
        raise ValueError("Unexpected dispatcher; review queue")
    text = text.replace(old, "    if (!lunar_queue_begin(a)) return;\n" + old +
                        "\n    if (!lunar_queue_dispatch()) return;", 1)
    old = "static void render_sounds(fm1_app_t *a, uint32_t n, float *out) {"
    if text.count(old) != 1:
        raise ValueError("Unexpected sound block entry; review queue")
    text = text.replace(old, old + "\n  if (!a->seq) {\n"
        "    if (lunar_queue_begin(a)) lunar_renderer_queue_push(4,0,0,99,0,0,0,0,0,0);\n"
        "    return;\n  }", 1)
    old = "  render_sounds(a, n, out);"
    if text.count(old) != 1:
        raise ValueError("Unexpected sound block; review queue failure propagation")
    text = text.replace(old, old + "\n  if (lunar_renderer_queue_error()) return NULL;", 1)
    # Exact source anchors keep measurements attached to the reviewed operations.
    detail_pairs = [
        ("static void render_sounds(fm1_app_t *a, uint32_t n, float *out) {",
         "static void render_sounds(fm1_app_t *a, uint32_t n, float *out) {\n  QUEUE_DETAIL(0, 1);"),
        ("    if (!lunar_queue_begin(a)) return;",
         "    QUEUE_DETAIL(0, 0);\n    if (!lunar_queue_begin(a)) return;\n    QUEUE_DETAIL(1, 1);"),
        ("    if (!lunar_queue_dispatch()) return;",
         "    QUEUE_DETAIL(1, 0);\n    if (!lunar_queue_dispatch()) return;"),
        ("    if (a->edit) fm1_edit_meter(a, 3u * (unsigned)k, b, n);   /* telemetry, read only */",
         "    QUEUE_DETAIL(2, 1);\n    if (a->edit) fm1_edit_meter(a, 3u * (unsigned)k, b, n);   /* telemetry, read only */"),
        ("    apply_mix_level(a, (unsigned)k, b, n);\n    if (a->edit)",
         "    QUEUE_DETAIL(2, 0);\n    QUEUE_DETAIL(3, 1);\n    apply_mix_level(a, (unsigned)k, b, n);\n    if (a->edit)"),
        ("    if (!(a->export_sound_mask & (1u << k))) continue;",
         "    if (!(a->export_sound_mask & (1u << k))) { QUEUE_DETAIL(3, 0); continue; }"),
        ("    first = 0;\n  }\n  if (first)",
         "    first = 0;\n    QUEUE_DETAIL(3, 0);\n  }\n  if (first)"),
    ]
    for stage, region in [("MASTERS", 4), ("AMP", 5), ("LIMITER", 6), ("SCOPE", 7), ("UI", 8)]:
        for entering in (0, 1):
            old = f"  PROFILE_STAGE(FM1_APP_PROFILE_{stage}, n, {entering});"
            detail_pairs.append((old, old + f"\n  QUEUE_DETAIL({region}, {entering});"))
    for old, new in detail_pairs:
        if text.count(old) != 1:
            raise ValueError("Unexpected CPU0 detail boundary; review queue: " + old)
        text = text.replace(old, new, 1)
    text = """#ifdef LUNAR_QUEUE_DETAIL
#include "renderer_queue_bridge.h"
#define QUEUE_DETAIL(region, entering) lunar_renderer_queue_detail_mark(region, entering)
#else
#define QUEUE_DETAIL(region, entering) ((void)0)
#endif
""" + text
    return text

def queue_micro_callbacks(text, modulation=False):
    """CPU0 subsets: command recording, app DSP, and control hooks.

    Keep this bank independent of the enclosing detail bank: its intervals are
    mutually exclusive, but overlap the existing recording/inserts/masters.
    """
    pairs = [
        ("  const fm1_app_unit_t *u = sound_of(c->a, c->sound);\n  /* Once recording,",
         "  const unsigned micro_kind = kind;\n  QUEUE_MICRO(micro_kind, 1);\n  const fm1_app_unit_t *u = sound_of(c->a, c->sound);\n  /* Once recording,"),
        ("  lunar_renderer_queue_push(c->sound, u->e, u->self, kind, lr, n, index, key, velocity, value);",
         "  lunar_renderer_queue_push(c->sound, u->e, u->self, kind, lr, n, index, key, velocity, value);\n  QUEUE_MICRO(micro_kind, 0);"),
        ("      fm1_fx_render(u->e, u->self, out, cur, f, &b);",
         "      QUEUE_MICRO(6u + (unsigned)unit, 1);\n      fm1_fx_render(u->e, u->self, out, cur, f, &b);\n      QUEUE_MICRO(6u + (unsigned)unit, 0);"),
        ("  if (cur < n) fm1_fx_render(u->e, u->self, out, cur, n, &b);",
         "  if (cur < n) {\n    QUEUE_MICRO(6u + (unsigned)unit, 1);\n    fm1_fx_render(u->e, u->self, out, cur, n, &b);\n    QUEUE_MICRO(6u + (unsigned)unit, 0);\n  }"),
    ]
    for old, new in pairs:
        if text.count(old) != 1:
            raise ValueError("Unexpected queue micro boundary; review: " + old)
        text = text.replace(old, new, 1)
    # The declaration follows app headers so the unit-count assertion is real.
    anchor = 'static unsigned lunar_queue_recording;'
    if text.count(anchor) != 1:
        raise ValueError("Unexpected queue micro support")
    text = text.replace(anchor, """#ifdef LUNAR_QUEUE_MICRO
#define QUEUE_MICRO(region, entering) lunar_renderer_queue_micro_mark(region, entering)
typedef char lunar_micro_units_match[FM1_APP_UNITS + 12 == LUNAR_QUEUE_MICROS ? 1 : -1];
#else
#define QUEUE_MICRO(region, entering) ((void)0)
#endif
""" + anchor, 1)
    if modulation:
        return text  # Internal stages replace hooks 20–25; never nest this flat bank.
    # Wrap the hook boundary rather than its implementation: every early return
    # is paired, and the dispatcher still consumes exactly the original result.
    hooks = [
        ("begin", "uint32_t", "void *ctx, uint32_t frames, const fm1_engine_t *engine, uint32_t bpm, int playing", "ctx, frames, engine, bpm, playing"),
        ("event", "void", "void *ctx, uint32_t frame, const fm1_seq_ev_t *e, int to_engine", "ctx, frame, e, to_engine"),
        ("lock", "float", "void *ctx, uint16_t index, float value", "ctx, index, value"),
        ("tick", "uint32_t", "void *ctx, uint32_t frame, const fm1_seq_hook_write_t **w, uint32_t *next", "ctx, frame, w, next"),
        ("lock_slot", "float", "void *ctx, unsigned slot, uint16_t index, float value", "ctx, slot, index, value"),
        ("note_on", "uint32_t", "void *ctx, uint32_t frame, unsigned slot, uint8_t key, const fm1_seq_hook_write_t **w", "ctx, frame, slot, key, w"),
    ]
    wrappers = []
    for region, (name, result, params, args) in enumerate(hooks, 20):
        call = f"seq_auto_{name}({args})"
        statement = f"{call};" if result == "void" else f"{result} result = {call};"
        returned = "" if result == "void" else "  return result;\n"
        wrappers.append(f"static {result} lunar_micro_{name}({params}) {{\n"
                        f"  QUEUE_MICRO({region}, 1);\n  {statement}\n"
                        f"  QUEUE_MICRO({region}, 0);\n{returned}}}\n")
    anchor = "static void render_sounds("
    if text.count(anchor) != 1:
        raise ValueError("Unexpected queue control wrapper location")
    text = text.replace(anchor, "\n".join(wrappers) + "\n" + anchor, 1)
    original = ("const fm1_seq_hook_t hook = { a, seq_auto_begin, seq_auto_event, seq_auto_lock,\n"
                "                                 seq_auto_tick, seq_auto_lock_slot, seq_auto_note_on };")
    replacement = "const fm1_seq_hook_t hook = { a, " + ", ".join(f"lunar_micro_{name}" for name, *_ in hooks) + " };"
    if text.count(original) != 1:
        raise ValueError("Unexpected queue control hook table")
    text = text.replace(original, replacement, 1)
    return text

def queue_modulation_micro(text, unit, modules=False):
    """Prepared-only, mutually exclusive CPU0 modulation subsets in slots 20–25.

    No runtime state or array growth: the existing hook wrapper bank is replaced.
    Global modules include parameter/gate preparation and output sanitation.
    """
    if "QUEUE_MOD_MICRO" in text:
        raise ValueError("Modulation micro boundary already instrumented")
    if modules and unit == "glue":
        return text  # Global-module components own the flat bank in this mode.
    if modules and unit == "core":
        start = "static void run_module(fm1_mod_t *m, unsigned pos, const fm1_mod_transport_t *tp) {"
        if text.count(start) != 1:
            raise ValueError("Unexpected module micro function boundary")
        begin = text.index(start)
        end = text.index("\n}", begin) + 2
        body = text[begin:end]
        stages = (
            (21, "  module_params(m, pos, kd, m->peff[pos]);"),
            (22, "  module_gates(m, pos, kd, gin, &m->gin_level[pos]);"),
            (24, "  kd->process(instance(m, pos), &io);"),
            (25, "  module_outputs(m, kd, out, gout, prev_end, NULL);"),
        )
        for region, old in stages:
            if body.count(old) != 1:
                raise ValueError("Unexpected module micro boundary; review: " + old)
            body = body.replace(old, f"  QUEUE_MOD_MICRO({region}, 1);\n{old}\n  QUEUE_MOD_MICRO({region}, 0);", 1)
        # Preparation between gate inputs and process is distinct from both.
        body = body.replace("  QUEUE_MOD_MICRO(22, 0);", "  QUEUE_MOD_MICRO(22, 0);\n  QUEUE_MOD_MICRO(23, 1);", 1)
        body = body.replace("  QUEUE_MOD_MICRO(24, 1);", "  QUEUE_MOD_MICRO(23, 0);\n  QUEUE_MOD_MICRO(24, 1);", 1)
        text = text[:begin] + body + text[end:]
    boundaries = {
        "core": [
            ("  take_system(m);", "  QUEUE_MOD_MICRO(20, 1);\n  take_system(m);\n  QUEUE_MOD_MICRO(20, 0);"),
            ("  for (i = 0; i < m->plan.n_order; ++i) run_module(m, m->plan.order[i], &tp);",
             "  QUEUE_MOD_MICRO(21, 1);\n  for (i = 0; i < m->plan.n_order; ++i) run_module(m, m->plan.order[i], &tp);\n  QUEUE_MOD_MICRO(21, 0);"),
            ("  write_sinks(m);", "  QUEUE_MOD_MICRO(22, 1);\n  write_sinks(m);\n  QUEUE_MOD_MICRO(22, 0);"),
            ("  run_voices(m, &tp);", "  QUEUE_MOD_MICRO(23, 1);\n  run_voices(m, &tp);\n  QUEUE_MOD_MICRO(23, 0);"),
        ],
        "glue": [
            ("  for (i = 0; i < n; ++i) {\n    const fm1_mod_write_t *x = &wr[i];",
             "  QUEUE_MOD_MICRO(24, 1);\n  for (i = 0; i < n; ++i) {\n    const fm1_mod_write_t *x = &wr[i];"),
            ("  g->sound_writes += k;", "  g->sound_writes += k;\n  QUEUE_MOD_MICRO(24, 0);\n  QUEUE_MOD_MICRO(25, 1);"),
            ("  k = voice_hook_writes(g, nv, k);", "  k = voice_hook_writes(g, nv, k);\n  QUEUE_MOD_MICRO(25, 0);"),
        ],
    }
    if unit not in boundaries:
        raise ValueError("Unknown modulation micro source")
    if modules:
        boundaries["core"] = boundaries["core"][:1]  # System intake only; no enclosing module timer.
    for old, new in boundaries[unit]:
        if text.count(old) != 1:
            raise ValueError("Unexpected modulation micro boundary; review: " + old)
        text = text.replace(old, new, 1)
    return ("#ifdef LUNAR_QUEUE_MICRO\n#include \"renderer_queue_bridge.h\"\n"
            "#define QUEUE_MOD_MICRO(r, e) lunar_renderer_queue_micro_mark(r, e)\n"
            "#else\n#define QUEUE_MOD_MICRO(r, e) ((void)0)\n#endif\n" + text)


def drums_ready_conversion(header, drums):
    """Specialize only the prepared Drums conversion path; retain checked fallback.

    The caller must satisfy need before the unchecked pop and may push only
    min(need, pending) inputs. Keep the FIR body literally unchanged and share
    its noinline kernel between the checked and ready entry in this TU.
    """
    begin = "static inline float fm1_resampler_pop(fm1_resampler_t *r) {"
    end = "\n/* Array form:"
    checks = ("  if (r->mode != FM1_RESAMPLER_CONVERT) {\n"
              "    if (!r->held) return 0.0f;\n"
              "    r->held = 0;\n"
              "    return r->in[0];\n  }\n"
              "  if (fm1_resampler_needed(r)) return 0.0f;\n")
    anchor = "  void Render(float *out_lr, uint32_t frames) {\n"
    reviewed_render = r"""  void Render(float *out_lr, uint32_t frames) {
    for (uint32_t f = 0; f < frames; ++f) {
      uint32_t need = fm1_resampler_needed(&resampler_);
      while (need) {
        if (!pending_) {
          RenderBlock();
          pending_ = kBlockSize;
        }
        const uint32_t took = fm1_resampler_push(
            &resampler_, &mix_[kBlockSize - pending_],
            need < pending_ ? need : static_cast<uint32_t>(pending_));
        pending_ -= took;
        need -= took;
      }
      out_lr[2 * f] = out_lr[2 * f + 1] = fm1_resampler_pop(&resampler_);
    }
  }"""
    reviewed_input = r"""static inline uint32_t fm1_resampler_needed(const fm1_resampler_t *r) {
  int64_t v;
  if (r->mode != FM1_RESAMPLER_CONVERT) return r->mode == FM1_RESAMPLER_PASS && !r->held;
  v = r->rel + r->lead;
  return v > 0 ? (uint32_t)(((uint64_t)v + 0xFFFFFFFFu) >> 32) : 0u;
}

/* Takes up to n samples, never more than fm1_resampler_needed(r); returns
 * how many it took. */
static inline uint32_t fm1_resampler_push(fm1_resampler_t *r, const float *in, uint32_t n) {
  uint32_t i, need = fm1_resampler_needed(r);
  if (n > need) n = need;
  if (r->mode != FM1_RESAMPLER_CONVERT) {
    if (n) { r->in[0] = in[0]; r->held = 1; }
    return n;
  }
  for (i = 0; i < n; ++i) {
    r->in[r->in_w] = r->in[r->in_w + FM1_RESAMPLER_IN_CAP] = in[i];
    if (++r->in_w == FM1_RESAMPLER_IN_CAP) r->in_w = 0;
  }
  r->rel -= (int64_t)n << 32;
  return n;
}
"""
    if drums.count(reviewed_render) != 1 or header.count(reviewed_input) != 1:
        raise ValueError("Unexpected Drums readiness boundary; review input/render bodies")
    if (header.count(begin) != 1 or header.count(end) != 1 or
            header.count(checks) != 1 or drums.count(anchor) != 1 or
            drums.count('#include "fm1_resampler.h"') != 1):
        raise ValueError("Unexpected Drums readiness boundary; review specialization")
    a, b = header.index(begin), header.index(end)
    original = header[a:b]
    if checks not in original:
        raise ValueError("Unexpected resampler readiness checks")
    ready_name = "fm1_resampler_ready_convert"
    ready = original.replace(begin, "static __attribute__((noinline)) float " + ready_name +
                             "(fm1_resampler_t *r) {", 1).replace(checks, "", 1)
    checked = (begin + "\n" + checks + "  return " + ready_name + "(r);\n}\n")
    helpers = r"""
/* Conversion-only entries: caller established CONVERT and input readiness.
 * Never call these with PASS/OFF, an overlong push, or an unready pop. */
static inline uint32_t fm1_resampler_needed_convert(const fm1_resampler_t *r) {
  const int64_t v = r->rel + r->lead;
  return v > 0 ? (uint32_t)(((uint64_t)v + 0xFFFFFFFFu) >> 32) : 0u;
}
static inline void fm1_resampler_push_convert(fm1_resampler_t *r, const float *in, uint32_t n) {
  for (uint32_t i = 0; i < n; ++i) {
    r->in[r->in_w] = r->in[r->in_w + FM1_RESAMPLER_IN_CAP] = in[i];
    if (++r->in_w == FM1_RESAMPLER_IN_CAP) r->in_w = 0;
  }
  r->rel -= (int64_t)n << 32;
}
"""
    # Other translation units retain exactly the original checked implementation.
    header = (header[:a] + "#ifdef FM1_DRUMS_READY_CONVERT\n" + helpers + ready + checked +
              "#else\n" + original + "#endif\n" + header[b:])
    loop = r"""    if (resampler_.mode == FM1_RESAMPLER_CONVERT) {
      for (uint32_t f = 0; f < frames; ++f) {
        uint32_t need = fm1_resampler_needed_convert(&resampler_);
        while (need) {
          if (!pending_) { RenderBlock(); pending_ = kBlockSize; }
          const uint32_t took = need < pending_ ? need : static_cast<uint32_t>(pending_);
          fm1_resampler_push_convert(&resampler_, &mix_[kBlockSize - pending_], took);
          pending_ -= took;
          need -= took;
        }
        out_lr[2 * f] = out_lr[2 * f + 1] = fm1_resampler_ready_convert(&resampler_);
      }
      return;
    }
"""
    drums = drums.replace('#include "fm1_resampler.h"',
                          '#define FM1_DRUMS_READY_CONVERT 1\n#include "fm1_resampler.h"', 1)
    return header, drums.replace(anchor, anchor + loop, 1)


def prepare_renderer(sdk, source, out, timing_only=False, profile=False, hot_ram=False, sine_ram=False, resampler_ram=False, cache_tables=False, fx_ram=False, resampler_outline=False, filter_process_ram=False, control_ram=False, plaits_cache=False, resampler_slopes=False, engine_profile=False, resampler_unroll=False, renderer_o3=False, mixer_ram=False, resampler_schedule=False, workload="mixed", dispatch_ram=False, msfa_narrow_adds=False, msfa_sine32=False, msfa_pure_unroll=False, fm6_pair=False, scheduling_probe=False, ui_ram=False, prep_profile=False, hook_ram=False, module_ram=False, kind_ram=False, event_ram=False, plan_ram=False, external_pixels=False, vcf_unroll=False, vcf_profile=False, oscillator_slopes=False, outer_timing_only=False, engine_queue=False, engine_queue_drums=False, engine_queue_profile=False, engine_queue_detail=False, engine_queue_micro=False, engine_queue_mod_micro=False, engine_queue_module_micro=False, engine_queue_insert=False, engine_queue_caller_post=False, resampler_stage1_schedule=False, metadata_ram=False, msfa_sine_pair=False, drums_ready_convert=False, dx7_sine="msfa"):
    if dx7_sine not in ("msfa", "trunc12"):
        raise ValueError("Unknown DX7 sine; choose msfa or trunc12 (engines/Makefile FM1_DX7_SINE)")
    if dx7_sine == "trunc12" and (msfa_sine32 or msfa_sine_pair):
        # Both patch msfa's interpolated lookup; the trunc12 build compiles
        # its own sin.h (engines/mk/msfa.mk), which has no interpolation.
        raise ValueError("Signed32 and paired sine loads patch msfa's interpolated sine; trunc12 has none")
    if engine_queue_caller_post and not engine_queue_insert:
        raise ValueError("Caller post requires guarded queue inserts")
    if engine_queue_insert and (not engine_queue or engine_queue_drums or engine_queue_detail or engine_queue_micro or engine_queue_mod_micro or engine_queue_module_micro):
        raise ValueError("Queue inserts require isolated whole-engine queue with only outer profiling")
    if engine_queue_module_micro and not engine_queue_mod_micro:
        raise ValueError("Module component timing requires modulation micro")
    if engine_queue_mod_micro and not engine_queue_micro:
        raise ValueError("Modulation micro timing requires queue micro")
    if engine_queue_micro and not engine_queue_detail:
        raise ValueError("Queue micro timing requires queue detail")
    if engine_queue_detail and not engine_queue_profile:
        raise ValueError("Queue detail requires queue region profiling")
    if engine_queue_profile and not engine_queue:
        raise ValueError("Queue region timing requires the guarded whole-engine queue")
    if engine_queue_drums and not engine_queue:
        raise ValueError("Worker Drums partition requires the guarded whole-engine queue")
    if engine_queue and (fm6_pair or scheduling_probe):
        raise ValueError("Whole-engine queue must not nest the FM6 worker")
    if engine_queue and not (timing_only and workload == "mixed" and hot_ram and renderer_o3 and outer_timing_only):
        raise ValueError("Whole-engine queue requires mixed timing-only resident O3 outer timing")
    if outer_timing_only and not (timing_only and profile and renderer_o3):
        raise ValueError("Outer-only timing requires timing-only profiled O3 placement")
    if oscillator_slopes and not (timing_only and profile and hot_ram and renderer_o3):
        raise ValueError("Oscillator slope reuse requires timing-only profiled resident O3")
    if vcf_unroll and not (timing_only and profile and hot_ram and renderer_o3):
        raise ValueError("VCF unrolling requires timing-only profiled resident O3")
    if external_pixels and not timing_only:
        raise ValueError("Caller-owned pixels require timing-only preparation; no display/DAC acceptance")
    if plan_ram and not (timing_only and profile and prep_profile and event_ram):
        raise ValueError("Plan placement requires timing-only preparation profiling and resident events")
    if event_ram and not (timing_only and profile and prep_profile and kind_ram):
        raise ValueError("Event placement requires timing-only preparation profiling and resident kinds")
    if kind_ram and not (timing_only and profile and module_ram):
        raise ValueError("Kind placement requires timing-only profiled resident module helpers")
    if module_ram and not (timing_only and profile and hook_ram):
        raise ValueError("Module placement requires timing-only profiled resident hooks")
    if hook_ram and not (timing_only and profile and dispatch_ram):
        raise ValueError("Hook placement requires timing-only profiled resident dispatch")
    if prep_profile and not (timing_only and profile):
        raise ValueError("Preparation profiling requires the timing-only shared profile")
    if ui_ram and not (timing_only and dispatch_ram):
        raise ValueError("UI SRAM requires the timing-only resident dispatch comparison")
    if scheduling_probe and not fm6_pair:
        raise ValueError("Scheduling probe requires the finite timing-only FM6 pair experiment")
    if fm6_pair and not (timing_only and hot_ram and profile):
        raise ValueError("CPU1 FM6 requires timing-only profiled hot code; no DAC acceptance")
    if workload not in ("mixed", "keys"):
        raise ValueError("Unknown renderer workload; choose mixed or keys")
    if msfa_pure_unroll and not (timing_only and hot_ram and msfa_narrow_adds and renderer_o3):
        raise ValueError("Pure FM unrolling requires timing-only hot O3 and narrow additions")
    if msfa_sine_pair and not (timing_only and hot_ram and msfa_sine32):
        raise ValueError("Paired sine loads require timing-only hot signed32 sine")
    if msfa_sine32 and not (timing_only and hot_ram and msfa_narrow_adds):
        raise ValueError("Signed32 sine requires timing-only hot code and narrow additions")
    if msfa_narrow_adds and not (timing_only and hot_ram):
        raise ValueError("Narrow msfa additions require timing-only hot code comparison")
    if profile and not timing_only:
        raise ValueError("Render profiling is worker-only; not an audio acceptance image")
    if hot_ram and not timing_only:
        raise ValueError("Hot SRAM comparison is worker-only until target validation")
    if sine_ram and not (timing_only and hot_ram):
        raise ValueError("Sine SRAM comparison requires timing-only hot code placement")
    if resampler_ram and not (timing_only and hot_ram and sine_ram):
        raise ValueError("Resampler SRAM comparison requires timing-only hot code and sine SRAM")
    if cache_tables and not (timing_only and hot_ram and sine_ram and resampler_ram):
        raise ValueError("Cache table comparison requires timing-only hot code, sine and resampler SRAM")
    if fx_ram and not (timing_only and cache_tables):
        raise ValueError("Effect SRAM comparison requires timing-only cache table placement")
    if resampler_outline and not (timing_only and fx_ram):
        raise ValueError("Outlined resampler comparison requires timing-only resident effects")
    if filter_process_ram and not (timing_only and fx_ram and not resampler_outline):
        raise ValueError("Filter process SRAM requires timing-only resident effects without outlining")
    if control_ram and not (timing_only and filter_process_ram):
        raise ValueError("Control SRAM requires the timing-only resident filter comparison")
    if plaits_cache and not control_ram:
        raise ValueError("Plaits cache tables require the timing-only resident control comparison")
    if resampler_slopes and not plaits_cache:
        raise ValueError("Resampler slopes require the timing-only Plaits cache comparison")
    if engine_profile and not (profile and resampler_slopes):
        raise ValueError("Engine profiling requires timing-only profiled resampler slopes")
    if vcf_profile and not (engine_profile and timing_only and renderer_o3):
        raise ValueError("VCF profiling requires timing-only O3 engine profiling")
    if resampler_unroll and not (resampler_slopes and profile):
        raise ValueError("Lowpass unrolling requires timing-only profiled slopes")
    if renderer_o3 and not resampler_unroll:
        raise ValueError("Renderer O3 comparison requires timing-only profiled lowpass unrolling")
    if metadata_ram and not (timing_only and kind_ram and cache_tables):
        raise ValueError("Resident metadata requires timing-only resident control kinds and tables")
    if drums_ready_convert and not (hot_ram and resampler_unroll and outer_timing_only and not resampler_outline):
        raise ValueError("Drums readiness requires resident unrolled outer-only conversion without outlining")
    if resampler_stage1_schedule and not (resampler_slopes and mixer_ram):
        raise ValueError("Stage-one scheduling requires pre-scaled pairs and resident mixer")
    if resampler_schedule and not mixer_ram:
        raise ValueError("FIR scheduling comparison requires timing-only resident mixer")
    if dispatch_ram and not mixer_ram:
        raise ValueError("Dispatch SRAM requires the timing-only resident mixer comparison")
    if mixer_ram and not renderer_o3:
        raise ValueError("Mixer SRAM requires the timing-only profiled O3 comparison")
    spec = importlib.util.spec_from_file_location("devkit_prepare", source / "tools/jieli/prepare-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Retain reviewed SDK configuration, disabled settings registration,
    # disabled downloader and mandatory UART command receiver.
    module.prepare(sdk, source, out, audio_probe=not timing_only, boot_control=True)
    app = out / "apps/demo/demo_hello"
    # os_api.h specifies four-byte stack units. Shared app setup includes the
    # modulation script parser and UI helpers, unlike the isolated FM6 probe.
    # Measured peak is 5544 bytes. Most comparisons retain a 12 KiB stack;
    # filter placement uses 8 KiB (2648 bytes above that peak) because its
    # 12 KiB allocation failed during startup. Recheck target high-water use.
    # Recovery is already reserved/configured before this allocation.
    main = app / "app_main.c"
    text = main.read_text()
    worker = 'os_task_create(lunar_devkit_worker, NULL, 10, 2048, 0, "lunar_devkit");'
    if text.count(worker) != 1:
        raise ValueError("Unexpected worker creation; review renderer task stack")
    worker_stack_words = 2048 if filter_process_ram else 3072
    parent_priority = 16 if scheduling_probe or engine_queue else 10
    replacement = worker.replace('10, 2048,', f'{parent_priority}, {worker_stack_words},')
    if fm6_pair or engine_queue:
        replacement = replacement.replace('"lunar_devkit"', '"#C0lunar_parent"')
    main.write_text(text.replace(worker, replacement, 1))
    if fm6_pair:
        shutil.copyfile(source / "firmware/devkit/fm6_pair_sdk.h", app / "fm6_pair_sdk.h")
    if engine_queue:
        shutil.copyfile(source / "firmware/devkit/renderer_queue_sdk.h", app / "renderer_queue_sdk.h")
    shutil.copyfile(source / "firmware/devkit/renderer_live.h", app / "renderer_live.h")
    shutil.copyfile(source / "firmware/devkit/renderer_timing.h", app / "renderer_timing.h")
    shutil.copyfile(source / "firmware/devkit/arithmetic_probe.h", app / "arithmetic_probe.h")
    staging = out / "lunar-source"
    for directory in ("engines", "sim/web/src", "sim/web/mk", "firmware/devkit"):
        shutil.copytree(source / directory, staging / directory,
                        ignore=shutil.ignore_patterns("build", "build-*", ".git", "__pycache__", ".DS_Store", "._*"))
    narrow_inputs = {}
    if msfa_narrow_adds:
        # trunc12 replaces msfa's sin.h in the build (engines/mk/msfa.mk), so
        # only the operator kernels' additions apply to it.
        for name in (("sin.h", "fm_op_kernel.cc") if dx7_sine == "msfa" else ("fm_op_kernel.cc",)):
            p = staging / "engines/third_party/msfa" / name
            original = p.read_bytes()
            narrow_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_text(narrow_msfa_adds(original.decode(), name))
    pure_unroll_input = None
    if msfa_pure_unroll:
        p = staging / "engines/third_party/msfa/fm_op_kernel.cc"
        pure_unroll_input = hashlib.sha256(p.read_bytes()).hexdigest()
        p.write_text(unroll_msfa_pure(p.read_text()))
    sine32_input = None
    if msfa_sine32:
        p = staging / "engines/third_party/msfa/sin.h"
        rom = (staging / "engines/src/msfa_rom.cc").read_text()
        sine32_input = hashlib.sha256(rom.encode()).hexdigest()
        p.write_text(narrow_msfa_sine_multiply(p.read_text(), rom))
    sine_pair_input = None
    if msfa_sine_pair:
        p = staging / "engines/third_party/msfa/sin.h"
        sine_pair_input = hashlib.sha256(p.read_bytes()).hexdigest()
        p.write_text(pair_msfa_sine_load(p.read_text()))
    hot_inputs = {}
    if hot_ram:
        # The pinned clang 4 vendor build supports MS code_seg under its
        # existing -fms-extensions flag; modern clang section is ignored.
        # Preserve LTO/arithmetic flags and source bodies. Only prepared private
        # copies change. Constants deliberately stay in XIP in this comparison.
        selected_hot = HOT_RAM_SOURCES + (("engines/src/fx_comp.cc", "engines/src/fx_drive.cc",
                                            "engines/src/fx_echo.cc") if fx_ram else ())
        for name in selected_hot:
            p = staging / name
            original = p.read_bytes()
            hot_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_bytes(b'#pragma code_seg(".volatile_ram_code")\n' + original)
    sine_input = None
    if sine_ram:
        p = staging / "engines/src/msfa_rom.cc"
        original = p.read_bytes()
        # The table the build's sine reads: msfa's 2,048-word delta table or
        # trunc12's 4,096 int16 points, both 8 KiB (engines/src/msfa_rom.cc).
        anchor = (b'extern const int32_t kSinTab[2048] = {' if dx7_sine == "msfa"
                  else b'extern const int16_t kSinTab12[4096] = {')
        if original.count(anchor) != 1:
            raise ValueError("Unexpected sine table definition; review placement")
        sine_input = hashlib.sha256(original).hexdigest()
        p.write_bytes(original.replace(anchor,
            anchor[:-4] + b' __attribute__((section(".volatile_ram"))) = {', 1))
    resampler_input = None
    if resampler_ram:
        # A single external copy avoids spending SRAM once per header user.
        # Keep every coefficient literal and arithmetic operation unchanged.
        p = staging / "engines/include/fm1_resampler.h"
        original = p.read_text()
        resampler_input = hashlib.sha256(p.read_bytes()).hexdigest()
        definitions = []
        for name, length in (("kernel", "FM1_RESAMPLER_KERNEL_LEN"),
                             ("lowpass", "FM1_RESAMPLER_LP_PAIRS + 1")):
            pattern = r"static const float fm1_resampler_" + name + r"\[[^\]]+\] = \{.*?\n\};"
            matches = list(re.finditer(pattern, original, flags=re.S))
            if len(matches) != 1:
                raise ValueError("Unexpected resampler table; review placement")
            definition = matches[0].group()
            original_definition = definition
            table_name = name
            if resampler_slopes and name == "kernel":
                definition = resampler_slope_definition(definition)
                table_name = "kernel_pairs"
                length = "(FM1_RESAMPLER_KERNEL_LEN - 1) * 2"
            definitions.append(definition.replace("static const float", "extern const float", 1)
                               .replace(" = {", ' __attribute__((section(".volatile_ram"))) = {', 1))
            original = original.replace(original_definition,
                "extern const float fm1_resampler_" + table_name + "[" + length + "];", 1)
        # The 51/47 fast path's table (FM1_RESAMPLER_POLY47, engines/resampler.md)
        # is the one Drums and Macro read at Plaits' rate, so it moves with the
        # others: 4,608 bytes more of the same section. It sits under its switch
        # in the header, so its external copy does too.
        pattern = (r"static const float fm1_resampler_poly47\[FM1_RESAMPLER_POLY47_ROWS\]"
                   r"\[FM1_RESAMPLER_POLY47_TAPS\] = \{.*?\n\};")
        matches = list(re.finditer(pattern, original, flags=re.S))
        if len(matches) > 1 or (not matches and "FM1_RESAMPLER_POLY47" in original):
            raise ValueError("Unexpected 51/47 resampler table; review placement")
        if matches:
            definition = matches[0].group()
            definitions.append("#if FM1_RESAMPLER_POLY47\n"
                + definition.replace("static const float", "extern const float", 1)
                .replace(" = {", ' __attribute__((section(".volatile_ram"))) = {', 1)
                + "\n#endif")
            original = original.replace(definition,
                "extern const float fm1_resampler_poly47[FM1_RESAMPLER_POLY47_ROWS]"
                "[FM1_RESAMPLER_POLY47_TAPS];", 1)
        if resampler_slopes:
            anchor = ("  const float *k = &fm1_resampler_kernel[t >> 16];\n"
                      "  return k[0] + (float)(t & 0xFFFFu) * (1.0f / 65536.0f) * (k[1] - k[0]);")
            if original.count(anchor) != 1:
                raise ValueError("Unexpected tap interpolation; review slope comparison")
            original = original.replace(anchor,
                "  const float *k = &fm1_resampler_kernel_pairs[(t >> 16) * 2];\n"
                "  return k[0] + (float)(t & 0xFFFFu) * k[1];", 1)
        p.write_text(original)
        # Macro is always present in this fixed diagnostic; no extra build list.
        p = staging / "engines/src/mi_macro.cc"
        p.write_text(p.read_text() + "\n" + "\n".join(definitions) + "\n")
    cache_link_input = None
    if cache_tables:
        # Use the SDK's existing initialized-data region, without changing
        # cache-way allocation or putting executable code in its rw region.
        p = out / "cpu/wl82/sdk_ld_sfc.c"
        original = p.read_text()
        anchor = "    .cache_ram_data ALIGN(4):\n    {\n"
        if original.count(anchor) != 1:
            raise ValueError("Unexpected cache RAM linker region; review startup copy")
        cache_link_input = hashlib.sha256(p.read_bytes()).hexdigest()
        p.write_text(original.replace(anchor, anchor + "        *(.lunar_cache_tables)\n", 1))
        for name in ("mi_macro.cc", "msfa_rom.cc"):
            p = staging / "engines/src" / name
            original = p.read_text()
            expected = 1
            if name == "mi_macro.cc":
                expected = 3 if "fm1_resampler_poly47[" in original else 2
            attribute = '__attribute__((section(".volatile_ram")))'
            if original.count(attribute) != expected:
                raise ValueError("Unexpected resident table definitions; review cache placement")
            text = original.replace(attribute, '__attribute__((section(".lunar_cache_tables")))')
            if name == "msfa_rom.cc":
                exp2 = "extern const int32_t kExp2Tab[2048] = {"
                if text.count(exp2) != 1:
                    raise ValueError("Unexpected exp2 table definition; review placement")
                text = text.replace(exp2, exp2.replace(" = {", ' __attribute__((section(".lunar_cache_tables"))) = {'), 1)
            p.write_text(text)
    plaits_table_inputs = {}
    if plaits_cache:
        # Relocate only exact definitions in private prepared sources. Preserve
        # the coefficients and external declarations; use existing SDK copying.
        for name, tables in (
            ("engines/third_party/mutable/stmlib/dsp/units.cc",
             ("lut_pitch_ratio_high", "lut_pitch_ratio_low")),
            ("engines/third_party/mutable/plaits/resources.cc", ("lut_sine",)),
        ):
            p = staging / name
            original = p.read_text()
            plaits_table_inputs[name] = hashlib.sha256(p.read_bytes()).hexdigest()
            text = original
            for table in tables:
                anchor = "const float " + table + "[] = {"
                if text.count(anchor) != 1:
                    raise ValueError("Unexpected Plaits table definition; review cache placement")
                text = text.replace(anchor, anchor.replace(" = {",
                    ' __attribute__((section(".lunar_cache_tables"))) = {'), 1)
            p.write_text(text)
    if resampler_outline:
        # Keep both sums, coefficients and evaluation order unchanged. This
        # private code-generation comparison tests register pressure only.
        p = staging / "engines/include/fm1_resampler.h"
        text = p.read_text()
        for name in ("fm1_resampler_intermediate_", "fm1_resampler_pop"):
            anchor = "static inline float " + name + "(fm1_resampler_t *r) {"
            if text.count(anchor) != 1:
                raise ValueError("Unexpected resampler kernel; review outlining")
            text = text.replace(anchor, anchor.replace("static inline", "static __attribute__((noinline))"), 1)
        p.write_text(text)
    filter_process_input = None
    if filter_process_ram:
        p = staging / "engines/src/fx_filter.cc"
        original = p.read_bytes()
        anchor = re.findall(rb'static void FiltProcess\([^\n]+\) \{.*?\n\}', original, re.S)
        if len(anchor) != 1:
            raise ValueError("Unexpected filter process definition; review placement")
        filter_process_input = hashlib.sha256(original).hexdigest()
        wrapped = b'#pragma code_seg(".volatile_ram_code")\n' + anchor[0] + b'\n#pragma code_seg()'
        p.write_bytes(original.replace(anchor[0], wrapped, 1))
    control_inputs = {}
    if control_ram:
        # Only private copies change. Column-zero closing braces delimit these
        # C definitions; reject source drift rather than guessing a new boundary.
        for name, signatures in (
            ("sim/web/src/fm1_app.c", (b"const float *fm1_app_render",) +
             ((b"static void render_fx", b"static void render_sounds") if mixer_ram else ())),
            ("engines/mod/mod_core.c", (b"static float sum_slots", b"uint32_t fm1_mod_tick")),
            ("engines/seq/seq_host.c", (b"void fm1_seq_host_dispatch_slots_ticks",) +
             ((b"static int walk_next", b"static void dispatched", b"static void play_slots_hook") if dispatch_ram else ())),
        ):
            p = staging / name
            original = p.read_bytes()
            control_inputs[name] = hashlib.sha256(original).hexdigest()
            text = original
            for signature in signatures:
                matches = re.findall(rb'^' + re.escape(signature) + rb'\([^;]*?\) \{.*?^\}', text, re.M | re.S)
                if len(matches) != 1:
                    raise ValueError("Unexpected control definition; review placement: " + signature.decode())
                wrapped = b'#pragma code_seg(".volatile_ram_code")\n' + matches[0] + b'\n#pragma code_seg()'
                text = text.replace(matches[0], wrapped, 1)
            p.write_bytes(text)
    hook_inputs = {}
    if hook_ram:
        for name, signatures in HOOK_RAM_FUNCTIONS.items():
            p = staging / name
            original = p.read_bytes()
            hook_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_bytes(place_hook_ram(original, signatures))
    module_inputs = {}
    if module_ram:
        for name, signatures in MODULE_RAM_FUNCTIONS.items():
            p = staging / name
            original = p.read_bytes()
            module_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_bytes(place_hook_ram(original, signatures))
    kind_inputs = {}
    if kind_ram:
        for name, signatures in KIND_RAM_FUNCTIONS.items():
            p = staging / name
            original = p.read_bytes()
            kind_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_bytes(place_hook_ram(original, signatures))
    metadata_inputs = {}
    if metadata_ram:
        # Only descriptors: preserve strings, coefficients and all DSP code.
        for name in (
                "engines/src/msfa_dx7.cc", "engines/src/mi_macro.cc",
                "engines/src/drums.cc", "engines/src/fx_filter.cc",
                "engines/src/fx_drive.cc", "engines/src/fx_echo.cc",
                "engines/src/fx_comp.cc", "engines/mod/kinds/mod_lfo.c",
                "engines/mod/kinds/mod_env.c", "engines/mod/kinds/mod_chance.c"):
            p = staging / name
            original = p.read_text()
            pattern = r"((?:static )?const (?:fm1_param_t|fm1_port_t|fm1_mod_kind_t|fm1_engine_t) \w+(?:\[[^\]]*\])?) = \{"
            expected = 4 if "/kinds/" in name else 2
            if len(re.findall(pattern, original)) != expected:
                raise ValueError("Unexpected metadata definitions: " + name)
            metadata_inputs[name] = hashlib.sha256(p.read_bytes()).hexdigest()
            p.write_text(re.sub(pattern, r'\1 __attribute__((section(".volatile_ram"))) = {', original))
    event_inputs = {}
    if event_ram:
        for name, signatures in EVENT_RAM_FUNCTIONS.items():
            p = staging / name
            original = p.read_bytes()
            event_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_bytes(place_hook_ram(original, signatures))
    plan_inputs = {}
    if plan_ram:
        for name, signatures in PLAN_RAM_FUNCTIONS.items():
            p = staging / name
            original = p.read_bytes()
            plan_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_bytes(place_hook_ram(original, signatures))
    ui_inputs = {}
    if ui_ram:
        # Placement only, in private copies: keep every UI update and query.
        for name, signatures in (
            ("sim/web/src/fm1_seq_ui.c", (b"int fm1_seq_ui_sync",)),
            ("engines/seq/seq_engine.c", (b"void fm1_seq_get_info",
             b"int fm1_seq_get_track", b"int fm1_seq_get_clip")),
        ):
            p = staging / name
            original = p.read_bytes()
            ui_inputs[name] = hashlib.sha256(original).hexdigest()
            text = original
            for signature in signatures:
                matches = re.findall(rb'^' + re.escape(signature) + rb'\([^;]*?\) \{.*?^\}', text, re.M | re.S)
                if len(matches) != 1:
                    raise ValueError("Unexpected UI definition; review placement: " + signature.decode())
                wrapped = b'#pragma code_seg(".volatile_ram_code")\n' + matches[0] + b'\n#pragma code_seg()'
                text = text.replace(matches[0], wrapped, 1)
            p.write_bytes(text)
    unroll_input = None
    if resampler_unroll:
        p = staging / "engines/include/fm1_resampler.h"
        unroll_input = hashlib.sha256(p.read_bytes()).hexdigest()
        p.write_text(unroll_resampler_lowpass(p.read_text()))
    schedule_input = None
    if resampler_schedule:
        p = staging / "engines/include/fm1_resampler.h"
        schedule_input = hashlib.sha256(p.read_bytes()).hexdigest()
        p.write_text(schedule_resampler_lowpass(p.read_text()))
    stage1_schedule_input = None
    if resampler_stage1_schedule:
        p = staging / "engines/include/fm1_resampler.h"
        stage1_schedule_input = hashlib.sha256(p.read_bytes()).hexdigest()
        p.write_text(schedule_resampler_intermediate(p.read_text()))
    drums_ready_inputs = {}
    if drums_ready_convert:
        header = staging / "engines/include/fm1_resampler.h"
        drums = staging / "engines/src/drums.cc"
        drums_ready_inputs = {str(p.relative_to(staging)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (header, drums)}
        changed_header, changed_drums = drums_ready_conversion(header.read_text(), drums.read_text())
        header.write_text(changed_header)
        drums.write_text(changed_drums)
    prep_profile_inputs = {}
    if prep_profile and not outer_timing_only:
        for name, planner in (("sim/web/src/fm1_app.c", False),
                              ("engines/mod/mod_plan.c", True)):
            p = staging / name
            original = p.read_bytes()
            prep_profile_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_text(instrument_prep_profile(original.decode(), planner))
        for name, functions in DISPATCH_PROFILE_CALLS.items():
            p = staging / name
            original = p.read_bytes()
            prep_profile_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_text(instrument_dispatch_profile(original.decode(), functions))
    oscillator_slopes_input = None
    if oscillator_slopes:
        p = staging / "engines/third_party/mutable/plaits/dsp/oscillator/variable_shape_oscillator.h"
        original = p.read_bytes()
        oscillator_slopes_input = hashlib.sha256(original).hexdigest()
        p.write_text(reuse_oscillator_slopes(original.decode()))
    vcf_unroll_input = None
    if vcf_unroll:
        p = staging / "engines/third_party/mutable/plaits/dsp/engine2/virtual_analog_vcf_engine.cc"
        original = p.read_bytes()
        vcf_unroll_input = hashlib.sha256(original).hexdigest()
        p.write_text(unroll_vcf_samples(original.decode()))
    vcf_profile_input = None
    if vcf_profile and not outer_timing_only:
        p = staging / "engines/third_party/mutable/plaits/dsp/engine2/virtual_analog_vcf_engine.cc"
        original = p.read_bytes()
        vcf_profile_input = hashlib.sha256(original).hexdigest()
        p.write_text(instrument_vcf_profile(original.decode()))
    engine_profile_inputs = {}
    if engine_profile and not outer_timing_only:
        for engine, name in enumerate(("engines/src/mi_macro.cc", "engines/src/drums.cc")):
            p = staging / name
            original = p.read_bytes()
            engine_profile_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_text(instrument_engine_profile(original.decode(), engine))
    queue_input = None
    if engine_queue:
        p = staging / "sim/web/src/fm1_app.c"
        queue_input = hashlib.sha256(p.read_bytes()).hexdigest()
        queued = queue_engine_callbacks(p.read_text())
        if engine_queue_insert:
            queued = queue_insert_callbacks(queued, engine_queue_caller_post)
        p.write_text(queue_micro_callbacks(queued, engine_queue_mod_micro) if engine_queue_micro else queued)
    modulation_micro_inputs = {}
    if engine_queue_mod_micro:
        for unit, name in (("core", "mod_core.c"), ("glue", "mod_glue.c")):
            p = staging / "engines/mod" / name
            modulation_micro_inputs[name] = hashlib.sha256(p.read_bytes()).hexdigest()
            p.write_text(queue_modulation_micro(p.read_text(), unit, engine_queue_module_micro))
    (staging / "tools/jieli").mkdir(parents=True)
    shutil.copyfile(source / "tools/jieli/renderer.mk", staging / "tools/jieli/renderer.mk")
    fragment = app / "board/wl82/lunar-renderer.mk"
    fragment_text = (source / "tools/jieli/devkit-renderer-sdk.mk").read_text()
    if renderer_o3:
        if fragment_text.count("OPT=-O2") != 1:
            raise ValueError("Unexpected renderer optimization flags; review O3 comparison")
        fragment_text = fragment_text.replace("OPT=-O2", "OPT=-O3", 1)
    if fragment_text.count("FM1_DX7_SINE=msfa") != 1:
        raise ValueError("Unexpected renderer DX7 sine switch; review the fragment")
    fragment_text = fragment_text.replace("FM1_DX7_SINE=msfa", "FM1_DX7_SINE=" + dx7_sine, 1)
    fragment.write_text(fragment_text)
    makefile = app / "board/wl82/Makefile"
    text = makefile.read_text()
    anchor = "objs/apps/demo/demo_hello/audio_probe.c.o: CFLAGS :="
    if text.count(anchor) != (0 if timing_only else 1) or text.count("ifeq ($(LINK_AT), 1)") != 1:
        raise ValueError("Unexpected SDK build structure; review renderer integration")
    # Defines must precede the immediate := snapshot for the DAC callback.
    # Keys uses 86896 target arena bytes; reserve 96 KiB with checked init
    # bounds. Mixed retains its existing pool and complete workload.
    renderer_pool_bytes = (96 if fm6_pair and workload == "keys" else
                           136 if control_ram else 148) * 1024
    renderer_flags = ""
    if external_pixels:
        renderer_flags += "CFLAGS += -DFM1_TFT_EXTERNAL_PIXELS=1\n"
    if fm6_pair:
        renderer_flags += "CFLAGS += -DLUNAR_DEVKIT_FM6_PAIR=1 -DLUNAR_DEVKIT_FM6_SDK=1\n"
    if engine_queue:
        renderer_flags += "CFLAGS += -DLUNAR_DEVKIT_ENGINE_QUEUE=1 -DLUNAR_DEVKIT_QUEUE_SDK=1\n"
        renderer_flags += f"CFLAGS += -I{staging / 'firmware/devkit'}\n"
    if engine_queue_insert:
        renderer_flags += "CFLAGS += -DLUNAR_QUEUE_POST=1\n"
    if engine_queue_caller_post:
        renderer_flags += "CFLAGS += -DLUNAR_QUEUE_CALLER_POST=1\n"
    if engine_queue_profile:
        renderer_flags += "CFLAGS += -DLUNAR_QUEUE_PROFILE=1\n"
    if engine_queue_detail:
        renderer_flags += "CFLAGS += -DLUNAR_QUEUE_DETAIL=1\n"
    if engine_queue_micro:
        renderer_flags += "CFLAGS += -DLUNAR_QUEUE_MICRO=1\n"
    if engine_queue_drums:
        renderer_flags += "CFLAGS += -DLUNAR_QUEUE_WORKER_DRUMS=1\n"
    if scheduling_probe:
        renderer_flags += "CFLAGS += -DLUNAR_DEVKIT_SCHEDULING_PROBE=1\n"
    if workload == "keys":
        renderer_flags += "CFLAGS += -DLUNAR_RENDERER_WORKLOAD=1\n"
    if timing_only:
        renderer_flags += "CFLAGS += -DLUNAR_DEVKIT_RENDERER_TIMING=1\n"
        if control_ram or (fm6_pair and workload == "keys"):
            renderer_flags += f"CFLAGS += -DLUNAR_RENDERER_POOL_BYTES={renderer_pool_bytes}\n"
        if profile and not outer_timing_only:
            renderer_flags += "CFLAGS += -DLUNAR_RENDERER_PROFILE=1 -DFM1_APP_RENDER_PROFILE=1\n"
        if prep_profile and not outer_timing_only:
            renderer_flags += "CFLAGS += -DLUNAR_RENDERER_PREP_PROFILE=1\n"
        if engine_profile and not outer_timing_only:
            renderer_flags += "CFLAGS += -DLUNAR_RENDERER_ENGINE_PROFILE=1\n"
        if vcf_profile and not outer_timing_only:
            renderer_flags += "CFLAGS += -DLUNAR_RENDERER_VCF_PROFILE=1\n"
    else:
        text = text.replace(anchor, "CFLAGS += -DLUNAR_DEVKIT_RENDERER_AUDIO=1\n" + anchor, 1)
    # The nested make snapshots CFLAGS into LUNAR_EXTRA with :=. Define its
    # profile flags before that include, not just before the worker compiles.
    text = text.replace("ifeq ($(LINK_AT), 1)", renderer_flags + "include lunar-renderer.mk\n\nifeq ($(LINK_AT), 1)", 1)
    makefile.write_text(text)
    receipt = json.loads((out / "lunar-devkit-input.json").read_text())
    receipt.update({
        "measurement": ("actual shared renderer worker timing, no DAC" if timing_only else
                        "actual shared renderer through internal DAC") +
                       "; four sounds/tracks, inserts, master effects, modulation and control edits",
        "timing_only": timing_only,
        "render_profile": profile and not outer_timing_only,
        "outer_timing_only": outer_timing_only,
        "engine_queue": engine_queue,
        "engine_queue_caller_post": engine_queue_caller_post,
        "engine_queue_insert": engine_queue_insert,
        "engine_queue_insert_allowlist": ["filter(sound0)", "drive(sound1)", "empty"] if engine_queue_caller_post else ["drive", "empty"] if engine_queue_insert else [],
        "engine_queue_drums": engine_queue_drums,
        "engine_queue_profile": engine_queue_profile,
        "engine_queue_detail": engine_queue_detail,
        "engine_queue_micro": engine_queue_micro,
        "engine_queue_mod_micro": engine_queue_mod_micro,
        "engine_queue_module_micro": engine_queue_module_micro,
        "engine_queue_mod_micro_inputs": modulation_micro_inputs,
        "engine_queue_micro_regions": (["record_render", "record_note_on", "record_note_off",
                                        "record_set_param", "record_bend", "record_set_note"] +
                                       [f"fx_dsp_app_unit_{i}" for i in range(14)] +
                                       (["mod_system", "module_params", "module_gates", "module_prepare",
                                         "module_process", "module_outputs"] if engine_queue_module_micro else
                                        ["mod_system", "mod_modules", "mod_sinks", "mod_voices",
                                         "mod_glue_global", "mod_glue_voices"] if engine_queue_mod_micro else
                                        ["control_begin", "control_event", "control_lock", "control_tick",
                                         "control_lock_slot", "control_note_on"])
                                       if engine_queue_micro else []),
        "engine_queue_detail_regions": (["sequence_setup", "record_callbacks", "inserts_meters", "level_mix",
                                         "masters", "amp", "limiter", "scope", "ui", "conversion_hash"]
                                        if engine_queue_detail else []),
        "engine_queue_profile_regions": (["before", "recording", "caller", "wait", "after", "worker_overlap"]
                                         if engine_queue_profile else []),
        "engine_queue_worker_sounds": ([1, 2] if engine_queue_drums else [1]) if engine_queue else [],
        "engine_queue_input_sha256": queue_input,
        "engine_queue_worker_priority": 16 if engine_queue else None,
        "engine_queue_stack_words": 2048 if engine_queue else 0,
        "engine_queue_protocol_budget_ticks": 2400000 if engine_queue else 0,
        "engine_queue_allowlist": ["dx7", "macro:model0", "drums", "dx7"] if engine_queue else [],

        "fm6_pair": fm6_pair,
        "scheduling_probe": scheduling_probe,
        "parent_task_priority": parent_priority,
        "fm6_worker_priority": (16 if scheduling_probe else 10) if fm6_pair else None,
        "uart_task_priority": 18 if scheduling_probe or engine_queue else 8,
        "fm6_pair_budget_ticks": 24000000 * 64 // 44100 if fm6_pair else 0,
        "fm6_pair_lifetime_ms": 120000 if fm6_pair else 0,
        "hot_ram_sources": hot_inputs,
        "msfa_pure_unroll": msfa_pure_unroll,
        "msfa_pure_unroll_original_sha256": pure_unroll_input,
        "dx7_sine": dx7_sine,
        "msfa_sine32": msfa_sine32,
        "msfa_sine_pair": msfa_sine_pair,
        "msfa_sine_pair_input_sha256": sine_pair_input,
        "msfa_sine32_rom_sha256": sine32_input,
        "msfa_narrow_adds": msfa_narrow_adds,
        "msfa_narrow_adds_original_sha256": narrow_inputs,
        "sine_ram_original_sha256": sine_input,
        "resampler_ram_original_sha256": resampler_input,
        "cache_tables": cache_tables,
        "plaits_cache": plaits_cache,
        "resampler_slopes": resampler_slopes,
        "prep_profile": prep_profile and not outer_timing_only,
        "prep_profile_original_sha256": prep_profile_inputs,
        "oscillator_slopes": oscillator_slopes,
        "oscillator_slopes_original_sha256": oscillator_slopes_input,
        "vcf_unroll": vcf_unroll,
        "vcf_unroll_original_sha256": vcf_unroll_input,
        "vcf_profile": vcf_profile and not outer_timing_only,
        "vcf_profile_original_sha256": vcf_profile_input,
        "engine_profile": engine_profile and not outer_timing_only,
        "drums_ready_convert": drums_ready_convert,
        "drums_ready_convert_input_sha256": drums_ready_inputs,
        "resampler_unroll": resampler_unroll,
        "resampler_stage1_schedule": resampler_stage1_schedule,
        "resampler_stage1_schedule_original_sha256": stage1_schedule_input,
        "resampler_schedule": resampler_schedule,
        "resampler_schedule_original_sha256": schedule_input,
        "renderer_optimization": "-O3" if renderer_o3 else "-O2",
        "renderer_workload": workload,
        "prepared_renderer_fragment_sha256": hashlib.sha256(fragment.read_bytes()).hexdigest(),
        "resampler_unroll_original_sha256": unroll_input,
        "engine_profile_original_sha256": engine_profile_inputs,
        "plaits_table_original_sha256": plaits_table_inputs,
        "fx_ram": fx_ram,
        "resampler_outline": resampler_outline,
        "filter_process_ram": filter_process_ram,
        "worker_stack_words": worker_stack_words,
        "control_ram": control_ram,
        "mixer_ram": mixer_ram,
        "dispatch_ram": dispatch_ram,
        "external_pixels": external_pixels,
        "plan_ram": plan_ram,
        "plan_ram_original_sha256": plan_inputs,
        "event_ram": event_ram,
        "event_ram_original_sha256": event_inputs,
        "metadata_ram": metadata_ram,
        "metadata_ram_original_sha256": metadata_inputs,
        "kind_ram": kind_ram,
        "kind_ram_original_sha256": kind_inputs,
        "module_ram": module_ram,
        "module_ram_original_sha256": module_inputs,
        "hook_ram": hook_ram,
        "hook_ram_original_sha256": hook_inputs,
        "ui_ram": ui_ram,
        "ui_ram_original_sha256": ui_inputs,
        "control_ram_original_sha256": control_inputs,
        "filter_process_original_sha256": filter_process_input,
        "cache_link_original_sha256": cache_link_input,
        "placement": ("SDK LTO, profiled DSP code in startup-copied ram0_data; " +
                       ("only 8 KiB FM6 sine table also SRAM" if sine_ram else "constants remain XIP") + ("; shared resampler tables also SRAM" if resampler_ram else "") + ("; sine/exp2/resampler tables relocated to SDK cache RAM data" if cache_tables else "") + ("; compressor/drive/echo code also SRAM" if fx_ram else "") + ("; two resampler kernels outlined" if resampler_outline else "") + ("; filter process code also SRAM" if filter_process_ram else "") + ("; render/sequence/modulation control code also SRAM" if control_ram else "") + ("; Plaits sine/pitch tables also cache RAM" if plaits_cache else "") + ("; pre-scaled resampler kernel pairs" if resampler_slopes else "") + ("; sound mixer and effect dispatch code also SRAM" if mixer_ram else "") + ("; independent FIR scheduling groups" if resampler_schedule else "") + ("; sequencer event walk and slot dispatch also SRAM" if dispatch_ram else "") + ("; UI synchronization and snapshot queries also SRAM" if ui_ram else "") + ("; sequence/modulation hooks and voice dispatch also SRAM" if hook_ram else "") + ("; modulation module runner/parameter/gate/output helpers also SRAM" if module_ram else "") + ("; default LFO/envelope/chance processing also SRAM" if kind_ram else "") + ("; control edits and note dispatch also SRAM" if event_ram else "") + ("; modulation plan and remaining event helpers also SRAM" if plan_ram else "") + "; target result pending"
                      if hot_ram else "SDK LTO, XIP code/constants; internal SRAM app and caller-owned engine pool; hot placement not yet measured"),
        "renderer_pool_bytes": renderer_pool_bytes,
        "worker_stack_bytes": worker_stack_words * 4,
        "renderer_integration_complete": False,
        "hardware_acceptance": False,
    })
    receipt["prepared_app_main_sha256"] = hashlib.sha256(main.read_bytes()).hexdigest()
    receipt["prepared_link_script_sha256"] = hashlib.sha256((out / "cpu/wl82/sdk_ld_sfc.c").read_bytes()).hexdigest()
    # The experiment keeps its exact source provenance in private build storage.
    for directory in ("engines", "sim/web/src", "sim/web/mk", "firmware/devkit"):
        for p in sorted((staging / directory).rglob("*")):
            if p.is_file():
                receipt["inputs"][str(p.relative_to(staging))] = hashlib.sha256(p.read_bytes()).hexdigest()
    for name in ("prepare-renderer-devkit.py", "devkit-renderer-sdk.mk", "renderer.mk"):
        p = source / "tools/jieli" / name
        receipt["inputs"][str(p.relative_to(source))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (out / "lunar-devkit-input.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timing-only", action="store_true",
                        help="Worker-context full-renderer preflight with OS yields; no DAC output")
    parser.add_argument("--workload", choices=("mixed", "keys"), default="mixed",
                        help="Named shared-renderer arrangement; keys is FM6/filter/echo/compressor, not the mixed stress test")
    parser.add_argument("--profile", action="store_true",
                        help="Time instrument/effect calls; requires --timing-only")
    parser.add_argument("--hot-ram", action="store_true",
                        help="Compare profiled DSP code in SRAM, constants in XIP; requires --timing-only")
    parser.add_argument("--sine-ram", action="store_true",
                        help="Move only FM6 sine table to SRAM; requires --hot-ram --timing-only")
    parser.add_argument("--resampler-ram", action="store_true",
                        help="Compare one shared SRAM coefficient copy; requires timing-only hot code and sine SRAM")
    parser.add_argument("--cache-tables", action="store_true",
                        help="Compare sine/exp2/resampler in existing SDK data RAM; requires all timing-only SRAM options")
    parser.add_argument("--fx-ram", action="store_true",
                        help="Compare compressor/drive/echo code in SRAM; requires timing-only cache tables")
    parser.add_argument("--resampler-outline", action="store_true",
                        help="Compare outlined resampler kernels; requires timing-only resident effects")
    parser.add_argument("--filter-process-ram", action="store_true",
                        help="Compare only filter processing code in SRAM; requires timing-only resident effects without outlining")
    parser.add_argument("--control-ram", action="store_true",
                        help="Compare render/sequence/modulation SRAM with a 136 KiB fixed workload pool; requires resident filter")
    parser.add_argument("--plaits-cache", action="store_true",
                        help="Compare exact Plaits sine/pitch tables in existing SDK data RAM; requires resident control")
    parser.add_argument("--resampler-slopes", action="store_true",
                        help="Compare pre-scaled float32 kernel pairs; requires timing-only Plaits cache")
    parser.add_argument("--engine-profile", action="store_true",
                        help="Locate engine generation/pop cost; adds measurement overhead, requires profiled slopes")
    parser.add_argument("--resampler-unroll", action="store_true",
                        help="Expand the fixed FIR loop without changing sums; requires profiled slopes")
    parser.add_argument("--renderer-o3", action="store_true",
                        help="Compare renderer -O3 with SDK flags unchanged; requires profiled lowpass unrolling")
    parser.add_argument("--mixer-ram", action="store_true",
                        help="Compare sound mixer/effect dispatch in SRAM; requires timing-only profiled O3")
    parser.add_argument("--metadata-ram", action="store_true",
                        help="Copy hot parameter/port/engine descriptors to SRAM; timing-only resident control")
    parser.add_argument("--resampler-stage1-schedule", action="store_true",
                        help="Interleave independent stage-one tap chains; timing-only pre-scaled resident mixer")
    parser.add_argument("--resampler-schedule", action="store_true",
                        help="Group independent FIR sums/products; requires timing-only resident mixer")
    parser.add_argument("--msfa-pure-unroll", action="store_true",
                        help="Compare two-way pure FM loops; timing-only hot O3 with narrow additions")
    parser.add_argument("--msfa-sine-pair", action="store_true",
                        help="Pair adjacent sine delta/base loads; requires timing-only hot signed32 sine")
    parser.add_argument("--msfa-sine32", action="store_true",
                        help="Compare bounded signed32 sine products; requires narrow FM additions")
    parser.add_argument("--msfa-narrow-adds", action="store_true",
                        help="Compare explicit 32-bit FM sums in private copies; timing-only hot code")
    parser.add_argument("--dispatch-ram", action="store_true",
                        help="Compare sequencer event walk and slot dispatch in SRAM; requires timing-only resident mixer")
    parser.add_argument("--engine-queue-caller-post", action="store_true",
                        help="Finish fixed caller track inserts before join; requires --engine-queue-insert")
    parser.add_argument("--engine-queue-insert", action="store_true",
                        help="Move sound1 Drive/empty insert chain to CPU1 before ACK; isolated queue mode only")
    parser.add_argument("--engine-queue-profile", action="store_true",
                        help="Add queue critical-path timers; requires --engine-queue, remains diagnostic-only")
    parser.add_argument("--engine-queue-drums", action="store_true",
                        help="Serialize Macro model0 and Drums on CPU1; requires --engine-queue")
    parser.add_argument("--engine-queue", action="store_true",
                        help="Finite fixed mixed whole-engine CPU1 queue; timing-only outer O3, no nested FM6 worker")
    parser.add_argument("--fm6-pair", action="store_true",
                        help="Finite CPU1 copied FM6 jobs; timing-only profiled hot code, no DAC")
    parser.add_argument("--scheduling-probe", action="store_true",
                        help="Timing-only FM6 pair scheduling comparison; render priority 16, UART 18")
    parser.add_argument("--ui-ram", action="store_true",
                        help="Compare UI synchronization/query placement in SRAM; timing-only resident dispatch")
    parser.add_argument("--prep-profile", action="store_true",
                        help="Observe note/control and nested planner costs; timing-only profile")
    parser.add_argument("--hook-ram", action="store_true",
                        help="Compare remaining sequence/modulation hooks and voice dispatch in SRAM; timing-only profiled resident dispatch")
    parser.add_argument("--module-ram", action="store_true",
                        help="Compare module runner/parameter/gate/output helpers in SRAM; timing-only profiled resident hooks")
    parser.add_argument("--kind-ram", action="store_true",
                        help="Compare default LFO/envelope/chance hot processing in SRAM; timing-only profiled resident modules")
    parser.add_argument("--event-ram", action="store_true",
                        help="Compare unchanged control edits and note dispatch in SRAM; requires timing-only preparation profile and resident kinds")
    parser.add_argument("--plan-ram", action="store_true",
                        help="Compare unchanged modulation planner and event helpers in SRAM; timing-only preparation profile and resident events")
    parser.add_argument("--outer-timing-only", action="store_true",
                        help="Omit internal observer hooks/flags; retain outer timing and requested O3 placement")
    parser.add_argument("--oscillator-slopes", action="store_true",
                        help="Reuse exact rounded PWM reciprocals in private oscillator loops; timing-only profiled resident O3")
    parser.add_argument("--vcf-unroll", action="store_true",
                        help="Compare two-way VCF sample-loop scheduling; timing-only profiled resident O3")
    parser.add_argument("--vcf-profile", action="store_true",
                        help="Observe VCF oscillator/filter sections; timing-only O3 engine profiling")
    parser.add_argument("--external-pixels", action="store_true",
                        help="Caller-owned screen pixels; timing-only renderer does not draw or attach a framebuffer")
    parser.add_argument("--engine-queue-detail", action="store_true",
                        help="Split queue recording and post-join CPU0 work; requires queue profile")
    parser.add_argument("--engine-queue-micro", action="store_true",
                        help="Time recording command kinds and per-unit effect DSP; requires queue detail")
    parser.add_argument("--engine-queue-mod-micro", action="store_true",
                        help="Replace six control-hook timers with internal modulation subsets; requires queue micro")
    parser.add_argument("--engine-queue-module-micro", action="store_true",
                        help="Split global module preparation/process/output; requires modulation micro")
    parser.add_argument("--drums-ready-convert", action="store_true",
                        help="Reuse established Drums conversion readiness; resident unrolled outer-only comparison")
    parser.add_argument("--dx7-sine", choices=("msfa", "trunc12"), default="msfa",
                        help="FM6 sine (engines/Makefile FM1_DX7_SINE): msfa's interpolated table, or "
                             "trunc12's 12-bit non-interpolated one pending the owner's A/B (engines/msfa.md)")
    args = parser.parse_args()
    prepare_renderer(args.sdk.resolve(), args.source.resolve(), args.out.resolve(), args.timing_only, args.profile, args.hot_ram, args.sine_ram, args.resampler_ram, args.cache_tables, args.fx_ram, args.resampler_outline, args.filter_process_ram, args.control_ram, args.plaits_cache, args.resampler_slopes, args.engine_profile, args.resampler_unroll, args.renderer_o3, args.mixer_ram, args.resampler_schedule, args.workload, args.dispatch_ram, args.msfa_narrow_adds, args.msfa_sine32, args.msfa_pure_unroll, args.fm6_pair, args.scheduling_probe, args.ui_ram, args.prep_profile, args.hook_ram, args.module_ram, args.kind_ram, args.event_ram, args.plan_ram, args.external_pixels, args.vcf_unroll, args.vcf_profile, args.oscillator_slopes, args.outer_timing_only, args.engine_queue, args.engine_queue_drums, args.engine_queue_profile, args.engine_queue_detail, args.engine_queue_micro, args.engine_queue_mod_micro, args.engine_queue_module_micro, args.engine_queue_insert, args.engine_queue_caller_post, args.resampler_stage1_schedule, args.metadata_ram, args.msfa_sine_pair, args.drums_ready_convert, args.dx7_sine)
