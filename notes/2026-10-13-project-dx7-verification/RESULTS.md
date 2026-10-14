# Native DX7 bank startup restoration

The cold-start adapter stages up to32 VCED voices in4964 bytes of caller-owned
scratch and commits through fm1_app_dx7_put only after the complete binary
PROJECT read and CRC succeed. The shared codec validates field ranges and
printable names; the adapter refuses missing FM6, duplicate slots, live
rendering and overlapping arguments. Scratch is disposable and must remain
outside the app and allocation pool. This is not complete project activation
or persistence migration [verified source].

Host v1 failed16 valid fixtures: a PROJECT requires its Sound1 UNIT, which the
fixture omitted. Host v2 added that UNIT and real installed-instance checks;
it reached the cleanup assertion, then failed because the first sound slot
cannot be cleared. V3 uses the removable second sound slot. Neither fix weakens
production validation. All failed logs and terminal receipts are retained in
ignored build/dx7-verification. V3 passed all76 cases in30 Hera ASAN/UBSAN chunks:30 DX7 startup,30 scalar
startup and16 existing arena/audio cases. Every log and zero exit/noOOM state
was inspected; exercised source hashes match the immutable snapshot. Installed
FM6 instances before/after bank restoration hold identical VCED bytes; malformed
records, corruption/truncation and overlap refusals preserve the app [verified].
Owned containers were removed.

Link v1 passed all30 native links with the public DX7 restoration entry retained,
SDK-free audit, embedded-content bytes and project-loader report checked. All30
logs inspected and exit states zero, noOOM; owned containers removed [verified].
Profiles contain five engines, optional Plate and0/1/2/4 text/binary assets.
These are link tests, not all13 release, startup execution, hardware installation
or audible acceptance. Reproduction driver and receipts accompany this note.

Serena and Rarefaction resolve shared symbols in the primary checkout, not this
worktree; their indexes are incomplete without the actual compile database.
The selection was left untouched for other active sessions. Actual worktree
source, host tests and Hera target links are the acceptance authority.
