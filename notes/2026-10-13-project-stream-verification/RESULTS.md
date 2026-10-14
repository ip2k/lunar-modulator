# Project serializer and NOR transaction verification, 2026-10-13

[verified] Compact binary writer streams directly through lunar_project_write.
The transaction format validator invokes the actual binary reader with CRC
checking enabled before commit. Nine golden binary files roundtrip via this
path and compare canonical records after reconstructing startup storage state.

[verified] 30 tests pass30 Hera ASan/UBSan chunks. FIRST ORBIT performs793
flash operations. All793 positions are tested in three modes: operation rejected
before modification, half erase/program then failed acknowledgement, and full
erase/program then lost acknowledgement. Total2379 failures followed by restart
scan and real-reader record comparison. Inactive slot starts with stale zero
bytes, so erasure is necessary. Previous slot remains byte-identical in every
case. Failed transaction rejects further writes without HAL operations; no
manual deactivation masks the latch. Restart accepts either prior or newly
committed file after ambiguous acknowledgement. All logs/exits/noOOM and five
source hashes checked.

Limits: simulated half/full operations, not every byte cutoff or physical NOR
power loss; replacement changes session transpose, and restart compares the selected slot
with the correct old or changed canonical records. Needs generation
wrap/ambiguity tests, real HAL/format-validator integration and final device
allocation. Two maximum-size slots still need200KiB unavailable behind current
13engine app. No physical flash operation or application persistence claim.
Initial v1 campaign passed with weaker empty-target/two-mode model; v2 strengthened
stale-target, lost acknowledgement and direct latch coverage; v3 added changed
project rollback verification. Private final logs in
build/native-project-stream-20261013/hera-results-v3/.
