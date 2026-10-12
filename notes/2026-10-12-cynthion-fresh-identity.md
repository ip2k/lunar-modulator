# Cynthion connection and fresh identity

[verified: owner screenshot and passive bench sysfs] CONTROL connects to the
Mac, TARGET C to bench01 and TARGET A to the FM-1. Packetry captures Full Speed
12 Mbps and decodes the normal FM-1 USB descriptors. The fresh passive artifact
SHA `7a062e09a4f6383885e5d3784825039c209a183af483b76f880d4c6aa7aafcc0`
observed port1-1,bus1/device3,4c4a:c755 at1791795886.2641566.

[verified: physical query and independent receipt replay] Root deployed a new
private one-use identity packet. Source SHA
`22a4f5369847af3f91a0c00a06cbb6966895021025f5a64da650fc4611058b39`
retains eight accepted identity-wrapper function ASTs; capture changes only
usbmon3 to usbmon1. Deployment hashes and a zero-command preflight passed.
Exactly one query `f0 00 32 45 00 00 00 40 7f f7` was submitted at
1791796140.650997. It returned the exact known41-byte FM-1_092 reply, including
the previously documented checksum exception. The process exited zero and
terminated only its owned capture group with returncode-15. No soft key, loader,
reset or flash operation occurred; no device command has followed this query.

The capture contains22 records and exactly one16-byte USB-MIDI OUT transfer
encoding that10-byte query. The kernel capture truncates the56-byte reply
transfer to32 payload bytes; the actual MIDI receive log preserves the complete
41-byte reply. These are distinct evidence limits. Receipt archive SHA
`aa0857d431f5eedd6b903806becfae9ed7da57e4fda4890406e0c77d6a416dd0`;
independent review SHA
`39aabe793b522f066b0d89a43faa897bf8f9db082a302ebe04002df1012ed070`.
Ignored evidence: `build/sdk-trace-fresh-entry-bench-v1/`; private bench root:
`/home/claude/fm1-sdk-trace-entry-20261012/`. The identity marker is consumed.

[verified: tool limitation] Computer plugin inventory omits Packetry. Both
`getApp("Packetry")` and selection by `/opt/homebrew/bin/packetry` return
Invalid app. No window clicks were performed; owner capture remains running.
Fresh soft-key entry and two matching stock backups are the next physical
steps, after the successor installation/boot/read path is ready.
