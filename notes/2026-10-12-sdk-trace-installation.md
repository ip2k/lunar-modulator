# Exact SDK recovery-trace image admission and install successor

Status: design/source investigation; no new hardware permit or production opener
is prepared. The parent owns device work, commits and push. This is a personal,
non-commercial private SDK experiment. [verified: current task authorization]

The old bound SDK gate pins app `991b569d…`, ELF `8832aa46…`, complete target
`df6c963e…`, and the original fixed-backup adapter. The frozen rehearsal and
install-only runner cannot admit another image by relabeling a receipt. [verified:
`tools/fm1_bound_sdk_diagnostic.py`, `tools/fm1_sdk_rehearsal.py`,
`tools/fm1_sdk_install.py`]

## Exact candidate and immutable dependencies

Proposed app SHA:
`76382f531491b63a9cb75258ae9299185219b55f201e5110a74eb03ab328bf44`.
ELF SHA:
`e9d54172bda7dd085fbd1a46ef35c353210f75ec5f621a3e352a075d7f2a6035`.
Trace nonce `6b5482dbb66b5f45ed73e2f26c4a4657`; ELF-allocated record
`0x01c02880..0x01c028c0` (64 bytes); diagnostic stage symbol `0x01c03418`.
Artifacts reside in `build/sdk-recovery-trace-hera/native-enabled/`; its
`build-manifest.json`, key/link audit, image audit, native listing/map and the
trace lane's `evidence-index.json` must be literal-pinned after independent
native/allocation acceptance. [reported: trace author; manifest read here]

The new complete raw NOR target hash is not yet sealed. It must be emitted by
the reviewed exact raw emitter and independently validated against stock
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
App size 120,688 suggests the same 30-sector extent, but the successor must
derive ranges from actual bytes and compare the exact sealed result. [inferred:
candidate size and existing raw geometry]

## Minimal separate successor

1. `tools/fm1_bound_sdk_trace.py`: offline actual-file admission, with exact
   app/ELF/nonce/allocation/build-audit pins and fresh matching stock-backup
   provenance. Recompute the unchanged SDK key/native/raw geometry gates; add
   trace-specific evidence only where the old gate does not describe the record.
   Build separate exact-instance install and restore policies using the reviewed
   transaction/framing primitives. Preserve stock SPL/config/OTA/protected tail,
   direction-bound payloads and application directory sector `0x4000` last.
2. `tools/fm1_sdk_trace_install.py`: strict new campaign and one-use install-only
   runner. Reuse only source-pinned `f696…` SG framing/binding through a new
   prepared object; do not alter its globals or invoke its old factory. Validate
   both directions first, then run install and verify the full new target. Add
   no ROM entry, upload, reset, retry or boot-success claim.
3. Private closed prepare/capture template under a new ignored build directory:
   literal pins are absent until exact candidate, fresh session and recovery
   packet review. It must issue unique destination/marker, own capture lifecycle,
   one child and preserved nonzero/ambiguous failure evidence.

The factory binds a fresh successful FM-1_092 identity/soft-key entry, full
8,757-command fixed-loader replay, two complete matching stock dumps, exact
loader/profile/reader source pins and the **new** USB/SG identity. Existing
historical receipts are evidence of past work only. After insertion of Cynthion,
neither the old USB path nor old SG identity is presumed usable. The operator's
no-later-command attestation is scoped to the new backup. [inferred: successor
design; verified: existing source requirements]

All source/evidence must be checked before opening and rechecked across durable
mutation intents. Prepared/policy objects require exact identity registry
membership; copies acquire no authority. Any uncertain command closes/latches
the handle, keeps the marker and forbids replay. The initial full-NOR read must
equal stock before any write; final full-NOR read must equal the new target
before success publication. Genuine stock restoration must be preflighted, not
claimed performed. [inferred: required preserved behavior]

## Remaining gates and limits

Before source activation: independent trace native/allocation review, unchanged
raw validator acceptance of exact candidate, exact emitted target/ranges, new
source/factory review and 16 isolated Hera chunks plus genuine private-file
modeled composition. Heavy work uses the pinned `7e32…` image, source read-only,
no device/network/privileged access and retained exit/OOM/removal evidence.
Before hardware: fresh entry/backups/current session, exact concrete install
packet and recovery packet. Reset, retained trace reads and recovery after this
new target need separate successors; the old target-reset and returned-ROM
helpers hard-pin the old image and stay frozen. Physical display/recovery, warm
recovery after a corrupt app and USB_KEY availability remain separate claims.

Semantic status/config were read during this task: both MCPs select the shared
primary checkout, not this worktree; Serena exposes C++ only and Rarefaction's
Python server was not started. No retarget/restart occurred. Bounded direct file
inspection is the fallback; no semantic worktree coverage is claimed.

Owned task paths are distinct new modules/tests/templates and this note. Parent
checkpoint for the preceding accepted model is
`a6164e5369e9cfb940ad1f456b52b3b7786b668d` [reported: parent push verification].
