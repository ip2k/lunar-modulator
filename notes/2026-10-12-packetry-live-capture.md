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

[verified: source staging only] The missing provenance files were subsequently
added to both bench recovery roots after a successful check-only invocation.
The stager uses the previously reviewed no-follow/private-file helpers, validates
all existing tool hashes, requires absent firmware trees and recovery attempt
files, and exclusively creates the 22 exact manifest-pinned source copies.
No source factory, hardware opener, entry command or activation gate is invoked.
A partial staging failure would be preserved without automatic retry.
Stager source, sealed inventory and actual receipt are tracked under
`notes/2026-10-12-recovery-provenance-supplement/`; private source archive remains
in the build evidence directory. Stager SHA-256:
`aa3863ab2563d48b97e322c1c23e283e756c5296197e37e29541391dd37c1d51`.
Archive SHA-256:
`f0ffe4884eed0ed34b32106c05b519fc82abc9d7c8e07f0193f09009a0895349`.
The original V5 staging receipts remain intact. This source-only supplement must
be included in root acceptance before any sequence activation.


### V6d terminal failure and V6e successor proposal

[verified: modeled execution] V6d passed the missing provenance-input boundary,
then failed after 253 seconds at the admission verifier's stage/run relationship.
It derives the original capture stage from the recovery verifier's own location,
although the recovery helper runs in its separate source directory. The failed
container remains stopped and retained on Hera. Private inputs were unchanged.
Retained archive SHA-256:
`cf588f07a0937bd4c6af87a6c93db0e64897697a1057824e9fbaae8b7eaa27af`.
166 regular files and all 144 temporary-inventory hashes replayed locally.

[inferred: WIP repair] Admission now derives the original stage from the frozen
native campaign's run directory. Its original wrapper/child AST derivatives,
packet hashes, private-directory checks and receipt relationships remain checked.
This source change is not accepted for hardware: tracked dependent pins still
reference the old verifier. A separately sealed V6e model successor updates the
transitive literal source-pin closure offline; no runtime pin, factory or registry
overrides are introduced. The assembly script and before/after hash delta are
tracked in `notes/2026-10-12-recovery-stage-successor-v6e/`.
V6e archive SHA-256:
`015c7eb055422c8b6c5a935f64889770e7d689824dcec3be40e57911ad5c07fd`.
Runner SHA-256:
`80c93dda16bb875882424db073c47f76a42d4e47a3b67e433846874534f81a5e`.
Remote root: `/home/claude/mvave-fm1/owned-restore-v6e-resumed-20261012`.
This proposal inherits older pre-V5 helper/wrapper behavior; passing it cannot
accept the newer staged V5 hardware pins. Next: inspect terminal results, retain
all evidence, review adversarial original-stage/path cases and replay the current
V5 successor closure before any bench gate activation.

[verified] Latest passive bench enumeration remains normal `4c4a:c755`,
bus1/device8 and `/dev/snd/midiC2D0`. No physical cycle is needed to continue this
model work. No firmware write, soft key, reset or target-power action occurred.
Active branch: `feature/2026-10-11@installable-firmware`; prior verified pushed
checkpoint `b0446d58d05996275b08c0d51792514dcea1372c`. The next checkpoint is WIP:
source pin acceptance and model verification remain outstanding.


### V6e mechanics results and current-adapter V6f rehearsal

[verified: modeled tests] All 235 collected mechanics tests passed across exactly
16 parallel Hera containers. Each container used the sealed V6e source inventory,
network isolation, no devices, no private fixtures and an independent source copy.
The first collector failed because its temporary destination already existed in
the image; it did not run tests. That failure remains retained. The corrected
runner uses `/shard-work` and a fresh `mechanics-16b` output directory and session.
Exact corrected runner is tracked in the V6e notes directory. All sixteen final
exit codes are zero. This exercises admission, backup, restore, capture templates,
partial restore and historical retained-recovery mechanics, not physical hardware.

