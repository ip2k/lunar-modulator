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


def prepare_renderer(sdk, source, out, timing_only=False, profile=False, hot_ram=False, sine_ram=False, resampler_ram=False, cache_tables=False, fx_ram=False, resampler_outline=False, filter_process_ram=False, control_ram=False, plaits_cache=False):
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
    main.write_text(text.replace(worker, worker.replace('10, 2048,',
        '10, ' + str(worker_stack_words) + ','), 1))
    shutil.copyfile(source / "firmware/devkit/renderer_live.h", app / "renderer_live.h")
    shutil.copyfile(source / "firmware/devkit/renderer_timing.h", app / "renderer_timing.h")
    shutil.copyfile(source / "firmware/devkit/arithmetic_probe.h", app / "arithmetic_probe.h")
    staging = out / "lunar-source"
    for directory in ("engines", "sim/web/src", "sim/web/mk", "firmware/devkit"):
        shutil.copytree(source / directory, staging / directory,
                        ignore=shutil.ignore_patterns("build", "build-*", ".git", "__pycache__", ".DS_Store", "._*"))
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
            definitions.append(definition.replace("static const float", "extern const float", 1)
                               .replace(" = {", ' __attribute__((section(".volatile_ram"))) = {', 1))
            original = original.replace(definition,
                "extern const float fm1_resampler_" + name + "[" + length + "];", 1)
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
            ("sim/web/src/fm1_app.c", (b"const float *fm1_app_render",)),
            ("engines/mod/mod_core.c", (b"static float sum_slots", b"uint32_t fm1_mod_tick")),
            ("engines/seq/seq_host.c", (b"void fm1_seq_host_dispatch_slots_ticks",)),
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
    (staging / "tools/jieli").mkdir(parents=True)
    shutil.copyfile(source / "tools/jieli/renderer.mk", staging / "tools/jieli/renderer.mk")
    shutil.copyfile(source / "tools/jieli/devkit-renderer-sdk.mk", app / "board/wl82/lunar-renderer.mk")
    makefile = app / "board/wl82/Makefile"
    text = makefile.read_text()
    anchor = "objs/apps/demo/demo_hello/audio_probe.c.o: CFLAGS :="
    if text.count(anchor) != (0 if timing_only else 1) or text.count("ifeq ($(LINK_AT), 1)") != 1:
        raise ValueError("Unexpected SDK build structure; review renderer integration")
    # Defines must precede the immediate := snapshot for the DAC callback.
    renderer_flags = ""
    if timing_only:
        renderer_flags = "CFLAGS += -DLUNAR_DEVKIT_RENDERER_TIMING=1\n"
        if control_ram:
            renderer_flags += "CFLAGS += -DLUNAR_RENDERER_POOL_BYTES=139264\n"
        if profile:
            renderer_flags += "CFLAGS += -DLUNAR_RENDERER_PROFILE=1 -DFM1_APP_RENDER_PROFILE=1\n"
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
        "hot_ram_sources": hot_inputs,
        "sine_ram_original_sha256": sine_input,
        "resampler_ram_original_sha256": resampler_input,
        "cache_tables": cache_tables,
        "plaits_cache": plaits_cache,
        "plaits_table_original_sha256": plaits_table_inputs,
        "fx_ram": fx_ram,
        "resampler_outline": resampler_outline,
        "filter_process_ram": filter_process_ram,
        "worker_stack_words": worker_stack_words,
        "control_ram": control_ram,
        "control_ram_original_sha256": control_inputs,
        "filter_process_original_sha256": filter_process_input,
        "cache_link_original_sha256": cache_link_input,
        "placement": ("SDK LTO, profiled DSP code in startup-copied ram0_data; " +
                       ("only 8 KiB FM6 sine table also SRAM" if sine_ram else "constants remain XIP") + ("; shared resampler tables also SRAM" if resampler_ram else "") + ("; sine/exp2/resampler tables relocated to SDK cache RAM data" if cache_tables else "") + ("; compressor/drive/echo code also SRAM" if fx_ram else "") + ("; two resampler kernels outlined" if resampler_outline else "") + ("; filter process code also SRAM" if filter_process_ram else "") + ("; render/sequence/modulation control code also SRAM" if control_ram else "") + ("; Plaits sine/pitch tables also cache RAM" if plaits_cache else "") + "; target result pending"
                      if hot_ram else "SDK LTO, XIP code/constants; internal SRAM app and caller-owned engine pool; hot placement not yet measured"),
        "renderer_pool_bytes": (136 if control_ram else 148) * 1024,
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
    args = parser.parse_args()
    prepare_renderer(args.sdk.resolve(), args.source.resolve(), args.out.resolve(), args.timing_only, args.profile, args.hot_ram, args.sine_ram, args.resampler_ram, args.cache_tables, args.fx_ram, args.resampler_outline, args.filter_process_ram, args.control_ram, args.plaits_cache)
