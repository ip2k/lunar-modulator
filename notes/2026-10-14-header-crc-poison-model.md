# Conditional app-header CRC poison model — 2026-10-14

This offline probe evaluates a narrow recovery-ordering idea against the
recorded FM-1_092 app header: clear one currently-set raw bit in the stored
app-area-header CRC, reread and prove the decoded header invalid, and only then
allow app-payload mutation. It does not produce a flash command, admit an
image, allocate a staging range, or establish physical program atomicity.
No device, USB, MIDI, flash or power operation occurred.

## Source and captured-byte evidence

[verified] `tools/jieli/raw_flash_profile.py` decodes the captured app area at
physical `APP_BASE=0x4000` with `sfc_decode(..., 0)`. The SFC helper in
`tools/jieli/inspect_fwsc.py` is bytewise XOR (`header_decode`), restarted per
32-byte block using key `0x980f ^ ((logical_offset + index) >> 2)`. XOR is
self-inverse: changing one stored raw bit at a header byte changes only the
corresponding decoded bit. The 16-bit stored record CRC is at header bytes 0–1;
`inspect_stock_flash.record()` validates it against bytes 2–31.

[verified] Offline inspection used the retained Hera `stockA.bin` and matching
`stockB.bin` from `native-external-arenas-16-20261012/out/expanded-private-geometry-v1`.
The captured image SHA-256 is
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`; decoded
header name and CRC validate as `app_area_head`. Eight bits in the two raw CRC
bytes are set. Clearing raw bit 1 at absolute offset `0x4000` leaves every
CRC-covered decoded byte unchanged and makes the record CRC fail. This is
static input/model evidence only; no candidate image or binary bytes were
written to the repository.

[verified] Stock SPL ordinary-selection flow requires a CRC-valid app-area
header and enters the normal XIP route when selection succeeds. At `0x2e08`,
a selected app bypasses the trailing recovery-record scan; the scan runs only
when ordinary app selection fails. The exact SPL contract and scan bounds are
in `notes/2026-10-11-stock-spl-final-contract.md` and
`notes/2026-10-14-stock-spl-update-record-byte-review.md`. Thus directory-last
alone does not protect power cuts while an old valid header points at a
partially rewritten payload. A deliberately invalid header, confirmed by
readback before payload changes, is a logically necessary precondition for
relying on the conditional record scan.

## Model and tests

`tools/native/app_header_crc_poison_model.py` is a pure in-memory model. It
accepts exactly a raw 32-byte header, verifies decoded identity/CRC, chooses a
set bit only in the raw stored CRC, and computes the expected one-bit variant.
It checks that the decoded CRC-covered body remains identical and that the
new CRC comparison fails. Its route predicate distinguishes the verified
ordinary-XIP selection from the conditional rescue scan, and its payload gate
requires a verified invalid-header readback plus valid rescue-record and
loader predicates. Plan metadata permanently says `hardware_admitted=false`
and `installable=false`.

`tests/test_app_header_crc_poison_model.py` exercises all set raw CRC bits in
a synthetic valid header, one-bit-only/coverage invariants, malformed inputs,
ordinary-header bypass, unavailable rescue outcomes, and the mutation gate.
Run in the focused Hera regression image with standard Python:
`python3 -m unittest -v tests.test_app_header_crc_poison_model` — 4 tests pass.
The available focused Docker images lacked pytest; the file uses `unittest`
and remains pytest-discoverable in the project CI environment.

## Limits and corrected geometry

The logical model assumes an ideal single raw `1 -> 0` transition with no
collateral changes: power loss during the operation leaves either the old or
new bit. This is not established for the device. The maintained Dinghy NOR
source uses page-program opcode `0x02`, waits/polls, and exposes readback, but
neither it nor the retained loader trace establishes torn-program behavior for
one bit on the in-package flash. Source notes `notes/2026-10-14-native-nor-hal-audit.md`
and `notes/2026-10-11-fixed-loader-nor-write-review.md` explicitly limit what
those traces prove. Physical programming granularity, timing, collateral
corruption, and torn-operation outcomes remain unknown. Readback can detect a
bad result after the fact; it cannot make a torn result atomic or recoverable.

The two-sector tail proposal also does not fit the present all-13 image as
measured. With `APP_ORIGIN=0x4120`, preserved cfg-tool/cfg extents of 384 and
2,940 bytes, and a tail reservation beginning at `0xD7000`, the app budget is
`0xD7000 - 0x4120 - 384 - 2940 = 860,644` bytes. The current linked app is
862,296 bytes, exceeding that budget by 1,652 bytes; its app/tool/cfg records
end at `0xD7674`, inside the proposed two sectors `0xD7000..0xD9000`. Do not
claim this reservation fits, move protected cfg, or reduce production features
without a separately reviewed decision.

Even a passing conditional bit-transition model would not establish sector
ownership, safe persistent-record placement, rescue-loader provenance/size,
SPL entry on a cold boot, normal-app safety after a failed attempt, or physical
recovery. The capture is not a fresh pre-write backup pair. The correct next
step is to obtain independent exact-part NOR torn-program/bit-transition
assurance and a reviewed staging placement that fits the corrected all-13
geometry; until then this remains a logical ordering constraint for design,
not an installer protocol or recovery claim.
