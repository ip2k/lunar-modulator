# Exact WL82 LoaderV2 reset command (2026-10-11)

Offline review, with no hardware traffic. This corrects the FC0C description in [the earlier loader audit](2026-10-05-softkey-efuse.md): for the pinned WL82 loader, “run app” **requests a core soft reset**, rather than jumping to an app address [verified]. It does not establish that stock firmware or USB will resume.

The reviewed encrypted `wl82loader.bin` is 24,064 bytes, SHA256 `d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376`. Independent per-512-byte decoding gives SHA256 `db8676b9cca4e2c0dfee062715cdb41528a2a8ccc827520ba8c194e4a2e0356e`. JieLi toolchain `20250324.1` disassembled a linked image at 0x01C02000 on Hera; every displayed instruction/data byte was checked against the complete decoded file (24,064 bytes, zero mismatches) [verified]. Vendor binaries and the detailed listing remain private and ignored. Disassembled data is not evidence of executable behavior.

## Command behavior

FC0C is a **LoaderV2 command**, not a documented mask-ROM UBOOT1 command. Kagaimiq’s [protocol description](https://github.com/kagaimiq/jl-uboot-tool/blob/main/docs/usb-loader-v2.md#run-app) and pinned tool source `adb3f18889e88ac512ce0a3c4d8cc3d3cb30696a` distinguish them [verified]. Its fixed argument-1 CDB is `fc0c00000001ffffffffffffffffffff`; this records the protocol, not a hardware execution instruction.

The FC table at 0x01C042C6 has index3 bytes `5B 02` at 0x01C042CC, selecting handler 0x01C0477C. Fresh loader entry clears context 0x01C09700+16; with no later FC16 configuration command, this flag bypasses an optional indirect callback at configuration +28 [verified]. If enabled, that callback has effects outside the narrow default path and a nonzero result aborts reset.

The default handler performs these writes, in order [verified]:

| Address | Register (primary SDK) | Operation |
| --- | --- | --- |
| 0x00051000 | `JL_USB_IO->CON0` | OR 0x200 |
| 0x00011800 | `JL_USB->CON0` | Write 1 |
| 0x00051000 | `JL_USB_IO->CON0` | OR 0x800, then AND 0xFFFFFFFB, then AND 0xFFFFFFFE |
| 0x00010000 | `JL_POWER->CON` / `JL_CLOCK->PWR_CON` | OR 0x10, then spin |

The final call is 0x01C047E8 → 0x01C04B6E → 0x01C0292C. At 0x01C0292C bytes `60 E0 80 0B` load 0x10000; `00 EF 10 00` at 0x01C02930 ORs bit4; `F7 9F` at 0x01C02934 spins [verified]. SDK `WL82.h` identifies the registers; `cpu/wl82/tools/jtag/dbg.config` explicitly names this address as soft-reset control and bit4 as the reset bit [verified]. USB bit meanings were not established; the writes do not prove USB detach/reattach. Stock soft-key recovery uses **P33 reset**, a different reset domain.

Arguments below 100 (decimal) normalize to zero for the delay helper, so argument1 skips its explicit loop. A logging call still uses UART polling, and external transport code is not intrinsically time bounded [verified]. A host timeout/disconnect alone is not a reset or stock-boot witness. The loader idle timer also reaches the same core-reset routine.

## Whole-loader initialization remains a separate gate

The exact 47-block image ends at 0x01C07DFF. Its initializer scans CRC-bearing configuration candidates at 0x01C07E00 and 0x01C08E00 (each repeated in a four-slot loop), then deciphers the selected candidate’s first 1,024 bytes. These windows end at 0x01C081FF and 0x01C091FF; neither is uploaded with the image nor cleared by entry’s BSS wipe at 0x01C09600 [verified]. With no valid header it still uses 0x01C07E00. Thus an invalid header alone does not prove the default configuration: parsing still examines that memory.

The `spi` field parser can select quad mode. No matching field takes the default state OR 0x10300 at 0x01C026E0, giving mode2 (dual) [verified]. The NOR initializer is 0x01C04E3C → 0x01C03ACA. It configures peripherals and sends flash resume opcode 0xAB, JEDEC-read opcode 0x9F and a 16-byte opcode0x4B read with four zero/dummy bytes [verified emitted bytes; inferred unique-ID meaning for 0x4B]. It does not merely write RAM.

Mode2 branches at 0x01C03B60 to 0x01C03C8C and bypasses quad status changes. Mode4 reads status0x05/0x35 and, if the required status bit is clear, calls WREN (0x06) at 0x01C03BCC, writes status with opcode0x01 at 0x01C03BD6, and can fall back to opcode0x31 at 0x01C03C28 [verified]. These are flash-status writes even without a host erase/program command. Exact loader SHA, matching backups and previous default-path success do not independently establish the current post-image RAM contents.

The initializer also calls external address 0x01E00428 and ROM-supplied operation pointers. Their full implementations are outside this binary and were not decoded here [verified edges, unknown effects]. The direct default FC0C path does not reach eFuse or flash-program handlers [verified]; this must not be inflated to complete semantic coverage of loader entry or arbitrary commands.

## Mailbox and practical recovery limits

Stock writes `usb_update_mode\0` to 0x01C7FD80 before its P33 reset [verified in the earlier stock trace]. The traced FC0C body does not clear it. No exact ROM consumer/clear implementation is available; mailbox retention/consumption across a core reset and the resulting boot path remain unknown. Absence of a literal mailbox address/string from this loader is not proof against writes by external code.

FM-1-transporter reported that V15 after a warm reset runs without USB attachment until a cold power-on [reported; earlier audit links the source]. This review does not supersede that warning with a USB restoration guarantee. The previous 700-byte RAM probe disconnected and re-enumerated as ROM; it did not prove execution of its reset or mailbox code [verified receipt]. A real owner power cycle remains the established physical recovery route.

There is no independently verified bare-ROM reboot opcode in this review. Clearing the mailbox through ROM memory-write and running a reset routine would be a separate exact-image experiment, requiring independent review and an execution witness. ROM memory-read is also not strictly no-write on WL82: its transfer cipher temporarily modifies RAM [reported protocol, verified tool implementation]; it must not be aimed at SFRs casually. Jumping straight to stock XIP bypasses the SPL handoff contract.

Before any loader-upload/reset campaign is called no-flash-write, resolve both candidate windows and the resulting initialization branch. A new memory-clearing step changes the campaign and needs its own guard/review. Use a dedicated fixed-sequence command guard; retain existing backup/read allowlists, prohibit FC16/FC12/A1 and arbitrary commands, bind the exact ROM port/device, permit no retry, preserve a private receipt and observe host enumeration within a fixed bound. These are proposal gates, not a claim that a physical reset was attempted or succeeded.

Credit: kagaimiq (Andrey Grigoryev), JieLi’s AC79 SDK. No third-party code or vendor binary was added. Detailed independent findings and hash receipt are saved privately under ignored `build/loader-run-app-review.md` and `build/loader-run-app-evidence/hashes.json`.
