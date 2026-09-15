# 17 — V15 operator state and attenuation interpolation

This is an offline reconstruction of the three-operator path in the exact
`FM-1_015` application. It supplies a concrete state contract for further DSP
work; it is not a complete voice emulator or evidence of hardware equivalence.

## Evidence boundary

- **[verified]** Application SHA-256:
  `306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203`.
- **[verified]** Kernel bytes: file `0x85064` inclusive to `0x85284` exclusive,
  544 bytes, SHA-256
  `92017cba35125f6258bf30bcbe4ae3008babf18afbc0e1c6e4e6cca975e7c9e7`.
- **[verified]** Its RAM entry is `0x01c01124`, using the independently checked
  startup-copy map: file `0x83f40` maps to RAM `0x01c00000`.
- **[verified]** The containing render routine is file `0x85284..0x85b62`,
  SHA-256 `d382c2d836c686c9cce9dba22142eba5556687991c685f39275fa6b38dad0680`.
- **[inferred]** Semantic names are ours. They are supported by the V15
  loads, stores, arithmetic, call sites and full lookup-table matches.
  The older V009 listing is an instruction-decoding reference, not a source
  of V15 addresses or proof of unchanged behavior.

All offsets below are decoded-application file offsets, unless marked RAM.
Re-extract a locally obtained package with `tools.fm1_package.inspect_and_extract`
and verify the application hash before applying these annotations.

## Calling convention

The V15 call at `0x85554` enters the kernel at RAM `0x01c01124`.

| Argument | Reconstructed meaning | V15 evidence |
| --- | --- | --- |
| `r0` | Output pointer, 64 signed 32-bit samples; the kernel assigns samples | Saved at `0x8506c`; indexed word store at `0x8525e` |
| `r1` | Base of three consecutive 16-byte operator states | Phase loads at `0x85070/74/78`; frequency loads at `0x85178`, `0x851ea`, `0x8525a` |
| `r2` | First operator's starting attenuation, with the zero sentinel already handled by the caller | Caller `0x85362..0x85376`; interpolation at `0x850c8..0x850d4` |
| `r3` | First operator's new target attenuation | Caller conversion at `0x85366..0x85372`; consumed at `0x850ce` |
| Entry stack `+0` | Pointer to two feedback-history words | Caller stores at `0x8554e/50`; kernel loads entry stack `+0` at `0x8506e` |
| Entry stack `+4` | Feedback shift parameter | Caller `0x8554a/4c`; kernel loads at `0x850cc`, adds one at `0x850d6` |

**[verified]** The outer render routine transforms its feedback parameter
before this call. At `0x852fc..0x85308` it forms
`kernel_shift = min(outer_shift + 2, 16)` for the ordinary nonnegative domain.
The kernel adds one more bit of arithmetic right shift. Consequently the
three-operator path uses `min(outer_shift + 2, 16) + 1` bits, not simply
`outer_shift + 1`.

**[verified]** The kernel pushes thirteen words and allocates 24 local bytes.
Consequently its adjusted stack offsets `+76` and `+80` refer to entry stack
offsets `+0` and `+4`. There is no sample-count argument to this kernel: the
loop exit compares its counter with 64 at `0x85272`.

**[verified]** The outer render caller at `0x86064..0x8607e` supplies
`r1 = voice + 260`, algorithm from `voice + 452`, feedback pointer
`voice + 440`, feedback shift from `voice + 448`, and a stack sample count of
64. These are direct V15 operands. A complete voice-structure definition and
every caller's validity constraints remain outside this reconstruction.

**[verified]** The dispatch immediately before this call distinguishes three
paths: algorithm 31 branches from `0x8553a` to `0x856cc`; algorithm 5 branches
from `0x8553e` to `0x8578e`; and algorithms other than 3 branch from `0x85544`
to `0x8591e`. The remaining algorithm-3 path reaches the three-operator call
at `0x85554`. **[inferred]** The other two branches enter one-operator and
inlined two-operator feedback paths. Their presence does not mean they call
this three-operator kernel. Earlier buffer/feedback conditions still govern
whether this dispatch is reached.

## The 16-byte state has a lifecycle

| Byte offset | Meaning at entry to rendering | What rendering does |
| --- | --- | --- |
| `+0` | Previous block's target attenuation | Reads it; zero is treated as the initialization sentinel 16383 |
| `+4` | New level value with 14 fractional bits discarded during conversion | Replaces it with `16384 - (level >> 14)` using arithmetic right shift |
| `+8` | Phase increment per sample | Adds it to the working phase each sample |
| `+12` | Phase accumulator | Loads the initial phase; the outer render routine advances the stored phase |

