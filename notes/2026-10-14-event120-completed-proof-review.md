# Event120 completed-install proof review

Reviewed proof commit  on Hera. The proof wrapper pins its imported project dependencies before import, records replay-source hashes in the returned evidence map, checks exact V2 campaign/candidate/transport/backup/plan/journal/result/transcript bindings, and delegates the transcript’s sector/readback semantics to the pinned pure replay. Admission, installability, boot and physical recovery remain explicitly false.

The V1 stopped-attempt validator now matches the retained event schema: campaign identity is on the prepared row; the terminal stopped row has only . The prepared identity, exact two-row count, terminal , , monotonic finite times, consumed marker, campaign and transcript bytes are all pinned. I invoked  directly against the actual retained Hera transcript; it returned the expected pre-SG proof with zero SG commands, reset commands and write intents. This is retained evidence validation only.

Source execution must retain the coordinator’s fresh private  contract: use a newly created root-only directory with  before importing the pinned modules, so pre-existing bytecode caches cannot substitute code after source-file hash checks. No code change was needed for that operational control. The proof worker’s pytest set is portable and does not reach into private absolute paths.

Checks:  passed 8 tests; commit c28058350a9837ec9a100f2200f98d172ca0dd35
Author: ip2k <humbugs_pride_6u@icloud.com>
Date:   Wed Oct 14 10:07:05 2026 -0700

    Pin Event120 proof dependencies and match retained V1 stop passed; direct V1 retained-transcript verification passed. The synthetic completion tests exercise the actual replay, but this review did not independently run the wrapper against the live V2 output bundle. That completed-bundle proof remains a coordinator acceptance step. No device command was issued.
