# monome, O_C T4.1 and jhjlim as sources for the FM-1 (2026-10-01)

**Scope.** The owner asked for a look at three sources: github.com/monome (the Google redirect in the request resolves there), [PaulStoffregen/O_C_T41](https://github.com/PaulStoffregen/O_C_T41), and everything under [github.com/jhjlim](https://github.com/jhjlim).

- **How it was read.** Through the GitHub API only. Nothing was cloned, built or run.
- **monome.** One lane read all 74 repositories. The pinned heads include teletype `e390bacdf0`, ansible `9796656cbb`, libavr32 `5eca040f88`, aleph `d7ffa3e766` (branch `dev`) and dsp-kit `24ec4b0996`.
- **O_C_T41.** One lane read it at `d6235f0b`. It holds hardware only, so the lane followed it to the firmware it runs: [djphazer/O_C-Phazerville](https://github.com/djphazer/O_C-Phazerville) at `195932ab6f`.
- **jhjlim.** One lane read all 9 repositories. It followed AsmallerClouds to Mutable's Clouds at our pinned `pichenettes/eurorack@08460a69`.
- **What this note is.** The verifier's synthesis. I re-read the licence of every candidate recommended as code, and the main resource claim of each top pick, from the files themselves. CPU figures are **not measured on pi32v2** [inferred].

**Who to credit** [verified in file headers, unless marked]:
- **Emilie Gillet**: Clouds, Peaks, Frames, Streams, the Braids quantiser and Grids.
- **Bryan Head**: the codebook-free quantiser ("Re-implemented by Bryan Head to eliminate codebook").
- **Patrick Dowling**: the Tonnetz core, the Turing register and the grid utility.
- **Tim Churches**: the logistic map, the integer sequences and the Lorenz port.
- **Max Stadler (mxmxmx)**: Ornament & Crime.
- **Logarhythm**: TB-3PO.
- **Benjamin Rosenbach**: DrumMap.
- **Naomi Seyfer**: Passencore.
- **Jason Justian (Chysn)**: the Hemisphere framework.
- **Nicholas J. Michalek**: Animorf; maintains Phazerville with djphazer.
- **Ezra Buchla**: dsp-kit.
- **monome** for teletype, ansible and libavr32. Individual credits there are [reported] from READMEs: @ngwese, @scanner-darkly, @csboling.
- **Paul Stoffregen and Beau Seidon**: the T4.1 hardware [reported].
- **Jason H. J. Lim** (profile: Instruō, Glasgow).

## Verdict

**About eight small permissive cores are worth taking as code, and about a dozen sequencer and MIDI-effect designs are worth reimplementing. jhjlim's own repos have nothing to take.**

- **O&C/Phazerville is the best code source.** Its algorithm cores are MIT, integer, heap-free and a few hundred bytes each:
  - the quantiser and its 145 scales;
  - the Tonnetz triad transforms;
  - the Turing and logistic generators;
  - the Peaks, Frames and Streams modulation cores;
  - TB-3PO.

  They fill the empty `FM1_KIND_MIDI_FX` slot and a modulation layer that `fm1_engine.h` does not have yet.
- **monome is almost all GPL.** It is worth taking as designs only: Kria's per-lane loops, Ansible's arpeggiator, Meadowphysics, Earthsea's gesture recorder, and Teletype's heap-free scripting model.
- **The jhjlim lane's real find is Clouds.** Its `PitchShifter` (8 KB, MIT) fills a gap in engines/, and a reduced granular processor fits in about 88 KB.

## Worth bringing in, ranked

Sizes are for 32-bit builds. The gap is the 387,924 B stock SRAM gap (engines/README.md).

**As code.** All are MIT unless marked. "Shareable" means the code may sit in a binary that links JieLi's libraries.

| # | Candidate (source) | FM-1 kind | Resources | Effort | Build-switch consequence |
| --- | --- | --- | --- | --- | --- |
| 1 | **Pitch shifter**: Clouds `dsp/fx/pitch_shifter.h` + `fx_engine.h` + `frame.h` (eurorack `08460a69`) | audio FX | 8,192 B delay (`FxEngine<4096, FORMAT_16_BIT>`) [verified]; about 40–60 cycles per stereo sample plus 1 float divide [inferred] | ½ day | none: shareable; extend our existing Mutable vendoring |
| 2 | **Quantiser** + 145-scale table (Phazerville `src/extern/braids_quantizer*`) | MIDI-FX service | about 64 B per instance; 145 × 40 B = 5,800 B flash [verified count, inferred layout]; at most 16 compares on a cell change | ½–1 day | none: shareable |
| 3 | **Tonnetz** P/L/R/N/S/H core + `util_grid.h` | MIDI FX | about 40 B of state; event-rate | ½ day | none: shareable |
| 4 | **Generators**: `util_turing.h`, `util_logistic_map.h`, `util_integer_sequences.h` | MIDI FX / sequencer source | under 100 B each; the logistic map does int64 multiplies at clock rate | ½ day + fixes (below) | none: shareable, with a local diff recorded |
| 5 | **Reduced Clouds**: our own ~300-line processor over unmodified `clouds/dsp` (granular + looping delay; no reverb, phase vocoder or WSOLA) | audio FX | about 88 KB (64,000 B samples + 8,192 diffuser + 8,192 shifter + state + 2 resamplers) [inferred from verified parts]; about 23 KB of tables; about 7 % CPU at 16 grains [inferred, unmeasured] | 3–5 days | none: shareable |
| 6 | **Modulation cores**: Peaks multistage envelope (12 shapes in O&C's version, 3 upstream), Frames poly LFO, Streams Lorenz/Rössler | modulation source | about 100–150 B each; flash ≈ 6.7 KB, 5.3 KB, 1 KB; tables are for 16,666 Hz and must be regenerated | 1 day each, after a modulation API | none: shareable |
| 7 | **TB-3PO** acid generator (`applets/TB3PO.h`): lift `regenerate_*`, swap the PRNG | MIDI FX / sequencer track | about 250 B; event-rate | 1–2 days | none: shareable. Seeds will not reproduce O&C's patterns |
| 8 | **Animorf** MuRF filter bank (`Audio/animorf_core.h`) | audio FX | under 1 KB; 8 SVFs per channel per sample [inferred] | 1–2 days | shareable on the README's MIT statement alone. Ask for a header, or rewrite it on `stmlib::Svf` |
| 9 | **DrumMap**: the applet is MIT (Rosenbach), but the map data `grids_resources.h` is **GPL-3.0-or-later** (Gillet) | drum MIDI FX | about 2–3 KB flash | 1 day | **personal builds only**, in `third_party/grids/` behind a switch. Or draw our own map |

**As design.** Reimplement these in our own code; no licence follows them.

| Candidate | Source / licence | Kind | Size | Why |
| --- | --- | --- | --- | --- |
| **Kria lanes** | ansible `ansible_grid.[ch]`, GPL-2.0 | sequencer mode | `kria_data_t` ≈ 19,152 B [inferred: verified struct, 4-byte enum] | 7 lanes per track, each with its own loop, clock multiplier, 4-level probability, direction and ratchet bits. The most distinctive sequencer idea here |
| **Arpeggiator** | libavr32 `arp.c`, GPL-2.0, plus CHOMPI TEMPO (MIT) | first MIDI FX | under 1 KB | 8 styles and 4 players with euclidean gating and transpose, which CHOMPI's arpeggiator lacks |
| **Chord memory and progressions** | Acid Curds `Chords.h` + `OC_chords*`, MIT (tables may come as code) | MIDI FX | about 260 B | Chord qualities are counted in scale steps, so chords stay in key |
| **H1200, Automatonnetz, Passencore** | Phazerville, MIT | MIDI FX on the Tonnetz core | under 0.5 KB | Voice-led triad moves; Passencore is commented out upstream, so treat its correctness as unproven |
| **Meadowphysics** | ansible, GPL-2.0 | MIDI FX / sequencer mode | `mp_data_t` = 105 B [verified struct] | 8 cascading counters mapped to 8 white keys |
| **Earthsea recorder** | ansible, GPL-2.0 | performance looper | about 8.7 KB | Record a gesture, "linearize" it, replay it transposed from any key |
| **Scale slots, random pattern chains, Euclid with padding** | Meta-Q (MIT), White Whale (GPL-2.0), EuclidX (MIT) | Movy additions | tiny | Song-mode and track ideas |
| **Teletype interpreter model** | teletype, GPL-2.0 | scripting | about 24–29 KB fixed, no heap [inferred] | The model for a heap-free script tier, if Berry or Lua (docs/11 §5) proves too big |
| **ASL / `casl.c`, Cycles** | crow (GPL-3.0), ansible (GPL-2.0) | modulation | about 1.2 KB per channel | Compact slope-language runtime; knob-thrown LFOs with inertia |
| **Hemisphere / Quadrants** | Phazerville, MIT | UI | – | A "four tools" TFT page, one per knob, with stable registry IDs for presets |

## Licence findings (re-verified)

1. **Phazerville has no LICENSE file**, and the API reports none.
   - The README (line 104) says the code is "generally considered MIT licensed", except where file headers say otherwise. It adds that GPLv3 parts make "the whole thing also subject to compliance with the GPL".
   - Every file recommended above carries a full MIT permission header, with the authors listed under "Who to credit".
   - **GPLv3 only:** `software/src/grids_resources.h` and `grids2_resources.h` ("version 3 of the License, or (at your option) any later version").
   - **No header:** `tideslite.h/.cpp`, `Audio/animorf_core.h` and `OC_scales.h`. The README covers them [reported].
2. **Mutable's split** [verified: eurorack README 33–35]. "Code (AVR projects): GPL3.0. Code (STM32F projects): MIT license."
   - Grids is AVR, so GPL. Clouds, Peaks, Frames and Streams are MIT, with a header in every file read.
   - All four are in our pinned commit, so `vendor.py` can take them under the existing UPSTREAM.md.
3. **monome.**
   - teletype, ansible and libavr32 are GPL-2.0 [verified: API, LICENSE].
   - dsp-kit is MIT, "Copyright 2019-2020 Ezra Buchla" [verified]. Its `easing.hpp` is credited to "The Min-Lib Authors" under MIT and implements Penner's equations.
   - aleph's `dsp/` is Unlicense [verified: root LICENSE.TXT list, `dsp/UNLICENSE.TXT`]. Its headers come from `bfin_lib/` (Unlicense), `libfixmath` (MIT) and `common/types.h`, which the root list does not cover.
4. **O_C_T41** has no LICENSE file. Its readme (lines 50–51) states CC BY-SA 4.0 for the hardware [verified].
5. **jhjlim.** All 9 repos have no licence, according to the API [verified].

## Corrections to the lane reports

- **aleph's pitch shifter is unfinished and does not compile.** Its verdict drops from "code" to "design", and Clouds' `PitchShifter` covers the gap.
  - `dsp/pitch_shift.c` reads `dl->pitchDetector` and `dl->scrubCentrePitch`, which exist only in `grain` (`grain.h` 25, 33), not in `pitchShift`.
  - It carries 3 FIXMEs.
  - `modules/grains/Makefile` builds `grain.c` only [verified].
- **dsp-kit's `easing.hpp` is not heap-free as written.** It has a `static const std::string` table (line 503) and a `std::function` getter (line 604) [verified]. Copy the formulas with credit; do not vendor the header.
- **`util_turing.h` has undefined behaviour at its maximum length.**
  - `Clock()` returns `shift_register & ~(0xffffffff << length_)`, and `kMaxLength` is 32 [verified]. A shift by 32 is undefined.
  - It happens to yield the full mask on ARM, but 0 on x86, and on pi32v2 it is unknown [inferred]. Our UBSan job would halt.
  - It also calls Arduino's `random(n)`, as do the integer sequences and TB-3PO.
  - This is an upstream candidate.
- **Clouds `PitchShifter::Init` leaves `ratio_` uninitialised** [verified]. The wrapper must call `set_ratio` before the first `Process`, or the any-fill test fails.
- **Clouds figures confirmed** [verified]:
  - buffers `block_mem[118784]` and `block_ccm[65536 - 128]` (`clouds.cc` 51–52);
  - the shifter's 8,192 B overlaid on a 1,560 B correlator allocation (`granular_processor.cc` 416–422; `kMaxWSOLASize` 4096). This is benign upstream; a port that tightens the workspace would overrun it.
  - **docs/11 §4 is wrong** to say "Spectral mode needs its own FFT". `stft.h` 34–40 comments out `USE_ARM_FFT`, so stmlib's ShyFFT is the default.
- **Peaks: take O&C's version.** Upstream Peaks' envelope has 3 shapes (`ENV_SHAPE_LINEAR/EXPONENTIAL/QUARTIC`) against O&C's 12 [verified].
- **Animorf** is a single commit (`37594b28`, 2026-07-07), commented out of both registries (`audio_applets/_config.h` 79, 108). Its 16 patterns are generic band masks, not transcribed Moog presets [verified: lines 196–215].

## Memory against the FM-1

Sizes are 32-bit. Movy's grid is about 72 KiB (docs/13 §1). Clouds-lite is item 5 above.

| Chain | Bytes | Left of 387,924 |
| --- | --- | --- |
| Macro + Plate + Movy grid + Clouds-lite | about 245,000 | about 143,000 |
| … + pitch shifter + CHOMPI echo (0.37 s) | about 318,700 | about 69,200 |
| Shapes + Plate + Clouds-lite | about 358,500 | about 29,400 |
| Shapes + Plate + Clouds-lite + Movy grid | about 432,000 | does not fit |

The MIDI FX and modulation cores together come to under 2 KB of RAM. Their flash cost is about 25 KB of tables.

## What to skip, and why

- **O_C_T41 itself.** It is KiCad, gerbers and Teensy test sketches, with no firmware.
- **Phazerville as a platform.** It is built around the Teensy ISR, DAC, OLED, EEPROM and Arduino.
- **The CV logic and utility applets.** The FM-1 has no CV.
- **The Abyss reverb.** It needs more than 400 KB.
- **The Teensy Audio Library applets, and the Mistier, modal and Karplus applets.** Better Mutable originals exist.
- **Captain MIDI.** CV again; only its 7-in-8 SysEx packing is worth noting, for after the one rule allows writes.
- **monome's softcut.** GPL-3, with double-precision phase; the FM-1's FPU is single-precision. Use it as a design reference for a later looper.
- **monome's norns engines, crone and matron.** They need Linux, JACK and SuperCollider.
- **libmonome, serialosc and ii.** The FM-1 has no USB host and no i2c.
- **iii.** No source is published. It is the API model only.
- **The aleph voices.** They duplicate Plaits.
- **BEES.** CC-BY-SA, and bound to its UI.
- **All of jhjlim's repos.** They are unlicensed hobby projects from 2013–2018, and AsmallerClouds is hardware only. Keep `quad`'s free-running knob-motion recorder as an idea.
- **InstruoModular/pitch_shift.** Unlicensed, it needs a private library, and it is far over budget.

## How the top picks fit the roadmap

- **engines/.**
  - The pitch shifter and Clouds-lite are `FM1_KIND_AUDIO_FX`. They queue after the CHOMPI echo, DJ filter and Warble.
  - Clouds-lite runs at its native 32 kHz through `fm1_resampler.h`, consistent with the 2026-10-01 native-rate decision. The dry/wet mix stays at the host rate.
  - It needs the SRAM-ownership decision from the CHOMPI note, step 3.
- **`FM1_KIND_MIDI_FX`.**
  - The quantiser becomes a shared service.
  - Then, in order: the arpeggiator (CHOMPI TEMPO's behaviour plus Ansible's euclidean players), chord memory (Acid Curds tables), Tonnetz P/L/R, and a generator (TB-3PO, Turing, logistic).
  - All of them wait on the contract (docs/11 §3.1: `process_midi` + `tick`, at most 16 output messages) and on tempo and transport in `fm1_host_t`.
- **Modulation.**
  - `fm1_engine.h` has no modulation kind [verified: lines 41–47].
  - Proposal: a host-side matrix that writes `set_param` at block rate (689 Hz), fed by the Peaks, Frames and Lorenz cores and ASL-style slopes.
  - That avoids a fourth plugin kind. Lorenz needs sub-steps at that rate [inferred].
- **The Movy port (docs/13).**
  - M1 stays a tick-identical port; none of this touches its compat tests.
  - Later milestones can add a Kria "lanes" mode, Meta-Q scale slots, White Whale chains and Euclid fill, plus Meadowphysics and Earthsea as alternative modes on the white keys.
- **Scripting (docs/11 §5).** Berry or Lua stays the plan. Teletype's fixed-memory interpreter is the fallback model. Write scenes on a computer and send them as SysEx, since the FM-1 cannot host a keyboard.

## Next steps

1. **Pitch shifter, first.**
   - Add `clouds/dsp/fx/pitch_shifter.h`, `fx_engine.h` and `frame.h` to `vendor.py` ROOTS, kept unmodified.
   - Wrap them as our own effect (for example `pitch`), calling `set_ratio` in `create`.
   - Tests:
     - a sine shifted ±12 semitones lands within ±5 cents;
     - at ratio 1 the output stays correlated with its input;
     - any-fill byte identity, NaN parameters, and non-finite input under ASan and UBSan;
     - record the 32-bit size.
2. **Create `engines/third_party/oc/`** with an UPSTREAM.md.
   - Record `djphazer/O_C-Phazerville@195932ab6f`, the README licence quote and per-file authors.
   - Bring in the quantiser and scales, Tonnetz and `util_grid.h` unmodified, with shim headers for `OC_options.h` and `util_macros.h`.
   - Bring in the three generators with a recorded local diff: a seeded PRNG in place of `random()`, and a 64-bit mask in the Turing register.
   - Add golden-output tests.
3. **Settle the MIDI_FX contract and tempo**, as in the CHOMPI note step 3. Then write the arpeggiator as our own code, with golden event-stream tests and a seeded RNG.
4. **Build Clouds-lite** after the CHOMPI echo and the SRAM decision. Test it against upstream `GranularProcessor` driven at 32 kHz.
5. **Decide the modulation route.** Then port the Peaks envelope, Frames LFO and Lorenz cores, regenerating their tables with the repositories' own generators (`res/peaks_lookup_tables.py` and others) for the control rate.
6. **Bookkeeping.**
   - docs/11: §3.3 candidates; §4, fix the Spectral FFT line; §7, Grids is GPL-3.0-or-later, O&C is MIT at repo level, aleph is licensed per directory.
   - docs/13: a "later" list (Kria lanes, Meadowphysics, Earthsea, Meta-Q, White Whale).
   - `notes/upstream-candidates.md`: the `util_turing.h` length-32 UB, under the oss-contributions rules; the Clouds shifter overlay, benign and not worth filing.
7. **Optional.** Ask Nicholas J. Michalek to add MIT headers to `tideslite` and `animorf_core.h` before we vendor either.