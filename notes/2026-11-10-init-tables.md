# 2026-11-10: derived tables filled at startup ("Control + build tables")

docs/18 §3 item 9, lane `init-tables`. Branch `feature/2026-11-10@init-tables`,
cut from `fe834266` (main after PRs #192 and #194). Measured images were built
from `fe834266` (main) and `f2cf8e4e` (this branch's first commit). The later
commits change comments, the receipt parser and docs only.

**The decision.** The owner chose "Control + build tables": the 1.0 FM-1
image is `prepare-fm1-app.py --full-ui on --size-levers control` plus lever
(a) of `notes/2026-11-10-size-levers.md`, derived tables computed at startup.
USB-MIDI stays off (docs/18 §3 item 7).

**Result.**

- **Size.** The four tables save **15,140 B** of flash in every
  configuration [verified: offline links]. The control full-UI image goes
  from 5,568 B to **20,708 B** under V15's slot. Heap rises by 64 B.
- **Selection.** One named way to build it:
  `prepare-fm1-app.py --profile fm1-1.0`. The profile is the same as `--full-ui on
  --size-levers control --init-tables on --usb-midi off`. The default image
  is unchanged except for its build id.
- **Audio.** On the dev kit all four case hashes equal main's.
  - The target's own check prints `LUNAR_INIT_TABLES bad=0` with the hash of
    every entry of all four tables, and each hash equals the host's [verified].
  - The producer's mean block time rises **397 ticks (+1.5%)**, from 74.2% to
    75.3% of the budget. Late blocks are unchanged: 2 in each image.

## 1. The tables

All four are derived arrays that this tree defines itself. A generator,
`tools/init_tables.py`, reads each stored table from its source file and
proves that the derivation reproduces it exactly before it writes anything. It
refuses ("is not exactly derivable") if any entry differs. Its output,
`engines/src/fm1_init_tables.cc`, holds:

- the seeds, as const data in flash;
- `lunar_init_tables()`, which fills every entry of all four tables;
- under `FM1_INIT_TABLES_CHECK`, `lunar_init_tables_check()`, which hashes
  each table (FNV-1a over each entry as a 32-bit word).

| Table | Stored | Seed kept | Identity |
| --- | ---: | ---: | --- |
| `fm1_msfa::kSinTab12[4096]` (msfa_rom.cc) | 8,192 B | quarter wave, 2,048 B | `T[k]=T[2047-k]=s`, `T[2048+k]=T[4095-k]=-s` |
| `fm1_msfa::kExp2Tab[2048]` (msfa_rom.cc) | 8,192 B | 1,024 values, 4,096 B | odd entries are values; each even entry is the next value minus this one, the last against 2^31 |
| `fm1_resampler_kernel_pairs[1536]` (stored-table build, `resampler_slope_definition`) | 6,144 B | 769-tap kernel, 3,076 B | `P[2i]=K[i]`, `P[2i+1]=(K[i+1]-K[i])*(1/65536)` in float32 |
| `plaits::lut_sine[641]` (resources.cc, MIT, Emilie Gillet) | 2,564 B | 131 values, 524 B | `s[128+k]=s[128-k]`, `s[256+k]=-s[k]`, `s[512+k]=s[k]` |
| **Total** | **25,092 B** | **9,744 B** | |

**Bit-exactness.**

- The integer tables and the mirrored sine are copies and negations, so
  they are exact by construction.
- The kernel slope is one float32 subtraction and one multiplication by a
  power of two. It is exact under IEEE single precision. The image is built
  without `-ffast-math` and with `-ffp-contract=off`, so no fused
  multiply-add can change it.
- The sine seed is written as the same double literals as `resources.cc`,
  without an `f` suffix, so each float is rounded once, as the stored table is.
- The host build compares every entry of all four tables at `-O0`, `-O2` and
  `-Os` (`tests/test_init_tables.py`).
- The dev kit's pi32v2 build prints the four hashes, and they equal the host's
  [verified: §4].

**Vendored output.** Vendored output is unchanged: `resources.cc` and
`msfa_rom.cc` keep their tables. The preparer drops the four definitions only
from its private copies, and only with `--init-tables`. Every hash and render
in §4 matches main.

**Not derived.** Every other table stays stored: the exponential and pitch
LUTs, the wavetables and the DX7 ROM. This lane looked for no further
candidates. The four above are the lever that size-levers estimated at about
13 KB.

## 2. Placement and ordering

**Placement.**

- The tables live in a new output section, `.lunar_cache_init ALIGN(4)
  (NOLOAD)`. It is placed in `cache_ram` after the SDK's `.cache_ram_bss`, not
  inside it.
- In the `fm1-1.0` image the section is `BSS`, 0x6204 B (25,092), at
  `0x1F28828` [verified: vendor `objdump -h`, `nm`].
- The tables are no longer in `.cache_ram_data`. That section shrinks from
  0x6A2C to 0x828 B, so the flat `app.bin` no longer carries them.
- Cache RAM still ends at `0x1F2EA2C`, the same address as on main: 1,492 B
  are left in the 28,672 B locked region.
- `audit_link.py` passes and `sram_budget` passes for every image in §3.

**Ordering.** Verified in the disassembly of the kit image (`kt`) and the
`fm1-1.0` FM-1 image (`t-p1`):

1. `startup.S` calls `cache_way_config` once (`0x200020A`; no other call
   site). It locks the ways, `memmove`s `.cache_ram_data` from flash and
   `memset`s `.cache_ram_bss`, which is 0 B. Nothing touches `.lunar_cache_init`.
2. In `main`, LTO inlines `setup_arch()`, and the call to
   `lunar_init_tables()` is inlined into it, so it has no symbol of its own.
   It runs after `p33_io_latch_init()` and before `os_init`, `task_create` and
   `os_start`. CPU1, the audio tasks and the first audio block all start after
   that point, so every table is complete before anything reads it.
3. Before the call the tables hold whatever the RAM held. The host test shows
   the check fails on all four before the call (mask 15) and passes after it.

The tables share one risk with the stored tables on main [inferred]. Main's
cache-RAM tables are also written only once at boot, by the same
`cache_way_config`. So any later path that dropped the locked ways would break
main too. No such path was found.

**Boot time.** The fill is 8,321 stores. Its time was not measured
[inferred: well under 1 ms at 360 MHz].

## 3. Size and heap, offline links on aeon

All images were linked with the pinned SDK V1.2.13 (`e30b1ee`). Each passed
`audit_link: PASS (0 fail, 1 pending, linked)` and `fm1_budget.py`
[verified]. The V15 slot is 581,564 B and the heap minimum is 47,212 B.
GPL 0 and GPL 1 give the same sizes.

| Image | `app.bin` | Slot margin | Heap | Over minimum |
| --- | ---: | ---: | ---: | ---: |
| default, main | 551,260 | +30,304 | 48,076 | +864 |
| default, this branch | 551,260 | +30,304 | 48,076 | +864 |
| `--full-ui on --size-levers control`, main | 575,996 | +5,568 | 50,412 | +3,200 |
| **`--profile fm1-1.0`** | **560,856** | **+20,708** | **50,476** | **+3,264** |
| control, USB-MIDI on, main | 582,652 | −1,088 | 49,580 | +2,368 |
| control + tables, USB-MIDI on | 567,544 | +14,020 | 49,644 | +2,432 |

**The default image.** The default image differs from main's in 4 bytes
[verified: `cmp -l`]:

- three bytes of the 32-bit build-id immediate (`0x4590eaa5` →
  `0xff90018c`). It hashes the preparer, which changed.
- one digit of `__TIME__` in the SDK's banner.

**USB.** With USB-MIDI on, the control image does not fit (1,088 B over). With
the tables it fits, with 14,020 B to spare. USB stays off by the owner's
decision (docs/18 §3 item 7). This only shows that the tables leave room for
it.

## 4. Dev-kit replay (pipeline image, same session, 2026-11-10)

**The images.** The kit cannot run the FM-1 image, so it runs the pipeline
image:

- `prepare-pipeline-devkit.py --policy cap8 --worst-block --size-profile`;
- `km` is main;
- `kt` is the same image with `--init-tables`, which also builds the target
  check.

The init unit is built at `COLDOPT=-Oz` with the same LTO flags in both the kit
and FM-1 builds [verified: build logs]. The FM-1 build leaves out the check.

**The run.** All three runs were in one session on bench01, holding
`~/.lunar-devkit.lock` throughout: `km`, then `kt`, then `km2` (main again).
Each run did the following:

1. acknowledged UART ROM entry;
2. a target check: exactly one `4c4a:8057`, at `3-1.2`, and `1-2` is the
   Pico transporter;
3. an app-only install of sectors `0x4000`–`0x97000` (11.6 s);
4. a 180 s receive-only UART capture;
5. one loader reset.

Results were parsed with `tools/devkit_pipeline_result.py`. Timing is in
24 MHz ticks. The budget is 34,829 ticks, and the mean rule is ≤ 29,604 (85%).

| Image | Producer means, cases 0–3 | Whole producer mean | Producer late blocks | Max `p_max` | Case hashes |
| --- | --- | ---: | ---: | ---: | --- |
| `km` main | 23,131 / 26,023 / 27,119 / 27,062 | 25,834 (74.2%) | 2 | 39,528 | b587a942 d8a97c43 964c7c0f 859d06bc |
| `kt` tables | 23,538 / 26,413 / 27,521 / 27,453 | 26,231 (75.3%) | 2 | 38,808 | identical |
| `km2` main, repeat | 23,134 / 26,029 / 27,127 / 27,069 | 25,840 (74.2%) | 2 | 39,960 | identical |

**Every run** produced the following [verified: receipts]:

- 66,156 blocks;
- 0 faults, 0 DAC gaps and 0 consumer late blocks;
- zero underruns;
- the same soak fold, `1a000058`;
- `LUNAR_PIPELINE failure_line=370` at the end. This is the per-block deadline
  flag set by the two buffered late producer blocks. Main's runs show it too.

**The tables' check.** `kt` printed `LUNAR_INIT_TABLES bad=0 sin12=7fc5c845
exp2=01a4d02b pairs=f4de843d lut_sine=d70ef728` 1.2 s into the capture. These are
the host generator's hashes of the stored tables. The parser now reads this
line and refuses a run whose mask is not 0.

**The kit's final image.** The kit was left on `km2`: main's pipeline image,
built from `fe834266`, target sha256 `d2ec7d20…5004`. It answered a PING
afterwards.

**Timing.** `km2` repeats `km` within 8 ticks in every case. So the +397 ticks
of `kt` are real, and they are nearly flat across cases (+390 to +407).

The cause is not pinned [inferred]. Two candidates:

- **Constness.** The tables are no longer const definitions that LTO can treat
  as invariant. The hot renders that read them are compiled differently: Plaits
  `FMEngine::Render` and `WaveshapingEngine::Render`, Drums `RenderVoice`, and
  DX7 `MixVoice`. Register allocation and scheduling differ [verified:
  disassembly diff], and stores through `float*`/`int32_t*` may now alias the
  tables.
- **Layout.** About 10 KB of seeds and a larger `main` shift the XIP code that
  follows.

The single worst blocks do not isolate a stage.

**A possible follow-up.** This PR does not make it. Compile
`fm1_init_tables.cc` as a native, non-LTO object. The consumers could then
keep their `const` declarations, and LTO would never see a definition it could
fold.

## 5. Selection

**Decision: tables are their own switch, `--init-tables on|off`. They do not
join `--size-levers control`.**

- **What `control` is.** It changes compile options per unit. It does not
  change the source or the linker script. Its kit cost (+2.4%,
  size-levers note) was measured on its own.
- **What the tables are.** They change four declarations and the linker script,
  and they need a target hash check. Their kit cost (+1.5%, §4) is a different
  trade.
- **Why keep them apart.** As separate switches, earlier receipts and kit
  comparisons stay valid. A later change to either lever can then be measured
  alone.
- **The 1.0 build.** `--profile fm1-1.0` names it in one place and is the
  documented way to build it. It refuses a contradicting explicit switch (for
  example `--profile fm1-1.0 --usb-midi on`). The receipt records both the
  profile and the switches it set.

**Not combined on the kit.** Control and tables together were not timed. The
two costs come from different sessions and baselines: the size-levers main was
at 76.0%, this one at 74.2%. Adding them is not a measurement.

## 6. Tests

- `tests/test_init_tables.py`:
  - the generated file is current;
  - the generator refuses a perturbed `kSinTab12`, `kExp2Tab` and `lut_sine`;
  - a host build at `-O0`, `-O2` and `-Os` compares every entry of the four
    tables and their hashes;
  - the reference tables are the shipped ones.
- `tests/test_prepare_pipeline_devkit.py`:
  - `--init-tables` changes exactly 12 files;
  - it removes only the four definitions;
  - declarations go from const to non-const only;
  - the section, setup hook, flags and worker print are exact;
  - reapplying it is refused;
  - the object is linked only with the flag.
- `tests/test_prepare_fm1_app.py`:
  - the `--init-tables` switch;
  - `--profile fm1-1.0` equals the explicit switches (only the receipt
    differs);
  - profile conflicts are refused, and the CLI exits 2;
  - `init_tables=off` leaves the build id unchanged.
- `tests/test_devkit_pipeline_worst.py`: the parser reads the
  `LUNAR_INIT_TABLES` line and refuses a nonzero mask.

## 7. Not done or not verified

- Nothing was sent to the FM-1. The `fm1-1.0` image has not run on any device.
- The init path as the FM-1 image compiles it (without the check) has not
  run. It has the same source and flags as the kit's.
- Control and tables were not timed together on the kit (§5).
- The boot-time cost of the fill was not measured.
- The cause of the +1.5% is not pinned (§4).
