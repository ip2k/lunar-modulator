#!/usr/bin/env python3
"""Prepare the private shared-renderer SDK build. No USB access or downloader.

Input must be the verified private AC79 V1.2.13 e30b1ee archive. This prepares
an offline candidate only, not an admitted image or a performance result.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil


def prepare_renderer(sdk, source, out, timing_only=False):
    spec = importlib.util.spec_from_file_location("devkit_prepare", source / "tools/jieli/prepare-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Retain reviewed SDK configuration, disabled settings registration,
    # disabled downloader and mandatory UART command receiver.
    module.prepare(sdk, source, out, audio_probe=not timing_only, boot_control=True)
    app = out / "apps/demo/demo_hello"
    # os_api.h specifies four-byte stack units. Shared app setup includes the
    # modulation script parser and UI helpers, unlike the isolated FM6 probe.
    main = app / "app_main.c"
    text = main.read_text()
    worker = 'os_task_create(lunar_devkit_worker, NULL, 10, 2048, 0, "lunar_devkit");'
    if text.count(worker) != 1:
        raise ValueError("Unexpected worker creation; review renderer task stack")
    main.write_text(text.replace(worker, worker.replace('10, 2048,', '10, 5120,'), 1))
    shutil.copyfile(source / "firmware/devkit/renderer_live.h", app / "renderer_live.h")
    shutil.copyfile(source / "firmware/devkit/renderer_timing.h", app / "renderer_timing.h")
    staging = out / "lunar-source"
    for directory in ("engines", "sim/web/src", "sim/web/mk", "firmware/devkit"):
        shutil.copytree(source / directory, staging / directory,
                        ignore=shutil.ignore_patterns("build", "build-*", ".git", "__pycache__", ".DS_Store", "._*"))
    (staging / "tools/jieli").mkdir(parents=True)
    shutil.copyfile(source / "tools/jieli/renderer.mk", staging / "tools/jieli/renderer.mk")
    shutil.copyfile(source / "tools/jieli/devkit-renderer-sdk.mk", app / "board/wl82/lunar-renderer.mk")
    makefile = app / "board/wl82/Makefile"
    text = makefile.read_text()
    anchor = "objs/apps/demo/demo_hello/audio_probe.c.o: CFLAGS :="
    if text.count(anchor) != (0 if timing_only else 1) or text.count("ifeq ($(LINK_AT), 1)") != 1:
        raise ValueError("Unexpected SDK build structure; review renderer integration")
    # Defines must precede the immediate := snapshot for the DAC callback.
    if timing_only:
        text += "\nCFLAGS += -DLUNAR_DEVKIT_RENDERER_TIMING=1\n"
    else:
        text = text.replace(anchor, "CFLAGS += -DLUNAR_DEVKIT_RENDERER_AUDIO=1\n" + anchor, 1)
    text = text.replace("ifeq ($(LINK_AT), 1)", "include lunar-renderer.mk\n\nifeq ($(LINK_AT), 1)", 1)
    makefile.write_text(text)
    receipt = json.loads((out / "lunar-devkit-input.json").read_text())
    receipt.update({
        "measurement": ("actual shared renderer worker timing, no DAC" if timing_only else
                        "actual shared renderer through internal DAC") +
                       "; four sounds/tracks, inserts, master effects, modulation and control edits",
        "timing_only": timing_only,
        "placement": "SDK LTO, XIP code/constants; internal SRAM app and caller-owned engine pool; hot placement not yet measured",
        "renderer_pool_bytes": 148 * 1024,
        "worker_stack_bytes": 20 * 1024,
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
    args = parser.parse_args()
    prepare_renderer(args.sdk.resolve(), args.source.resolve(), args.out.resolve(), args.timing_only)
