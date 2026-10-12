# Packetry application discovery and live capture

Personal/non-commercial. The owner resumed work after the desktop/macOS restart.

[verified] Computer Use discovered `~/Applications/Packetry.app`, displayed its
GTK window and controlled capture start, stop and save by screenshot coordinates.
GTK exposed only limited accessibility nodes. The process ran as the logged-in
user despite the owner's `sudo open` launch; Cynthion access worked in this session.
No target-power toggle or FM-1 command accompanied this capture.

[verified] The full-speed capture saved 5,458,012 bytes. Its big-endian pcapng
block lengths and trailing lengths all agree. It contains 19,563 enhanced packet
blocks and 148,654 custom analyser-event blocks, matching Packetry's displayed
168,217 total. SHA-256:
`61bc6069223f1219a235e9a848b68af2ea99f94b9665754fa42d26ae46693d33`.
The private capture and structural receipt are under
`build/packetry-live-capture-20261012/`. Packetry showed zero decoded devices and
endpoints; this proves analyser capture, not fresh enumeration or device recovery.

[verified] A passive bench check found normal FM-1 USB `4c4a:c755`, bus1/device8,
and `/dev/snd/midiC2D0`. Hera responded at `claude@192.168.1.48`; its unrelated
`ray-worker` container was left alone. No power cycle was needed at this point.
Historical flash/entry/reset markers remain consumed and old backup freshness
windows remain expired.

[verified] At owner request, the wrapper installer and tested Apple Silicon
bundle archive were uploaded to the separate private repository
<https://github.com/ip2k/packetry-macos-wrapper>. Local/remote main matched
`619c461e405ca4910179466bb258ed4a340b7fb5`; GitHub reports private visibility.
The archive preserves Packetry's BSD notice. It depends on Homebrew libraries;
embedded dependency notices require review before any public binary release.
No captures, firmware dumps or credentials were included.

[verified: source integrity only] Root read the V6c recovery rehearsal runner,
delta, proposal and test entry points, and replayed all 1,786 archive member
hashes against its snapshot. The sole source addition is the existing test-only
wall-clock launcher. Runner pin:
`ecfb0b7fe79f4f20d5c6ac96662c582d2b2f2bbdd3b480e7b53fb28a1881c275`.
Archive pin:
`055aad2025124c7b8a42681a6355ec689b7d9b4a35a3b0ac28335088f161e3d3`.
A distinct model-only run was started on Hera under
`/home/claude/mvave-fm1/owned-restore-v6c-resumed-20261012/` with session label
`partial-stock-restore-wrapper-model-v6c-heavy-proposal`. Its containers have
network disabled, no device bindings and read-only fixture mounts. Results must
be retained and checked before acceptance; launch alone is not a passing result.

The installable firmware goal remains active by owner instruction. Physical
installation, boot/display acceptance and full recovery remain outstanding.
Continue with the recovery rehearsal result, V5 file-only stager review and
actual partial-recovery plan before activating a fresh hardware campaign.

## Recovery staging and rehearsal follow-up

[verified] The V5 source-only stagers copied and hash-checked 107 main/entry
files and 80 recovery-root files on bench01. Their receipts record no source
execution, factory invocation or hardware open. An initial relative-path CLI
invocation was rejected before creating destinations; the subsequent invocation
used absolute input paths. The four activation gates remain closed.

[verified] V6c finished with the CLI smoke test passing and its heavy wrapper
model failing after 252 seconds. The canonical admission verifier could not find
`firmware/sdk-diagnostic/board.c` in the temporary recovery stage. Private inputs
remained unchanged. The private retained failure archive SHA-256 is
`ce9bba5691ae1d299cd5084099d1e109c8fceda1d388afb879d7cda933d2e960`;
155 regular files were retained and all 133 temporary-inventory hashes replayed.
The stopped failed container remains retained on Hera.

[verified: file inspection] This is also a production staging omission:
all 11 `/source/firmware/...` inputs from the native build manifest are missing
from both V5 recovery source roots. Their worktree bytes match all manifest pins.
The three build-audit tools already exist with matching pins. Do not activate
the current V5 hardware sequence until those missing provenance inputs are
included in an independently checked recovery staging closure.

[verified: launch only] V6d changes only the helper model fixture to copy exact
native-manifest source/build-audit inputs and the consumer's producer-test hash.
Production helper, adapter, verifier and wrapper bytes are unchanged. Fresh Hera
root: `/home/claude/mvave-fm1/owned-restore-v6d-resumed-20261012`.
Source archive SHA-256:
`46c95465a0be342f8fae9856b11e0b05d5e73cc7793cc25d7333036399e2a3ba`.
Runner SHA-256:
`8ad4c6017287bba985c59db335f85e91b0145bacf9aef278661d5da4482af1df`.
The heavy test is still pending. Its helper/adapter/wrapper versions precede
V5, so even a pass must not be claimed as acceptance of the newer V5 pins.

[verified] CI run 38294796000 targets exact head e967af98 and was still running
when checked. Latest passive bench check again found normal FM-1 `4c4a:c755`
at bus1/device8 and its MIDI port; no physical power cycle was needed. No firmware
write, reboot, soft key or target-power operation accompanied these checks.
