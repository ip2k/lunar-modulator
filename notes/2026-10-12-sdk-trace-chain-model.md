# SDK trace chain V3: composed model and remaining hardware gates

The closed V3 proposal passed one genuine composed helper/factory case and
30 phase cases on Hera. The genuine case took 410 seconds. Root and an
independent reviewer replayed `check-retained-v3.py` against the retained
source archive, XML, container inspection/removal receipts and transaction
artifacts. [verified: retained model evidence; no hardware execution]

The model executed the actual entry/backup preparation, identity derivation,
install preparation and canonical installation, boot, native-read, admission,
returned backup and full-target stock-restore factories. Production authority
registries and pinned factories were unchanged. Its command inventory was
8,757 initial-backup requests, 10,653 install requests, one reset, five native
RAM reads and 19,410 returned-backup/restore requests. The original install
journal survives byte-identically in both retained copies; the live journal
records restore, and full final stock readback matches the pinned baseline.
[verified: modeled execution and retained command/journal receipts]

There were 31 isolated containers with the pinned image, 2 CPU/2 GiB limits,
4 GiB combined memory/swap, no network, no device passthrough and no privilege.
All exited zero without OOM, all removals succeeded, label queries were empty,
and read-only input inventories were unchanged. The archive checker matched
all 1,801 source files; the 30 phase XML cases are unique. [verified: retained
invocations, inspections, XML, inventories and cleanup receipts]

V1 and V2 failures remain preserved. V3 corrects the entry-source pin and
supplies the transaction geometry required by the actual install factory.
Flash size comes from the completed backup manifest; sector/page geometry and
the JEDEC gate come from reviewed worker constraints. These are not new device
measurements. Original identity reply, observation time and topology remain
unchanged. The file-only stager leaves the 73-file frozen source stage intact.
[verified: source review and proposal closure]

The model substitutes USB/SG discovery and transport, clocks and capture
observations. The outer sequencer, real subprocess interpreter/environment and
capture supervisor were not executed. Real 120-second admission timing,
descendant cleanup, interrupted-write physical recovery, CPU/SPL behavior,
normal boot and visible display remain unproven. The separate retained-loader
partial-to-stock branch is required for a caught partial NOR write; full-target
restore does not admit that state. [verified: model scope and source gates]

Before the next physical invocation, complete the outer lifecycle model and
the genuine partial recovery wrapper test; bind the four currently closed
activation pins to concrete reviewed source/recovery artifacts; create fresh
private empty run directories; then observe fresh normal USB/MIDI and run the
timed sequence once. Keep failed attempts, consumed markers and timestamps.
The next hardware objective is the five native RAM reads before a loader
upload, followed by canonical stock restore and diagnosis of the recorded
firmware phase. [verified: reviewed source requirements; planned hardware work]

Ignored evidence directory:
`build/sdk-trace-fresh-entry-bench-v1/next-campaign/automatic-trace-chain-v3/`.
Important SHA-256 pins:

- Source/model archive: `a37c93aa8fed125c67eefb61ac387fbb906ea78059bc6b3951514217cc60c62d`.
- Closed proposal archive: `83c519b55c4cd3f4696a59f3f66ae637b832d4502624976bc21243185afc10c6`.
- Retained model receipts: `dc18f71a5ab2c0197b83d0a9c47d7c1b515f23e02ad36e1ef11d6b1bcedb6979`.
- Retained phase receipts: `63c5e0570125c2fba6f5f5f4fd8cc53fe8825d61d51e0712783c777240338ee9`.
- Retained checker: `de5db38ccec2d8c72732de7e0f27e4a5c93de6a09e3a5ec7453bf508762380c8`.
- Checker result: `c04db74e5b5411338bcb6076f07e9474c30b01dcb9c7e4545d1fd1117547e386`.

The full code audit is due after growth beyond the d7111a9 baseline trigger.
A mechanical delta inventory is not a substitute for its file-level review.
Packetry native control remains blocked by a false locked-Mac response from
Computer Use despite the owner's confirmation; bench usbmon remains the
independent capture route. [verified: tool response and owner observation]
