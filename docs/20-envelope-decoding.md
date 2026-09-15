# 20 — Envelope update and stage transitions

## Exact image and function

[verified, 2026-09-14] This analysis uses the 581,564-byte `FM-1_015`
application with SHA-256:

```text
306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203
```

The helper occupies application file `0x1896..0x1966` (end exclusive),
runtime `0x020019B6..0x02001A86`. Its 208 bytes have SHA-256:

```text
c49189757d64e629c1a7da7c68729bedd1d46362a502b4d8421dde7d2965c752
```

The entry pushes return and saved registers; the return is at file `0x1964`.
The next routine begins at `0x1966`. Calls at file `0x85F7C` and `0x86042`
both target runtime `0x020019B6`. Those calls occur on different paths in
the voice routine; their presence does not mean the envelope runs twice per
audio block. File offsets and runtime addresses use the map in
[13 — Firmware decoding](13-firmware-decoding.md).

All **79 instruction boundaries / 208 bytes** were checked against the local
V009 application and its vendor disassembly. The V009 helper at file
`0x1888..0x1958` matches **204 bytes**. The four changed bytes occur only in
the data-base immediate and level-table displacement. Every control-flow
and arithmetic encoding is unchanged. The V009 helper SHA-256 is
`49f36b25663b264c7eda8cb2cca949d53830b7bb1bbe047c1f688c69804571b8`;
its application SHA-256 is
`73f37ac3db15f5e70ae718dac43ab30055a0e27f659ae1b3eeb4c51a39b1616a`.

## State layout

[verified accesses; inferred field names] The input register `r0` points to
the envelope state. The helper returns the current level in `r0`.

| Offset | Width | Interpreted field |
| --- | --- | --- |
| `+0..+3` | Four unsigned bytes | Stage rates |
| `+4..+7` | Four unsigned bytes | Stage levels |
| `+8` | 32 bits | Output-level adjustment |
| `+12` | 32 bits | Rate scaling |
| `+16` | 32 bits | Current level |
| `+20` | 32 bits | Target level |
| `+24` | 32 bits | Stage index |
| `+28` | 32 bits | Stored increment |
| `+32` | Byte | Rising flag |
| `+33` | Byte | Key-down flag |

These accesses establish at least 34 bytes of state, not its allocation size
or padding. The arrays use bytes, so this layout must not be replaced with
the original C++ class layout, whose arrays contain integers.

## Control flow and comparison evidence

[verified] The helper updates stages below 3. Stage 3 updates only when the
key-down byte is zero. Other stages return the stored level unchanged.
An update that reaches its target clamps to that target, increments the
stage, and calculates the next stage's parameters if the new index is below
4. There is at most one stage transition per call.

Seven encodings initially missing from the partial decoder are explicitly
identified in the V009 vendor listing. The same bytes occur at these V15
offsets:

| File offset | Bytes | Meaning |
| --- | --- | --- |
| `0x18B4` | `34 f4 41 45` | Signed maximum of current level and the attack threshold; paired with the increment load |
| `0x18CA` | `84 ed 4a 50` | Return path if updated level is signed-less-than target |
| `0x18FA` | `04 ee 32 50` | Return path if updated level is signed-greater-than target |
| `0x192C` | `b2 ee 10 00` | Execute the following assignment when the calculated target is at most 16 |
| `0x1938` | `95 ee 00 04` | Execute the following assignment when the new target is at most current level |
| `0x194E` | `31 ed 3f 00` | Execute the following assignment when the calculated rate is at least 63 |
| `0x195C` | `31 22` | Set bit 2 in the masked rate fraction |

The two return branches target file `0x1962`, which loads the stored level.
The three conditional assignments respectively clamp the target to 16,
clear the rising flag, and clamp the rate to 63. They condition **one following
instruction**; treating their bodies as unconditional changes the envelope.
The signed-maximum instruction is paired with a load that does not depend on
its destination, so that pair introduces no operand-order ambiguity here.

## Arithmetic recovered from the instructions

Let `L` be current level, `T` target, and `I` the stored increment. The rising
path first raises `L` to at least `1716 * 65536`, then adds:

```text
(((0x11000000 - L) arithmetic_shift_right 24) * I) << 6
```

The falling path subtracts `I << 6`. Rising values clamp when `L >= T`;
falling values clamp when `L <= T`. Comparisons are signed. Arithmetic and
shifts operate on 32-bit words; source-level equivalence below excludes
overflowing or malformed states.

For a new stage, its level byte is mapped through `S`. Values below 20 use
the byte lookup at file `0x4E8AA`, runtime `0x0204E9CA`; other values use the
level byte plus 28. The table contains:

```text
0, 5, 9, 13, 17, 20, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 42, 43, 45, 46
```

Its complete 20-byte SHA-256 is
`319a4da2eaaa74752d129db6f615a78431d5d113d5aa2d51bdc7b28c016f271b`.
The new target and increment are formed as follows:

```text
T = max_signed(((S << 5) & 0x1FC0) + output_adjustment - 4256, 16) << 16
q = min_signed(((unsigned_rate * 41) >> 6) + rate_scaling, 63)
I = (4 | (q & 3)) << (2 + (q arithmetic_shift_right 2))
```

The rising flag is set exactly when the new target exceeds the current level.
The rate calculation has no observed lower clamp. Valid parameter ranges
must therefore come from the initialization and parameter paths, not from
assuming this helper sanitizes arbitrary input.

## Comparison with original MSFA

[inferred algorithm correspondence, with verified arithmetic above] The
original Google [envelope implementation](https://github.com/google/music-synthesizer-for-android/blob/master/app/src/main/jni/env.cc)
has the same stage gate, attack threshold, rise/fall update, table values,
target conversion, and rate calculation. V15 incorporates the stage-advance
work directly into this helper. For the documented 0..99 level domain, the
masked shift above equals halving `S` with integer truncation and then
multiplying by 64. This equivalence need not hold for malformed larger levels.

The important representation difference is the increment. Google's
[block-size definition](https://github.com/google/music-synthesizer-for-android/blob/master/app/src/main/jni/synth.h)
sets `LG_N` to 6 and puts that factor in the increment calculation. V15
stores an increment **64 times smaller**, then applies the factor of 64 in
both update paths (`0x18C2` and `0x18F2`). Under the normal parameter domain,
this is the same block scaling. It does not establish a sample rate or
wall-clock envelope duration.

The original [envelope interface](https://github.com/google/music-synthesizer-for-android/blob/master/app/src/main/jni/env.h)
documents rates and levels in 0..99 and a logarithmic level representation
with `2^24` per doubling. Those comments support the field interpretation;
the FM-1 initialization, key-down/retrigger handler, complete gain/modulation
path, and valid state ranges still require their own inspection.

The three primary files were checked on 2026-09-14. Their source hashes are:

```text
env.cc  83bf4debc5ea480466892ccf572adcc27b55ee2ac3c21979485e6fa73e5b9ccc
env.h   8eb661f6c5e4798b0a50f7a81d6493fb8419e1cf9966fbe7911c541b5a277603
synth.h 96f1881020f67e12e3d8ac5d79fc546cab9407605d5274d58ba3b4576b8aaf73
```

The comparison uses these original Apache-2.0 Google sources and the
[V009 vendor listing preserved by AL-255](https://github.com/AL-255/FM-1-RE/blob/95eca8488ac8c3b6f86287b2d3d43678e03e271a/analysis/disassembly/app_pi32v2_objdump.txt).
It does not incorporate later envelope modifications from local projects.
No execution on the FM-1, timing measurement, or hardware audio equivalence
is established by this static analysis.