**[verified]** Before computing a new level, `0x85efc/0x85efe` copies state
`+4` to state `+0`. The new level is stored at `0x86052`. The conversion to
target attenuation occurs at `0x85366..0x85372` for the first operator, and
`0x85086..0x850a2` for the other two. Thus `+4` has different units before and
after rendering. Naming it simply `gain` loses an important part of the
contract.

**[inferred]** The level is a logarithmic level input, based on its subtraction
from the attenuation origin and the following log-sine/exponent evaluation.
The entire upstream envelope and modulation calculation is not decoded here;
the field must not be described as a linear amplitude.

### Parallel instruction bundles matter

**[verified]** The vendor listing marks paired instructions with `#`; the V15
encodings include the same pairing bits. **[inferred]** Their operand reads
must precede their combined writes. For example, the pair at
`0x850a0/0x850a2` moves 16383 into `r0` while storing the prior `r0` target in
state `+36`. Similarly `0x8536e/0x85372` changes `r2` to 16383 while the store
uses the old state pointer in `r2`. Treating these rows as sequential Python
statements produces invalid stores and the wrong attenuation.

This interpretation is supported by dataflow and the instruction-pair
markers, but has not been executed on a pi32v2 instruction emulator here.

## Per-sample attenuation

**[inferred from verified V15 instructions]** For each operator, let `old` be
state `+0`, `level` its new input, and `start = old if old != 0 else 16383`.
The integer computation is:

```text
target = 16384 - arithmetic_shift_right(level, 14)
step   = arithmetic_shift_right(target - start + 32, 6)
attenuation[sample] = start + (sample + 1) * step  # sample = 0..63
```

The `+32` is rounding before division by 64. It does not force the final
sample to equal the target. For example, `start=8000`, `target=8063` gives
`step=1`, first sample 8001 and last sample 8064; `target=7968` gives a
zero step. The next block begins from the stored target, not the rounded
last-sample accumulator.

Even starts and targets inside `0..16384` can produce sample attenuations
outside that interval: `start=33,target=0` ends at -31, while
`start=16352,target=16384` ends at 16416. For endpoints in that interval, the
rounded ramp remains within `-31..16416`; its final error relative to the
target is between -31 and +32. A complete block model must retain these
values or explicitly reject such blocks. Clamping them changes the decoded
arithmetic.

**[verified]** For the second and third operators, V15 materializes 16416
(`16384 + 32`) at `0x850aa`, subtracts the sum of the starting attenuation
and shifted level, and arithmetic-shifts by six at `0x850b0/0x850c2`.
The first operator uses `32 - r2 + r3` at `0x850c8..0x850d0`. Initial increments
occur before the first lookup. Per-sample increments are at
`0x85262..0x8526c`.

**[verified]** This path has no clamp to 16383: zero level converts to target
16384. The caller's audible-work threshold compares with 16284/16285 at
`0x85378..0x85384`, but that does not prove all three operators are individually
bounded below the threshold when the cascade executes. Malformed or extreme
states require an explicitly defined 32-bit model, not Python's unbounded
integer arithmetic.

### Concrete difference from V009

**[verified]** The V009 kernel at file `0x85824` reads state `+16/+32` for its
second and third level conversions (`0x85832`, `0x8584a`) and computes their
local increments without the V15 rounded `/64` ramp. V15 instead reads level
inputs from `+20/+36`, reads previous attenuations from `+16/+32`, and forms
the two rounded slopes using the 16416 constant.

**[inferred]** This corrects the specialized cascade's use of the current
level and smooths its attenuation over the block. The byte changes establish
different arithmetic; they do not establish why the manufacturer changed it,
an audible improvement, or a general change to all rendering paths.

## Feedback, phases and lookup scaling

**[inferred from verified dataflow]** With signed 32-bit wraparound, each
sample performs the following structure:

```text
feedback = arithmetic_shift_right(history0 + history1, feedback_shift + 1)
y0 = lookup(phase0 + feedback, attenuation0) << 13
y1 = lookup(phase1 + y0,       attenuation1) << 13
y2 = lookup(phase2 + y1,       attenuation2) << 13
output[sample] = y2
history0, history1 = history1, y2
phase0 += increment0; phase1 += increment1; phase2 += increment2
```

The lookup uses the log-sine/exponent tables described in
[16 — Operator mathematics](16-operator-mathematics.md). It uses 24 phase
bits; the low 12 bits are discarded for table selection. For attenuation
inside the scalar helper's domain, its negative half cycle uses one's
complement before the final left shift.

**[inferred from verified instructions]** A general lookup must reproduce the
signed-16-bit branch on the combined logarithm, including ramp underflow:

