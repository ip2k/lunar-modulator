# 22 — Effects evidence roll-up

The effects work spans the pinned AL-255 FM-1 analysis and the exact V15
application analysis in this repository. This page makes the progress visible
without merging binaries, private captures, or version-specific addresses that
have not been reconciled.

## Sources and coordinate spaces

The external comparison is [AL-255/FM-1-RE at commit
`95eca8488ac8c3b6f86287b2d3d43678e03e271a`](https://github.com/AL-255/FM-1-RE/tree/95eca8488ac8c3b6f86287b2d3d43678e03e271a),
especially its [FM engine analysis](https://github.com/AL-255/FM-1-RE/blob/95eca8488ac8c3b6f86287b2d3d43678e03e271a/docs/io/04-synth-engine.md)
and [effects function inventory](https://github.com/AL-255/FM-1-RE/blob/95eca8488ac8c3b6f86287b2d3d43678e03e271a/analysis/subsystems/FX.txt).
That analysis reports a six-slot effects pass, multi-stage delay/feedback
structures, a recursive 268-byte effect object, and a chorus/flanger process
with LFO/sine-table modulation.

This repository's primary map is the extracted `FM-1_015` application with
SHA-256:

```text
306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203
```

Its file offsets, flash runtime addresses, and RAM-resident code addresses are
defined in [13 — Firmware decoding](13-firmware-decoding.md). The AL-255
analysis uses a different image and address presentation. Its addresses are
therefore corroborating source references, not V15 coordinates.

## What the combined evidence establishes

| Area | Exact V15 evidence in this repository | Cross-repository corroboration | Boundary |
| --- | --- | --- | --- |
| Dispatch | File `0x872BE`, a 656-byte six-slot dispatcher; state base `0x01C0E840`; indexed object, slot ID, enabled, and parameter fields; six indirect process calls. | Six effect slots and a process path accepting the effect buffer and frame count. | V15 callback argument naming and full caller behavior remain partly inferred. |
| Callback table | Six 12-byte records at file `0x457A4`, with init, parameter-update, and process pointers. The process candidates are Filter, Reverb, Delay, Distortion, Chorus, and Phaser by ordered UI labels. | The external dispatch table also uses 12-byte records with initialization and process entries. | Every V15 name-to-ID binding remains inferred until the UI consumer is traced end to end. |
| Reverb | V15 constructors allocate 164, 332, or 276 bytes; one path builds eight delay stages with lengths `59, 227, 419, 617, 137, 313, 509, 727`; another ring has 10,261 elements. | Multi-stage comb/delay/feedback render core and three constructor variants. | Reverb equations, mode bindings, and sample-rate scaling remain unresolved. |
| Delay | V15 initialization allocates 44 bytes plus a 110,294-byte ring; adjacent signed 16-bit reads, two-byte pointer advance, wrap check, and signed saturation are observed. | Interpolated-delay interpretation and coefficient/state structure. | Feedback, wet/dry mix, smoothing, and exact interpolation are unresolved. |
| Distortion | V15 initialization allocates 268 bytes. The final stage is traced: input ×512, absolute lookup position, sign restoration, linear interpolation, separate gain, and explicit `1.0` saturation when the index exceeds 511. | A recursive 268-byte effect object and coefficient blocks are independently classified as an effect candidate. | The name is inferred; preceding filters, user gain/tone/level mapping, float conversion behavior, and hardware audio are unresolved. |
| Chorus | V15 initialization allocates 44 bytes and an 884-byte buffer, sets ring length 220 and end pointer start+876, and the process callback loads the exact 513-cell sine table at file `0x53B94`. | Chorus/flanger process with LFO/sine-table modulated delay. | Phase increment, interpolation, modulation depth, mix, and parameter scaling are unresolved. |
| Phaser and filter | V15 state sizes, callback entries, lookup/coefficient use, and nearby UI labels are recorded in [18](18-effects-decoding.md). | The external inventory identifies the corresponding effect families and coefficient-heavy code. | Stage count, transfer functions, and mode bindings are unresolved. |

## Two concrete effect milestones

### Chorus is a decoded structure, not only a label

The V15 bytes establish a small delay ring, its allocation size and wrap
boundary, and a process callback that reads the exact firmware sine table. The
external chorus/flanger classification matches that combination. Together they
support a modulated-delay implementation target. They do not yet select the
phase accumulator format, interpolation rule, modulation rate/depth, or wet/dry
mix.

### Distortion has a decoded nonlinear output stage

The V15 callback's final stage is described numerically in
[19 — Effects lookup mathematics](19-effects-mathematics.md): it scales the
preceding value by 512, interpolates the firmware tanh table between adjacent
cells, restores the input sign, applies a separate gain, and uses exactly 1.0
when the converted index is outside the interpolated range. The external
analysis corroborates the surrounding 268-byte object and coefficient setup.
The pre-filter chain and user parameter conversion still need decoding.

## What this changes in the contribution

The PR can now state the effects progress precisely:

- six effect candidates are tied to a V15 dispatcher and callback table;
- chorus has a V15 delay-ring and sine-LUT structure with external
  chorus/flanger corroboration;
- distortion has a V15 nonlinear output stage with scaling, sign,
  interpolation, gain, and saturation behavior identified;
- reverb and delay have observed state allocations, buffers, and processing
  structures with external multi-stage/interpolated-delay context;
- the full effect equations, UI parameter path, floating-point semantics, and
  physical audio equivalence remain open.

These are static and cross-repository observations. They do not establish that
the reconstructed algorithms run on the device or that a rebuilt image is safe
to install.
