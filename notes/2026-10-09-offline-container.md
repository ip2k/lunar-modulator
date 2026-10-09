# Offline stock container validation and remaining packing gates

2026-10-09. Personal MIT project. Branch
`feature/2026-10-09@guarded-offline-package` is explicitly stacked on the
pushed diagnostic checkpoint `566496a`; integrate after PR #104, not as an
independent branch from main. No device traffic or firmware writes occurred.

## Concrete result

`tools/jieli/inspect_fwsc.py` is an independently authored, read-only reader
for the established FM-1 FWSC/UFW envelope. Format sources are kagaimiq's
MIT [jl-misctools unpacker](https://github.com/kagaimiq/jl-misctools/blob/master/firmware/fwunpack_newfw.py)
and AL-255's [FM-1-RE OTA client](https://github.com/AL-255/FM-1-RE/blob/main/tools/fm1_ota.py).
No Felucca/SLOOP code was read or copied. The reader creates only an optional
new JSON report, refuses overwrite, and sends nothing anywhere.

Local stock V14 (`FM-1_updater.fwsc`), V15 (`FM-1_v15_cdn.fwsc` and the
previously acquired Baud Girl V15 copy) pass the outer header/list and all
payload CRC checks [verified]. The inspected FM-1_092 copy is rejected at
USR under this strict V14/V15 profile; its relocated auxiliary representation
is explained below. Every successful result explicitly says
`inspected-incomplete`, `packaging_ready=false` and
`device_execution=unverified`: nested flash rewrite remains unfinished.
99 focused tests pass, including outer-envelope and nested checks
(with optional real-container validation enabled), and the real stock SPL
pin check [verified]. No vendor bytes are
committed.

Rarefaction Python orientation used the original checkout's on-open Pyright
index. Serena's diagnostic checkout was activated but its cached C++-only
configuration rejected Python navigation even after adding Python to the
ignored project file; file inspection and Rarefaction were used for this
reader. Neither semantic tool establishes firmware format correctness.

## Format evidence checked against actual stock V15

The first 960 physical bytes are twenty 48-byte slots. Removing each slot's
last byte yields 940 logical header bytes; the rest of the file follows
unchanged. Marker bytes minus their one-based ordinal give `FM-1_015`, then
`0x7D` filler [verified: existing source rule and stock bytes]. This exposes
the identity; it does not establish permission to install any new version.

The first 64 logical bytes decode through the ENC XOR stream initialized at
`0xFFFF`. The same initial state is restarted separately for each 80-byte
entry record [verified: header/list interpretation and matching stock CRCs].
The header's CRC covers its remaining 62 decoded bytes; the entry-list CRC
covers the stored encrypted records. Polynomial `0x1021`, initial value
**zero**, no reflection or final XOR matches both, the flash payload and OTA
payload. Initial `0xFFFF` does not match the header. This is CRC-16/XMODEM,
not the previously documented CCITT-FALSE [verified].

V15's physical length is 699,956 and logical length is 699,936 bytes. The
header declares `AC791N`, eight entries, logical length 699,936, and two
remaining metadata fields 4 and 512 whose full semantics remain unknown
[verified values; interpretation unresolved]. For entries after the 940-byte
logical prefix, physical offsets equal logical offsets plus 20.

| Entry / type | Logical offset | Data / allocation bytes | CRC evidence |
| --- | ---: | ---: | --- |
| flash.bin / 0 | 0x400 | 602112 / 602112 | raw payload matches 0x9B24 |
| info.log / 2 | 0x93400 | 0 / 0 | empty payload matches 0 |
| USR / 50 | 0x93400 | 73226 / 73248 | SFC decoded matches 0xE3BC |
| isd_config.ini / 52 | 0xA5220 | 3296 / 3296 | SFC decoded matches 0xACEF |
| ota.bin / 100 | 0xA5F00 | 19969 / 20000 | raw payload matches 0xA1C9 |
| script.ver / 251 | 0xAAD20 | 27 / 32 | SFC decoded matches 0xAAB7 |
| blimit.bin / 161 | 0xAAD40 | 144 / 160 | SFC decoded matches 0x33FE |
| tail.bin / 255 | 0xAADE0 | 64 / 64 | raw payload matches 0x8936 |

All offsets/sizes/CRCs above are [verified: strict reader against stock V15].
The checked allocations are disjoint and inside the logical image. The OTA
payload is byte-identical to the reference that passes `package_guard.py`.
Its physical offset is therefore 0xA5F14, agreeing with the earlier bench
carve. The last 16 logical bytes begin `JLUFW`; other trailer fields need
explanation. The package SHA-256 is recorded in the ignored report; it is
not an authenticity signature.

The four auxiliary types (50, 52, 251, 161) use 32-byte SFC blocks with
key `0x980F`, the stock chip key. Each block restarts the ENC stream at
`key XOR (logical block offset >> 2)`, with logical container origin zero,
not the entry or flash payload origin. All four decoded CRCs match V15 and
V14. V15 script.ver decodes to `AC791N-v0.01-cfg_tool-v0.10` plus terminators,
consistent with AL-255's [protocol note](https://github.com/AL-255/FM-1-RE/blob/main/docs/io/11-ota-protocol.md)
[verified locally; named source supplied key/expected text]. Corrupting
an encrypted synthetic payload is now rejected; multiblock roundtrip and
wrong-origin regressions cover the block rule. Remaining metadata is
preserved as unresolved, rather than treated as permission to rewrite it.

### FM-1_092 representation boundary

The locally acquired `scratch/baudgirl-2026-09-29/fw/FM-1_092.fwsc` has a
larger flash.bin: 712704 bytes, versus V15's 602112. Its four auxiliary
payloads are **byte-identical ciphertext** to V15's, and their entry records
differ only in the offset field, each increased by `0x1B000`; sizes,
allocation, metadata and stored CRCs match [verified exact comparison].
Every auxiliary remains 32-byte aligned. USR's stored CRC is `0xE3BC` and
raw CRC is `0x5419` in both copies; decoding at its declared 092 offset
`0xAE400` yields `0xBC95`, while decoding those bytes at V15 offset `0x93400`
yields `0xE3BC`. Config/script/blimit show the same relocation dependency.
This is evidence of reused auxiliary bytes, not proof of how the updater
consumes or ignores them. The reader rejects this representation rather
than silently guessing the V15 origin or lowering the checksum gate.
FM-1_092's header/list and raw flash/OTA/tail CRCs were checked separately
before the stricter auxiliary gate was added. No device acceptance or
rollback behavior is inferred from that earlier partial result.

The nested `flash.bin` is a JLFS image using ENC-protected top records,
chip-key-dependent SFC blocks in the application area and further directory
CRCs [reported: MIT unpacker]. The existing unpacker tolerates an outer
flash CRC mismatch and stops parsing the UFW list as soon as it finds
flash.bin. It is useful as an independent extraction oracle, but its exit
success cannot be a complete package-validation gate [verified source].
The UFW isd_config.ini auxiliary entry is 3296 bytes, whereas the guarded
unpacked top/isd_config.ini is 699 bytes: these are different representations
and must not be silently substituted [verified lengths].

## Nested stock validation and no-op reconstruction

`tools/jieli/inspect_stock_flash.py` adds a read-only **stock FM-1_015** nested
profile [verified against the local V15 package]. It checks the flash header,
four ENC top-directory records, one SPL bank header, two SFC app/resource
records and seven child records: 15 header CRCs in total. It also checks eight
stored data CRCs (SPL, config, bank body, two directory bodies and three regular
files) and the stock chip-key blob CRC. The bank is uncompressed, 14368 code
bytes plus a 16-byte header, loaded at `0x01C02000`. Its decoded complete
14384-byte SPL, top config and cfg resource are byte-identical to the
`package_guard.py`-checked components. Outer inspection separately binds OTA.
App, cfg_tool and eq_cfg_hw extracted hashes also match the independent
jl-misctools unpacker's files [verified local comparison].

The app/resource SFC stream uses chip key `0x980F` with origin at flash-payload
`0x4000`; this differs from the outer auxiliary origin zero. Directory records
may cross 32-byte block boundaries, so the aligned region is decoded once.
VM, PRCT, BTIF, USR and key_mac are reserved descriptors with CRC `0xFFFF`,
not payloads to read/erase/checksum. Some reserved name tails contain additional
metadata (`CODE`, `AUTO`, or numeric bytes), retained without interpretation.
Strict profile guards retain their observed addresses, sizes and flags:

| Reservation | Physical flash descriptor address | Bytes | Flags |
| --- | ---: | ---: | ---: |
| key_mac | 0xFF000 | 4096 | 0x12 |
| VM | 0x93000 | 352256 | 0x12 |
| PRCT | 0 | 602112 | 0x92 |
| BTIF | 0xE9000 | 4096 | 0x92 |
| USR | 0xEA000 | 73728 | 0x92 |

These are verified descriptor fields, not a verified write/address mapping.
PRCT overlaps the image by design as a descriptor; its operational meaning
remains unresolved. The app-dir entry is `0x02000120`, while app.bin lies at
flash-payload offset `0x4120`. XIP translation must be established before any
modified app placement. The 556 bytes after the final resource block are
preserved exactly with no padding/encoding semantic claim.

The inspector decodes and inversely reconstructs nested regions in memory,
retaining all unknown bytes; it also reverses the outer ENC records and
reconstructs identity markers. The entire reconstructed 699956-byte FWSC is
byte-identical to the input [verified]. No binary is emitted. This no-op
proof checks preservation under the established decode rules; it does not
validate a modified image builder or device behavior. Original/reconstructed
FWSC SHA-256:
`db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a`.
Flash payload SHA-256:
`c1068a403c04a6378a626afb66cc217f72d13f10aa200e983b7a9817cc1dac03`.
Synthetic negative tests bypass only the outer gate to exercise malformed
nested layers even if an attacker repairs outer CRCs; the real-container test
runs the complete outer/stock guard. Damaged CRCs, component changes, name,
range and reservation errors are rejected.

All three extracted files (`app.bin`, `cfg_tool.bin`, `eq_cfg_hw.bin`) are
also compared byte-for-byte to the guarded reference [verified]. CRCs and
no-op reconstruction alone do not establish stock provenance: independent
review demonstrated that a modified app with repaired child/directory CRCs
previously passed. That classification gap is closed, with repaired-CRC
regressions for all three files and a separate EQ-reference mismatch check.

## Exact next gates and bounded offline experiment

No packager was implemented. The successful no-op reconstruction retains
stock structure; changed size/address/CRC rules and remaining metadata need
proof before a fail-closed modified-image builder is appropriate.

1. Explain auxiliary allocation metadata, trailer/version fields and the
   FM-1_092 relocated-ciphertext representation. Preserve the strict stock
   profile and damaged-layer regressions while these rules remain open.
2. Verify physical/XIP mapping and fixed app/resource allocation using named
   SPL instructions and actual package bytes. Preserve all guarded components,
   observed reservation descriptors and their uninterpreted metadata. Model
   changed app size/CRC, directory-body CRC, outer flash CRC and list/header
   CRC propagation; validate a synthetic modified-image experiment offline.
3. Only after those checks, construct an offline experimental container with
   an explicit identity/version policy, exact address/size manifest and
   complete independent revalidation. A container is not bootability proof.

Parallel stock-SPL research is on `chore/2026-10-09@stock-spl-handover`
(`e1201e9`), note `notes/2026-10-09-stock-spl-handover.md`. It reports a
`call r1` with boot argument 0x01c7fe08, disabled interrupts, and loaded SPL
RAM 0x01c02000..0x01c05830 overlapping the inert diagnostic reservation.
These are static findings, not executed behavior. Before a device experiment,
resolve that RAM/exception-stack ownership and final watchdog/clock/cache/secondary-
core handover, implement an observable diagnostic, and document the owner's
staged recovery/address/rollback gate. Existing bounded 4 KiB restoration
is not full-image or broken-application recovery proof.

## Reproduce / handoff

From the managed diagnostic worktree:

```sh
python3 tools/jieli/inspect_fwsc.py \
  /Users/likwid/Developer/mvave-fm1-firmware/scratch/FM-1_v15_cdn.fwsc \
  --stock build/jieli-diagnostic/stock-v15-reference \
  --json build/jieli-diagnostic/stock-v15-envelope-report-new.json
```

The reference and reports remain ignored. Existing report:
`build/jieli-diagnostic/stock-v15-envelope-sfc-report.json`.
No heavy build was required; the new work is a small offline Python reader.
The previously bounded LAN toolchain/runtime artifacts remain unchanged.
Nested reproduction (new report filename required):

The nested inspector requires the guarded reference to contain
`files/app.bin`, `files/cfg_tool.bin` and `files/eq_cfg_hw.bin` in addition to
the existing SPL/config/OTA/cfg assets. Copy the first two from the known
V15 unpack tree; copy the EQ file from its `files/cfg-extracted/eq_cfg_hw.bin`
to the reference's `files/eq_cfg_hw.bin`. These local vendor files remain
ignored; a missing or different reference file fails inspection.

```sh
python3 tools/jieli/inspect_stock_flash.py \
  /Users/likwid/Developer/mvave-fm1-firmware/scratch/FM-1_v15_cdn.fwsc \
  --stock build/jieli-diagnostic/stock-v15-reference \
  --json build/jieli-diagnostic/stock-v15-nested-noop-new.json
```

Ignored successful report: `build/jieli-diagnostic/stock-v15-nested-noop-final.json`.
Focused tests use the original project's `.venv/bin/python`; system Python
lacks pytest. Set `FM1_STOCK_FWSC` to the local V15 package and
`FM1_STOCK_UNPACK` to the guarded reference to enable actual-container/SPL
checks. Source is on the feature branch, now merged with origin/main after
PR #104 integration; root owns PR/CI/integration.

## Change log

- 2026-10-09: Validated established outer layers against local V14/V15/092,
  corrected the proven CRC name, added damaged-envelope regressions and
  persisted exact blocking format/handover gates instead of constructing an
  unchecked installer.

- 2026-10-09: Established and checked the V14/V15 auxiliary SFC block origin
  and all payload CRCs; retained strict rejection of FM-1_092's relocated
  ciphertext and recorded the exact comparison instead of guessing a decode
  origin. Three structural/device-version gate groups remain.

- 2026-10-09: Bound nested V15 SPL/config/cfg to guarded stock, validated all
  established nested CRCs, and reconstructed the full stock FWSC identically
  in memory. Preserved reserved descriptors and unknown tail bytes; no
  modified-image builder or installable output was created.

- 2026-10-09: Closed the stock-result classification gap found by independent
  review by binding all three extracted files to reference bytes; 99 focused
  checks pass including repaired-CRC modifications and actual V15 validation.
