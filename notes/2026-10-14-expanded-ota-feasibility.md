# Expanded stock-OTA feasibility and write-bound evidence

Date: 2026-10-14
Scope: offline review of existing package evidence, the preserved stock V15 FWSC/OTA path, and established open loaders/installers. No package was emitted; no device, USB, MIDI, flash, power, or reboot operation occurred. This note claims neither installation nor recovery for the current Lunar candidate.

## Finding

The often-repeated `0x93000` app ceiling is **not a proven hard bound of the proprietary M-VAVE stock OTA loader**. It is the exact V15 profile accepted by Lunar's current inspection/model tools and the write limit of the maintained Felucca/SLOOP (Dinghy-derived) loader. A stronger counterexample exists for stock OTA: the FM-1_092/FM1+VA package kept the stock head, `ota.bin`, and `cfg`, grew the `flash.bin` component by 110,592 bytes, appended 110,180 bytes to `app.bin`, moved `PRCT` from `[0, 0x93000)` to `[0, 0xD9000)`, and moved `VM` to `0xD9000`. The project records that this package was installed through the stock update path and the owner's unit subsequently identified and ran as FM-1_092. This demonstrates that the stock path handled that particular larger package/layout; it falsifies a universal stock-loader write cutoff at `0x93000`.

It does **not** establish the proprietary loader's maximum address, its behavior for arbitrary lengths, or acceptance of Lunar's current candidate. The FM-1_092 app is 691,744 bytes; the current 845,036-byte D7000 candidate is 153,292 bytes larger. Its size/address, full directory and auxiliary record placement, integrity values, image identity, and transaction behavior still need an exact package contract and validation. Neither a variable-length outer container nor the 092 counterexample alone proves this candidate will install.

## Evidence and boundaries

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §3–4; `docs/03-update-protocol.md` update history; package diff inputs summarized there | [verified in repository record] The 092 package has 810,548 bytes vs V15's 699,956; only its `flash.bin` component grew. `app.bin` grew 581,564→691,744; `VM` moved 0x93000→0xD9000 and `PRCT` covers `[0,0xD9000)`. Head, stock `ota.bin`, `isd_config.ini`, and `cfg` are byte-identical. The package was installed through the stock path and the device ran/identified as 092. | No direct post-install full-flash readback is cited here. The evidence does not identify the loader's general maximum, prove every byte at the upper boundary was written, or cover an 845,036-byte app. |
| `tools/jieli/inspect_stock_flash.py` and `tools/jieli/model_app_replacement.py` on this branch | [verified source behavior] The stock-only parser accepts the known V15 `flash.bin` size `0x93000`, V15 reserved descriptors, and V15 identity. The replacement model refuses apps larger than the original 581,564-byte entry and preserves the V15 allocation. | These are explicitly V15-only host tools, not source/disassembly of the proprietary OTA loader and not general limits of FWSC/UFW or stock firmware. Their rejection is a tooling/profile gate. |
| Dinghy pinned `ldr_core.c` and its packer; Felucca/SLOOP packers | [verified upstream source] These open loader/packer combinations set an end-exclusive app write bound of `0x93000`, model a `0x93000` flash payload / `0x8DFBC` app slot, and do not extend writes just because a longer transfer is received. | The code is not the proprietary M-VAVE `ota.bin`. Do not attribute its constant to the stock loader. |
| SLOOP browser installer source | [verified upstream source] Its WebMIDI UI explicitly refuses foreign-firmware OTA mode because another loader may lay out the image differently. It is a useful transport example for SLOOP's own firmware, not a Lunar-on-stock loader adapter. | It is not a reusable, validated browser path for stock M-VAVE OTA. |
| Groove OS firmware manual | [reported by its vendor] Its browser updater has an app-mediated second-area step for content the stock OTA loader does not write. | This is another product's design and gives no M-VAVE write bound or drop-in Lunar transport. |

Primary/public source links:

