# Workbench recovery assets and provenance

This is an offline byte and source record. It is not a current device observation, recovery procedure, or authorization for device traffic.

| Asset or evidence | Digest and identity | Establishes | Does not establish |
|---|---|---|---|
| Bundled stock recovery package | `sdk/firmware/FM-1_015.fwsc`, 699,956 bytes, SHA-256 `db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a` | Exact stock V15 package bytes; retained evidence reports equality with two V15 research copies | Not Open V13, an owner dump, an entry transport, or recovery of a non-enumerating device |
| Decoded stock SPL | 14,384 bytes, SHA-256 `730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef` | Matches Lunar's existing stock-SPL package guard | Does not validate the separate Open-build SPL |
| Decoded stock OTA | 19,969 bytes, SHA-256 `ef1f2db89b011fa53e71df363f0122de0ea896618c53fb53e8da676322004541` | Identifies the OTA payload in the stock FWSC | Does not prove a live OTA endpoint or restoration |
| Open-build packager SPL | `sdk/tools/pack/uboot.boot`, 14,488 bytes, SHA-256 `b88747cb72afc554d6ca078594a89f4fdcea5a74d26345b633f8e2524e7e3415` | Identifies a separate build resource | Does not match Lunar's stock-SPL guard and is not interchangeable |
| Historical owner full-flash backup | 1,048,576 bytes, SHA-256 `96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`; bytes are absent here | Retained bench record reports matching copies and previous complete stock-baseline restore/read-back | Does not describe later interrupted stage7 or prove current device state |
| Latest retained passive observation | 2026-10-17 16:46 UTC: blank screen/red charge light and supply current; no app, OTA or mask-ROM USB identity observed | Historical passive observation summarized by the evaluation | Not a fresh probe; current topology/cabling were not checked, and supply current does not prove CPU execution |

The retained parser evidence checked the container/table, unencrypted-entry and boot-bank CRCs, decoded stock SPL, and hashed the OTA payload. Encrypted auxiliary plaintext CRCs were not independently validated; the whole-package digest matched. The verifier checks archive/source hashes only and does not parse or execute firmware payloads.

The Workbench updater requires a responding compatible USB-MIDI app or OTA endpoint and identity/protocol responses, including in force mode. Raw `UBOOT1.00` without its MIDI updater, or no USB enumeration, requires separately reviewed recovery tooling and separately admitted hardware work. The public stock FWSC supplies asset provenance; it provides no demonstrated entry path.

No binary is committed. No USB, MIDI, flash, reboot, restore or vendor-tool operation was performed.
