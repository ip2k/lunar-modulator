# Ordered demo preparation controller

[verified] `tools/native/prepare_demo_selection.py` accepts version 1 module groups,
ordered trusted project IDs, and a startup index. It exports the repository's own
catalogue, snapshots the request and staged source identities, invokes the real
state codec, and verifies the prepared manifest and each ordered packed asset.
Client paths/catalogue hashes are not accepted. Existing output directories are
refused without removing their contents; failed preparation cleans its new output.
`selection.json` is emitted only after verification. Downstream linking must bind
both its prepared-manifest digest and startup index.

[verified] Three controller cases passed on Hera with the actual freshly built
`fm1-state`, alongside 40 existing preparation/integrity/staging cases (43 total).
The tested controller SHA-256 is
dd755fd80d31294092387ec996b9b7e20c089f17336814d83cd0ca9bea519035;
test source SHA-256 is
9007e850c6e8047828502ce56a5d30031f855b11810c80ce33d4408fd57f569d.
Coordinator independently matched these hashes against the Hera tested copies.
The production Afterglow manifest and packed asset hashes were also independently
matched. Exact codec/container provenance and four song sizes are recorded in
`2026-10-14-demo-packed-validation.md` and its JSON receipt.

This is an offline controller, not a deployed build service or installer UI.
No native link, target RAM, sequence semantics, musical approval, physical boot,
or flashing acceptance is implied. Receipt flags remain false for installation,
native link/RAM and hardware. Original demos remain legacy examples, not approved
showcases. The shipping default still needs an accepted full-length song. FIRST
ORBIT alone does not satisfy that requirement. No device commands were issued.
