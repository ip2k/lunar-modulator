# Vendored Mutable Instruments code

| | |
| --- | --- |
| Upstream | https://github.com/pichenettes/eurorack at `08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4` (2023-08-16) |
| stmlib | https://github.com/pichenettes/stmlib at `e3bd7c9cc00e4364166f9905c0509b6ffd0535ec` (2023-05-30), the commit eurorack pins as its submodule |
| Author | Emilie Gillet (Mutable Instruments) |
| Licence | MIT. Every vendored `.h`/`.cc` carries its MIT header (checked with grep on 2026-09-30); `stmlib/LICENSE` is copied alongside. stmlib's GPL-3 `ui/event_queue.h` is **not** vendored |
| Copied by | `vendor.py`, which follows `#include`s from the files listed in its `ROOTS` and copies the whole of `plaits/dsp`. Only Rings' reverb and its `fx_engine.h` come from `rings/`, and only Clouds' reverb, diffuser, `fx_engine.h` and `frame.h` from `clouds/` |
| Local changes | **None.** Files are byte-identical to upstream; fixes and adaptations live in our wrappers (`engines/src/mi_*.cc`) |

Re-vendoring:

```bash
git clone https://github.com/pichenettes/eurorack reference/mi-eurorack
git -C reference/mi-eurorack checkout 08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4
git clone https://github.com/pichenettes/stmlib reference/mi-stmlib
git -C reference/mi-stmlib checkout e3bd7c9cc00e4364166f9905c0509b6ffd0535ec
python3 engines/third_party/mutable/vendor.py reference/mi-eurorack reference/mi-stmlib
```

## Names

Mutable Instruments asks that derivative works not use "Mutable Instruments"
or the module names. The engines built on this code are called **Macro**
(from Plaits) and **Shapes** (from Braids) in the firmware and its UI, and the
effects **Plate** (Rings' reverb), **Ensemble** (Plaits' ensemble),
**Diffuse** (Plaits' diffuser) and **Room** (Clouds' reverb and diffuser);
the origin is stated in each engine's `credits` string and in these notes,
as the MIT licence requires.

## What our wrappers work around

- **Sample rate.** Plaits' engines are written for 47,872.34 Hz and Braids for
  96 kHz. Since 2026-10-01 the wrappers run them at exactly those rates,
  whatever the host's rate, and resample each engine's mix to the host with
  `engines/include/fm1_resampler.h` (engines/resampler.md). Every time
  constant and frequency the code keeps in samples is therefore the module's
  own. At 44,118 Hz the engines match upstream rendered at its own rate and
  resampled the same way: byte for byte on 20 of 21 Macro and Macro Heavy
  slots, within 1 LSB on Chiptune, within 0.55 LSB on all 47 shapes, and
  closely on Six-Op [verified: engines/reference-plaits.md,
  engines/reference-braids-fx.md]. Before, the wrappers ran at the host's
  rate with a pitch offset of `12*log2(native / host)` semitones, which left
  envelopes 8.5 % long, struck shapes ringing 1.6–2.8 times as long, the
  noise clock 1.41 semitones low and the string -9.5 cents at A2. The
  effects (Rings' reverb, Plaits' ensemble and diffuser) still run at the
  host's rate with rescaled loop gains (engines/mi-fx.md).
- **Block size.** Plaits' envelopes are per 12-sample block, and Braids'
  shapes step once per 24-sample block; 11 of its digital renderers also write
  two samples per pass and run off an odd-sized buffer. The Macro wrappers
  render exactly 12-sample blocks and Shapes exactly 24-sample blocks, and
  both buffer them out to the host's block, so the time constants stay exact
  and output does not depend on the host's block size. Before Shapes did this
  (fixed 2026-09-30), 22 of its 47 shapes drifted from upstream and 11
  crashed on odd-sized calls.
- **`WavetableEngine` arena overrun (upstream bug).** `Init` allocates 64 wave
  pointers; `LoadUserData` writes 4 × 64 = 256. On the module every engine
  shares one 16 KB arena from offset 0, so the overrun lands in unused space.
  With one tight arena per voice, as polyphony needs, it corrupts memory; the
  first render segfaulted here. The wrapper sizes each voice's arena for
  256 pointers. Recorded as an upstream candidate in
  `notes/upstream-candidates.md`.

## Audio effects (stream mi-fx, 2026-09-30)

Added to `ROOTS` in `vendor.py` for `engines/src/mi_fx.cc`
(notes in `engines/mi-fx.md`):

| File | Why |
| --- | --- |
| `rings/dsp/fx/reverb.h` | **Plate**: the Griesinger/Dattorro plate loop Rings uses, 32,768 × 16-bit words of delay memory. Chosen over the Elements and Clouds versions of the same topology because Rings runs at 48 kHz, closest to the FM-1's 44,118 Hz (Elements and Clouds run at 32 kHz) |
| `rings/dsp/fx/fx_engine.h` | pulled in by the reverb. It differs from Plaits' copy only in its namespace and in clearing the buffer in `Init` |
| `plaits/dsp/fx/ensemble.h`, `plaits/dsp/fx/diffuser.h` | **Ensemble** and **Diffuse**. Already vendored through `plaits/dsp`; listed so they survive if `TREES` is narrowed |

Re-running `vendor.py` against the pinned checkouts added exactly the two
`rings/` files and changed no existing file. The eurorack repository has no
top-level `LICENSE` file: its README gives the STM32 projects as MIT, and
each file carries the full MIT permission notice. All 146 vendored `.h`/`.cc`
files carry that notice and none mentions the GPL (checked with a script on
2026-09-30, after this addition).

