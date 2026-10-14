# Current thirteen-engine expanded candidate

[verified] The real private CLI constructor now selects vendor objdump's r3
CPU decoder explicitly. The current stack-readout ELF reconstructs an 845916-byte
application and a private full-flash target. Its SDK-free link, entry, provenance
and expanded geometry gates pass. Exact target/ELF hashes are in candidate-summary.json.

[verified] All 53 geometry and rejection tests passed across 30 Hera containers,
with zero exits and no OOM. Every recorded source hash matches this worktree.
Receipts: gate-verification.json and gate-source-hashes.json. Private image and
full receipt remain in build/native-current-candidate-20261013/ and Hera
out/current-candidate-private-v1/. No firmware bytes are published.

This is offline construction, not physical admission, migration, rollback,
real-time acceptance or web installation. [verified] The current-image 40-case interruption/recovery campaign passed in
30 Hera chunks. All30 logs and16 source hashes were checked against the exact
remote source snapshot; no failed exit or OOM. Receipts: recovery-40.json and
recovery-source-hashes.json. The snapshot predates the optional geometry_baseline
test argument; it validates this current target against original stock bytes.

## Exact current-device offline plans

[verified] expanded_bench_transactions.py seals the fresh device36 backups and
current target to native install/Trio restore and subsequent stock install plans.
The existing durable transaction engine is source-pinned, and reloading checks
all saved image hashes and directory-last sector order. Current native plan has
213 changed sectors; Trio-to-stock has13. Public summary: device36-plan-summary.json.
Full plans and images remain private in build/native-current-candidate-20261013/device36-plans/.
Nine boundary checks pass;32 actual-byte private tests skip without private inputs.
[verified] The separate41-case fresh-Trio baseline campaign passed in30 Hera
chunks. All30 logs, terminal exits/noOOM and19 source hashes were checked;
receipts: fresh-recovery-41.json, fresh-recovery-log-check.json and
fresh-recovery-source-hashes.json. This is byte-accurate modeled interruption
and restore evidence, not execution or recovery on the physical CPU.

An exact-device36 writer is implemented but has not been admitted or run. The new geometry_baseline test argument
keeps validation anchored to the original stock components when simulating a
transition from the physically installed Trio image. Earlier stock-baseline
campaigns keep their unchanged default. Physical settings preservation, boot,
rollback and realtime acceptance remain unproven.

## Exact-device36 writer checkpoint

[verified] expanded_bench_policy.py admits only the pinned native213-sector and
stock13-sector plans, backed by the exact fresh matching physical dumps. Source,
image, plan, journal and loader/session provenance checks reuse the existing
transaction and bound-command implementation. expanded_bench_live.py adds the
one-use fresh passive SG/sysfs admission and durable receipts. No actual opener,
preflight or device command was executed in this checkpoint.

[verified] The original transport limit20000 would stop the healthy expanded
install, whose non-heartbeat commands total25572 (restore24276). expanded_sg.py
retains the reviewed RehearsalSG class body byte-identically while giving this
campaign a32768-command/2700-second bounded envelope. Its worst-case sector
rebuild plus half-second read heartbeats fits that command envelope. This is
an upper count check, not physical timing proof. Original historical adapters
and pins remain unchanged.

[verified]41 admission/wire-budget checks pass locally with actual private image
inputs using the primary checkout .venv (1.26s). The system Python lacks pytest;
a first local test setup using file symlinks was correctly refused by the
regular-file evidence gate and was rerun with copied private files. Tests include
mismatched provenance, expired observations, changed SG mapping, consumed
campaign, opener failure/no retry, protected writes and limit enforcement.
A live physical campaign still needs concrete review, fresh passive observation,
full candidate recovery results and a bounded boot/recovery path. No hardware
acceptance or settings migration is claimed.

[verified] The same41 admission/budget checks passed on Hera (8.21s). Passive
bench Pi preflight verified all source pins, the exact native plan SHA and the
unchanged USBdevice36/SGmapping. Receipt: device36-writer-preflight.json. Zero
hardware operations; no transport opened, no flash write, and no boot sent.
The copied private campaign timestamp expires and must be refreshed before any
run. Pi source/plan/backup root: /home/claude/fm1-expanded36-source-20261013/.
A new bounded boot envelope for the expanded install is still required; the
older device31 boot adapter must not be used.

## Guarded physical installation started

[verified] Staged expanded proof/boot modules import and pass source pins on Pi.
Fresh canonical SG/USB preflight passed; reviewed campaign SHA256
094be5c78fec1ca9e66407ece933f21eba157299cf9ce5a5306614db9e0ab560.
The physical writer is running through exec53310 on the original device36
fixed-loader connection. No boot request has been sent. Preserve this process
and inspect its durable journal/commands/result; do not restart on silence.
Concrete trial/recovery review: ../2026-10-13-expanded-device36-trial.md.
An operator helper initially compared tuples to decoded lists directly and
refused unchanged SG metadata; canonical comparison corrected the helper
before any device operation. Production pinned source was unchanged.

## Physical installation completed

[verified] exec53310 exited0. All213 planned sectors were written and verified;
the complete1MiB readback matches target c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903.
Independent exact-campaign replay passed25,669 commands/58,709 events over
385.04seconds. Summary: device36-physical-install.json. Private complete receipts
are mirrored under build/native-current-candidate-20261013/device36-physical-install/.
No boot request or physical recovery acceptance. The same fixed RAM loader
remains the next boot dependency; do not upload/replay the consumed writer.
