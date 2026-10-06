# 14 — The verification ladder: desktop, browser, dev board, FM-1

The owner's goal (2026-10-01): when the hardware on order arrives, show 1:1
behaviour between Lunar Modulator's emulators and a real JieLi board, and
between that board and the FM-1. On order: the **JL-AC79-DevKit V1.0**
(core board JL-AC79-WIFI V1.0 with an **AC7916**, docs/07 §3) and JieLi's
**USB updater dongle** (the "forced download tool", docs/07 §2.1).

This plan builds on docs/07, 10, 11 §8 (stage B) and 13 §7 and §9, on the
notes in `engines/`, and on the virtual FM-1 (`sim/web/`). Nothing in it has run on a JieLi
chip. The 2026-10-02 compile check (§5.2) verified what compiling alone can
show: code generation, sizes and symbols. Every claim about how pi32v2 code
behaves when run stays [inferred] until §5's probes replace it.

## 1. Short answer

| Question | Answer |
| --- | --- |
| What does "1:1" mean? | **Bit-exact wherever both sides do the same arithmetic.** That covers sequencer events, screen frames, LED states and MIDI bytes. It covers the DSP too, once float contraction and libm are pinned. A tolerance is allowed only where a named cause differs (compiler, libm, FPU edge cases, the analog path). It is never found by loosening a bound until a test passes. |
| Emulator ↔ dev board? | Expected to be bit-exact in a "ladder" build profile: `-ffp-contract=off` and one libm on every rung [inferred]. Today the browser module matches native `fm1-render` built against musl in 12 of 12 scenarios, and built against glibc in 10 of 12. The two Sophie scenarios differ because of libm [verified: sim/web/README.md, "Parity"]. |
| Dev board ↔ FM-1? | Same ISA, FPU, toolchain and object code, so the output before the DAC should be bit-exact. The differences are confined to the board: analog stage, crystal tolerance, flash and cache timing, keys, LEDs, TFT [inferred]. **This rung opens only after the FM-1 has been dumped and restored byte for byte** (CLAUDE.md, the one rule). |
| Stock firmware ↔ ours? | Never 1:1. Stock is msfa with its own effects, trims and UI. Before the gate it is a black box: the owner plays it by hand and we observe passively (§4.1). |
| How? | One golden corpus, one heap-free C runner built for every rung, per-block hashes, one diff tool, and a results record per rung like `www/fm1.wasm.json` (§3). |
| First week? | Inventory, toolchain, the kit's own dump and restore, blink and UART, FPU probes, the second-core probe, audio out, then rung 2 offline and the stage B numbers (§5). |

## 2. The ladder

### 2.1 Rungs

