# Multi-sound parity fixtures after immutable lock events

[verified] Source checkpoint `94952e1f5e82e8c993b0881b09e319b55a1170a4` on
`fix/2026-11-01@seq-panel-parity-budget`, based exactly on combined freeze
`951ca6eb053c7fde82cd17baed949fd43528dab0`. Coordinator-approved scope: four
Room fixture substitutions and directly related test setups; no production
selection, refusal, rate, state, allocation or RAM-budget changes. No hardware
commands or WASM regeneration occurred.

## Cause and counted costs

[verified] `fm1_app_select` returns `FM1_APP_SELECT_RAM` (-4) before creating
Shapes in the former Macro + Plate + Shapes arrangement. Standalone Shapes
loads. `ram_of` sums actual instance/event/cache sizes; it does not add the
`FM1_APP_SEQ_BUDGET` macro. Immutable events increased the event array from
3,264 to 9,792 B (+6,528); the eight-track core grew from 32,072 to 32,080 B
(+8). The counted increase is **6,536 B**, rather than the 8 KiB implementation
budget change. The unchanged production limit is **387,924 B**.

[verified] At 44,118 Hz in the frozen native 64-bit binary: empty fixed meter
82,408 B; Macro 32,880; Shapes 207,872; Plate 65,728; Room 41,200; Ensemble
4,752; each extra sound adds 512 B mix scratch. Room saves 24,528 B per chain.
The fixed 43,156 B header comment now names only the sequencer instance,
events, pending record, UI bound and click subtotal; other counted components
remain separate. Neither subtotal nor host meter proves aggregate device fit.

| Scenario | Former Plate total | Over limit | Room load total | Load headroom |
| --- | ---: | ---: | ---: | ---: |
| seq-panel-tracks | 389,400 | 1,476 | 364,872 | 23,052 |
| mod-voice-routes | 389,400 | 1,476 | 364,872 | 23,052 |
| mod-multi-panel | 394,152 | 6,228 | 369,624 | 18,300 |
| multi-panel | 394,152 | 6,228 | 369,624 | 18,300 |

[inferred from verified sizes] Subtracting the SS2 delta reconstructs the
unchanged-engine pre-SS2 totals as 382,864 and 387,616 B, respectively. These
are arithmetic reconstructions, not execution of a historical binary. Setup
loads units before the script resets its track count; `multi-panel` then uses
two tracks and its final native meter is 348,792 B (39,132 B remaining).

## Coverage preserved

[verified] Exactly `seq-panel-tracks`, `mod-multi-panel`, `mod-voice-routes`
and `multi-panel` use Room instead of Plate. Their notes, panel gestures,
routes, sidecar, PCM and screen assertions remain. **29 other scenarios still
use Plate**. Mix and Decay in both effects are continuous float parameters,
UIDs 1 and 2, range 0..1, defaults 0.3 and 0.5, on page 0
(`engines/src/mi_fx.cc` and `fx_room.cc`). Both have two pages. Thus the master
Mix/Decay gestures and SELECT detents retain their targets. Room has Blur/Width
on its second page, which the updated test comment names correctly.

[verified] Four directly related test setups now use Room: insert/master
modulation gesture, multi-sound replay, current-sound log, and the first
refusal figure test. The general Plate chain and golden gesture traces remain.
The FX navigation test retains its ALGORITHM gesture and now asserts that
Plate is refused at 101% and Ensemble is loaded into the current sound's
insert. The first-refusal test still checks both rejected engines and distinct
rounded need figures. The old four Plate initial setups are retained as RED
witnesses: each returned -4; the new 108-scenario setup scan has no failures.

## Validation and limits

[verified] Reused the build worker's exact frozen native/musl/WASM products
read-only. Source differences affecting execution here are fixture choices;
the app source change is a comment. Six existing pytest checks passed via a
small prebuilt-tools fixture override: the five affected setup/navigation tests
and the complete native panel-scenario replay test. All 108 initial scenario
setups passed at their declared rates/parameters; this scan does not play each
scenario to completion. The four changed scenarios additionally ran the actual
`parity.mjs` with native glibc, native musl, renderer JS and app WASM: **4 passed,
0 failed, 0 differing PCM samples/LSB in every comparison, exact screens,
no imports and no dropped sequencer events**. No tolerance or screen-mask
changes. No ASan rerun: no executable production source changed. The parent
still owns regeneration and the full combined WASM acceptance run.

[verified] Lane source hashes from `sim/web/tools/source_hash.py`:
engines `dc42550a6f98e498a3ce3a44834c50dd74a33169632ee32e9e11df878746fa62`;
sim `ebdc62abfa0a12801ac4ad816d01357686714694be6ff9adc1f0cc6bcf8a31cf`.
The header comment, scenario inputs and panel comment change the declared sim
hash. Parent must recalculate after its separate SS3 integration.

[verified] Rarefaction orient on shared main could not resolve the RAM function
at its requested position; scope on the related refusal test returned expected
co-change paths. Serena found that test. Both servers remain pinned to main,
outside this isolated worktree; no global activation/restart. Exact worktree
files, explicit call search and runtime probes were used for authoritative
checks. This is a bounded fallback, not a claim of complete semantic coverage.

[verified] Aeon jobs used exclusive CPUs 12–15, four CPUs, 6 GiB memory/swap,
`docker-batch.slice`, `--rm`, project=lunar/session=seq-panel-parity-20261101.
Evidence and scripts are in ignored `scratch/seq-panel-parity-20261101/` here
and `/home/likwid/datasets/lunar/seq-panel-parity-20261101/` on Aeon. The worker's
`release-combined-20261101` products were read-only and untouched. Own candidate
copies, pytest scratch and generated parity PCM/screens are removed after small
logs/JSON capture. This worktree remains for coordinator review, then normal
removal after integration. Mac free space at handoff: 1,118 GiB, above 500 GiB.
