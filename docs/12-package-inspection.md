# 12 — Reproducible offline package and application inspection

[`tools/fm1_package.py`](../tools/fm1_package.py) provides the package inspection
used by the [local workbench](11-workbench.md). It uses Python's standard
library, works without MIDI dependencies, and reads the supplied file in memory.
It has no firmware builder, hardware transport, or download operation.

## Run it

Supply your own vendor package under ignored `scratch/` or `reference/`.
The source filename does not determine its identity.

```powershell
python tools/fm1_package.py package scratch/FM-1.fwsc
python tools/fm1_package.py app scratch/app.bin
```

Both commands print JSON and create no files. Extraction and saved reports
require explicit output paths, inside this repository's ignored trees:

```powershell
python tools/fm1_package.py package scratch/FM-1.fwsc --app-out scratch/inspection/app.bin --report scratch/inspection/report.json
```

Existing output files are never overwritten. Source, report and application
paths cannot overwrite one another. Keep the vendor file and extracted payloads
local; a JSON report contains hashes and analysis, not their bytes or local paths.

## API and limits

`inspect_package(raw: bytes) -> dict` returns only after supported integrity
checks pass. `inspect_application(raw: bytes) -> dict` searches a supplied
application for the existing msfa constants. `PackageError`, a `ValueError`,
reports malformed inputs, failed checks and unsupported package layouts.

The CLI/API input limit is 16 MiB; the workbench applies its smaller 8 MiB upload
limit. Parsing permits at most 12 UFW entries in the observed 0x400-byte header
region, 64 entries per traversed JLFS directory, and 64 msfa anchors. Declared
sizes are checked before slicing; directory payloads and UFW allocations cannot
overlap. Every report has `schema_version: 1` and `device_io_performed: false`.

| Report field | Meaning |
| --- | --- |
| `kind`, `size`, `sha256` | Input type, byte length and stored-byte fingerprint |
| `identity.value` | `FM-1_0xx` decoded from the 20 interleaved marker positions; not a filename guess |
| `identity.matches_application` | Whether that identity appears in the extracted application; `null` when no application identity is found |
| `integrity` | Checked UFW header/table CRCs, entry count, exact CRC parameters; `authenticated` is always false |
| `entries[]` | Names, types, indexes, logical offsets, sizes, allocations, stored-byte SHA256, CRC and its scope |
| `entries[].decoded_sha256` | Additional fingerprint for an SFC-decoded entry whose CRC covers decoded bytes |
| `application` | Extracted app size/hash, embedded identity strings, msfa matches and extraction evidence |
| `application.extraction` | CRC results, directory counts, derived key and offsets inside `flash.bin` |
| `unchecked_layers[]` | Explicit boundaries of the analysis, shown in the workbench |

A standalone application report contains `size`, `sha256`,
`embedded_identities` and `msfa_tables`; it has no package CRC provenance.

## What is checked

**[verified: synthetic tests and the three local packages listed below]** The
parser checks the complete logical image length, descrambled UFW header CRC,
still-scrambled entry table CRC, each payload's declared CRC, the tail/key record,
the new-fw header, traversed top-directory headers, configuration/key data,
application-area header/body, and all regular files in its application directory.

The SFC key and application-area base come from checked metadata. The parser
does not assume the familiar stock values `0x980F` and `0x4000`, search the
image for an `app.bin` filename, or infer executable addresses. The synthetic
fixture deliberately uses an application area at `0x1000`.

The top `app_dir_head` is a pointer record, with `size=0xFFFFFFFF` and
`data_crc=0xFFFF` in the observed packages **[verified]**. Those sentinel fields
are not a payload checksum/length. Its header is checked, its pointer is bounded,
and the pointed-to `app_area_head` supplies independently checked contents.

### UFW CRC scope: four entries require decoding first

**[verified 2026-09-14 against all three packages below]** UFW entry CRCs for
`USR` (type 50), `isd_config.ini` (52), `blimit.bin` (161) and `script.ver` (251)
cover SFC-decoded bytes. Checking their stored bytes directly gives mismatches.
Types 0, 2, 100 and 255 cover stored bytes. Other entry types are rejected until
their integrity semantics are established.

The 32-byte chip-key record at the start of `tail.bin` has a CRC at bytes 32–33;
the complete 64-byte tail has its own UFW CRC and `JLUFW` marker at byte 48.
Decode that key record using kagaimiq's documented algorithm. For each 32-byte
payload block, the cipher's starting key is:

```text
(chip_key XOR ((logical_entry_offset + block_offset) >> 2)) AND 0xFFFF
```

The XOR stream uses the key's low byte, then advances its 16-bit shift register
with polynomial `0x1021`; restart at each block. Application-area SFC decoding
uses offsets relative to that area's base. These are two different offset
origins. The key from `tail.bin` must agree with the separately checked
`isd_config.ini` key record inside `flash.bin`.

