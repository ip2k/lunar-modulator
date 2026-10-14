# Offline FM-1_092 expanded app-container model

This is a strict, offline model for replacing the FM-1_092 app while moving the end of the packaged inner flash image to the D7000 stage boundary. It is not a package writer or installable image. The model emits only a JSON report; it writes no FWSC binary and does not run device or transport commands. Hardware admission, installability, and recovery remain false.

## Inputs and reproducibility

- Public FM-1_092 FWSC input: `scratch/092-package-model/FM-1_092.fwsc`, 810,548 bytes, SHA-256 `ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80`.
- Its unpacked public reference tree: `scratch/092-package-model/FM-1_092.fwsc_unpack`. Protected decoded references include `top/uboot.boot`, `top/isd_config.ini`, `files/cfg_tool.bin`, and `files/cfg`.
- Target linked app: `/home/claude/mvave-fm1/shapes8-target-fit-20261014/link/artifact/app.bin`, 845,036 bytes, SHA-256 `5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573`. This is a retained public build artifact; using it here is a model assumption, not permission or evidence for a physical relocation.
- Run from the repository root:

  ```sh
  python3 tools/jieli/model_092_app_replacement.py \
    scratch/092-package-model/FM-1_092.fwsc \
    --reference-dir scratch/092-package-model/FM-1_092.fwsc_unpack \
    --app /home/claude/mvave-fm1/shapes8-target-fit-20261014/link/artifact/app.bin \
    --json /tmp/model-092-report.json
  ```

The report from this run identifies its modeled output hash as `cfb7c149154bbd9243581d728a78a0605966aaf0536edd0c2633ac92fbe90e8b`, with a modeled outer size of 978,484 bytes. The modeled byte sequence exists only in memory and is not saved.

## What the model checks

The helper accepts only the pinned source FWSC and target app hashes, the FM-1_092 identity, exact outer entry order/types, and the pinned 092 unpacked reference. It independently decodes and verifies outer FWSC header/list/payload CRCs, the nested flash records and CRCs, stock SPL bytes/hash, `isd_config.ini`, CFG tool, CFG resource and key descriptor. It builds a new flash payload in memory, relocates app/tool/CFG while preserving the original decoded 968-byte opaque tail, fills the remaining gap to D7000 with decoded `0xFF`, re-encodes the nested SFC region and rechecks its records. Outer entries after `flash.bin` are shifted by 167,936 bytes and their stored entry offsets, size/list/header checksums are updated.

The original 092 suffix ciphertext is inherited from the V15 offset layout. On the source package, attempting to decode those encrypted suffix records at their 092 offsets fails their payload CRCs; decoding at `offset - 0x1B000` validates them. The model therefore decodes at that pinned legacy offset, then re-encodes the same decoded allocation at each shifted destination offset. For `USR`, `isd_config.ini`, `script.ver`, and `blimit.bin`, output ciphertext SHA-256 differs from the input while decoded allocation bytes remain identical. This proves logical payload preservation under the implemented transform; it does not prove hardware behavior or physical ciphertext identity. `info.log`, `ota.bin`, and `tail.bin` stay byte-identical because they are raw outer entries.

## Measured bounds

The decoded inner flash grows from 712,704 bytes (`0xAE000`) to 880,640 bytes (`0xD7000`), a 167,936-byte insertion. With app image origin `0x4120`, 383-byte CFG tool, 2,937-byte CFG resource record including its header, and the exact 968-byte decoded tail preserved, the strict candidate-app maximum is 859,680 bytes. The 845,036-byte candidate leaves 14,644 bytes before the D7000 boundary. The model places the candidate app end at `0xD260C`, CFG end at `0xD3304`, and the end of the retained tail at `0xD36CC`; remaining fill to D7000 is decoded `0xFF`.

Protected decoded SHA-256 values checked by the run:

| Component | SHA-256 |
| --- | --- |
| `uboot.boot` | `730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef` |
| `isd_config.ini` | `0952afd96f533dd0fba72a8fab9cb4a4336f55424a1a89eecb13ff8a51a0eff0` |
| `cfg_tool.bin` | `276579954f076886a6a7694f65dc71c034a63a2c204b76749065c0ac7b010d1b` |
| `cfg` | `962b3cbe3520502cf9ccd6a475b60e366b762ead371f0975a386c09c46201766` |
| key/MAC descriptor | `c91c86f43cbb8cc58225297f4871d983d7aeba01dd66151979b656562115c078` |

## Validation and limits

`tests/test_model_092_app_replacement.py` passed 4/4 on Hera using the mounted pytest dependency environment. It checks exact original physical FWSC prefix-marker round-trip, legacy-offset handling, successful target model/integrity and false admission flags, destination ciphertext relocation, over-bound and wrong candidate rejection, source hash pinning, and corruption rejection. Retained corpus tests skip when these ignored public build/unpack inputs are unavailable elsewhere.

The strict max is specific to this exact 092 nested layout and preserved tail. The result does not validate whether the stock updater accepts a larger FWSC container, whether all outer metadata/version conventions are accepted, whether shifted payloads are physically supported by the loader, whether the D7000 extent is available on device, or whether a recovery transaction is safe. The opaque tail is preserved as decoded bytes from the public fixture, but the implementation necessarily changes SFC ciphertext when relocating its containing region. Owner-specific raw backups, private identifiers/secrets, and device reads/writes are not used.

Rarefaction/Serena roots were unavailable for the Hera isolated checkout and were not retargeted because those MCP selections are shared; verification used direct source and caller/test inspection. No target build, physical package, installation or hardware test was performed in this task.

The next dependency is independent review of the model's exact 092 outer metadata semantics and a separately authorized offline proof that the stock loader can consume the modeled relocated extents. Do not turn this in-memory model into a package or installation path until those gates pass.
