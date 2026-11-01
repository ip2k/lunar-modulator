# FM6 user-bank browser download — 2026-11-01

Personal, non-commercial Lunar work. Independent lane based on exact
`a1b7823ba768d7657474f9be432d7584998b1501`.
Branch: `feature/2026-11-01@dx7-bank-export`.
Worktree: `/Users/likwid/.codex/worktrees/lunar-dx7-export-20261101`.

## Outcome

[verified] Save… includes **FM6 user bank, all 32 slots (.syx)**. It snapshots
the live project through the existing bridge, mirrors it in the shadow Worker,
and calls `fm1w_dx7_save_bank` using core `fm1_dx7_write_bank`. Output is
`<project-title>.fm6-bank.syx`, 4,104 bytes, Yamaha channel 1, User 1–32 in
place. The current sound may use another engine. No device MIDI is sent.
The existing voice import and other Save choices are preserved.

[verified] VMEM has no unloaded-slot marker. Empty and partial banks are
refused, with a visible suggestion to save a `.lunar` project. This avoids
silently manufacturing INIT VOICE entries or collapsing slot numbers.
FM6 absent from a build returns -2 (source checked; no reduced-registry
runtime build performed); partial/empty returns -3 (runtime checked). The Save
choice reuses the existing labelled native select, notices, download anchor,
and delayed object-URL revocation.

## Checks and evidence

[verified] Full `sim/web/build.sh` in `emscripten/emsdk:6.0.10`, with static
musl reference from `alpine:3.22`: 108/108 parity scenarios byte exact against
JS and musl; glibc comparison 105/108 exact (the existing libm-sensitive
scenarios retain their documented musl acceptance); 4,713 native screen
states, zero layout faults; SysEx suite 19/19; metadata check passed; editor
checks passed. Added actual-WASM test checks empty/partial refusal, export
while current engine is Macro, all 32 slots, 4,104-byte framing/checksum,
exact original bank bytes, and load/export/load byte equality.

[verified] Full browser files suite passed in headless Chromium
153.0.8010.12 / Playwright: files, unavailable storage, load links, hash,
embed API, localhost policy, and layout, with no console/page errors. Added
checks verify empty-bank refusal starts no download, chooser import followed
by a byte-exact bank download with the `.fm6-bank.syx` filename, delayed URL
revocation, and removal of the download anchor. Existing project/sound saves
and voice imports still pass. JS syntax and git diff whitespace checks pass. The target-card screenshot
was inspected: the full bank option fits without clipping or collisions.

Evidence is under ignored `scratch/dx7-export-20261101/` in this worktree.
Build log: `wasm-build.log`; the initial wrapper log records an invocation
error placing --network after the image; the direct corrected compile ran
with --network=none and passed. No source or test failure caused that retry.

## Tool coverage and limits

[verified] Rarefaction status selected the primary checkout, C fallback flags
without a root compilation database, and sim/web JS profile. Absolute lane
`orient` and `scope` were refused because the worktree is outside its root.
No shared root was switched. Serena initial instructions/config were read;
absolute-path find_symbol correctly located `fm1w_dx7_load` in this worktree.
Its reference query was empty despite known JS/WASM callers: no FFI/cross-
language coverage claimed. Bounded source reads and explicit export-list,
shadow handler, Save flow, and actual runtime tests supplied the checks.

## Resources and next dependency

Aeon CPU0–3, at most 4 CPUs, 6 GiB RAM/swap, docker-batch.slice, labelled
project=mvave-fm1-firmware/session=dx7-export-20261101, --rm. Compilation
network disabled; Alpine package installation used networking. Remote staging
is `/home/likwid/datasets/lunar/dx7-export-20261101`; remove after collecting
small reports. No hardware, USB, flash, reset, or device output was attempted.
[verified] Cleanup: own labelled containers exited, remote staging and build
products removed after copying the small reports. No local generated binary
was fetched. Temporary build wrapper removed. Retained local ignored evidence
is 388 KiB (logs, parity/SysEx/browser reports and one screenshot), at the
path above. Worktree remains for parent review and must be removed after
integration with `git worktree remove` from the main checkout.
Mac free space at start: 1,130 GiB; final: 1,127 GiB, above the 500 GiB floor.

Parent requested source-only integration: do not commit this lane's generated
WASM/record, because the MIDI clock lane adds another export. Parent must
review both lanes, merge sources, rebuild actual WASM and generated record,
run required integrated CI/review, and merge with a merge commit. This lane
opens no PR and merges nothing. Full native pytest/ASan/32-bit CI were not
run in this lane; integrated source/hash gates require the parent rebuild.

Source commit and verified GitHub branch SHA:
`4f27480cd455421c213f53bc091869312f78a2a0` (immediate explicit-refspec push;
remote `ls-remote` equal). This note is a subsequent documentation commit.
No source edits remain uncommitted. No hardware acceptance claim is made.
