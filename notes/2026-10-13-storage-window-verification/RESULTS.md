# Native settings window geometry verification

[verified] `tools/native/storage_window.py` binds two matching complete backups
and a complete candidate to externally retained SHA256 values. It inspects both
reservation tables, requires two aligned sectors inside 0xFC000..0xFF000, checks
the stock prefix, opaque VM/BTIF/USR/globals gap and key sector are preserved,
and rejects a window containing existing data. Receipt verification reconstructs
all fields rather than accepting an edited approval bit.

[verified] 30 cases across stock-V15 and recorded-092 profiles passed in 30
parallel Hera containers. All 30 logs, container exits/no-OOM states and seven
source digests were checked after the launcher terminated successfully. Public
collection, source hashes and result metadata are retained here; raw logs are
under private ignored `build/native-storage-window-20261013/hera-results/`.

[verified] The retained stock092 matching pair and installed c543 candidate pass
this offline geometry check for 0xFC000..0xFE000. The receipt contains hashes and
geometry only, no private settings bytes. This uses historical backups, not a
fresh physical read. No USB operation or flash modification occurred.

[verified] Ownership, backup provenance, semantic migration, physical rollback
and hardware admission remain false. Erased bytes alone cannot prove ownership.
The native adapter must enforce the exact two-sector range, keep OTA cleanup
disabled, stop audio while NOR operations mask interrupts and propagate uncertain
write failures without retries. A settings journal cannot replace whole-project
SAVE: compact project serialization and a separately allocated transaction store
remain required for the complete release.

[verified] Serena and Rarefaction currently select the primary checkout. Both
rejected queries against this absolute worktree (ignored/outside root). Shared
configuration was left unchanged; direct source inspection and Hera execution
provided verification here. No target ABI claim is made for this Python tool.
