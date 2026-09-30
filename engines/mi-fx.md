# mi-fx: audio effects from Mutable Instruments code

The first `FM1_KIND_AUDIO_FX` engines (docs/11 §4, stage A): a plate reverb,
a string ensemble and a diffuser, built from Emilie Gillet's MIT code in
`third_party/mutable/` (unmodified; see its `UPSTREAM.md`). Source
`src/mi_fx.cc`, build fragment `mk/mi-fx.mk`, tests
`tests/test_engines_mi_fx.py` (27 tests).

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
   so no loop can run away numerically [verified: `fx_engine.h`]. 10 s of
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
   belongs to Shapes, not to this stream [verified].
9. **Cost, desktop only** (Apple M1 Max, defaults, 64-frame blocks): Plate
   0.84 µs, Ensemble 0.45 µs, Diffuse 0.87 µs per block, 0.03–0.06 % of the
   1.451 ms block. As for the engines, this says nothing about pi32v2; stage
   B measures it.

## Limits

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
