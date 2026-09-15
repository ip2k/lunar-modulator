# 18 — Effects callbacks and state

## Source and address mapping

[verified, 2026-09-14] These observations use the extracted `FM-1_015`
application, 581,564 bytes, with SHA-256:

```text
306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203
```

All file offsets below refer to that application, not its firmware package.
Flash code uses runtime address `0x02000120 + file_offset`. The startup code
copies application bytes beginning at `0x83F40` to RAM at `0x01C00000`.
See [13 — Firmware decoding](13-firmware-decoding.md) for the checked mapping.
Historical disassembly addresses based on `0x02000000` must not be copied
directly into this map. No device execution or audio measurement was used.

The related cross-repository findings are consolidated in
[22 — Effects evidence roll-up](22-effects-evidence-rollup.md). That document
keeps the AL-255 analysis as corroborating context and does not transplant its
addresses into this V15 map.

## Six-slot dispatcher

[verified] The routine at file `0x872BE`, runtime `0x01C0337E`, contains six
indirect process calls. Its extent is **656 bytes**, ending immediately after
the return at file `0x8754C`. A new function starts at `0x8754E`. The earlier
5,702-byte annotation included several unrelated routines.

The corrected 656-byte function has SHA-256:

```text
2575f84297ba0bfbe772fb8cc46cf632fd1440c0a559ebef449c2d7e47833760
```

The dispatcher loads shared state at `0x01C0E840`. These fields are observed
in its indexing instructions; names describe their apparent use:

| Field | Address calculation | Confidence |
| --- | --- | --- |
| Effect object pointer | `state + 0x488 + 4*id` | Verified loads/stores; six IDs |
| Effect ID for a chain slot | `state + 0x18E7 + 3*slot` | Verified byte load |
| Enabled flag for an effect | `state + 0x18E8 + 3*id` | Verified condition |
| Process parameter byte | `state + 0x18E9 + 3*id` | Verified byte load; meaning unresolved |

The six process call instructions occur at application offsets `0x8746C`,
`0x87498`, `0x874C4`, `0x874F0`, `0x8751C`, and `0x87548`.
[inferred] Register setup gives the process interface
`process(parameter_byte, audio_buffer, frame_count)`.

The callback load and argument setup include a paired instruction: assigning
the buffer to `r1` occurs alongside loading the callback from **the previous
value** of `r1 + 8`. Reading these as two sequential operations gives an
incorrect callback address.

## Callback records

[verified] The table at file `0x457A4`, runtime `0x020458C4`, contains six
12-byte records. Each record has three little-endian code pointers. The
dispatcher uses the pointer at `+8` as the process callback. [inferred] The
`+0` and `+4` callbacks initialize the object and update its parameters.

The addresses in this table are **runtime addresses**. All eighteen callbacks
are in flash; subtract `0x02000120` to obtain their application file offsets.

| ID | Candidate name | `+0` initialization | `+4` parameter update | `+8` process |
| --- | --- | --- | --- | --- |
| 0 | Filter | `0x0201A8BC` | `0x0201A572` | `0x0201A8E4` |
| 1 | Reverb | `0x0201AC54` | `0x0201ABEA` | `0x0201AECE` |
| 2 | Delay | `0x0201C1D8` | `0x0201C28A` | `0x0201C2F6` |
| 3 | Distortion | `0x0201C720` | `0x0201C858` | `0x0201C8D6` |
| 4 | Chorus | `0x0201D0F8` | `0x0201D1A4` | `0x0201D20E` |
| 5 | Phaser | `0x0201D59A` | `0x0201D65E` | `0x0201D6CC` |

The complete 72-byte table has SHA-256
`b0a6e5f01ce6f24f10e5a5814d25a0a4cc5e28ba4a7f2db94d5b37606c5e87d1`.

**Every name-to-ID binding is inferred.** A separate six-pointer UI table at
file `0x4E9B8` contains the names in the order shown above. The code and state
patterns support those names, but the UI consumer's full indexing path has
not been traced. The callback pointers themselves are verified independently
of these names.

## Observed processing structures

### ID 0 — Filter candidate

[verified] Initialization copies five float words with values `[1, 0, 0, 0, 0]`
from file `0x4DAF0`. The short process callback calls runtime `0x01C07E10`
(application file `0x8BD50`) from file `0x1A7DE`.

