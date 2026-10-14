# Fixed-entry first-sector contract against the stock SPL

## Finding

The fixed-entry idea is compatible with the observed SPL entry mechanics, but it is not an existing Dinghy feature or an established package contract. Three separate conditions must be solved before calling it a recovery design:

1. Keep the first physical app sector [0x4000, 0x5000) fixed across body revisions, despite the current image builder recalculating nested length and payload-CRC fields there.
2. Ensure immutable entry code can validate the mutable body and invoke an independent rescue path without entering mutable C/runtime code first.
3. Define and test how that rescue code and mutable-body integrity metadata are provisioned and recovered. The stock SPL does not checksum the app body and does not invoke its trailer rescue scan when ordinary app headers pass.

This is architectural feasibility, not proof of a functional rescue loader, installer, frozen vendor package, or device behavior.

## Exact SPL behavior

The examined stock SPL is the retained decoded binary spl-decoded.bin, 14,384 bytes, SHA-256 730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef; vendor-tool disassembly is /tmp/lunar-spl-record-byte-review/spl.lst, SHA-256 bc930edc43ab535ec0fcd4a6163a549bdcd13fbfe4864d24a917ddc6922b2dee. This matches the recorded SPL identity used by the project guard; it is retained evidence, not a new device read.

At disassembly 0x2d3e and 0x2d72, SPL calls helper 0x1320 for ordinary header selection. Success sets r13=0 at 0x2d7e. The branch at 0x2e08 sends r13==0 directly to 0x2f78, bypassing the trailer rescue-record scan beginning at 0x2e0c. The successful path later loads the selected entry and calls it at 0x3294..0x329c, with r0=0x01c7fe08 immediately before the call at 0x3298.

The helper validates 32-byte directory records: it calculates CRC16 over bytes +2..+31 and compares with the stored word at +0, then checks record fields. In app-area selection, SPL uses the selected XIP entry; this path has no body checksum. A valid ordinary header can therefore direct SPL into a partial or corrupt app body without falling back to the trailer rescue scan. Header invalidation or torn-program behavior is not assumed; separate NOR research has not established atomicity.

The stock entry ABI has a first-instruction constraint. Maintained Dinghy CRT comments and code say SPL jumps to XIP 0x02000120 with r0 pointing at 0x01C7FE08, and expects goto +4; rts as the first instruction pair. Dinghy crt0.S then reads core state, disables interrupts, installs _ustack_top and _sstack_top, calls fm1_cstart, and loops. An immutable first-sector stub could run before normal C startup if it preserves this contract, but normal Dinghy startup does not offer a pre-C rescue dispatch.

## Actual package metadata is not frozen

The strict raw package builder treats descriptors as checksummed metadata. tools/jieli/build_raw_diagnostic.py::_replace_application writes app payload CRC and size at decoded offsets 0x4022 and 0x4028, recomputes the app directory-record CRC at 0x4020, recomputes app-area payload CRC at 0x4002, and recomputes the app-area header CRC at 0x4000. Replacing the app therefore changes first-sector fields even though SPL's entry selection does not validate the body payload CRC.

Retained offline raw images confirm this:

| Retained image | Raw image SHA-256 | Selected app length | App payload CRC | Area payload CRC |
| --- | --- | ---: | ---: | ---: |
| expanded-private-geometry-v1/stockA.bin (identical stockB.bin) | 96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4 | 691,744 | 0x36ee | 0x184f |
| Historical expanded-private-geometry-v1/target.bin | 400fcbcc883af0a6fdbb60e17759ae8a0778f16adb9490519b9935d11a32d907 | 838,712 | 0x86f2 | 0x81b3 |

Both point to app relative 0x120 (XIP 0x02000120); the area record points there and carries its enclosing size. Raw first-sector SHA-256 differs: stock 4e323f5e322e1b671be1b526ff6277418b56c2ee1585a806ebbe9f5505ae6a19, historical candidate 564cbc244c37daba13ae8a3a1d9fed30e5c02693dd3c10fdb89e8425d264625c. These artifacts are old retained candidates, not current admission evidence.

The outer app_dir_head is a fixed sentinel in the retained profile (length=0xffffffff, stored CRC=0xffff), but this does not freeze selected app_area_head or child app.bin metadata. A custom fixed-prefix format could reserve constant padded app/area lengths, keep descriptors fixed, and put a versioned/hash-checked manifest in mutable storage. However, frozen payload CRCs would not satisfy the current strict package parser/builder semantics. Implementation must define a distinct bounded format or prove every relevant stock/package consumer ignores those fields. No compatibility proof was found. If standard package CRCs remain truthful, the first sector changes with the body and is not immutable.

App bytes start at raw 0x4120 (0x4000 + 0x120), XIP 0x02000120. Freezing physical sector [0x4000,0x5000) fixes the first 0xee0 app bytes; mutable app begins at raw 0x5000, XIP 0x02001000. This is geometry, not a reserved/write grant.

## Dinghy does not provide pre-runtime rescue

The checkout pins unmodified Dinghy platform code from [zvenson/dinghy](https://github.com/zvenson/dinghy) at d44df7db09b98ccad2f1233b8f83f5f09c04829e, GPL-3.0-only (firmware/third_party/dinghy/UPSTREAM.md). Its OTA/update and USB recovery code lives in the ordinary application and reaches normal app code; crt0.S enters C startup. It cannot be reused as-is from an immutable entry before mutable C code.

The SPL trailer rescue scan is conditional on ordinary header selection failing. It is not a callable Dinghy API and is skipped when ordinary headers pass, even if the body is partial. Retained notes say the staged loader source is not vendored. A fixed-entry rescue design needs a concrete, independently validated recovery execution mechanism and ABI; branching to fm1_cstart, the updater, or an untracked loader is not proof.

## Decision and next proof gate

Do not treat this as implementation-ready. The narrow design question is whether an explicitly custom fixed descriptor can coexist safely with all normal validators/consumers:

- Fix app and enclosing-area lengths using bounded padding; make the immutable descriptor sector identical across releases.
- Put version, exact mutable-body length, and integrity data in a bounded mutable manifest that the immutable stub validates before transfer of control.
- Prove no stock updater/package path requires the frozen descriptor payload CRCs; otherwise the layout conflicts with existing format behavior.
- Separately implement or identify a maintained recovery target executable before mutable C startup; prove its load, entry, stack, and IRQ assumptions from target source and link output.
- Test two target-built bodies with identical first sectors and different body hashes, then corruption, truncation, and manifest-bound rejection. Keep this as offline evidence until package producer, SPL interaction, and recovery route are independently accepted.

The SPL app-entry address is observed. The blockers are the unproven intersection of fixed descriptors versus strict nested-CRC semantics, and a real pre-C recovery execution path. Initial-migration recovery and physical flash semantics remain separate acceptance gates.

## Evidence limits

- No device, USB, MIDI, reset, flash, or power operation occurred.
- Raw image artifacts are retained historical captures/candidates, not fresh backups or physical-layout authorization.
- SPL behavior is inferred from the retained binary and vendor objdump listing; no substitute disassembler was used.
- No stock updater tolerance for frozen CRCs, first-sector immutability, rescue invocation, power-cut property, target code fit, or physical acceptance is established.
- Dinghy is GPL-3.0-only; its loader source and package tools are explicitly excluded per UPSTREAM.md.
