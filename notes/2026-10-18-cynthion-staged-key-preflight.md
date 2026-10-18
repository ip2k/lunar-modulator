# Two-stage Cynthion recovery-key profile (offline)

[verified: source and Amaranth simulation] Added explicit `staged-operation`:
physical USER preflights disconnected K/J/SE0/SE1, then state 9 READY is high-Z.
Only a fresh steady release after READY and second press starts the unchanged
bounded KEY/WAIT_DP/SOF path. A held button cannot advance. All four self-test
bits and no failure are required. Interlock loss, including explicit PHY fault,
latches FAULT; restoring gates cannot rearm. Reset clears readiness and mask.
Existing state IDs 0–8 and original modes' protocol paths are preserved.

Layout 7 appends staged-profile bit 15 to status register 3, so SAFE/READY and
terminal profiles are distinguishable. READY does not freeze terminal receipts
or event history. CONTROL power remains explicit; staged recovery recipe selects
CONTROL-to-TARGET-A only, TARGET-C/AUX/discharge off. See scoped README staging.

[verified] Focused suites: 28 passed using existing test interpreter and Cynthion
site-packages; covers original modes, staged successful two presses, held first
press, high-Z READY, each gate loss/no rearm, reset, mismatch/no KEY and invalid
automatic staged configuration. Only dependency deprecation/unused-elaboratable
warnings. Final source guard strengthening rerun recorded in handoff below.

Semantic startup: Rarefaction and Serena both reported the original absolute
checkout, not this isolated worktree. Did not retarget global shared servers
while other sessions work. Source inspection used instead; no semantic practical
evaluation claimed for this worktree. Main repo .venv lacks Amaranth; initial
throwaway /tmp/lunar-staged-key-venv ran 26 passing checks before the coordinator
provided the established interpreter, then established interpreter ran 28.
No global dependencies changed.

No SSH, FPGA build/load, device traffic, FM-1 writes or hardware acceptance.
Connected/unpowered-target failure cause remains unproven. This source preparation
does not relax dump-and-byte-identical-restore gate or authorize an attempt.

Handoff: branch `fix/2026-10-18@cynthion-staged-key-preflight`, isolated checkout
`/Users/likwid/.codex/worktrees/cynthion-staged-key/mvave-fm1-firmware`, exact base
`01f7df96`. Coordinator must review/integrate, teach its read-only reader explicit
layout7/bit15/state9 identity, and separately authorize/build/load the exact image.

## Coordinator integration and offline routed build

[verified] Integrated workerccd79e6a as1998c49055da5f8a130dcac81752f65eb6072604;
pushed and remoteSHA verified. Root combined ULPI/key/power monitor/readout
suites:82passed. CI39107811315 exactsource1998c490 gateware job passed; overall
CI remainedinprogress at review, not an exacthead fullCIclaim.

Aeon build root `/home/claude/.local/share/codex-builds/lunar/cynthion-staged-key-1998c490-20261018`.
Pinned image d065eaf170070135564c88bd4273f30784278b35c9355d36a0a96bd6ba20cc8c,
existingrovenv/OSSCAD;4CPU/8GiBRAM+memoryswap/512PID/docker-batch.slice,netnone,
readonlyroot,capdropALL,no-new-privileges,uid1003,no devices. Root verified
created/terminalreceipts; container2cf3543e exited0/noOOM. Logs and receipts
saved before explicit removal; buildclaim released after sharedhandoff.

Bitstream175113B, SHA bf0f00293a24ea7dc909737f23dd23ed58acc2fddf451e1a3cd744af5ae94826.
NetlistSHA503ac8c0ed2198bc39596e9fff575649740340eb5a115f595966efc52c840572.
LPF7779409006f61ba755ff3ebf07e16ec64d75c2abe2674da2c23a077821d4e0c3.
Final routed68.92MHz PASS60 and217.68MHz PASS120; earlier placement-only
58.44MHzFAIL is superseded by final routed analysis, not ignored.
Root netlistcheck CONTROL1,C0,AUX0,discharge0, DP N4/DM P3 LVCMOS33/NONE
with actual bidirectional tri-state cells.

