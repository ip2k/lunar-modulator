# Filters, compressors, limiters and overdrives: options (2026-10-05)

**Scope.** This note covers classic filter designs, compressors, limiters, overdrives and saturators. For each it says what to port, what to write ourselves, how it fits the effect slots, the voices and the modulation matrix, and what it costs on the FM-1. The owner also asked what four repositories can teach us: JieLi's AC79 SDK, Felucca, fm1-nes and sloop-fm1 (§1.3).

**Companion note.** notes/2026-10-02-delay-reverb-eq-gates-options.md (PR #37) covers:
- delays and reverbs;
- EQ, the DJ filter and tilt;
- Master Sat;
- the Gate and the key (side-chain) design.

This note does not repeat them. It keeps the file name the companion note links to, though it was written on 2026-10-05.

**What exists now** [verified: main `3596d95`]:
- PR #38 merged today (2026-10-05 16:38 UTC). It added four effects, all our own MIT code and all libm-free:
  - **Filter**, seven types: SVF, Ladder, Diode, Sallen-Key, SK Mixed, Comb and Formant. Parameters: Cutoff, Resonance, Drive, Mode, Morph, Mix, Level. A Type change warms the new type up and crossfades, so Type is MOD. Its renders are byte-identical from GCC/glibc, musl and Emscripten [verified: engines/README.md].
  - **Drive**, five types: Soft, Tube, Diode, Fuzz, Tape. It uses first-order anti-aliasing (ADAA) and has Tone, Bias, Gate and Auto level.
  - **Comp**: feed-forward, with Peak, RMS, Glue and Punch characters, Auto Rel and Auto Gain. `fm1_comp_reduction_db()` is in `engines/include/fm1_comp.h`.
  - **Limiter**: Brickwall and Soft Clip modes, 0–5 ms look-ahead (default 2 ms), and Link.
- Also on main:
  - the Crush, Fold and Echo effects;
  - vendored stmlib `Svf`, `OnePole`, `SoftClip`/`SoftLimit` and `Limiter`;
  - Braids `svf.h`;
  - Plaits VA+Filter, LPG, String and Overdrive (Overdrive is vendored but not yet wrapped as an effect);
  - the host's `fm1_mix_limiter`.
- **In flight, not on main** [verified: local branches]:
  - MG1–MG3: @mod-core `e00adea`, @mod-kinds `2d337cc`, @mod-pages;
  - multi-sound, with per-sound inserts and master slots: docs/15 §3.16 on @multi-sound `3ce8a40`;
  - per-note parameters (POLY and `set_param_note`): @per-note-params, worktree scratch/wt-pv;
  - the companion note's master-tone and Gate worktrees.
  - docs/15 S5 (record) and S6 (tracks and pages) are next on the sequencer.

**How this was checked.**
- Three research lanes:
  1. a filter catalogue of 62 entries;
  2. a dynamics and drive catalogue of 43 entries;
  3. a check of how these fit the repo and the in-flight branches.
- Licences were read from file headers and LICENSE files at pinned commits (§8). Nothing third-party was built or run, and no repo file was edited.
- I re-checked these myself:
  - PR #38's state and the merged parameter tables;
  - `step_of()` in `sim/web/src/fm1_app.c`;
  - the parameter flag bits in `fm1_engine.h`;
  - stmlib's tan-polynomial comment;
  - Felucca's audio HAL and its no-FPU comment;
  - notes/2026-10-02-jieli-compile-check.md §5.

**Marks.**
- [verified]: read or computed at the pinned commit.
- [reported]: a source says so; not re-checked.
- [inferred]: our estimate.

**Where the lanes disagreed, and what this note takes.**
1. **PR #38.** The lanes read before it merged:
   - lane 3 called it open;
   - lane 2 said Comp, Drive and Limiter lived only on worktrees;
   - lane 1 said the tree had no ladder, diode or Korg-35-style filter.

   It is now merged at `3596d95`. So most of lane 1's "write our own" verdicts are already done: the ZDF ladder, the diode ladder, both Sallen-Key families and the Cytomic SVF. The ports lane 1 proposed for the same designs (DaisySP Ladder, Open303, MoogLadders) become test oracles, not second implementations.
2. **The FPU.**
   - What is verified: JieLi's compiler emits single-precision FPU instructions for float add, multiply and divide [verified: compile check §5].
   - What is not measured: whether AC791N silicon runs them, and how fast.
   - Felucca's source says it targets "a CPU without an FPU" [verified: the comment, phys_dsp.c line 24; the claim itself is reported]. Felucca, SLOOP and fm1-nes are all integer-only.

   The lanes are each right about a different thing. The dev kit's FPU probe decides (docs/14). Plaits, Rings and every effect use float, so a missing FPU would change the whole platform, not only the filters (§4.2, decision 13).
3. **CPU yardsticks.** The lanes used different cost models:
   - lane 1: about 1.5 cycles per flop;
   - lane 2: 1 cycle per operation and 9 per divide;
   - lane 3: Plate, measured on the desktop and guessed at 3–5 % of a core, plus Felucca's instruction-count rule.

   They disagree by 2–3×. §5 gives ranges, and every CPU figure there is [inferred].
4. **Cutoff "log".** engines/README.md describes Filter Cutoff as "20 Hz–18 kHz, log". The parameter itself is linear:
   - the panel steps it 180 Hz per detent [verified: `step_of()` at `3596d95`];
   - the matrix adds amount × signal × (max − min) [verified by lane 3: `mod_core.c` at `e00adea`].

   How the DSP maps Hz internally does not change either. See §4.4.
5. **stmlib's FAST tan.** Lane 1 said to refit it for 44,118 Hz. The comment says it was fitted for 16 Hz–16 kHz at 48 kHz [verified: `filter.h` at `e3bd7c9`], which is 0.0003–0.333 of the sample rate. At 44,118 Hz that covers 15 Hz–14.7 kHz with the same error. Above that, use ACCURATE. No refit is needed. (The Filter effect has its own tan polynomial anyway.)
6. **Diode resonance limit.** Pirkle's note uses k ≈ 17 [reported], and so does Vital [verified: header]. Our Diode self-oscillates at k = 18.39 [verified: README]. These are different models, so this is not a contradiction.
7. **x42 dpl.lv2** is GPL-3.0-or-later, not GPL-2 [verified: file header at `8bcd25d`].
8. **Where the final clip goes.** Lane 2 put ClipOnly2 after the host bus limiter. Lane 3 keeps the bus limiter as the fixed last stage. This note keeps the bus limiter last and offers ClipOnly2 as a Limiter mode (§3).
9. **Telling Felucca about the FPU.** Lane 2 suggested telling Felucca's authors that the FPU is present. Not yet: only the compiler's output is verified, not the silicon (decision 15).

## Contents

1. Short answer
2. Filter designs
3. Dynamics and drive
4. How they fit
5. Budgets
6. Staged plan
7. Owner decisions
8. Sources

## 1. Short answer

### 1.1 What to build first

- **No new filter DSP first.** Main already has seven filter types. The first two stages make them usable:
  - **FD0: split Comb out of Filter.** Comb's delay lines make every Filter instance 18,368 B instead of 688 B [verified: README]. Twelve Filter slots would take 57 % of the 387,924-byte RAM gap.
  - **FD1: add a LOG taper flag.** Today a ±50 % LFO on Cutoff swings ±8,990 Hz and pins at the ends. With LOG, a route moves the knob position instead of the value. A NOTE route to Cutoff at +100 % then gives exact keytracking.
- **Per-voice filters next (FD7), inside the existing engines.**
  - A lean shared SVF kernel goes into Macro and Shapes first, then Six-Op and Macro Heavy.
  - Its Type defaults to Off, so every existing render stays byte-identical.
  - Until then, the filter-envelope recipe is one Filter insert driven by an Envelope kind (§4.2).
- **Dynamics gaps (FD2, FD3).** Comp, Limiter and Drive exist. Four things are missing:
  - a programme-dependent "mu" or half-wave character;
  - a compressor with a built-in gate;
  - a transient shaper;
  - a final rounding clip.

  First picks: Airwindows Pop3 (MIT), our own transient shaper after Bus Driver's measured law, and ClipOnly2 as a Limiter mode.
- **Modulation sources and side-chain (FD4, FD5):**
  - a control-rate filter kind in the rack;
  - Follow, fed by host tap meters on a fixed 32-frame grid;
  - Comp and Limiter gain reduction as sources, through `fm1_fx_ext_t`;
  - side-chain in three steps; the first needs no API change.
- **Licences.** Every pick is MIT, ISC, Apache-2.0, WTFPL, STK-4.3, public domain or our own code. Nothing needs GPL or LGPL code, so nothing goes behind `FM1_GPL_MODS`.
- **Nothing is measured on pi32v2.** A full four-sound set with dynamics comes to 75–200 % of a core on one yardstick and about 35 % on the other. The dev kit decides (FD9). Meanwhile, add an advisory CPU meter beside the RAM meter.

### 1.2 Recommended first set

| Order | What | Kind | Licence |
| --- | --- | --- | --- |
| 1 | Comb split (FD0) | refactor | own |
| 2 | LOG taper, 16-bit flags, dB unit (FD1) | API | own |
| 3 | Squash, with Pop3 first (FD2) | port | Airwindows, MIT |
| 4 | ClipOnly2 as Limiter mode "Round" (FD2) | port | Airwindows, MIT |
| 5 | Transient shaper (FD3) | own | after Bus Driver (MIT); no code taken |
| 6 | Resonator kind, Follow taps (FD4) | own | — |
| 7 | Gain-reduction sources, key input, latency (FD5) | API | own |
| 8 | Per-voice SVF (FD7) | own | Cytomic maths, public domain |

### 1.3 What the four named repositories teach

**JieLi AC79 SDK.** Gitee Jieli-Tech/fw-AC79_AIoT_SDK; local clone `reference/ac79-sdk` at `e30b1ee375d1`. The repository is Apache-2.0 [verified: LICENSE].
- **A hardware EQ block:** up to 20 IIR sections, float coefficients, 2 channels, coefficient fade-in (`asm/eq.h`) [verified: header].
  - It could carry a master EQ or DJ filter.
  - Its rounding is unknown, so the simulator could not match it sample for sample.
  - Measure it first, and keep a software path.
- **Closed dynamics libraries** [verified: headers and file sizes]:
  - `libcompressor.a`, 21,824 B;
  - `liblimiter.a`, 13,828 B;
  - `libdrc.a`, 44,440 B: a 3-band DRC with a 5-point dB curve and PEAK or RMS detection.

  They are binary-only, so they cannot run in WebAssembly. Use them only as a reference for parameter design; a "Curve" mode for Comp is one idea from them.
- **`math_fast_function.h`:** fast sin, cos, exp, ln, tanh and sigmoid, in fixed-point and float forms [verified: header]. The implementations are closed. Do not build voice DSP on them.

**Felucca.** `reference/Felucca` at `727f272015da`; GPL-3.0-only [verified: LICENSING.md and SPDX headers]. It runs on the chip. Ideas only:
- an integer trapezoidal SVF in Q13, with a 128-entry g table interpolated per block, and a 257-entry Q15 tanh table;
- 12 modal modes instead of 24, "the device cost" [verified: comment];
- load shedding: the audio interrupt measures its own load every half buffer, and fades one voice after two halves above 85 % [verified: audio.c];
- audio goes out over ALNK0 I2S to an external codec, with full scale at −6 dBFS of the 24-bit word [verified: `firmware/hal/fm1_audio.h`, `audio.c`]. docs/01 and CLAUDE.md say "internal DAC". Check against the PCB photos (decision 16).

**sloop-fm1.** `reference/sloop-fm1` at `f2b44c219b8a`; GPL-3.0-only, derived from Felucca [verified]. Ideas only:
- a one-knob DJ filter;
- a kick duck with the curve (1 − t/T)², applied as a gain ramp once per block;
- a lo-fi master stage called DUST.

The duck can be built here as a free matrix patch (§4.3).

**fm1-nes.** `reference/fm1-nes` at `870f3054869c`; Apache-2.0 [verified: LICENSE].
- It has a Q12/Q8 Chamberlin SVF with a 128-entry table: no float, and no division per sample.
- It can be ported with its notice, as the no-FPU fallback if one is ever needed.
- Its THIRD_PARTY.md notes that the repository licence does not cover separately supplied libraries [reported].

**All three FM-1 firmwares are integer-only.** That is either a real limit of the chip or a habit. The FPU probe will tell.

## 2. Filter designs

**CPU class** per mono voice-sample on pi32v2 [inferred: lane 1's operation counts at about 1.5 cycles per flop; unmeasured]:
- **A**: under 30 cycles;
- **B**: 30–80;
- **C**: 80–200;
- **D**: over 200.

At 12 voices, each voice has about 453 cycles per sample for everything (240 MHz ÷ 44,118 Hz ÷ 12). A stereo master effect costs about twice its class.

**Verdicts:**
- **BUILT**: on main, in the Filter effect.
- **PORT**: vendor permissive code.
- **OWN**: write our own from papers.
- **ORACLE**: permissive code used only as a desktop test reference.
- **REF**: read only.

| Design | Character | Verdict | Best source, licence, commit | CPU |
| --- | --- | --- | --- | --- |
| Trapezoidal SVF (Simper/Cytomic) | Clean 12 dB; LP, BP, HP and notch; peak, allpass and bell by mixing | BUILT (Filter SVF); the extra mixes OWN | Cytomic technical papers, "placed in the public domain" [reported: fetched through a summariser; quote the page itself in the licence inventory]; stmlib `Svf`, MIT, `e3bd7c9cc00e` [verified] | A |
| Chamberlin SVF, fixed point | Cheapest; unstable above about fs/6 unless run at twice the rate | PORT only if the FPU fails | fm1-nes `fm1_nes_fx.c`, Apache-2.0, `870f305` [verified]; stmlib `NaiveSvf`/`ModifiedSvf`, MIT [verified]; Teensy `filter_variable`: MIT-style notice in each file that must be kept, no repo LICENSE, `3039be2` [verified] | A |
| Integer SVF with "punch" (Braids, Peaks) | A transient opens cutoff and damping | Already vendored; punch is an idea for a modulation target | eurorack `braids/svf.h`, MIT, `08460a69a7e1` [verified] | A |
| LP–notch–HP morph (SEM style) | Smooth, open | OWN, as a Mode law if wanted. Filter's Mode already blends LP, BP, HP and notch | Faust `oberheim`, STK-4.3, `bf9f71af2f6`, as a cross-check [verified] | A |
| Transistor ladder: ZDF, one curve in the loop | Warm 24 dB; loses bass as resonance rises | BUILT (Filter Ladder, with 6–24 dB taps) | Zavalishin, *The Art of VA Filter Design* rev 2.1.2 (the book's licence covers copying the book only) [verified p.ii]; Faust `moogLadder`, STK-4.3, as a cross-check | B |
| Ladder with tanh in every stage (Huovilainen), 2–4× | Richer resonance | ORACLE; never per voice | DaisySP `LadderFilter`, MIT, keep its header, `2c72eaf9eac5` [verified]. Not the Csound or MoogLadders Huovilainen code (LGPL) | C at 1×; D at 2–4× |
| Ladder, D'Angelo–Välimäki "improved" model | Accurate self-oscillation | ORACLE | MoogLadders `ImprovedModel.h`, ISC, `a968ec6ddfe1` [verified] | C |
| Cheap explicit ladders (Krajeski, Microtracker, Stilson) | Cheap; detune as cutoff moves | Not needed; only a no-FPU option | MoogLadders: Unlicense, or public domain by the authors' email [verified: headers]. Never musicdsp #24 or #26, or FunDSP's copy of those coefficients (no licence) | B |
| Slope taps 6–24 dB; HP and BP ladders | One ladder, many responses | BUILT for the LP taps (Mode). HP and BP tap tables are available | Open303 `TeeBeeFilter`, MIT, `313bf0d9ade7` [verified: License.txt]; DaisySP, MIT | +9 flops |
| Diode ladder (TB-303 style) | Rubbery, "acid" | BUILT (Filter Diode). The 303's high-pass in the feedback path (150 Hz in Open303) is not in it [inferred from the README] | Open303 TB_303 mode, MIT, as an oracle or an option; Faust `diodeLadder`, STK-4.3 | B–C |
| Sallen-Key with saturating feedback (Korg-35 style) | Raspy; screams | BUILT (Filter Sallen-Key) | Cytomic SKF notes, public domain [reported]; Faust `korg35LPF`/`korg35HPF`, STK-4.3 | B |
| Mixed-input Sallen-Key (Steiner-Parker style) | Vocal, "honky" | BUILT (Filter SK Mixed) | Zavalishin §5.8. No open code found: the Vult Tangents source is missing at `3cc9a46` [verified] | C |
| OTA 4-pole (CEM3320 and IR3109 class) | Rounder and cleaner than a transistor ladder | OWN later: a Ladder variant with an OTA-style curve in each stage | Zavalishin §6.9 [verified]. GPL Hera, Surge and Vital are REF only | B–C |
| Hard-clipping SVF (Polivoks style) | Gritty; distorts before it rings | OWN, low priority | No DSP code. Shruthi filter boards are cc-by-sa 3.0, the discontinued ones cc-by-nc-sa [verified: README, `56bfe78`] | B |
| CMOS-inverter SVF (Wasp style) | Dirty, asymmetric | OWN approximation, low priority | Koper et al., DAFx-22 (paper only, no code) [verified] | B |
| Multimode with notch offset (ARP 1047 style) | Resonator with a movable notch | OWN later, from Collin's paper | chowdsp `ARPFilter`, GPLv3, REF only | A–B |
| Generalised SVF ladder (Werner–McClellan) | One structure for 2- and 4-pole blends | OWN, after reading the paper (unread: its host was down) | chowdsp `WernerFilter`, GPLv3, REF only | C |
| Low-pass gate | "Ping", with vactrol memory | In tree (Plaits LPG, Macro page 3). OWN a vactrol-style envelope | Plaits, MIT [verified]; Streams `vactrol`, MIT, for the idea, `08460a6` [verified]; Parker and D'Angelo, DAFx-13 | B |
| Comb | Peaks or notches | BUILT (Filter Comb); split it out (FD0) | Zölzer, *DAFX*; Plaits String, MIT, in tree | A |
| Formant | Vowels | BUILT (Filter Formant, Peterson–Barney data). A Klatt cascade later if wanted | Rings formant filter, MIT; klattsch, MIT, `63dc2c6` [verified] | B |
| Phaser (allpass chain) | Swept notches | OWN, as an effect | DaisySP `phaser`, MIT, for parameter ranges [verified] | A |
| DJ one-knob filter, isolator | Master tone | Companion note (its stages B2 and B6) | stmlib, MIT; Airwindows `Isolator3`, MIT | A |
| Biquads (RBJ, Vicanek matched) | EQ, voicing | PORT the design maths; compute coefficients per block | signalsmith `dsp`, MIT, `4f62b0a8783c` [verified]; Faust Vicanek filters, MIT | A |
| 2× half-band oversampling | For hard-driven types | PORT; run the designer offline | HIIR, WTFPL v2, unevens/hiir `4589fed` [verified] | about 25 cycles per direction |

**Reference only.** Never in the public simulator or in a build we share.
- **GPL:**
  - Vital `636ca0e` (GPL-3+);
  - sst-filters `3431696` (GPL-3). Its `CytomicSVF.h` says it may be copied in an MIT context [verified: quote], but we already have our own SVF;
  - VCV Fundamental `10dd016` (GPL-3+; its panels are CC BY-NC-ND);
  - Befaco `bf03788` and Bogaudio `656eaae`;
  - chowdsp_filters in chowdsp_utils `e97b826` (GPLv3);
  - Odin 2 `265e9e2`, OB-Xd `0c7c737` and SuperCollider `d81d67f`;
  - Felucca and sloop-fm1 (GPL-3.0-only).
- **AGPL:** JUCE `dsp::LadderFilter` `be29c81` (AGPLv3 or commercial). Its tap table is the same common knowledge as Open303's.
- **LGPL:**
  - Csound `95ce8ad` (LGPL-2.1+);
  - DaisySP-LGPL `c89d380`;
  - Soundpipe's modules extracted from Csound, `3efb43b`: MIT at the repo level, LGPL by origin;
  - MoogLadders' Huovilainen model.
- **No licence:**
  - the musicdsp archive `d7c8525`, and code copied from it: FunDSP's Moog coefficients and the filter in schwung-moog/RaffoSynth;
  - MoogLadders' "Simplified" model is for educational use only.

**Why this set.**
- The seven built types already cover the transistor ladder, the diode ladder, both Sallen-Key families, the SVF, a comb and formants. Their tuning, slopes, self-oscillation and determinism are tested [verified: README].
- What is missing is not more types. It is four things:
  1. RAM (Comb) and the parameter law (LOG).
  2. A lean per-voice kernel. The Filter effect solves a nonlinear loop every sample and updates its coefficients every 8 samples. That is too heavy to run per voice (§5).
  3. Test oracles:
     - compare Ladder against DaisySP's ladder and the MoogLadders Improved model;
     - compare Diode against Open303's TB_303 mode;
     - at low drive, within a tolerance, not bit for bit.

     This means building permissive third-party code in a desktop test target (decision 10).
  4. New types, but only after the dev kit, with OTA Ladder first. Name them after circuits, never after makers, people or part numbers (owner's rule, 2026-10-02 [verified: README "Names"]).

## 3. Dynamics and drive

**CPU** per stereo frame on pi32v2 [inferred: lane 2's static operation counts]. Assumed costs:
- 1 cycle per operation;
- 9 per divide;
- about 15 per polynomial sin;
- about 40 per `sqrtf` call.

1 % of a core is about 54 cycles per frame.

| Design | Character | Verdict | Best source, licence, commit | CPU per frame |
| --- | --- | --- | --- | --- |
| Feed-forward compressor: Peak, RMS, Glue, Punch | General purpose | BUILT (Comp) | own, MIT | 1.5–2.2 µs per block on an M1 Max [verified] |
| Look-ahead limiter | Programme limiting | BUILT (Limiter). Signalsmith's design, written from the article | Signalsmith `basics` `369e906` and `dsp` `4f62b0a`, MIT, as design references [verified] | 1.0–1.4 µs per block [verified] |
| Bus guard | Safety net | BUILT (`fm1_mix_limiter`: instant attack, 100 ms release, 0.98 ceiling, NaN guard) | own | about 20 operations |
| Overdrive: 5 curves with ADAA | Soft, Tube, Diode, Fuzz, Tape | BUILT (Drive) | own | 2.6–5.5 µs per block [verified] |
| Compressor with a gate stage (Pop3) | Attack and release; can only attenuate; quarter-sine gate | PORT first | Airwindows `Pop3`, MIT, `e718c9bcfcdd` [verified: LICENSE and header] | about 95 |
| Variable-mu machine (Pressure4) | Programme-dependent, "bloomy" | PORT, without its built-in 1/threshold makeup and its sin output stage | Airwindows `Pressure4`, MIT | 135–165 |
| Half-wave split glue (ButterComp2) | No timing knobs; recovers more slowly while loud | PORT; delete the function-static noise | Airwindows `ButterComp2`, MIT | about 140 |
| Slew-chase leveller and swell (Surge, Swell) | A smooth leveller; a self-keyed volume swell | PORT, optional | Airwindows, MIT | about 55 / about 35 |
| Bezier release (Dynamics3, BeziComp) | The gain curve turns at a fixed sharpest corner | OWN, as a release shape for Comp | Airwindows, MIT, for the idea | — |
| Transient shaper | Attack up or down, sustain up or down | OWN, from Bus Driver's measured two-follower law (fast 1.5 ms / 50 ms, slow 1 ms / 669 ms) | legsmechanical/schwung-busdriver, MIT, `36b6788` [verified]. Its shaper tables are measurements of a commercial unit, so take the law, not the tables. Airwindows `Point` is the cheap baseline, though it softens only weakly [reported] | 100–150 |
| Gate, expander | Drawmer DS201 style | Companion note (its stage B3) | Ideas: Signalsmith `dynamics.h` knee and hysteresis, MIT; Airwindows `Gatelope` split decay, MIT; Schwung Gate, MIT, `afdd5c2` | about 60 |
| Ducker curves | Linear, exponential, S-curve, pump | A matrix patch (§4.3), with the curves as Function shapes | Schwung Ducker, MIT, `0033e4c` [verified] | about 0 |
| Interpolating final clip (ClipOnly2) | Rounds overs; 1 sample of latency | PORT, as a third Limiter mode | Airwindows `ClipOnly2`, MIT | about 45 |
| Cheap soft drive | SoftClip with automatic gain | Already vendored. Wrap it only if Drive proves too heavy on the device | Plaits `overdrive.h`, MIT, `08460a6` [verified] | about 40 |
| Soft clippers with no divide | Smooth (C1) curves | PORT the formulas | stmlib `SoftLimit`, MIT; Faust `softclipQuadratic`, MIT, and `cubicnl`, STK-4.3 (`bf9f71a`) [verified] | 10–20 |
| Opto-style release | Release slows after long gain reduction | OWN, as a Comp release option | Streams `vactrol`, MIT, for the idea | small |
| Normalled key and amount law | Side-chain with a fallback | OWN (companion §7.6 already cites it) | Streams `compressor.cc`, MIT [verified] | — |
| Diode-pair circuit model | Pedal-like clipping | OWN after the dev kit, as an optional Drive type | KlonCentaur, BSD-3-Clause, `f3bb633`; its `omega.h` is MIT (D'Angelo) [verified] | 80–120 per channel |
| Tape and console models; heavy Airwindows plugins (Logical4, Compresaturator, ToTape5–9, ADClip7, Pop v1) | — | No: each needs 24–177 KB of RAM or 9–13 % of a core | Airwindows, MIT | — |

**Reference only:**
- **GPL:**
  - Faust `compressors.lib`, the Brouns functions, `bf9f71a`. They are declared GPL-3.0-only per function, under a file header of LGPL-2.1+ with a compiled-output exception. Take the stricter licence;
  - chowdsp's compressor, waveshapers and dsp_utils modules (GPLv3), `e97b826`;
  - x42 dpl.lv2 (GPL-3+), `8bcd25d`;
  - ChowTape `604372e` and OTTx (GPL-3);
  - Guitarix (GPL-2+), `666b564`;
  - Rakarrack/rkrlv2 (GPL-2 only), `0e6d6e0`;
  - Felucca and SLOOP.
- **LGPL:**
  - DaisySP-LGPL's `Compressor`, `c89d380`. It was removed from the MIT DaisySP in `c59a4dcd` (2023-12-21). Older copies, such as CHOMPI's, still carry it under an MIT label [reported]; never take it from those;
  - Calf (LGPL-2.1), `ecbbb2d`.
- **Unclear or no licence:**
  - Soundpipe's compressor, dist, clip and fold modules, `3efb43b`;
  - Faust `tubes.lib`, whose tables come from Guitarix;
  - Super Boom and PushNPull (no licence).
- **Closed:** the AC79 SDK's `libcompressor.a`, `liblimiter.a` and `libdrc.a`.
- **MIT but too heavy:**
  - Signalsmith `crunch.h`: about 18 % of a core with 2× oversampling. Take three of its ideas: filter the gain rather than the signal; its formula for fuzz asymmetry; a high-pass before the shaper.
  - TapeScam: hard-coded to 48 kHz, with 22 libm calls.

**Rules for porting Airwindows code.** These apply to every Airwindows item above.
1. Float only: no `double` and no `long double`. Both run in software on pi32v2 [verified: compile check §5].
2. Delete the `fpd` xorshift noise that keeps values out of the denormal range. Delete the "live air" noise in ButterComp2, VariMu and DeEss too: its state is function-static, so it is shared across instances. Silence in must give exact silence out.
3. Replace `sin`, `cos`, `pow` and `sqrt` inside the loop with polynomials or precomputed values.
4. Keep `overallscale` = fs ÷ 44,100. It is 1.0004 at 44,118 Hz.
5. Build with `-ffp-contract=off`, keep the existing input guard, and allow no libm in `nm`.
6. Vendor the code into `third_party/airwindows/` with LICENSE, `UPSTREAM.md` and the pinned commit. Keep "Airwindows uses the MIT license" in each file. Lane 2 read `e718c9b` (2026-10-04); the companion note read `d22a25b`. Record whichever one is vendored.

**Recommended first set:**
1. **Squash**, with Pop3 first (FD2). It has attack and release, it cannot raise the noise floor, and it brings a gate for free. Bus Driver measured 0.00 dB of lift on a −48 dBFS sine [reported].
2. **Transient shaper** (FD3), our own.
3. **ClipOnly2**, as a Limiter mode called "Round" (FD2).
4. **Comp units** (FD1): Release gets LOG; Threshold, Knee and Makeup get the dB unit.
5. **Mu (Pressure4) and Split (ButterComp2)** as Squash types, after the dev kit has measured Pop3.

Comp's controls (Threshold, Ratio, Attack, Release) do not map onto Pressure4 or ButterComp2, which have no timing knobs. So these go into a separate small effect, not into Comp as characters (decision 9).

## 4. How they fit

### 4.1 Per-sound inserts and the master chain

**Per-sound inserts.** docs/15 §3.16 on @multi-sound gives each sound two slots.
- In1, colour or tone: Filter or Drive.
- In2, dynamics or space: Comp, Squash, Gate, transient shaper or Echo.
- The order can be swapped. Put Drive before Comp in a sound, so the Comp tames what Drive adds.
- No Limiter on a sound's insert, because of its latency (see below).
- Reverb and delay are shared sends (companion §8).

**Master chain.** Recommended order:
1. Tone (Tilt, EQ or Isolator);
2. Sat, or Drive at low drive;
3. Comp (Glue, keyable);
4. a performance slot (Repeat or Gate);
5. DJ Filter;
6. Limiter;
7. the host bus limiter;
8. MASTER volume.

Why this order:
- Comp comes before DJ Filter, so sweeps and resonance do not pump its detector.
- The Limiter comes last, to catch resonant peaks.
- Have **four master slots, not two** (decision 4). An empty slot costs only a record, and the RAM meter limits what loads.

**Limiter latency.** Look-ahead is latency.
- The default 2 ms is 88 frames at 44,118 Hz. RAM is sized for 5 ms: 11,008 B [verified: README].
- On one sound's insert, it would shift that sound by 2 ms against the others.
- Now: look-ahead on the master only. On an insert, use Lookahead 0 or the Soft Clip mode.
- With `fm1_fx_ext_t` (FD5): each effect declares `latency_frames`, and the host delays the shorter paths to match. That is up to 221 stereo frames, about 1.7 KB per compensated unit.

**Host bus limiter.** It stays as the final guard.
- With the Limiter at its default −1 dB ceiling (0.891), the bus limiter never acts.
- HOST AMP (tremolo) stays per sound, before the inserts. Level comes after the inserts.

### 4.2 Per-voice filters

**First, a filter envelope with no per-voice cost** (paraphonic):
- one Filter insert on the sound;
- an Envelope kind into Cutoff, gated by KEY and retriggered by TRIG;
- NOTE to Cutoff at +100 %, which keytracks the last note (needs FD1);
- VEL to Resonance or Drive.

All notes share one filter. Make this the documented recipe and a demo preset.

**Then, a lean kernel inside the engine wrappers** (decision 5). All four wrappers are our code. Each sums its mono voices before one resampler, so there is a clean point to insert the filter [verified by lane 3 at main `6c03073`]:

| Engine | Voices | Native rate, block | Where the filter goes |
| --- | --- | --- | --- |
| Macro | 12 | 47,872 Hz, 12 samples | `v.out` after `Render`, before Plaits' LPG/VCA (`mi_macro.cc` 325–329) |
| Shapes | 12 | 96,000 Hz, 24 samples | `v.pcm` after `osc.Render`, before the envelope (`mi_shapes.cc` 182–187) |
| Six-Op | 8 | 47,872 Hz, 16 samples | `scratch_` after `fm.Render`, before SoftClip (`mi_sixop.cc` 333–337) |
| Macro Heavy | 4 | 47,872 Hz | `v.out` after `Render` (`mi_macro_heavy.cc` 628) |

Not Sophie: it is a closed-off Schwung module with its own per-pad filters.

**The kernel:**
- a mono trapezoidal SVF with LP12, LP24 (two stages), BP, HP and notch;
- coefficients computed once per chunk, from a cutoff in log pitch: base + keytrack + envelope + POLY offset, with a 5 ms glide;
- a cheap cubic soft clip, so resonance cannot reach the int16 clip in Plaits' output stage;
- about 24 B per voice.

**Parameters**, appended after the existing uids:

| Parameter | Range | Flags |
| --- | --- | --- |
| Filter Type | Off, LP12, LP24, BP, HP, Notch | ENUM, LATCH, MOD (reaches new notes only, so no crossfade is needed) |
| Cutoff | Hz | LOG, POLY, SMOOTH, MOD |
| Reso | 0–1 | POLY, SMOOTH, MOD |
| Env Cutoff | −1 to 1: the voice's own envelope, like Env Timbre | POLY, MOD |
| Keytrack | −1 to 2 (1 = 100 %) | MOD |
| Drive | 0–1 | POLY, SMOOTH, MOD |

- Type Off skips the code, so every existing render stays byte-identical.
- Keep the fixed Keytrack and Env Cutoff parameters even after MG9. They cost nothing, and they make a sound with an empty matrix sound right. Felucca's analog engine does the same [verified: eng_analog.c].

**Never reuse the Filter effect's kernels per voice.** For 12 Macro voices that would cost about 10 Plates, 31–51 % of a core (§5).

**A new subtractive engine: defer it** (decision 6).
- Macro already has VA and VA+Filter oscillators. What it lacks is a sustain stage. A POLY Envelope kind (MG9) gives that to every engine.
- Revisit once the per-voice filter and the POLY envelope have been heard in the simulator.
- If it is still wanted: our own, about 400 lines, starting at 8 voices.

**The integer question.** Lane 1 suggested a fixed-point fallback for every filter. But Plaits, Rings and the effects all use float, so a missing FPU would sink the whole platform plan, not just the filters.
- Write the per-voice kernel in float.
- Keep a written design for an fm1-nes-style Q12 kernel, and build it only if the FPU probe fails (decision 13).

### 4.3 Filters and dynamics as modulation sources

**A control-rate filter kind in the rack** (FD4).
- Inputs and parameters:
  - IN, an INPUT parameter;
  - Cutoff, 0.05–300 Hz (LOG, MOD);
  - Reso and Level.
- It runs once per tick, at 1,378.7 Hz. Cutoffs above about 0.45 of the tick rate are clamped.
- Outputs:
  - LP: a 2-pole lag, smoother than Slew's single pole;
  - BP: a resonator. A gate into IN rings a damped sine ("boing", "wobble");
  - HP: a change detector;
  - notch.
- Plain lag stays with Slew.
- Cost: about 25 flops per tick and 24 B of the module arena.
- Name: "Filter" would clash with the audio effect, so the recommendation is **Resonator** (decision 12).

**Follow, fed by host tap meters** (FD4, decision 7). docs/16 §3.7 planned to split the tapped unit's render at every tick. Instead:
- The host feeds the chosen tap buffer to a detector one sample at a time, in whatever pieces it renders. The detector is attack and decay one-poles on max(|L|, |R|), plus one band split near 1.5 kHz for a BRIGHT output.
- It takes a snapshot at every absolute multiple of 32 frames.
- The tick at time t reads the snapshot taken at t − 32.
- The value is exactly one tick (0.725 ms) late. It is the same at any block size and needs no extra render calls.

Details:
- Taps: each sound before and after its inserts, each insert and master slot's output, and the master input.
- To use a filter's output as a source, put a Follow on that slot's tap.
- Outputs: ENV, BRIGHT, and GATE (with hysteresis).
- Drop docs/16's "audio level (previous block's peak)" system source, because its value depends on the block size.
- Write our own detector. Streams' follower (MIT) costs 100–150 cycles per sample.

**Effect outputs** (FD5, with the companion's `fm1_fx_ext_t`):
- Outputs:
  - Comp: GR (0–1 = 0–24 dB) and KEY;
  - Limiter: GR (add `fm1_limit_reduction_db()`);
  - Gate: OPEN, ENV and KEY.
- Source ids are 128 + 4 × slot + port.
- The host splits an effect's render at tick frames only while one of its outputs is routed.
- The Filter exports nothing; use a Follow tap on it.

**Side-chain in three steps** (decision 11):
0. No API change: route any source to Comp's Threshold, with Threshold at 0 dB and Ratio 8–20. Comp's own attack and release then shape the duck.
1. A DUCK INPUT parameter (a gate cable through a comparator) and a Duck depth, using Comp's free uids.
2. An audio key from another sound's tap (companion §7), once there are several sound units.

docs/16's Duck module is then redundant. The companion's decision 8 agrees.

**The SLOOP-style duck, as a patch:**
- A kick track's gate (or TRIG) drives an Envelope with curve SQUARE, inverted, into the pad sound's Level.
- It needs each sound's Level exposed as a HOST destination with MOD (LEVEL1–4, beside PITCH and AMP).
- Cost: one envelope tick.

### 4.4 Parameters as routing targets

**LOG taper** (FD1, decision 2):
- It is a new flag. The knob position is u = ln(v/min) ÷ ln(max/min).
- A knob detent moves u by 1/100, about 1.2 semitones for Cutoff.
- A route moves u by amount × signal.
- Hz stays the stored, displayed and preset unit.
- One rule gives keytracking: a SEMI source into a LOG target moves it by amount × signal × 60 semitones. So NOTE to Cutoff at +100 % tracks one octave per octave.
- LOG needs min > 0.
- Cost: one polynomial exp2 per LOG target per tick.

**The flags byte is full.**
- `fm1_param_t.flags` is a `uint8_t`. On main, LATCH is 0x01, SMOOTH 0x02, NOLOCK 0x04, MOD 0x08 and INPUT 0x10 [verified: `fm1_engine.h` at `3596d95`].
- POLY takes 0x20 on @per-note-params. The companion note's KEYSRC also asks for 0x20 (its §7.4) [verified by lane 3].
- Fix: widen flags to `uint16_t` in the API v3 bump, put KEYSRC at 0x40 or above with LOG beside it, and add `FM1_UNIT_DB`.

**Proposed flags:**

| Unit | Parameter | Now [verified: `3596d95`] | Proposed |
| --- | --- | --- | --- |
| Filter | Cutoff | CONTINUOUS (SMOOTH, MOD), linear | add LOG |
| Filter | Type | MOD (the warm-up and crossfade make stepping safe) | keep |
| Filter | Resonance, Drive, Mode, Morph, Mix, Level | CONTINUOUS | keep |
| Comp | Threshold, Knee, Makeup | CONTINUOUS, unit none | add the dB unit; Threshold is the duck target in step 0 |
| Comp | Release (10–2000 ms) | CONTINUOUS | add LOG |
| Comp | Attack (0–100 ms) | CONTINUOUS | stays linear (its min is 0) |
| Comp | Character, Auto Rel, Auto Gain | ENUM, MOD | keep |
| Limiter | Ceiling, Drive | CONTINUOUS, unit none | add the dB unit |
| Limiter | Release (1–1000 ms) | CONTINUOUS | add LOG |
| Limiter | Lookahead | CONTINUOUS | drop MOD once latency is compensated, since it is the latency [inferred] |
| Drive | Drive, Level | CONTINUOUS, unit none | add the dB unit |
| Per-voice | Cutoff, Reso, Drive, Env Cutoff | — | POLY (§4.2) |
| Host | LEVEL1–4 | — | MOD, not NOLOCK |

**How POLY offsets arrive.** They go through `set_param_note(self, key, index, offset)`:
- in the parameter's own units;
- each call replaces the last;
- dropped when the voice ends.

[verified by lane 3 in scratch/wt-pv; uncommitted, so the shape may change.] For a LOG parameter, the host converts to an absolute value and sends (final − base), so engines need no knowledge of logs.

## 5. Budgets

**Basis:**
- 240 MHz ÷ 44,118 Hz = 5,440 cycles per frame;
- 348,160 cycles per 64-frame block;
- at 12 voices, about 453 cycles per voice-sample for everything.

Nothing below is measured on pi32v2. Two yardsticks are used:
- **Plate:** desktop µs ÷ Plate's 0.89 µs × 3–5 % of a core. Plate's share of a core is itself [inferred].
- **Operations:** static counts at 1 cycle per operation (lane 2), or Felucca's on-device rule of about 1.7 % of the device per 100 host instructions per sample [reported: test comments; the measurements are not in the clone].

They differ by 2–3×. Double the operation-count figures until something is measured.

### 5.1 Per instance

| Unit | RAM | Desktop per 64-frame block, M1 Max [verified] | Plate yardstick | Operations yardstick |
| --- | --- | --- | --- | --- |
| Filter SVF / Ladder / Diode | 688 B (+17,680 B for Comb's lines today) | 1.4 / 2.2 / 2.4 µs | 5–8 / 7–12 / 8–13 % | — |
| Filter Sallen-Key / SK Mixed | same | 3.2 / 3.6–4.9 µs | 11–18 / 12–27 % | — |
| Filter Comb / Formant | same | 0.8 / 0.9 µs | 3–5 % | — |
| Drive | 240 B | 2.6 µs (defaults) to 5.5 µs | 9–31 % | about 3 % |
| Comp | 208 B | 1.5–2.2 µs | 5–12 % | — |
| Limiter | 11,008 B at 44,118 Hz | 1.0–1.4 µs | 3–8 % | — |
| Squash: Pop3 / Pressure4 / ButterComp2 | under 200 B | — | — | 1.7 / 2.5–3 / 2.6 % |
| ClipOnly2, Plaits Overdrive | under 150 B | — | — | 0.8 / 0.75 % |
| Transient shaper | under 100 B | — | — | 1.8–2.8 % |
| Resonator rack kind | 24 B | — | — | negligible |
| Tap meter | 16 B + 3 floats | — | — | 0.15–0.6 % per tap |

### 5.2 Per-voice filter at 12 voices

Native-rate samples per voice per host block: 69.4 for Macro and Six-Op, 139.3 for Shapes. A lean SVF is about 20 operations per sample [inferred].

| Engine | Voices | Lean SVF | Ladder-class lean kernel (about 1.6×) |
| --- | --- | --- | --- |
| Macro | 12 | 4.8 % at 1 operation per cycle; 10–14 % at 2–3 | 8–22 % |
| Shapes | 12 | 10–29 % | 17–46 % |
| Six-Op | 8 | 3–10 % | 5–16 % |
| MG9 per-voice routing | 12 | about 2.7 % (3 POLY routes, 2 ticks per block, plus 12 envelopes) | — |

- Running the Filter effect's SVF per voice instead would cost about 10 Plates for 12 Macro voices: 31–51 %, or 23 % on the operations yardstick. That rules it out.
- A ladder with tanh in every stage at 4× costs about 320 cycles, 70 % of the whole voice budget. Never per voice at 12 voices.
- Consider a lower Shapes voice cap with the filter on, until it is measured.
- RAM: under 300 B for 12 voices.

### 5.3 Against the FM-1

**RAM.** The gap is 387,924 B [verified: README]. Filter is the only problem:
- twelve Filter slots take 220,416 B with Comb, or 8,256 B without it;
- everything else in this note comes to under 12 KB together, the master Limiter included.

**CPU, a worked set:**

| Part | Plates |
| --- | --- |
| Four sounds, each with Drive and Comp inserts | 19–34 |
| Master chain: Tone, Sat, Comp, DJ Filter, Limiter | 4–6 |
| Per-voice filters on two Macro sounds | 2–6 |
| **Total** | **25–45** |

That is 75–200 % of a core on the Plate yardstick, or about 35 % on the operations yardstick, before the engines.

**So:**
- Add an advisory CPU meter beside the RAM meter:
  - each effect gets a cost class, from desktop figures now and pi32v2 cycles after the dev kit;
  - amber at 70 %;
  - it never refuses a change. RAM keeps the only refusal.
- An effect at Mix 0 with no tail skips its loop. fm1-nes does this [reported by lane 3].
- Decide a shed policy at the dev kit: bypass the costliest insert first, then cap voices. Felucca sheds a voice after two half-buffers above 85 % [verified].

## 6. Staged plan

These stages come after the current work: docs/15 S5 and S6, MG1–MG3 (docs/16), the per-note branch and multi-sound. They are named FD (filters and dynamics) so they do not clash with the companion note's B1–B8.

Every stage keeps these standing tests:
- **Parity:** native output equals WebAssembly output byte for byte: GCC with glibc, musl, Emscripten under Node, and Apple clang with FP_CONTRACT off.
- **Block size:** identical output at host blocks of 1, 7 and 64 frames.
- **Neutral identity:** Mix 0, Type Off or a zero route leaves existing renders byte-identical.
- **Contracts:**
  - silence in gives exact silence out;
  - output stays finite under noise, NaN and infinities;
  - no libm in `nm`.

| Stage | Contents | Depends on | Extra tests |
| --- | --- | --- | --- |
| **FD0 Filter tidy** | Comb becomes its own effect (Filter back to 688 B). Fix the README's Cutoff wording. Later in the same stream: a 12/24 dB Slope for SVF LP and HP, and exact bypass at the open end (companion §4.6) | main `3596d95` | Every non-Comb Filter render is unchanged. The Comb effect equals the old Comb type sample for sample. Formant's enum value moves from 6 to 5; nothing is released, so no migration |
| **FD1 Parameter law** | The LOG flag; the SEMI-to-LOG octave rule; flags widened to `uint16_t`; KEYSRC at 0x40 or above; `FM1_UNIT_DB`. LOG on Cutoff and the Release times; dB units on Comp, Limiter and Drive | MG1 merged; the per-note POLY bit settled; API v3 (companion decision 6) | NOTE to Cutoff at +100 % tracks exactly 1 octave per octave. LOG routes identical at blocks 1, 7 and 64. All audio unchanged (flags only) |
| **FD2 Squash and Round** | `third_party/airwindows/` with Pop3 and ClipOnly2; Pressure4 and ButterComp2 after FD9. The Squash effect. The Limiter's Round mode | FD1, for units | Reference renders against the upstream double-precision code with its noise disabled, compared by residual (decision 10). Exact silence. Pop3 lifts nothing on a −48 dBFS sine |
| **FD3 Transient shaper** | Our own: two followers, symmetric up and down, polynomial exp2 | FD1 | Attack boost and tail cut, in dB, on a drum loop, within stated bounds. The centre setting passes the signal bit for bit |
| **FD4 Rack sources** | The Resonator kind. Follow with host tap meters on the 32-frame grid. Drop the previous-block level source | MG1–MG3 | The ring stays bounded. Follow is exactly one tick late at blocks 1, 7 and 64. A tap that is off costs nothing |
| **FD5 Effect outputs, key, latency** | `fm1_fx_ext_t`, shared with the companion's B3: GR and Gate outputs; `fm1_limit_reduction_db()`; Comp's DUCK input; `latency_frames` and compensation. Later, the audio key | FD1; the companion's B3 | A routed output does not change the audio. The GR source is identical at any block size. An impulse through a 2 ms Limiter lines up with an uncompensated path |
| **FD6 Chains** | Per-sound inserts and 4 master slots; the default master order; Limiter look-ahead on the master only; LEVEL1–4 as MOD targets. Demo presets: the paraphonic filter envelope and the kick duck | multi-sound (docs/15 §3.16); S6; the companion's B7 | The default chain at neutral settings passes the signal bit for bit. The ceiling holds at −1 dB |
| **FD7 Per-voice filter** | The lean kernel in Macro and Shapes, then Six-Op and Macro Heavy. Parameters: Type, Cutoff, Reso, Env Cutoff, Keytrack, Drive | FD1 | Type Off is byte-identical on every engine render. The per-voice SVF matches the Filter SVF on one mono voice within a tolerance. Resonance stays below the int16 clip. Voice stealing is click-free |
| **FD8 Per-voice modulation** | POLY on Cutoff, Reso, Drive and Env Cutoff; routes from MG9 | the per-note API; MG9 | A zero offset leaves each voice unchanged. A poly-to-mono cable is refused. Per-voice routes are identical at blocks 1, 7 and 64 |
| **FD9 Dev kit** | The FPU probe; cycles per effect and per voice; interrupt load. Replace the yardsticks; set the CPU meter's classes; the shed policy; the Shapes voice cap. Then, if the budget allows: Mu and Split; an OTA Ladder type; a feedback high-pass option on Diode; HIIR 2× oversampling for hard drive; the subtractive-engine question | AC79 dev kit (docs/14) | Measured cost is under budget. The integer kernel is built only if the FPU fails |

**Size** [inferred]:
- FD0: about 150 lines;
- FD1: about 300;
- FD2: 400–600, not counting vendored files;
- FD3: about 200;
- FD4: 300–400;
- FD5: about 400;
- FD7: about 300, plus tests.

All of it counts toward the next dead-code audit mark in CLAUDE.md.

## 7. Owner decisions

1. **Comb.** Split it into its own effect? Or raise its lowest pitch to about 80 Hz with int16 lines (about 2.2 KB)? Or leave it? *Recommended: split it (FD0) now, while nothing is released.*
2. **LOG taper.** Add the flag and the SEMI-to-LOG octave rule? Or store pitch-like parameters in semitones, or move to 0–1 knobs? *Recommended: the LOG flag, with Hz as the stored unit.*
3. **Flags and units.** In API v3: widen flags to 16 bits, put KEYSRC at 0x40 or above, and add `FM1_UNIT_DB`? *Recommended: yes to all three.*
4. **Master slots.** Two (the docs/15 §3.16 draft), four or six? *Recommended: four, with the host bus limiter fixed after them.*
5. **Per-voice filter.** A lean kernel inside the engine wrappers, a new engine, or an API that hands voice buffers to the host? *Recommended: the lean kernel, Macro and Shapes first.*
6. **Subtractive engine.** *Recommended: defer it until the per-voice filter and the POLY envelope have been heard.*
7. **Audio taps.** Host tap meters read one tick late, or docs/16's render splits? *Recommended: tap meters, and drop the previous-block level source.*
8. **Limiter latency.** *Recommended: look-ahead on the master only for now; delay compensation once `fm1_fx_ext_t` lands.*
9. **Airwindows dynamics.** Vendor Pop3 and ClipOnly2 now and Pressure4 and ButterComp2 later, as one new effect? Or add them to Comp as characters? Or leave them out? *Recommended: one new effect, working name Squash, with types Snap (after Pop3), Mu (after Pressure4) and Split (after ButterComp2). ClipOnly2 becomes the Limiter's Round mode. The names follow the 2026-10-02 naming rule, and Airwindows is credited in the docs.*
10. **Test oracles.** May permissive upstream code be built in a desktop-only test target, as reference renders? That means the Airwindows originals, DaisySP's ladder, Open303 and the MoogLadders Improved model. *Recommended: yes, for desktop tests only, never linked into an engine or the simulator, each under `third_party/` with its licence. The research lanes built nothing.*
11. **Side-chain order.** *Recommended: a matrix route to Threshold now; the DUCK input next; the audio key once there are several sound units. Drop docs/16's Duck module.*
12. **Name of the rack filter kind.** *Recommended: Resonator (abbreviation RES), since "Filter" is the audio effect.*
13. **Integer fallback.** *Recommended: write none before the FPU probe. The fm1-nes-style Q12 SVF stays a design on paper.*
14. **New Filter types.** *Recommended: none before the dev kit. Then OTA Ladder first, and the Diode's feedback high-pass as an option. Hard-clipping and inverter SVFs (Polivoks and Wasp style) come later, named after their circuits.*
15. **Telling Felucca's authors about the FPU.** *Recommended: not until the dev kit shows the FPU runs on AC791N silicon. Then put a draft in notes/upstream-candidates.md and send it only with your sign-off.* The same goes for the contradiction in Faust `compressors.lib`'s licence header: a draft, sent only with your sign-off.
16. **docs/01's audio path.** Felucca's HAL drives ALNK0 I2S to an external codec, but docs/01 and CLAUDE.md say internal DAC. *Recommended: check the PCB photos (notes/2026-09-29) and, if confirmed, correct docs/01 in its own small PR.* It also affects the output ceiling.

## 8. Sources

### This repository [verified]

- **main `3596d95`** (PR #38 merged 2026-10-05):
  - `engines/src/fx_filter.cc`, `fx_drive.cc`, `fx_comp.cc`, `fx_limit.cc`;
  - `engines/include/fm1_comp.h`, `fm1_mix_limiter.h`, `fm1_engine.h`;
  - `engines/README.md`;
  - `sim/web/src/fm1_app.c` (`step_of`);
  - `mi_macro.cc`, `mi_shapes.cc`, `mi_sixop.cc`, `mi_macro_heavy.cc`.
- **Branches, read only:**
  - @mod-core `e00adea` (`fm1_mod.h`, `mod_core.c`);
  - @mod-kinds `2d337cc`;
  - @multi-sound `3ce8a40` (docs/15 §3.16);
  - the per-note work in scratch/wt-pv (uncommitted).
- **Docs and notes:** docs/14, docs/15, docs/16; notes/2026-10-02-delay-reverb-eq-gates-options.md; notes/2026-10-02-jieli-compile-check.md §5.

### Local clones

- **Mutable** [verified]:
  - `reference/mi-eurorack` `08460a69a7e1`: MIT for the STM32 code, per the README. Read: plaits, rings, elements, warps, clouds, streams, braids, peaks.
  - `reference/mi-stmlib` `e3bd7c9cc00e`: MIT. Read: `dsp/filter.h`, `dsp.h`, `limiter.h`.
- `reference/Felucca` `727f272015da`: GPL-3.0-only [verified].
- `reference/sloop-fm1` `f2b44c219b8a`: GPL-3.0-only [verified].
- `reference/fm1-nes` `870f3054869c`: Apache-2.0 [verified].
- `reference/ac79-sdk` `e30b1ee375d1`: the repository is Apache-2.0; the `.a` libraries are closed [verified].

### Filters, upstream

**Usable:**
- Open303 `313bf0d9ade7`: MIT.
- DaisySP `2c72eaf9eac5`: MIT.
- DaisySP-LGPL `c89d380c6262`: LGPL-2.1.
- Teensy Audio `3039be2773e8`: an MIT-style notice in each file.
- MoogLadders `a968ec6ddfe1`: licence per model (Unlicense, ISC, LGPL, educational use).
- Faust libraries `bf9f71af2f6`: licence per function (STK-4.3, MIT, ISC, GPL-3.0-only); the file header is LGPL-2.1+ with an exception.
- HIIR (unevens fork) `4589fed`: WTFPL.
- signalsmith dsp `4f62b0a8783c`: MIT.
- klattsch `63dc2c6`: MIT.
- STK `6aacd357d762`: MIT-style.
- Vult `cc56038e06ae`: MIT.
- Pure Data `f3497d41dd28`: BSD.
- FunDSP `559584043aa3`: MIT or Apache-2.0, but its Moog coefficients come from musicdsp.
- Airwindows `e718c9bcfcdd`: MIT.

**Reference only:**
- Vital `636ca0ef517a`, sst-filters `343169683176`, VCV Fundamental `10dd0160c664`;
- Befaco `bf03788cf116`, Bogaudio `656eaae458e0`;
- chowdsp_utils `e97b826ef3de`, and chowdsp_wdf `43bcd295e840` (BSD-3);
- Odin 2 `265e9e227581`, OB-Xd `0c7c73708e0e`, SuperCollider `d81d67f8eeb2`;
- JUCE `be29c81492b6`, Csound `95ce8ada3c02`, Soundpipe `3efb43bdabd0`, musicdsp `d7c8525c9b3a`;
- Vult Modules `3cc9a46a06ea`, shruthi-1 `56bfe78a27cd`;
- schwung-hera `255be0655d88`, schwung-moog `fd11c89902b2`, RaffoSynth `e2731c9b2597`.

### Dynamics, upstream

**Usable:**
- Airwindows `e718c9bcfcdd736deeddb08bffe6bce2aa8e0eea`: MIT.
- Signalsmith basics `369e906e0376` and dsp `4f62b0a8783c`: MIT.
- DaisySP and DaisySP-LGPL, as above.
- faustlibraries `bf9f71af2f66`.
- Cycfi Q `73e6eeee9290`: MIT.
- KlonCentaur `f3bb633a593b`: BSD-3; its `omega.h` is MIT.
- schwung-busdriver `36b6788de7eb`, schwung-gate `afdd5c2bd634`, schwung-ducker `0033e4ce1d23`, schwung-tapescam `65bdfeeda17b`: MIT.
- CVCHothouse `fd0fe1e4b43e`.
- schwung `70c41718ce18` (the module catalogue).
- Tympan_Library `7ea89f4c5f7b`: MIT.
- OpenAudio_ArduinoLibrary `1dbecf11ca7d`: no root LICENSE.

**Reference only:**
- chowdsp_utils `e97b826ef3de` (GPLv3 modules);
- AnalogTapeModel `604372e4ffd9` (GPL-3);
- guitarix `666b564bb8a7` (GPL-2+);
- x42 dpl.lv2 `8bcd25deaf67` (GPL-3+);
- Calf `ecbbb2d68a50` (LGPL-2.1);
- rkrlv2 `0e6d6e052ed2` (GPL-2);
- Soundpipe `3efb43bdabd0`;
- schwung-ottx `8035c5e` (GPL-3);
- super-boom-move `8fb18dc` and schwung-pushnpull `8031c94` (no licence).

### Papers and notes

Implement from the equations; do not vendor these.
- Zavalishin, *The Art of VA Filter Design* rev 2.1.2 (2020). Read from discodsp.net's mirror; NI's own URL returned 404 on 2026-10-05 [verified].
- Cytomic's technical papers, cytomic.com/technical-papers [reported: public domain].
- Papers by citation:
  - Huovilainen, DAFx-04; Välimäki and Huovilainen, CMJ 2006; D'Angelo and Välimäki, ICASSP 2013 [citations verified in code headers];
  - Wise, DAFx-06; Parker and D'Angelo, DAFx-13;
  - Koper et al., DAFx-22 [read];
  - Werner and McClellan, DAFx-20 [unread];
  - Vicanek, 2016; Collin, on the ARP 2500;
  - Pirkle, application notes AN-4 to AN-7 [not fetched].
- Signalsmith's limiter article, 2022 [read].
- Mystran's and Voipio's KVR forum posts: no licence, ideas only.
