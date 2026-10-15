# Opaque VM/USR archive prototype

This host-only prototype stores the exact recorded FM-1_092 VM and USR extents
as one bounded raw-DEFLATE archive. It does not parse or migrate settings, write
flash, define sector ownership, or establish a rollback/recovery procedure.

The encoder requires two complete 1 MiB images to match byte-for-byte and an
independently supplied full-image SHA-256. It then checks the recorded-092
reservation profile and extracts VM `[0xD9000,0xE9000)` and USR
`[0xEA000,0xFC000)`. BTIF `[0xE9000,0xEA000)` is outside the archive and must
remain separately preserved. The canonical schema-1 header binds both fixed
extents, compressed and uncompressed sizes and SHA-256 values, codec policy,
and full-image baseline digest. The total serialized archive, including its
header and alignment, is limited to 20,480 bytes; overflow fails before any
archive is returned.

The decoder requires an external `expected_archive_sha256` before it parses
the archive. Embedded digests and the baseline SHA are integrity metadata, not
an authentication root: a producer could alter the payload and recompute every
embedded hash while leaving the baseline label untouched. The caller must
obtain the archive digest from a separate trusted boundary. Decode also bounds
output to the exact combined extent length and rejects truncation, trailing
data, noncanonical or duplicate-key metadata, invalid lengths and hash
mismatches.

The retained private A/B images were identical and each had SHA-256
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`. The
concatenated 139,264-byte VM/USR payload had SHA-256
`ece60f1ad121619b773993dbf5f6667303c7edbe8e02e1e97cb643c4a07a11db`; its
extents had hashes `bfbca6eba6e259269880685cb2dc5c19a403d5e343699af9d18e9e54551c2299`
(VM) and `f63fe429d2ba487b138d17b60d4a26bcf15bf35c051cb57cef6cf9b81988b3c9`
(USR). With raw DEFLATE, 4 KiB window (`wbits=-12`) and level 6, the complete
archive was 18,673 bytes, leaving 1,807 bytes below the nominal 20 KiB bound.
The archive SHA-256 was
`2931f3e50be326ca66953ff68d40dc89aebea064010d0b966d0afc52e7b9a993`; decoding
with that external pin reproduced both extents byte-for-byte.

This fit applies only to these captured bytes and does not prove future stock
data will fit. A measured adjacent 20 KiB area contains 7,690 non-`0xFF` bytes,
so the size result does not authorize using it or overwriting any bytes. No
target-side inflater build, flash write, recovery trial, stock-settings
compatibility, or hardware admission was performed. The existing firmware
inflater's compatibility with this archive stream still needs an explicit
target-hosted test before considering any consumer.

Validation: `tests/test_opaque_stock_archive.py` passed 20 tests, including
retained-image exact roundtrip, mismatched A/B refusal, archive-pin refusal,
recomputed-inner-hash forgery rejection, malformed/trailing/truncated input,
bounded decompression and incompressible-capacity refusal. `py_compile` and
`git diff --check` passed.
