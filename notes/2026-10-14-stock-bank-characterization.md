# Retained FM-1_092 VM/USR bank characterization — 2026-10-14

## Decision

[verified] A read-only scan of the locally retained historical FM-1_092 archive shows that VM and USR are not uniformly erased. VM has non-erased bytes in two sectors, while USR has dense non-erased data across ten sectors and partial non-erased content in two more. The scan supports treating both reservations as opaque stock state. It does not identify records, settings, presets, or ownership, and it does not authorize reuse of even sectors that read as all `0xFF`.

[inferred] Erased sectors within a named VM/USR reservation may be free space in a stock allocator, erased log pages, or unused padding. Without the matching stock allocator/format and a version-matched semantic parser, a static all-`0xFF` observation cannot distinguish those cases or prove the stock firmware will not later use the sector.

No hardware command or write was performed. No private binary content or preset data is reproduced here.

## Archive identity and method

The only input was the existing owner-private archive directory `build/native-storage-backup-20261013/private-stock092/`. The archived profile is `recorded-092`; the committed receipt `notes/2026-10-13-storage-backup-verification/RESULTS.md` says the two saved matching full images were exported and the exact named extents checked against their manifest. Its baseline SHA-256 is `96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`; the archive manifest SHA-256 is `ae1bb3f601e8bdffa2980bb6b4a24ced4439ecda62619fe7f7a07cdb2d9a2923`.

[verified] This pass recomputed SHA-256 and byte count for each local bank copy and matched each to its manifest entry. The scan then split the opaque copies into 4 KiB sectors, counting bytes equal to `0xFF` and the number of distinct byte values per sector. It did not print or decode sector contents. The distinct-value count is only a density descriptor, not a record-format detector. Reproducible read-only command:

```sh
python3 - <<'PY'
from pathlib import Path
import hashlib, json
root=Path('build/native-storage-backup-20261013/private-stock092')
m=json.loads((root/'manifest.json').read_text())
for name,base in [('vm.bin',0xD9000),('usr.bin',0xEA000)]:
    data=(root/name).read_bytes()
    assert len(data)==m['files'][name]['bytes']
    assert hashlib.sha256(data).hexdigest()==m['files'][name]['sha256']
    rows=[]
    for i in range(0,len(data),4096):
        s=data[i:i+4096]
        rows.append((base+i,sum(b==255 for b in s),len(set(s))))
    erased=[off for off,ff,_ in rows if ff==4096]
    occupied=[(off,4096-ff,distinct) for off,ff,distinct in rows if ff<4096]
    print(name, 'fully_erased_sectors=',len(erased), 'nonfully_erased=',occupied)
PY
```

The exact archive component hashes (privacy-safe identifiers) are:

- VM `[0xD9000,0xE9000)`: 65,536 bytes; SHA-256 `bfbca6eba6e259269880685cb2dc5c19a403d5e343699af9d18e9e54551c2299`.
- USR `[0xEA000,0xFC000)`: 73,728 bytes; SHA-256 `f63fe429d2ba487b138d17b60d4a26bcf15bf35c051cb57cef6cf9b81988b3c9`.

## Sector observations

All addresses are flash offsets, with half-open sector ranges. “Non-FF count” means only bytes that differ from `0xFF`; it is not a measure of live semantic data.

| Reservation | 4 KiB sectors observed | Aggregate observation | What it establishes |
|---|---|---|---|
| VM `[0xD9000,0xE9000)` | `[0xD9000,0xDA000)`: 142 non-FF bytes, 75 distinct byte values; `[0xDA000,0xE8000)`: fourteen consecutive sectors all `0xFF`; `[0xE8000,0xE9000)`: 213 non-FF bytes, 87 distinct byte values | 14/16 sectors all `0xFF`; 2 sectors have sparse non-FF bytes | Two concrete sectors contain structured-looking bytes; the two endpoint sectors are not erased. The middle erased run does not prove it is reclaimable. |
| USR `[0xEA000,0xFC000)` | `[0xEA000,0xF2000)`: eight sectors each have 4,096 non-FF bytes and 106–109 distinct byte values; `[0xF2000,0xFA000)`: eight consecutive sectors all `0xFF`; `[0xFA000,0xFB000)`: 11 non-FF bytes, 11 distinct values; `[0xFB000,0xFC000)`: 3,594 non-FF bytes, 61 distinct values | 8/18 sectors all `0xFF`; 10 are wholly non-FF and 2 are partial | USR is materially populated. The initial dense run and non-FF tail are consistent with serialized records/metadata, but no schema is proven. The erased run is not ownership evidence. |

