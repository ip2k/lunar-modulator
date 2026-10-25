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


def prepare_renderer(sdk, source, out, timing_only=False, profile=False, hot_ram=False, sine_ram=False, resampler_ram=False, cache_tables=False, fx_ram=False, resampler_outline=False, filter_process_ram=False, control_ram=False, plaits_cache=False, resampler_slopes=False, engine_profile=False, resampler_unroll=False, renderer_o3=False, mixer_ram=False, resampler_schedule=False, workload="mixed", dispatch_ram=False, msfa_narrow_adds=False, msfa_sine32=False, msfa_pure_unroll=False, fm6_pair=False, scheduling_probe=False):
    if scheduling_probe and not fm6_pair:
        raise ValueError("Scheduling probe requires the finite timing-only FM6 pair experiment")
    if fm6_pair and not (timing_only and hot_ram and profile):
        raise ValueError("CPU1 FM6 requires timing-only profiled hot code; no DAC acceptance")
    if workload not in ("mixed", "keys"):
        raise ValueError("Unknown renderer workload; choose mixed or keys")
    if msfa_pure_unroll and not (timing_only and hot_ram and msfa_narrow_adds and renderer_o3):
        raise ValueError("Pure FM unrolling requires timing-only hot O3 and narrow additions")
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
    if resampler_unroll and not (resampler_slopes and profile and not engine_profile):
        raise ValueError("Lowpass unrolling requires timing-only profiled slopes without detail instrumentation")
    if renderer_o3 and not resampler_unroll:
        raise ValueError("Renderer O3 comparison requires timing-only profiled lowpass unrolling")
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
    parent_priority = 16 if scheduling_probe else 10
    replacement = worker.replace('10, 2048,', f'{parent_priority}, {worker_stack_words},')
    if fm6_pair:
        replacement = replacement.replace('"lunar_devkit"', '"#C0lunar_parent"')
    main.write_text(text.replace(worker, replacement, 1))
    if fm6_pair:
        shutil.copyfile(source / "firmware/devkit/fm6_pair_sdk.h", app / "fm6_pair_sdk.h")
    shutil.copyfile(source / "firmware/devkit/renderer_live.h", app / "renderer_live.h")
    shutil.copyfile(source / "firmware/devkit/renderer_timing.h", app / "renderer_timing.h")
    shutil.copyfile(source / "firmware/devkit/arithmetic_probe.h", app / "arithmetic_probe.h")
    staging = out / "lunar-source"
    for directory in ("engines", "sim/web/src", "sim/web/mk", "firmware/devkit"):
        shutil.copytree(source / directory, staging / directory,
                        ignore=shutil.ignore_patterns("build", "build-*", ".git", "__pycache__", ".DS_Store", "._*"))
    narrow_inputs = {}
    if msfa_narrow_adds:
        for name in ("sin.h", "fm_op_kernel.cc"):
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
        anchor = b'extern const int32_t kSinTab[2048] = {'
        if original.count(anchor) != 1:
            raise ValueError("Unexpected sine table definition; review placement")
        sine_input = hashlib.sha256(original).hexdigest()
        p.write_bytes(original.replace(anchor,
            b'extern const int32_t kSinTab[2048] __attribute__((section(".volatile_ram"))) = {', 1))
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
            expected = 2 if name == "mi_macro.cc" else 1
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
    engine_profile_inputs = {}
    if engine_profile:
        for engine, name in enumerate(("engines/src/mi_macro.cc", "engines/src/drums.cc")):
            p = staging / name
            original = p.read_bytes()
            engine_profile_inputs[name] = hashlib.sha256(original).hexdigest()
            p.write_text(instrument_engine_profile(original.decode(), engine))
    (staging / "tools/jieli").mkdir(parents=True)
    shutil.copyfile(source / "tools/jieli/renderer.mk", staging / "tools/jieli/renderer.mk")
    fragment = app / "board/wl82/lunar-renderer.mk"
    fragment_text = (source / "tools/jieli/devkit-renderer-sdk.mk").read_text()
    if renderer_o3:
        if fragment_text.count("OPT=-O2") != 1:
            raise ValueError("Unexpected renderer optimization flags; review O3 comparison")
        fragment_text = fragment_text.replace("OPT=-O2", "OPT=-O3", 1)
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
    if fm6_pair:
        renderer_flags += "CFLAGS += -DLUNAR_DEVKIT_FM6_PAIR=1 -DLUNAR_DEVKIT_FM6_SDK=1\n"
    if scheduling_probe:
        renderer_flags += "CFLAGS += -DLUNAR_DEVKIT_SCHEDULING_PROBE=1\n"
    if workload == "keys":
        renderer_flags += "CFLAGS += -DLUNAR_RENDERER_WORKLOAD=1\n"
    if timing_only:
        renderer_flags += "CFLAGS += -DLUNAR_DEVKIT_RENDERER_TIMING=1\n"
        if control_ram or (fm6_pair and workload == "keys"):
            renderer_flags += f"CFLAGS += -DLUNAR_RENDERER_POOL_BYTES={renderer_pool_bytes}\n"
        if profile:
            renderer_flags += "CFLAGS += -DLUNAR_RENDERER_PROFILE=1 -DFM1_APP_RENDER_PROFILE=1\n"
        if engine_profile:
            renderer_flags += "CFLAGS += -DLUNAR_RENDERER_ENGINE_PROFILE=1\n"
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
        "render_profile": profile,
        "fm6_pair": fm6_pair,
        "scheduling_probe": scheduling_probe,
        "parent_task_priority": parent_priority,
        "fm6_worker_priority": (16 if scheduling_probe else 10) if fm6_pair else None,
        "uart_task_priority": 18 if scheduling_probe else 8,
        "fm6_pair_budget_ticks": 24000000 * 64 // 44100 if fm6_pair else 0,
        "fm6_pair_lifetime_ms": 120000 if fm6_pair else 0,
        "hot_ram_sources": hot_inputs,
        "msfa_pure_unroll": msfa_pure_unroll,
        "msfa_pure_unroll_original_sha256": pure_unroll_input,
        "msfa_sine32": msfa_sine32,
        "msfa_sine32_rom_sha256": sine32_input,
        "msfa_narrow_adds": msfa_narrow_adds,
        "msfa_narrow_adds_original_sha256": narrow_inputs,
        "sine_ram_original_sha256": sine_input,
        "resampler_ram_original_sha256": resampler_input,
        "cache_tables": cache_tables,
        "plaits_cache": plaits_cache,
        "resampler_slopes": resampler_slopes,
        "engine_profile": engine_profile,
        "resampler_unroll": resampler_unroll,
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
        "control_ram_original_sha256": control_inputs,
        "filter_process_original_sha256": filter_process_input,
        "cache_link_original_sha256": cache_link_input,
        "placement": ("SDK LTO, profiled DSP code in startup-copied ram0_data; " +
                       ("only 8 KiB FM6 sine table also SRAM" if sine_ram else "constants remain XIP") + ("; shared resampler tables also SRAM" if resampler_ram else "") + ("; sine/exp2/resampler tables relocated to SDK cache RAM data" if cache_tables else "") + ("; compressor/drive/echo code also SRAM" if fx_ram else "") + ("; two resampler kernels outlined" if resampler_outline else "") + ("; filter process code also SRAM" if filter_process_ram else "") + ("; render/sequence/modulation control code also SRAM" if control_ram else "") + ("; Plaits sine/pitch tables also cache RAM" if plaits_cache else "") + ("; pre-scaled resampler kernel pairs" if resampler_slopes else "") + ("; sound mixer and effect dispatch code also SRAM" if mixer_ram else "") + ("; independent FIR scheduling groups" if resampler_schedule else "") + ("; sequencer event walk and slot dispatch also SRAM" if dispatch_ram else "") + "; target result pending"
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
                        help="Expand the fixed FIR loop without changing sums; requires profiled slopes without engine detail")
    parser.add_argument("--renderer-o3", action="store_true",
                        help="Compare renderer -O3 with SDK flags unchanged; requires profiled lowpass unrolling")
    parser.add_argument("--mixer-ram", action="store_true",
                        help="Compare sound mixer/effect dispatch in SRAM; requires timing-only profiled O3")
    parser.add_argument("--resampler-schedule", action="store_true",
                        help="Group independent FIR sums/products; requires timing-only resident mixer")
    parser.add_argument("--msfa-pure-unroll", action="store_true",
                        help="Compare two-way pure FM loops; timing-only hot O3 with narrow additions")
    parser.add_argument("--msfa-sine32", action="store_true",
                        help="Compare bounded signed32 sine products; requires narrow FM additions")
    parser.add_argument("--msfa-narrow-adds", action="store_true",
                        help="Compare explicit 32-bit FM sums in private copies; timing-only hot code")
    parser.add_argument("--dispatch-ram", action="store_true",
                        help="Compare sequencer event walk and slot dispatch in SRAM; requires timing-only resident mixer")
    parser.add_argument("--fm6-pair", action="store_true",
                        help="Finite CPU1 copied FM6 jobs; timing-only profiled hot code, no DAC")
    parser.add_argument("--scheduling-probe", action="store_true",
                        help="Timing-only FM6 pair scheduling comparison; render priority 16, UART 18")
    args = parser.parse_args()
    prepare_renderer(args.sdk.resolve(), args.source.resolve(), args.out.resolve(), args.timing_only, args.profile, args.hot_ram, args.sine_ram, args.resampler_ram, args.cache_tables, args.fx_ram, args.resampler_outline, args.filter_process_ram, args.control_ram, args.plaits_cache, args.resampler_slopes, args.engine_profile, args.resampler_unroll, args.renderer_o3, args.mixer_ram, args.resampler_schedule, args.workload, args.dispatch_ram, args.msfa_narrow_adds, args.msfa_sine32, args.msfa_pure_unroll, args.fm6_pair, args.scheduling_probe)
