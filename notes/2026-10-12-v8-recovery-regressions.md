# V8 physical execution and recovery regressions

[verified] The V8 diagnostic target was installed and fully read back on the
owner's FM-1. The 20-second diagnostic boot returned to ROM, and the native
trace read completed. This proves execution, not visible display output;
owner display confirmation remains outstanding.

[verified] Returned admission originally received the staging lineage instead
of the native worker's retained `run/lineage.json`. A distinct corrected
envelope passed the unchanged validator; original failed evidence is retained.
The source sequence now uses the retained lineage and has a routing regression.

[verified] The independent backup child completed successfully: two matching
1 MiB target reads and 8,757 recorded commands. Owned capture cleanup succeeded.
The outer wrapper failed afterward comparing tuple stat identities with their
JSON list representations. The ambiguity receipt is retained, and is not a
successful wrapper receipt. A fresh passive inspection found numerically
matching USB/SG identities. No later device command was sent in this change.

[verified] A tracked wrapper source copy corrects only that SG comparison using
JSON encoding with nonfinite values rejected. Its frozen historical dependency
pins remain unchanged. A deployed derivative needs explicit source review and
new one-use paths; the consumed V8 pipeline must never be replayed.

[verified] 84 cases passed in 16 Hera containers with networking disabled and
no device mounts. Exit statuses, OOM flags and XML results were inspected;
no failed, errored or skipped cases, and all owned containers were removed.
Private evidence: `build/v8-recovery-regressions-16-20261012/verification.json`;
remote evidence: `/home/claude/fm1-v8-recovery-regressions-16-20261012`.
The initial local run passed the new focused cases but an existing Linux-root
test failed its platform gate on macOS. The authoritative full run is Hera.

Current recovery dependency: independently validate the completed backup and
the exact post-child failure, preserving all old receipts, then prepare a
distinct pinned stock restore. Stock restoration and normal boot are still
pending. The diagnostic target remains installed with the fixed RAM loader.
Captured Cynthion data is saved privately; framing was checked, transaction
decoding remains outstanding. Visible probe, interrupted/corrupt recovery,
required review/CI and integration remain acceptance gates.

## Independent retained-backup checks

[verified] The unchanged canonical `validate_completed_backup` accepted the
actual retained backup with preserved original journal. Campaign hash
`ad11bf7e162381b7b5c29849bcb4b0bfd31aa92b923f3b53a307b0d35ff9e89f`,
manifest `a94ffd74d85cab828c5779620c22943f943a5e30d4d73deb6ead49bf81784075`,
commands `fd37cd4f87feb19bb1fdb8df64c867000bb7d8745abe04fd11ffe211285200bb`.
The check performed no device I/O.

[verified] `tools/fm1_admitted_backup_postchild_evidence.py` separately validates
the exact retained failed wrapper source, successful child, live owned capture,
ordered finite timestamps, known post-child SG comparison error, and completed
owned cleanup. It retains all eight file hashes and explicitly reports
`wrapper_succeeded=false`, `restore_authorized=false` and
`current_connection_verified=false`. It cannot prepare or execute a campaign.
Its actual live-evidence check passed without device I/O; no receipt was changed.

[verified] Final classifier tests passed 37 cases across 16 isolated Hera
containers; inspected exit/OOM/network/XML results, no skipped cases, containers
removed. Private proof: `build/v8-postchild-evidence-16-v2-20261012/`.
The first classifier assumed nonempty stdout; live inspection established the
successful CLI is silent. Corrected tests allow empty stdout while rejecting an
empty USB capture. The earlier 35-case run and failed live check are retained.

Next compose a separately reviewed restore preparation using both checks and
the unchanged canonical factory. Do not alter the original preparer's rejection
of ambiguous wrappers or rerun the consumed backup. Then review a new wrapper
derivative with canonical SG comparison, start a new Cynthion capture, execute
the bounded stock restore once, verify full readback, and separately admit stock
boot. Those operations remain pending.
