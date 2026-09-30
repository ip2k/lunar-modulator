# mi-fx: audio effects from Mutable Instruments code

The first `FM1_KIND_AUDIO_FX` engines (docs/11 §4, stage A): a plate reverb,
a string ensemble and a diffuser, built from Emilie Gillet's MIT code in
`third_party/mutable/` (unmodified; see its `UPSTREAM.md`). Source
`src/mi_fx.cc`, build fragment `mk/mi-fx.mk`, tests
`tests/test_engines_mi_fx.py` (45 tests).

```bash
make -C engines
engines/build/fm1-render --engine macro --param Model=4 \
    --note 0:57:100:0.5 --note 0:60:100:0.5 --note 0:64:100:0.5 --seconds 3 \
    --fx ensemble --fx diffuse --fx plate --fx-param Mix=0.4 --out chain.wav
engines/build/fm1-render --input impulse --fx plate --fx-param Mix=1 --seconds 3 --out ir.wav
```

## The effects

| id / name | From | What it is | In → out | Delay memory |
| --- | --- | --- | --- | --- |
| `plate` / Plate | Rings `dsp/fx/reverb.h` | Dattorro's plate topology: four input all-passes, then a loop of two branches (two all-passes and a delay each), with slow LFOs on the loop delays | L+R → stereo | 32,768 × 16-bit = 64 KB |
| `ensemble` / Ensemble | Plaits `dsp/fx/ensemble.h` (its string machine's ensemble) | three taps per side on two short delay lines, swept by a 0.75 Hz and a 6.6 Hz LFO at 0°/120°/240° | stereo → stereo | 1,024 floats = 4 KB |
| `diffuse` / Diffuse | Plaits `dsp/fx/diffuser.h` (its particle engine's diffuser) | four all-passes into a modulated feedback delay with two more all-passes; a short, grainy reverb | L+R → stereo | 8,192 × 12-bit = 16 KB |

Names are ours: Mutable Instruments asks that derivatives not use its name or
module names. Each `credits` string names the module the code came from.

Why these three [inferred]: the reverb is the one docs/11 §4 budgets for
(64 KB). Of the three copies of the same reverb (Rings, Elements, Clouds),
Rings' runs at 48 kHz, closest to the FM-1's 44,118 Hz; the other two run at
32 kHz [verified: their `SetLFOFrequency` calls and `dsp.h`]. Plaits' ensemble
and diffuser were already vendored, need no new resource tables, and give a
chorus-type and a diffusion-type effect with a tail. A second chorus (Rings'
`chorus.h`) would have needed Rings' `resources.cc` for its sine table.

## Parameters

All four-knob page 0, all 0..1.

| Effect | Mix | 2nd | 3rd | 4th |
| --- | --- | --- | --- | --- |
| Plate | crossfade dry → wet (upstream's `amount`); default 0.3 | **Decay**: loop gain 0.35..0.98 (Rings' `part.cc` range); default 0.5 | **Damping**: in-loop low-pass coefficient 0.9..0.3 (Rings' brightness range, reversed); default 0.3 | **Diffusion**: all-pass coefficient 0.5..0.75 (upstream fixes 0.625, the default here; Elements sweeps 0.55..0.70) |
| Ensemble | wet × Mix + dry × (1 − Mix/2), Plaits' own law: the dry never drops below half; default 0.5 | **Depth**: LFO depth, up to ±176 samples; default 0.5 | **Width**: ours, see findings; default 1 | — |
| Diffuse | crossfade dry → wet; default 0.5 | **Time**: loop gain 0.25..0.90 (Plaits' particle engine uses 0.25..0.75); default 0.5 | **Tone**: ours, one-pole low-pass on the wet, 250 Hz .. beyond Nyquist; default 0.75 (about 9.5 kHz) | **Width**: ours, see findings; default 1 |

Plate's input gain is fixed at 0.2 × (L+R), as every upstream user sets it.

## Memory per instance

Everything lives in the instance, including the delay memory; nothing
static, no heap.

| Effect | 64-bit desktop | 32-bit | of which delay memory |
| --- | --- | --- | --- |
| Plate | 65,648 B | 65,632 B | 65,536 B |
| Ensemble | 4,704 B | 4,704 B | 4,096 B (+ 524 B Width offset line) |
| Diffuse | 18,848 B | 18,848 B | 16,384 B (+ 2,360 B decorrelator) |

[verified] 64-bit from `fm1-render` (`fx_bytes`); 32-bit from clang laying
the same structs out for `i386-apple-macos10.13` (`-fsyntax-only`, sizes read
from a template diagnostic). The upstream classes themselves are 68/56/44 B
on 32-bit, 80/64/56 B on 64-bit; the delay memory dominates. pi32v2 is also
ILP32, so it should match the i386 column [inferred]. The Plate alone is
about 11 % of the FM-1's 578 KB SRAM and eight times stock's shared 8 KB FX
arena (docs/11 §2) [inferred from those figures]. Rings shares one buffer
between its reverb, chorus and ensemble because only one runs at a time; a
host that allows one reverb-class effect at a time could do the same.

## Sample rate

[verified: the vendored sources] Rings ran at 48,000 Hz and Plaits at
47,872.34 Hz. Delay lengths and LFO rates are fixed in samples inside the
vendored classes, so at 44,118 Hz:

- every delay is 8.8 % (Plate) or 8.5 % (Ensemble, Diffuse) longer: a
  slightly bigger room, a slightly longer ensemble delay (4.35 ms instead of
  4.0 ms centre);
- every LFO runs 8.1 % / 7.8 % slower (Plate 0.46 and 0.28 Hz, Ensemble 0.69
  and 6.05 Hz, Diffuse 0.28 Hz);
- **not left as is:** a loop gain `g` per pass would give a tail 8 % longer
  in seconds, and a one-pole coefficient `k` a cutoff 8 % lower. The wrappers
  set `g^(native/host)` and `1 − (1 − k)^(native/host)` instead, at
  `set_param` time: Plate's loop gain and damping, Diffuse's loop gain.
  Diffuse's in-loop damping (0.75) is fixed upstream and is not compensated.

Measured [verified, `test_plate_decay_is_rate_compensated` and scratch
probes]: the Plate's impulse tail at 44,118 Hz decays at 0.96–0.97 of the
rate of the unmodified reverb at 48 kHz (Decay 0.3/0.5/0.7). With the
compensation disabled it was 0.914–0.926, which matches 44,118/48,000 = 0.919.
The residual 3 % comes from the loop's 16-bit truncation, which costs more
per second at the higher rate and matters most at the impulse tail's low
level: a louder noise burst (Schroeder-integrated) measures 0.98–0.99 for
the Plate and 0.96–0.97 for Diffuse [inferred cause, verified figures].

The effects run per sample, so the output is bit-identical for any host
block size (tested at 1, 7 and 64 frames) [verified].

Diffuse measured the same way [verified,
`test_diffuse_decay_is_rate_compensated`]: its impulse tail (Time 0.8,
0.05–0.5 s) decays at 0.967 of the 48 kHz rate with the loop gain rescaled
and at 0.915 without. The rest is the uncompensated in-loop damping and the
12-bit loop's truncation [inferred cause].

## Input guard

Every input sample goes through `Guard` before anything else sees it, the
dry path included: NaN becomes 0, and anything beyond ±16 (+24 dBFS),
infinities included, is clamped to ±16. It costs two compares per sample and
no state. Added after the stream's review, which found two problems
[verified here with a scratch harness under ASan/UBSan: each effect, Mix 0
and 1, other parameters at 1, fed 0.1 s of a ±x square or of noise with one
bad sample, then 3.9 s of silence]:

1. **One non-finite sample latched Plate and Diffuse at NaN for good.** NaN
   (or ±Inf, which the loops turn into NaN) reaches float state that never
   flushes: `rings::Reverb`'s two damping filters, `plaits::Diffuser`'s
   damping filter, and the wrapper's tone filters and all-passes. Mix 0 did
   not isolate it, because both crossfades compute `NaN × 0 = NaN`. The last
   second of every such run was NaN, at Mix 0 and 1, for NaN, +Inf and
   −Inf. Ensemble recovered once its 1,024-float line had flushed.
2. **Huge input was undefined behaviour.** The vendored `Compress()` stores
   `static_cast<int32_t>(value × 32768)` (Plate) or `× 4096` (Diffuse),
   which overflows for |0.2·(L+R)| beyond 65,536 or |0.5·(L+R)| beyond
   524,288, and for NaN. UBSan reported both `fx_engine.h` lines, for input
   of 10^6 and for NaN. What pi32v2 does with an out-of-range conversion is
   unknown.

With the guard, the same harness finds no non-finite output anywhere, no
UBSan report, and a run with one NaN sample identical, bit for bit, to the
run with a 0 in its place. ±16 is far above anything the bus should carry
and far below either overflow: with the loops' own stored values bounded by
their formats (±1 and ±8), no store can then exceed about 10^6, against
int32's 2.1 × 10^9 [inferred from the loop structure].

Why guard the dry path too, rather than only what enters the loops: the
first effect after a faulty engine then heals the bus, so nothing
downstream, the host's limiter included, sees the NaN. Mix 0 remains a
bit-exact bypass for any finite input within ±16
(`test_mix_zero_passes_the_input_through`); beyond that it clamps.
`test_bad_input_is_guarded` drives each effect with half a second of
nothing but NaN, of input in the millions and of ±Inf, built from the host's
noise and Test Gain stages.

The guard relies on IEEE comparisons (`NaN < x` is false): a build with
`-ffinite-math-only` or `-ffast-math` would compile it away. The engine
Makefile uses neither; the JieLi toolchain profile must not either.

## Findings

1. **Plaits' ensemble gives L == R for a mono input** [verified: correlation
   1.0 with the host's mono noise, and by reading the code]. Both outputs read
   the same three LFO phases; only the delay line feeding the third tap
   swaps. Plaits' string machine feeds it two differently filtered signals,
   but every FM-1 engine so far is mono. **Width** feeds the right delay line
   a copy of the right input delayed by 131 samples (3 ms), which moves the
   right-hand taps; correlation drops to 0.53 at Mix 1 (the half-level dry is
   common to both sides). To keep the dry path clean, the wrapper runs
   upstream at amount 1, recovers the wet as `out − in/2`, and applies the
   same mix law itself. Width 0 behaves as upstream.
2. **Diffuse's wet is twice its loop level upstream** (`c.Write(del, 2.0f)`),
   5 dB hotter than the Plate's wet for the same noise. The wrapper halves it
   on output; the loop and its 12-bit headroom are untouched. Wet gain
   against white noise, Mix 1: Plate −3.9 / −2.9 / +1.1 dB at Decay 0 / 0.5
   / 1; Ensemble −3.3 dB; Diffuse −4.4 / −3.5 / 0.0 dB at Time 0 / 0.5 / 1
   [verified].
3. **Diffuse runs on the mono sum and decorrelates its wet** with one
   Schroeder all-pass per side (241 and 349 samples, g = 0.5); at Width 0 the
   two sides are identical. A second diffuser for true stereo would have cost
   another 16 KB.
4. **Uninitialised upstream state.** `rings::Reverb` sets its two damping
   states only at the end of `Process`, and Plaits' `FxEngine::Init` does not
   clear the delay memory. The wrappers have no constructor, so
   `new (mem) Instance()` value-initialises (zeroes) the whole instance, and
   they call `Reset()` on the Plaits effects. The engine API does not promise
   zeroed memory; the desktop host happens to provide it. A scratch harness
   created each effect in memory filled with 0xFF, 0x7F and 0xA5 (NaN
   patterns and noise) and got output bit-identical to a create in zeroed
   memory [verified]; the renderer cannot test this, because it zeroes.
5. **Stability.** All delay memory is 16- or 12-bit and `Compress` saturates,
   so for finite input no loop can run away numerically [verified:
   `fx_engine.h`]; non-finite and huge input is the input guard's job
   (above), and without it one NaN sample did latch Plate and Diffuse. 10 s of
   noise at the longest, brightest settings stays finite, peaks at 2.1
   (Plate), 0.69 (Ensemble) and 1.6 (Diffuse) before the host limiter, and
   holds a steady level; the Plate at Decay 1 takes about 8 s to build up
   and then holds 0.465 RMS for 20 s against the input's 0.289 [verified].
6. **Tails end in digital silence.** In the 16-bit output the Plate's
   default impulse tail reaches zero at 2.0 s and Diffuse's (Time 0.8) at
   1.3 s [verified]. The loops store with `static_cast<int32_t>`, which
   truncates toward zero, so they should decay to zero rather than hold a
   limit cycle [inferred]; none was seen in these renders.
7. **Ensemble has no tail to test.** It is feed-forward: an impulse is gone
   after 11 ms (192 + 176 samples of modulated delay plus Width's 131). Its
   test checks that the response ends, instead of a decaying tail.
8. **Sanitizers.** ASan and UBSan over 77 renders (every input, minimum,
   maximum, out-of-range and NaN parameters, blocks of 1 to 256 frames,
   rates 8 to 96 kHz, chains) found nothing in the effects. The one report
   was in Braids' `analog_oscillator.cc:182` (a left shift of a negative
   value, CSaw), reached only because a chain used Shapes as its source; that
   belongs to Shapes, not to this stream [verified]. The renderer cannot feed
   NaN or huge input directly, so those renders missed the two problems the
   input guard now handles; the review's harness found them.
9. **Cost, desktop only** (Apple M1 Max, defaults, 64-frame blocks): Plate
   0.84 µs, Ensemble 0.45 µs, Diffuse 0.87 µs per block, 0.03–0.06 % of the
   1.451 ms block. As for the engines, this says nothing about pi32v2; stage
   B measures it.
10. **The host's bus limiter latches on NaN too** (`fm1_mix_limiter.h`, not
    this stream's code) [verified: scratch program]. One NaN in the right
    channel (or both) makes `envelope` NaN for good; `envelope > ceiling` is
    then always false, so the limiter stops limiting: a 2.0 square came out
    at 2.0 for the next second. A NaN in the left channel alone is ignored
    (`a > b ? a : b` picks the right). The input guard keeps these effects
    from passing NaN on, but an engine with no effect after it still can;
    the host should sanitise the bus or the limiter should ignore NaN.
11. **Every parameter is tested for what it does** (added after the review,
    which showed that five of the eleven could be disconnected with all
    tests still passing): Plate Decay sets the decay slope (−43 / −23 /
    −6 dB/s at 0 / 0.5 / 1), Damping darkens the tail, Diffusion raises the
    early echo density (0.31 / 0.44 / 0.49 over the first 100 ms), Ensemble
    Depth turns a steady sine into a beating one (level variation 0.008 /
    0.45 / 0.51), Diffuse Tone sets the brightness, and a wet-level window
    per effect catches a gain slip. Each of nine scratch mutants (each of
    those five parameters held fixed, Plate's or Diffuse's loop-gain rate
    compensation removed, Diffuse's wet gain at 0.1, the input guard
    removed) fails at least one test [verified]. Not covered: Plate's
    damping rate compensation. Removing it moves the impulse tail's share
    of energy above 2 kHz (0.2–0.6 s, 44,118 against 48,000 Hz) only from
    0.998 to 0.985 at Damping 0.5 and from 1.014 to 0.990 at Damping 1, and
    the decay-slope ratio by under 1 %: too little for a robust test
    [verified].

## Limits

- Input is guarded: NaN becomes 0 and anything beyond ±16 is clamped, on
  the dry path too, so Mix 0 is a bit-exact bypass only for finite input
  within ±16 (+24 dBFS).
- No parameter smoothing. Mix, Decay and the rest change at block
  boundaries; a large jump in Mix can click. Upstream smooths at its control
  rate outside these classes.
- Plate and Diffuse sum their input to mono; the input's stereo image
  survives only in the dry path.
- Delay lengths and LFO rates are not rate-compensated (see above).
- 16-bit (Plate) and 12-bit (Diffuse) delay memory: the Diffuse wet has a
  noise floor about 72 dB below 1.0 [inferred from the format].
- Float states (filters, all-passes, Ensemble's float delay line) decay into
  subnormals after the input stops. That costs time on x86 without
  flush-to-zero; what pi32v2's FPU does with subnormals is unknown.
- No freeze, no tempo sync, no reset of the tail short of re-creating the
  instance.
- The Plate does not fit the stock FX arena; on the FM-1 it needs its own
  64 KB.
