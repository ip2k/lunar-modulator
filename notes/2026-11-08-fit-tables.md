# 2026-11-08: fitting the soak image into V15's app slot by engine set and tables

Docs/18 M2 follow-up, lane "fit-tables". The eight-voice soak image
(`clk320-soak30/cap8-trunc12`, 597,916 B) is 16,352 B over V15's 581,564 B app
slot (`notes/2026-10-29-fm1-image-budget.md`). This note measures what the
engine set and the big tables cost, so the owner can decide what 1.0 contains
(docs/18 §3, decision 2). Nothing was sent to the FM-1 or to the dev kit; every
number is from an offline link on aeon.

## Method

- **Image.** The soak image is rebuilt on aeon from this tree: pinned AC79 SDK
  (e30b1ee, V1.2.13 libraries), the reviewed pipeline `system.a` (SHA-256
  `792c7599…`), `lunar-jieli-check:bookworm` with the cached JieLi toolchain,
  `prepare-pipeline-devkit.py --policy cap8 --worst-block --poly47-at-44100
  --cycles 57`. The rebuilt base is **597,916 B**, the soak image's figure
  [verified]. Its `.text`, `.ram0_data` and `.cache_ram_data` sizes (439,552 /
  131,184 / 27,180) match, and the two SRAM-placed images are byte-identical to a
  build with the unmodified make fragment; `.text` differs in four bytes, the
  `__TIME__` string [verified: `base` against `base0`].
- **Variants.** Each variant is one more link of the same tree with one input
  changed:
  - the engine set, through the new make variable `LUNAR_MODULES`
    (`tools/jieli/devkit-renderer-sdk.mk`; its default is the soak set, so an
    unset variable gives the same image);
  - preset entries switched off, through `tools/jieli/prepare-fit-variant.py`;
  - the engine optimisation level, by editing the generated fragment's `OPT=-O3`;
  - Macro models replaced by `VirtualAnalogEngine` in the prepared copy of
    `mi_macro.cc`, so the linker can drop the removed Plaits classes. Size
    measurement only.
- **Measure.** `tools/jieli/fm1_fit_table.py` (new) reads each linked ELF with
  `fm1_budget.measure`. App bytes are the sum of the ELF's load images. The kit
  build writes no `app.bin` offline, and for the soak image the sum equals the
  file [verified]. The SRAM column is the heap margin over the 47,212 B floor of
  `fm1_budget.py`.
- **Not done.** No variant was run: the dev kit was not used, and a variant's host
  replay hashes are not the soak image's, because dropping an engine changes the
  kit workload. Sizes are the evidence, not timing.
- Variants whose names start `no…` drop the named module or model. All builds are
  GPL-off (`FM1_GPL_MODS=0`) and `FM1_DX7_SINE=trunc12`, as the kit's fragment has
  always had them.

## Findings

1. **The soak image is already the GPL-off image.** `devkit-renderer-sdk.mk` has
   passed `FM1_GPL_MODS=0` all along. The three Felucca engines, the x0x kits and
   Acid Bass are not in it, so docs/18 §2.1's "drop out of a shared build" saves
   nothing further here [verified: the fragment and the symbol table].
2. **The whole non-GPL catalogue does not fit.** `FM1_MODULES=default`
   (`engines/modules/default.list`, GPL entries filtered by the switch) links to
   872,188 B, 290,624 B over the slot. The 1.0 engine set must be a subset
   [verified].
3. **The 50,688 B Plaits wave table is shared.** `plaits::wav_integrated_waves`
   is read by both the Wavetable and the Terrain models of Macro. Dropping either
   one saves about 2 KB; dropping both saves 55,008 B [verified]. This is the one
   lever that closes the gap alone.
