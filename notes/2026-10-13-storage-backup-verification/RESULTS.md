# Lossless stock-storage backup verification, 2026-10-13

[verified] All 30 cases passed in 30 independent Hera containers. Every log,
container exit and OOM flag was checked; the five source hashes match this
checkpoint. Tests cover both stock-V15 and recorded-092 reservation geometry,
opaque bank tails, mismatched backups, retained digest mismatch, malformed
headers/reservations, profile mismatch, missing/corrupted files, forged
manifest claims, extra entries, symlinks, exclusive output and truncated images.
Private output files have mode 0600; their directory has mode 0700.

[verified] The two saved matching owner FM-1_092 stock backups were exported
without hardware operations. A full baseline and exact VM, BTIF, USR and
0xFC000..0xFF000 gap copies were independently verified using the retained full
backup digest and archive manifest digest in historical-092-archive.json.
Private bytes remain in build/native-storage-backup-20261013/private-stock092/;
only digests and verification results are committed.

[verified] This checks known reservation geometry and lossless archive contents.
It does not verify backup acquisition provenance, complete firmware validity,
semantic settings migration, physical rollback, or permission to program flash.
Historical erased gap bytes do not establish a safe write window on another
unit or on the current unit without fresh backup evidence. The exporter has no
hardware transport or write path.

[verified] Rarefaction Python is ready at the primary checkout but rejects this
absolute worktree as outside its root. Serena is configured for C++ at the
primary checkout and rejects this ignored worktree Python file. Source inspection
and actual tests were used; no shared MCP configuration was changed.
