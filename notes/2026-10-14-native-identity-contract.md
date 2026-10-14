# Native application/package identity contract — 2026-10-14

[verified] The pinned Dinghy platform defaults `FELUCCA_ID` to `FM-1_990`.
`ota_reply_identity()` uses `OTA_IDENTITY`; the platform selects `FM-1_000`
in recovery and `FELUCCA_ID` otherwise. Earlier application probes do not
override this default. The strict offline 092 package model deliberately
preserves `FM-1_092`; it is not a ready-to-install Lunar package.

[verified] `reference/FM-1-RE/tools/fm1_ota.py` checks the running firmware's
model/version against the incoming package after reboot (lines 460–482 in
the inspected local checkout). A model package and application with different
identities cannot satisfy that client's success condition. [reported] Same
version rejection is documented from Baud Girl's tests in docs/03 §5; this
does not establish the exact stock verifier algorithm for Lunar.

[verified] `build_application_probe.py --firmware-identity FM-1_5xx` now
generates an application-only macro override and records it in its receipt.
The default remains byte-identical source generation for existing probes;
the checked-in vendor file and its inventory stay unchanged. Explicit
identities are restricted to ASCII FM-1_500–599, the planned Lunar range
in DEVELOPERS.md I15. Recovery still reports FM-1_000. Invalid identities
are rejected before a build directory or toolchain process is created.

[verified] Mac Python 3.13 focused identity, SAVE-option and runtime-mode
tests exited zero. They cover foreign/stock identities, malformed and injected
macro text, changed vendor guards, recovery preservation and false acceptance
claims. This is host source-generation evidence. No new pi32v2 application
has been linked with the override, and no package identity was changed or
emitted. Existing hardware candidate and its SHA remain unchanged.

Next: build a separately named target with one explicit Lunar identity,
independently verify its handshake data and valid ID block, then construct
and independently decode a matching private package. Retain stock boot,
loader, configuration and opaque data protections. Post-reboot identity,
same-version policy, OTA rollback and physical acceptance remain required;
the option and receipt confer none of those admissions.