```text
position = unsigned32(phase) >> 12
index = position & 1023
if position & 1024: index ^= 1023
logarithm = log_sine[index]
if position & 2048: logarithm |= 0xffff8000
x = unsigned32(logarithm + attenuation)
magnitude = (exponent[(~x) & 1023] + 4096) >> ((x >> 10) & 31)
representative = magnitude if signed16(x) >= 0 else ((magnitude | 0x70000) ^ 0xffff)
output = signed32(representative << 13)
```

The sign comes from `signed16(x)`, not only the phase quadrant. At the positive
peak with table logarithm zero, attenuation -1 produces output -8192; at the
negative peak it produces zero. These are consequences of the encoded
integer operations, not a mathematical sine approximation or a claim about
the intended audible behavior.

**[verified]** The feedback shift opcode at `0x850f2` is arithmetic, not
logical. Lookup index formation at `0x850f6` is logical right shift followed
by explicit masks: `0xc00` selects the quadrant and `0x3ff` selects the cell.
Exponent shift counts are explicitly extracted from five bits at positions
10 through 14. No extrapolation about the CPU's variable-shift behavior for
negative or greater-than-31 shift counts is needed for ordinary feedback
parameters: outer feedback shifts `0..15` produce counts between 3 and 17.

**[inferred]** A reference implementation should wrap additions and the final
left shifts to 32 bits, reinterpret the feedback sum as signed before its
arithmetic shift, and retain the exact first-sample ramp increment. Applying
a final-only modulo operation can change feedback when modeling extreme
states. The general integer lookup above covers the rounded ramp's
`-31..16416` interval. The full envelope/modulation pipeline's valid starting
and target ranges are not established here.

**[verified]** History words load at `0x8507c/0x85082`, shift through
`r11/r15` at `0x850ea..0x850f2`, and are written at `0x85278/0x8527c`.
The feedback source is the final third-operator output in `r15`, not an
assumed first-operator output. Phase increments occur at
`0x851c4/0x85236/0x85270`. The kernel does not store its working phase
registers back into the operator states.

**[verified]** Immediately after the kernel call, `0x85558..0x85564`
advances the second and third stored phases by their frequency times 64.
The render epilogue at `0x85b4c..0x85b50` advances the first selected phase by
frequency times the outer sample count.

## Python reference API and validation

`tools.fm1_operator` implements the bounded integer reference described above:

- `OperatorState(previous_attenuation, level, phase_increment, phase)`
  describes the four pre-render words. It accepts starting attenuations and
  converted targets in `0..16384` and explicit 32-bit phase words.
- `attenuation_ramp(state)` returns the converted target and 64 sample
  attenuations, including rounding overshoot and the zero sentinel.
- `lookup_sample_word(phase, attenuation)` returns the signed 32-bit output
  after the lookup's left shift. It retains the combined-logarithm sign test.
- `render_three_operator_block(states, feedback, kernel_feedback_shift=16)`
  returns samples, final history, converted targets and working phases.
  Its input combines the first operator's caller preparation with the kernel
  contract; it is not a raw register-entry interface. `kernel_feedback_shift`
  is the already adjusted stack argument, restricted to `2..16`.

**[verified]** An independent static review found the implementation consistent
with the 183 decoded kernel instructions in this stated domain: feedback sum
wraps before arithmetic shift; the ramps increment before sampling; all
three phase/modulation sums wrap; and history contains the last two final
operator outputs. Updating each working phase immediately after that
operator's lookup gives the same next-sample state as the firmware's
staggered updates because no intervening instruction reads the updated phase.

**[verified]** The focused operator and DSP suite passes 32 tests, including
all 4096 phase cells at four attenuations against the separate scalar helper,
analytic carrier checks, underflow vectors, signed/unsigned word equivalence,
and input-domain checks. These establish internal numerical consistency.
The scalar and block implementations share generated tables; those comparisons
are not independent instruction execution. Parallel packet timing remains an
inferred ISA behavior pending a separate execution check or authoritative
hardware evidence.

## Remaining work

- Independently execute the paired-instruction semantics and establish
  shift-count behavior outside the ordinary feedback parameter range.
- Finish the caller's conditional dispatch, buffer accumulation and all
  algorithm-specific paths. A three-operator kernel does not imply every
  algorithm routes through it.
- Decode the complete level/envelope/modulation calculation and establish
  the valid input-state domain.
- Compare a full reconstructed kernel with a trusted instruction emulator
  and controlled captured audio. Current validation is offline static
  reconstruction only.

### Prior work used as evidence

AL-255's [FM-1-RE disassembly](https://github.com/AL-255/FM-1-RE/tree/95eca8488ac8c3b6f86287b2d3d43678e03e271a/analysis/disassembly)
provides the V009 vendor-objdump listing used to identify exact instruction
encodings and cross-version differences. The state and phase interpretation
was rechecked against V15 bytes; historical symbol names remain hypotheses.
No vendor firmware payload is included in this document.
