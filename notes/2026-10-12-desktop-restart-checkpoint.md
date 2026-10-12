# Desktop and macOS restart checkpoint

Personal/non-commercial, 2026-10-12 UTC. The owner requested a safe stopping
point within the next hour, a checkpoint, and preparation for restarting the
desktop application and macOS to repair the Computer Use connection.
This is a pause of the installable-image goal, not completion or cancellation.

## Resume here

Checkout: `/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`.
Branch: `feature/2026-10-11@installable-firmware`. Previous pushed checkpoint:
`a5b1381b8180f1459650218e14fdb6f8c1a8ac08`. The restart checkpoint commit is the
branch tip; read `git log -1` and compare `git ls-remote origin` before continuing.
Root alone integrates, commits, pushes, stages and operates the FM-1.

[verified: passive observation only] At epoch `1791826230.1032424`, bench01
reported the FM-1 on USB port `1-1`, bus1/device7, `4c4a:c755`, product `FM-1`,
12 Mbps, with `/dev/snd/midiC2D0` present. No device command accompanied this
check. Normal enumeration is not a fresh identity or display/CPU acceptance.
No trace image installation has occurred since Cynthion was connected.

[verified: final passive stopping check] At epoch `1791826884.3624265`,
the same normal USB device and C2D0 remained present. A bounded `/proc` scan
found no known firmware wrapper or open USBmon capture descriptor. Hera's
container inventory at `1791826884.254075` found no matching FM-1 test
containers. All three delegated lanes finished. This scan is a stopping
check, not proof of every process or the device's display/CPU state.

[reported: owner wiring] Cynthion CONTROL goes to the Mac, TARGET C to the
bench Pi, TARGET A to the FM-1. The owner confirmed the Mac was unlocked and
locked-use permission enabled. Native Computer Use nevertheless returned a
locked-Mac error and exposed no Packetry app/window. Do not ask the owner to
unlock again on that evidence. No live Packetry window, screenshot or click
was obtained; the captures collected here came from bench01 USBmon.

All historical entry/reset/install markers stay consumed. The two complete
fresh physical flash backups matched stock
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
Their 120-second installation window expired; never refresh their timestamps
or reuse them to authorize a later flash operation. Reset experiments led to
normal enumeration but lacked complete acknowledgements. Do not retry those
consumed reset packets. See
`notes/2026-10-12-software-reset-fresh-stock-backup.md` for the exact receipts.

## Newly completed model verification

[verified: retained nonroot model evidence] The lifecycle successor V2 passed
63 unique cases across 30 Hera chunks, with zero failures, errors or skips.
Root independently verified 167 retained regular files, archive members,
all seven frozen source pins, 31 constrained container inspections/removals,
exact JUnit nodes and empty cleanup receipts. All containers used UID
`1001:1001`. The three production wrappers remain byte-identical; only two
test files and their source-pin metadata changed. Disposable test directories
model root ownership, while two additional cases exercise the actual root
guards before child activity. This does not test a physical capture process
or admit the canonical flashing factory.

Check: `63cc4e8ebaddda098e3f9811eb0003f04af50ffad8bfec5dd9c13fa650710189`.
Archive: `c825e31bb9ae299c643fabf1df645be3a3270eecb2e76c4bd633d75edf6b3d39`.
Local evidence: `build/lifecycle-ci-nonroot-successor-v1/successor-v2/`.
Hera evidence:
`/home/claude/mvave-fm1/lifecycle-ci-nonroot-successor-v2-20261012`.
The earlier fixture/ownership failures remain retained. GitHub CI for the
new checkpoint must be checked separately; this focused Hera result does
not imply exact-head CI success or merge readiness.

[verified: preceding checkpoint CI] Run `38281670309` on exact head
`a5b1381b8180f1459650218e14fdb6f8c1a8ac08` completed with 12 successful
jobs and one failed job, `tests (ubuntu-latest)`. The new test-fix checkpoint
starts a separate CI run; retain the preceding failure and do not treat the
older all-green `48629ff7...` run as coverage for the current branch tip.

[verified: retained model evidence] The genuine interrupted-INSTALL successor
passed both exact erase/program cases on Hera. Root read the independent
review/checker, verified 160 ordinary retained files and the regular-only
archive, then replayed all 1,770 source hashes, three constrained container
inspections/removals, unchanged private inputs, and the exact two cases.
The reproduced check is
`e4847812748bbef3cf1189a8141e99569064504a38bcc9cd078948971f8401de`;
retained archive is
`9f4797fa8a67ce668d5c4662923531d71fe9a681ff5e418205009f88a2b754dd`.
Two nonregular paths were recorded as metadata only and were absent from the
ordinary export; they were not followed.

Each case exercised the actual `068fd62c...` adapter with actual `59b8e8c2...`
capture source bytes, consumed the failed install, acquired two matching
1 MiB partial dumps with 8,707 read-only commands, then restored exact stock
and checked every final 256-byte page. SG/ioctl, clocks, passive witnesses and
capture records were modeled. Actual capture subprocesses, physical interrupted
write recovery, boot/display, disconnected/new-ROM recovery and kernel
exclusivity remain unproved. This accepts the retained-same-loader model only.

