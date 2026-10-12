# One-reset USB capture proof

This is a separate MIT evidence parser, `tools/fm1_reset_wire.py`; it never
opens a device or grants a transport. Existing reset, stage-resume and returned
recovery policies are unchanged. [verified]

`verify_reset_wire(raw, old_usb, new_usb)` requires the same USB port/bus and a
changed address. It pairs every relevant old/new endpoint-1 bulk record. It
admits exactly one FC0C argument-1 CBW, complete successful OUT31, then either
IN16 disconnect `-108/0` without reply/CSW or exact 16-byte echo plus matching
successful zero-residue CSW. Other accepted BOT commands are exact TUR,
REQUEST SENSE and INQUIRY forms. Failed TUR requires immediate exact 02/3a/00
sense; optional unique new-ROM PREVENT(1) must fail and immediately report exact
05/24/00 sense. No second reset, upload, NOR, eFuse or other outgoing bulk
payload is admitted. [verified: source and modeled tests]

`validate(raw, commands, config, old_usb, fresh_rom, terminal_time)` additionally
checks original bounded campaign/log bytes and exact trace-reset preparation,
single intent, structured optional SG completion and terminal completed or
caught-ambiguity envelope. The original snapshot `observed_at` must follow the
terminal event; it is never refreshed here. The caller must validate and freeze
the complete installed-image lineage, source bytes, consumed marker, owned
capture lifecycle, original snapshot and current ROM/SG connection. The parser
does not establish who initiated standard commands, verify unrelated devices
or USB control traffic, or supply kernel exclusivity. [verified]

Proof of completed CBW OUT is proof of transmission at that captured endpoint.
The result deliberately leaves SG request completion, CPU reset, application
boot, display, recovery and RAM retention unattested. Even a valid echo/CSW is
not a CPU-reset observation. USBmon text caps displayed INQUIRY data at 32 bytes;
the logical 36-byte transfer is checked but its four-byte tail is unavailable.
Captures with timestamp wrap or nonsequential/interleaved relevant transfer
pairs fail closed. [verified parser limits; reset cause remains unverified]

The final source SHA is
`9c81a30a7f8741a606961315d0689341d3ce2e29775d395e05e81d5dbdedfd92`;
tests SHA is
`0ee732911a5ce17875ce0d99115a9114a45351e396cb6464c36cf477119f4038`.
Hera source archive
`fe50ae2d1633fb3aae7cafa35def69518d7892306130c83ee683597f4ff108fe`
contains these two exact files. All 55 unique modeled cases passed exactly once
in 16 chunks. A separate no-device parser run accepted the retained target
reset capture (130 paired records/26 BOT commands) and stock-return reset
capture (34 records/7 commands); both show one transmitted reset and detached
IN without CSW. This is replay of prior evidence, not a new physical action.
[verified: `build/reset-wire-hera/coverage-check.json`]

All 18 final collect/chunk/history containers used pinned image
`7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`,
2 CPUs/2 GiB, no network/devices/privilege, read-only source/jobs mounts, exit0
and no OOM. Named removals and fresh exact-label empty cleanup were checked.
The first 54 modeled cases passed, but historical replay rejected the legitimate
USBmon `>` OUT-completion marker; that earlier source/run is retained under
`build/reset-wire-hera/failed-v1`. The final source admits only native `<` for
IN submission and `>` for OUT completion, and adds a rejection test for the
wrong direction marker. All final work is offline. [verified]

The parent must review and freeze this source before newboot lineage binds it.
Actual completed install/owned reset capture/current snapshot remain separate
acceptance gates. Private receipts and earlier captures stay under ignored
`build/reset-wire-hera`; no firmware or recovery binaries enter the repository.
