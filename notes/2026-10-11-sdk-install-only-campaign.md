# Exact SDK diagnostic install-only campaign

[verified] `tools/fm1_sdk_install.py` is a distinct runner for the private SDK
diagnostic target. It uses the unchanged, pinned `fm1_sdk_rehearsal.py`
(`f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4`)
factory and SG transport. It validates both install and restore policies,
executes only install, then verifies the complete NOR image. The original
rehearsal's wire allowlist, source pins, loader guards, and directory-last
transaction behavior are unchanged.

The new exact schema has six fields:

```json
{
  "schema": 1,
  "kind": "fm1-exact-sdk-install-only",
  "adapter_sha256": "<reviewed actual fm1_sdk_install.py SHA256>",
  "rehearsal_campaign_path": "/absolute/private/rehearsal-campaign.json",
  "rehearsal_campaign_sha256": "<SHA256 of that exact file>",
  "receipt_path": "/absolute/original-backup-receipt/new-install-receipt"
}
```

[verified] The underlying campaign retains the frozen rehearsal schema and
adapter hash. It must name the exact current fixed-loader backup, original
private receipt parent, actual loader/profile bytes, inventory/entry evidence,
prepared transaction, SDK ELF/app/audit and stock reference files. The new
receipt path must equal that underlying campaign's already-validated path.
The new Prepared object is registered by identity, exposes only the install
policy, and rechecks both campaign files, both adapter sources and the
underlying frozen artifacts before binding and mutation. The initial pinned
rehearsal source read is bounded to 2 MiB, opens with NOFOLLOW/NONBLOCK,
and requires a regular file before importing the frozen reader. Both runners consume
the same `.sdk-rehearsal.consumed` marker, preventing adapter or receipt-name
changes from reusing one attested loader session.

[verified] Successful output records the target SHA and complete NOR
verification. It records `stock_restore_preflighted: true`,
`stock_baseline_restored: false`, `boot_observed: false`, and
`physical_recovery_verified: false`. Errors stop without retry or automatic
restore. A close failure, including `KeyboardInterrupt`, or final receipt/log
failure invalidates success. The runner never permits FC0C, ROM entry, upload,
eFuse commands, arbitrary NOR ranges or target boot.

The physical sequence remains separately reviewed: fresh fixed-loader backups,
exact install/full readback, a target-specific FC0C boot adapter that verifies
the install evidence, observation of the diagnostic display, the proposed
20-second P33 recovery, then fresh ROM entry/backups and a newly bound stock
restore. Root owns hardware execution. A source/model check cannot establish
display output, physical recovery or transport timing.

Device-free test evidence and exact source/artifact pins are retained in
`build/sdk-install-test/handoff.md`. Actual-fixture tests use the private pinned
ELF and recorded NOR/campaign files through the production gates; SG traffic
is modeled, and disposable containers never mount the physical bench backup
path. No vendor binaries are committed or distributed.
