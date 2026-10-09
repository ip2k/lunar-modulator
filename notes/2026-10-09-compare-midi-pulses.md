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