Adjacent BTIF `[0xE9000,0xEA000)` contains 10 non-FF bytes in this archive. The unnamed globals gap `[0xFC000,0xFF000)` is all `0xFF` in this historical copy. Neither observation changes their protected/unnamed status or admits them for storage.

## What stock-source evidence does and does not say

- [verified] `tools/jieli/raw_flash_profile.py` identifies the FM-1_092 reservation extents from stock descriptors: VM 64 KiB, BTIF 4 KiB, USR 72 KiB. This is geometry, not a payload decoder.
- [verified] `tools/native/storage_backup.py` and the raw profile parser preserve VM/BTIF/USR bytes as opaque data. The archive receipt explicitly leaves backup acquisition provenance, complete firmware validation, semantic migration, physical rollback, and hardware admission unverified. This historical image is not a fresh device baseline.
- [verified] The local reference folder `reference/FM-1-RE-v15` is absent in this checkout. The earlier provenance note records that a similarly named local reference, when present, analyzed FM-1_009 rather than FM-1_092. No FM-1_092 record decoder was found in the inspected checked-in parsers.
- [reported] The SDK diagnostic review (`notes/2026-10-11-sdk-diagnostic-review.md`) reports that the analyzed stock-V15 native image registered syscfg file initialization but discarded VM/BTIF registration sections; it found no direct retained call to `syscfg_vm_init`, while VM busy/idle callbacks inspect RAM state. The same review warns that linked erase/reset code is not proof of execution. This call trace is for a different analyzed firmware build, is not an FM-1_092 data-format analysis, and cannot prove the FM-1_092 banks are unused.
- [verified] The local open-native Dinghy/Felucca-derived `firmware/third_party/dinghy/hal/fm1_flash.h` describes its own project store `[0x97000,0xE0000)` as “projects, user samples; settings” and its own globals area `[0xFC000,0xFF000)`. This is an independently selected application layout, not evidence that stock FM-1_092 uses its USR reservation the same way. It must not be used to label the retained stock sectors.
- [verified] The local `reference/dinghy/tools/fm1pkg_make.py` emits a named USR descriptor for its package, but does not define the semantics of the owner’s stock bank bytes. A descriptor name alone is not a format contract.

## Conclusion and next evidence needed

[verified] The static scan cannot settle whether stock VM contains user presets/configuration, runtime variables, storage allocator metadata, or some combination; it likewise cannot establish whether USR contains user projects/presets or is available. The named reservations plus observed non-FF bytes require preservation until a version-matched format/usage analysis is complete. The all-FF spans are noteworthy characterization results only, not allocation proposals.

The most direct next offline gate is a version-matched parser/allocator analysis for the exact FM-1_092 stock build, checked against both matching archived full images. It must enumerate every record and metadata structure while retaining unknown bytes, then map sectors to allocator reachability and stock features. If the SDK source required for that analysis is not already accessible locally, acquire its exact revision and license/source provenance through the authorized offline software path; do not substitute V15 or community format assumptions. A future proposal must identify precisely which sectors can be preserved or migrated, demonstrate stock-state round trip and byte-exact rollback from the archived baseline, and receive explicit owner authorization before changing descriptors or using any such sector. This note does not admit reuse or any device operation.

## Scope and limits

Read-only analysis of local files and source. No device, USB, MIDI, flash, power, reboot, network transfer, or code build/test was performed. The existing backup verification receipt is prior evidence; the only new check here was local size/hash matching plus the aggregate sector scan. Serena/Rarefaction were not used for binary-sector characterization; prior worktree notes report their configured roots point at the primary checkout, so no shared project selection was changed. Other concurrent worktree changes were left untouched; this task owns only this note.
