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
