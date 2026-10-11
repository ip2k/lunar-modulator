# Single RAM-only recovery probe — 2026-10-11

## Authorization and scope

[reported: owner] The FM-1 need not remain running while the owner is away;
a later manual power cycle is acceptable. Cynthion remains deferred. The
reviewed experiment permitted one exact 700-byte RAM probe after a fresh
FM-1_092 identity and same-port soft-key entry, with exclusive device access,
capture established before entry, no flash commands and no retry.

The exact artifact and fixed transport are documented in
[`firmware/ram-recovery/README.md`](../firmware/ram-recovery/README.md).
Independent preflight and result reviews remain in ignored
`build/ram-probe-review.md` and `build/ram-probe-result-review.md`.

## Observed result

[verified: bench01 event log and usbmon] Normal FM-1 on USB `3-2`, device 19,
answered as FM-1_092. The vetted soft key was sent once. The same port
enumerated `4c4a:8057`, `WL80UBOOT1.00`, device 20. Two fixed encrypted
512-byte uploads completed with successful BOT status. One jump to
`0x01c02000` was submitted. Its expected 16-byte reply was lost:
`SG_IO status=0 host=7 driver=0 resid=16`.

[verified: capture] Port connection-loss status arrived 159 microseconds
after jump CBW submission, or 103 microseconds after completion. The same
port subsequently enumerated UBOOT as device 21, about 0.8 seconds after
jump intent, and remained there at the end of the 15-second observation.
Enumeration latency is not instruction/reset latency. The driver's observer
was passive; Linux usb-storage continued ordinary device probing.

[inferred] This timing supports an immediate effect of the jump. It cannot
distinguish the intended marker/P33 reset from an immediate fault/reset or
other ROM jump behavior. There is no independent execution witness for core
zero, marker write/readback or P33 transaction completion. Application-origin
recovery, full-image restoration and USB_KEY entry remain unproven.

[verified: full CBW parse] The 62 captured CBWs comprise 3 INQUIRY,
26 TEST UNIT READY, 28 REQUEST SENSE, 2 PREVENT/ALLOW MEDIUM REMOVAL,
2 RAM WRITE (`FB06`) and 1 RAM JUMP (`FB08`). No loader/flash vendor command
or ordinary block-read/write command appears. No extra device command was
sent by our driver. Flash bytes were not reread, so this result is not a
byte-identical-flash verification.

## Private receipts

No vendor binary, flash dump or private capture is committed. The private
receipt is retained locally under `build/ram-probe-bench/receipt/` and on
bench01 at `/home/claude/fm1-ram-probe-20261011/receipt/`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Probe | 700 | `4498aabad49b5acf1c4f90d949463b590e76e56acf80d6e6d01b292ee9d32c42` |
| Fixed driver | 3983 | `8c96204a652d22d8693b0f048bb9526a2f19634420aacd540a8c958f3014aa89` |
| Event log | 6375 | `58f1b2def18eddaadc3a23e1a4fa79bd2b256101b4fefe2c3e56345fb1d1b40b` |
| usbmon text | 31638 | `a83aeef279d1357ea1cc0782752ba9ac1b0da1a234189a3b9f445f6904721075` |

[verified] Text usbmon records transfer lengths and successful upload status,
but contains only the first 32 payload bytes. Both prefixes match the guarded
ciphertext. The full wire payload is not independently retained by that text
capture. The copied transport modules match the worktree source.

## Next steps and recovery boundary

Device commands stopped after this one attempt. Leave the current UBOOT state
until the owner can perform a real cold power cycle; then obtain owner normal
screen/operation acceptance and fresh read-only identity. VBUS switching alone
is not a proven cold cycle of this battery-powered unit.

Continue offline bring-up and recovery work on Hera. Close startup, memory,
core/exception, watchdog, clock/timer and PA2 contracts, prepare a concrete
stock-preserving diagnostic image, and review its recovery plan before any
application-sector mutation. This probe does not complete the installable
diagnostic milestone. A later experiment needs a separately reviewed execution
witness; do not automatically repeat this probe or infer a safe RAM-read ABI.
