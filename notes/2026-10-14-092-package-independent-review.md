# Independent FM-1_092 expanded-container model review

## Result

[verified] I found no byte-level or CRC defect in `tools/jieli/model_092_app_replacement.py` for its one pinned source fixture and pinned 845,036-byte app. Independent decoding and rechecking corroborate the model’s logical payload preservation and D7000 extent. This is a structural offline result only: the model emits JSON, not an FWSC package, and neither device-side updater acceptance nor physical flash behavior is established.

## Independent inputs and method

- Source FWSC: 810,548 bytes; SHA-256 `ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80`.
- Candidate app: 845,036 bytes; SHA-256 `5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573`.
- Independent unpack reference: the retained public source package tree at `/home/claude/.local/share/codex-worktrees/092-package-model/scratch/092-package-model/FM-1_092.fwsc_unpack`. Extracted SPL, `isd_config.ini`, `cfg_tool.bin`, and `cfg` hashes match this tree exactly.
- Maintained independent decoder: kagaimiq/jl-misctools at `0a5b12db0ef38f3042acffbe2452730a37fd2405` (MIT). `firmware/fwunpack_newfw.py` SHA-256 `b263277648102eb259fd658f974a3d30ed6f15f6b0bff307de186fab040820af`; its cipher and CRC source hashes are `3e6112cf8171b6dcbbed738a8c57beda2559fd2bdf8c6e95b995e8a0d124c1f4` and `d400960a1a80ef993fc0108610173214c78ae4a9708d137ca6c9eb87c58d6a44`.
- Original physical FWSC prefix/marker removal and reconstruction returned the exact original source SHA. On the original, upstream `fwunpack_newfw.py` independently extracted a 712,704-byte flash payload and the protected component hashes above.
- To avoid creating a package file, I called the model builder in memory and passed its returned byte sequence through a Linux memfd to the upstream decoder. Only decoded temporary files were written under `/tmp`; no FWSC artifact was written or committed. Upstream decoding completed successfully. The app bytes matched the pinned app; SPL, config, CFG tool, and CFG resource matched the independent pinned unpack.
- A separate outer parser using upstream `jl_enc_cipher` / `jl_crc16` validated the output header CRC, entry-list CRC, and all eight payload CRCs. It also decoded every encrypted outer allocation at its source/destination logical offsets: all non-placement fields and complete decoded payload allocations matched, including the encrypted `USR`, `isd_config.ini`, `script.ver`, and `blimit.bin` entries. Their ciphertext changes are expected for relocation.
- Independently decrypting the inner SFC region with the upstream cipher confirmed the 968-byte decoded opaque suffix is preserved at `0xADC38` → `0xD3304`. It ends at `0xD36CC`; the modeled flash ends at `0xD7000`. The 845,036-byte app ends at `0xD260C`; CFG tool ends at `0xD278B`; CFG ends at `0xD3304`. The preserved-tail maximum is 859,680 bytes, leaving 14,644 bytes of additional app headroom.

Reproduction checks on Hera:

```text
/tmp/092-review-venv/bin/pytest -q tests/test_model_092_app_replacement.py
.... [exit 0; four tests]
/tmp/092-review-venv/bin/python /tmp/check_092_outer_equivalence.py
upstream_outer_crypto_crc: all entry CRCs pass; encrypted allocations logically identical after old-offset decode/re-encode
upstream_fwunpack_newfw: output UFW/JLFS decodes; target app and 4 protected payloads match reference
opaque_tail: exact 968 decoded bytes match at 0xADC38 -> 0xD3304
no FWSC file emitted; output passed via memfd; decoded-only temp artifacts
```

The output modeled-container hash reported in memory is `cfb7c149154bbd9243581d728a78a0605966aaf0536edd0c2633ac92fbe90e8b` (978,484 bytes). Model status remains `binary_emitted=false`, `packaging_ready=false`, `hardware_admitted=false`, `installable=false`.

## Findings and unresolved gates

- [verified] Legacy suffix handling is internally consistent for this fixture: the original encrypted suffix allocations validate only after decoding at their inherited `offset - 0x1B000`; the model relocates the outer entries by `0x29000` and re-encodes them at the destination offsets. Independent source/destination decryptions and CRCs agree.
- [verified] Protected decoded SPL/config/CFG tool/CFG/key descriptor remain byte-identical. The exact decoded opaque 968-byte suffix is preserved. Plain `ota.bin`, `info.log` (empty), and `tail.bin` remain unchanged; trailer placement remains at the output logical end.
- [verified] The FWSC identity marker remains `FM-1_092`. The decoded `script.ver` record remains `AC791N-v0.01-cfg_tool-v0.10`. The model does not choose a new firmware identity/version.
- [reported, not confirmed for this proposed container] Repository `docs/03-update-protocol.md` §3 says the update no-op gate is a same-version refusal based on Baud Girl observations; it also says the device’s exact version-vs-file-list comparison is unknown. It records a prior stock-path install of a V15-derived package changed to FM-1_016, but that does not establish acceptance of this enlarged 092 container or of any new chosen version on the owner’s current unit. Because the current unit is recorded as FM-1_092 and this model preserves that identity, a same-version refusal is a material risk. Do not call the model installable or infer that changing the marker alone is sufficient. A future package needs a reviewed new identity/version contract and positive updater/loader validation; the model currently rejects identities other than 092.
- [not established] Upstream unpacker acceptance proves the file is structurally decodable by that host tool, not that the stock OTA loader accepts a 978,484-byte container, the shifted outer entries, D7000 inner extent, or the rewritten address-dependent ciphertext. Upstream unpacker itself prints a warning rather than rejecting an outer data-CRC mismatch, so the separate strict CRC check above is important.
- [not established] This does not prove device flash size/ownership, SFC/XIP behavior for the moved bytes, install/recovery safety, migration, or musical/device acceptance. There was no device access, package emission, transport, download, or deployment.

## Pointers

- Model: `tools/jieli/model_092_app_replacement.py` — `_logical`, `_physical`, `_outer_parse`, `_flash_parse`, `_build`, `verify_modeled`, `model`.
- Existing checks: `tests/test_model_092_app_replacement.py`.
- Model author’s scope/limits: `notes/2026-10-14-092-package-model.md`.
- Project OTA evidence and limits: `docs/03-update-protocol.md` §3 and `notes/2026-10-09-offline-app-replacement.md`.
- Upstream decoder source: <https://github.com/kagaimiq/jl-misctools/blob/0a5b12db0ef38f3042acffbe2452730a37fd2405/firmware/fwunpack_newfw.py>.
- Upstream OTA client/source overview: <https://github.com/AL-255/FM-1-RE/blob/main/tools/fm1_ota.py>. The project’s local update-protocol record remains the source for the specific same-version report; no live updater behavior was tested here.

## Tool coverage and handoff

Rarefaction and Serena select the shared Mac primary checkout rather than this Hera isolated worktree. I did not retarget their global state. This review used direct source inspection, the upstream pinned decoder, and the focused model tests.

Next bounded dependency: define and validate the output identity/version contract and establish stock updater/loader size and relocation acceptance separately before any package builder or install route is considered. No implementation change is recommended to this narrowly pinned offline model based on the checks performed.
