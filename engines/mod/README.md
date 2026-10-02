# engines/mod — modulation primitives

Small C99 building blocks for modulation: an LFO, a multistage envelope, a
slew limiter, sample-and-hold, a Turing-machine register and a clock
divider/multiplier. They follow §3–§5 of the arpeggiator, modulation and
effects options note of 2026-10-01. The modulation runtime that docs/16 is
designing will wrap them; this directory defines no module API, no
parameter pages and no routing. Nothing here is wired into an engine, the
renderer or the simulator yet.

```bash
make -C engines                              # builds build/fm1-mod with everything else
engines/build/fm1-mod --sizes                # struct sizes (JSON)
printf 'lfo a 1\nshape a sh\nhz a 30\nproc a 128\nstate a\n' | engines/build/fm1-mod -
python -m pytest tests/test_engines_mod.py   # the tests
python3 engines/mod/gen_tables.py            # regenerate mp_tables.c (--check: verify)
```

## Files

| Path | What |
| --- | --- |
| `fm1_mp.h` | The API, prefix `fm1_mp_`, so it cannot clash with the module API |
| `mp_rng.c` | The PRNG: xorshift64* seeded through splitmix64 |
| `mp_lfo.c` | The LFO |
| `mp_env.c` | The multistage envelope, after Peaks |
| `mp_slew.c` | The slew limiter |
| `mp_sah.c` | Sample-and-hold and track-and-hold |
| `mp_turing.c` | The Turing-machine register |
| `mp_clkdiv.c` | The clock divider and multiplier |
| `mp_tables.c`, `gen_tables.py` | The envelope curves and Peaks' time curve as 257-point float tables, and the script that writes them |
| `mp_int.h` | Shared internals: table lookup, NaN-safe clamps |
| `mp_tool.c` | `fm1-mod`, the desktop test tool: a command script in, JSON Lines out |
| `../mk/mod.mk` | The build fragment |

## Rules every primitive keeps

- **No heap, no stdio, no libm.** The caller owns each struct, and `init`
  sets every field, so prior memory contents never matter. The tests check
  the objects' undefined symbols for allocators, stdio and libm, and run a
  script from memory filled with `0x00`, `0xA5` and `0xFF` [verified:
  `tests/test_engines_mod.py`]. The sine is a polynomial, and the curves
  and times are tables. The one double operation is in the LFO's rate
  setter.
- **One timing convention.** `process(n)` advances n samples and returns
  the value after the last one. `render(out, n)` writes the value after
  each sample, so its `out[n-1]` equals what `process(n)` returns. `value()`
  reads the current value without advancing. Events such as a gate, a
  reset or a sync happen between calls.
- **Block-size independence.** The LFO, envelope, slew and S&H give
  bit-identical values however a span is split into calls, provided events
  fall on the same samples. The tests compare every value that a chunked
  `process` returns (blocks of 7 and 64, and random splits) with the
  per-sample `render` at that sample [verified].
  - The LFO and the envelope advance integer phases, so a call costs O(1),
    plus one step per wrap or segment crossed.
  - The slew's linear mode is O(1); its exponential mode loops per sample.
- **NaN safety.** Every setter maps NaN and ±inf to a documented value, and
  every signal input ignores non-finite values. No output is ever NaN or
  infinite [verified: tests].
- **Determinism per seed.** Each random source owns its own PRNG.
  - It never touches `stmlib::Random`'s global: the reference tests depend
    on that (options note §2.3).
  - The draws are integers mapped to multiples of 2^-23, so a seed gives the
    same values on every platform. The tests pin golden values for seed 1
    [verified on arm64 macOS clang, and on Linux gcc with `-m32`].
- **`-ffp-contract=off`.** This is docs/14's ladder profile: macOS arm64
  clang would otherwise fuse multiply-adds.

## LFO (`fm1_mp_lfo_t`)