Actual versions: Python3.12.3,Amaranth0.5.10,Apollo1.1.1,Cynthion0.2.5,
LUNA0.2.3,luna-soc0.3.2; Yosys0.70+145,nextpnr0.11.1-63,ecppack1.4-86.
Nonfatal wrapper XDG/font-config warnings under readonlyroot retained; final
route/pack completed normally. A local runner-template syntaxerror was caught
before remote build, preserved, corrected; only one actual container run.

Local artifacts/independentrootchecks: `scratch/cynthion-staged-key-build-20261018/`,
includingroot-review.json,sourcearchive,runner,created/terminal/logs.
Sharedhandoff `handoffs/lunar-modulator--staged-key-1998c490-20261018.md`,
SHA6e34d83264b9cdc17d0b5509ac5af17a74c806936265bfa7cc6d156345491fd7.
Explicit staged reader `scratch/cynthion-staged-key-20261018/read_status.py`
requiresLUNR/layout7 andprofilebit15+CONTROLbit14/selftestmodeoff before
interpretingregisters; SHAaff10638d3bf3a00f0c33d5f5847863eb5ab417d899aa8ae5bbc6c5ededc9b64.

No stagedbitstreamload yet. AwaitownerBOTHtargetsemptyconfirmation; existing
oldlayout6 operationimage remainsFAULT/high-Z. No FM1write/flash/loader.

## Volatile load and disconnected SAFE verification

[verified] At 2026-10-18 07:37 UTC, after owner confirmed both TARGET ports
empty with CONTROL connected and no USER press, coordinator loaded the reviewed
175113-byte bitstream successfully. No FM1 was attached during the load.
The layout7 reader captured `scratch/cynthion-staged-key-20261018/disarmed-status.json`:
status `0xC410`, SAFE0, PHY ready, no fault, GPIO/output enables0, terminal
receipt0; safety markers unchanged across the non-atomic sweep. Volatile loader
exit0 and log `volatile-load.log` retained alongside the capture.
Owner asked to press/release USER once while both TARGET ports remain empty.
This is only the disconnected preflight; connection and second USER press remain
separate later steps after READY9/selftestF/high-Z verification.

[verified] Owner pressed/released USER while both TARGET ports empty. At
07:38 UTC, `preflight-ready-status.json` reports status0xC7D9: READY9, all
four self-tests passed (maskF), PHY ready/no fault, GPIO/OEs0, terminal0,
packets0. Safety markers unchanged across sweep. Asked owner connect FM1 on
TARGET A with LEFT/OFF, TARGET C empty and no USER; connection verification
remains pending before the second fresh USER recovery attempt.

## Connected OFF readiness verification

[verified] Owner connected FM1→TARGET A, LEFT/OFF, TARGET C empty, no USER.
At 07:39 UTC, `connected-left-ready-status.json` reports status0xC7D9/READY9,
selftestF, PHYready/no fault, GPIO/OEs0, terminal0. Those safety values were
unchanged across the non-atomic read. The live ring head changed1030→1035;
therefore the helper's combined ring-stability flag is false, without a
safety-state transition. No key had been sent. Owner asked for the second
fresh USER press/release followed immediately by LEFT/OFF→RIGHT/ON, keeping
TARGET C empty until terminal output-release verification.

## Corrected-direction staged recovery sequence completed

[verified] Owner pressed second USER and switched LEFT/OFF→RIGHT/ON.
At 07:40 UTC, `post-power-on-status.json` reports status0xCFD7/DONE7,
no fault, selftestF, GPIO1 with both OEs0; receipt0x701 is valid with
protocol-failure reason0 and terminal DONE7. Recorded873 packets,
ACKprogress397, WAIT_DP1628us, SOF1503000us, final low counter2999.
Ring frozen at32 events (reg19=3072); status/GPIO/terminal/ring markers
unchanged across the non-atomic read. Controller completion does not establish
mask-ROM entry; passive USB identity remains required. Asked owner connect
TARGET C→bench01 while leaving RIGHT/ON and not pressing USER.
