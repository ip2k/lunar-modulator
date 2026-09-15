# 14 — Exact-source application patches and reversible FWSC rebuilding

[`tools/fm1_rebuild.py`](../tools/fm1_rebuild.py) turns reviewed application byte
changes into an integrity-checked local image and a reversible manifest. It
supports both a standalone decoded `app.bin` and an FM-1 `.fwsc` containing one.
It is an offline building block for the development workbench: it does not
compile source, install firmware, or communicate with the device.

## Contract

Every operation is bound to the complete source file's SHA256. Every patch
also provides the exact original bytes expected at its decoded application
file offset. Patches must replace a nonempty range with the same number of
bytes, cannot overlap, and cannot add, remove, move or change an embedded
`FM-1_0xx` identity. Package marker bytes are retained exactly. The builder
never infers a firmware version from a filename or silently raises a version.

**[verified: synthetic tests and the three local package checks below]** The
source is inspected before rebuilding and the result is independently parsed
again. Decoding and encoding an unmodified package must return identical bytes,
including unused padding, directory ordering, all marker bytes, resources and
uninterpreted fields. A byte comparison rejects any changes outside the exact
patch ranges and their dependent checksum fields.

This makes patches version-specific through their source fingerprints and
original-byte checks. It does not assume that an offset found in one version
has the same meaning in another version.

## APIs for the workbench

```python
rebuilt, manifest = rebuild_package(
    package_bytes,
    [{"offset": application_file_offset,
      "expected_hex": original_bytes.hex(),
      "replacement_hex": replacement_bytes.hex(),
      "label": "Describe the reviewed change"}],
    expected_source_sha256=source_sha256,
)
restored, rollback_manifest = rollback_package(rebuilt, manifest)
```

`rebuild_application` and `rollback_application` provide the corresponding
standalone application operations. Both rebuild APIs accept `patches=[]` to
exercise a no-op round trip. They return `(bytes, dict)` in memory and perform
no file writes. `fm1_package.inspect_and_extract(raw)` supplies the verified
package report and decoded application for a byte viewer or editor.