For the `FM-1_015` package below, the decoded CRCs are `USR=e3bc`,
`isd_config.ini=acef`, `script.ver=aab7`, and `blimit.bin=33fe` **[verified]**.
The resulting `script.ver` SHA256 is
`efb8d7f47d9187ae77414868887c33078f4b856afc5f426e8b8dde048d2f1b0c`.

**CRC naming:** the exact checked parameters are polynomial `0x1021`, initial
value `0x0000`, no reflection and final XOR `0x0000`. The `123456789` check value
is `0x31C3` (CRC-16/XMODEM), not the `0xFFFF` initialization of CCITT-FALSE.
This follows `jl-misctools` and is checked against the packages **[verified]**.

### Boundaries

The report's `application.status = "verified"` describes extraction integrity.
It does not certify vendor authenticity, device compatibility, bootability or
recovery. CRCs can be regenerated. Interleaved identity marker bytes and unused
allocation padding are outside the stored CRC coverage; their syntax and bounds
are checked, but changing a valid identity can leave those CRCs unchanged.

The outer `flash.bin` CRC covers nested boot and resource bytes. The inspector
checks top-file bounds/overlaps but does **not** decode/verify the SPL's internal
bank checksums, the OTA loader's decompressed-image checksums, or later resource
directory checksums. Reserved regions are metadata declarations, not file
payloads; they can describe flash outside the supplied image. These limitations
appear in `unchecked_layers`, and runtime address validity is not claimed.

## Fresh local verification, 2026-09-14

The same API inspected all three packages without writing files or touching
hardware. The older two inputs were local copies of AL-255's `firmware-images`
examples; the last was the contributor's locally retained vendor package. These
are fingerprints of the actual inputs checked here, not a claim that a remote
download still has those bytes. The vendor V15 source is linked in
[docs/02](02-stock-firmware.md#1-versions-and-packages).

| Marker identity | Package bytes | Application bytes | msfa table file offset | Entry CRCs |
| --- | ---: | ---: | --- | --- |
| `FM-1_009` | 704084 | 583068 | `0x8C46C` | 8/8 |
| `FM-1_014` | 704052 | 584956 | `0x8CBCC` | 8/8 |
| `FM-1_015` | 699956 | 581564 | `0x8BE8C` | 8/8 |

Package SHA256 **[verified]**:

```text
FM-1_009  5b3ac73bdd5ec6c774ecf9be65f51b2575ad67b775f8fb175c7130ea8af687ae
FM-1_014  a1adca99b1f9823ff2873292be74877a7a14ca0846fca3d25a23aba2750162d3
FM-1_015  db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a
```

Extracted application SHA256 **[verified]**:

```text
FM-1_009  73f37ac3db15f5e70ae718dac43ab30055a0e27f659ae1b3eeb4c51a39b1616a
FM-1_014  54a32371e8fc19e7492210e958023762f7335e354a4cab41cb26c35d6f0f0443
FM-1_015  306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203
```

All three have exactly the full 32-row table with the known algorithm 4/6
feedback-byte differences **[verified]**. This is reproducible evidence of the
msfa/Dexed family described in [docs/02](02-stock-firmware.md), not a discovery
of new executable code or a proof of sound equivalence. The inspector reuses
[`check_msfa_table.py`](../tools/check_msfa_table.py)'s existing reference;
it labels original, exact known variant, other variant and truncated matches
separately. A short matching anchor alone is never labeled a complete table.

## Tests and provenance

```powershell
python -m pytest tests/test_fm1_package.py
```

The tests generate small synthetic packages with independent bitwise CRC and
cipher helpers. They cover nested corruption with repaired outer CRCs, partial
headers, bounds, overlaps, encrypted-entry corruption, duplicate names,
identity mismatch, exact msfa classification, analysis limits and safe output
paths. No vendor binary is committed or required by tests.

This implementation carries forward Echomatter's offline analysis from the
local `EM_MVAVE_FM1_USB_RECOVERY_TOOL` tools `fwsc_inspect.py`,
`extract_fm1_application.py`, and the decoding helpers formerly colocated in
`build_fm1_v15_bridge_stage.py`. Those tools were analysis evidence; their
package-building operations and hardware workflows are not imported.

The UFW/JLFS, cipher and chip-key format work comes from **Andrey Grigoryev
(kagaimiq)**, especially
[`fwunpack_newfw.py`](https://github.com/kagaimiq/jl-misctools/blob/0a5b12db0ef38f3042acffbe2452730a37fd2405/firmware/fwunpack_newfw.py),
`jltech/cipher.py`, `jltech/chipkeybin.py` and `jltech/crc.py` at that revision.
The adapted algorithms retain its MIT notice in
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). AL-255 supplied the older
package analysis and fixtures; Google msfa and the Dexed lineage supply the
reference table. See [prior art](04-prior-art.md) for those projects.