| Rung | What runs | Built by | Status |
| --- | --- | --- | --- |
| R0 desktop | `fm1-render`, `fm1-seq`, `fm1-sim-render`: 64-bit, `-m32`, ASan + UBSan | clang and GCC, CI | [verified] in CI |
| R1 browser | `fm1.wasm`: the virtual FM-1's app layer and every engine | Emscripten 6.0.10 on aeon | [verified] 12/12 against musl R0 |
| R2 dev board | the same C sources on the AC7916, in two modes: *offline* (a render loop) and *live* (driven by the DAC interrupt) | JieLi Clang/LLVM 4.0.1 with newlib 2.2.0's libc and libm [verified: §5.2] | stage B: compile-only done (§5.2); nothing run |
| R3 FM-1, ours | R2's portable code with the FM-1's board-support layer; RAM-only first, flash later | the same | gated by the one rule |
| Rs FM-1, installed | `FM-1_092` (Baud Girl's FM-1+VA) today; stock V15 if the owner rolls back | — | black box only |

### 2.2 Where the arithmetic can differ

| Source | R0 ↔ R1 | R0/R1 ↔ R2 | R2 ↔ R3 | Handling |
| --- | --- | --- | --- | --- |
| Integer code (seq, screen, LEDs, MIDI) | none [verified: screens match pixel for pixel, except the RAM figure, which shows 32-bit sizes] | none, provided `char` signedness, shifts and wrapping agree [inferred] | none | class E; keep `-fwrapv` on vendored code (engines/README.md) |
| Multiply-add contraction | none: Wasm has no fused op, and x86-64 GCC emits none without `-mfma` [inferred]. macOS arm64 clang contracts by default [inferred] | none: the pi32v2 code is byte-identical with `-ffp-contract=fast` and `=off` in all 622 code sections [verified: §5.2]. Whether the FPU has a fused op the backend never uses is unknown | none | `-ffp-contract=off` on every rung in the ladder profile |
| libm (`sinf`, `expf`, `exp2f`, `powf`, `logf`) | none, since both sides use musl; glibc differs on Sophie [verified] | JieLi's `libm.a` is newlib's fdlibm (`__ieee754_*`, `__kernel_*`), not musl; `sqrtf` is a library call, not an instruction [verified: §5.2] | none | compile musl's float functions (MIT) into the ladder profile on every rung, with `-fno-builtin` for them, because GCC folds constant calls using correctly rounded results [inferred] |
| Subnormals | IEEE on both | flush-to-zero behaviour unknown (mi-fx.md). Subnormals sit near 10⁻³⁸, far below a 16-bit LSB, so they change CPU time and float hashes, not int16 output [inferred] | none | compare int16 output, not float state; time the effect tails |
| Float divide by zero | gives inf | trap or inf unknown. Plaits' String model relies on inf (plaits-heavy.md, quirk 12) | none | probe first; before the board runs the corpus, list every divide by zero in it under UBSan's `float-divide-by-zero` |
| NaN or out-of-range float → int | target-specific | unknown | none | our code clamps (host contracts, engines/README.md); list the conversions in vendored code |
| `double` | hardware | software (compiler-rt `__muldf3` and so on), because the FPU is single precision [verified: SDK README; §5.2]. Basic ops round the same way; libm double functions do not [inferred]. The engines use `double` only at create, Test Sine excepted [verified: §5.2] | none | keep `double` out of the audio and runner paths |
| Struct layout | both have 4-byte pointers | none: pi32v2 aligns `double` and `uint64_t` to 4 inside structs, as i386 does, and every engine instance and sequencer record has i386's size [verified: §5.2] | none | compare a `sizeof` table; seq already lays out the same on 32 and 64 bits [verified: seq.md] |
| Clocks, DAC, analog | n/a | rate set by the kit's clock tree | crystal ppm, analog stage, amp | compare before the DAC; analog as class A |
| CPU cycles | desktop and browser figures do not transfer | measured | flash/XIP and cache can differ by part | reported; gated only against the budget |

### 2.3 Tolerance classes

| Class | Rule | Allowed when |
| --- | --- | --- |
| **E** exact | identical int16 output (SHA-256 per case, CRC32 per block); identical event logs, frames, LED logs and sizes | the default for every case |
| **R** rounding | ≤ 1 LSB at every sample and ≤ 0.1 LSB RMS (the reference tests' `HOST_LSB`) | there is a named cause: contraction, or a libm last-bit difference outside a feedback loop |
| **C** chaotic | level within 0.5 dB, onsets within one sample, spectra compared [inferred bounds] | feedback amplifies libm differences (Sophie) and libm is not pinned |
| **A** analog | after alignment by cross-correlation and a fitted rate: residual within 6 dB of the rung's own repeat-capture floor; response within ±0.5 dB from 20 Hz to 18 kHz [inferred bounds] | DAC captures |
| **T** timing | MIDI out lands within one USB frame (1 ms) plus one block (1.451 ms) of its event's frame [inferred bound]; jitter reported | live mode, and USB-MIDI clock in and out (docs/12 stage B) |

The bounds come from measurement. Two runs of the same rung set the floor.
Negative controls (deliberately broken builds) must fail, the way the
mutants do for the reference-render tests (engines/README.md). Each case in
the manifest carries its class, and every class other than E names its
cause.

### 2.4 What is compared

| Artefact | R0 / R1 | R2 | R3 | Class |
| --- | --- | --- | --- | --- |
| Audio, digital | int16 render buffers | the same buffers before the DAC, hashed per block and dumped on a mismatch | the same | E (R or C with a cause) |
| Audio, analog | — | the kit's output into an audio interface | the FM-1's stereo out jack | A |
| Sequencer events | `--log-events` JSON Lines: master tick, frame, kind, arguments [verified format] | the same lines from the runner | the same | E |
| MIDI in and out | timed input in the scripts | USB-MIDI and UART: bytes as E, timing as T | USB-MIDI out; the TRS jack is input only [reported] | E, T |
| CPU cycles per block | not transferable | cycle counter per block: min, mean, max | the same image | reported |
| Memory | `instance_bytes`, `fm1_seq_size`, `-m32` and Wasm sizes | a `sizeof` table, and the linker map against the FM-1 budget (387,924 B gap; the app area) | the same map | E, or explained |
| Screens | the 240 × 240 RGB565 frame buffer, 287 screens [verified] | the same buffer, hashed; the panel checked through an SPI decode | an SPI decode of the TFT stream; photos for layout only | E |
| LEDs | the simulator's LED state | logged state | the decoded 74HC595 stream | E |

## 3. Harness

### 3.1 One corpus

| Set | Size | Source | What it checks |
| --- | --- | --- | --- |
| Engine reference renders | the fm1 side of about 350 tests | `tests/test_engines_reference_*.py` | every engine and effect at native rates through the resampler. R2 compares with R0's fm1 output, not with upstream |
| Virtual FM-1 scenarios | 12 | `sim/web/test/scenarios.json` | effect chains, bends, parameter changes, more notes than voices, 44,100 Hz |
| Host contracts | per engine | `--fill 0/0xA5/0xFF`, NaN parameters, `--fault` | device memory is not zeroed either |
| Movy fixtures | 24, six of them with D1 traces | `tests/fixtures/movy/` | compat mode, D1 frames, the exported sets |
| Random sequencer scripts | 9,500 match Movy at R0 [verified: seq.md] | `gen_scripts.py --no-undo`, seeded | a seeded few hundred per R2 run, and all of them overnight |
| Screens | 287 | `fm1-sim-render --screens` | frame hashes |
| Worst cases | each engine at its voice cap; seq_bench's burst and edit scripts | `tools/seq_bench.py` | cycles |
| FPU probes | about 20 | new | the unknowns in §2.2 |

The golden results come from R0 in the ladder profile. They are committed
as a manifest: SHA-256 per case, CRC32 per block, the class, the toolchain,
the flags and a source hash (from sim/web's `tools/source_hash.py`). No
WAVs are committed; they are regenerated from the manifest.

### 3.2 One runner

A heap-free C99 runner (proposed: `ladder/runner/`) sits on top of the
virtual FM-1's app layer, which already matches `fm1-render` byte for byte
[verified: tests/test_sim_web.py].

- **Input.** A case in the existing `@<frame>` line format
  (`engines/host/seq_script.h`), extended with note, bend and parameter
  lines.
- **Output.** JSON Lines: a `hello` line (git SHA, toolchain, flags hash,
  library hash, clock, board, rate, block), then per-block hashes, events,
  cycles, sizes and a summary.
- **Builds.** The same source builds for R0, for R1 (under Node, as
  `parity.mjs` does) and for R2/R3.
- **Prerequisite.** `fm1_app_t` is 1,168,288 B of fixed arenas [verified:
  sim/web/README.md], about twice the chip's 578 KB. The runner needs one
  arena sized to the chain, plus strip rendering (ten 240 × 24 strips). That
  README already proposes both.

*Offline* mode renders as fast as the core allows and then waits for the
transport, so the results cannot depend on the transport. *Live* mode
drives the chain from the DAC interrupt, and its pre-DAC buffers must hash
the same as the offline ones.

### 3.3 Cases in, results out

| Stage | Transport | Use |
| --- | --- | --- |
| 1 | cases compiled into the image; results on the kit's debug UART | first week. Compact hex block hashes come to about 7.6 KB per second of audio, so at 115,200 baud the speed only sets the run time [inferred] |
| 2 | USB CDC ACM (or a vendor bulk interface) on the kit's USB device port | cases streamed in, full buffers sent out on a mismatch. Stereo int16 at 44,118 Hz is 176 KB/s, well within full speed [inferred: SDK class support unchecked] |
| 3 | TF card: the base board has a slot [verified: DevKitBoard V1.2 schematic in the SDK; check the bought revision] | the full random corpus and full dumps |
| R3 | USB only, since the FM-1 has no header or test pads (docs/01 §3): CDC, or SysEx over USB-MIDI as a fallback | the FM-1 rung |

`tools/ladder.py run --rung r2 --port …` runs a rung and writes to
`results/<rung>/`. `tools/ladder.py diff r0 r2` compares block hashes,
fetches the first differing block in full, and classifies the case by
§2.3. Its report names the first differing block, frame and sample.

### 3.4 CI

- R0 already runs in CI (Linux, macOS, `-m32`, ASan + UBSan). Add the
  ladder profile, and a job that reproduces the committed manifest on both
  operating systems.
- R1 stays on aeon (`build-on-aeon.sh`), and CI checks its record as it
  does today.
- R2 cannot use GitHub-hosted runners, because JieLi's toolchain is
  archived privately and not published (docs/07 §3).
  - Build it in a container on aeon from a private image in the LAN
    registry, with the kit plugged into aeon's USB.
  - `ladder/run-on-aeon.sh` builds, flashes the kit, runs the corpus and
    writes a record. CI checks that record against the source hash.
  - A self-hosted GitHub runner on a public repository would run fork PRs
    on aeon. If one is added, restrict it to `workflow_dispatch` and the
    owner's pushes.
  - Changes to aeon go through lan-compute's Ansible.
- R3 and the FM-1 never run in CI.

## 4. The FM-1 rung under the one rule

### 4.1 Before a dump and a byte-identical restore

Two things are allowed: the read-only identity query
(`tools/fm1_identify.py`, at the start and end of every session) and
passive captures. docs/12 §1 says it plainly: no writes, and no MIDI beyond
the identity query. The installed firmware is therefore a black box, played
by the owner's hands:

| Observation | How | What it settles |
| --- | --- | --- |
| Audio clock | a long held note on the line out, pitch-fitted against a reference | whether the DAC runs at 44,118 Hz [reported: AL-255] |
| USB audio | record the `FM-1 Audio` input (2 channels, 44,100 Hz [verified 2026-09-06]) while playing | whether it carries the synth at all, and how it bridges 44,118 Hz to 44,100 Hz (about 408 ppm) [unverified] |
| USB-MIDI out | listen on the FM-1's port while the keys and knobs are played | what the installed firmware sends, and when |
| Analog chain | line-out captures of simple sounds set up on the panel | level, noise floor and response of the FM-1's analog stage; this becomes R3's class A reference |
| Screen | photos or video | the layout reference for the virtual screen (look, not bits) |
| TFT and LED buses | a logic analyser on the FPC or on the 595s; passive, but the case must be open | the panel's command stream, for R3's SPI decode. The owner decides whether to open the case |

Not allowed before the gate:

- notes, CCs or SysEx sent from a computer;
- any update traffic;
- the vendor writer (`isd_download.exe`), which is never run against the
  FM-1 (docs/07 §2.1).

Channel messages are plausibly harmless. Widening the rule to allow them is
the owner's decision, recorded in CLAUDE.md, and this plan does not assume
it.

While FM-1+VA is installed, every capture describes FM-1+VA, and a dump
taken now would capture FM-1+VA rather than stock (docs/07 §4). Record the
identity with every capture.

**Comparing with stock audio is meaningful** in only two places:

- the output chain: level, noise, response and clock rate;
- once Lunar Modulator has an msfa engine (docs/08 Phase 4), DX7 voices
  compared statistically: pitch, envelope times, spectra.

Never sample by sample. Stock adds its FX slots and calibration trims, and
today's Six-Op FM is Plaits' DX7-style engine, which is different code from
msfa [inferred].

### 4.2 After the gate

The gate is docs/08 Phase 2 on the FM-1, run as its own deliberate session:
enter `UBOOT1.00` through the dongle, take two identical 1 MB dumps,
restore, and take a third identical dump (docs/10 §5–6). It is rehearsed
first on the kit (§5 step 3). After the gate, in order:

1. **RAM-only runs.** `jlrunner.py` loads the runner into RAM and jumps to
   it. Nothing is written to flash, and a power cycle brings back the
   installed firmware [reported mechanism: kagaimiq; untested on WL82]. How
   the results get out is still open (§6).
2. **Flash images.** They keep the head, `ota.bin`, `cfg` and the layout
   byte-identical to stock (docs/07 §4 rule 2; FM-1+VA's layout is not
   V15's, docs/01 §2). They carry the fail-open boot path and the watchdog
   counter (rule 4). Every update stage is power-cut on the kit first
   (rule 5).
3. **The full ladder on R3.** The same corpus, digital results over USB,
   and analog from the stereo out jack.

"Same object code" is checked, not assumed. The portable layers (engines,
seq, app) are built once as a static library and linked into both board
images. The `hello` line carries the library's hash, and R2 ↔ R3 compares
only runs whose hashes are equal.

### 4.3 What the board-support layer hides

| Function | FM-1 | Dev kit | Contract |
| --- | --- | --- | --- |
| Keys, buttons | 27 keys and 14 buttons in an 11 × 6 matrix behind two 74HC595s, read on PA0, PA5–PA8 and PB7 [reported: AL-255, Felucca, fm1-nes; photos verified] | a few buttons [inferred] | `bsp_keys()` returns a 41-bit state; on the kit, the runner supplies scripted events |
| Knobs | MASTER is a pot on PB6 (ADC 4); the seven encoders are scanned in the key matrix and decoded in software; ADC 3 is the battery [reported: Felucca, fm1-nes; docs/01 §3.1] | none, or one pot [inferred] | detent and position events; scripted on the kit |
| LEDs | lines PA9, PA10, PH6 and PH9, lit on the column the two 74HC595s select [reported: Felucca]; the 595s seen in photos [verified] | one or two LEDs [inferred] | an LED state array (the simulator's 41 bytes), logged on the kit |
| Display | 240 × 240 RGB565, ST7789V on SPI1 `0x11D00` (PC7–PC10, backlight PA2), ten strips [reported] | the LCD board; controller and size unknown | a strip flush of a 240 × 240 frame; the frame hash is compared, not the panel's pixels |
| Audio | ALNK0 (I2S) DMA ping-pong to an external codec, IRQ 11, 44,117.6 Hz, 64 frames per half; codec `U5`/`U9` unidentified [reported: Felucca, fm1-nes] | the AC7916's DAC to earphone jack J12 [verified: DevKitBoard V1.2 schematic]; the kit's ALNK has no codec on the board [inferred], so the kit rehearses only the DAC path | `bsp_audio_start(rate, 64, callback)`; the board reports its true rate and R0 renders at that rate |
| Clocks | 24 MHz crystal [verified], 240 MHz [reported] | crystal unknown | both set to 240 MHz for cycle counts, with 320 MHz as a second figure |
| Cores | two pi32v2 cores. Stock runs JieLi's OS on cpu0 and renders the msfa voices bare-metal on cpu1 [inferred; §5.1] | two pi32v2 cores [reported: docs/07 §3] | the board image declares which core runs audio; the runner logs `cnum` with every block's cycle count |
| Memory | 578 KB SRAM, no SDRAM [verified]; 1 MB flash [reported] | the AC7916 may carry SDRAM [reported] and more flash | the kit links with the FM-1's limits: no SDRAM, the FM-1's app area and SRAM gap |
| Results | USB-C only; the TRS jack is MIDI in | UART console and USB | one `bsp_report()` sink: UART, CDC or SysEx |
| Power | battery and slide switch; absent from USB until switched on [verified] | USB | — |
| Radios | BLE-MIDI | Wi-Fi and Bluetooth | outside the ladder |

## 5. First week

| # | Step | Exit criterion |
| --- | --- | --- |
| 1 | Unbox, and photograph both boards and the dongle: AC7916 marking, crystal, flash, USB-UART bridge, audio jack and amp, buttons, LEDs, LCD controller, TF slot, and the dongle's version and DIP switch. The SDK's schematics (core board `JL_AC79_WIFI V1.2`, DevKitBoard V1.2) already show an external 25Q64 flash, UPDATA (K1) and RESET (K2) keys, no USB-UART bridge (debug TX on PB03), earphone jack J12 on DACL/DACR and a TF slot [verified: SDK PDFs]; docs/07 lists the kit as V1.0, so check the bought revision | `notes/<date>-devkit.md` with a parts table; the "unknown" cells of §4.3 filled in |
| 2 | Toolchain: JieLi's Linux toolchain and post-build tools in a container on aeon, with the AC79 SDK (Apache-2.0) at a pinned commit (V1.2.13 `e30b1ee`, CLAUDE.md trap 11). Build the SDK's hello demo for the kit, and run `tools/jieli/audit_link.py` on the linked image | the toolchain archive's SHA-256 recorded; two clean builds byte-identical; the link audit passes (no live key/eFuse code) |
| 3 | The kit's own dump and restore. Rule 1 covers every device, and this also rehearses docs/10 §5 for the FM-1. Enter download mode with the kit's own UPDATA + RESET keys (hold UPDATA, press and release RESET [reported: JieLi doc 2.3]), then again through the vendor dongle in DIP bit 3 (continuous key, no power cut) with a power-up, as on the FM-1 (docs/07 §2.1); then run `jl-uboot-tool` read-only | JEDEC ID; two identical dumps, a restore, a third identical dump; VID:PID, inquiry string and every step recorded |
| 4 | Blink and UART. Steps 4 and 6 flash the kit with the Linux `isd_download` flow (SDK V1.2.12+, linux-postbuild `20260923.1`) in a container on aeon, its SHA-256 archived; it is a writer, for the kit only | the build id on the console; a toggled pin's period, measured on a logic analyser, within crystal tolerance at 240 MHz |
| 5 | A probe image covering: the cycle counter against a timer; `sizeof`/`alignof`; `char` signedness; float divide by zero; subnormal handling and cost; NaN and overflow in float → int; fused ops in `objdump` at `-O2`, with and without `-ffp-contract=off`; libm's float functions swept against musl | every [inferred] cell in §2.2 becomes [verified] or is corrected |
| 5b | The second-core probe (§5.1): how cpu1 starts; per-core counters; the FPU on each core; one core against two; cross-core ordering; the ways to keep audio on cpu1 (C6a–C6f); flash writes; power (optional) | `notes/<date>-devkit-cpu1.md` holds: a yes or no, with the method named, for "audio on cpu1 in an SDK build"; the dual-core factor for code in RAM and in flash; FPU results bit-identical across the cores; how long a flash write stalls cpu1 |
| 6 | Audio out: Test Sine through the DAC path, captured twice | the measured sample rate and noise floor; the two captures set class A's floor |
| 7 | R2 offline: the runner with the 12 scenarios, the Movy fixtures and the 287 screens compiled in | every case is E against R0, or each difference has a named cause; Sophie is E once libm is pinned |
| 8 | Stage B: cycles per block for each engine at its voice cap, each effect, the resampler and seq_bench's worst cases; the linker map against the budget; `-fPIC` and its relocations | docs/11 §8's exit (a cycle table, and a yes or no on Tier 2) and docs/13's stage B exit (the sequencer takes ≤ 2 % of any block); the resampler and Shapes decisions in engines/README.md taken |
| 9 | R2 live: the same chains driven from the DAC interrupt | pre-DAC hashes equal the offline ones for ten minutes, with no underrun and the worst block within budget |

Steps 8 and 9 may run into week two. Step 5b takes 4–5 days and may spill
into week two as well. Steps 8 and 9 report each figure for one core and,
if 5b says yes, also with audio on cpu1. The FM-1 receives nothing but the
identity query all week.

### 5.1 Step 5b: the second-core probe

**What is known.**
- **Stock already uses both cores** (docs/11 §2 has the evidence):
  - cpu0 runs JieLi's OS, the UI, MIDI, USB and BLE, and an audio task that
    runs the six FX slots and feeds the output [reported: AL-255; the core
    inferred]. The output is ALNK0 (I2S) to an external codec, not the DAC
    [reported: Felucca, fm1-nes].
  - cpu1 runs a routine outside the OS. It busy-polls a state byte at
    `0x01C16EC0` and calls the msfa block render, which has no other caller
    (V13 file `0x86AD6`) [verified: V13 disassembly]. That it runs on cpu1
    is [reported: AL-255's symbol names; inferred from the
    `cpu1_run_flag`].
  - `irq_info_table` is the SDK's `CPU_CORE_NUM 1` table: {SOFT5, prio 7,
    cpu0}, {SOFT4, prio 7, cpu1}, then the sentinels [verified: V13 file
    `0x4DD48`; V15 and FM-1_092 file `0x4D4A0`, identical].
  - The build stamp reads "modified #define CPU_CORE_NUM 1" [verified].
  - `app.bin` runs from `0x02000120`, not `0x02000000` [verified: our V15
    `jlfw.yaml` entry point; docs/01 §2], which is why earlier readings put
    nothing on cpu1.
- **What the public SDK offers.** JieLi documents this mode [reported: AC79
  doc 7.40; the SDK's `init.c` verified]. It needs `CPU_CORE_NUM 1` and a
  single-core `system.a`, which the doc says to request from JieLi. Its
  rules:
  - `cpu1_main` may not call the OS or `printf`;
  - the two cores synchronise with `spin_lock`;
  - a flash write suspends cpu1, unless `cpu1_run_flag = 0` and everything
    cpu1 runs is in RAM.
- **What the public SDK offers for task placement.** `os_task_create`
  takes no core argument [verified: `os_api.h`], and no affinity symbol is
  in either public `system.a` [verified: 2026-10-01 study]. The AC792N SDK
  has `os_task_create_affinity_core`; the AC79 SDK does not [verified: both
  `os_api.h`]. **But a task-name prefix does the job for core 0**: the SDK's
  demos name `btctrler`, `btstack`, `btencry` and `usb_msd0` with a `#C0`
  prefix at V1.1.9 and at `e30b1ee`, JieLi's doc 2.18 gates it on
  `CPU_CORE_NUM > 1`, `StaticTask_t` ends in `int cpu_id`, and the DWARF in
  `system.a` shows the TCB members `cpu_id` and `cpuSuspend` [verified:
  SDK sources and strings, 2026-10-05]. fm1-nes uses `#C0` on an FM-1
  [reported]. Whether `#C1` pins a task to cpu1 is untested [inferred: the
  parser is inside the closed `system.a`]; C6d tests it.
- **Interrupts that run through critical sections.** With
  `CONFIG_IPMASK_ENABLE`, `__local_irq_disable` raises the core's IPMASK to 7
  instead of masking everything, so a priority-7 interrupt pinned to cpu1
  keeps running through OS critical sections and flash writes, if its code
  and data are in RAM and it takes no lock [verified:
  `apps/common/system/init.c`; doc 7.41]. In the default SMP build,
  `local_irq_disable()` also takes one global `bt_lock` spinlock shared by
  both cores, so a long critical section on cpu0 stalls cpu1 [verified:
  source].
- **Interrupts can be pinned:** `irq_info_table` and `request_irq` take a
  cpu argument [verified: `hwi.h`].
- **Speed.** JieLi's own CoreMark at 320 MHz, two threads, `-Oz`, gives
  about 2.3–2.4 per MHz for both cores together [verified: JieLi's
  BenchMark page screenshots]. Per core that may be about a third of a
  Cortex-M4F per clock on integer code [inferred], which would undercut
  docs/11 §2's per-cycle-parity assumption.
- **The FPU.** Both cores probably have one: the SDK README calls the chip a
  dual-core floating-point DSP [reported], and stock's cpu1 path uses inline
  float instructions with no soft-float calls [inferred].

**What to build.** One probe image from the pinned SDK, in variants:
- the public SMP `system.a`, with its `SYSTEM-$` stamp and SHA-256 recorded;
- `cpu1_main` patched (it lives in the open `apps/common/system/init.c`);
- the step-5 FPU probes;
- Macro (12 voices), Six-Op FM (8), Macro Heavy's Particle (4) and Plate, as
  render kernels;
- a UI-like load: SPI DMA strips plus flash-resident code.

| Case | Do | Measure and record |
| --- | --- | --- |
| C1 boot | Boot the SMP default and log from cpu0. Compare with stock's start sequence: mailbox `0x01C7FFF8`, `0x10008` bit 3, corex2 `C1_CON` bit 3 set and bit 1 cleared | `cnum` per task; `cpu1_run_flag`; the mailbox word; `C0_CON` and `C1_CON` before and after; cpu1's PC (`q32DSP(1)->PCRS`) |
| C2 counters | On each core, read `TTMR_CNT` and corex2 `Cn_TL_CKCNT` across 1 s, timed by a GPIO toggle on a logic analyser, at 240 and 320 MHz | whether both count sysclk; these become stage B's cycle counters |
| C3 FPU per core | Run the step-5 probes once with `cnum` 0 and once with 1 (inside an IRQ pinned to each core), then time a 1,024-op float kernel on each core | results bit-identical across the cores; time per op |
| C4 scaling | Render each kernel for 10,000 blocks on cpu0 alone, on cpu1 alone, and on both at once; first with code in flash, then with hot code in RAM (`.volatile_ram_code`); then again with the UI-like load on cpu0 | cycles per block (min, mean, max); stall % from `Cn_IF/RD/WR_UACNT`; the slowdown on cpu1 caused by cpu0's load |
| C5 litmus | Pass data and then a flag 10⁸ times, with and without `csync`. Have both cores increment a counter under `spin_lock` 10⁷ times each. Run an SPSC ring at 64 frames and 44,118 Hz for 10 minutes with a CRC per block | ordering failures (expect none with `csync`); the counter exactly 2×10⁷; no bad CRC |
| C6a pin by interrupt | Register the audio interrupt on cpu1 (the kit's DAC; on the FM-1 it is ALNK0, IRQ 11) and render inside the ISR | worst block, jitter, and the throughput lost by tasks the scheduler puts on cpu1 |
| C6b pin by priority | Render in a top-priority task woken by the audio interrupt, with BLE and USB active | `cnum` per block as a migration histogram; the worst block |
| C6c bare metal under the SMP library | Patch `cpu1_main` to skip `os_start` and run the render loop; soak cpu0's OS for 1 h (task create and delete, `os_time_dly`, USB, BLE advertising) | any hang or watchdog reset |
| C6d pin by name | Create the render task as `#C1audio` on the public SMP library, with BLE and USB active | `cnum` per block (always 1, or a migration histogram); the worst block |
| C6e IPMASK interrupt | With `CONFIG_IPMASK_ENABLE`, render in a priority-7 interrupt pinned to cpu1, its code and data in RAM, and run C7's flash writes on cpu0 | underruns and the worst block through the writes; the RAM it costs |
| C6f the shared lock | Measure how long cpu1 waits on `bt_lock` while cpu0 does BT, USB and flash work | the longest and the 99th-percentile stall per block |
| C7 flash writes | After step 3's dump and restore, erase and program 4 KB on a scratch sector of the kit while cpu1 renders. Repeat with `cpu1_run_flag = 0` and all of cpu1's code and constant data in RAM | how long cpu1 is suspended; underruns; the RAM the second variant costs |
| C8 power (optional) | Measure supply current with cpu1 busy-polling as stock does, then with cpu1 in `idle`, woken by `IRQ_SOFT4` each block | current in each case |

**Record** everything in `notes/<date>-devkit-cpu1.md`, with the toolchain
archive's hash, the SDK commit and the `system.a` hash.

**Exit:**
- a yes or no, with the method named (C6a–C6e, or "needs JieLi's
  single-core library"), for "audio on cpu1 in an SDK build, with the worst
  block within budget";
- the dual-core factor for code in RAM and in flash;
- FPU parity across the cores;
- cpu1's suspension time during a flash write.

**The decisions it informs:**
1. **How Lunar splits the work.** Four candidates:
   - A, stock-like: engine, effects, resampler, limiter and
     `fm1_seq_advance` on cpu1, and everything else on cpu0, joined by
     docs/13 §6's command ring;
   - B, stock's own pipeline: voices on cpu1 and effects on cpu0, at one
     block more latency;
   - C: one engine's voices split across both cores;
   - D: one engine per core.

   A is the first candidate [inferred].
2. **The budget.** docs/11 §2 gains a two-core column, and engines/README.md
   gets voice caps for both budgets. CPU-bound engines (Six-Op FM, Macro's
   2-op FM, Particle) gain; memory-bound ones (Shapes, PSX Verb) do not,
   because the second core brings no SRAM [inferred].
3. **The library.** Whether to ask JieLi for the single-core `system.a`, and
   on what licence terms.
4. **RAM-resident code.** How much audio code must sit in RAM to keep
   playing through flash writes, against the SRAM gap.

None of C1–C8 runs on the FM-1. All week, the FM-1 receives only the
identity query.

### 5.2 Stage B, compile-only (done 2026-10-02)

The pi32v2 half of I2's compile step was done ahead of the kit, in a
container on the build host (`tools/jieli/compile-check.sh`;
[`notes/2026-10-02-jieli-compile-check.md`](../notes/2026-10-02-jieli-compile-check.md)).

**What was built.** JieLi's Linux toolchain (Clang 4.0.1) at a pinned
SHA-256, with the AC79 SDK V1.1.9's flags and libc++ headers. It compiled
everything a firmware would link: the engines, the vendored Mutable and
Schwung code, the sequencer core and the app layer. That is 63 objects, each
in the ladder profile, with `-ffp-contract=fast`, at the SDK's `-Oz` and
with `-fPIC`. Nothing was linked or run.

The SDK pin has since moved to **V1.2.13** (`e30b1ee`; owner's decision,
2026-10-05, CLAUDE.md trap 11) and the check was re-run against its
libraries, flags and libc++ — whose own `math.h` removes the one fix the
V1.1.9 run needed — and extended with the key/eFuse link audit
(`tools/jieli/audit_link.py`). See the dated addendum in
[`notes/2026-10-02-jieli-compile-check.md`](../notes/2026-10-02-jieli-compile-check.md).

**What it showed** [verified]:

| Question | Answer |
| --- | --- |
| Does the code compile? | Yes, 63 of 63 in every profile, with no C++11 or dialect problem. The one fix: the SDK's libc++ has no `math.h` wrapper, so `<cmath>` fails (42 objects) until libc++ 7.0.0's `math.h` is added to the include path |
| Do the external symbols resolve? | Yes, all of them, in what the SDK's `demo_hello` links. No C++ runtime is needed beyond one `std::sort` |
| Code and tables | 386 KB at `-O2`, 343 KB at `-Oz`, before `--gc-sections` and before the SDK's own base |
| Fused multiply-add | None. The ladder profile's `-ffp-contract=off` changes nothing on pi32v2 |
| Instance sizes at 32 bits | Equal to i386's for every engine; `-m32` desktop builds give device sizes |
| Largest stack frame | 2,224 B, the app's `draw`. Audio-path frames are under 500 B |
| `-fPIC` | Compiles, with GOT and function-descriptor relocations. Linking it is untested |

**Still open** for steps 2, 5 and 8: linking and the SDK base's size, cycles,
newlib's libm against musl, and the SDK's link-time `-inline-threshold=5`,
which would reach our engines in an LTO build.

## 6. Risks and open questions

| Item | Why it matters | How it is settled |
| --- | --- | --- |
| JieLi's Clang 4.0.1 (2017) | an old front end: C99 and C++11 should build, newer builtins may not [inferred] | settled for compiling (§5.2): all 63 objects build once libc++'s `math.h` is supplied, which the SDK's libc++ copy lacks; linking is step 2 |
| pi32v2 traps on float divide by zero | Plaits' String model would fault | step 5; add a guard in our wrapper |
| Subnormal cost | effect tails decay into subnormals (mi-fx.md) | step 5 timings; flush in the wrapper if slow |
| JieLi's libm differs from musl | affects Sophie, and Capture's tempo search near a tie | pin musl's float functions in the ladder profile; keep JieLi's only if stage B shows it is worth accepting class C |
| The dongle or `jl-uboot-tool` on AC79 | the dongle listings name only Bluetooth families, and jl-uboot-tool lists WL82 as "unknown" | step 3, read-only first; the RP2040 dongle (docs/10) as the fallback |
| The AC7916 is not the FM-1's AC791N variant | caches, flash interface, SDRAM and DAC wiring may differ | compare cycles only for SRAM-resident code; R3 settles the rest |
| The kit's audio path | the base board has earphone jack J12 on DACL/DACR [verified: DevKitBoard V1.2 schematic], but the FM-1 sends audio over I2S to a codec instead [reported], so the kit's live rung differs from the FM-1's in interrupt source and path | step 1 checks the bought revision; `bsp_audio_start` hides the difference; R3 settles the FM-1's |
| USB CDC in the AC79 SDK | needed for transport stage 2 | settled: the SDK has a CDC class (`cdc.c`) [verified: 2026-10-01 MIDI study]; SysEx stays the fallback |
| `os_task_create` has no core argument; only the `#C<n>` name prefix places tasks, and `#C1` is untested | audio may not be pinnable to cpu1 through the OS | C6d first, then C6a–C6c and C6e; otherwise JieLi's single-core `system.a` |
| The single-core `system.a` is supplied by JieLi on request only [reported: doc 7.40] | stock's arrangement may be unreachable with public libraries | the owner decides whether to ask, after C6 |
| Flash writes suspend cpu1 | audio drops out during preset saves | C7; RAM-resident audio code with `cpu1_run_flag = 0` |
| Both cores fetch from one flash and cache controller | cpu0's UI and BLE code may stall cpu1's audio | C4 under the UI-like load |
| stmlib's random generator is a global in vendored code | splitting one engine's voices across the cores races, and ladder results stop being bit-exact | confine such engines to one core (splits A, B and D), or give the generator per-core state behind a build flag |
| The runner's SRAM | the simulator's `fm1_app_t` is 1.17 MB | one sized arena and strip rendering, before step 7 |
| Results from RAM-only runs on the FM-1 | after the jump, can the ROM loader still read RAM? | a RAM mailbox read back, a USB stack in the RAM image, or hashes drawn on the TFT |
| Passive bus taps on the FM-1 | the case must be open | the owner decides |
| Channel messages to the FM-1 before the gate | would allow scripted black-box tests | the owner decides, recorded in CLAUDE.md |
| A self-hosted runner on a public repository | fork PRs would run on aeon | dispatch-only, or no runner |