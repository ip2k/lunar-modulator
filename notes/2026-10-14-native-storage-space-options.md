# Native project storage space options — 2026-10-14

## Decision

[inferred, conditional] Keep two-generation transactions, but evaluate **two
48 KiB slots for collector-generated native SAVE only**. The latest source
bound is 43,130 bytes for the complete compact stream, including the fixed
1,316-byte stream-header/directory reservation. A 48 KiB slot is 49,152 bytes;
the existing 32-byte transaction header leaves 49,120 bytes for the stream, so
the source bound fits with 5,990 bytes of margin. Two such slots occupy exactly
98,304 bytes (24 sectors). This retains the old generation while erasing and
writing the other slot, as the existing store does.

This is a viable **logical-capacity reduction**, subject to completing the
collector-bound validation below. It does not solve the physical allocation:
no 24-sector range, nor an equivalent owned scatter map, is currently admitted
in the FM-1 layout. Keep the generic binary import limit at 98,304 bytes; the
native collector bound does not constrain imported files. Do not silently
truncate, partially save, or report success for a generic import that cannot
fit a native SAVE slot. The save/load API needs an explicit distinction between
collector-produced and imported data, with a checked refusal or separately
approved storage strategy for the latter.

## Capacity arithmetic and evidence

| Quantity | Bytes | Evidence / implication |
| --- | ---: | --- |
| Native SAVE maximum (source-derived) | 43,130 | `notes/2026-10-14-collector-total-bound.md`; sums collector-reachable chunk maxima, 24 chunk-start alignment allowance and fixed stream reservation. |
| One 48 KiB physical slot | 49,152 | 12 × 4,096-byte NOR sectors. |
| Existing per-slot transaction header | 32 | `firmware/native/project_store.h`, `LP_HEADER`. |
| Native SAVE payload available in one slot | 49,120 | 49,152 − 32. |
| Bound margin in each slot | 5,990 | 49,120 − 43,130. |
| Two slots | 98,304 | 24 sectors / 96 KiB total; enough for two 48 KiB generations. |
| Generic import maximum | 98,304 | Existing `LP_MAX`; this exceeds one 48 KiB slot's payload by 49,184 bytes. It remains a separate compatibility requirement. |

The store is a relative-offset, contiguous two-slot transaction abstraction;
its header explicitly grants no physical permission. `lunar_project_begin`
erases only the inactive slot, and commit validates data before writing the
header/commit marker. Shrinking its configured slot size to 49,152 bytes would
preserve this transaction shape for the bounded native writer, but not the
existing maximum-size generic import contract. Existing readers also validate
against the slot's payload capacity. Implementation must therefore route and
validate the distinct formats/callers explicitly before any capacity change.

The source-bound note is conservative rather than a runtime proof: it
overcounts mutually constrained maxima, and at the time of inspection says a
second maximal collector/writer fixture is still being exercised. The retained
capacity test source has native two-pass collection, compact writing and
rollback modeling, but the exact latest matching Hera receipt was not found in
the coordination `out` tree during this task. The older retained dense fixture
is 32,924 bytes and is not a maximum. Therefore the 48 KiB slot is an attractive
target, not yet an accepted bound: first retain and review the completed
maximal-state Hera run, including emitted length, exact input/source hashes,
two-slot generation behavior and refusal at the 49,120-byte payload limit.

## Physical space: presently unallocated

The latest expanded-layout ownership review reports the retained all-13 app at
863,380 bytes, 5,456 bytes under its candidate application budget. In the
recorded FM-1_092 geometry, aligned app/config records end at `0xD7AB0` and the
expanded boundary is `0xD9000`; only `[0xD8000, 0xD9000)` is a wholly erased
4 KiB sector. The preceding 1,360 bytes are only padding/tail, not a sector.
There is no current raw-package receipt or physical storage admission for the
retained link.

The rest of the map is not available capacity under the recorded preservation
profile: VM `[0xD9000,0xE9000)` (64 KiB), BTIF `[0xE9000,0xEA000)` (4 KiB),
USR `[0xEA000,0xFC000)` (72 KiB), and the opaque globals gap
`[0xFC000,0xFF000)` (12 KiB). `key_mac` `[0xFF000,0x100000)` is protected.
The candidate settings journal window is 8 KiB and explicitly has ownership,
backup-provenance, semantic-migration and hardware-admission results false; it
cannot be counted as project space. The approved expanded profile preserves
raw bytes from `0xD9000` onward, so it does not authorize consuming these banks.
V15 has a different VM extent and cannot be treated as spare capacity either.

Even if the entire 144 KiB hypothetical ledger were owned, it is not a physical
allocation and assumes data currently marked opaque or preserved. For the
reduced 96 KiB requirement, 24 whole sectors still must be identified and
admitted. The existing profile only exposes one full erased app-tail sector.
No contiguous range or 24-sector scatter set has been shown to retain all
opaque content and the required stock rollback bytes. The store currently
requires contiguous slots, so a scatter allocation would also require a
separately specified/reviewed store and recovery format.

## Alternatives considered

