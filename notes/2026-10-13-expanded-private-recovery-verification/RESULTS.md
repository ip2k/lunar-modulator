# Actual expanded candidate recovery verification

First campaign: 32 cases in 30 Hera containers; 28 passed and four failed.
All containers exited without OOM and were removed. Recorded source hashes
match checkpoint 61423215 [verified]. Full logs are retained privately in
`build/expanded-private-recovery-v1/` and Hera `out/expanded-private-recovery-v1/`.

The four commit-erase install cases completed rather than losing power: the
test counted changed sectors, but the real candidate has 213 changed sectors
and only 170 erase operations because 43 sectors are already blank. No intended
final-erase interruption occurred in those four cases. This is a test injection
error, not proof of successful recovery at that boundary [verified logs/source].

The helper now counts erase/program operations from actual initial/desired bytes,
including skipped blank sectors/pages, and checks the actual torn page within
its sector. Corrected campaign v2 runs all 32 private cases plus eight synthetic
regressions, split into 30 Hera containers. Terminal v2 results: all 40 cases passed across 30 containers, with no nonzero
exit or OOM. Every shard log was inspected and all 16 recorded source hashes
match the tested worktree [verified]. Owned containers were removed. Public
receipts: `v2-verification.json` and `v2-source-hashes.json`; full logs remain
private under `build/expanded-private-recovery-v2/`.

Private inputs and simulated boot registration do not prove physical boot,
settings migration, OTA installation or hardware recovery. No device command
was issued during either campaign.
