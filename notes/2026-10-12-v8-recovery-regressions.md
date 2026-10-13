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
