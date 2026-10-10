# Compare MID multi-zone pulses

The Compare audit finding in `notes/2026-10-07-full-code-audit.md` was
reproduced and fixed. A native regression primed Compare above `+Width`, then
moved A below `-Width` in one modulation tick. Before the fix, MID emitted no
edges although the interpolated segment crossed the entire band. The same
regression checks the reverse BELOW-to-ABOVE sweep.

`mod_compare.c` now emits MID high and low at the ordered interpolated
crossings when a tick moves directly between the two extreme zones. The test
uses Width `0.25`, zero hysteresis and input `+0.5` to `-0.5` (and back); MID
edges occur at frames 8 and 24 in both directions. Existing zone outputs and
final levels remain asserted.

Verification used aeon's bounded `lunar-asan:ubuntu-24.04` container
(`--memory=4g --memory-swap=4g`, `docker-batch.slice`) with the focused native
target `make CC=cc build/fm1-mod-kinds-test && ./build/fm1-mod-kinds-test`.
Before the source fix, the new MID edge assertions failed (3 checks); after
the fix and the reverse-direction case, all 1,240,305 checks passed, including
135 filter responses, 16 memory-fill cases and 32 fuzz cases. No hardware was
used.

Rarefaction was available but its configured root remained the original
checkout instead of this isolated worktree; the exact-position query was
therefore not used as evidence. Serena was activated on this worktree and
returned the Compare processing body. The regression and native run are the
behavior evidence.

CI follow-up: the full Compare trace correctly changed when previously lost
MID pulses began appearing between the sampled excerpt ticks. Regenerated
only Compare's golden trace with the native renderer on bounded LAN Linux
clang; all 4,134 rows and excerpt length are unchanged, other kinds are
byte-for-byte unchanged, and the new digest `a9e6c48d…` matches the failing
macOS CI's actual digest. The focused golden test passes both regeneration
and a separate normal verification (1 pass each). This updates the expected
intended behavior, not a tolerance or gate.

The branch's committed simulator build record also predates its simulator
sources; a fresh bounded Wasm/native parity rebuild completed. All 104
scenarios match JS/musl exactly, 101 match glibc exactly and the other
exact-scenario comparison differs by at most 1 LSB. Native edit-layer parity
passed; the 30-second storm applied 82,728 edits across 10,341 quanta with
zero late quanta/resyncs (p99 0.092377ms, max 0.226653ms). Record source and
module hashes were checked locally. CI must pass the new complete head
before integration. No browser-page rerun is claimed for this rebuild.

## Current-main crossing review and integration

[verified: source inspection] Above-to-below traversals emit MID high at
`Width - Hyst/2`, then low at `-Width - Hyst/2`. Below-to-above uses
`Hyst/2 - Width`, then `Width + Hyst/2`. Each pair has ordered crossing times
because `crossing` divides by the signed endpoint delta; the thresholds are
separated by twice nonnegative Width. `kind_gate_set` updates levels and
`mod_gate_edge` appends alternating edges in nondecreasing frame order.
The final MID level remains low. These are discrete modulation tick facts,
not hardware MIDI timing measurements.

The existing zero-hysteresis bidirectional regression pins frames 8/24.
Added two nonzero-hysteresis cases in both directions: Width 0.25 / Hyst 0.25
requires high/low at frames 12/28; Width 0.125 / Hyst 0.5 requires 20/28.
They also assert the departing ABOVE/BELOW fall and arriving BELOW/ABOVE rise
at those same times, and the final levels. The latter case exercises a
hysteresis half-band greater than Width. No implementation or gate changed.

[verified] Integrated main `67d5e12d`, retaining the source correction and
Compare's intended golden trace. The only conflicts were generated Wasm and
its record; their final resolution comes from an actual combined LAN build,
not a prior branch binary. That build passes 104 parity scenarios, 4621
screens with zero layout faults, metadata, 18 DX7 checks and native edit
checks. Edit audio delta is zero; the 30-second offline edit storm reports
zero late quanta/resyncs, maximum 0.235581 ms against deadline 2.901310 ms.
Both source hashes match the generated record.

LAN tree `/home/claude/mvave-fm1/compare-main-integrated-20261009/src`; local
logs `/tmp/lunar-compare-main-{build,pytest}.log`; compact receipt
`notes/data/2026-10-09-compare-main-integration.json`. Containers use the
existing Docker batch slice, four CPUs and 8 GiB memory. Rarefaction still
points at the original checkout and lacks a compilation database, so its
orientation is not exact-branch verification. Serena was activated on this
worktree and returned the exact Compare body; file inspection and tests are
the behavior evidence. No browser page rerun or hardware traffic is claimed;
new exact-head CI must pass before merging.

[verified] Focused current-main verification: 32 pytest tests pass in 13.97 s,
including all modulation kind golden traces, canonical metadata, served
examples, committed Wasm record and measured offline edit storm. The native
kind checker reports 1,245,985 checks, 135 filter responses, 16 fill cases,
32 fuzz cases and zero failures, including the new hysteresis assertions.
