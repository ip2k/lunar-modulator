# Bounded browser nested FWSC inspection

[verified: source and synthetic tests] `native-fwsc-inspection.js` now checks the
FM-1_092 D7000 nested layout independently in JavaScript, following
`model_092_app_replacement._flash_parse`. It validates top JLFS header/records,
SPL bank/header/data CRCs, config/key CRC and key derivation, SFC app-region
origin, six directory children, fixed reserved descriptors and tightly bounded
app/tool/cfg extents and CRCs. The flash extent is exactly 0xD7000, inside the
existing 2 MiB outer bound. Decoded allocations are fixed-size and never returned.

Outer identity policy is unchanged. Nested inspection selects the known layout
for FM-1_092 and FM-1_5xx (the trusted Python continuous tuple identity range).
Other identities report unsupported-profile. A supported identity with malformed
structure fails closed. Identity does not establish provenance. A successful
`nestedFlashVerified` means only the named structure/CRC profile passed;
`nestedInspection` states protected-stock correspondence, opaque suffix semantics
and device behavior are unverified. `admissible` and `releaseAccepted` remain
false; `verifyNativePackage` still always rejects. No download, install, transport,
backend, deployment or device path changed.

Unlike the private Python model, this public inspector cannot compare protected
bytes against a pinned private reference. It must never claim stock preservation,
hardware acceptance, cryptographic authenticity, or package release acceptance.
Reserved descriptor data CRCs are not claimed verified. The opaque suffix is
bounded (at least the model's 968-byte tail fits) but not interpreted.

[verified: local small tests] Node inspection/admission tests: 10 passed, one
optional private-artifact test skipped. Synthetic Python generator first validates
its valid fixture with independent `_flash_parse` and temporary synthetic reference
files, then supplies bytes to the browser tests. Cases cover 092/500/503 identities,
unknown identity, repaired enclosing CRCs with overlap/length/reservation errors,
child and top header/data corruption, config/SPL/cfg CRC corruption, wrong SFC
origin and short/oversized flash. Existing envelope Python oracle checks pass.
No vendor binaries are saved or committed. No hardware or deployment validation.

Semantic MCP readiness was checked: Rarefaction and Serena both select
`/Users/likwid/Developer/mvave-fm1-firmware`, not this isolated worktree; Serena
lists only cpp active. They were not retargeted because shared active selection
must not change. Direct exact-worktree source inspection was used instead; no
semantic coverage of this JavaScript/Python change is claimed.

Next dependency: coordinator review and required CI integration; trusted external
package tuple/protected-byte binding and release/hardware acceptance remain separate
unimplemented gates.
