# 2026-10-29: dev-kit timing of the perf-levers images at 320 MHz

Three images from `feature/2026-10-28@perf-levers` (`cddf3ded`) ran on the
AC79 dev kit on bench01: UART through the Tigard, audio through the KA6. This
was a dev kit, not an FM-1; nothing was sent to the FM-1. Codex's protocol was
followed: acknowledged UART ROM entry, app-only write of `[0x4000, 0x97000)`,
capture armed before one reset per image, never retried.

Ticks are the 24 MHz timer. The budget is 34,829 ticks (1,451 µs) per 64-frame
block. The owner's buffered rule (2026-10-28) requires mean ≤ 85% (29,604).

| | fixed12-msfa | cap8-msfa | cap8-trunc12 |
|---|---|---|---|
| producer mean, cases 0–3 | 21,063 / 24,615 / 27,060 / **30,566** | 21,185 / 24,739 / 26,163 / 26,073 | 20,283 / 23,122 / 24,230 / 24,164 |
| producer max, worst case | 41,678 | 37,317 | 35,195 |
| consumer mean range | 28,298–28,941 | 28,300–28,890 | 28,292–28,871 |
| late producer blocks | 17 | 2 | 1 |
| consumer late, DAC gaps, faults | 0 | 0 | 0 |
| case hashes and fold match host replay | yes | yes | yes |
| mean rule | **fail** (case 3) | pass | pass |

[verified: `scratch/bench-2026-10-29/*/uart.bin`, parsed by
`tools/devkit_pipeline_result.py`]

- Against V225 (fixed12, no 51/47 path), producer means fell from
  23,779 / 27,227 / 29,583 / 32,986 and late blocks from 1,589 to 17. V225 had
  no worst-block recorder; these images do, and its cost (about 6 marks of
  23 ticks per block) is inside their numbers.
- The worst blocks of cases 2 and 3 are the first block of each case's
  segment, the note-on burst; `dispatch` dominates (cap8-msfa case 3:
  22,996 of 37,317 ticks).
- trunc12 lowers cap8's means by 4–7% in cases 1–3.
- Every capture has a DAC-open transient of −6.4 to −7.7 dBFS about 1.7 s
  before the music. No dropout was found by an uncalibrated screen; this is
  not the 30-minute analog soak.
- The SDK's printf split each `LUNAR_WORST_BLOCK` receipt across lines; the
  parser now joins those continuations.

Not done: the 360 MHz images (`--sys-clk 360 --stock-power`). The msfa ones
have 96 B of heap headroom against the 128 B gate, so they were not run; that
is an owner decision. No A/B listening or 30-minute soak yet; the A/B excerpts
are in `scratch/bench-2026-10-29/ab/` (not tracked).
