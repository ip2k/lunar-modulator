# V7 launch and failure recovery review

[verified: source review] Reviewed the staged one-use sequencer, entry/backup
orchestrator, fresh identity derivation, and file-only partial recovery helper
against the closed V7 inventories. The sequencer checks all four activation
pins before persistent activity, freezes child sources before invocation, and
records exclusive intent/exit receipts. It does not retry a consumed chain or
kill an outer wrapper that owns capture cleanup. Every hardware child retains
its own admission checks. Canonical baseline replay prepares evidence only;
it does not call the reset transport.

[verified: source review] The entry child requires a fresh normal USB/MIDI
binding, queries the actual identity before its single vetted soft key, and
the backup requires two matching full-flash reads before install preparation.
The bounded diagnostic path preserves stock SPL, OTA and cfg. The subsequent
native read and returned-target restore require their own fresh provenance.
Chain completion records complete stock readback separately from boot,
display and physical recovery acceptance.

The reviewed proposal is `partial-recovery-plan-proposal.json`, SHA256
`0ee6ac405cc0b5cd7453624921c324e5f27501198da762c342b93f1d83cd7e63`.
Its INSTALL and RESTORE paths match the actual sequencer destinations. The
accepted R model exercises the genuine helper and owned wrapper, including
uncertain writes and restore ordering; it does not prove physical transport
or successful hardware recovery.

## Invocation boundaries

These are command templates, not runnable approval receipts. Replace each
uppercase evidence argument with the hash/path derived from the actual
accepted evidence. Never substitute a historical receipt, invent timestamps,
or reuse consumed directories. All Pi invocations use `/usr/bin/python3`
with `-B -E -s -S`, Linux root and the reviewed private sources.

Entry root: `/home/claude/fm1-sdk-trace-entry-20261012-v7`.
Install stage: `/home/claude/fm1-sdk-trace-campaign-20261012-v7`.
Acquisition stage: `/home/claude/fm1-sdk-trace-partial-acquire-20261012-v7`.
Restore stage: `/home/claude/fm1-sdk-trace-partial-restore-20261012-v7`.

After exact-head CI acceptance, concrete root launch receipt, reviewed recovery
plan, source closure and four literal activation pins have been verified, the
single sequence invocation is:

```sh
sudo -n /usr/bin/python3 -B -E -s -S \
  /home/claude/fm1-sdk-trace-entry-20261012-v7/sequence-once.py \
  --reviewed-self-sha256 ACTIVATED_SEQUENCE_SHA256
```

On a caught INSTALL or admitted RESTORE failure, first preserve and inspect
the child, capture, journal and commands. The exact retained fixed-loader
connection and complete owned terminal capture are required. A new ROM
enumeration or lost connection refuses this procedure. Build the direction's
request from actual failure hashes and a fresh passive connection witness.
Run the pinned file-only helper in that direction's acquisition stage:

```sh
sudo -n /usr/bin/python3 -B -E -s -S \
  /home/claude/fm1-sdk-trace-partial-acquire-20261012-v7/prepare-file-only.py \
  --request ACTUAL_ACQUISITION_REQUEST_PATH \
  --reviewed-self-sha256 d39ee727c961cd0b6613589808c3eb221b1e99128d8ccea44a928e63797f0101
sudo -n /usr/bin/python3 -B -E -s -S \
  /home/claude/fm1-sdk-trace-campaign-20261012-v7/build/sdk-trace-fresh-entry-bench-v1/next-campaign/partial-recovery-v7/owned-acquire-once-v1.py \
  --stage /home/claude/fm1-sdk-trace-partial-acquire-20261012-v7 \
  --run /home/claude/fm1-sdk-trace-entry-20261012-v7/partial-acquire-capture-v7 \
  --packet ACTUAL_ACQUISITION_PACKET_PATH --packet-sha256 ACTUAL_PACKET_SHA256
```

Acquisition performs two matching full reads without a loader upload or
reset. Only completed acquisition, validated protected bytes and a new fresh
same-loader witness admit the distinct restore request. Run the same pinned
file-only helper with that actual restore request, then the reviewed restore
wrapper
`/home/claude/fm1-sdk-trace-campaign-20261012-v7/build/sdk-trace-fresh-entry-bench-v1/next-campaign/partial-recovery-v7/owned-partial-stock-restore-once.py`
with the restore stage, `partial-restore-capture-v7` run and exact prepared
packet hash. The restore helper is the separate
`/home/claude/fm1-sdk-trace-partial-restore-20261012-v7/prepare-file-only.py`,
with the same reviewed helper hash. Its original 30-sector whitelist remains fixed; dirty
directory sector `0x4000` is restored last. Validate native completions, page
readback, zero unresolved uncertainty and the entire original stock hash.
Separately observe stock boot. Failure in this acquisition or restore stops;
nested readmission is unsupported.

## Current physical boundary

[verified: passive observation] The latest bench check enumerated normal
`4c4a:c755`, bus 1/device 8, MIDI `/dev/snd/midiC2D0`; no physical power cycle
was needed. No device command was sent during this review. Cynthion r1.4 is
detected, but exclusive interface claim is refused while another process
holds it. Computer Use reports the Mac locked. Owner was asked to quit
Packetry normally so a bounded headless capture can proceed.

Exact source head `a8dca15e60d8c18ac84f46572c246f08f45b6e09` has CI run
`38307343562` pending at this review. Activation remains closed. Physical
diagnostic boot/display and recovery of this image remain unverified.