4. **Optimisation level is a large lever and a timing risk.** The engines are
   built `-O3` (the preset's `renderer_o3`). `-O2` is 11,136 B smaller, `-Os`
   72,480 B, `-Oz` 94,304 B [verified: sizes]. The margins on the kit were 66% and
   82.8% means; whether `-O2` keeps them was not measured.
5. **Four derivable tables, 13,312 B in flash [inferred: arithmetic; the
   identities are verified].** Each could be filled into SRAM at init from a
   smaller flash image, with the same bytes:
   - `kSinTab12`: the full 4,096 entries equal the first 1,024 mirrored
     (`s[k] = s[2047-k]` for 1,024..2,047) and negated (`s[k+2048] = -s[k]`).
     Verified for every entry; integer only. Saves 6,144 B.
   - `kExp2Tab`: each pair's delta equals the next value minus this one (the last
     against 2^31). Verified for all 1,024 pairs; integer only. Saves 4,096 B.
   - `fm1_resampler_kernel_pairs`: the slope half is `f32(f32(k[i+1]-k[i]) *
     2^-16)`, the expression the preparer already rounds to produce the literals.
     Saves 3,072 B if the target's float arithmetic is IEEE single [inferred].
   - Not derivable: the wave table. Its first differences reach 1,024 and only
     7,793 of 25,152 fit an int8, so a lossless packing needs 12-bit codes and a
     prefix sum on every read. Rejected.
   - Not recommended: `kBankUnpacked` (4,992 B, derivable from `kBank`). Patch
     select copies it on the audio path, and the worst blocks of the soak were
     the first block after a program change (notes/2026-10-29-devkit-soak30.md).
   None of these is implemented. All three change where a table lives, so they
   wait for the FM-1 board layer's placement (M3) and the dev-kit hash replay.
6. **What does not help.** Moving SRAM-placed code back to XIP does not shrink
   `app.bin`: the code is in flash once either way. The 2026-10-29 note's
   "counts twice" is wrong on this point [inferred from the load-image
   arithmetic; not tested by moving code]. `rc_off` (the Drums readiness
   conversion off) is +32 B. The kit's own worst-block and pipeline marks cost
   1,568 B, and an FM-1 build drops them [verified: `nomarks`].
7. **Dropping Macro needs a kit change.** The preparer places the resampler
   tables in `mi_macro.cc` ("Macro is always present in this fixed diagnostic"),
   so a kit link without Macro but with Drums fails on undefined
   `fm1_resampler_*` tables. Kit variants without Macro also leave Drums out. In a
   non-kit build this is a header-level choice to make once (single external copy
   of the three resampler tables), not a size cost.

## The table

All rows are links of this tree. Slot margin is against 581,564 B. "SRAM" is the
heap margin over the kit's 47,212 B floor; the FM-1 build also needs about 23 KB
of display strip buffers the kit does not have (notes/2026-10-29-fm1-image-budget.md
[inferred]), so a row needs a heap margin of about +23,000 or more to be
believed on the SRAM side. "Cache" is cache RAM used of 28,672 B.

| Variant | app bytes | vs base | slot margin | SRAM | Cache | Lost |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **base (soak set, -O3)** | 597,916 | 0 | -16,352 | +1,632 | 27,180 | nothing |
| rc_off (Drums readiness conversion off) | 597,948 | +32 | -16,384 | +1,568 | 27,180 | a kit timing path |
| nomarks (no worst-block recorder) | 596,348 | -1,568 | -14,784 | +2,112 | 27,180 | kit-only recorder |
| no Wavetable model | 595,676 | -2,240 | -14,112 | +1,632 | 27,180 | 1 Macro model |
| no Terrain model | 595,868 | -2,048 | -14,304 | +1,632 | 27,180 | 1 Macro model |
| no PhaseDist model | 593,212 | -4,704 | -11,648 | +1,632 | 27,180 | 1 Macro model |
| no Wavetable + VA+Filter | 594,396 | -3,520 | -12,832 | +2,848 | 27,180 | 2 Macro models |
| **no Wavetable + Terrain** | **542,908** | **-55,008** | **+38,656** | +1,632 | 27,180 | 2 of 8 Macro models |
| no Wavetable, Terrain, PhaseDist | 538,204 | -59,712 | +43,360 | +1,632 | 27,180 | 3 Macro models |
| Macro = VA, Shaper, 2-op FM, Chip | 536,988 | -60,928 | +44,576 | +2,848 | 27,180 | 4 Macro models |
| no Drums engine | 573,116 | -24,800 | +8,448 | +23,712 | 27,180 | Drums |
| no Wavetable + Terrain, no Drums | 518,140 | -79,776 | +63,424 | +23,712 | 27,180 | both |
| no Filter effect | 583,708 | -14,208 | -2,144 | +5,600 | 27,180 | Filter |
| no Arp | 583,772 | -14,144 | -2,208 | +1,632 | 27,180 | Arp |
| no Env mod kind | 590,716 | -7,200 | -9,152 | +5,280 | 27,180 | Env |
| no Drive | 591,452 | -6,464 | -9,888 | +6,816 | 27,180 | Drive |
| no Chance | 592,764 | -5,152 | -11,200 | +6,048 | 27,180 | Chance |
| no Comp | 592,828 | -5,088 | -11,264 | +6,112 | 27,180 | Comp |
| no Echo | 593,020 | -4,896 | -11,456 | +4,576 | 27,180 | Echo |
| no LFO | 594,428 | -3,488 | -12,864 | +4,128 | 27,180 | LFO |
| no Filter, Drive, Echo, Comp | 567,228 | -30,688 | +14,336 | +18,208 | 27,180 | four effects |
| no Arp, LFO, Env, Chance | 556,284 | -41,632 | +25,280 | +14,112 | 27,180 | arp and mods |
| FM6 + effects + arp + mods only | 446,512 | -151,404 | +135,052 | +47,520 | 16,416 | Macro, Drums |
| FM6 only | 373,904 | -224,012 | +207,660 | +76,576 | 16,416 | all but FM6 |
| every non-GPL module (`default`) | 872,188 | +274,272 | -290,624 | +1,888 | 27,180 | none; does not fit |
| base at -O2 | 586,780 | -11,136 | -5,216 | +7,200 | 27,180 | timing, not content |
| base at -Os | 525,436 | -72,480 | +56,128 | +28,512 | 27,180 | timing, not content |
| base at -Oz | 503,612 | -94,304 | +77,952 | +40,608 | 27,180 | timing, not content |
| no Wavetable + Terrain, -O2 | 531,932 | -65,984 | +49,632 | +7,200 | 27,180 | 2 models, timing |
| derived sine, exp2, kernel slopes (arithmetic) | 584,604 | -13,312 | -3,040 | +1,632 | 27,180 | nothing; inferred |
| derived tables and -O2 (arithmetic) | 573,468 | -24,448 | +8,096 | +7,200 | 27,180 | timing; inferred |

