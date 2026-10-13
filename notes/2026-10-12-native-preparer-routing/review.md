# Native preparer routing and next diagnostic campaign

[verified: source] The tracked lifecycle sequencer still selected the original
untracked build helper that failed in V7 because its packaged dependency set
omitted fm1_fixed_target_reset.py. It now selects
STAGE/tools/fm1_prepare_native_read_packet.py. The tracked replacement retains
all original input/source pins and packages its transitive dependencies.
The lifecycle source pin was updated to the actual edited source hash.
Consumed V7 stages and original receipts were not changed or replayed.

[verified: Hera models] 79 unique checks passed in 16 parallel containers,
no failures/errors/skips/OOM. Included isolated dependency omissions, actual
first-child CLI failure/consumption, nonroot rejection, and capture lifecycle
models. These do not prove a physical native read, display or reset cause.
The first run omitted the lifecycle JSON fixture and failed collection; its
terminal logs/inspections were retained before removing all 16 containers.
The corrected run retained all XML and inspections and removed its 16 owned
containers. Stage: /home/claude/native-preparer-routing-16-v2-20261012.
Local private artifacts: build/native-preparer-routing-16-v2-20261012/.

[verified: source-only proposal] A new V8 closed sequence is saved privately at
build/fresh-diagnostic-v8-proposal-20261012/sequence-once.closed.py.
It derives from the original closed V7 sequence with new V8 paths and the
tracked native-preparer call. All four activation pins remain None; it cannot
execute a physical chain. Its proposal receipt records its hash and pending
gates. Do not use an old snapshot, rewrite freshness timestamps, copy consumed
markers into a new campaign, or treat this proposal as a launch receipt.
A fresh stage must include the tracked preparer plus all its pinned tool and
repository dependencies; updating the call site alone does not stage them.

[verified: current USB] bench01 still enumerates normal FM-1 4c4a:c755 at
bus 1 device 11; previous actual identity is FM-1_092. No device query, reset,
flash write or power cycle was performed in this routing checkpoint.
The recovery README now describes the retained FINAL_START_INTENT trace and
its limits instead of claiming the component never executed on hardware.

Next: assemble and review the fresh V8 source closure and unchanged firmware
inputs; obtain exact-head CI acceptance; use fresh entry identity and dual
matching flash backups; then one owned diagnostic install/boot/native-read/
stock-restore campaign. Display observation and physical interrupted/corrupt
write recovery remain required before overall acceptance or integration.