- [SLOOP pinned packer](https://github.com/isod89/sloop-fm1/blob/d315ad88c5fbaad232ce9426b06db66395bd87db/tools/fm1pkg_make.py)
- [SLOOP browser installer](https://github.com/isod89/sloop-fm1/blob/main/docs/webapp/installer/index.html)
- [Felucca pinned packer](https://github.com/hugelton/Felucca/blob/1727537624390cc3f9c7dff2456b43b3a8edb005/tools/fm1pkg_make.py)
- [Dinghy pinned loader core](https://github.com/zvenson/dinghy/blob/d44df7db09b98ccad2f1233b8f83f5f09c04829e/firmware/loader/ldr_core.c)
- [Groove OS firmware/update manual](https://www.groove-os.com/manual/firmware)

## Format, loader, and transport are separate questions

1. **Container format.** The outer FWSC/UFW uses entry records with payload lengths and checksums. The 092 package comparison shows the `flash.bin` payload can grow while other entries remain unchanged. This is evidence of a variable-length container instance, not permission to change the inner flash map or an assertion that the updater accepts every length.
2. **Inner layout.** JLFS directory entries and their CRCs describe app and reserved regions. The 092 package demonstrates that its stock-path verifier did not reject that package merely because `VM`/`PRCT` differed from V15. `isd_config.ini`/chip-key material is not an allocation knob and remains byte-preserved by policy. Do not alter it to “make room.”
3. **Loader behavior.** The exact M-VAVE loader is opaque. The strongest grounded stock-path claim is the successful 092 case above. The largest documented M-VAVE app boundary here is `0xD9000` (exclusive PRCT end), not a proved upper limit. The exact 092 loader's acceptance of a larger `flash.bin` is established only for that package and transaction.
4. **Web transport.** WebMIDI is a transport mechanism, not a flash-layout guarantee. The SLOOP installer guards against using its own writer through a foreign loader. Existing Lunar stock-OTA tools cannot represent 092 yet; current expanded raw-image/transport-manifest tools are a distinct host SCSI/recovery path and do not form an OTA package.

## Candidate routes

| Route | Assessment for 845,036-byte D7000 candidate |
|---|---|
| Pretend the V15 0x93000 packer/model applies; add a size override | Reject. It would only bypass an inspected V15 parser/slot gate without establishing inner directory integrity, loader extent, or rollback. |
| Reuse SLOOP/Felucca WebMIDI page/loader unchanged | Reject. Their own source fixes writes at 0x93000, packages substitute their own boot/config components, and SLOOP refuses foreign loader mode. This conflicts with Lunar's preserved-stock-component policy. |
| Create a strict 092-derived stock-OTA package/profile | **Best next offline investigation, not yet an installable path.** Preserve exact stock SPL, `ota.bin`, `isd_config.ini`, `cfg`, and key bytes; encode only a profile-bounded new `flash.bin`/directory/app; independently validate UFW CRCs, header/entry sizes, SFC/JLFS CRCs, file offsets, preserved ranges, app and metadata end, and exact firmware identity. Use an explicit 092-expanded profile rather than arbitrary `--size`/identity flags. First positive fixture should reproduce/verify 092 from its documented package inputs, then use synthetic target app bytes around 691,744 and 845,036 to test format construction and refusal boundaries offline. This proves format/model invariants only. A separately reviewed loader acceptance/rollback gate remains before a package can be admitted or sent. |
| Existing D7000 rescue-loader/raw-image design | Separate route. It may support an expanded image through a new reviewed loader but it requires owned stage space, settings preservation/migration, boot-selection recovery, and transport proof. The 6,954-byte stage-size result is only geometry; D7000 currently overlaps app/tool/config metadata for the 862,296-byte candidate described in `notes/2026-10-14-expanded-rescue-loader-fit.md`. Do not treat it as a stock OTA result or general fit proof for the 845,036-byte profile. |
| App writes additional content after a compact OTA install | Not a route to install this full XIP app by itself. Groove OS documents this architecture for another product; Lunar would need a bootable compact installer app, a separate validated writer, and a different staging/recovery contract. It is not an immediate substitute. |

## Recommendation and next dependency

Correct the project's claims that equate Dinghy/Felucca/SLOOP's `0x93000` writer bound with the proprietary M-VAVE stock loader. Keep the narrow facts:

- V15 inspection/model tools enforce a 0x93000 payload and original 581,564-byte app slot.
- Open Dinghy/Felucca/SLOOP loaders write only `[0x4000,0x93000)`.
- The stock path demonstrably installed one FM-1_092 package whose app/PRCT reached `0xD9000`, but its general maximum and acceptance of Lunar's larger candidate are unknown.

The smallest useful coding step is an **offline, explicit 092-expanded FWSC model** that parses/constructs the real variable-length entries and validates the exact protected component and inner-map invariants above. It must never emit “installable” or relax the existing package guard. Before attempting any loader or hardware campaign, compare that output against the real proprietary loader's accepted layout/extent using a separately authorized, recoverable validation plan. The current package path has no such demonstrated transaction for Lunar; the existing raw-image route remains the more directly specified candidate, but also retains unresolved stage, migration, and recovery gates.

No exact stock-loader source, complete stock-loader disassembly, post-write raw readback for the 092 install, or loader write-end measurement was located in this bounded review. Do not infer a hard ceiling from the open loader, a stock V15 image size, a host parser refusal, or a partition boundary alone.

