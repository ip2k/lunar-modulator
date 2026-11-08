# 2026-10-29: the soak image against the FM-1's app slot and SRAM

Docs/18 M2. `tools/jieli/fm1_budget.py` (tests: `tests/test_fm1_budget.py`)
checks an `app.bin` and its linked ELF against V15's app slot and the FM-1's
SRAM. Run on the 30-minute soak image (`clk320-soak30/cap8-trunc12`,
`app.bin` and `sdk.elf` from the same build, SDK pin e30b1ee). Nothing was
sent to the FM-1; the tool reads files only.

## Limits used

- App slot: `app.bin` at flash 0x4120, `cfg_tool.bin` at 0x920DC, so
  0x920DC - 0x4120 = **581,564 B** [verified: V15 layout, notes/2026-09-06-bench.md,
  docs/01 §2]. The limit holds only while cfg, OTA loader and layout stay
  byte-identical to stock [inferred: CLAUDE.md conventions]. The kit's own
  bound is 601,824 B (writer stops at 0x97000, `pipeline_bounds.py`); it is not
  the FM-1's.
- SRAM: 578 KB on chip [verified: SDK README]; the app's SRAM runs from
  0x01C00000 to `boot_info` at 0x01C7FD4C, 523,596 B [verified: SDK
  `sdk_ld_sfc.c`]. Stock's own static data ends at 0x01C211FC (135,676 B), which
  leaves the 387,924 B "SRAM gap" to 0x01C7FD50 [inferred: docs/11 §2,
  engines/README.md]. The brief's "about 379 KB" is the same 387,924 B in KiB
  (378.8), as the web-editor note says; the docs agree. The gap includes stock's
  heap [inferred], so the gate compares static RAM plus a minimum heap with the
  whole 523,596 B, which is the same arithmetic as gap plus stock's static.
- Minimum heap 47,212 B: the kit's pipeline needs 43,512 B after the DAC opens
  plus a 3,700 B floor [inferred: `pipeline_bounds.py`, one board's logs].
- Cache RAM 0x01F28000-0x01F2F000, 28,672 B [reported: fm1-nes].
- Stock SPL body 0x01C02000-0x01C05820 [verified: handover layout audit].

## Measured (soak image)

| | bytes |
| --- | --- |
| `app.bin` | 597,916 [verified] |
| V15 slot | 581,564 |
| **Overflow** | **16,352 (2.8 %)** |
| `.text` / `.ram0_data` / `.cache_ram_data` load images | 439,552 / 131,184 / 27,180 (sum = `app.bin`, `.data` and `.dynamic_data` empty) |
| RAM static (`.ram0_data` 131,184 + `.ram0_bss` 343,528) | 474,712, ends 0x01C73E58 |
| Heap (`HEAP_END - HEAP_BEGIN`) | 48,844, 1,632 above the 47,212 floor |
| Cache RAM used | 27,180 of 28,672 |
| SPL body overlap | 14,368 B, all by `.ram0_data` |

- **Verdict: overflows the slot by 16,352 B; fits the SRAM only by 1,632 B** over
  the dev-board heap floor [verified: tool output; floor inferred].
- The SPL overlap is expected for a flash-installed app: stock's `.data`
  (0x01C00000-0x01C09E7B) covers the same range [verified: docs/01 §2 addresses].
  It matters only for a RAM-run image that must keep the SPL alive
  (`--spl-hole fail`).
- The SRAM fit does not carry over. Stock keeps two 11.5 KB display strip
  buffers [reported: docs/01 §2], and the kit renders no display
  (`FM1_TFT_EXTERNAL_PIXELS=1`), so the FM-1 image needs about 23 KB more than
  the 1,632 B of heap margin [inferred]. That agrees with docs/18 M6 ("does not
  fit in SRAM"), by this arithmetic, not by a measured FM-1 link.

## What the size is made of

There is no linker map in the artefacts (`-Map` is not passed by the kit
build; only `sdk.elf`, its symbol table and the logs). The image is LTO, so
the symbol table is by symbol, not by object; names are the only attribution
[inferred].

- Largest symbols: `plaits::wav_integrated_waves` 50,688 B in `.text` (the
  Plaits wavetable data), `apply_op` 19,172 (msfa), two LTO-merged global blobs
  16,304 and 15,528, `fm1_mod_script_apply` 7,776, `fm1_seq_advance` 7,220,
  `malloc` 6,066.
- Rough split of `.text` symbols by name: Plaits/stmlib about 74 KB, msfa/DX7
  about 37 KB, Lunar's own (fm1_/mod_/seq_/arp_/pipeline) about 77 KB, libc and
  libc++ about 51 KB, SDK drivers and file system about 45 KB, unclassifiable
  (mostly our own static functions and merged globals) about 164 KB. The symbols
  sum to 448,780 B against a 439,552 B section, so these are indications, not
  an accounting.
- No Bluetooth or Wi-Fi stack is linked: no `bt_`, `ble`, `wifi`, `lwip`
  functions of any size are in the table, and the build uses `CONFIG_NO_SDRAM`
  with the update/OTA and file-system code of the kit. SDK libraries are a small
  part of the overflow; the engines and tables are the bulk [inferred from names].
- `.ram0_data` (131,184 B) is hot code and tables placed in SRAM by the
  perf-levers work; it ships in flash and is copied at start-up, so it counts
  against the slot twice over what it saves in XIP, and so do the 27,180 B of
  cache-RAM tables. Together the two SRAM-placed load images are 158,364 B, 26 %
  of the image. Moving 16,352 B of that back to XIP, or dropping the 50,688 B
  wavetable, each closes the gap; both cost cycles or content.
- Biggest RAM objects: the renderer `pool` 139,264 B (`LUNAR_RENDERER_POOL_BYTES`),
  `app` 117,632, `pipeline_work_storage` 46,328, `pipeline_recorded` 10,288.

## Is the kit image comparable to an FM-1 image?

- Format: yes. The kit `app.bin` is the SDK's flat image from 0x02000120 (text,
  then the data initialisers), the same layout as the V15 `app.bin` whose
  `.data` initialiser image sits inside it [verified: ELF load-image sum equals
  the file size; V15 `jlfw.yaml` entry point]. Flash encryption does not change
  the length [inferred].
- SDK base: the same V1.2.13 libraries the FM-1 build is pinned to (trap 11)
  [verified: `sdk_commit_required`]. The kit uses the SDK's own boot path; an FM-1
  build adds the `boot_info` bridge and no SDK key blobs, a few hundred bytes
  [inferred].
- Differences that move the number, all [inferred]: the kit carries its DAC
  path, SD/FAT and VM code, UART boot command, benchmark and pipeline marks
  (`FM1_APP_PIPELINE_MARKS=1`), which an FM-1 build drops; the FM-1 build adds
  the display driver, key matrix, ALNK0 codec, MIDI UART and the panel UI. The
  net is unknown until M3's board layer links, so 16,352 B is an estimate of the
  overflow's order, not the FM-1 figure.
- The gate is therefore a tool for the real FM-1 link; this run is its
  calibration point, not a verdict on 1.0.

## Not done

- No FM-1 link exists, so no FM-1 `app.bin` or SRAM figure is measured.
- No map file: per-object attribution needs `-Map` in the kit build.
- The 47,212 B heap floor is one board's log; an FM-1 board layer may need more
  or less.
