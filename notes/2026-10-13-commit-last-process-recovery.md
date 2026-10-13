# Commit-last recovery across process and loader loss

Status: synthetic model verification only; no physical transport or partition
changes. Existing guards and private loader pins remain unchanged.

## Coverage gap and result

The existing transaction tests checked commit-last ordering with an in-process
session. The process-reopened 497-case device campaign used ascending sector
order. Added `tests/test_commit_last_recovery.py` to exercise their combination:
32 faults spanning install and restore, with a synthetic two-sector application
region and its first sector designated the final directory/commit sector.

Each case executes the real transaction engine in a separate worker process
against the persistent NOR/CDB model. The fault must produce the exact injected
exception type and recovery-required journal. Reopening discards all RAM loader
state and live handles. The test checks the precise torn/committed NOR prefix,
that the noncommit sector already equals the desired data, and that every
protected byte remains unchanged. It then acquires a new modeled recovery
session, resumes to a full-image hash match, resets, rolls back to stock, and
resets again [verified model].

Faults cover partial commit-sector erase at 0/2047/4096 bytes, partial first and
last commit-sector pages at selected 0/1/127/255/256-byte boundaries, lost erase
or program acknowledgements and disconnect-before-command. A nonbootable
modeled image refuses the app soft key before modeled external USB_KEY entry.
The boot oracle and USB_KEY route remain assumptions, not pi32v2 execution or
physical electrical/ROM recovery evidence.

## Hera verification

`commit-last-recovery-v2` passes all 113 combined cases from the new suite,
`test_flash_transaction.py` and `test_simulated_device.py`, sharded across
sixteen network-disabled Hera containers. All exits are zero; no container OOM.
The v2 tests add exact fault-type and interrupted-byte assertions after v1
passed its less-specific checks. Both receipts are retained privately.

Receipt location:
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/commit-last-recovery-v2-verification.json`

Receipt SHA-256:
`3d03437e45a3fe5a78eeaa189a3a299283e2ac06cb7114f6d79f3d30f1d80daf`

## Recovery procedure implications

1. Preserve the transaction directory and its two complete backups, target,
   sealed plan and journal after an ambiguous write. Stop using its old handle.
2. Independently observe the actual recovery enumeration, then obtain a fresh
   authorized binding and reload the reviewed RAM loader when required.
3. Revalidate unit identity and read all flash before resuming. A journal cursor
   is not a substitute for current bytes; any protected-region discrepancy
   blocks writes.
4. Rebuild differing authorized sectors, retaining the sealed commit-last order.
   Verify every rebuilt sector and the final complete image.
5. Verify cold boot and recovery on the physical FM1 separately. The model does
   not authorize replaying a consumed boot request or assuming a broken app can
   use its MIDI soft key.

No default-thirteen image, enlarged layout, physical interruption test or web
OTA installation is accepted by this result. Those release gates remain open.
