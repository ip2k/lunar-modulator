# Offline native OTA adapter increment — 2026-10-14

## Scope and result

Added a GPL-3.0-only, explicitly unwired browser OTA protocol increment. The
maintained reference is Felucca `web/fm1ota.js` pinned at
`1727537624390cc3f9c7dff2456b43b3a8edb005`; source and license notices are
retained in `sim/web/www/third_party/felucca-ota/`. The new
`sim/web/www/native-ota-adapter.js` accepts only an injected verifier result,
checks its logical-image digest and separately pins both logical-image and
package SHA-256, requires explicit matching MIDI port objects, and binds the
handshake/session/resume token to the exact observed identity and selected
artifact. Resume requires explicit reselected ports and exact loader identity
text, but MIDI identity is not a unique physical-device identifier.

Before hardening, the upstream parser accepted weaker identity/request framing,
the incoming queue had no cap, transfer lifetime could be extended by traffic,
zero-byte/out-of-image ranges were not rejected consistently, and a failed
finish ACK could still look complete. The adaptation checks frame boundaries,
decoded and declared lengths, checksum and normalized identity, bounds the
queue and packet size, enforces idle plus absolute deadlines, rejects invalid
data ranges, and reports finish only after the ACK send succeeds. Fake-port
tests demonstrate these cases and that no port is opened or probed until the
caller supplies verifier-produced admission and explicitly selected ports.

## Validation and limits

`node --test sim/web/test/native-ota-adapter.test.mjs` passes all 10 tests;
`node --check` passes for both JavaScript modules; `git diff --check` passes.
The exact package hash protects resume continuity while the logical-image hash
is the byte stream served to the target.

This is transport support, not an installer. The repository does not yet
provide the audited package verifier required by `packageAdmission.verify`,
compose verify/write/reboot/post-identity stages, request Web MIDI permission,
connect to a real device, validate recovery/physical admission, or wire this
module into the installer page/service. No hardware or live MIDI I/O occurred.
The verifier injection is a trust boundary: a future integration must bind it
to the actual package parser, protected-component policy, and exact target
profile before offering a connect action. Matching port names and SysEx identity
text alone do not prove physical-device continuity; the future UI must make
reselection explicit and must not claim unique-unit continuity. The fake tests do not prove the
browser/OS port behavior or target protocol acceptance.

Rarefaction reported a ready TypeScript/JavaScript server rooted at the primary
checkout rather than this worktree; Serena symbol overview succeeded on the
authoritative worktree for both new modules. Treat Rarefaction coverage as
unavailable for this edit, not as validation of these files.
