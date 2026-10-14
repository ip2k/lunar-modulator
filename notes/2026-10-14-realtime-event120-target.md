# Instrumented Event Horizon diagnostic link

## Scope and source delta

[verified] This is a private, non-installable target link prepared to measure the real-time status footer against the later, uninstalled Event Horizon-plus-SET build configuration. The source base is `68c7a51d7edf5dff54da9bd87d57d856ba9c0b16`; the uninstalled comparison app is from source `43a5a8d77721e58011a00cec782cb64df73a9f86`.

[verified] The source delta from that uninstalled comparison revision is limited to `firmware/native/app_probe.c` (footer instrumentation) and the new `firmware/native/realtime_readout.h` (fixed-width formatter). There are no platform, HAL, audio callback, clock, engine, project, catalogue, or save-service source changes. The current generated LTO disassembly shows the footer refresh loading `audio_queue.underruns` from `audio_queue + 8` at each update in `app_main`; it does not retain a prior sample in a register. The C field remains non-volatile despite asynchronous ISR mutation, so this is evidence for this exact compiler output, not a source-level synchronization guarantee for future builds.

[verified] Readout semantics are deliberately narrow:

- `R` is the largest observed duration of one 64-frame `fm1_app_render` call, shown in integer microseconds (`ticks / 24`). It is not a complete audio callback deadline measurement.
- `D` is elapsed time around one `fm1_app_draw` call plus the stack readout and new footer rendering. It does not include the rest of the main loop or `display_strip`, and the value is shown on a later draw.
- `U` is the cumulative number of 64-frame blocks where the audio callback could not pop a block. It is an underrun count, not a direct measurement of audible severity.

The footer therefore helps distinguish render pressure from loop/display delay, but one watched capture is needed to determine whether these counters explain the reported lag.

## Configuration and build evidence

[verified] The link used the prepared Event Horizon project and its companion SET from the current source-fresh catalogue: Event Horizon is startup index 0 and the SET follows it. The two packed assets total 6,232 bytes; the prepared profile hash is `af37827fa09a5925864bfebe01d800f8b37ffcda8ce4f42bf533ea9e774c4f30`. The build receipt binds selection receipt SHA `1cf0a0b897005e4ff0925d63a345c8d5db59a3b59368c6e7dfcd34308994db95`.

[verified] Build configuration: all 13 engines selected (54 modules including the companion content path), Shapes voice cap 8, indexed TFT, compressed Braids and Plaits wave tables, `song-diagnostic`, 120-second return-to-ROM request, stack watermark, D7000 layout, SAVE service linked but disarmed. The fresh catalogue source-manifest gate passed. The target toolchain is JieLi pi32v2 from SDK V1.2.13 toolchain bundle `jieli-linux-toolchains-20250324.1`; container image ID `sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc` (`lunar-jieli-check:bookworm`). Build log: `/home/claude/mvave-fm1/realtime-event120-instrumented-20261014/build-v2.stdout`; exit receipt says `exit=0`.

[verified] Main artifacts are private scratch outputs, not committed:

- App: `/home/claude/mvave-fm1/realtime-event120-instrumented-20261014/out/link/artifact/app.bin`, 846,000 bytes, SHA-256 `26f13c5951844de2c98c6dd4b56162674e7c2032b2dba7e6aa4b7f121e9cd2ee`.
- ELF: `/home/claude/mvave-fm1/realtime-event120-instrumented-20261014/out/link/lunar-app-probe.elf`, SHA-256 `4fcf7a2c3be993bc708b2dc48f58e2ee1d90e8d1bb33eb2fbadc21c4d97e1c0d`.
- Artifact receipt: `.../out/link/artifact/artifact.json`, SHA-256 `aa9ca22e3e7bc456f17b32d163a2436cff062a7e40865d54b91db704c3675ee2`.
- Verification JSON: `.../out/link/verification.json`, SHA-256 `e48d0a18f92ad17e18b6efa4c4bd63cd701c270ffe7eecf4c76902068b02a9ec`.
- Vendor disassembly: `.../out/link/artifact/disassembly.txt`, SHA-256 `f6a2504aaf2ff70383ce84f92e02b0d36da7472149e556683412259e8f8ccc3d`.

[verified] Link, size/layout, and key audits passed. The app is 846,000 bytes against an 860,644-byte D7000 budget (14,644 bytes spare). The build receipt explicitly records `hardware_admitted=false`, `hardware_tested=false`, `hardware_candidate=false`, `installable=false`, `release_accepted=false`, empty flash write range, SAVE disarmed, and boot/OTA cleanup false. It records project and SET sequence semantics and native playback as unverified. Identity `FM-1_990` is implicit and package identity is unverified.

[verified] The existing readout formatter test was attempted on Hera host but could not link because the host lacks `/usr/lib64/libasan.so.8.0.0` and `/usr/lib64/libubsan.so.1.0.0`. That is an environment limitation, not a passing test. The target build itself linked and passed its audits; no separate formatter test result is claimed.

## Comparison and acceptance limits

[verified] Correction after device53 flash extraction: `43a5a8d7` / app `ba46bf0a…` is an offline comparison build, not the installed image. The device53 readback has raw SHA `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`; its decoded application is 845,036 bytes, SHA `5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573`. That installed build uses D9000, 55 modules and singleton Event Horizon content (5,100 bytes), whereas this footer link uses D7000, 54 modules and Event Horizon plus SET (6,232 bytes). It is therefore not a footer-only comparison against the installed hardware image. See `2026-10-14-installed-app-provenance-correction.md`.

[verified] This is a private diagnostic build only. It has not been installed or listened to, does not prove the footer’s counters explain the reported audio lag, and does not establish project/SET semantic or full-song acceptance. It is not an installable package and does not authorize SAVE or flash writes. The next step is coordinator review of the pinned artifact and, if chosen, a separately staged watched diagnostic run under existing recovery procedures.
