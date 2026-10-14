# Device53 Event Horizon read and repeat-boot adapter preparation

[verified] This work adds separate device53 adapters and offline tests on top of source base `b00776ce1d9a57e0458ca04940df8f3df8fdb363`. It does not issue USB, SG, MIDI, flash, reset, power, or reboot operations. The Mac coordinator exclusively owns the bench.

[reported: coordinator task handoff] The intended comparison target is the previously retained Event Horizon full-flash image SHA-256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`, containing app SHA-256 `ba46bf0a4d1bda4d604223c658b141b4a9068e37f65afddd998af04d5296cfc8`. The adapters bind to the full-flash digest; they do not separately inspect or claim the app digest.

## What changed

[verified] Before this change, the reviewed device50 adapter pair rejected any other USB enumeration. The new pair pins USB `1-1`, bus `1`, device `53`, VID:PID `4c4a:8057`, gives read/boot campaigns and log events device53-specific kinds, and uses device53-specific one-use markers. The boot verifier pins the SHA-256 of the new read adapter (`47fae66459fd87983b9c75bcb0074fe345627fbd86d85ff022fe48e94035137e`) and still verifies the fixed loader, inventory, source pins, complete dual-read manifest/transcript, fresh same-session USB/SG mapping, and no-later-command attestation before constructing its one-shot reset authorization.

[verified] Read acceptance still requires the exact 8,757-operation inventory, two complete 1 MiB reads, and equality to the fixed target digest. Reset acceptance still sends only the existing FC0C arg1 request once. Ambiguous completion is latched; there is no retry. Read/reset receipts keep install history, boot observation, physical recovery and flash operations false. This is preparation for a fresh device53 evidence campaign, not evidence that such a campaign has occurred.

[verified] Tests explicitly reject device50 and device52 enumeration evidence in both the read and same-session boot snapshot validators, alongside other foreign enumerations. Existing tests cover the fixed target digest, read adapter hash binding, consumed markers, freshness checks, pre-open policy refusal, and single-shot ambiguous reset behavior.

## Checks and limits

[verified] Focused command on Hera:

```text
/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest -q tests/test_event120_device53_repeat_read.py tests/test_event120_device53_repeat_boot.py
31 passed
```

[verified] The system Python has no pytest; the test run used the existing pinned project venv. No test performs device I/O; transport and prepared-authority seams are mocked. Serena/Rarefaction were not safely pointed at this isolated Hera worktree: Serena's active root was the Mac worktree and Rarefaction reported the Mac checkout, so source review used exact file inspection without retargeting shared language servers.

[reported: coordinator task handoff] A new campaign must use fresh device53 sysfs and SG evidence from the same current ROM connection, with the exact `devnum=53` binding and current SG inode identities. The read adapter must preflight the newly captured campaign and snapshot; after two matching full reads, a separate fresh same-connection snapshot and no-later-command attestation are required to prepare a one-shot boot request. Never reuse device50's snapshot, read manifest, transcript, campaign, boot receipt, or consumed marker. The root must review all generated evidence and controls before any invocation that performs hardware I/O.

[verified] No image was built, installed, packaged, or admitted here. No Event Horizon playback, installability, updater acceptance, persistence, recovery, or physical result is established. GitHub backup remains pending coordinator review because Hera has no GitHub write credential.
