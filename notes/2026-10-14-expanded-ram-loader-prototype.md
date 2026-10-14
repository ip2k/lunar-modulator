# Expanded RAM-stream prototype boundary

## Result

Added an offline host-side pull scheduler in `tools/native/expanded_ram_stream_model.py` and focused standard-library tests in `tests/test_expanded_ram_stream_model.py`. It binds immutable baseline/target bytes to a canonical-SHA-pinned `offline-expanded-transport-manifest`, recomputes the exact changed sector set, enforces the expanded-d9000 profile and protected prefix/suffix, checks the directory sector is last, and serves each changed 4 KiB sector as eight sequential 512-byte responses. It rejects stale image/manifest hashes, reordered or foreign sectors, protected-byte changes, admitted manifests, replay, and out-of-order pulls.

The class serves bytes only. It has no flash interface, sector erase/program/readback operation, USB/MIDI access, reset path, package admission or loader staging. It therefore proves only the offline scheduling and request-boundary model. It is not an FM-1 updater or an installable image.

## Exact candidate smoke

Read-only smoke against the existing private full-song candidate and transport receipt:

- Target: 1,048,576 bytes, SHA-256 `cd8f0de6548714868461f960de15dcc65fbc4a5e8c278f8f02d93e65010d6d76`.
- Canonical transport manifest SHA-256: `261f53873b266e93a4cc7ec4b2e99cec91b03f8dfb5ee634aae88c83d872c972` (the raw JSON-file hash is a separate value).
- Changed sectors: 213; 212 ordinary sectors followed by directory sector `0x4000`. First scheduled sector `0x5000`; final sector `0x4000`.
- Served payload: 1,704 responses of 512 bytes, 872,448 bytes total; concatenated stream SHA-256 `0d85673335fc2bc64803f3b4fc7fb79c52f5bddc17acc573a7c31a6dc5b481e4`.
- Manifest keeps `installable`, `hardware_admitted`, `physical_writer_ready`, `settings_migration_verified`, `recovery_verified`, and `device_io_performed` false. Baseline is retained historical evidence, not a fresh pre-write device pair.

No private binary or package was copied into this repository.

## Maintained-source boundary and blockers

The maintained `firmware/third_party/dinghy/src/ota.c` is the app-side M-UPGRADE package receiver, not the staged loader implementation. Its contract at lines 24–30 reserves `0xE0000..0xE5000` (five 4 KiB sectors), with SPL record at `0xE4F00` and a 512-byte host-pull maximum. At lines 285–292 it rejects loader bodies above `0x4E00`; the known official body is `0x4DE1`, only 31 bytes below the limit. Lines 303–333 erase all five sectors, receive the loader body in 512-byte chunks, verify CRC/readback and write the head last; lines 334–339 wait for the host's final confirmation. This is a bounded loader-package staging workflow, not a mechanism for writing an arbitrary expanded app.

The staging range intersects the approved expanded layout's VM region (`0xD9000..0xE9000`). Reusing that route would violate the protected expanded-layout data. The existing Dinghy flash HAL at `firmware/third_party/dinghy/hal/fm1_flash.h:38–53` allows the app's own store and `0xE0000..0xE5000` staging range. Its RAM erase/program routines at lines 166–190 are not an expanded-app writer, and this task did not widen them. The staged loader source itself is not vendored in this checkout; `firmware/third_party/dinghy/UPSTREAM.md` identifies it as excluded. Therefore there is no reviewed RAM-resident loader source/link target here against which to measure target code or RAM footprint. No claim that a custom loader fits the existing 20 KiB body or 80 KiB RAM loader contract is made.

The candidate transport plan (`tools/native/expanded_transport_manifest.py`) explicitly labels itself review evidence, not a command stream (docstring lines 3–7). The new model preserves that boundary. A target-side adapter still needs a maintained or separately reviewed RAM-resident flash transaction that can execute outside the app XIP range, validate each sector, write/read back safely, preserve protected regions, and commit the app directory last. Its code/RAM footprint, XIP behavior, interrupt/USB-MIDI path, failure recovery and current-device identity gate remain unproven.

## Verification

Focused tests passed in the pinned networkless, bounded container with Python `unittest`: 4 tests passed. Pytest is not installed in the selected image or host interpreter; no dependency was added. The exact private candidate smoke above exercised all 1,704 requests without any target operation. No target linking, hardware, package admission or install was tested.

## Next dependency

Before any target implementation, obtain the maintained staged-loader source and its exact build/link configuration (or identify a reviewed alternative that does not overwrite VM/USR data). Then prototype the RAM-resident sector writer behind a fake flash interface, measure code/data/stack against the real RAM linker map, and test power-cut/recovery phases with a model. Only after review should that transaction be composed with the current hash-bound candidate receipt. A fresh matching device backup, migration/recovery proof and owner-controlled hardware acceptance remain separate gates.