An offset is an integer file offset inside decoded `app.bin`, never a device
address or a position in the scrambled `.fwsc`. Hex byte strings may contain
spaces; manifests normalize them to lowercase contiguous hex. Error types
derive from `ValueError` (`RebuildError` or the inspector's `PackageError`).

### Manifest schema 1

| Field | Meaning |
| --- | --- |
| `kind` | `fm1-rebuild-manifest` |
| `input_kind` | `package` or `application` |
| `operation` | `rebuild` or `rollback` |
| `source_sha256`, `result_sha256` | Exact parent/result blob hashes, suitable for an immutable project revision chain |
| `source`, `output` | Metadata snapshots: sizes, SHA256 values, package identity, embedded application identities; no whole-image payloads |
| `patches` | Normalized, sorted original/replacement byte ranges and their labels |
| `updated_integrity` | Seven recalculated package CRC fields, with old/new values and logical package field offsets; empty for a standalone app |
| `verification.no_op` | Source and result have the same SHA256 |
| `verification.changed_application_bytes` | Number of bytes actually changed in the specified application ranges |
| `verification.non_application_payloads_preserved` | All other payload bytes retained exactly |
| `verification.unrelated_bytes_preserved` | All bytes outside the patches and dependent CRC fields retained exactly |
| `verification.bootability_verified` | Always false |
| `manifest_sha256` | SHA256 of the other fields serialized as canonical JSON; detects accidental manifest changes |
| `device_io_performed` | Always false |

The canonical JSON uses sorted keys, separators `,` and `:`, ASCII escaping and
no NaN/Infinity. The manifest digest is an integrity check, not an author
signature. Patch ranges contain original and replacement bytes, so retain
manifests privately alongside the supplied firmware and project file.

Rollback first checks the manifest digest, supplied result hash, image kind and
metadata. It reverses each expected/replacement pair through the same builder,
then requires the original source SHA256 and metadata to be restored. A changed
manifest cannot bypass those original-source checks merely by recomputing its
manifest digest. Rollback produces a new manifest whose source hash is the
modified image and result hash is the restored source; reversing that manifest
reapplies the change. No revision or source file needs to be overwritten.

## CLI: preview, save a pair, restore

Start by proving a no-op for your exact local package. This PowerShell example
creates a patch request, then prints a preview manifest without writing output
firmware:

```powershell
$sourcePackage = "scratch/FM-1.fwsc"
@{
    expected_source_sha256 = (Get-FileHash -LiteralPath $sourcePackage -Algorithm SHA256).Hash.ToLowerInvariant()
    patches = @()
} | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 scratch/rebuild-request.json

python tools/fm1_rebuild.py rebuild package scratch/FM-1.fwsc scratch/rebuild-request.json
```

UTF-8 JSON with or without a BOM is accepted. Repeated JSON object keys are
rejected. A request contains exactly `expected_source_sha256` and `patches`.
Populate `patches` with reviewed ranges from the application's byte viewer;
wrong original bytes or a different source file cause an error.

To save, specify both a firmware path and its manifest path:

```powershell
python tools/fm1_rebuild.py rebuild package scratch/FM-1.fwsc scratch/rebuild-request.json --output scratch/experiment/result.fwsc --manifest-out scratch/experiment/rebuild.json

python tools/fm1_rebuild.py rollback package scratch/experiment/result.fwsc scratch/experiment/rebuild.json --output scratch/experiment/restored.fwsc --manifest-out scratch/experiment/rollback.json
```

Use `app` in place of `package` for a standalone application. Neither command
saves files unless both output options are supplied. Output paths must resolve
inside this repository's ignored `scratch/` or `reference/` trees; existing
files are never overwritten. The manifest is saved first so a written firmware
result is accompanied by its reverse description. Keep original inputs.

The inspector's 16 MiB image limit applies. Rebuild requests permit at most
1,024 patches and 1 MiB of specified application bytes in total, with labels
up to 160 characters. CLI JSON files and rollback manifests are limited to
8 MiB. These limits bound review artifacts and processing cost.

## Integrity dependency chain

**[verified]** A package rebuild starts from the original raw bytes and the
inspector's checked directory metadata. It does not recreate the package from
a template or make assumptions about app size, key, entry index or app base.
After patching the decoded application, it recalculates:

1. `app.bin` data CRC.
2. `app.bin` directory header CRC.
3. Enclosing `app_area_head` body CRC.
4. Enclosing application-area header CRC.
5. UFW `flash.bin` payload CRC, after SFC encoding.
6. UFW entry-table CRC, over the encoded entry records.
7. UFW header CRC.

Some recalculated values can remain equal; the manifest records both values.
The unchanged bytes are copied exactly, including `uboot.boot`, `ota.bin`,
configuration/resources, the key records, allocation padding and marker bytes.
The report's logical field offsets locate encoded or plaintext storage fields;
they do not infer runtime addresses. See [docs/12](12-package-inspection.md) for
the two SFC offset origins and precise CRC parameters.

The rebuild result inherits the inspector's explicit limitations: no claim is
made about nested SPL/OTA executable validity, reserved flash regions, device
compatibility, or bootability. In particular, valid CRCs and a successful local
rollback do not prove a hardware recovery path. The project's
[recovery rules](07-recovery-and-risk.md#4-rules-of-engagement-adopted-from-al-255s-safety-review)
continue to govern device writes.

## Real package round trips, 2026-09-14

**[verified locally; no device I/O or vendor output files]** All three retained
packages from [docs/12](12-package-inspection.md#fresh-local-verification-2026-09-14)
passed the following checks:

- Empty-patch decode/repack returned exactly the original bytes.
- A one-byte offline probe changed the first flag of algorithm 4 in the known
  msfa table from `41` to `c1`; all seven integrity layers were recalculated.
- Re-inspection accepted the result and retained the original identities.
- Manifest rollback returned exactly the original bytes and SHA256.

The probe is a reproducible builder test, not a proposed firmware feature or
an image that was run on hardware.

| Package identity | Application probe offset | No-op equality | Rollback equality |
| --- | --- | --- | --- |
| `FM-1_009` | `0x8C47E` | byte-identical | byte-identical |
| `FM-1_014` | `0x8CBDE` | byte-identical | byte-identical |
| `FM-1_015` | `0x8BE9E` | byte-identical | byte-identical |

Input/restored SHA256:

```text
FM-1_009  5b3ac73bdd5ec6c774ecf9be65f51b2575ad67b775f8fb175c7130ea8af687ae
FM-1_014  a1adca99b1f9823ff2873292be74877a7a14ca0846fca3d25a23aba2750162d3
FM-1_015  db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a
```

Offline probe result SHA256:

```text
FM-1_009  a41bafc3f3ebbafa33a231afdb205dfabcc7640353a666b31ea62e450c9578e5
FM-1_014  913f2531a21a03155e378212645af19784ab742726a0bc21357c810a645bc82d
FM-1_015  d702ebc9b6885a65f04801633294a80f08e2b4df61830e46cf4c496016e8fc87
```

## Synthetic validation

```powershell
python -m pytest tests/test_fm1_rebuild.py tests/test_fm1_package.py
```

Tests use the independently assembled synthetic package fixtures from the
inspector suite, including its non-stock app-area base. They cover byte-exact
no-op/rebuild/rollback/redo; unrelated payload and padding preservation; the
exact allowed difference set; wrong source hashes and original bytes; malformed,
overlapping, out-of-range and oversized patches; identity changes; tampered
manifests; and paired, non-overwriting CLI output. Vendor firmware is unnecessary
for these tests.

The rebuild code reuses the existing inspector's checked format/cipher helpers;
their kagaimiq and Echomatter provenance and MIT notice remain documented in
[docs/12](12-package-inspection.md#tests-and-provenance) and
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). This stage adds no vendored
compiler, package-builder binary or hardware write path.
