# Stock SPL trailer scan and Felucca cleanup intersection with storage48

2026-10-14. Offline source/binary review only. No device, USB, MIDI, flash,
power, reboot, package emission, or writer/admission action occurred.

## Inputs and evidence

[verified: retained artifacts rechecked in this task] The pinned SPL hash matches the repository pin; the retained vendor listing decodes to the same bytes and compares equal. This task did not rerun the vendor disassembler. External loader cleanup below is verified from the retained source snapshot hash, not from execution on a device.

The pinned SPL is `top/uboot.boot` from the retained
`expanded-private-geometry-v1` capture under
`/home/claude/mvave-fm1/native-external-arenas-16-20261012`. Its SHA-256 is
`730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`, matching
the repository package-guard pin. The associated full capture SHA-256 is
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
The previously retained vendor-toolchain disassembly at
`/tmp/lunar-spl-record-byte-review/spl.lst` was produced from a temporary
assembly `.incbin` wrapper; decoded output is 14,384 bytes, hash
`730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`, and
byte-compares equal to the pinned SPL. This independently re-checks the
previous note's evidence artifacts; this task did not rerun the disassembler.
The source trace is preserved in
`notes/2026-10-14-stock-spl-update-record-byte-review.md`.

Felucca source provenance is pinned in the repository's
`firmware/third_party/expanded-loader-offline/UPSTREAM.md` to upstream
Felucca commit `1727537624390cc3f9c7dff2456b43b3a8edb005`. Its stated
offline-probe edits omit record invalidation/cleanup, so the cleanup analysis
uses the retained source snapshot
`/home/claude/mvave-fm1/native-baseline-20261012/firmware/loader/ldr_core.c`,
whose SHA-256 is
`389aa2e09e74fdac184221edd9b8b7d76eb59ec3dabd11008cbb06081f9fe1de`.
The same bytes occur in the slot48 source snapshot. This source snapshot
contains the record-drop implementation described below; no claim is made
that Lunar's modified host-only loader performs that cleanup.

## SPL scan behavior

[verified: retained exact-byte vendor disassembly] The statements in this section describe decoded instructions and constants; they do not establish that the condition occurs on a particular boot or that a device executed this path.

The exact disassembly has a conditional flash-record scan. At SPL offset
`0x2e08`, a zero ordinary-app selection value branches to `0x2f78`, around
the scan. The loop at `0x2e0c–0x2e74` is reached when ordinary app selection
did not succeed. The loop obtains flash capacity, sets a sector stride (4 KiB
for the recorded 1 MiB profile), starts at `capacity - stride`, reads 80
bytes at `boundary - 0x100`, and decrements the boundary by one stride.
It stops after the boundary falls to `0x1000`. For this profile the exact
candidate offsets are:

```
0x01f00, 0x02f00, ..., 0xfef00
```

That is one candidate in every 4 KiB sector except the first and last sectors.
It does not scan `capacity - 0x100` in the final sector. The candidate offset
is always sector base + `0xF00`.

A candidate passes SPL's record checks only when the 16-bit word at +6 is
`0x5441`, CRC16 over bytes +2 through +79 (78 bytes) equals the 16-bit word
at +0, and the 16-bit word at +2 is nonzero. On a match, SPL reads the
pointer at +72 and proceeds to a separate 32-byte inner-header CRC check.
These checks are integrity filters, not authentication. An ordinary valid app
selection bypasses this flash scan; the scan is not a general boot-time
inspection of all records.

## Cleanup behavior and predicate difference

[verified: retained source snapshot] The statements in this section are derived from the retained ldr_core.c snapshot at the hash recorded above. They are source behavior, not an observation of physical flash cleanup.

In the pinned Felucca loader source, `LDR_REC_LO=0x93000` and
`LDR_REC_HI=0xFC000`. `ldr_records_drop()` first clears the RAM record,
then loops with `s=0xFC000; s>0x93000; s-=0x1000`. It reads 80 bytes at
`s-0x100`. If the word at +6 is `0x5441`, the word at +0 is nonzero, and
that word equals CRC16 over +2..+79, it erases sector `s-0x1000`.
Consequently cleanup candidates run from `0xFBF00` down through
`0x93F00`, inclusive, and the erased sector is the 4 KiB sector containing
the candidate.

Unlike SPL dispatch, cleanup does not require the +2 word to be nonzero and
does not validate or follow the +72 pointer or inner header before erasing.
Its predicate is therefore a superset of the SPL's outer-record predicate.
The source calls record cleanup after successful update completion and on
the wrong-flash refusal path. This distinction matters: a payload that SPL
would reject can still look like a cleanup record and cause an entire sector
erase when the loader runs this path.

## Exact collision with the proposed two-slot map

[verified: address-set arithmetic over the documented map and scan ranges] The intersection is exact for the listed ranges; it does not assert current bytes match a record.

The arithmetic-only storage48 map in
`notes/2026-10-14-storage48-migration-plan.md` has two 12-sector slots:

| Slot extent | Trailer candidates in those sectors | Count |
| --- | --- | ---: |
| A: `[0xD9000,0xE0000)` | `0xD9F00–0xDFF00`, step `0x1000` | 7 |
| A: `[0xE5000,0xE9000)` | `0xE5F00–0xE8F00`, step `0x1000` | 4 |
| A: `[0xEA000,0xEB000)` | `0xEAF00` | 1 |
| B: `[0xEB000,0xF7000)` | `0xEBF00–0xF6F00`, step `0x1000` | 12 |

All 24 candidates are within both the SPL's full 1 MiB scan and Felucca's
cleanup candidate range `[0x93F00,0xFBF00]`. The current OTA staging range
`[0xE0000,0xE5000)` is excluded by the map, but this does not avoid the
other scanned sectors. If any candidate's 80 bytes satisfy the corresponding
predicate, the SPL may dispatch it after ordinary app selection fails, and
Felucca cleanup may erase that candidate's entire containing sector. Both
outcomes are incompatible with treating arbitrary journal bytes there as
inert.

This establishes a concrete conflict by address and predicate, not that any
current/project byte actually forms a matching record. No current device
bytes were read. The historical capture and record search described in earlier
notes do not prove a future journal state is safe.

## Consequence and limits

[inferred from the verified predicates and map] Treating these sectors as inert without an invariant is unsafe. No physical outcome is claimed.

The proposed scatter map cannot be treated as SPL-record-safe or cleanup-safe
by sector arithmetic alone. A future storage implementation would need an
explicit, format-level invariant that protects every candidate's 80-byte
window from the respective predicates across all persistent states and
partial writes, with mutation/fault tests, or a design that avoids every
affected sector. A probabilistic signature argument is insufficient.
This is an analysis result, not a new admission gate or a claim that the
existing storage authorization does or does not cover these sectors.

The project-side Felucca probe intentionally omits cleanup; it must not be
used to infer cleanup safety from its fake-NOR tests. No production code,
profile, SAVE flag, storage map, or device state was changed. This does not
establish stock VM/USR ownership, migration safety, physical boot behavior,
or installability.