| Option | Evidence | Assessment |
| --- | --- | --- |
| Native-only 2 × 48 KiB raw slots | 43,130-byte source-derived bound; 49,120-byte payload capacity each | Best next storage target. Preserves all collector-supported states if the bound and save/import separation are proven. Still needs a 96 KiB physical extent plan. |
| Keep 2 × 100 KiB slots | Current `LP_MAX=98,304`; 102,400-byte slots | Preserves generic maximum-size two-generation persistence, but needs 204,800 bytes / 50 sectors. No admitted allocation; even the hypothetical 144 KiB ledger is short by 57,344 bytes. |
| Whole-file compression | Existing state container supports independently DEFLATED chunks, but has no evidence that every valid native state compresses below 49,120 bytes | Cannot provide a hard slot guarantee without raw fallback, which still must fit. Compression may help typical cases; reject or select another approved medium on incompressible output. |
| Compress firmware tables/code | Best recorded lossless wave-table experiment saves 25,583 bytes after isolated decoder; drum sample experiment saves 8,976 bytes after isolated decoder. Existing app tail is 5,456 bytes. | Does not produce the roughly 92,848-byte reduction needed to carve 96 KiB at the end of the app region, before full-link decoder/RAM costs. Table expansion needs 83,712 B RAM or an unimplemented cache; drum expansion needs about 110 KiB. No justified feature-preserving code-size path currently closes the gap. |
| Reclaim VM/BTIF/USR/gap or move stock data | Current profile preserves the bytes; bank semantics/ownership are incomplete; settings-window check explicitly denies admission | Not supported. Requires a separately reviewed full data export/restore/migration and rollback plan, an exact layout with 24 admitted sectors, and relevant owner approval. Historical erased bytes alone are not ownership proof. |
| Scatter two slots across candidate regions | Current store accepts contiguous slots; no admitted set of 24 sectors | No present allocation and adds format/recovery complexity. Reconsider only after extent ownership is proven and transaction recovery is specified/tested against interrupted erases and writes. |

## Compression and existing code

`engines/state/state_bin.c` already supports the container's `DEFLATED` chunk
flag using raw DEFLATE with a window limited to 4 KiB and
`engines/state/fm1_deflate.{h,c}`. Its comments identify an inflater working
area around 5.5 KiB plus a 64-byte pull-reader buffer; the encoder is bounded
and has caller-supplied scratch. This is a per-chunk serialization feature,
not compression of the entire transaction store, and should be evaluated
before introducing another codec. The already-vendored `firmware/third_party/tinf`
is used in offline wavetable investigations and elsewhere in the native build;
that full-window DEFLATE decoder is a distinct option with its own stack/RAM
and source/licence audit, not a reason to add another dependency now. No claim
is made that current native SAVE chunks are compressed or that this code
reduces the worst-case project bound.

If whole-file/chunk compression is explored for typical-space gains, retain the
uncompressed byte length, format/version and integrity checks, cap expansion at
the validated raw size, reject malformed/truncated streams, and never commit a
slot until decode/parse validation succeeds. The existing transaction CRC is
over stored bytes; decoded-format validation remains necessary. Compression
failure or expansion beyond 49,120 bytes must leave the prior generation
recoverable and return an explicit no-space/refusal result. No compression
ratio may be used as a capacity guarantee without an exhaustive bound over the
entire accepted domain.

## Recommendation and next dependency

1. Finish the source review and exact maximal-state Hera test receipt for the
   43,130-byte SAVE bound. Re-run with the project's actual two-pass collector,
   writer and transaction model; hash the source/test/fixture and retain exact
   logs. Confirm both prior-generation preservation and failure/refusal paths.
2. Define a native-collector-only 48 KiB save contract and preserve generic
   import compatibility explicitly: either reject oversized imports before
   changing stored state, or maintain another approved path for them. Do not
   globally lower `LP_MAX` or assume every imported project is collector-made.
3. Separately identify, from a fresh backed-up image and the approved raw-layout
   process, 24 owned sectors that retain VM/BTIF/USR/gap and stock recovery
   contents. Until then, do not assign the 96 KiB logical store to NOR.
4. Only after those gates, bind exact slot bases/sizes to a reviewed raw-layout
   verifier and test interruption/rollback behavior; physical install remains
   a separate authorized acceptance gate.

No production source or geometry was changed. This task performed no build,
device, USB, MIDI, flash, power or reboot operation. The exact current limiting
fact is the missing admitted 96 KiB physical extent; compression alone cannot
resolve it.

## Evidence references

- `notes/2026-10-14-collector-total-bound.md` — 43,130-byte conservative native
  collector/writer source bound; based on base
  `31d2e8cd05afd4875d303dca1b52ea5c138aed0f` and notes a maximal combined
  fixture still in progress.
- `notes/2026-10-14-expanded-storage-ownership-review.md` — map, retained link,
  opaque banks, candidate ledger and explicit non-admission results.
- `notes/2026-10-14-native-size-savings.md` and
  `notes/2026-10-12-native-engine-link.md` — current link headroom and prior
  offline table/sample compression measurements and RAM implications.
- `firmware/native/project_store.h` and `firmware/native/project_save.h` —
  32-byte header, sector-aligned contiguous two-slot store, 98,304-byte generic
  limit, native two-pass writer preflight and slot-derived output capacity.
- `engines/state/state_bin.c`, `engines/state/fm1_deflate.{h,c}` and
  `firmware/third_party/tinf/tinflate.c` — existing chunk compression and
  distinct vendored inflater implementations.
- Read-only Hera search of the coordination `out` tree on 2026-10-14 did not
  locate a matching latest maximal collector-capacity result. This is a
  receipt-availability limitation, not evidence that the run failed.
