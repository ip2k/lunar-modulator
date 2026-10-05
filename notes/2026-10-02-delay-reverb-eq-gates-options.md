# Delay, reverb, EQ, saturation and gates: options (2026-10-02)

**Scope.** The owner asked for research on a second group of effects:
- saturation, delay, reverb and EQ;
- a DJ-style tilt filter, "for the master bus in particular";
- low-pass, high-pass and band-pass filters;
- gates that can be triggered, like a Drawmer DS201;
- above all, a trigger input that is patched separately from the audio input, on the gate and on the compressors (side-chaining).

**Companion note.** notes/2026-10-02-filters-dynamics-options.md is being written in parallel. It covers the classic filter designs, compressors, limiters and overdrives, and this note does not repeat them. This note covers the rest:
- delays and reverbs;
- master EQ and DJ filters;
- bus saturation;
- the gate;
- the key (side-chain) design that the gate and the Comp share.

**What already exists** [verified: engines/README.md, engines/src/registry.cc, main `a121f18`]:
- The effects are Plate (Rings' reverb), PSX Verb (Schwung), Diffuse and Ensemble (Plaits), Crush, Fold and Echo.
- The host limiter `fm1_mix_limiter` runs after the effects.
- Both hosts have one sound unit and a short effect chain. `render.cc` runs a list of effects (line 560). `fm1_app.c` runs the units after the sound (lines 693–695). docs/15 O10 still says "one shared sound unit".
- No host gives an effect a tempo, a reset call or a second (key) input. `fm1_host_t` holds only the API version, the sample rate and the largest block.

**Being built on other branches.** These worktrees are uncommitted at `a121f18`. I only read them [verified: scratch/wt-fx-*, 2026-10-02].
- **Filter:** seven types, with its own zero-delay SVF that has a nonlinear energy term.
- **Drive:** Soft, Tube, Diode, Fuzz and Tape curves, first-order anti-aliasing, and a Tone tilt about 800 Hz.
- **Comp:** feed-forward, with Peak, RMS, Glue and Punch characters, a libm-free `fx_comp_math.h`, and `fm1_comp_reduction_db()`.
- **Limiter.**

**How the candidates were checked.**
- Three lanes did the research:
  1. delay and reverb;
  2. EQ, the DJ and tilt filters, and saturation;
  3. gates and side-chain.
- They read through the GitHub API, raw files and the local clones `reference/mi-eurorack` (`08460a6`) and `reference/mi-stmlib` (`e3bd7c9`). Every source has a pinned commit (§11).
- Nothing third-party was built or run, and the repo was not edited. Lane 2 checked formulas with its own numpy re-implementations, kept in the scratchpad only.
- I re-checked the repo-local facts myself: the API header, instance sizes, docs/16 and docs/15 lines, the four effect worktrees, and libm use. I also evaluated stmlib's two tan polynomials (§4.1).

**Marks.**
- [verified]: read or computed at the pinned commit in this run.
- [reported]: a manual, README, licence field or second-hand source says so. Not re-checked.
- [inferred]: our estimate.

**CPU.** Nothing here is measured on pi32v2. Figures use two bases:
- "× Plate" counts operations against Plate, which measured 0.87 µs per 64-frame block on an M1 Max. Plate is probably 3–5 % of one 240 MHz core [inferred].
- "% of a core" counts flops at an optimistic 1 flop per cycle.

One block is 64 frames: 1.451 ms, or about 348,000 cycles at 240 MHz. The AC79 dev kit decides (docs/14).

## Contents

1. Short answer
2. Delays
3. Reverbs
4. EQ, DJ filter, tilt and isolator
5. The master-bus set
6. Saturation: Master Sat and the Drive effect
7. Gates (DS201-style) and side-chain
8. Budgets
9. Staged plan
10. Owner decisions
11. Sources

## 1. Short answer

| Need | Pick | Code | Licence | Why |
| --- | --- | --- | --- | --- |
| Gate | **Gate**: Threshold, Attack, Hold, Decay, Range, Return (hysteresis), a Duck mode, key filters with Listen, Lockout (stops retriggers) and optional 0–5 ms look-ahead. Controls follow the Drawmer DS201 and DS301 manuals | ours, 300–400 lines | MIT | Nothing needs vendoring. The manuals give the behaviour [reported] |
| Side-chain, on the Gate **and** the Comp | Three trigger inputs for each. (a) An **audio key**: itself, another sound before or after its inserts, or the master input, through key HP and LP filters. (b) A **trigger** from the modulation matrix: a sequencer track gate, Divide, Burst or an LFO. (c) **Gain reduction and gate state** as matrix sources. All of it comes from one optional API struct | ours | MIT | The key is an optional second, read-only buffer, and NULL means "key from yourself", as CLAP and LV2 do it [verified] |
| Master tone | **Tilt** (one knob around a pivot) and **DJ Filter** (one knob: low-pass to the left, high-pass to the right, a dead zone, resonance) | ours, on vendored `stmlib::Svf` and a first-order shelf | Cytomic's SVF maths is public domain; stmlib is MIT | The cheapest effects in the set. They sweep without zipper noise and pass the signal bit-exact at their defaults |
| Kill EQ | **Isolator**: 3 bands, Linkwitz-Riley crossovers | ours | none | Flat when summed, deep kills [verified: lane 2 numerics] |
| EQ | **EQ**: low shelf, bell and high shelf on the SVF | ours | Cytomic, public domain | Can be modulated. At 0 dB it is bit-exact |
| LP/HP/BP | Use the multimode **Filter** (companion note). Add 12/24 dB slopes, exact bypass at the open end, and a flat-top Band mode | none new | none | Avoids a second filter effect |
| Bus saturation | **Master Sat**: band-limited odd polynomial, Bass protect, Clean highs, Glue | ours; constants after Airwindows | MIT | Aliasing about −126 dB at moderate drive [verified: lane 2 numerics] |
| Reverb | **Plate Freeze**, **Room** (port of the Clouds reverb), **Hall** (our own 8-line FDN), then **Classic** (our own int16 Freeverb) and **Shimmer** | Mutable (port), ours | MIT, public domain | 32–72 KB each, no libm in the loop |
| Delay | **Tape** (3 heads), **Taps** (tempo multi-tap), **Smear**, **Repeat** (reverse, tape stop, stutter, hold), **Pitch** (port of the Clouds shifter), and Sync and Duck on Echo | ours; Mutable (port) | MIT | Need tempo and reset from the host |
| Later | Clouds granular and looper; JPverb; Greyhole | port, or write from the Faust text | MIT | Each waits on a CPU measurement or a provenance check |

**Licences.** Every pick is MIT, public domain, or our own code. Each is fine in the public simulator and in a shareable FM-1 binary. No GPL or LGPL code is needed, so nothing goes behind `FM1_GPL_MODS` (§11).

**Three facts decide most of the rest:**
- **RAM.** One Plate or one Echo is 64 KiB of the 387,924-byte gap [verified: engines/README.md]. Once there are several sound units, reverbs and delays should be shared send effects, not inserts on every unit (§8).
- **Four host additions.** The host has no master chain, no tempo or reset for effects, and no key input. Each is small (§7.4, §9).
- **Units.** Audio side-chain between sounds (a kick ducking a pad) needs the 4-unit host the owner described, which docs/15 has not written down yet. With one unit, these work today: Self keys, keys from the sound before its effects (gated reverb), and ducking triggered by the matrix.

## 2. Delays

### 2.1 What Echo already does

[verified: engines/README.md "Echo"]
- A stereo ping-pong delay with a 16-bit line of 16,384 cells per side: 65,728 bytes in all.
- Up to 371 ms runs at the host rate. Beyond that, the line's clock slows down as a bucket-brigade delay's does, up to 1,000 ms, with darker repeats.
- Wow comes from a seeded random walk. Tone is a low-pass inside the loop.
- It costs about 2.5× Plate on the desktop.
- "Not yet": tempo sync and a reset call. Both wait on the host. Every option below needs those same two host features.

### 2.2 Options

| Working name | What | Basis and licence | RAM | CPU [inferred] | Verdict |
| --- | --- | --- | --- | --- | --- |
| **Echo: Sync and Duck** | A Sync enum (Free, 1/1 to 1/16T, dotted, triplet). Duck lowers the wet level against the input's own envelope, a self-key with no key bus | ours | none | +2 % of Echo | Do first, once tempo exists |
| **Tape** | Three read heads at 1×, 2× and 3× spacing, plus a head-mode selector. Tape speed changes the read speed, so pitch bends. Flutter from a random walk keyed to the level, a band-pass in the regeneration path, saturation | Ours. Head spacing from RE-201 documentation [reported]. Ideas from Airwindows TapeDelay2 and Flutter2 (MIT, `d22a25b`) [verified]. No code copied | (a) Reuse Echo's 64 KiB line and its slowing clock: no new RAM, darker long repeats. (b) Its own host-rate line: 53 KB mono for 0.6 s, 106 KB stereo | about 3× Plate | Write our own, as a sibling of Echo that shares Echo's line code. Try (a) first |
| **Taps** | 4–8 taps set in beats, each with level, pan and filter; dotted and triplet divisions; ping-pong | Ours. The division list is a convention. Airwindows PurestEcho (MIT); schwung-performance-fx (MIT, `914d9ee`) [verified] | 88 KB per second, mono int16. 117 KB for 1.33 s (a half note at 90 BPM) | about 1× Plate with 8 taps | Write our own after tempo |
| **Smear** | Echo's loop with an 8-all-pass diffuser inside the feedback path: washes that build up | Clouds `diffuser.h` (MIT, `08460a6`) [verified]; Greyhole as the design reference | Echo plus 8 KB | about 1.5× Echo | Write our own |
| **Repeat** | Reverse (two heads, 4x(1−x) window), tape stop (read speed ramps to zero), beat repeat, stutter and hold, all on one capture buffer. Tape stop also works as a master performance move | Faust `misceffects.lib` reverseEchoN, tapeStop (STK-4.3, `9c42142`); Performance FX DSP (MIT, `914d9ee`) [verified] | 88 KB per second, mono int16 | about 0.3× Plate | Write our own, about 20 lines per mode |
| **Pitch** | A stereo delay-line pitch shifter: two taps with a triangle crossfade, a 128–2,047-sample window. Detune and octaver. Also the core of Shimmer | Port Clouds `pitch_shifter.h` (MIT, `08460a6`) [verified] | 8 KB | about 0.3× Plate | **Port, header-only** |
| Analog mode on Echo | An NE570-style compressor and expander around the line, plus clock-noise bleed | Ideas from jpcima BBD (BSL-1.0, `580c89b`), ChowDSP BBDDelay (BSD-3, `eb21974`) and Patina (MIT, `8ad9e70`) [verified] | none | about +0.5× Plate | Optional, later |
| Grain and looper | Clouds' granular mode and its looping delay (freeze, tap-tempo trigger) | Port (MIT, `08460a6`) [verified] | 150 KB lean, 80 KB lo-fi | 55–90 % of a core at full density | Later, behind a dev-kit measurement (§3.3) |
| Greyhole | A diffused feedback delay | Faust `reverbs.lib` header says MIT, `9c42142` [verified]. It mirrors a SuperCollider UGen (GPL-3), not re-checked | about 100 KB at 0.5 s | 4–5× Plate | Second wave, after a provenance check |

### 2.3 Rules for every delay

These come from Echo's notes and the lanes:
- **Storage.** Delay words are int16, or 12-bit as in FxEngine. Float lines double the RAM. The store truncates towards zero, so silence decays to exact zeros, as in Echo.
- **Stable interpolation.** Interpolation inside a loop stays linear, a convex combination, so feedback cannot grow.
- **No libm in the sample loop.**
  - LFOs use a recursive oscillator or a table. stmlib's CosineOscillator calls `cosf` only at init.
  - The random walk uses the project's seeded PRNG.
  - Airwindows' `sin()` vibrato and `frexpf`/`pow` dither do not come along.
- **Tempo sync.** Delay = 60 / BPM × the note length. Dotted is ×1.5 and triplet ×2/3. A tempo change glides or crossfades over 50–100 ms, so repeats bend like tape and do not click.
- **One time buffer at a time.** Only one time-buffer effect is active per chain: Echo, Tape, Taps, Smear, Repeat or the looper. Each keeps its own `instance_size`, so this "time arena" is a budget rule (§8), not a new mechanism [inferred].
- **Input guard.** Every effect keeps `mi_fx.cc`'s input guard (NaN to 0, clamp ±16). Mix 0 stays a bit-exact bypass.

### 2.4 Not ported

- **Space Echo emulations, all copyleft:** dusk-audio, dm-SpaceEcho, doobie, JankyTapeEcho and RE-Tape-Echo are GPL-3.0 [verified: GitHub licence fields]. Do not read their code while writing ours.
- **cyrusasfa/TapeDelay** (`c9ba1aa`) has no licence [verified]. So schwung-space-delay's own MIT label cannot clean the engine its source says it is "based on" (`aae4c5e`) [verified]. Ideas only.
- **Airwindows delays:** TapeDelay, TapeDelay2 and PurestEcho (MIT). They use doubles, `sin` and dither per sample, and 0.35–0.7 MB of lines. Ideas only.
- **DaisySP's pitch shifter** (MIT, `2c72eaf`): 128 KB and two `sinf` per sample. The Clouds shifter does the job in 8 KB.

## 3. Reverbs

### 3.1 What exists

Instance sizes on 32-bit, from engines/README.md [verified]:

| Effect | Bytes |
| --- | --- |
| Plate (Rings' reverb, 32,768 16-bit words) | 65,632 |
| PSX Verb (a fixed 128 KB work area) | 134,208 |
| Diffuse | 18,848 |
| Ensemble | 4,704 |

### 3.2 Options

| Working name | What | Basis and licence | RAM | CPU [inferred] | Verdict |
| --- | --- | --- | --- | --- | --- |
| **Plate Freeze** | Infinite hold: time 1.0, input gain 0, low-pass 1.0 | Elements' recipe, `elements/dsp/part.cc` 236–250 (MIT, `08460a6`) [verified] | none | none | Add a switch to Plate |
| **Room** | The same Griesinger/Dattorro loop as Plate but smaller: a 16,384-word 12-bit buffer, longest loop 108 ms against Plate's 143 ms. Plus Clouds' stereo Diffuser | Port `clouds/dsp/fx/reverb.h` and `diffuser.h` unmodified, header-only, with `mi_fx.cc`'s rate compensation (MIT, `08460a6`) [verified] | 32 KB, plus 8 KB for the Diffuser | about 1× Plate | **Port.** Half Plate's RAM. Noisier, being 12-bit [inferred] |
| **Hall** | An 8-line Householder FDN: mutually prime delays, a shelving damper per line, a seeded random-walk modulation per line, an input diffuser (Clouds' all-passes), predelay | Ours. Structure from schwung-work's "Voidspace" (MIT, `c88ec15`; the README's clean-room claim is [reported]), Signalsmith basics (MIT, `369e906`), Jot | 32–64 KB int16 | about 1× Plate | **Write our own**, about 60 lines in the core. The best new reverb |
| **Classic** | Freeverb: 8 low-pass combs and 4 all-passes per side, tuned for 44.1 kHz (ours is within 0.04 %), with a freeze. Bright and metallic, unlike Plate | Ours, in int16. The original header says "This code is public domain", Jezar at Dreampoint, read in ML_modules `05ac273` [verified] | 51 KB | about 2× Plate | Write our own, about 100 lines. Bit-exact by construction |
| **Shimmer** | The Pitch shifter (+12 or +7 st) inside Plate's feedback, at ≤0.5 gain, with a soft clip | Ours, on Plate and the Clouds shifter (MIT) | 72 KB | about 1.3× Plate | Write our own, as a Plate mode or its own effect |
| Plate-D | Dattorro's seven output taps per channel, for a denser stereo image | el-visio/dattorro-verb tap table (MIT, `41e976a`) [verified] | none | +0.5× Plate | Optional |
| Tiny | JCRev: 3 all-passes and 4 combs | STK `6aacd35` (STK licence, MIT text plus a request) [verified] | 14 KB | about 0.9× Plate | Only if a tiny slot is wanted |
| JPverb | A lush, chorused, Lexicon-style reverb with a 3-band decay | Faust `reverbs.lib` header says MIT, `9c42142` [verified]. Its SuperCollider lineage is not re-checked | 49 KB at size 1, 88 KB at size 3 | 5–6× Plate (15–30 % of a core) | Second wave: check provenance, measure CPU |

### 3.3 Reference only, and why

| Source | Licence | Why not ported |
| --- | --- | --- |
| CloudSeed / CloudSeedCore | MIT, `deb21de` [verified] | Buffers sized for 192 kHz: 67 MB as written. 15–40× Plate. Borrow the ideas: per-line post-diffusion and seeded L/R decorrelation. Its README asks not to confuse the name |
| Airwindows reverbs: Galactic, Verbity, MatrixVerb, the k-series | MIT, `d22a25b` [verified] | Double precision; `frexpf`, `pow` and `sin` per sample [verified]; 0.25–1 MB. Their Householder banks fold into Hall. Running the late field at a lower rate (Airwindows' "derez") is an idea worth keeping |
| ReverbSc (DaisySP-LGPL `c89d380`, Soundpipe revsc `3efb43b`) | LGPL-2.1 [verified]. Soundpipe's file says it was extracted from Csound's reverbsc [verified], so the repo's MIT does not clean it | Hall rebuilds the same idea from scratch. Do not copy its seed table |
| Zita-Rev1 (Faust `zita_rev*`) | The Faust function is headed STK-4.3 [verified]. The original is GPL-2.0 [reported] | Provenance unresolved |
| Faust `vital_rev`, `kb_rom_rev1`; `springreverb` | GPL-3.0-only; no licence [verified] | Never |
| Signalsmith `reverb-example-code` (`2798498`) | No licence [verified] | Ideas only. The MIT `basics` library is fine as a reference |
| Teensy Audio Freeverb and JCRev (`3039be2`) | MIT-style, plus a funding notice to keep [verified] | Uses ARM DSP intrinsics that pi32v2 lacks. Reference for int16 scaling only |
| Valhalla (blog, AES 2015 slides) | No code; copyrighted text | Ideas only. Never use their algorithm names |
| Valley Plateau, MVerb, Dragonfly, Freeverb3 | GPL [reported, not fetched] | Not read |

**Gated reverb** is Plate followed by Gate, with the Gate keyed from the sound (§7.8).

## 4. EQ, DJ filter, tilt and isolator

### 4.1 One linear kernel: the vendored stmlib SVF

- **Same filter as Cytomic's.** `stmlib::Svf` is the trapezoidal (Cytomic/Simper) state-variable filter. Its band-pass and low-pass outputs match Simper's to about 1e-15 [verified: lane 2 numerics].
- **No new kernel.** A bell or a shelf is `out = m0·in + m1·bp + m2·lp` on one SVF update. `set_g_r()` takes g directly, so a knob law can skip `tan` [verified: filter.h].
- **Why it modulates cleanly.** The two states are integrator charges, so new coefficients change the filter's future, not its stored energy. Direct-form biquads hold history that is wrong for new coefficients [reported: Cytomic; Airwindows Biquad2's own note].
- **Shared helpers, separate resonant kernel.** The Filter in progress has its own zero-delay SVF with a nonlinear energy term [verified: wt-fx-filter, uncommitted]. Keep that for resonant sounds. The master and key filters here are linear, so they use `stmlib::Svf`. A small shared header holds:
  - the bell and shelf mix;
  - the g-space knob law;
  - the coefficient tables.
  This settles lane 2's "one SVF header" against what the Filter branch already does [inferred].
- **No libm, even at control rate.**
  - The browser's parity table shows Fold off by 1 LSB under glibc, and Fold calls `exp2f` and `tanf` at control rate [verified: sim/web/README.md "Parity", fx_fold.cc].
  - The matrix will write parameters every 32 frames.
  - So new effects use the libm-free `CompLog2` and `CompExp2` from the Comp branch, promoted to a shared header. They give the same bits under Apple clang, GCC and Emscripten [reported: header comment, wt-fx-comp]. They also use tables.
- **tan accuracy at 44,118 Hz.** The error of stmlib's two polynomials against the exact value [verified: evaluated here]:

  | Frequency | FAST | ACCURATE |
  | --- | --- | --- |
  | 8 kHz | +0.06 % | −0.02 % |
  | 12 kHz | −0.68 % | −0.46 % |
  | 16 kHz | −9.2 % | −4.7 % |
  | 20 kHz | −49 % | −36 % |

  Use ACCURATE up to about 12 kHz (key filters, EQ). Use the g-space law or an offline table above that (precedent: `engines/mod/gen_tables.py`).

### 4.2 Tilt (first priority)

- **Filter.** One first-order pole/zero pair, `out = T·x − (T − 1/T)·LP1(x)`. The gain is 1/T at DC and T at high frequencies, and exactly 0 dB at the pivot. LP1 is a trapezoidal one-pole with `g = T·g_pivot`, which is the exact bilinear transform prewarped at the pivot. So turning Tilt needs no `tan` [verified: lane 2 numerics].
- **Response.** At 1 kHz and ±6 dB: −5.98 dB at 30 Hz, 0.00 at 1 kHz, +5.99 at 18 kHz [verified: lane 2 numerics]. The slope through the pivot is within 0.8 dB of a straight line from 200 Hz to 5 kHz. Two staggered sections bring that to 0.57 dB, and that only matters past about ±6 dB.
- **Page:** Tilt (±6 or ±9 dB per side), Pivot (200 Hz–5 kHz, log, default 1 kHz), Sections (1 or 2, NOLOCK), Level. Tilt 0 is bit-exact. The best modulation target is Tilt.
- **Cost:** about 7 flops per channel, about 0.5 % of a core, 4 bytes of state per channel [inferred].
- **Ideas from:** Airwindows ToneSlant (MIT) and Faust `fi.spectral_tilt` (STK-4.3). No code is copied.
- **Drive's Tone.** The Drive branch's Tone is a tilt about 800 Hz [verified: wt-fx-drive comment]. Drive and Tilt should share this code.

### 4.3 DJ Filter (first priority)

- **Page 1:** Sweep −1..1 (default 0), Reso, Slope 12/24 dB (NOLOCK), Mix.
- **Page 2:** Dead zone (default about 0.05) and Range.
- **Centre.** In the dead zone the filter does not run, and the output is the input bit for bit.
- **Knob law in g-space, no `tan`.** With u = (|Sweep| − dead) / (1 − dead), `g = g_a·(g_b/g_a)^u`, using one table lookup per control tick.
  - The LP side runs from g 7.0 (20 kHz) down to about 0.0043 (60–80 Hz).
  - The HP side runs from 0.0014 (20 Hz) up to about 0.64 (8 kHz).
  - The sweep is exponential in frequency below about 7 kHz [verified: arithmetic].
- **Resonance** follows `Q = 0.707 + Reso·(Qmax − 0.707)·4u(1 − u)`. The open ends never whistle. Qmax is 8–10 [inferred]. At 24 dB a second SVF at Q 0.707 follows, and only the first resonates.
- **Entering a side.** Crossfade dry to wet over the first 8 % of u, and set the states to the input's DC steady state. Switching one SVF between its LP and HP taps would click, and Airwindows Isolator3 notes the same [verified].
- **Block-size independence.** Smooth Sweep with a 10 ms one-pole. Update coefficients on a 16-frame grid tied to an instance frame counter, or glide per sample as Fold does. Either way the output does not depend on the host block size (the tests use 7, 12 and 64).
- **Cost:** 1–1.5 % of a core [inferred].
- **Not a Filter mode.** Keep it as its own effect: its labels and its exact-bypass centre differ from the Filter's. Mixxx's filter (GPL-2, `75acec8`) was read for ideas only [verified].

### 4.4 Isolator (second priority)

- **Bands.** Three bands from Linkwitz-Riley crossovers, as in Faust's `crossover3LR4` (STK-4.3, `9c42142`):
  - low = AP(f2)(LR4-LP(f1)(x));
  - mid = LR4-LP(f2)(LR4-HP(f1)(x));
  - high = LR4-HP(f2)(LR4-HP(f1)(x)).

  That is 7 SVF updates per channel.
- **Measured** at 250 Hz and 2.5 kHz [verified: lane 2 numerics]:
  - The bands sum flat to 0.0 dB.
  - Kill low gives −64 dB at 40 Hz. Kill high gives −80 dB at 15 kHz.
  - Kill mid gives −30 dB at 600 Hz but only −19 dB at 1.5 kHz, because the mid band is three octaves wide.
- **Rejected:** the cheap subtractive bands (x − LP). Kill low reaches only −7 dB at 40 Hz [verified: lane 2 numerics].
- **Page 1:** Low, Mid, High (unity at 75 % of travel, +6 dB at the top, true zero at 0) and a Kill mask.
- **Page 2:** the two crossovers, 80–400 Hz and 1.5–5 kHz.
- **Defaults** are 250 Hz and 2.5 kHz. Mixxx starts at 246 Hz and 2,484 Hz [verified: its constants]. The Xone:92 is said to use 12 dB/oct [reported: retailer page].
- **Smoothing.** Band gains glide over 5 ms, so a kill does not click. Treat the crossovers as static.
- **Cost:** about 3.9 % of a core. The dearest item in the master set [inferred].

### 4.5 EQ (parametric)

- **Bands:** low shelf (Gain, Freq), bell (Gain, Freq, Q), high shelf (Gain, Freq).
- **Coefficients** come from Simper's formulas [verified: lane 2 against neodsp/simper-filter `8cb7d7f`, MIT or Apache-2.0]. A bell at +9 dB measures 9.00 dB. At 0 dB a bell is bit-exact, because m1 is exactly 0.
- **No libm.** `A = 10^(dB/40)` and `sqrt(A)` come from stmlib's `SemitonesToRatio` tables (vendored, MIT), at about 0.004 dB steps.
- **Cost:** about 2 % of a core [inferred].
- **The RBJ cookbook** (W3C Note, 2021-06-08) [verified] serves only as a test reference and for fixed filters. Its direct-form biquads must not be modulated.

### 4.6 LP, HP and BP for the master

Do not write another filter effect. Add four things to the multimode Filter (companion note):
- a 12/24 dB slope for LP and HP;
- exact bypass when LP is fully open or HP fully closed;
- the g-space knob law from §4.3;
- a Band mode: HP and LP in series with a Width control, a flat-top band. A telephone sound is HP 300 Hz with LP 3.4 kHz.

The key filters of the Gate and Comp are the same linear SVF pair (§7.6).

### 4.7 Width (optional, last)

- **What it does.** A one-pole high-pass on the side signal only: everything below a corner (20–300 Hz) becomes mono, plus a Width control (0–2). Exact bypass at the defaults.
- **Source:** after Airwindows Sidepass (MIT) [verified].
- **Cost:** about 0.2 % of a core.

### 4.8 Not used

- **The Airwindows EQ family** (Baxandall2, ToneSlant, Hull2, Capacitor2; MIT, `d22a25b`) [verified].
  - Its biquads step once per block.
  - It uses doubles.
  - It adds noise per sample (`fpd·1.18e-17`), which breaks silence-in, silence-out.
  - Ideas only.
- **Pafnuty** was on the shortlist as an EQ. It is a Chebyshev harmonic generator [verified: source and Airwindopedia]. It could be a later "Harmonics" effect, not part of the master set.

## 5. The master-bus set

**Today.** The host runs the sound, then its effects, then `fm1_mix_limiter` [verified: render.cc 550–565, fm1_app.c 686–695]. There is no master chain yet. Until there is one, Tilt and DJ Filter go in the last effect slot (FX2), which already acts as "master" for a one-unit app.

**Recommended order**, once a master chain exists [inferred: lane 2's order, with the performance slot added]:

```
units' sum + send returns (master-in)
  -> 1 Tone:  Tilt, or Isolator, or EQ
  -> 2 Master Sat (with Glue)
  -> 3 Comp, glue setting (companion note), keyable (section 7)
  -> 4 optional performance: Repeat, tape stop, or a Gate as a trance gate
  -> 5 DJ Filter
  -> 6 Limiter (companion note)
  -> fm1_mix_limiter (exists: the safety net)
```

**Why this order:**
- The Comp comes before the DJ Filter, so sweeps and resonance do not pump its detector.
- Repeat and the trance gate come before the DJ Filter, so a stutter can be swept.
- The limiters come last, to catch resonant peaks.
- The trance gate is a Gate whose Trig input comes from a sequencer track, from Divide, or from an LFO through the matrix (§7.3).

**Build priority:**
1. DJ Filter
2. Tilt
3. Master Sat
4. Isolator
5. Comp and Limiter (companion note)
6. EQ
7. Width
8. Console sum mode (deferred, §6)

**Pages.** Every master effect has an exact-bypass default and one best modulation target: Sweep, Tilt, Drive or a band gain.

**Cost.** Tilt, DJ Filter, Master Sat and Isolator together cost about 7.5 % of a core at 1 flop per cycle, about 10 % with the EQ. Double that until pi32v2 is measured. State is under 1 KB, with no delay lines [inferred].

## 6. Saturation: Master Sat and the Drive effect

### 6.1 The two compared

| | **Drive** (in progress, companion note) | **Master Sat** (proposed) |
| --- | --- | --- |
| Job | An insert that distorts: Soft, Tube, Diode, Fuzz, Tape; −12 to +36 dB | Gentle warmth on the bus: 0–18 dB, linear for small signals |
| Curves | C2 piecewise quintics with first-order anti-aliasing [verified: wt-fx-drive comment] | Odd polynomials to the 11th power: PurestSaturation or TapeHack2 constants, a C1 plateau at the clamp |
| Aliasing at 3 kHz, input peak 1.5 | — | −127 dB (PurestSat), −126 dB (TapeHack2), against −70 dB (stmlib SoftClip) and −66 dB (tanh) [verified: lane 2 numerics] |
| What it protects | A tilt Tone | It distorts only the band between a Bass-protect HP (20–300 Hz) and a Clean-highs LP (about 5–6 kHz): `y = x + wet·(f(band) − band)`. At peak 3.0 the alias falls from −22 to −47 dB [verified: lane 2 numerics] |
| Programme dependence | Auto gain | **Glue**: the overspill \|u\| − \|f(u)\| drives an envelope (2 ms attack, 100–300 ms release) that lowers the drive. Feed-forward, stereo-linked, no buffers |
| Bypass | Mix 0 | Mix 0, and linear near zero |
| Cost | companion note | about 1.5 % of a core, no libm, no memory [inferred] |

### 6.2 Recommendations

- **Master Sat** is its own small effect.
  - Page 1: Drive, Bass, Glue, Mix.
  - Page 2: Shape (PurestSat or TapeHack2), Asymmetry (an offset, with f(offset) subtracted, then a DC blocker), Clean highs, Level.
  - Licence: Airwindows' constants are MIT (`d22a25b`) [verified]. Keep the notice if the exact coefficient sets are copied, and record them in the licence inventory.
- **Tape colour stays in Drive.**
  - Drive already has a Tape type with 50 µs emphasis [verified: wt-fx-drive].
  - Lane 2's "Tape mode for Master Sat" was a stripped ToTape9: the TapeHack2 curve, a head-bump shelf and slew-gated smoothing. Hold it until the Drive's Tape has been heard on the bus.
  - Do not port ToTape9, IronOxide5 or ChowTape. ChowTape is GPL-3.0 (`604372e`) [verified].
- **Glue overlaps** the Comp's "Glue" character [verified: wt-fx-comp]. Share the envelope code, or let Master Sat call the Comp's smoother, so there are not two.
- **Console sum mode is deferred.** Airwindows Console6 (MIT) encodes each channel with `x(2 − |x|)` and decodes the sum with `1 − sqrt(1 − x)` [verified]. It only means something where several units are summed. Never use the Buss curve alone: it expands. Console5, 7 and 9 use `asin`, `sin` and `log1p` per sample: not those.
- **Compresaturator** (MIT) is where the Glue idea comes from. It is not ported: it carries `sin` per sample and 40 KB per channel.

## 7. Gates (DS201-style) and side-chain

### 7.1 The DS201 and DS301 as the spec

All [reported]: from the operator manuals, read in full by lane 3. Facts only, nothing copied.

- **DS201 controls:**
  - Threshold −54 dB to off. Attack 10 µs–1 s. Hold 2 ms–2 s. Decay 2 ms–4 s. Range 0 to −80 dB.
  - Key filters on the side-chain only: HP 25 Hz–4 kHz and LP 250 Hz–35 kHz.
  - Ext/Int key. Gate/Duck. Key Listen (the filtered key goes to the output).
  - Stereo Link, in which both channels follow channel 1's key.
- **DS201 behaviour:**
  - Once triggered, the attack always completes.
  - Hold starts when the key crosses the threshold.
  - Key LP filtering delays the trigger.
  - In Duck, Range is the level the music drops to.
  - Classic uses: gated reverb keyed from a drum, bass gated from the kick, key filters set to reject hi-hat spill.
- **What the DS301 adds:**
  - A key source switch, INT / EXT / MIDI. An audio key and a note trigger are alternatives on one gate.
  - It sends a MIDI note each time the audio opens the gate.
  - Retrig, 5 ms–5 s, which inhibits re-opening.
  - Key filters stated as 12 dB/oct. The ramp starts from the Range level.
- **Not in either manual:** hysteresis or look-ahead. The DS201's filter slope (12 dB/oct) is [inferred] from the DS301.

### 7.2 The Gate effect

| Page | Knob 1 | Knob 2 | Knob 3 | Knob 4 |
| --- | --- | --- | --- | --- |
| 1 | Thresh −80..0 dB (−40) | Attack 0.023–1,000 ms, log (0.5) | Hold 2–2,000 ms (50) | Decay 2–4,000 ms (150) |
| 2 | Range 0..−90 dB (−80; −90 reads "off") | Return 0–12 dB hysteresis (4) | Mode: Gate, Duck | Trig: Audio, Gate, Either |
| 3 (KEY) | Key: host-owned source, NOLOCK | Key HP 20 Hz–10 kHz (20 = out) | Key LP 200 Hz–20 kHz (20 k = out) | Listen: Off, Key |
| 4 | Lockout 0–5,000 ms (0) | Look 0–5 ms (0) | Link: Max, Sum, Left | — |

- **Ports.** Outputs OPEN (a gate), ENV (the gain, 0..1) and KEY (the key level, 0..1). One gate input, TRIG.
- **Credits string:** "controls after Drawmer DS201/DS301 manuals; algorithm ours".
- **Algorithm** (ours, MIT). Per sample and sequential, so any render split or block size gives the same output:
  - **Key level:** rectified into a peak envelope with instant attack and a 3–5 ms decay, which stops chatter at low frequencies.
  - **Schmitt trigger:** opens above Thresh, closes below Thresh − Return.
  - **States:** Closed, Attack, Open, Hold, Decay. A started attack completes. Hold reloads while the key is above threshold. Lockout ignores new rises for its time.
  - **Duck** inverts the gain.
  - **Ramps in dB:** "Decay 4 s" means 80 dB in 4 s, from the Range level. The conversion uses the shared libm-free exp2, skipped while the gain is steady.
  - **Look-ahead** delays the audio path only. The latency is constant and shown on the panel.
  - **Fastest attack** is one sample, 22.7 µs, against the DS201's 10 µs. On bass it clicks, as the manual warns.
  - **Guard:** NaN or huge key samples must not latch the hold counter.
- **Cost:** about 60 flops per sample with both key filters, 1.1 % of a core (2.2 % at 2 cycles per flop). About 30 flops with the filters out. RAM about 400 B, plus 1,768 B for 5 ms of look-ahead [inferred].
- **Later idea:** a "Fade" close mode after Airwindows Gatelope (MIT), which closes a band-pass instead of attenuating. Low priority.

### 7.3 Three trigger inputs, the same for the Gate and the Comp

```
 audio key (Self | Sound N pre | Sound N post | Master-in)
   -> guard -> link (Max/Sum/Left) -> key HP -> key LP -> level --+
                                                                 +--(Trig: Audio / Gate / Either)--> detector -> gain
 matrix gate (SEQ track, Divide, Burst, LFO via comparator) -----+                                                 |
 audio in -------------------------------------------------------------------------------------------------------> x --> audio out
 outs to the matrix: Gate OPEN, ENV, KEY;  Comp GR, KEY
```

1. **Audio key: the trigger input patched apart from the audio input.**
   - The effect picks its key source from a list the host builds:
     - Self;
     - S1–S4 pre (a sound unit before its inserts);
     - S1–S4 post (after its inserts);
     - Master-in (for master effects only);
     - later, USB.
   - Taps are pre-fader and pre-mute, so a muted kick still drives the pump (the "ghost kick").
   - This follows Ableton's model and Digitakt II's: the effect picks a source and a tap [reported].
   - The alternative is key buses with per-sound send levels, as on the Deluge (GPL-3, `62a516c`, design only) [verified licence]. It costs extra buffers and a second idea in the UI. Rejected for v1.
2. **Trigger from the modulation matrix.**
   - docs/16's GATE_DST is extended to effect slots. The Gate gets a TRIG input and the Comp a DUCK input.
   - Possible sources: sequencer track gates, KEY and NOTE gates, CLOCK, BEAT and BAR, Divide (Euclidean and trance rhythms), Burst (ratchets), and an LFO through the comparator.
   - Gate-to-gate cables keep their frame offsets. The host then splits only that effect at the edge frame and calls `gate_edge` between the pieces, so the edge is sample-accurate.
   - Order at one frame follows docs/16: falls, then the tick's `set_param` writes, then rises.
   - **A first version needs no API.** A `FM1_PARAM_INPUT` "Trig" parameter, with a comparator inside the effect (rise at 0.5, fall at 0.25), lands on tick frames: up to 0.725 ms of jitter. The INPUT flag exists and no engine uses it yet [verified: fm1_engine.h].
   - **Trig: Gate.** A high gate counts as "key above threshold", so Hold, Attack, Decay and Lockout all apply.
   - **Comp.** A high DUCK gate asks for a fixed Duck depth through the Comp's own attack and release. The applied reduction is the larger of the two, in dB.
3. **Gain reduction and gate state as sources.**
   - **Ports:** Gate OPEN, ENV and KEY; Comp GR (0..1 for 0–24 dB) and KEY.
   - **Ids:** docs/16 uses system sources 0–63 and module outputs 64–127, and keeps 0xFF for "none" [verified: docs/16 §2.4]. So effect outputs take 128 + 4 × FX slot + port [inferred].
   - **Timing.** While one of an effect's outputs is routed, the host splits that effect at tick frames, as docs/16's AUDIO_TAP rule does, and reads after each piece. That is at most one tick (32 frames, 0.725 ms) late, and the same at any block size.
   - **Uses:**
     - Comp GR ducks an Echo's feedback or a Plate's Mix.
     - Gate OPEN fires Segments or Burst.
     - Later, through docs/16's TO NOTES sink, Gate OPEN does the DS301's audio-to-note trick.
   - **The Comp branch is ready for this.** It already exposes `fm1_comp_reduction_db()` [verified: wt-fx-comp `include/fm1_comp.h`, uncommitted]. That becomes `out(GR)`.
   - **docs/16's Duck module** (Streams compressor, REDUCTION output) [verified: docs/16 line 701] becomes redundant for effects. Keep Follow.

### 7.4 API changes

One optional struct, appended as the last field of `fm1_engine_t` (`const fm1_fx_ext_t *fx; /* NULL = none */`):

```c
typedef struct fm1_fx_ext {
  uint32_t flags;      /* FM1_FX_KEY, FM1_FX_GATE_IN, FM1_FX_TRANSPORT */
  void (*render_key)(void *self, float *io_lr, const float *key_lr, uint32_t frames);
  const fm1_port_t *gate_in;  uint8_t n_gate_in;
  void (*gate_edge)(void *self, uint8_t port, uint8_t high);
  const fm1_port_t *outs;     uint8_t n_outs;
  float (*out)(const void *self, uint8_t port);
  void (*tempo)(void *self, float bpm);        /* delays: Sync; NULL if unused */
  void (*reset)(void *self, uint32_t why);     /* START, STOP, PRESET: drop tails */
} fm1_fx_ext_t;
```

**Rules for the key:**
- `key_lr` is stereo, read-only, valid for exactly `frames`, never aliases `io_lr`, and is never stored in the instance. Not storing it keeps 32-bit and 64-bit instance sizes equal.
- `render_key(self, io, NULL, n)` equals `render(self, io, n)` bit for bit.
- The key is guarded like the input.
- `out()` is read after the last render piece.

**Other additions:**
- `fm1_port_t` (name ≤5 characters, kind, unit) moves from docs/16's `fm1_mod.h` into `fm1_engine.h`, so modules and effects share it.
- **`FM1_PARAM_KEYSRC` (0x20):** an ENUM the host owns. It is never forwarded to `set_param`, it is always NOLOCK, the host supplies its names, and presets store it by uid.
- **`FM1_UNIT_DB` = 6.** Today's units are NONE, SEMI, MS, HZ, PCT and DEG [verified]. The Comp branch shows dB values with `FM1_UNIT_NONE` [verified].
- **Tempo and reset ride on the same struct.** They are Echo's two missing host features, and the same shape as docs/16's module `reset(why)` and its TRANSPORT flag [verified: docs/16 lines 232–237].
- **Shared libm-free maths:** the Comp's `CompLog2`/`CompExp2`, a dB ramp, and g tables, in one header used by Gate, Comp, Limiter, Master Sat, Tilt and DJ Filter. Without it, divergent copies appear.

**Rejected:**
- the key as extra interleaved channels, which breaks the stereo contract for every effect;
- a `set_key(pointer)` call, which stores a pointer and has to be re-set for each split piece;
- an envelope the host computes for the effect, which cannot gate on a 20 µs transient and duplicates the key filters.

**Version.** The struct changes layout. Both hosts require `api_version` to equal the macro (render.cc 127, fm1_app.c 191), and every engine in the tree uses the macro, 12 times in engines/src [verified]. So a bump to v3 is mechanical.
- Lane 3 argued for staying at v2, because aggregate initialisation zero-fills the new field.
- Both work in the tree. A bump is the safer signal for out-of-tree modules (the planned catalogue). Owner decision 6.

### 7.5 Block order rules for the host

One shared C99 chain host, like `fm1_seq_host.h`, used by `fm1-render` and `fm1_app.c`. Today they are two separate loops [verified: render.cc 560, fm1_app.c 693]. Per block:

1. The sequencer advances.
2. Each sound unit renders into its own 512 B buffer, split at its note events. Its PRE tap is copied only if some effect selects it.
3. The insert chains run in an order computed from key dependencies: Kahn's algorithm over at most 4 chains, recomputed on edit, ties broken by unit number. A unit's POST tap is its buffer once its chain is done.
4. The units are summed into master-in. Send effects (one reverb, one delay; §8) run on their send sums and return into master-in [inferred: send layer added here].
5. The master chain runs. Its keys can be Self, master-in or any unit tap.
6. `fm1_mix_limiter` runs last.

**Rules:**
- **No loops.** A key that would close a loop is not offered (v1).
- **Zero-latency taps.** Every tap has zero latency. Never read "the previous block": a one-block delay is N frames long, so the output would change with the host block size and fail the 1/7/64 identity test. If loops are ever wanted, read through a fixed 64-frame ring, 1 KiB per tap [inferred].
- **Splits.** Splits are per effect, at gate-edge or tick frames only, never for the whole chain.
- **Pre-fader taps.** Taps are pre-fader and pre-mute.

### 7.6 Key conditioning

**Order inside the effect:**
1. The key, or the effect's own input.
2. The guard.
3. Link.
4. Key HP, then key LP: two linear SVFs at Q 0.707, using ACCURATE `tan`.
5. The detector.

The filters bypass themselves at HP 20 Hz and LP 20 kHz. Listen sends the filtered key to both outputs, as the DS201 does.

**Link default: Max.** Lane 3 proposed Sum, a mono 0.5(L+R), which filters once and costs half. But:
- the Comp branch's detector is `max(|L|, |R|)` [verified: wt-fx-comp `fx_comp.cc` header];
- Sum cancels anti-phase content, which ping-pong and Ensemble produce.

So the default is Max for both effects, at about 28 extra flops when the filters are in. Sum and Left (the DS201's link) are the alternatives. Owner decision 3.

**Latencies** [verified: arithmetic]:
- 1 sample is 22.7 µs. One tick is 0.725 ms. One block is 1.451 ms.
- The 12 dB/oct key LP delays the trigger by about 28 µs at 8 kHz, 225 µs at 1 kHz and 0.9 ms at 250 Hz.

**Key = Auto** (optional): the effect's own input when the external key has been silent for 5 s. This is Streams' normalled key (MIT, `08460a6`) [verified].

### 7.7 What the Comp needs (send to its author before its uids freeze)

The Comp's pages 1–3 hold uids 1–10, with two knobs free on page 3 [verified: wt-fx-comp, uncommitted]. Uids never move, so append:
- **Page 3, spare knobs:** Trig (Key, Gate, Either) and Duck (0 to −30 dB, −12).
- **Page 4 (KEY):** Key, Key HP, Key LP, Listen.

**Detector.** It reads a `const float *key` that defaults to its own input, so `render` and `render_key(NULL)` share one code path.

**Auto Gain.** Ignore it while Key is not Self. The Comp's Auto Gain adds the curve's reduction at 0 dBFS [verified: its header], which would boost the signal while an external key is silent [inferred]. Ableton disables automatic makeup with an external key [reported].

**Cost.** The key path adds about 40 flops per sample with both filters, 0.7–1.5 % of a core [inferred].

### 7.8 With one sound unit (today) and with four

**Works with one unit:**
- **Gated reverb.** FX1 Plate, FX2 Gate, with Key set to the sound before its effects. The host needs one 512 B tap copy.
- **Trance gate.** A Gate with Trig set to Gate, driven by a sequencer track, Divide or an LFO.
- **Pumping from the sequencer.** A Comp whose DUCK input comes from a track gate. It ducks the whole unit, kick included.
- **Ducked echoes.** Echo's own Duck parameter (§2.2). A Comp after Echo would duck the dry signal too, because Echo's output includes it.

**Needs at least two units:** a kick ducking a pad from audio. docs/15 O10 still describes one shared unit, and in the simulator each extra unit is "a 512 KiB arena" [verified: docs/15 line 1758]. The 4-unit plan has to be written there before stage B7.

**Not yet:** a key from USB audio. The jacks are audio out and MIDI in [verified: docs/01]. USB enumerates audio [reported: docs/01]. Whether stock routes USB input to the mixer is unknown.

### 7.9 Prior art

| Source | What we take | Licence (commit) |
| --- | --- | --- |
| Mutable Streams `compressor.cc`, `envelope.cc` | A separate excite (key) input per channel; the normalled key; the Schmitt pair; exposed gain reduction; integer log and exp tables. Never `streams/ui.h` (GPL-3 include) | MIT (`08460a6`) [verified] |
| Signalsmith basics `dynamics.h`, dsp `envelopes.h` | An AUX detector input; look-ahead with PeakHold and BoxFilter; hysteresis. Rewrite without the doubles and per-sample `log10`/`pow` | MIT (`369e906`, `4f62b0a`) [verified] |
| Faust `misceffects.lib` gate_mono | Resetting the hold counter | STK-4.3 (`9c42142`) [verified] |
| Faust `compressors.lib` | The SC-filter, switch and signal design. **Trap:** the file header says LGPL-2.1+ with an exception, while 24 functions declare GPL-3.0-only | mixed [verified] |
| Airwindows Gatelope, SoftGate | A later "Fade" close mode | MIT (`d22a25b`) [verified] |
| DSPark NoiseGate | Adaptive hold (at least one signal period). Reference only: C++20, three months old | MIT (`4686009`) [verified] |
| MarkzP AudioEffectDynamics | Confirms the normalled key. Too slow for a gate (30 ms floor) | MIT notice in its headers (`093c4cf`) [verified] |
| DaisySP | Nothing: its LGPL compressor was removed in `c59a4dc`, and it has no gate. Older forks still carry the LGPL code | MIT (`2c72eaf`) [verified] |
| Deluge sidechain | Hits placed at their exact frame inside a block; per-sound hit strength. Design only | GPL-3.0 (`62a516c`) [verified] |
| CLAP audio-ports, LV2 isSideChain | The key is an optional non-main input, and the effect must work without it | MIT (`a47f6ba`), ISC [verified] |
| LSP, Calf, Zam, Open-X, Silentium gates | Licences only. Code not read | LGPL, GPL, AGPL [verified/reported] |

### 7.10 Tests (exit for the key stage)

1. `render_key(NULL)` equals `render` bit for bit, for Gate and Comp.
2. Block sizes 1, 7, 13 and 64, with a key from another unit and with sequencer gates, give identical WAVs. So do random split points around gate edges (fuzz).
3. Latency:
   - with Attack at one sample, the gate opens within 2 samples of the key crossing;
   - with Look = L, an impulse comes out exactly L samples late;
   - the key LP's delay matches the Butterworth group delay within a sample.
4. Listen output equals a Python reference of the filter pair.
5. NaN, infinities and huge key samples do not latch the hold counter. Instance memory filled with 0xA5 or 0xFF changes nothing.
6. Logged `gate_edge` frames equal the sequencer's event frames.
7. Planner:
   - an impossible key is never offered;
   - loops are refused;
   - a permuted unit order gives the same plan.
8. Matrix:
   - with no route there are no splits and no `gate_edge` calls;
   - GR and ENV read the same at block sizes 1, 7 and 64;
   - GATE_DST into an effect matches a hand-scripted run.
9. Parity: native and wasm agree byte for byte with `-ffp-contract=off`, including under glibc, and `nm` shows no libm in the new objects.
10. A key tap stays alive when its unit is muted.
11. ASan/UBSan. The `-m32` job prints the Gate and Comp sizes.
12. Uids and flags are pinned in `tests/fixtures/param-uids.json`. `fm1-render` gains `--fx-key self|noise|click:T|FILE`.

### 7.11 Flags found in the repo

- docs/16 line 356 lists the source "audio level (the previous block's peak)" [verified]. It depends on the host block size and would fail §2.7's identity test [inferred]. Read it through tick-aligned splits instead.
- docs/15 O10 still describes one shared sound unit [verified]. The 4-unit and master-bus plan is not written down.
- Lane 3 found the Comp worktree empty. By the time of this synthesis it held an uncommitted Comp [verified]. The advice in §7.7 is written against that version.
- Existing effects call `expf`, `exp2f`, `powf` and `tanf` at control rate [verified: fx_crush, fx_fold, fx_echo]. Fold already differs by 1 LSB under glibc [verified: sim/web/README.md]. New code should not add more.
- Lane 3's stage names K1–K4 clash with the knob names K1–K4. This note uses B1–B8.

## 8. Budgets

### 8.1 RAM per instance, against the 387,924-byte gap

Part of that gap is stock's heap (docs/11) [inferred].

| Effect | Bytes | Mark |
| --- | --- | --- |
| Plate / Echo (exist) | 65,632 / 65,728 | [verified] |
| PSX Verb (exists) | 134,208 | [verified] |
| Room / Hall / Classic / Shimmer | 32 KB (+8 KB Diffuser) / 32–64 KB / 51 KB / 72 KB | [inferred] |
| Pitch | 8 KB | [inferred] |
| Tape | 0 (on Echo's line) or 53–106 KB | [inferred] |
| Taps / Repeat | 88 KB per second, mono int16 | [inferred] |
| Clouds granular and looper | 80–150 KB lean; 184,192 B as shipped | [verified shipped figure; lean inferred] |
| Tilt, DJ Filter, Isolator, EQ, Master Sat, Width | under 1 KB of state together | [inferred] |
| Gate | about 400 B; 2.2 KB with 5 ms look-ahead | [inferred] |
| Key taps | 512 B each, only when selected; at most 2 KB | [inferred] |

### 8.2 Worked examples

- **Today, one unit.** Macro at 12 voices (18,864) + Plate (65,632) + Echo (65,728) = 150,224 B. Adding Gate and a tap makes about 153 KB [verified sizes; arithmetic].
- **Four units with sends** [inferred]:

  | Part | Size |
  | --- | --- |
  | 4 × Macro | 75 KB |
  | Light inserts, about 8 KB per unit | 32 KB |
  | One send reverb (Plate) | 64 KB |
  | One send delay (Echo) | 64 KB |
  | Master chain and taps | about 5 KB |
  | **Total** | **about 240 KB** |

  That leaves about 145 KB for the sequencer, the UI and stock's share.
  - A Plate insert on every unit instead adds 197 KB and does not fit.
  - Shapes at 12 voices (206 KB) does not fit in a 4-unit set at all.

### 8.3 CPU per instance

All [inferred]. "× Plate" with Plate taken as 3–5 % of a core. Percentages are flops at 1 per cycle: double them until measured.

| Effect | Estimate |
| --- | --- |
| Echo (exists) | 2.5× Plate (desktop ratio), so 7–12 % |
| Room, Hall | about 1× Plate |
| Classic | about 2× |
| Shimmer | about 1.3× |
| Tape | about 3× |
| Taps (8) | about 1× |
| Smear | about 1.5× Echo |
| Repeat, Pitch | about 0.3× each |
| JPverb | 5–6× (15–30 %) |
| Clouds granular at full density | 55–90 % (scaled from Mutable's 168 MHz Cortex-M4F sizing). Cap the grain count |
| Tilt / DJ Filter / Master Sat / EQ / Isolator / Width | 0.5 / 1–1.5 / 1.5 / 2 / 3.9 / 0.2 % |
| Gate | 1.1 % (0.5 % with the filters out) |
| Comp key path | +0.7 % |

**A full set** costs roughly 20–35 % of one core before engines: Tilt, DJ Filter, Master Sat and Isolator doubled for latency, one reverb, one delay, one Gate, plus the Comp and Limiter (companion note).

The engines are the bigger unknown. If cpu1 becomes usable, the buffer-heavy effects (delays, Repeat, Pitch, granular) are the candidates to move there (notes/2026-10-01-arp-modulation-effects-options.md).

## 9. Staged plan

| Stage | Contents | Depends on | Exit |
| --- | --- | --- | --- |
| **B1 Foundations** | The shared libm-free maths header (promote `CompLog2`/`CompExp2`; dB ramp; g and log-frequency tables). `FM1_UNIT_DB`. Linear SVF helpers on `stmlib::Svf` (bell and shelf mix, g-space law). House rules: glide per sample, flush below 1e-20, keep k ≥ 0.05 | the Comp branch merged | Every existing engine renders the same; no new libm in `nm` |
| **B2 Master tone** | DJ Filter, Tilt, then Master Sat, as ordinary effects (usable in FX2 now) | B1 | Exact bypass; sweep tests free of zipper noise; identical at 1, 7 and 64; wasm equals native under glibc |
| **B3 Gate and key** | `fm1_fx_ext_t` (`render_key`, outputs), Gate, the Comp's key hook (§7.7), the host's pre-effects tap for the one unit, the Trig INPUT-parameter fallback, `fm1-render --fx-key` | B1; the Comp lane | Tests 1–5 and 9–12 |
| **B4 Reverbs** | Plate Freeze. Vendor the Clouds reverb, Diffuser and PitchShifter, giving Room and Pitch. Then Hall, Classic and Shimmer | none (Pitch before Shimmer) | Reference renders; Mix 0 bit-exact; silence decays to zeros |
| **B5 Delays** | `tempo` and `reset` in the struct; Echo Sync and Duck; Tape; Taps; Repeat; Smear | B3's struct; tempo from `fm1_seq` | Tempo-change glide test; reset drops the tail |
| **B6 More EQ** | Isolator, EQ, Width | B1 | Flatness and kill-depth tests (§4.4) |
| **B7 Units and master** | The shared chain host, taps, planner, sends and master slots. GATE_DST into effects with `gate_edge`; sources 128+. The panel's KEY page, picker and meters | docs/15's 4-unit plan (O10, S6); docs/16 MG1–MG3; docs/15 S2 | Tests 6–8 and 10 |
| **B8 Gated by the dev kit** | Clouds granular and looper; JPverb and Greyhole (after provenance checks); Echo's Analog mode; Console sum mode | AC79 CPU measurement (docs/14) | Measured cost under budget |

**Size.** Lines [inferred]: shared header about 100, Gate 300–400, chain host about 400, tests about 600, and each effect 60–400. They count towards the next dead-code audit mark in CLAUDE.md.

## 10. Owner decisions

1. **Key model.** Should an effect pick its key source (Ableton/Digitakt style), or should there be key buses with send levels (Deluge style)? *Recommended: the effect picks; pre-fader taps.*
2. **Key loops.** *Recommended: refused in v1.* If wanted later, use a fixed 64-frame ring, never "the previous block".
3. **Detector link default.** Max, Sum or Left? *Recommended: Max, to match the Comp, with Sum and Left as options.* This overrides lane 3's Sum.
4. **Gate look-ahead.** *Recommended: 0–5 ms, default 0, latency shown on the panel, no latency compensation across units.*
5. **Order of the trigger features.** *Recommended: audio key first; then the matrix trigger through an INPUT parameter (tick-quantised); then sample-accurate `gate_edge`.*
6. **API version.** Append `fm1_fx_ext_t` and bump to v3, or keep v2? *Recommended: bump to v3.* It is one macro, and the layout change is explicit for future out-of-tree modules.
7. **`FM1_UNIT_DB`.** *Recommended: add it, and switch the Comp's dB parameters to it.*
8. **docs/16's Duck module.** *Recommended: drop it in favour of Comp keys plus the GR source. Keep Follow.*
9. **One-unit app.** Expose the Self and Sound (before effects) keys now, or wait for four units? *Recommended: now.* Gated reverb and the trance gate work today.
10. **Reverb and delay with several units.** *Recommended: one shared send reverb and one send delay. Inserts only for small effects (Gate, Filter, Drive, Tilt).* Per-unit Plates do not fit (§8).
11. **Master chain.** *Recommended: an ordered list of slots, defaulting to §5's order. Until it exists, master effects go in FX2.*
12. **First reverbs.** *Recommended: Plate Freeze, Room and Hall first; Classic and Shimmer next; JPverb only after its provenance check and a dev-kit measurement.*
13. **Tape colour.** *Recommended: keep it in Drive's Tape type. Master Sat ships without a Tape mode.*
14. **DJ Filter and Tilt.** *Recommended: two separate small effects. The DJ Filter is not a mode of the multimode Filter.*
15. **Clouds granular and looper.** *Recommended: after the dev-kit CPU measurement. Port granular and the looping delay only, at the host rate (`fm1_resampler` only downsamples). Leave out spectral and WSOLA.*
16. **Names.** *Recommended working names: Gate, Tilt, DJ Filter, Isolator, EQ, Master Sat, Width, Room, Hall, Classic, Shimmer, Tape, Taps, Smear, Repeat, Pitch.* Drawmer, DS201, Space Echo, Clouds, Freeverb and Xone appear in credits only. CLAUDE.md's rule on Mutable module names already covers Clouds.
17. **USB audio as a key.** *Recommended: later. It is unproven on the device.*

## 11. Sources

**Licences in local clones and the repo**
- `reference/mi-eurorack` `08460a6`: Clouds `dsp/fx/{reverb,diffuser,pitch_shifter,fx_engine}.h`, the granular files, `mu_law`; Elements `dsp/fx/reverb.h` and `part.cc`; Streams `compressor.cc` and `envelope.cc`. MIT header on every file; the README says STM32 code is MIT and AVR code GPL-3 (AVR not used) [verified].
- `reference/mi-stmlib` `e3bd7c9`: `dsp/filter.h`, `units`, `limiter.h`. MIT, vendored [verified].
- Repo `a121f18`: `engines/include/fm1_engine.h`, `engines/README.md`, `engines/src/fx_*.cc`, `engines/host/render.cc`, `sim/web/src/fm1_app.c`, `sim/web/README.md`, docs/01, docs/11, docs/15, docs/16. Uncommitted worktrees `scratch/wt-fx-{comp,filter,drive,limit}` [verified].

**Upstream, at pinned commits**
- Airwindows `d22a25b7f7c0c8c05e9f3ae480e7f1da9769f49d`: MIT, LICENSE "Copyright (c) 2018 Chris Johnson", and per-file headers [verified]. Plugins read: reverbs, TapeDelay/2, PurestEcho, Flutter2, Baxandall2, ToneSlant, Hull2, Capacitor2, Isolator3, Pafnuty, PurestSaturation, TapeHack2, Density3, ToTape9, Console5–9, Compresaturator, Sidepass, Gatelope, SoftGate.
- Faust libraries `9c421426fa1f92859c8df94460331eb1ecc2a029`: per-function licences [verified].
  - `reverbs.lib` 1.5.2: jpverb and greyhole MIT; zita_rev1, jcrev, satrev and dattorro_rev STK-4.3; freeverb LGPL with an exception; vital_rev and kb_rom_rev1 GPL-3.0-only; springreverb none.
  - `misceffects.lib` 2.6.0: reverse and tapeStop STK-4.3; gate_mono STK-4.3.
  - `filters.lib` 1.11.8: SVFTPT MIT; crossover LR4 STK-4.3.
  - `compressors.lib`: mixed, 24 functions GPL-3.0-only.
  - The STK-4.3 text is MIT plus a non-binding request (`licenses/stk-4.3.0.md`).
- Freeverb originals in ML_modules `05ac273`: "This code is public domain", Jezar at Dreampoint [verified].
- Schwung core `cfeb2b0` (freeverb.c, MIT) [verified].
- schwung-work `c88ec15`: MIT, "Copyright (c) 2026 Tim Cox" [verified]. Clean-room claim [reported].
- schwung-performance-fx `914d9ee`: MIT. Not its Bungee (MPL-2.0) or `pfx_revsc` (Csound lineage) [verified].
- schwung-space-delay `aae4c5e` and cyrusasfa/TapeDelay `c9ba1aa`: upstream unlicensed [verified].
- schwung-cloudseed `1d907e3`, CloudSeedCore `deb21de`, ValdemarOrn/CloudSeed `aa546ba`: MIT [verified].
- Signalsmith basics `369e906e`, dsp `4f62b0a8`: MIT. reverb-example-code `2798498`: no licence [verified].
- STK `6aacd35`: STK licence [verified].
- Teensy Audio `3039be2`: MIT-style with a funding notice [verified].
- DaisySP `2c72eaf9`: MIT. Compressor removed in `c59a4dcd` [verified].
- DaisySP-LGPL `c89d380`: LGPL-2.1 [verified].
- Soundpipe `3efb43b`: `revsc.c` extracted from Csound [verified].
- el-visio/dattorro-verb `41e976a`: MIT. khoin/DattorroReverbNode `d65d0da`: public domain [verified].
- Dattorro, "Effect Design Part 1", JAES 1997 (ccrma.stanford.edu/~dattorro) [reported].
- jpcima/bbd-delay-experimental `580c89b`: BSL-1.0. jatinchowdhury18/BBDDelay `eb21974`: BSD-3-Clause. Patina `8ad9e70`: MIT. schwung-junologue-chorus `463bdef`: MIT [verified].
- Cytomic technical papers page, read 2026-10-02: "This knowledge is placed in the public domain" [verified]. The PDFs are © Andrew Simper 2013: equations only.
- neodsp/simper-filter `8cb7d7fcc356b40b1418ff0b1cb1c1d8ce72a2eb`: MIT or Apache-2.0 [verified].
- W3C Audio EQ Cookbook, Working Group Note, 2021-06-08, adapted from Robert Bristow-Johnson with permission [verified].
- Mixxx `75acec85f791da9234cd7191590bf5d5885b115c`: GPL-2. Facts and constants only [verified].
- AnalogTapeModel (ChowTape) `604372e4ffd9690c3e283362e4598cb43edbb475`: GPL-3.0 [verified].
- Drawmer DS201 operator's manual (umlsrt.com mirror of drawmer.com/op201.htm) and DS301 manual (drawmer.com/uploads/manuals/archive/301_op.pdf): facts only [reported].
- DSPark `4686009d`: MIT [verified]. MarkzP AudioEffectDynamics `093c4cf8`: MIT notice [verified]. Deluge `62a516c2`: GPL-3.0 [verified]. CLAP `a47f6bad`: MIT; LV2: ISC [verified].
- Ableton Live audio-effect reference (Compressor sidechain) [reported]. Elektronauts threads 212825 and 209290 (Digitakt II, Syntakt) [reported].
- Valhalla DSP blog posts (2011-07-07, 2021-09-22) and the AES PNW 2015 slides: ideas only.
- Not fetched, said to be GPL or AGPL: Valley Plateau, MVerb, Dragonfly, Freeverb3, elysiera, frost-reverb, LSP, Calf, Zam, Open-X, Silentium [reported].

**Not verified in this run:**
- pi32v2 FPU speed. Every CPU figure is an estimate.
- The provenance of JPverb and Greyhole beyond the Faust header.
- The provenance of zita_rev1 in Faust.
- The DS201's key-filter slope.
- The Xone:92 specifications.
- Elektron behaviour.
- Live's Gate section.
- Whether stock routes USB audio input to its mixer.