[inferred] The coefficient layout and nearby UI strings `Low Pass`, `Band
Pass`, `High Pass`, `CutOff`, and `Q` support a configurable filter. The
coefficient order and complete transfer function remain unresolved.

### ID 1 — Reverb candidate

[verified] Three constructor paths allocate 164, 332, or 276 bytes of state.
One path builds eight stages with lengths `59, 227, 419, 617, 137, 313, 509,
727` and alternating float coefficients approximately `-0.6` and `+0.6`.
The helper at runtime `0x0201A94E` initializes a stage with a 16-bit count at
`+0`, a 16-bit position at `+2`, a buffer pointer at `+4`, and a float
coefficient at `+8`; allocation is four bytes per element. Another observed
ring has 10,261 elements.

[inferred] This is a network of delay stages consistent with reverberation.
Its equations and three mode bindings remain unresolved. These observations
do not establish a particular published reverb design.

### ID 2 — Delay candidate

[verified] Initialization allocates 44 bytes of state and a 110,294-byte ring
for 55,147 two-byte elements. The process code loads adjacent signed 16-bit
samples at file `0x1C26C` and `0x1C270`, and advances the write pointer by two
bytes with a wrap check. It includes signed 16-bit saturation before a store.

| State offset | Observed or candidate meaning |
| --- | --- |
| `+0`, `+4`, `+8`, `+12` | Ring count, buffer start, buffer end, write pointer |
| `+16`, `+20` | Coefficient and history candidates |
| `+24`, `+28` | Current/target delay candidates; initial float value 13,235 |
| `+32`, `+36`, `+40` | Feedback/mix/filter coefficient candidates; initially about 0.3 |

[inferred] Adjacent sample access and intervening float operations support
an interpolated delay. The feedback, wet/dry mix, smoothing, and sample-rate
conversion equations have not been established.

### ID 3 — Distortion candidate

[verified] Initialization allocates 268 bytes of state. The code uses several
coefficient blocks and helpers at runtime `0x0201C400` and `0x0201C652`.
[inferred] The UI ordering suggests distortion. Its final tanh lookup stage,
including scaling, interpolation, sign, saturation and a separate gain, is now
traced in
[19 — Effects lookup mathematics](19-effects-mathematics.md). The complete
filter arrangement, gain mapping, and mode bindings remain unresolved.

### ID 4 — Chorus candidate

[verified] Initialization allocates 44 bytes of state and an 884-byte buffer;
it sets a ring parameter to 220 and an end pointer to buffer start plus 876.
The process callback loads the sine table address `0x02053CB4` at file
`0x1D178`. Its complete contents are reproduced in
[19 — Effects lookup mathematics](19-effects-mathematics.md).

[inferred] The small delay ring and sine lookup support a modulated delay.
The phase increment, interpolation, modulation depth, and mix remain
unresolved.

The cross-repository analysis independently classifies this shape as a
chorus/flanger process with LFO/sine-table modulation. That corroborates the
V15 interpretation while leaving the V15 parameter and sample equations open.

### ID 5 — Phaser candidate

[verified] Initialization allocates 96 bytes of state and uses a substructure
at `+48`. The process code contains several coefficient groups and lookup
operations, including three interpolated tanh lookups before its sample loop.
[inferred] The UI ordering suggests phaser; the number of stages,
coefficient equations, and feedback topology remain unresolved.

## Limits and next checks

The instruction patterns and data above provide entrypoints for further
analysis, not an audio-equivalent effects implementation. In particular:

- Resolve the floating-point instructions and their rounding/conversion
  behavior before treating guessed equations as decoded formulas.
- Trace the UI name and parameter indices into the callback records.
- Recover each state field's read/write behavior and loop boundaries.
- Confirm the sample rate and parameter scaling at the caller.
- Compare a reconstructed implementation against recorded device audio
  before claiming behavioral equivalence.

The prior [AL-255 synth-engine analysis](https://github.com/AL-255/FM-1-RE/blob/95eca8488ac8c3b6f86287b2d3d43678e03e271a/docs/io/04-synth-engine.md)
provided initial search locations. Addresses, table bytes, function extent,
and state accesses reported as verified here were checked against the V15
application above, rather than transferred from that earlier image.
