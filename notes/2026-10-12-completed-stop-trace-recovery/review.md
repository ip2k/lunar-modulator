# Completed trace: distinct backup and stock restore

[verified: source inspection] New closed adapters use the completed-stop-trace
proof without relaxing the predecessor's rejection of consumed trace authority.
The backup accepts a distinct fresh connection witness and consumes its own
loader marker. It preserves the existing fixed loader and dual full-flash read
inventory. No erase/program/reset belongs to the backup adapter.

The restore reuses the pinned f583 policy/transport/replay kernel. It binds a
completed dual-target backup, preserves the pre-restore journal, reads the full
target before writes, restores 29 app sectors followed by directory sector
0x4000, and checks full baseline readback. Its own consumed marker prevents
reuse. It has no reset or automatic retry. Later operation publication causes
refusal. Canonical adapters remain closed (dependency source pins are None).

[verified: Hera device model] Sixteen backup cases passed in separate isolated
containers, with one test per chunk, zero skips/errors/failures. All seventeen
backup/boundary containers exited zero without OOM, network disabled, and were
removed after inspection. Eighteen combined backup/restore closed-authority
boundary tests passed on Hera. Python compilation and diff whitespace checks
passed. Private artifacts are under completed-stop-trace-backup-16-20261012.

[verified: inspected Hera results] Restore composition: sixteen chunks passed in
completed-stop-trace-restore-16-20261012. First attempt failed at pytest
collection because the helper import was unavailable under importlib mode;
logs were preserved as evidence-collection-failure, and the helper is now
loaded by its exact file path. No modeled or physical operation occurred in
that failed attempt. All16 XML suites contain exactly one test and zero skips/errors/failures. All16 containers exited zero without OOM and with network disabled; inspected and removed. Successful cases restored the exact full baseline hash and replayed completed evidence without further model commands. Interrupted/corrupt writes halted with no success publication/reset/retry. This includes runtime model acceptance, not physical acceptance.

These models do not establish physical stock boot, recovery, visible display,
or USB transport acceptance. No physical FM1 command was issued in this work.
Do not erase consumed markers, replay the old read, or promote a model result
to physical recovery evidence. Next inspect the restore results, resolve any
faults, complete source/pin review, then prepare a fresh physical backup packet.