Local evidence:
`build/partial-stock-recovery-production/install-capture-allowlist-successor-v1/genuine-install-proposal-v1/`.
Hera evidence:
`/home/claude/mvave-fm1/partial-install-capture-successor-genuine-v1-20261012`.

[verified: retained failed model] The owned partial-restore wrapper V6b
collection and CLI-help checks passed. Its heavy case failed before the helper
or factory because `/shard-work/tests/model-clock-launcher.py` was missing.
All 153 retained regular hashes, unchanged private inputs, stopped exact
container identity, resource constraints and removal were independently checked.
Check: `aaa7ca061080b80ee8d389852f048f60a28c1fe0621a9ebd956426bcaa38c0f5`;
archive: `4a5be66d0ee18d8f38ce7362dff081e7211a9fce228bd406a8a363ef24487499`.
This failed run grants no wrapper/factory acceptance. A successor adding the
existing test-only launcher is prepared but has not run. Review its exact
source/runner delta after the restart; do not retry the old runner.
Local parent directory:
`build/partial-stock-recovery-production/next-campaign-readiness-v1/hera-owned-restore-v1/hera-owned-restore-v6/`.

## Closed physical proposal and outstanding work

[verified: index only] The V5 proposal remains source-only and closed. Root
rechecked all 14 exact files against review index
`598da41ab7d584276d9652e8fad1528f00f7e4a7bbaac20af390fb1736b6661e`.
No V5 stager/helper/factory or hardware action was executed. The actual root
`partial-recovery-plan.json` is absent, and all four sequence activation pins
remain `None`.

Directory:
`build/sdk-trace-fresh-entry-bench-v1/next-campaign/automatic-trace-chain-v5/`.
Main archive: `5a176f20bf7a765ce317e078a81ab60830523a2b39c1b8e5967ec5a5738e606b`.
Separate recovery sources:
`fa76d3d230af9be4a08bf87f6c5b471b6e201a9a79127238592d034b894ba542`.
Closure: `4d97a3db0464edccbd27d98af047bb8a36703b6c8284816fe2afaefdff3a1451`.
The earlier V4 file-only stager passed 39 cases in30 chunks; that does not
validate the new recovery-stager control flow or authorize bench staging.

[verified: private restart backup] Root rehashed all 331 V5 source files and
regular PAX archive members, then copied six inert backup/index/handoff files
to a fresh exclusive private directory on Hera. Destination hashes, sizes,
0600 file modes, 0700 directory mode and file/directory fsync were checked.
The archive was not extracted; no proposal source was executed or staged.
Hera destination:
`/home/claude/mvave-fm1/automatic-trace-chain-v5-private-backup-20261012-restart-v1`.
Archive SHA:
`8b54d216912aaceb38642ac33121a450785ac1ba68903b4b0ba0e0ffa0cff386`.
Local receipt:
`build/sdk-trace-fresh-entry-bench-v1/next-campaign/automatic-trace-chain-v5-restart-handoff-v1/root-verified-hera-backup-receipt.json`,
SHA `335f4871708b80a658fc2a0dfc3ed95ed25e6b72d1380be88d028292b4987990`.
The frozen proposal's earlier no-transfer statement records its original
state; this later root receipt records the completed file-only backup.

Resume in this order:

1. Retry the computer-use skill's documented native-app entry point and inspect
   Packetry. Reconfirm actual wiring and live USB/MIDI topology after reboot.
   Use the native connector for UI; do not bypass its failure with shell UI
   automation or change permission settings without the owner's request.
2. Read the latest lifecycle nonroot result and exact checkpoint CI status.
   Models, GitHub CI and physical acceptance remain separate gates.
3. Review and run the narrow missing-launcher successor; then review the V5
   main stager delta and the new separate recovery-source stager. Write the
   actual partial-recovery plan with the admitted helper/wrapper source pins
   before any sequence activation. Preserve all historical failure receipts.
4. After the prerequisite gates pass, issue a fresh one-shot physical campaign:
   identity, soft-key entry, dual stock backups, install, one boot, five original
   RAM trace reads before loader upload, returned backup and full stock recovery.
   Use actual timestamps and SG/USB generation. A caught partial write needs
   the same retained loader, fresh witness, actual command journal and owned
   stopped capture. Disconnect, new ROM, ambiguous cleanup or nested failure
   remains consumed for review; no automatic reset/upload/retry fallback.
5. Resolve trace/startup findings and obtain physical display/boot/recovery
   acceptance. Complete required exact-head review/CI/integration/merge and the
   overdue full-code audit before claiming the agreed firmware goal complete.

Hera is `claude@192.168.1.48`; bench01 is `claude@bench01.local` with `sudo -n`.
Keep builds/tests on Hera and leave aeon alone. No private image, stock backup,
vendor binary, loader or toolchain belongs in Git. Rarefaction/Serena still
select the shared primary checkout rather than this worktree; no retarget or
server restart occurred. File/AST and retained evidence checks supplied this
worktree's coverage.
