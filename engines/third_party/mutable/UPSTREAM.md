# Vendored Mutable Instruments code

| | |
| --- | --- |
| Upstream | https://github.com/pichenettes/eurorack at `08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4` (2023-08-16) |
| stmlib | https://github.com/pichenettes/stmlib at `e3bd7c9cc00e4364166f9905c0509b6ffd0535ec` (2023-05-30), the commit eurorack pins as its submodule |
| Author | Emilie Gillet (Mutable Instruments) |
| Licence | MIT. Every vendored `.h`/`.cc` carries its MIT header (checked with grep on 2026-09-30); `stmlib/LICENSE` is copied alongside. stmlib's GPL-3 `ui/event_queue.h` is **not** vendored |
| Copied by | `vendor.py`, which follows `#include`s from the files listed in its `ROOTS` and copies the whole of `plaits/dsp`. Only Rings' reverb and its `fx_engine.h` come from `rings/` |
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
effects **Plate** (Rings' reverb), **Ensemble** (Plaits' ensemble) and
**Diffuse** (Plaits' diffuser); the origin is stated in each engine's
`credits` string and in these notes, as the MIT licence requires.

## What our wrappers work around

- **Sample rate.** Plaits' engines are written for 47,872.34 Hz and Braids for
  96 kHz. The wrappers run them at the host's rate (44,118 Hz on the FM-1) and
  correct the pitch by `12*log2(native / host)` semitones. Envelope times
  scale by the same ratio. The tests hold tuning to ±5 cents at A2, A4 and A6.
- **Block size.** Plaits' envelopes are per 12-sample block. The Macro wrapper
  renders in exactly 12-sample blocks and buffers them out in 64-frame host
  blocks, so its time constants stay exact.
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