A uint32 phase accumulator with a 32.32 increment. Output is bipolar,
−1..1; phase 0 starts a cycle.

| Shape | Value at phase x (0..1) |
| --- | --- |
| `SINE` | sin 2πx, from an 11th-order Taylor polynomial on the folded quarter wave (error under 6e-8 [verified: tests compare with `math.sin` to 2e-6]) |
| `TRIANGLE` | 0 → 1 → −1 → 0, in phase with the sine |
| `SAW_UP`, `SAW_DOWN` | 2x − 1, 1 − 2x |
| `SQUARE` | +1 while x < pulse width, else −1; widths 0 and 1 give constant −1 and +1 |
| `SMOOTH_RANDOM` | glides from the previous draw to this cycle's draw (smoothstep) |
| `SAMPLE_HOLD` | this cycle's draw, held |
| `RANDOM_WALK` | glides to a target that moves by up to `walk` × [−1, 1) each cycle, reflected at ±1 |

- **Rate as a ratio.** The rate is `hz = base_hz × ratio`, clamped to
  0..rate/2. Free-running, `base_hz` is the rate and `ratio` a multiplier.
  Tempo-synced, `base_hz` is BPM/60 and `ratio` is cycles per beat.
  - The increment is rounded up to 2^-64 of a cycle per sample. A period
    that is a whole number of samples therefore wraps on its last sample.
    At 120 BPM, one cycle per bar wraps after exactly 88,236 samples
    [verified: test].
- **Modes.** `FREE` runs on. `ONE_SHOT` runs one cycle from the start phase
  and holds at its last phase. `HALF` does the same for half a cycle.
  These cover Elektron's free, trig, one and half modes [reported:
  options note §3.1] once the module calls `reset` on a note.
- **`reset`** retriggers. The phase goes to the start phase, a one-shot
  runs again, and random shapes draw a new cycle.
- **`sync(phase)`** moves the phase the shorter way round, to lock the LFO
  to `fm1_mp_clkdiv_phase` or to a tick count without drift.
  - A forward move across the wrap draws.
  - A backward move across it owes a draw instead, so jitter around the
    wrap point never draws twice in one cycle [verified: test].
  - The tests lock an LFO to a one-bar clock for 30 bars; it starts exactly
    one cycle per bar [verified].

**The S&H wrap fix.** Schwung's `src/host/lfo_common.h` (Charles Vestal,
MIT) re-rolls its S&H only when phase < 0.05. Once a block advances more
than 0.05 of a cycle it misses wraps, and a held 0.0 counts as unset
[reported: options note §3.1, lines 173–178 at `ba3b39d`; not re-read
here].
- **What this LFO does instead.** A wrap is a carry out of the 64-bit sum
  of phase and increments. Each carry draws exactly once, however many fall
  in one call. The random state is kept up to date for every shape, so it
  is never unset.
- **The numbers.** At 30 Hz in 128-frame blocks, a block is 0.087 of a
  cycle. Over 2,000 blocks, the 0.05 rule on the same phases catches 99 of
  174 wraps (57 %); this LFO draws on all 174 [verified:
  `test_lfo_sample_hold_draws_on_every_wrap`].
- **Several wraps in one call** draw several times, the same draws as
  per-sample processing [verified].

**The random state.** Each cycle makes two draws, always in the same order:
one for S&H and smooth random, one for the walk. Changing the shape
therefore never shifts the random sequence.

## Envelope (`fm1_mp_env_t`)

