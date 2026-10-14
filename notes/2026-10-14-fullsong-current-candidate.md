# Fresh full-song expanded candidate preparation (2026-10-14)

## Result and boundary

The existing guarded `tools/native/expanded_candidate.py` accepted the fresh 862,296-byte full-song diagnostic app and produced a private FM-1_092 expanded-d9000 raw NOR candidate from the retained matching stock backup pair. `tools/native/expanded_transport_manifest.py` then accepted the resulting candidate together with the exact linked image receipt and prepared preload receipt. This establishes offline correspondence and protected-range preservation for this candidate only. It is not an OTA/FWSC package, is not installable or hardware-admitted, and authorizes no write.

The private raw target is `/home/claude/mvave-fm1/fullsong-current-candidate-20261014/candidate/target.bin` (1,048,576 bytes; SHA-256 `cd8f0de6548714868461f960de15dcc65fbc4a5e8c278f8f02d93e65010d6d76`). Candidate receipt: `candidate/receipt.json`. Offline transport plan: `transport/manifest.json` (SHA-256 `98fb43486c03fdf87fc7437b50c0c1e736a7a225170b613cd720f713ad549723`). Its sector order is evidence for review, not a command stream.

## Inputs and exact bindings

- Source controller worktree base: `b3a9c34baac68b710062a02d217859fb01568ccb`.
- Fresh app: 862,296 bytes; SHA-256 `b4eb29241bc32833a49d171c1b1ff0caa25246fdb94c66e604b78539afbdf956`.
- Linked ELF: SHA-256 `f370fdb840b723e78388b81f56a076d30a130ad560485281fbe6c2ad406d294a`.
- Expanded layout budget: 868,836 bytes; 6,540 bytes remain. App entry offset `0x4120`; tool record start 878,968 (`0xd6978`), configuration record start 879,352 (`0xd6af8`), records end 882,292 (`0xd7674`), all before `0xd9000`.
- Prepared selection request SHA-256 `0a3b172639a849aa95d0e97519fc67c2dafc674c17bdde053c48f04be84afe7a`; prepared profile SHA-256 `b4086fe3bc9e53e7bc6fc7c40a041fbbfdd46beb708ce318f218c3f63f3b1a46`; exactly one project `replacement-showcase-candidate-event-horizon`, startup index 0.
- Candidate baseline SHA-256 `96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`; backup pair byte-equal. The retained source is the 2026-10-12 private fixed-loader backup set in `/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/expanded-private-geometry-v1/`, not a fresh prewrite pair. Its manifest binds recorded FM-1_092 identity and historical USB-entry provenance but explicitly does not prove silicon serial identity or current-device state.
- The candidate's link audit passes with zero failures/pending checks and SDK-free/key/eFuse checks passing. Image and target receipts preserve `installable=false`, `hardware_admitted=false`, `hardware_tested=false`, `physical_writer_ready=false`, `settings_migration_verified=false`, and `ota_package_verified=false`.

## Layout and stock-component evidence

The guarded profile independently validates the 1 MiB raw NOR format, matching backup bytes, pinned recorded-092 payload/layout, app ELF flattening, firmware entry, expanded directory and CRCs. It records 213 changed 4 KiB sectors: 212 sectors from `0x5000` through `0xd8000`, plus directory sector `0x4000`; transport ordering places the directory sector last. The manifest's protected raw ranges are `[0,0x4000)` and `[0xd9000,0x100000)`. Direct comparison confirms both ranges are byte-identical to the retained baseline. The candidate preserves the pinned `uboot.boot` digest `730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`, `isd_config.ini` digest `0952afd96f533dd0fba72a8fab9cb4a4336f55424a1a89eecb13ff8a51a0eff0`, configuration tool digest `276579954f076886a6a7694f65dc71c034a3a2c204b76749065c0ac7b010d1b`, and cfg digest `962b3cbe3520502cf9ccd6a475b60e366b762ead371f0975a386c09c46201766`. It reports `configuration_contents_identical=true`; the guard re-parses the candidate directory, app/config extents, CRCs and exact tool/config payload bytes. Key/mac and all bytes beyond `0xd9000` remain byte-identical.

`ota.bin` is an outer package component, not a component of this raw NOR candidate. No FWSC/UFW package was composed, so this task does **not** verify an OTA component or a stock OTA package. The existing `tools/native/ota_candidate.py` is pinned to one separate V15 stock container hash, one 20-second probe app hash and `FM-1_990` identity; it cannot package this FM-1_092 120-second expanded app without changing its guard. No such change or unsupported package composition was attempted. A later package path needs its own exact stock-package/component correspondence guard.

## Execution and checks

Candidate construction used the pinned vendor pi32v2 objdump and existing guarded constructor in a network-disabled pinned container (`sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`), UID 1001, `docker-batch.slice`, 4 CPU/4 GiB/equal swap, read-only source/stock/build/toolchain inputs and task output as the only writable mount. It exited successfully. A second similarly bounded network-disabled container ran the existing transport manifest verifier against exact output bytes and receipts; it succeeded and wrote the manifest. Both outputs retain admission false. Docker inspect and command artifacts are in the private task output directory. No firmware binaries or backup material were added to Git; no USB, MIDI, flash, power or reboot operation occurred.

The transport manifest binds the candidate/app/ELF SHA values, canonical candidate/image/selection receipt digests, ordered project selection, request/profile hashes, actual changed-sector map and protected ranges. The manifest's `physical_writer_ready`, `hardware_admitted`, `settings_migration_verified`, `recovery_verified`, `installable`, and `device_io_performed` fields are all false.

## Remaining gates and next dependency

This is an offline candidate based on a retained historical backup pair, not a fresh observed prewrite pair. There is no OTA/FWSC package, no validated browser or native write transport, and no hardware admission. Settings migration, exact-stock rollback, interrupted-write recovery, SAVE runtime/storage safety, app boot/full-song device playback, installer package admission, current identity and watched recovery remain unverified. Next, coordinator should review the private receipt/sector manifest and choose a separately bounded package/transport or physical-evidence task under Mac hardware ownership. Do not treat raw candidate generation or its sector order as install permission.
