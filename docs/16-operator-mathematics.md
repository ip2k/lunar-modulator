# 16 — Operator lookup mathematics

## Evidence

[verified, 2026-09-14] The stock `FM-1_015` application has SHA-256
`306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203`.
Two adjacent tables used by the operator/core candidates are completely
reproduced by mathematical formulas. Each table contains 1,024 little-endian
unsigned 16-bit integers. All **2,048 values match exactly**; maximum integer
error is zero.

[verified] Independent package extraction and the same complete-formula search
also reproduce both tables exactly in stock identities `009` and `014`:

| Package identity | Exponent file offset | Log-sine file offset |
| --- | --- | --- |
| `FM-1_009` | `0x8A578` | `0x8AD78` |
| `FM-1_014` | `0x8ACC2` | `0x8B4C2` |
| `FM-1_015` | `0x89F8E` | `0x8A78E` |

These are application-file offsets. Runtime addresses for the older versions
are withheld until their startup mappings receive the same verification.

| Table | Application offset | Initialized RAM address | Formula, i = 0..1023 |
| --- | --- | --- | --- |
| Fractional exponent | `0x89F8E` | `0x01C0604E` | `round((2**(i/1024) - 1) * 4096)` |
| Quarter-wave logarithmic sine | `0x8A78E` | `0x01C0684E` | `round(-log2(sin((i + 0.5) * pi / 2048)) * 1024)` |

The RAM addresses use the independently established startup-copy map in
[13 — Firmware decoding](13-firmware-decoding.md). Application file offsets
and runtime addresses are distinct.

Full table SHA-256 fingerprints:

```text
exponent e515a71ae736d92dcb3fd36973dea486c96d1521f1a0bab1f917be2c4ec07794
log sine 990c19e90732efe712a19ba4272f97c7c9d884ac0e4e19450a1067165d8aa8a8
```

[verified] Six-byte immediate-load instructions at application offsets
`0x850E0` and `0x8510C` load the two RAM pointers. The FM core candidate uses
the same pointers repeatedly, including `0x85414` and `0x8543A`. The source
application's algorithm table is separately located at file `0x8BE8C`, which
the startup copy places at RAM `0x01C07F4C`.

The formulas are implemented in `tools/fm1_dsp.py`; no vendor table bytes are
needed at runtime or included as fixtures. Full-table scanning rejects a
matching prefix followed by different data. A detected table is evidence of
its contents; it does not by itself establish that a particular function uses
it or is reachable.

## Lookup-stage interpretation

[verified: inspected instruction encodings; full execution still unverified]
The operator path takes the phase/modulation sum shifted right by 12, uses the
next 12 bits to select one of 4,096 cells around the wave, and folds the second
and fourth quarters by complementing the low ten bits. There is no fractional
interpolation within this lookup stage. The cell centers in the log-sine
formula avoid `log2(0)`.

The table is **logarithmic attenuation**, not an ordinary signed sine table.
Its scale is 1,024 units per amplitude octave (approximately 6.02 dB).
Adding an envelope attenuation to its value therefore multiplies the sine
amplitude by a power of two after conversion back to a linear value.

For the positive half-wave, the conversion is:

```text
logarithm = log_sine[index] + attenuation
mantissa = exponent[(~logarithm) & 1023] + 4096
magnitude = mantissa >> ((logarithm >> 10) & 31)
```

The complement of the ten fractional bits introduces a `2**(-1/1024)` factor
relative to an ideal mantissa without that bias. Negative samples use one's
complement in the inspected path: the raw register becomes `0x7FFFF - magnitude`,
then is shifted left by 13 with 32-bit wrap for downstream phase/modulation
arithmetic. The helper returns its signed 19-bit representative
(`-magnitude - 1`), which produces the same shifted 32-bit result; it does not
claim the intermediate raw register is already negative. This sign handling is material when comparing
integer output vectors; replacing it with ordinary negation changes them.

`log_sine_lookup_stage(phase, attenuation)` is an independent scalar model of
this stage, with a 24-bit phase wrap and attenuation restricted to 0..16384.
The endpoint 16384 is produced when the caller converts a zero input level;
the separate zero-state sentinel in the kernel initializes to 16383.
It is not a voice renderer or a firmware emulator. Tests check the measured
table fingerprints, all 4,096 phase cells against a separate sine expression,
phase wrapping and the exact one-octave amplitude shift.

## What remains to decode

The surrounding routines still need complete, version-specific verification
of their calling conventions, operator-state fields, gain interpolation,
feedback history, block iteration, saturation/overflow and bus routing. The
FM-1's complete sound cannot be inferred from these two tables. No modified
firmware or sample-vector result has yet been validated on the physical unit.

Prior AL-255 analysis of V009 supplied a useful instruction/data-flow reference:
[`04-synth-engine.md`](https://github.com/AL-255/FM-1-RE/blob/95eca8488ac8c3b6f86287b2d3d43678e03e271a/docs/io/04-synth-engine.md).
Its addresses and table descriptions were treated as hypotheses; the V15
table contents, formulas, RAM mapping and literal loads above were checked
directly. The current lookup-stage interpretation still requires full routine
and hardware validation before supporting replacement DSP.
