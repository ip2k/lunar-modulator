# Resampler intermediate inlining experiment

Source-only experiment based on `d168869b5aa77385ccbecaaf32dbaa2379d65887`.
Candidate source checkpoint: `c0df27b43bff97f778b1c29d115bb023236b7a58`.
Branch: `codex/resampler-inline-experiment-20261016`. Do not integrate on the
strength of the isolated object result: full thirteen-engine link/RAM review
and current-profile target codegen remain required.

## Hypothesis and implementation

[verified: source diff] Only in `FM1_HOT_DSP_RAM && __ELF__` builds, change the
intermediate helper from `noinline, section(".ram_dsp")` to `always_inline`.
Ready-pop and ready-push retain `noinline, section(".ram_dsp")`. Arithmetic,
loop order, ring updates, state fields and coefficient tables are unchanged.
The sole production intermediate caller is ready-pop. Thus the FIR body moves
into its RAM caller, rather than moving the render loop into XIP. The existing
placement regression now verifies the absence of a separate intermediate
symbol and the continued RAM placement of ready-pop.

## Host differential evidence

[verified] `python3 tools/native/compare_resampler_inline.py` compares the
candidate against the original header read directly from the immutable base
Git object. It does not reimplement the reference algorithm. Commands run:

```
python3 tools/native/compare_resampler_inline.py
python3 tools/native/compare_resampler_inline.py --opt=-Oz
python3 tools/native/compare_resampler_inline.py --opt=-O3 --sanitize
```

Each run passed **576,000 bit-exact outputs and complete post-output states**,
plus comparisons after initialization and every partial or whole input push.
Each observed **5,820 intermediate-ring wraps and 1,199 active tail states**.
All state bytes are compared with `memcmp`, including padding initialized to
an equal `0x5a` sentinel before init; unchanged field declarations and a size
static assertion establish the same layout. This is stronger than comparing
only output samples or selected counters.

Eight rate pairs include 47,872.34 -> 44,118 (both Drums and SixOp use the
same corrected engine rate), 47,872.34 -> 44,117.6, 47,872.34 -> 24,000,
96,000 -> 44,118, the 4:1 endpoint, equal-rate pass-through, zero input rate
and an unsupported upsample ratio. Twelve patterns cover initial silence,
negative and alternating signed zeros, impulses, sustained nonzero then full
FIR tails, deterministic broadband values, alternating polarity, a quiet NaN
payload, positive/negative infinities, subnormal/minimum-normal values and
maximum finite floats. Both checked and trusted ready paths are exercised.
No promise about preserving signaling-NaN payloads or alternate FP rounding
modes is added.

[verified] The existing `engines/test/resampler_test.cc` harness was compiled
standalone at `-O2`: pass-through had 100,000 samples and zero mismatches;
chunking at 47,872.34 and 96,000 each had 25 patterns and zero differences;
extreme-input cases had no nonfinite outputs for their finite bounded inputs,
and their NaN/infinity bursts retired within 69/68 outputs. Existing refused
rate cases included negative, NaN and infinity inputs. These are host checks,
not FM-1 throughput measurements. The differential Darwin build adapts only
the ELF section spelling to Mach-O; Apple ld warns that the custom text
section lacks code-section flags. This does not affect the bit comparisons.

## Pinned pi32v2 isolated codegen

[verified] Hera bounded container uses the existing frozen stage-7 toolchain
and image `sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`.
Two CPUs, 2 GiB RAM, 2 GiB total swap allowance, docker-batch.slice, network
none, read-only root and read-only toolchain, unique project/session labels.
The exact candidate checkpoint was transferred through the Git exchange repo
and checked out in an isolated detached worktree. No hardware was accessed.

Reproduction driver: `notes/2026-10-16-resampler-inline/codegen.py`.
Retained raw evidence on Hera:
`/home/claude/mvave-fm1/resampler-inline-experiment-20261016/`.
Local mirror: `scratch/target-codegen/` (ignored).
The probe exposes ready-pop and ready-push and uses shared coefficient tables;
it is a non-LTO object experiment, not an engine/application link.

| Optimization | Original RAM code bytes | Candidate | Delta |
| --- | ---: | ---: | ---: |
| `-Oz` (Drums current catalogue setting) | 978 | 1026 | +48 |
| `-Os` (SixOp current override) | 1022 | 1004 | -18 |

[verified: pinned objdump] Original has one static call site inside the
2-iteration loop, executing intermediate twice for a nonempty output. Candidate
has no intermediate symbol and no call instructions inside ready-pop. Pop and
push remain in `.ram_dsp`. Original local stack allocations are 36/20 bytes
for intermediate plus 4/8 bytes for pop (`-Oz`/`-Os`), in addition to saved
register frames. Candidate pop allocates 52/36 local bytes plus one register
frame. Removing the extra call frame increases local spill requirements; it
is not valid to infer a cycle win from call count alone.

Disassembly SHA256:

| Object | Original | Candidate |
| --- | --- | --- |
| `-Oz` | `5843ad139ac3d1664a5c0a776298bcbaf12e0b90e3ef20dca1021c309e132bb6` | `ea3e24f02ca77a578372b1cdc13bee7fd34bc833ac4d5da0e4fa79c059796723` |
| `-Os` | `1550d9afeefa9c8d87460a8a1aaceae8e06288a944144ffa2b0d58c014a76457` | `e9369dd672b9915b75bf2e182d9d486ba5852d4283eb66c17ca9838e97e786cb` |

## Limits and next dependency

No complete thirteen-engine build or link was run for this candidate. The
prior stage-7 `.ram_dsp` size of 15,524 bytes does not establish candidate fit.
Run a fresh exact-source current-profile catalogue+application link, review
RAM and image budgets and real linked Drums/SixOp disassembly, and then have
the Mac coordinator decide whether a concrete hardware experiment is warranted.
No merge, flash, USB, MIDI, power action, speedup, musical acceptance or release
readiness is claimed.

[verified: tool readiness] Rarefaction and Serena select the other active
`/Users/likwid/Developer/mvave-fm1-firmware` checkout. Bounded orient/find_symbol
queries returned its older resampler body and caller, which visibly differ
from the experiment base. Their global selection was not changed. Source
inspection and pinned compiler/objdump supply this experiment's evidence.

[verified] Focused pytest regression command completed with **13 passed**:
`test_resampler_stage1_placement.py`, `test_resampler_table_placement.py`,
`test_resampler_push_ready_placement.py`, `test_engines_resampler_ready_path.py`,
`test_engines_resampler_zero_fast_path.py` and
`test_engines_resampler_zero_history_reference.py`. `git diff --check` and
Python byte compilation of both experiment drivers passed.
