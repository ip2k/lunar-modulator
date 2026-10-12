# SDK-trace completed-stock reset adapter

[verified: source review] The distinct `fm1_sdk_trace_stock_reset.py` adapter
pins the genuine SDK-trace completed-stock restore validator and the existing
reviewed single FC0C arg1 transport. Admission requires the exact target and
baseline, all 30 sectors restored with directory last, frozen restore evidence,
the unchanged fixed-loader binding and absent conflicting evidence. The
receipt and consumed marker also refuse broken symlinks. No upload, flash,
read probe or retry is introduced. Request completion does not prove boot.

[verified: modeled checks] 63 syscall/admission cases passed in 16 isolated
Hera containers, zero failures/errors/skips. Exact collected node union,
source immutability, terminal exits, image, resource limits, no network,
no privileged/device mounts and removal of these containers were checked.
These cases explicitly inject the completed-restore proof; they do not prove
factory provenance. Retained evidence is private under
`build/sdk-trace-stock-reset-16-20261012`; public hash-only results are adjacent.
Two collection setup failures were corrected (preexisting image work directory,
then missing test-module PYTHONPATH), without weakening assertions.

[verified: modeled integration] The separate genuine-factory test passed on Hera at
`/home/claude/mvave-fm1/sdk-trace-stock-reset-actual-20261012`. It preserves
source pins, completed-proof factories and registries and models the device
only. Its acceptance gate is completed restore admission followed by refusal
when conflicting evidence appears after durable reset intent, with no reset
ioctl and a consumed attempt. One pass, zero failures/errors/skips in 407.97 seconds; terminal isolation and cleanup verified. Private retained archive hash is recorded in genuine-verification.json.

[verified: tooling limitation] Rarefaction and Serena still select the primary
checkout rather than this managed worktree. Bounded queries could not find
the relevant reset source there. Actual-worktree file inspection was used;
shared active project selection was not changed. No semantic coverage of
this worktree is claimed.

Physical diagnostic boot/display and stock boot remain unverified. This new
adapter is a separate post-restore step; the closed staged V7 sequence and
its source closure were not changed or activated by this work.
