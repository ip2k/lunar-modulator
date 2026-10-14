# Current thirteen-engine expanded candidate

[verified] The real private CLI constructor now selects vendor objdump's r3
CPU decoder explicitly. The current stack-readout ELF reconstructs an 845916-byte
application and a private full-flash target. Its SDK-free link, entry, provenance
and expanded geometry gates pass. Exact target/ELF hashes are in candidate-summary.json.

[verified] All 53 geometry and rejection tests passed across 30 Hera containers,
with zero exits and no OOM. Every recorded source hash matches this worktree.
Receipts: gate-verification.json and gate-source-hashes.json. Private image and
full receipt remain in build/native-current-candidate-20261013/ and Hera
out/current-candidate-private-v1/. No firmware bytes are published.

This is offline construction, not physical admission, migration, rollback,
real-time acceptance or web installation. A current-image 40-case interruption/
recovery campaign is running on Hera; its completion must be inspected before
claiming success. The old actual-byte result covers an earlier target.

## Exact current-device offline plans

[verified] expanded_bench_transactions.py seals the fresh device36 backups and
current target to native install/Trio restore and subsequent stock install plans.
The existing durable transaction engine is source-pinned, and reloading checks
all saved image hashes and directory-last sector order. Current native plan has
213 changed sectors; Trio-to-stock has13. Public summary: device36-plan-summary.json.
Full plans and images remain private in build/native-current-candidate-20261013/device36-plans/.
Nine boundary checks pass;32 actual-byte private tests skip without private inputs.
A separate fresh-Trio baseline campaign is prepared for Hera; results are pending.

No physical writer exists for these plans. The new geometry_baseline test argument
keeps validation anchored to the original stock components when simulating a
transition from the physically installed Trio image. Earlier stock-baseline
campaigns keep their unchanged default. Physical settings preservation, boot,
rollback and realtime acceptance remain unproven.
