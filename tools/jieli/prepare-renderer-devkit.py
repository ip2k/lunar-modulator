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


def prepare_renderer(sdk, source, out, timing_only=False, profile=False, hot_ram=False, sine_ram=False, resampler_ram=False):
    if profile and not timing_only:
        raise ValueError("Render profiling is worker-only; not an audio acceptance image")
    if hot_ram and not timing_only:
        raise ValueError("Hot SRAM comparison is worker-only until target validation")
    if sine_ram and not (timing_only and hot_ram):
        raise ValueError("Sine SRAM comparison requires timing-only hot code placement")
    if resampler_ram and not (timing_only and hot_ram and sine_ram):
        raise ValueError("Resampler SRAM comparison requires timing-only hot code and sine SRAM")
    spec = importlib.util.spec_from_file_location("devkit_prepare", source / "tools/jieli/prepare-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Retain reviewed SDK configuration, disabled settings registration,
    # disabled downloader and mandatory UART command receiver.
    module.prepare(sdk, source, out, audio_probe=not timing_only, boot_control=True)
    app = out / "apps/demo/demo_hello"
    # os_api.h specifies four-byte stack units. Shared app setup includes the
    # modulation script parser and UI helpers, unlike the isolated FM6 probe.
    # Actual target high-water usage is 5400 bytes; retain >2x that budget.
    # Recovery is already reserved/configured before this allocation.
    main = app / "app_main.c"
    text = main.read_text()
    worker = 'os_task_create(lunar_devkit_worker, NULL, 10, 2048, 0, "lunar_devkit");'
    if text.count(worker) != 1:
        raise ValueError("Unexpected worker creation; review renderer task stack")
    main.write_text(text.replace(worker, worker.replace('10, 2048,', '10, 3072,'), 1))
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
        for name in HOT_RAM_SOURCES:
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
        "placement": ("SDK LTO, profiled DSP code in startup-copied ram0_data; " +
                       ("only 8 KiB FM6 sine table also SRAM" if sine_ram else "constants remain XIP") + ("; shared resampler tables also SRAM" if resampler_ram else "") + "; target result pending"
                      if hot_ram else "SDK LTO, XIP code/constants; internal SRAM app and caller-owned engine pool; hot placement not yet measured"),
        "renderer_pool_bytes": 148 * 1024,
        "worker_stack_bytes": 12 * 1024,
        "renderer_integration_complete": False,
        "hardware_acceptance": False,
    })
    receipt["prepared_app_main_sha256"] = hashlib.sha256(main.read_bytes()).hexdigest()
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
    args = parser.parse_args()
    prepare_renderer(args.sdk.resolve(), args.source.resolve(), args.out.resolve(), args.timing_only, args.profile, args.hot_ram, args.sine_ram, args.resampler_ram)