A C99 reimplementation of Peaks' `MultistageEnvelope` (Emilie Gillet, MIT):
`peaks/modulations/multistage_envelope.h` and `.cc` in
[pichenettes/eurorack](https://github.com/pichenettes/eurorack/tree/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/peaks/modulations)
at `08460a6`, the commit `engines/third_party/mutable` pins. The structure
is Peaks':
- up to 8 segments, each with an end level, a time and a curve;
- a sustain point, held while the gate is high, that the gate's fall jumps
  to;
- a loop from `loop_end` back to `loop_start`;
- a uint32 phase per segment, whose overflow moves on and drops the
  overshoot;
- retrigger from the current value, or from the first level with hard
  reset on.

**Curves** come from Peaks' formulas in `peaks/resources/lookup_tables.py`
lines 122–129:

| Curve | Formula | Shape |
| --- | --- | --- |
| `LINEAR` | t | straight |
| `EXPO` | (1 − e^−4t)/(1 − e^−4) | fast, then settling: the RC charge and discharge |
| `QUARTIC` | t^3.32 | slow, then fast |

Synths disagree on what to call these. Some label EXPO's shape "log" on a
rising segment, and QUARTIC's "exponential"; the names here are Peaks'.
Values come from 257-point tables, as in Peaks. Interpolation error is
under 4e-5 [verified: `test_env_curves_are_peaks`].

**Presets.**
- `set_adsr(a, d, s, r, curve, loop)`:
  - `LOOP_OFF` is ADSR.
  - `LOOP_AD` repeats 0 → 1 → 0 while the gate is high.
  - `LOOP_ADR` repeats 0 → 1 → s → 0 while the gate is high.
  - Every mode releases from the current value in `r` when the gate falls.
- `set_ad(a, d, curve, loop)` is Peaks' AD: the gate's fall is ignored.
  With `loop` it is Peaks' free-running AD loop.
- `configure` and `set_segment` build any other shape.
- `fm1_mp_env_time_from_knob` is Peaks' knob-to-time curve, 0.5 ms to 8 s
  (`lookup_tables.py` 55–68), within 0.2 % [verified: test].

**Differences from Peaks**, all deliberate:
1. **Units.** Levels are float, −1..1, and times are in seconds. Peaks uses
   int16 levels and 16-bit time codes through a 48 kHz increment table, so
   any sample rate works here.
2. **Curve tables.** They use the plain ramp t = i/256. Peaks' ramp repeats
   its 256th point, so its curves reach 1 one step early. Interpolation
   uses a 24-bit fraction, against Peaks' 16.
3. **Output timing.** Output is the value after each advance; Peaks writes
   it before. So the sample on which a segment overflows outputs that
   segment's end level exactly, and a retrigger or release starts from the
   value "now" with no repeated sample.
4. **Finished envelopes.** A gate falling after the envelope has finished
   does nothing. Peaks reruns the release from the final level.
5. **Loop presets.** `LOOP_AD` and `LOOP_ADR` repeat while the gate is high
   and release on its fall. Peaks' loop presets have no sustain point and
   ignore the fall. `set_ad(…, loop=1)` keeps Peaks' behaviour.
6. **Segment length.** A segment lasts at least 2 samples, the uint32
   increment cap. Peaks' shortest time is 0.5 ms.
7. **Reshaping.** A reshape that removes the running segment finishes the
   envelope at its current value; a finished envelope stays finished.
   Peaks restarts at segment 0 with value 0.
8. **Curves per preset.** One curve applies to all of a preset's segments.
   Peaks' ADSR mixes a quartic attack with an exponential decay and
   release; `set_segment` can rebuild that.
9. **Gates.** Gates are events between calls, not per-sample flags.

## Slew limiter (`fm1_mp_slew_t`)

- **Linear:** at most 1/(time × rate) per sample. `rise` and `fall` are the
  seconds a full 0 → 1 or 1 → 0 change takes.
- **Exponential:** a one-pole lag with the time constant `rise` going up and
  `fall` going down (63 % of a step).
  - The coefficient comes from the [2/2] Padé approximant of e^−x, within
    0.1 %.
  - Each step moves at least one LSB, so it lands exactly on the target. A
    float one-pole with a long time constant stalls a few ulps short.
- **The state** is integer, Q4.28: values are quantised to 2^-28 and limited
  to −8..8.
- **Time 0** passes the input through. Non-finite inputs leave the target
  as it was.

## Sample-and-hold (`fm1_mp_sah_t`)

- **`SAMPLE`** takes the input on a rising gate.
- **`TRACK`** follows the input while the gate is high and holds while it is
  low.
- **Non-finite inputs** are never taken.
- **The modes** are DaisySP's `SampleHold` modes (Electrosmith, Paul
  Batchelor, MIT) [reported: options note §5]; written from the behaviour.
