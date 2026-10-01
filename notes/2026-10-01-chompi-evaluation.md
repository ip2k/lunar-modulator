# CHOMPI as a source of FM-1 engines and effects (2026-10-01)

**Scope.** We read [CHOMPI-Club/CHOMPI](https://github.com/CHOMPI-Club/CHOMPI) through the GitHub API only. It has a single commit, `a73d732613` ("CHOMPI Open Source Bundle", 2026-09-29). Nothing was cloned, built or run. Three readers reported on TAPE 2.0, TEMPO 1.0 and WAVE 1.0. This note is the verifier's synthesis. Every licence claim below, and the memory and CPU figures for the candidates, were re-read from the files: all 111 files under the three apps' `code/src/` and the top-level notices. CPU figures are estimates and are **not measured on pi32v2** [inferred].

**Who to credit** [verified: LICENSE, THIRD_PARTY.md; the claims inside them are reported]:
- **CHOMPI Club** holds the copyright and is "now part of Chase Bliss".
- **TAPE 2.0, TEMPO and WAVE** were "written at Chase Bliss".
- **Electrosmith** wrote the original firmware and platform, TAPE through 1.0.9, and "the DSP and hardware-support source they brought".
- **Emilie Gillet** wrote `reverb.h`, `fx_engine.h` (with an Electrosmith port note) and `limiter.h`.
- No individual people are named anywhere in the repository.

The README calls this a "discontinuation open-source release" that "will likely not be receiving updates". Bugs we find there are not worth filing upstream.

## Verdict

**CHOMPI is worth including as a source of three small MIT effects and two designs. It is not a platform to port.**

What it fills:
- engines/ has no delay, no filter effect and no wow/flutter. TAPE and WAVE share one ping-pong echo, all three apps share a one-knob DJ filter, and TAPE has a small Warble. These are the easy wins.
- The stock FM-1 already has Filter, Delay and Distortion [reported, docs/02 §6]. So the echo and filter restore what an open firmware would otherwise lose; they are not new features.
- Genuinely new to the FM-1 would be:
  - TAPE's varispeed looper;
  - TEMPO's tempo-synced event delay;
  - TEMPO's arpeggiator with rest masks.

  All three need things `fm1_engine.h` does not have yet: tempo, transport, and a `FM1_KIND_MIDI_FX` contract. Do them after those API decisions.

What not to take:
- **The reverb.** It is our `plate` again, at a higher cost.
- **The saturator.** Plaits' `Overdrive` is already vendored in `engines/third_party/mutable/plaits/dsp/fx/overdrive.h`.
- **The wavetable voice.** It aliases, where Macro's Wavetable model is anti-aliased.
- **The samplers.** They need an SD card and up to 64 MB of SDRAM.
- **Anything from CHOMPI's copy of DaisySP** (see the licence section).

**Licence.** Everything we would take is MIT, and none of it is GPL or LGPL [verified], so it can link next to JieLi's closed libraries (docs/11 §7).

## Components

The FM-1 budget used here: 5,440 cycles per sample, and a 387,924-byte SRAM gap, part of which is stock's heap. Memory is for a 44,118 Hz port. CPU is per output sample and [inferred].

| Component (source) | Kind | Licence | FM-1 fit | Effort | Recommendation |
| --- | --- | --- | --- | --- | --- |
| **Ping-pong echo** (TAPE `DSPEngine.h:306-334`, WAVE `subtractiveEngine.h:306-333`, `InterpolatedDelayLine.h`) | audio FX | MIT (root); "Derived from Electrosmith DSP source" | As shipped, 96,256 stereo int16 frames = 385,024 B [verified], the whole gap. 65,536 B gives 0.37 s; 131,072 B gives 0.74 s. About 300–500 cycles as written (one `powf` and three `%` per sample); about 50–80 once those are hoisted | small (about ½ day) | **Port first** |
| **DJ filter** (`DJFilter.h` + `BasicMMF.h`, all three apps) | audio FX | MIT; the BasicMMF core matches Paul Kellett's musicdsp.org filter [inferred] | About 170 B. As written, TAPE does 8 divisions per sample (4 `SetFreq` + 4 `SetRes`); about 30 MACs at block rate | small | **Port the knob mapping**, preferably onto the vendored `stmlib::Svf` |
| **Warble** wow/flutter (TAPE `Warble.h`) | audio FX | MIT; generic LCG with Csound-style names [inferred: no Csound routine found] | 2 × `DelayLine<float,1024>` = 8 KB, or 4 KB as int16; 40–60 cycles | small | **Port**, with fixes |
| Saturation (TAPE `DSPEngine.h:293-300`) | audio FX | MIT | trivial | trivial | **Skip**: Plaits `Overdrive` is vendored and better (block-rate gain interpolation) |
| One-knob compressor into saturator (WAVE `subtractiveEngine.h:251-281`, `limiter.h` `ProcessComp`) | audio FX | MIT (Gillet's header plus CHOMPI/Electrosmith additions) | about 40 B | small | Optional, low priority. The gain jumps from 1 to 1/ratio at the threshold (no knee) [verified: limiter.h `ProcessComp`] |
| **Varispeed looper** (TAPE `Sampler.h`, `LooperEngine.h`, `RamBuffer.h`) | audio FX plus transport | MIT | As shipped, 2 × 31,694,848 B SDRAM buffers [verified]. 128 KB holds 0.74 s stereo or 1.49 s mono int16. 100–250 cycles | medium | **Later**: needs transport events and an SRAM decision |
| **Event delay** (TEMPO `granularDelay.h`, `SimpleCrossfade.h`) | audio FX plus host tempo | MIT; no third-party code | As shipped, 2 × 3.84 MB float [verified]. Stereo int16: 0.75 s = 132 KB. 150–400 cycles | medium (2–4 days, rewrite) | **Later**: needs tempo and clock edges in the API |
| **Arpeggiator / pattern generator** (TEMPO `ArpeggiatorSequencer.h`, `clockManager.h`) | MIDI FX | MIT | under 1 KB, event-rate | 1–2 days, reimplement | **Design reference** for the first `FM1_KIND_MIDI_FX` |
| Step recorder (WAVE `Sequencer.h`) | MIDI FX | MIT | under 1 KB | reimplement | Reference only; stock already has a 16-step sequencer |
| Wavetable voice plus 7 tables (WAVE) | sound | code MIT; table provenance unstated | 118,272 B in flash as int16 at 256 samples per frame | medium | **Skip**: a worse duplicate of Macro's Wavetable |
| Reverb (`reverb.h`, `fx_engine.h`, identical in TAPE and WAVE) | audio FX | MIT, Gillet | 64 KB | – | **Skip**: it is `plate`, with 4 `cosf` per sample and the AP1 smear commented out [verified] |
| SD samplers, RAM sampler, TEMPO chromatic/slice engines | sound | MIT | need SD and 30–168 MB of sample data | large | **Skip**. A RAM sampler could reuse a looper buffer later |
| UI, LEDs, MIDI I/O, JSON presets, mic filter, bootloader | – | MIT / BSD (.lds) | hardware- or SD-specific | – | **Skip** |

## Licence findings

1. **The top level is MIT** [verified].
   - `LICENSE` reads "MIT License / Copyright (c) 2026 CHOMPI Club". README: "Everything here is **MIT**". The API reports MIT.
   - THIRD_PARTY.md asks that "the copyright attributions in the source files … be preserved in any redistribution".
   - A port must therefore carry the CHOMPI Club MIT notice, plus the "Derived from Electrosmith DSP source" line where the file has it.
2. **Per-file notices** [verified by grep over all 111 source files].
   - Only `reverb.h`, `fx_engine.h` and `limiter.h` carry licence text, all MIT Emilie Gillet (2014, 2014 and 2015). `chompi_sram.lds` says "provided under the BSD license" (VisualGDB).
   - `DJFilter.h` and `InterpolatedDelayLine.h` say only "Derived from Electrosmith DSP source."
   - `BasicMMF.h`, `Warble.h`, `Sampler.h`, `LooperEngine.h`, `granularDelay.h`, `ArpeggiatorSequencer.h`, `Sequencer.h` and the rest have no header at all. They are covered by the root LICENSE.
3. **Electrosmith's code inside the grant** is [reported] only, by THIRD_PARTY.md. The exposure is a few dozen lines (the filter, the delay line). Low risk, and easy to rewrite if challenged [inferred].
4. **Trademarks** [verified: TRADEMARKS.md]. The CHOMPI name, logo, character and trade dress are not under the MIT licence. Its words: "please do not use the CHOMPI name or marks in a way that suggests it is an official CHOMPI Club release — give your version its own name". Name our ports ourselves, and avoid CHOMPI, JAMMI and CUBBI.
5. **CHOMPI's copy of DaisySP is unsafe to take from.**
   - Each app vendors a DaisySP whose `LICENSE` reads "MIT License / Copyright (c) 2020 Electrosmith, Corp." [verified].
   - Each copy still contains **all 19** headers that Electrosmith now publishes as LGPL in `electro-smith/DaisySP-LGPL`, whose LICENSE reads "Published under the LGPL-V2.1 license" [verified: tree comparison, 19 of 19 in TAPE, TEMPO and WAVE].
   - Example: CHOMPI's `reverbsc.h` credits "Ported from csound/soundpipe … Sean Costello, Istvan Varga" and has no licence text [verified].
   - Prebuilt `build/*.o` files, including `reverbsc.o`, `moogladder.o`, `tone.o` and `port.o`, and a `libdaisysp.a` of 167,742 B are committed [verified: tree].
   - The upstream removal commits named by the readers (`cfcb239619`, `c59a4dcd3f`) were not re-checked [reported].
   - **Rule:** never take DaisySP code from this repository.
6. **No candidate pulls in LGPL code** [verified].
   - The app sources use only Adsr, Svf, DcBlock, Oscillator, DelayLine, SampleRateReducer, SoftClip, SoftLimit, fonepole and fclamp. None of these is in DaisySP-LGPL.
   - "Tone and ATone" appear only in a TODO comment in each `DJFilter.h`.
   - What the candidates actually need is `fonepole`, `fclamp` and `DelayLine`. These are a few lines each, and we can write them ourselves or use stmlib equivalents.
7. **Data.**
   - **Wavetables** [verified by fetching all seven].
     - Format: RIFF, IEEE float, mono, 44,100 Hz, 33 × 2048 samples, with a Serum-style `clm ` chunk "<!>2048 11000000 wavetable (CHOMPI WAVE)". WAVE's README calls it "the common Serum wavetable layout".
     - The copies in `wavetables/` and `card-profiles/wave-1.0/` are identical (same blob SHAs).
     - Our analysis: every frame peaks at 0.900, RMS is constant within each table, and the highest harmonic above −90 dB in frames 0/8/16/24/32 is 63, 64, 57, 29, 64, 64, 64.
     - Provenance is not stated beyond the repo-wide MIT. Ask Chase Bliss before shipping the tables.
   - **Samples.**
     - TAPE's card holds 168 WAVs (167,594,520 B); TEMPO's holds 29 (29,919,856 B) [verified: tree sizes].
     - Neither has stated provenance. Neither is needed, and neither fits.
   - **Binaries.** The three firmware `.bin`, three bootloader `.bin` and the DaisySP objects are never to be copied (CLAUDE.md).

## Corrections and additions to the reader reports

- **One echo, not two.** TAPE's "tape delay" and WAVE's "ping-pong echo" are the same code [verified].
  - `InterpolatedDelayLine.h` differs only in comments.
  - The loop differs only in which variable drives the mix: feedback in TAPE, a separate amount in WAVE.
  - Treat it as one candidate.
- **The event delay's memory was understated.** TEMPO's buffer is interleaved stereo, with per-channel feedback and random-pan events (`granularDelay.h` `write`, `randomPan`) [verified]. A mono buffer would change the effect. A faithful port needs stereo int16, which doubles the figure: 0.75 s = 132 KB. Its divisions span 1/8 to 2 four-beat units, so a sub-second buffer covers only the short divisions at moderate tempos [inferred].
- **The WAVE allocator bug is broader than reported.** Starting from power-on priorities (`i + 1`), holding 8 notes and playing a 9th drops the 9th: the oldest voice has priority 7, and the steal looks for exactly 8 [inferred: transcribed-logic simulation]. WAVE is not a candidate, so this is only for the record.
- **The DJ filter is stable over its reachable range** [inferred: simulation of `BasicMMF` on noise, f ≤ 0.97, res ≤ 0.95]. At maximum resonance it peaks at about 4× (+12 dB), so the host limiter will see it.
- **Converting a NaN to int16 is undefined behaviour.** libDaisy's `f2s16` (`daisy_core.h:128-133`) clamps with comparisons, which let NaN through to an `(int32_t)` cast [verified]. Every int16 buffer in the echo, looper and event delay needs a non-finite guard. Our UBSan CI job would otherwise halt.
- **Confirmed as reported** [verified]:
  - uninitialised state in `DjFilter`, `Warble` (plus its shared `static randval`), the looper (`input_env`, `turn_period_count_`, `al`, `ar`, `rpos_frac_`, `scrub_target_`) and `Limiter::gain_`;
  - hard-coded 48 kHz in TEMPO (`granularDelay.h:431, 439, 457`) and in Warble (`onedsr`);
  - heap `push_back` in the audio path and `static bool up_` (`ArpeggiatorSequencer.h:563, 889, 799, 850`);
  - the unreachable REST event (`rand() % 2`, line 225);
  - WAVE computing 4 compressor channels and then overwriting 2;
  - the sequencer's millisecond timing that drops each step's overshoot (`clockManager.h:54-57, 155-157`);
  - the delay line writing with modulo `max_size_` but reading with modulo `cur_size_`.

## Memory and CPU against the FM-1

These use the 32-bit instance sizes from engines/README.md. The 387,924-byte gap includes stock's heap, so the real headroom is unknown until we have our own link map [inferred]. Shapes now runs at 96 kHz (`a1e6ed2`), so its size should be re-read from CI.

| Chain | Bytes | Left of 387,924 |
| --- | --- | --- |
| Macro + Plate + echo (0.74 s) + Warble (int16) + DJ filter | 218,720 | 169,204 |
| Macro + Plate + echo (0.37 s) + looper (128 KB) | 279,856 | 108,068 |
| Shapes + Plate + echo (0.37 s) | 336,000 | 51,924 |
| Shapes + Plate + echo (0.74 s) | 401,536 | does not fit |

On CPU, every CHOMPI block divides or calls `powf`, `sinf` or `cosf` per sample, which CHOMPI's 480 MHz M7 absorbs. Hoisted to block rate, the echo, filter and Warble together should come to roughly 150–200 cycles per sample, about 3 % of 5,440 [inferred]. Stage B must measure `powf`, `cosf` and float division on pi32v2 before anything is ported as written.

## What does not fit, and why

- **The samplers (TAPE's SD voices, TEMPO's chromatic and slice engines)**:
  - no SD card;
  - 30–168 MB of samples against 1 MB of flash shared with code;
  - per-voice 16 KB FIFOs.
- **Long buffers.** TAPE's 31.7 MB loop and RAM buffers and TEMPO's 7.68 MB delay buffers are 80–20,000 times the SRAM gap.
- **The wavetable engine.** It is not band-limited and aliases above about F4 at 64 harmonics. Macro's Plaits Wavetable model already covers it, anti-aliased. User tables would need SD or flash writes, which the one rule forbids.
- **The reverb, limiter and saturation**: duplicates of `plate`, `fm1_mix_limiter.h` and Plaits `Overdrive`.
- **Mic filter, input monitoring, battery and LED UI, libDaisy MIDI and timers**: CHOMPI hardware with no FM-1 counterpart.

## Next steps

1. **Port the ping-pong echo first** as `FM1_KIND_AUDIO_FX`, under a name of our own (for example `pingpong`).
   - Vendor the two small sources under `engines/third_party/chompi/`, unmodified, with `LICENSE` and an `UPSTREAM.md` giving the commit and credits. Wrap them as we do Mutable's.
   - Use a fixed 32,768-frame int16 buffer with mask wraps, `powf` at block rate, and a NaN-safe float-to-int16 conversion.
   - Parameters: Time (seconds, so it is rate-independent), Feedback, Mix.
   - Tests:
     - the existing host contracts: any-fill byte-identity, NaN parameters, and non-finite input recovery under ASan and UBSan;
     - an impulse gives L at T, R at 2T and L at 3T, with a level ratio of fb^0.7 per round trip and T within ±1 sample at 44,118 Hz;
     - a Time sweep stays click-free (bounded sample-to-sample step) and never reads outside the buffer;
     - a reference render against the vendored loop at 48 kHz, within 1 LSB.
2. **Port the DJ filter and Warble next**, each as its own effect.
   - Put the DJ mapping on `stmlib::Svf`, with cutoff in Hz.
   - Tests:
     - flat response in the centre dead zone;
     - LP and HP corners at the extremes;
     - a knob × resonance grid on noise that never diverges, with a bounded peak;
     - Warble seeded per instance, two instances independent, Mix 0 a bit-exact bypass.
   - Record the 32-bit instance size in CI.
3. **Decide the API before the looper, event delay or arpeggiator.**
   - Tempo, transport and clock in `fm1_host_t`, or a clock call.
   - A trigger parameter type for record, play and clear.
   - The shape of `FM1_KIND_MIDI_FX` (docs/11 §3.1 points at Schwung's `midi_fx_api_v1`).
   - Who owns the SRAM gap: echo against looper against engine.
   - Then reimplement TEMPO's arpeggiator from its behaviour (5 orders, 20-step rest masks, octave-jump probability, latch and sustain) with fixed arrays, a seeded RNG and golden event-stream tests.
4. **Measure on the JL-AC79 board (stage B)** before trusting the CPU estimates above.
5. **Bookkeeping.**
   - Add CHOMPI to docs/11 §3.3 (candidates) and §7, with the warning about its DaisySP copy.
   - Credit "CHOMPI Club / Chase Bliss; original firmware Electrosmith" in each port's `credits` string.
   - Ask on the Chase Bliss Discord about the wavetables' provenance, only if we ever want the tables.