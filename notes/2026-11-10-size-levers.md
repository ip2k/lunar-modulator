# 2026-11-10: size levers for the full-UI FM-1 image

docs/18 §3 item 9 ("measure, then decide"), lane `size-levers`. Branch
`feature/2026-11-10@size-levers`, from `091df132` (main after PR #188).

**The problem.** With the full UI on (`LUNAR_FM1_FULL_UI=1`,
`notes/2026-11-09-controls.md`), the FM-1 app image is 620,700 B. V15's app
slot is 581,564 B, so the image is 39,136 B over. With USB-MIDI on as well it is
627,772 B, 46,208 B over. The owner wants to keep all eight Macro models if
possible. The M10 soft locks must be lifted before 1.0 (docs/18 §3 item 8),
which adds code. This note measures each lever, alone and combined.

**Result.** One combination fits and keeps every feature: `--size-levers
control`, the new switch on `prepare-fm1-app.py`.

- **Size.** The full-UI image becomes 573,436 B: 8,128 B under the slot, with
  1,664 B more heap than today [verified: offline link, `audit_link` PASS,
  `fm1_budget`]. With USB-MIDI on it is 580,604 B, 960 B under the slot
  [verified].
- **Audio.** On the dev kit the same unit set gives bit-identical audio (all
  four case hashes match main) [verified].
- **Timing.** The producer's mean block time rises by about 2.4%, from 76.0% to
  77.8% of the budget. The full-workload producer late blocks go from 2 to 6.
  All of them were absorbed by the buffer: no fault, gap or underrun
  [verified: kit receipts].
- **Not run on the FM-1** (no FM-1 traffic in this lane).

Both new switches default to off, and the default image is unchanged except
for its build-id constant [verified].

## 1. Method

**FM-1 image.** Each FM-1 image was built offline on aeon from a `git archive`
of this branch's commit `8aacd792` (and `origin/main` for the reference), using:

- `prepare-fm1-app.py`;
- the pinned AC79 SDK (`e30b1ee`, V1.2.13 libraries);
- the reviewed pipeline `system.a`;
- `lunar-jieli-check:bookworm` with the cached JieLi toolchain.

The app bytes are the ELF's load images, concatenated in link order. They equal
`fm1_budget`'s ELF check (`elf_matches_app_bin`) for every row. Each image then
went through two checks:

- `audit_link.py`. Every row passed, with 0 fail and 1 pending: the pending
  item is the usual one, the hardware run.
- `fm1_budget.py`. It reports the slot margin, and the heap margin over its
  47,212 B minimum. Cache RAM is 27,180 of 28,672 B in every row.

**Exploration builds.** The single-lever rows in §3 came from exploration
builds, made before the switches existed, on an aeon copy of main with these
local hooks:

- an `XOPT`/`XUNITS` hook in `size-profile.mk`;
- `fm1_live.h` with the full UI forced on;
- for some rows, source patches.

None of those hooks is in the repository. The rows in §2 are built from the
committed switches alone.

**Kit timing.** The dev kit cannot run the FM-1 app image (it has a different
pin map and no ALNK0 codec), so the kit runs the pipeline image instead:

- built with `prepare-pipeline-devkit.py --policy cap8 --worst-block
  --size-profile`;
- the same lever applied through the `XOPT` hook to the same unit list;
- installed on bench01's AC79 kit at USB path 3-1.2 through the unattended UART
  cycle (`CLAUDE.md`, 2026-10-26 rules): acknowledged UART enter, an app-only
  install of sectors `0x4000`–`0x97000`, a 180 s UART capture, one loader
  reset.

Results were parsed with `tools/devkit_pipeline_result.py`. That image runs
`fm1_app`'s pipeline produce and consume paths with the renderer and every
engine, on a fixed four-case workload, 66,156 blocks in about 96 s.

**What the kit run does not cover** [inferred: from the workload's source]. It
does not run the panel handlers, the drained barrier (`ui_after`), `arp_poll`
or the display. So the timing covers the per-block path, not the UI's own
latency. That latency was already unmeasured (`notes/2026-11-09-controls.md`
§"Owner decisions" 3).

**Device traffic.** Nothing was sent to the FM-1 or to the Pico transporter.

## 2. The switches, measured (committed tree)

`prepare-fm1-app.py` gains two options, both off by default:

- `--full-ui on|off` sets `LUNAR_FM1_FULL_UI=1`, which until now was a source
  edit (`fm1_live.h` already honours a `-D`).
- `--size-levers off|cold|control` selects the size levers.

Each option enters the build-id option string only when it is not the default.

| Build (GPL 0 unless stated) | app.bin | Slot margin | Heap margin | audit_link |
| --- | ---: | ---: | ---: | --- |
| main, default (`--full-ui off`) | 550,300 | +31,264 | +960 | PASS |
| this branch, default | 550,300 | +31,264 | +960 | PASS |
| `--full-ui on` | 620,700 | **−39,136** | +1,728 | PASS |
| `--full-ui on`, GPL 1 | 620,700 | −39,136 | +1,728 | PASS |
| `--full-ui on --usb-midi on` | 627,772 | −46,208 | +896 | PASS |
| `--full-ui on --size-levers cold` | 609,884 | −28,320 | +1,856 | PASS |
| `… cold --usb-midi on` | 617,052 | −35,488 | +1,056 | PASS |
| **`--full-ui on --size-levers control`** | **573,436** | **+8,128** | **+3,392** | PASS |
| `… control`, GPL 1 | 573,436 | +8,128 | +3,392 | PASS |
| `… control --usb-midi on` | 580,604 | +960 | +2,592 | PASS |
| `… control --usb-midi on`, GPL 1 | 580,604 | +960 | +2,592 | PASS |

All rows are [verified]. Notes on the table:

- **The default images.** Main's and this branch's default images differ in 4
  bytes, one 32-bit immediate at app offset `0x19D44`. That is the failopen
  build-id constant, which hashes the preparer and `fm1-app.mk`, both changed
  here [verified: `cmp`; inferred: that the constant is the build id].
- **GPL is not a lever.** No GPL module is in `LUNAR_MODULES`, so GPL 0 and 1
  link the same size. An exploration build from a different tree path differed
  by 32 B of path strings.

### What `cold` does

1. **Cold units at `COLDOPT` (`-Oz`).** These are the translation units that
   run only on an edit, a load, a save, at boot or in panel drawing, never in a
   block or at the drained barrier:
   - the modulation editor UI and app state;
   - the state codec (JSON, binary, deflate, Movy import, names, registry);
   - sequence persistence;
   - the editor metadata;
   - the panel probe and test pattern;
   - the fm1-nes key tables.

   `tools/jieli/size-profile.mk` already puts five others at `-Oz`.
2. **A smaller `strtod`/`strtof`.** The modulation script and the editor are
   compiled with `-Dstrtod=lunar_fm1_strtod -Dstrtof=lunar_fm1_strtof`.
   - **Why.** Their LTO bitcode symbol tables pull newlib's `strtod.o`, its
     multi-precision helpers and its locale objects into the link before LTO
     finds the callers' text. That costs about 7 KB.
   - **The replacement.** `firmware/fm1/fm1_strtod.c` (new, MIT) is Clinger's
     exact fast path. It returns only correctly rounded values and refuses
     everything else (returns 0 with `*end == s`):
     - hexadecimal, inf and nan;
     - more than 19 significant digits;
     - powers of ten beyond the exact range;
     - float double-rounding ties;
     - subnormal floats.

     Both callers treat a refusal as "not a number".
   - **Test.** `tests/test_fm1_strtod.py` checks 60,105 inputs against the host
     C library. Every value it accepts is bit-identical with the same end
     pointer, every value it refuses comes back as 0, and it must accept more
     than 60% of them [verified: 2 passed].

**SRAM effect of `cold`.** Its SRAM code is identical to the full-UI baseline's
function for function. Only newlib's locale objects leave SRAM: `lconv`, the
charset strings and `__mb_cur_max`, −136 B [verified: `nm`, names normalised].

### What `control` adds

`control` also builds these at `COLDOPT`:

- `fm1_app.c`, the app, including its pipeline produce and consume steps;
- the step-sequencer UI and capture;
- the key, encoder, ADC and MIDI input;
- `fm1_live`;
- the display transport.

**It leaves these alone.** The sequencer engine, the arpeggiator, the effect
hosts and the modulation runtime keep the build's level, because at `-Oz` they
cost 6.4% (§4). So do the renderer and every engine, which stay at `-O3`.

**SRAM effect of `control`.** It changes SRAM code: about −1.7 KB. For example,
`fm1_app_pipeline_produce` goes from 3,522 to 3,050 B, and `render_fx` is
inlined [verified: `nm`].

## 3. Single levers (exploration builds; full UI, GPL 0, USB off)

| Lever | app.bin | vs baseline | Evidence |
| --- | ---: | ---: | --- |
| Baseline (full UI) | 620,700 | 0 | [verified] |
| Cold set at `-Oz`, no strtod change | 616,956 | −3,744 | [verified]; SRAM identical |
| Cold set plus the panel and input units at `-Oz` | 615,644 | −5,056 | [verified] |
| The same, at `-Os` instead | 616,124 | −4,576 | [verified] |
| strtod/strtof replaced (both parsers) | 613,628 | −7,072 | [verified] |
| `fm1_app.c` alone at `-Oz` | — | −16,320 | [verified: per-unit link] |
| `fm1_seq_ui.c` alone at `-Oz` | — | −17,312 | [verified: per-unit link] |
| `fm1_mod_ui.c` alone at `-Oz` | — | −3,712 | [verified: per-unit link] |
| `control`'s unit set at `-Oz` (no strtod) | 580,476 | −40,224 | [verified] |
| … and the sequencer engine, arp, effect hosts, modulation runtime (`-Oz`) | 547,484 | −73,216 | [verified] |
| … the same at `-Os` | 557,148 | −63,552 | [verified] |
| … the same at `-O2` | 608,156 | −12,544 | [verified] |
| `minsize` attributes on the UI handlers in three files only | 604,860 | −15,840 | [verified] |
| Macro's Terrain and Wavetable built as VA (reference only) | 565,724 | −54,976 | [verified] |
| A stub for the one FAT symbol `vfs.c.o` needs | 577,852 | −42,848 | [verified: size only; never booted] |
| Derived tables filled at init (sine mirror, exp2 deltas, kernel slopes) | — | about −13,312 | [inferred: arithmetic, `notes/2026-11-08-fit-tables.md` §5] |

Notes:

- **The "three files" row** applies `__attribute__((minsize))` to the UI
  handlers in `fm1_app.c`, `fm1_seq_ui.c` and `seq_capture.c`, leaving their
  per-block functions alone. It has no measurable timing cost (§4), but it is
  source annotations, not a switch, and it saves less than half of `control`.
- **The FAT stub row.** The stub would leave the SDK's file system unable to
  scan subdirectories. It is a measurement, not a candidate, until a kit or
  FM-1 boot shows nothing reaches it. It is excluded from the recommendation.
- **The derived tables** were not implemented. Two reasons:
  - **Placement.** The tables live in `.cache_ram_data`, and filling them at
    init needs a NOLOAD cache-RAM bss output section. The SDK's
    `.cache_ram_bss` (`sdk_ld_sfc.c`) is not NOLOAD and holds `memp_memory_x`.
  - **Verification.** It needs a kit hash replay.

  With `control` and the tables together, the margin would be about +21.4 KB
  with USB off and +14.3 KB with USB on [inferred].

## 4. Dev-kit timing (pipeline image, same session, 2026-11-10)

Timing is in 24 MHz ticks. The block budget is 34,829 ticks, and the mean rule
is ≤ 29,604 (85%). Per-case producer means are for cases 0 to 3.

| Image | Producer means, cases 0–3 | Whole producer mean | Producer late blocks | Max `p_max` | Case hashes |
| --- | --- | ---: | ---: | ---: | --- |
| `kb` main | 23,798 / 26,663 / 27,767 / 27,703 | 26,483 (76.0%) | 2 | 38,909 | b587a942 d8a97c43 964c7c0f 859d06bc |
| `ka` = `control` | 24,394 / 27,284 / 28,421 / 28,349 | 27,112 (77.8%) | 6 | 41,541 | identical |
| `kc` = `control` + engine/arp/mod at `-Oz` | 25,475 / 28,348 / 29,469 / 29,398 | 28,172 (80.9%) | 51 | 43,245 | identical |
| `kf` = `minsize` handlers, 3 files | 23,742 / 26,599 / 27,708 / 27,640 | 26,422 (75.9%) | 2 | 39,960 | identical |
| `kb2` main, repeat (last run) | 23,801 / 26,668 / 27,770 / 27,705 | 26,486 (76.0%) | 2 | 39,041 | identical |

Every run produced 66,156 blocks with 0 faults, 0 gaps, 0 underruns and 0
consumer late blocks [verified: receipts]. Each run, main's included, ends with
`LUNAR_PIPELINE failure_line=370`, which the parser classifies as the
per-block deadline flag set by those buffered late producer blocks. `kb2`
repeats `kb` within 5 ticks per case mean, so differences of a few hundred
ticks between images are real. The kit was left on `kb2`: main's pipeline
image, built from `091df132` with the exploration hook empty. A late producer block is one over
the per-block deadline that the 64-block buffer absorbed. Findings:

- **`control` costs about 630 ticks a block (+2.4%)** and adds 4 buffered late
  producer blocks out of 66,156. The extra time is presumably in
  `fm1_app_pipeline_produce` and the step-sequencer sync, which run every
  block and are the SRAM functions that changed [inferred: from `nm`].
- **The sequencer engine, the arpeggiator and the modulation runtime must stay
  at `-O3`.** At `-Oz` they add about 1,700 ticks (+6.4%) and 51 late blocks.
  That is why they are not in `control`.
- **The `minsize` attributes on handlers cost nothing measurable.**
- **An observation on main itself** [verified: `kb`, `kb2`].
  - The whole consumer mean is 31,992 ticks, 91.9% of the budget. So
    `means_pass` is already false on main, for the consumer side, in every run
    here, levers or not.
  - The October receipts had a consumer mean near 28,300.
  - The consumer's mean includes its wait for the codec's half-buffer
    [inferred]. Whether this is a regression in main or a change in what the
    receipt measures is not investigated here. It is not caused by these
    levers: identical across all five images (31,966–31,992).

## 5. The soft locks: room needed [inferred]

Lifting the M10 soft locks (docs/18 §3 item 8) means letting engine and insert
selection, effect order and Macro's model change while audio plays, as R0 does.
The pipelined app would then have to:

- drain;
- re-run its geometry preflight for the new engine set;
- re-seal at the barrier.

It would also have to drop the `value[0]==0` hold on Macro.

The engines' own code is already linked: the Plaits models are in the image
today, only unreachable. So the new code is control logic, an estimated 3–8 KB
[inferred: the size of today's preflight and seal paths in `fm1_app.c`, not
measured]. Against that:

- `control` with USB off (+8,128 B) probably absorbs it;
- `control` with USB on (+960 B) does not.

The next feature-preserving lever is the derived tables (about 13 KB).

## 6. Recommendation (owner decision)

1. **Adopt `--size-levers control` for the full-UI FM-1 image** (recommended).
   - It fits V15's slot with 8,128 B to spare with USB off.
   - All eight Macro models stay.
   - Audio is bit-identical on the kit.
   - It costs about 2.4% of the producer's mean block time.
   - Before shipping it still needs the M5/M6 hardware gates that every FM-1
     image needs, and a kit run of the full-UI barrier.
2. **If the soft-lock work or USB-MIDI overflows that margin**, implement the
   derived tables next (about 13 KB, needs the NOLOAD cache bss and a kit hash
   replay). After that, the reference lever is dropping Terrain and Wavetable
   (55 KB), which the owner prefers to avoid.
3. **Do not use** the full control set at `-Oz` (6.4%, 51 late blocks) or the
   FAT stub (unbooted, removes a file-system path).

If there is no decision, both switches stay off, and today's shipped image and
its build stay exactly as they are.

## 7. Files

- `tools/jieli/prepare-fm1-app.py`: `--full-ui`, `--size-levers`; receipt
  fields `full_ui` and `size_levers`.
- `tools/jieli/fm1-app.mk`: the cold and control unit lists, the strtod
  mapping, and the guard that `control` needs `cold`.
- `firmware/fm1/fm1_strtod.c`, `tests/test_fm1_strtod.py`: new.
- `tests/test_prepare_fm1_app.py`: switch flags and build ids; the unit lists
  map to real sources, include no renderer or engine unit, and keep the
  per-block runtime out.

Exploration scripts, logs, `nm` dumps and maps stay in the lane's aeon scratch,
not in the repository.
