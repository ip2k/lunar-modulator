# Postmix master-gain traversal

## Change

[verified] `fm1_app_render` records the post-limiter scope and peak before it
applies master gain. For non-unity gain, the renderer now applies that gain to
each stereo frame in the same traversal that records the pre-gain scope and
peak. Unity gain takes a separate meter-only loop, so it does not pay a
per-frame gain conditional. The helper is `static inline` and adds no external
call boundary.

## Equivalence evidence

[verified] `tests/test_native_postmix_equivalence.py` compiles the production
helper against the original two-pass reference with `-O0` and `-O2`, without
fast-math or floating-point contraction. Its 288 cases compare output buffers,
all scope entries, scope position, and peak state byte-for-byte. Cases include
zero, fractional, and unity gain; silent, ordinary, and edge-value samples;
zero/short/wrapping/full test blocks; and zero, finite, infinite, and NaN
initial peak values. Both optimization-level runs pass.

## Limits

[inferred] The non-unity path removes one traversal of `2 * frames` output
samples, but no device timing or speedup has been measured. The owner’s current
master setting is unity gain, where this change keeps one meter traversal and
adds only a single gain branch before it. A fresh source-bound catalogue and
target build are still required because `fm1_app.c` and its new helper changed.