What the effect wrappers work around:

- **Uninitialised state.** `rings::Reverb` sets its two damping-filter states
  only at the end of `Process`, and Plaits' `FxEngine::Init` does not clear
  the delay memory. The wrappers value-initialise the instance (zeroing it)
  and call `Reset()` on the Plaits effects.
- **Plaits' ensemble is mono for a mono input.** Both outputs read the same
  three LFO phases; only the third tap's delay line differs. Every FM-1
  engine so far is mono, so the wrapper adds a Width control that feeds the
  right line a 131-sample-delayed copy (the dry path is untouched).
- **Diffuser level.** Plaits' diffuser writes its wet at twice the loop level
  (about 5 dB above the reverb's wet for the same input); the wrapper halves
  it on output.
- **Sample rate.** As for the engines: delay lengths and LFO rates are fixed
  in samples. The Plate and Diffuse wrappers rescale their loop gain (and
  Plate its damping) so decay times in seconds match the native rate.

## Modulation kinds (docs/16 stage MG2, 2026-10-02)

Added to `ROOTS` in `vendor.py` as **test oracles**, not as code the
firmware or `fm1-render` links. The Bounce, Burst and Quantize kinds run
C ports of these files (`engines/mod/mod_mi.c`, with Emilie Gillet's MIT
notice); `fm1-mod-mi-ref` (`engines/test/mod_mi_ref.cc`, built by
`mk/mod.mk`) compiles the originals beside the ports and compares every
output (engines/mod/kinds.md, "The ports of Mutable Instruments code"):

| File | Why |
| --- | --- |
| `peaks/modulations/bouncing_ball.h` | Bounce: the ball, per sample at 48 kHz |
| `peaks/pulse_processor/pulse_shaper.*` | Burst's Burst and Delay modes, per 4-sample call |
| `peaks/pulse_processor/pulse_randomizer.*` | Burst's Random mode, on `stmlib::Random` seeded per test |
| `peaks/resources.cc`, `.h` | `lut_delay_times` and `lut_gravity`; `engines/mod/gen_mi_tables.py` copies the two into `mod_mi_tables.c` |
| `braids/quantizer.*`, `braids/quantizer_scales.h` | Quantize and its 49 scales (`gen_mi_tables.py` copies the scales) |
| `peaks/gate_processor.h`, `stmlib/utils/ring_buffer.h` | pulled in by the above |

Re-running `vendor.py` against the pinned checkouts added exactly these 12
files and changed no existing one. All 158 vendored `.h`/`.cc` files carry
the MIT permission notice and none mentions the GPL (checked with a script
on 2026-10-02); `tests/test_engines_mod_kinds.py` pins the 12 by digest.
Peaks' `resources.cc` also holds the 36,824-byte `wav_digits` and the other
Peaks tables; only the test tool links it.

**Under the sanitizers**, `set_initial_velocity` in `bouncing_ball.h` shifts
a negative value left (`<< 4`), undefined in C++11 but what ARM GCC did;
`engines/sanitizers/ubsan.supp` names it. The port multiplies by 16 instead.

## Room (stream fx-room, 2026-10-05)

Added to `ROOTS` in `vendor.py` for `engines/src/fx_room.cc` (notes in
`engines/README.md`, "Room"; research in
`notes/2026-10-02-delay-reverb-eq-gates-options.md` §3.2):

| File | Why |
| --- | --- |
| `clouds/dsp/fx/reverb.h` | **Room**: the same Griesinger/Dattorro loop as Rings' (Plate), smaller: `FxEngine<16384, FORMAT_12_BIT>`, 32 KB of delay memory, written for Clouds' 32 kHz |
| `clouds/dsp/fx/diffuser.h` | Clouds' stereo all-pass diffuser (four all-passes a side, 2,048 floats), which Clouds runs before its reverb; Room's Blur |
| `clouds/dsp/fx/fx_engine.h` | pulled in by both. It differs from Rings' copy only in its namespace and a line break |
| `clouds/dsp/frame.h` | `clouds::FloatFrame`, which both classes take but neither includes (Clouds' granular processor includes it first) |

Re-running `vendor.py` against the pinned checkouts added exactly these four
files and changed no existing file; all four are byte-identical to
upstream (`cmp`) [verified, 2026-10-05]. All 150 vendored `.h`/`.cc` files
carry the MIT permission notice and none mentions the GPL (checked with a
script on 2026-10-05, after this addition); with the twelve of the
modulation kinds above, merged in beside them, there are 162, and the same
check passes [verified, 2026-10-05, `grep` over the tree].

What the wrapper works around:

- **`FloatFrame` is not included.** The wrapper includes `frame.h` first,
  as Clouds' granular processor does.
- **Uninitialised state.** As with Rings' reverb, the two damping states are
  set only by `Process`; the wrapper value-initialises the instance.
- **Mix 0.** In Clouds the reverb crossfades from the diffuser's output
  (the processor's dry input is mixed back only at the very end). Room runs
  the reverb at full wet and crossfades from its own input, so the diffuser
  colours only the wet and Mix 0 passes the input bit for bit.
- **Sample rate.** Clouds ran at 32,000 Hz; at 44,118 Hz every delay and
  LFO keeps its length in samples. The wrapper rescales the loop gain and
  the damping, without libm (`src/fx_room_math.h`).
