# Diagnostic install and first physical boot trial

Personal, non-commercial. The active milestone remains a diagnostic application
that boots, displays its probe and retains verified recovery. The earlier
complete install/readback/stock-restore/readback rehearsal and subsequent
stock identity response are verified separately in the SDK rehearsal note.

[verified: physical entry, pre-transport backup failure] A fresh identity/key
attempt returned the exact known `FM-1_092` identity and entered same-port
ROM device 25. The fixed backup adapter stopped while discovering an SG node:
Linux had enumerated USB before creating that node. Its complete two-event
log contains `campaign_prepared` and `campaign_stopped_ambiguous`, with no SG
intent or completion. Outer and backup child exits were 1; the entry child
exited 0. No backup manifest or dump was published. Preserve the consumed
entry marker and failed receipt; do not rerun the original campaign.

Private failure archive `build/diagnostic-boot-physical/fresh-pretransport-failure.tar.gz`
has SHA `7a322730f0b21538330bdeb028afa084c3cb931a3cad1d50c21dc95a1d91c7fa`;
entry `91f7bd4761889acec1061955e1981e5046550d1f8781ebffb913b1d4b3321f66`;
failed campaign `a990f0ff879e7c3ddafcedea45cbe59917b76da57ddbee57e368548764e0f146`;
failed log `96a637fbaed6564c62d45532e5e9c84acb5d74f24d1908849aff6ac3b573e2f1`;
capture `c45977567a700b26e6886cf91e14d463e12042d309602a8a2268028544191e1d`.
The owned capture was stopped and fsynced. The later SG node's ancestry was
observed passively on the same device-25 ROM connection. This is not loader
upload, backup, image installation or diagnostic boot evidence.

[verified: reviewed continuation and complete fresh backup]
A distinct private one-use wrapper continued only this proven discovery
failure. It pins the failed entry/campaign/log/capture, requires zero ROM bulk
traffic in that capture, verifies terminated original processes and unchanged
live ROM/SG binding, and retains the unchanged 600-second entry-age gate.
It preserves the original marker and adds a parent-scoped continuation marker
before creating a separate private receipt parent. It uses the unchanged
fixed backup adapter and its exact command envelope, without another identity
request, soft key, reset or NOR write. Its concrete source and final verdict
were independently reviewed before activation. A partial upload or ambiguous SG request
does not qualify for this continuation.

Wrapper `333a71295c773781341b2e39d5462155666b9a38834284147116a5af0eff022b`
ran once. The backup child exited zero, followed by the owned capture stop.
Both complete 1 MiB dumps match the original stock image
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
Independent replay verified all 8,757 vendor requests and their ordered BOT
CBW/data/CSW completions, upload prefixes against the fixed loader, and all
8,192 flash pages against the dumps. The final completion was 557.912 seconds
after entry, inside the unchanged 600-second gate. Eighteen standard kernel
requests were separated from the vendor transcript. Usbmon text carries only
32-byte payload prefixes; this is not a full-payload wire comparison.

Private continuation archive
`build/diagnostic-boot-physical/continuation-v1.tar.gz` has SHA
`006d722587698eca71e3b123b50fe0af01abcba1b99bf5773ecbf718c31a7cc9`.
The independent acceptance is `build/fixed-backup-physical-preflight.md`, SHA
`3c99af4b24109681e1b44dafbd2f5c2a818be133a9808bdcc382b98fe3fd49c5`.
No NOR write or reset occurred in this backup. Its original failed receipt and
marker remain intact. Same-session no-later-device-command attestation is
still a separate operator precondition for installation.

The fresh install-only packet has been prepared and passed actual staged-file
preflight without opening hardware. Archive SHA
`9c8a342e941678ca39d76d08a4644026a6a5de728a15bde1330594e096f83379`;
install campaign
`59bf948503e6084f1672b485a497a20d18ad5179a6e132b7e16ce65fb02b6067`;
one-use capture wrapper
`f59b80714a2abf9b636911ad4270bdfd3560ff97b3327ae5a478d52ce4ea4629`.
Its final concrete independent review is pending; no install/reset has run in
this session yet.

Next: independently accept that exact install-only packet; install and verify
the full target; separately review/execute its one-shot reset; establish actual
boot/display/recovery evidence; restore and verify stock with a fresh recovery
binding. No diagnostic application behavior has been accepted yet.
