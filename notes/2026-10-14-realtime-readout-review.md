# Native realtime readout review

Review base: 9ea86693825ee3e126d42cba81ce657aac9acf53 (codex/2026-10-14-realtime-readout-review). This is an offline review of the new diagnostic footer, with a target-compiler object check; it makes no hardware or installability claim.

## Source checks

- firmware/native/realtime_readout.h hashes to fab5c2a0c2769f0e99b7d0b43081852024a0283d2436e2f4c252211c2685a39d. Its label is 36 bytes including NUL; it writes three zero-padded 10-digit uint32 fields at their intended offsets, so the visible line is 35 characters and represents UINT32_MAX without overflow. This fits the 232-pixel footer interior at six pixels per glyph (210 pixels).
- firmware/native/app_probe.c hashes to fb1faacb0eb11bf9209eff63705d71899039303598ba69d21f79e7250a3ac4c6. The footer uses render_ticks_max, draw_ticks_max, and the consumer-owned missing-64-frame-block count. The diagnostic reads draw_ticks_max before measuring the draw containing that footer; the later maximum appears on the next refresh. The display is therefore one completed draw behind by design. The timer header firmware/third_party/dinghy/hal/fm1_time.h:16 sets 24 ticks per microsecond; the R/D conversion agrees with that source definition. This establishes units from source, not physical timer calibration.
- Layout boundaries are internally consistent: margins at (4,212), label at (128,212), timing at (4,224), 35 characters. The existing host fixture checks the complete uint32 range, canaries, actual indexed TFT text renderer, clear margins, and no clipping/truncation.

## Checks run

1. tests/test_native_realtime_readout.py passed (1 test) inside lunar-jieli-check:bookworm, network disabled, one CPU, 2 GiB memory/swap, 256 pids, under docker-batch.slice. The test used the repository Python 3.12 pytest site-packages mounted read-only; its compiler subprocess ran in the container.
2. A bounded pi32v2 compile of the current firmware/native/app_probe.c succeeded with the established target flags and matching cached expanded-D7000/Shapes8 link-generated headers and includes. Compiler: /toolchain/common/bin/clang, from toolchain tree /home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1; image lunar-jieli-check:bookworm, immutable ID sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc. Source checkout and toolchain/catalogue/link mounts were read-only; output was private under /home/claude/mvave-fm1/realtime-readout-review-20261014/.
3. The resulting target object app_probe.o is 387,968 bytes, SHA-256 636c62583247715d0d1caf9192a17e4a925dd4d0757b2654e8ba6e613d406420. Vendor objdump -t shows fm1_cstart object section size 0x1180, render_ticks_max and draw_ticks_max are four-byte objects, and the inlined readout label is 0x24 bytes. Vendor disassembly around the footer path shows the /24 conversions and the footer draw sequence. This was a standalone non-LTO object compile, not a full relink: it does not establish final linked code size, LTO output, target runtime timing, physical display legibility, or audio behavior.

The host pytest was also attempted directly on the Hera host but its system linker lacked libasan.so.8.0.0 and libubsan.so.1.0.0; the bounded container run above is the passing result. Root separately reported its ASan/UBSan host run and TFT preview inspection; those are not my independent physical observations.

## Disposition and remaining evidence

No source defect found in the requested scope. The formatter and footer geometry are coherent; the displayed draw maximum intentionally reflects the preceding completed draw. Target compilation provides syntax/codegen evidence only. Physical timer calibration, display output, actual diagnostic runtime, audio lag/underruns and the owner's song/control observations remain separate acceptance checks. SAVE/hardware/installability gates are unchanged.