- **Random voltages:** the LFO's S&H shape is the clocked random source.
  This primitive holds any signal.

## Turing-machine register (`fm1_mp_turing_t`)

After Tom Whitwell's Turing Machine (Music Thing Modular), from its
published behaviour.
- **Each clock** brings back the bit shifted in `length` clocks ago (1..32)
  and inverts it with probability `flip`:
  - 0 locks a loop of `length` steps;
  - 1 gives a loop of twice the length, its second half inverted;
  - 0.5 is fresh random [verified: tests].
- **Output** is the low 8 bits as 0..1, like the module's 8-bit DAC, and bit
  0 as a gate.
- **One draw per clock** whatever `flip` is, so turning it never shifts the
  stream.
- **Length 32 is safe.** No mask is built from the length, so length 32 has
  none of the shift-by-32 undefined behaviour of O_C's `util_turing.h`
  (`notes/upstream-candidates.md`).
- **Card 20.** Workshop Computer card 20 (Chris Johnson, MIT) is the
  implementation the options note lists. This one was not written from it.

## Clock divider and multiplier (`fm1_mp_clkdiv_t`)

`mul` pulses per `div` periods of `ref` input ticks: `ref` 96 is one beat
at `fm1_seq`'s 96 PPQN.
- **Where pulses fall.** Pulse k falls on tick ⌈k · ref · div / mul⌉,
  counting from the first tick after a reset, so pulses are spread as
  evenly as whole ticks allow and never drift.
  - Fifths of a beat land on ticks 0, 20, 39, 58, 77 and 96 [verified:
    test].
- **`advance(ticks)`** equals that many `tick()` calls [verified: test].
- **`phase()`** gives the position in the output period, for
  `fm1_mp_lfo_sync`.

## Sizes and cost

| Struct | Bytes |
| --- | --- |
| `fm1_mp_lfo_t` | 88 |
| `fm1_mp_env_t` | 96 |
| `fm1_mp_slew_t` | 40 |
| `fm1_mp_sah_t` | 8 |
| `fm1_mp_turing_t` | 32 |
| `fm1_mp_clkdiv_t` | 16 |

- **Sizes** are from `fm1-mod --sizes` on 64-bit arm64 macOS [verified]. A
  gcc `-m32` build passes every test; there `uint64_t` aligns to 4, so its
  sizes are the same or smaller [verified].
- **Read-only tables:** 3 × 257 floats, about 3 KB.
- **Cost.** A control-rate call is tens of operations. The exceptions are
  the exponential slew, at about 5 operations per sample, and the LFO's
  rate setter, which divides in double.
  - Not measured on pi32v2; that waits for the dev board (docs/14)
    [inferred].

## Credits and licences

All code here is this repository's, MIT. It is written from these MIT
sources and published behaviours, and copies none of their code:

- **Emilie Gillet**, Mutable Instruments Peaks: the envelope's structure,
  presets, curve formulas and time curve.
- **Charles Vestal**, Schwung's `lfo_common.h`: the shape set, and the S&H
  behaviour fixed here.
- **Electrosmith and Paul Batchelor**, DaisySP `SampleHold`: the two S&H
  modes.
- **Tom Whitwell**, Music Thing Modular's Turing Machine: the register's
  behaviour.
- **Sebastiano Vigna**: xorshift64* and splitmix64.

Mutable module names appear only as credited sources (CLAUDE.md).