[verified: launched, pending] The V6e genuine helper/owned-wrapper heavy rehearsal
is still running. V6f was independently assembled and launched with the current
tracked retained-recovery adapter (068fd62c baseline) and its current mechanics
tests, then a transitive source-pin successor closure. It still uses historical
install-capture fixtures; a pass will not establish the newer V5 capture lifecycle.
V6f archive SHA-256:
`6eb76d47069466b5d2cd3c7ac3b350e3277e1e2f387f9e1ce974607a737d5812`.
Runner SHA-256:
`b3d062fdfb43573c1aadcadd869cbe36877d1ddbae88fa13512f5b06a3af5f07`.
Remote root: `/home/claude/mvave-fm1/owned-restore-v6f-resumed-20261012`.
Both rehearsals use read-only private inputs, modeled transport/time/capture,
no physical device mounts and no runtime source-pin/factory/registry override.
Source assembly and hash delta are tracked under the V6f notes directory.

[verified: fresh UI/bench observation] Packetry was inspected with computer use
and a fresh passive Cynthion capture started successfully. Target Power remained
on; no power/reset/soft-key/flash operation was performed. The Pi still enumerates
normal FM-1 `4c4a:c755`, bus1/device8, with `/dev/snd/midiC2D0`. The owner was told
no physical cycle is presently needed before leaving. Passive bus traffic alone
does not prove CPU reset, recovery entry or diagnostic firmware boot.

Current verified pushed checkpoint before this update:
`7561db37caa5de7edb464f6e1c1eb038c9e66f04` on
`feature/2026-10-11@installable-firmware`. Source acceptance and hardware gates
remain pending. Next: retain terminal heavy results, test the current-adapter
mechanics, review the original-stage binding, then prepare a fresh closure for
hardware acceptance. Do not activate the historical V5 gates or reuse consumed
entry/backup markers.


### V6e retained import-boundary failure, V6g model isolation

[verified: modeled execution] V6e passed the corrected original capture-stage
admission and genuine file-only preparation, then failed after 537.32 seconds
before the owned restore marker. Its launcher imported the entire outer-tree
`test_sdk_rehearsal` module, caching `fm1_uboot_read.py` outside the staged closure.
The real staged recovery factory correctly rejected that ambient implementation.
Private fixture inputs were unchanged; failed container is retained. Archive:
`3ac2c345e7c2a60d1aa2dc092cfc050656e0c70602ca1ed48e955e6bf4ee8a36`.
All 229 temporary-inventory regular-file hashes replayed locally.

[inferred: test harness repair] A V6g successor loads only the source's exact
`wire` and `SGModel` definitions into a model namespace, and imports the actual
staged rehearsal module with a direct-path check. It does not replace factories,
registries or source hashes at runtime, or relax production import validation.
Its sealed transitive literal-pin closure and assembly script are tracked in the
V6g notes directory. A fresh Hera rehearsal is launched and pending:
`/home/claude/mvave-fm1/owned-restore-v6g-resumed-20261012`.
Archive SHA-256:
`8935647033aa4fd03ef90f0f6c4a0744f0a694c23c785e048e66e6799f0a5ac3`.
Runner SHA-256:
`2803354b244933518db6c0edd810dcfd4a3126e8d37d5cd6292ef6d21d880ee8`.
V6f is still pending and has the original launcher, so the same failure may recur.
Current-adapter 16-shard mechanics are also pending on Hera.

[verified: passive capture only] Fresh Packetry capture stopped and saved to
`build/packetry-live-capture-20261012-resume/cynthion-passive-resume.pcapng`.
23,162,388 bytes; SHA-256:
`84c290427c82712915cd9a7cb521550d777e520f27c6e5e107f59d2a71da8d25`.
PCAPNG uses big-endian blocks; all block lengths, alignment and trailing lengths
validate: 83,236 packet blocks and 630,658 analyzer event blocks. Packetry showed
713,894 total transactions and zero decoded devices/endpoints, as expected for a
capture without a fresh enumeration. No target power toggle or FM-1 command.
It proves fresh capture works, not recovery or firmware boot. Capture remains
private and ignored; it is not uploaded to the public firmware repository.

Next dependency: inspect V6f mechanics and V6g heavy terminal results, preserve
failure evidence, then complete original-stage adversarial review and a new bench
source closure. Physical diagnostic boot/full stock restore remain unverified;
no installable-image acceptance or hardware activation is claimed.
