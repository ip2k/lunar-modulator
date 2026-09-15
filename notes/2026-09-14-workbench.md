# Workbench bench check — Windows, 2026-09-14

Contributor: Echomatter. This is a fresh read-only check of the workbench
contribution, based on upstream revision
`93c80a5769ba8a6e72442d1470ae056cf6a413a5`.

## Device observation

[verified, 2026-09-14 22:22 UTC] The normal USB device exposed an FM-1 MIDI
input and output through Windows/RtMidi. Windows reported `OK` for the
`usbccgp` composite parent and both `usbaudio` children (FM-1 Midi and FM-1
Audio) at `4C4A:C755`. A separate 15-second passive USB-enumeration check
recorded no change before the query.

`Workbench.identify` opened the explicitly selected normal FM-1 input and
output and sent this one message:

```text
F0 00 32 45 00 00 00 40 7F F7
```

The captured reply was:

```text
F0 00 32 45 58 01 00 00 23 4D 5A 44 79 05 26 4C 1A
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 20 06 F7
```

The strict decoder returned `FM-1_015`, body length 27 and `checksum_ok: true`.
These bytes match the independent stock-unit fixture already recorded in
`tests/test_tools.py` and the 2026-09-06 bench note. The workbench closed the
ports after the reply. No upgrade entry, firmware transfer, executable upload,
driver change, power change, or reboot was performed.

## Evidence boundary

This verifies identity-query behavior through Windows/RtMidi. It does not
demonstrate flash readback, dump/restore, recovery entry, audio playback, or
firmware installation. USB status is a host observation. Raw host-enumeration
records remain local; the identity packet above contains no serial number or
machine-specific identifier.

## Offline package and browser checks

[verified] The current Python suite passes **84 tests** on Windows/Python 3.12.
The JavaScript passes `node --check web/app.js`. The existing Python CI matrix
now also includes Windows; this local branch has not been published or run in
hosted CI. The unchanged RP2040 firmware was not rebuilt during this contribution.

[verified] In the browser, a deliberate identity request returned `FM-1_015`
with its valid checksum and visible TX/RX bytes. Choosing the unrelated Windows
synth output disabled the query. The actual stock V15 package passed inspection
through the file picker and showed all eight UFW entry CRCs, logical offsets,
CRC scopes, the independently reproduced application hash, and the full
algorithm 4/6 feedback variant at application offset `0x8BE8C`.
The inspection limits were visible alongside the results.

[verified] A deliberately invalid synthetic package reported an error and
cleared the previous inspection. The Errors filter isolated that event. A
synthetic standalone application found the original 32-row msfa table at its
known test offset. Desktop and narrow-width layouts were visually inspected;
the narrow document had no horizontal overflow. No browser console errors were
reported in the final device/package session.

[verified] Three stock package identities (`009`, `014`, `015`) were checked
offline, with separate independent review. Exact package/application fingerprints
and the newly verified decoded-entry CRC scopes are recorded in
[12 — Package inspection](../docs/12-package-inspection.md).

The in-app browser's Blob-download event timed out and no downloaded file was
found. The export flow therefore presents the JSON directly and offers copy and
download actions; requesting a download does not claim that a file was saved.

[verified] The report preview contained valid JSON with the live `FM-1_015`
identity, all eight package-entry results, the expected package SHA-256 and
five session events. **Copy report** completed its browser clipboard write and
displayed its success message. The automation clipboard reader returned no
text, so OS clipboard readback and browser file-download delivery remain
unverified. The full JSON is directly selectable in the report preview.
