# OTA package correspondence checkpoint — 2026-10-14

This checkpoint strengthens offline verification for the existing private
`FM-1_990` native-controls OTA prototype. It does not create an installable
release or authorize any device operation.

`tools/native/ota_candidate.py::verify` now records and checks the outer
FWSC header and entry-list CRC results, exact nested component-name set,
no-op nested JLFS/SFC reconstruction, guarded stock OTA, and preserved stock
boot/config/resource component hashes. It binds the unique `FM-1_990` app
identity marker to the FWSC identity and verifies the observed stock trailer
record and header metadata profile. The receipt records the stock XIP/app
geometry and explicitly leaves device version acceptance false. The existing
`model_app_replacement.verify_replacement` remains the authority for decoded
app/SFC correspondence and rejects changes outside the bounded app replacement
contract.

`tests/native_ota_candidate.py` adds repaired-outer-CRC tamper cases for an
altered OTA payload and an altered trailer record. All 18 offline shards passed
using the local guarded stock fixture at
`build/native-ota-candidate-16-v2-20261012/source/inputs`.

## Expanded demo packaging remains separate

The all-demo controller at `tools/native/build_demo_image.py::build_selection`
binds selected IDs, startup index, prepared profile digest, SAVE service and
linked bytes into `image.json`, but emits `app.bin` plus diagnostic evidence;
it does not emit FWSC/OTA. The existing FWSC composer is deliberately pinned
by `APP_SHA` and `IDENTITY` in `tools/native/ota_candidate.py` to the small
`FM-1_990` controls probe. It cannot consume an all-13/song selection as-is.

The size makes direct substitution impossible for the observed stock V15
container: the all-13 Event Horizon Showcase application is 862,320 bytes in
the retained checked build receipt; the stock nested `app.bin` extent is
581,564 bytes (`inspect_nested` on the guarded V15 fixture). The normal
`model_app_replacement._build` path refuses any app larger than that extent.
The separate `tools/native/expanded_candidate.py::construct` path targets the
FM-1_092 expanded `d9000` raw-flash layout, requires two identical baselines,
manifest, identity and reference evidence plus app/ELF reconstruction and link
audit, then calls `expanded_flash_profile.construct_geometry`. That constructor
preserves raw bytes below `APP_BASE` and above `AREA_END`, including boot and
reserved banks, and verifies expanded record geometry. It explicitly reports
`ota_package_verified=false`; it creates a private raw candidate, not FWSC/OTA.

Thus there is no existing compatible installable package path for this
expanded app. The smallest next offline packaging increment is to define a
format and exact source-evidence contract around the expanded raw candidate,
then add correspondence/tamper checks for app/ELF/selection receipt identity,
geometry, and immutable ranges. That still cannot be called release-ready or
installed: current physical backup provenance, device version acceptance,
settings migration/rollback, and approved transport/recovery remain gates.

The offline correspondence checks here therefore apply only to that pinned
prototype. A future package composer needs a separately reviewed profile that
accepts the controller's exact app/artifact receipt and independently binds
app SHA, ELF/link receipt, prepared selection, startup ID, package identity,
guarded stock components, and geometry before emitting a candidate.

No hardware acceptance, device-version acceptance, recovery proof, settings
migration/rollback, installer transport or release admission is established.