The static SRAM of every Macro-only change is 474,712 B, because the renderer
pool is a fixed 139,264 B (`LUNAR_RENDERER_POOL_BYTES`). The SRAM column moves
only with Drums (about 22,000 B), the effects and mod kinds, and `-O2`.

## What each answer costs, for the decision

Recommendation, in the order I would try them:

1. **Ship 1.0 without the Terrain and Wavetable Macro models** (6 of 8 models
   stay). It is the only change that closes the gap alone, it is content, not
   timing, and it keeps 38,656 B of slot margin for the FM-1 board layer (M3).
   Cost: two models of one engine go, and Macro's Model parameter and saved
   states must keep the two indices reserved, or be re-numbered.
2. If the two models must stay: **derive the three tables and move the
   engines to `-O2`**, +8,096 B by arithmetic. That needs the dev kit to confirm
   timing and bit-identical PCM, and still leaves SRAM about 21 KB short of the FM-1's
   display buffers (SRAM column), so it does not finish the job.
3. **Drums** (24,800 B and about 22,000 B of SRAM) is the single biggest SRAM
   lever; an FM-1 image that needs the display buffers probably needs it or an
   equal SRAM cut. That is a separate decision from flash.

The SRAM side is not solved by anything here except dropping Drums or most of
the effects: the soak set has +1,632 B of heap against the kit's own floor and
about 23 KB more is needed on the FM-1 [inferred].

## Retained-engine audio

No retained engine's source changed. The only tracked changes are a make
variable (default equal to the old literal), two offline tools and a test. The
soak image's `.ram0_data` and `.cache_ram_data` are byte-identical with and
without the make change [verified], and `.text` differs only in `__TIME__`.
`pytest tests/test_fm1_fit_table.py tests/test_fm1_budget.py
tests/test_prepare_pipeline_devkit.py tests/test_dx7_sine.py
tests/test_devkit_diagnostics.py tests/test_pipeline_bounds.py
tests/test_module_list.py`: 162 passed. The size-only variants edit a prepared
copy and are never installable; the optimisation-level rows change generated code
and need the kit's hash replay before anyone counts them.

## Owner decision

**What 1.0 contains if trimming is required.** Options, measured above: (A) drop
Macro's Terrain and Wavetable models (recommended); (B) keep every model and
spend `-O2` plus derived tables, kit-verified; (C) also drop Drums for SRAM.
Asked 2026-11-08; answer to be recorded in docs/18 §3.

## Left on disk

The LAN scratch is `/datasets/lunar-modulator/fm1-wave1/fit-tables/` on aeon
(SDK copies removed after each link, the linked ELFs, logs and a source copy),
deleted when this PR is opened. The ELFs and logs are not committed.
