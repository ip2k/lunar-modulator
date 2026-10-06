# The soft key and the SDK's key and eFuse checks (2026-10-05)

Desk-only investigation, prompted by the owner's 2026-10-05 decisions:
- explore dongle-less recovery through the stock "soft key" SysEx `F0 22 24 35 7D F7`;
- upgrade the JieLi SDK to the latest release, once we know whether its eFuse checks run and what can blow a fuse.

**Nothing was sent to any FM-1 or dev board.** Vendor binaries were disassembled with JieLi's own `objdump`, in containers on the LAN build host. They come from our scratch copies of V13, V14, V15, FM-1_092 and the SDK releases, and none is committed. The hardware test plan is a separate draft for the owner to review: [notes/2026-10-05-softkey-readonly-test-plan.md](2026-10-05-softkey-readonly-test-plan.md).

A synthesis step that was meant to write this note was stopped by an automated safety check. This note was assembled in the main session from the two investigation lanes' returned findings. Anything about *programming* eFuses is kept to the commands a host tool must refuse.

## 1. Short answers

**Soft key.**
- In stock V15 and in FM-1_092 (byte-identical paths), the message only writes the marker string `usb_update_mode` to RAM `0x01C7FD80` and resets the chip through P33. No flash, VM or `UPDATA_PARM` write happens [verified: disassembly].
- After the reset, the mask ROM's UBOOT mode offers memory read, memory write and jump. It waits until the host acts or the power is cycled [reported: FM-1-transporter, kagaimiq].
- A dump needs the JieLi download loader uploaded to RAM and run, and then only read commands.

**Are the eFuse checks exercised, and what blows a fuse?**
- The SDK's key check (`sdk_meky_check`, which runs `_mkey_check` 8 s after boot) is present in every SDK release from V1.1.9 to V1.2.13 and in every stock FM-1 image (V13, V14, V15, FM-1_092) [verified].
- It does nothing on the FM-1, because no library, SDK source or stock app ever registers the licence blob it compares against [verified].
- The application never touches the eFuse controller [verified].
- **Nothing on the device writes eFuses:** not the app libraries, the SPL or the OTA loaders [verified].
- The only eFuse-programming code is in JieLi's USB download loader (`wl82loader.bin`), reached from PC tools through mask-ROM download mode by explicit key-burning commands. Programming only turns 1 bits into 0 bits and cannot be undone [verified: loader logic].
- **Recommendation:** upgrade to the V1.2.13 libraries, with the safeguards in §4. The upgrade adds no new key or eFuse risk over V1.1.9.

## 2. The soft key [desk findings]

Desk-only work: nothing was sent to any FM-1 or dev board, and the repo was not edited. Everything was disassembled with the vendor objdump in containers on aeon labelled project=lunar-modulator session=softkey-efuse. 
Main results:
(1) In stock V15, the soft key is handled inside the USB-MIDI receive callback. It runs only when a single 8-byte bulk OUT packet equals 04 F0 22 24 07 35 7D F7. It then calls a RAM function at 0x01C026A4, which:
  - turns interrupts off and takes the CPU lock;
  - copies the 16-byte string "usb_update_mode\0" to RAM 0x01C7FD80;
  - sets bit 4 of P3_PR_PWR through the P33 interface (a chip reset) and spins.
  No flash, VM or UPDATA_PARM write happens. 7F (the upgrade command) is handled by the same check.
(2) In FM-1_092 this whole path is byte-identical to V15.
(3) What the mask ROM does in UBOOT is known only from others' reports (FM-1-transporter, kagaimiq): it offers memory read, memory write and jump only, and waits forever. If the host drops the device, it resets and boots flash. A power cycle exits.
(4) Only loader commands FD05, FC0A and FC14 are read-only, but uploading the loader is a RAM write and runs JieLi's code. The loader's flash init can write the flash status register in quad mode.
(5) A read-only test plan for the owner's unit is given below, with the questions the owner must decide first.

Correction to existing notes: AL-255's "mask-ROM 0xFFC0xxxx" call targets come from disassembling at base 0. app.bin is loaded at 0x02000120, so all of those targets are RAM addresses 0x01C0xxxx. This affects AL-255's docs, FM-1-transporter's docs and the memory-map line in our CLAUDE.md.

- app.bin file offset 0 is VA 0x02000120, not 0x02000000. AL-255's listing used base 0 and added 0x02000000 to the left-hand addresses only. [[verified]] — Four checks agree:
- jlfw.yaml entry-point is 33554720 = 0x02000120.
- In decrypted.bin, app.bin starts verbatim at flash 0x4120, and XIP 0x02000000 is flash 0x4000.
- The C runtime copies 0xA05C bytes from 0x02084060 (file 0x83F40) to RAM 0x01C00000. At base 0x02000120, the soft-key code's absolute pointer 0x01C0800D lands on file 0x8BF4D, which holds 04 F0 22 24 07 35 7D F7.
- The string pointer 0x020550AA lands on file 0x54F8A, which holds "usb_update_mode".
This offset also explains AL-255's '0x120 anomaly' in its rodata tables (docs/io/05-midi.md §3.3).
- Every 'mask-ROM 0xFFC0xxxx' call in AL-255's docs is really a call into app RAM at 0x01C0xxxx (+0x120). The soft key does not call the mask ROM directly. [[verified] targets and call counts; [inferred] the explanation of the transporter crash] — Disassembled at VMA 0x02000120, V15's calls go 11,612 to flash, 334 to RAM 0x01Cxxxxx and none to 0xFFC0xxxx.
AL-255's labels map as follows:
- 0xFFC02532 → RAM 0x01C02652 in V13 (the soft-key function).
- 0xFFC00F6C ('P33_CON_SET', fatal sink) → 0x01C0108C, a P33 read-modify-write helper using P33_CON 0x13E08.
- 0xFFC00F2E → 0x01C0104E, the P33 write helper.
The last one explains FM-1-transporter's note that 'ROM P33 helper 0xFFC00F2E crashes inside UBOOT': that code is not in ROM. CLAUDE.md's memory-map entry 'mask ROM 0xFFC0xxxx' inherits the same mistake. The real WL82 ROM address is still unknown.
- The V15 soft-key check, with its exact conditions. [[verified] vendor objdump, out/v15_app.dis lines ~9151-9175] — Call chain: the USB EP4 OUT callback at 0x02006E1E (registered at 0x02006328) reads up to 64 bytes with usb_ep_read (0x0200683C). It then calls usb_midi_rx_parse at 0x02006A60, its only caller.
At 0x02006A6E the code checks three things:
- the packet length is exactly 8;
- memcmp(buf, RAM 0x01C0800D, 6) == 0, where the magic is 04 F0 22 24 07 35, i.e. CIN 4 + CIN 7 on cable 0;
- buf[7] == 0xF7.
Then it branches on buf[6]:
- 0x7D → call 0x01C026A4, then `goto self`.
- 0x7F → os_taskq_post("midi_route", 1, msg 148), the start of OTA step 1, and normal parsing continues.
- anything else → normal parsing.
The magic and the function are referenced only from here, so BLE and DIN MIDI cannot trigger it. If the host packs the message differently (merged with other events, or split), it silently falls through to the normal parser.
- What the 7D handler does: it writes a RAM mailbox and resets the chip through P33. It touches no flash and does not detach USB. [[verified] code; [reported] effect on hardware (kurogedelic/FM-1-transporter docs/DEVLOG.md, PROTOCOL.md; Felucca firmware/hal/fm1_sys.h)] — V15 RAM function at 0x01C026A4 (out/v15_ram.dis ~3311):
1. `cli`; increments the per-CPU counter [0x01C0971C+cnum*4]; takes the spinlock [0x01C09714] with lockset (the SDK's CPU_CRITICAL_ENTER).
2. Copies 16 bytes with `rep 16`: "usb_update_mode\0" from 0x020550AA to 0x01C7FD80.
3. Calls 0x01C0108C(0xA0, 4, 1, 1): read-modify-write of P33 register 0xA0 (P3_PR_PWR), setting bit 4.
4. Spins.
Nothing between the packet check and the reset touches flash.
This is the same as the SDK's go_mask_usb_updata() in msd_upgrade.c and new_cfg_tool.c (nvram_set_boot_state(2) + reset) and Felucca's fm1_enter_uboot(). The 16 bytes overlap the first 8 bytes of the UPDATA_PARM record at 0x01C7FD88. The SPL (uboot.boot 0x01C04DC4) checks that record with a CRC over 78 bytes from 0x01C7FD8A, so the overlap is ignored there.
The result on hardware, reported by FM-1-transporter (2026-10-01) on stock V15:
- V15 dropped off USB 21 ms after the key.
- It came back 1.0 s later as 4C4A:8057 'WL80UBOOT1.00'.
- SCSI INQUIRY returned WL82 / UBOOT1.00 / 1.00.
- The soft key has existed in every stock release since V13. docs/07 §1 ('no console, CDC, factory mode or recovery chord') needs amending. [[verified]] — Same handler and RAM function in all three:
- V13: call at 0x020064DA → 0x01C02652.
- V14: call at 0x02006732 → 0x01C02638.
- V15: call at 0x02006A96 → 0x01C026A4.
All three write "usb_update_mode" to 0x01C7FD80 and then call the P33 reset.
- FM-1_092 (Baud Girl) carries the soft-key path unchanged, at the same addresses as V15. [[verified] static; [inferred] that it behaves as on V15 (no report of the soft key on 092)] — Byte diff of V15 app.bin against 092 app.bin, over V15's length. These are identical:
- the whole USB driver range, file 0x5000-0x7000, which includes the callback registration and the parser;
- the magic at 0x8BF4D;
- the RAM function at 0x01C026A4 (file 0x865E4);
- the P33 helpers;
- the "usb_update_mode" string.
The vendor objdump shows the same instructions at 0x02006A60-0x02006AAC, and the same single caller at 0x02006E34.
092's 89 patch regions lie elsewhere: UI 0x2018xxx-0x2028xxx, rodata 0x204Dxxx-0x2056xxx, RAM-image trampolines at 0x01C00894-0x01C008E2, the PC-limit at 0x020018E4 raised from 0x02084060 to 0x020D5000, and a task entry at 0x02004AFE. None is on this path.
- Commands next to the soft key: 7F is one bit away from 7D and is a command that can write flash. The online tool's 0x24-0x27 commands do not exist in V15 or 092. [[verified] scans and handler; [reported] step-1 flash write (docs/03, AL-255)] — 0x7F goes through the same check and posts msg 148, which starts OTA step 1. Per docs/03 §5, step 1 loads ota.bin into the loader flash area and writes the UPDATA_PARM boot record.
A byte scan finds no `5A AA A5` preamble in V15 or 092 (AL-255 found none in V13/V14), and there is no CDC interface. The '24' in F0 22 24 35 is only part of the 3-byte magic.
Trap 7's syscmd 33-36 and 48 belong to the separate 00 59 framing.
- The SPL does not act on 'usb_update_mode'. The mask ROM consumes the mailbox. [[verified] SPL code; [inferred] ROM behaviour] — uboot.boot (SHA-256 730e54f0…, identical in V15 and 092) contains the string at 0x01C05720. No code references it; the only branch to that address lands mid-data. The SPL reads only the UPDATA_PARM record at 0x01C7FD88. UBOOT1.00 is the ROM variant (kagaimiq), and after a host drop the ROM boots flash rather than re-entering UBOOT, so something consumes or clears the mailbox.
- What the mask-ROM UBOOT does on its own, and how to leave it. [[reported] FM-1-transporter PROTOCOL.md/DEVLOG.md, kagaimiq jl-uboot-tool docs; [inferred] no autonomous writes] — Reported behaviour:
- UBOOT1.00 offers only FB06 (write memory), FD07 (read memory) and FB08 (jump); it has no flash commands.
- It waits indefinitely while idle.
- If the host drops the device it resets and boots flash, so all work must happen in one session.
- A JUMP target that does not return within ~2-4 s resets the chip.
- After the loader upload, ~3 s without a command resets the chip.
- Stock V15 after a warm reset runs but does not attach USB until a cold power-on.
- Before any host has enumerated the device, a cable swap keeps UBOOT alive (czietz's gist, used on two FM-1s).
- The soft key fails if another full-speed device shares the hub.
- Full dumps of V15 matched before and after sessions, and V15 booted after a one-sector self-test rewrite.
- On WL82, READ_MEMORY ciphers RAM in place for the duration of the transfer.
There is no evidence of autonomous flash writes; the ROM has not been dumped. The slide switch removes power completely (docs/10, verified 2026-09-06).
- The loader's command set, and which commands are read-only. Disassembled from jl-uboot-tool's wl82loader.bin after deciphering it with the documented cipher, loaded at 0x01C02000. [[verified] disassembly (out/ldr.dis); [inferred] that the default (no status-register write) applies when nothing is written after the loader] — The dispatcher is at 0x01C04194:
- FB: 00/01/02 → ioctl 201/200/202 (erase block/sector/chip), 04 write flash, 06 write memory, 08 jump, 0x42 → ioctl 203.
- FC (table at 0x01C042C6): 09 read key, 0A online device (ioctl 100, cached JEDEC ID), 0B read ID, 0C run app (writes SFRs at 0x51000/0x11800, then jumps), 0D rejected, 0E flash CRC, 12 (parses a 3300-5500 range), 13, 14 USB buffer size, 16 (a data-OUT command); also 40-48, 83, 84, 9D, A0, A1.
- FD: 05 read flash, 07 read memory, 0B ID.
FD05 only calls the device read op (ops[1] = 0x01C04E1A), updates a RAM CRC and sends data to the host.
Two cautions:
- FC0A reconfigures the SPI mode if CDB bytes 6-7 are '_' '0', so pad CDBs with 0xFF.
- The norflash init (ops[0] 0x01C04E3C → 0x01C03ACA) issues WREN + 01/31 status-register writes to set the QE bit when its configured mode is quad (4) and QE is clear. That mode comes from a config block at 0x01C07E00, right after the loader; without a block the default is mode 2 (dual), which takes no status-register write.
The write path also toggles write protection ('norflash_write_protect').
- The shortest read-only command sequence for a full dump is known. [[verified] loader dispatch; [reported] CDB layout and timing (FM-1-transporter src/jieli_uboot.c, PROTOCOL.md)] — In one session:
1. ROM FB06 × 47 blocks of 512 B: the already-ciphered loader into 0x01C02000-0x01C07DFF, each block with CRC16-XMODEM as an argument.
2. FB08 to 0x01C02000 with arg 0x0001.
3. FC14 (optional).
4. FC0A, which returns type 3 and ID 0x856014, also used as the ≤1 s keepalive.
5. FD05 over 0..0xFFFFF in 512-4096 B chunks, twice.
The dump path needs no FC09 (read key). FM-1-transporter reports 1 MiB in 3.3-20 s.
- A raw dump cannot be compared with jl-misctools' decrypted.bin. [[verified] code reading; [reported] raw = flash entry; layout [verified] notes/2026-09-29] — fwunpack_newfw.py deciphers the flash image in place with the chip key (jl_sfc_cipher in JLFSIterator) before writing decrypted.bin; that is why app.bin appears in plain text at 0x4120. FM-1-transporter reports that the .fwsc's type-0 flash entry, with only the UFW layer removed, is byte-identical to raw flash.
092 flash layout:
- image 0xAE000 bytes;
- PRCT [0, 0xD9000);
- VM 0xD9000-0xE9000;
- BTIF 0xE9000;
- USR 0xEA000;
- key_mac 0xFF000.
- fm1t.py is not usable as it stands for the owner's unit. [[verified] code read (scratchpad copy at a632d92320)] — - `ensure_uboot` sends the soft key automatically whenever PID C755 is attached, without reading the identity first.
- `write` and the package review import private fm-1-research-lab modules (fm1_ota, fm1fw).
- The firmware's write window [0x4000, 0x93000) is V15's layout; 092's app area runs to 0xD9000.
- The firmware also contains RAM-run commands (memw/jump/ramrun) and sector erase/write.

## 3. The SDK key and eFuse checks [desk findings]

Answers to the owner's two questions.

1. Are the eFuse checks exercised? The application never touches eFuse at all [verified]. What the SDK calls a key check is sdk_meky_check, a late_initcall. It schedules _mkey_check to run 8,000 ms after boot. It is present and runs in:
- every release from V1.1.9 to V1.2.13 [verified: IR of every release];
- every stock FM-1 image: V13 (FM-1_009), V14 (FM-1_014), V15 (FM-1_015) and FM-1_092 [verified: vendor objdump].

The check compares a registered licence blob (JL_KEY_2020, magic 'JKYS') against the 16-bit chip key that the SPL passes in boot_info. On the FM-1 that key is 0x980F. The check only enforces something after code has registered a blob, through sdk_mkey_lock, mkey_check or the soft-IRQ stub added in V1.2.8. Nothing registers one:
- no library in V1.1.9 (126 .a files) or V1.2.13 (157 .a files) does [verified: nm and IR];
- no SDK source does [verified];
- the stock FM-1 apps do not [verified: one reference to the blob pointer, no blob bytes].

So the check returns at the "nothing registered" branch and does nothing. fm1-nes ran V1.2.13 libraries on a V14 unit for well over 8 s without a fault [reported]. That is consistent with this reading [inferred].

2. What blows the fuse? Nothing that ships on the device:
- The SDK app libraries never touch the eFuse controller [verified].
- The SPL (uboot.boot, every release including the 2026 commits) only reads eFuse [verified].
- The OTA loaders do not touch it [verified].

The only eFuse-programming code is JieLi's USB download loader, wl82loader.bin, in every release [verified]. PC tools (isd_download with -key/-mkey, the production burner, jl-uboot-tool's burn-chipkey command) upload it through mask-ROM download mode. It has two burn commands:
- WRITE_KEY 0xFC12: writes the chip key to row 1, bits 8–23;
- a raw 24-bit row write, dispatch value 0xA1.

Programming can only turn 1 bits into 0 bits, so it cannot be undone [verified: loader logic]. A blank chip key reads 0xFFFF [reported: kagaimiq].

The 2026 commits 2559814 and 3bed429 change only the SPL and loader blobs. The new SPL adds Hamming SECDED correction of the chip key, using a 6-bit ECC field in eFuse row 1. When no ECC was burned, it falls back to a "flash key" stored inside the SPL image to work around eFuse bits flipping back after programming [verified: code; meaning inferred]. Nothing in those commits writes eFuse.

Recommendation: yes, upgrade to the V1.2.13 libraries for an FM-1 build, with these safeguards:
- Never ship any V1.2.x uboot.boot, uboot_no_ota.boot, wl82loader.bin or ota.bin. Assert the stock SPL hash 730e54f0… in packaging.
- Do not stub the key check: it is inert, fm1-nes kept it, and patching LTO-internal vendor code is riskier. Add a link-time audit instead (list below).
- Add a boot_info bridge (as fm1-nes does). V1.2.1 and later read the hand-off block out to +92 bytes, but the stock SPL only fills 6 words plus a 32-byte header [verified].
- Reserve IRQ 123 and the vector-table words at 0x1C80108–0x1C80110 for the SDK.
- Add a hard rule for the dongle and dev-kit work: never send loader command 0xFC12 or the raw 0xA1 eFuse write, and never pass -key, -key1 or -mkey to isd_download for the FM-1.

From the key and eFuse point of view the upgrade adds no new risk over V1.1.9. Both carry the same dormant check. V1.2.x only makes the failure path harsher (it trashes the vector table and recurses).

- sdk_meky_check is a late_initcall in every release. In V1.1.9–V1.2.6 it is in cpu.a key0_decode.c.o; from V1.2.7 it is in system.a os_api.c.o. It calls sys_timeout_add(NULL, _mkey_check, 8000). From V1.2.8 it also calls request_irq(123, prio 6, isr_check_key) on both cores and clears bit 12 of the interrupt-config registers at 0x1EF013C and 0x1EF033C. [[verified]] — LLVM IR from the vendor clang (-S -emit-llvm) of the bitcode in liba/*.a for V1.1.9, V1.2.1–V1.2.13 and commits 2c73d71, 2559814, 3bed429. Files on the build host: ~/mvave-fm1/softkey-efuse/work/<ver>/{cpu,system}/. Copies: scratchpad/ir/<ver>/. In V1.2.13 os_api.c.ll, sdk_meky_check starts at line 4601 and _mkey_check at line 4624.
- _mkey_check first runs an obfuscated decoy pass that XORs JL_RAND values into the 'puk' state. It then passes immediately when puk still holds its initial value 0xF36C3698, meaning no key was ever registered. Only when a key is registered does it decrypt the 32-byte JL_KEY_2020 blob and check magic 'JKYS' (0x53594B4A), version 1, type 15 and CRC16. It then compares (chipkey & KeyMask) with (KeyValue & KeyMask). From V1.2.1 it also rejects mask 0xFFC0 when (chipkey & 0x30) > 15. [[verified]] — IR of _mkey_check in each release. JL_RAND R64L/R64H are at 0x13B00/0x13B04 (WL82.h JL_RAND_BASE = lsfr + map_adr(0x3b,0)). The cipher is doe(), the JieLi CRC-CCITT LFSR XOR in cpu.a encryption.c. The CRC is CRC16 in cpu.a crc16.c.
- The 'chip id' the key check compares against is the 16-bit chip/encryption key passed by the SPL, not a direct eFuse read. get_chip_id() and get_system_enc_key() both return boot_info field 3. boot_info_init copies it from the SPL hand-off at offset +12. From V1.2.8, boot_info_init also passes it to mkey_dummy_func, which stores it at 0x01C8010C. [[verified]] — cpu.a crc16.c.ll: both functions load %struct._boot_info index 3. cpu.a boot.c.ll: boot_info_init. os_api.c.ll: mkey_dummy_func stores to inttoptr 29884172.
- What happens when a registered key fails, by release:
- V1.1.9: CRC mismatch calls P33_SYSTEM_RESET (when config_asser is 0); any other mismatch hangs in an infinite loop.
- V1.2.1–V1.2.7: fills RAM from 0x01C80000 with random words, then recurses into _mkey_check.
- V1.2.8–V1.2.13: writes random words to 0x01C80028 and 0x01C8002C–0x01C801DC, which is vector-table slots 10–119 (IRQ 123's slot is 0x1C801EC), then recurses.
In every case the failure is a runtime crash or hang. None writes flash or eFuse, so nothing is permanent. [[verified] (vector-table meaning [inferred])] — _mkey_check IR in each release. Per release: trashRAM refs 0/1/2, P33_SYSTEM_RESET 1/0/0, recursion 0/2/2. The vector-table base at 0x01C80000 is inferred from request_irq(123) matching the slot at 0x1C801EC.
- Nothing in any SDK library or SDK source registers a key, so the check is dormant in SDK builds. Only os_api.c.o / key0_decode.c.o reference sdk_mkey_lock, mkey_check, sdk_mkey_lock_v2_cfun, key_check_demo or sdk_chip_key_verify_v2. The same holds for the absolute stub 0x0200012E, the mailbox words 0x1C80108–0x1C80110 and the constants JKYS and 0xF36C3698. The only other references are cpu.a boot.c → mkey_dummy_func and startup.S → isr_check_key. [[verified]] — nm via LLVMgold over all 157 .a files (V1.2.13) and 126 (V1.1.9) in ~/mvave-fm1/softkey-efuse/scan-wt-*/. Grep of about 7,700 converted IR members in ir-wt-1213 and ir-wt-119. Grep of the V1.2.13 apps/, cpu/ and include_lib sources. For V1.2.1–V1.2.12 only the five core libraries were scanned.
- The SDK embeds its own JL_KEY_2020 blob, the 33-byte .str starting FE 23 A8 B1. It is used only by mkey_check() and key_check_demo(), and nothing calls either. Decrypted, it has KeyMask 0xFFC0 and KeyValue 0x013F, so it licenses chip keys 0x0100–0x013F (0x0100–0x010F under the V1.2.x rule). The FM-1 key 0x980F would fail it: (0x980F^0x013F)&0xFFC0 = 0x9900. Linking anything that calls mkey_check would therefore crash an FM-1 8 s after boot. [[verified]] — Decoded on the Mac with my own doe/CRC16 code. Plaintext tag 'JKYS', crc 0x1ECD matches CRC16(bytes 6..31), size 32, ver 1, mask 0xFFC0, value 0x013F, field 0xA000, type 15.
- V1.2.13 adds sdk_chip_key_verify_v2(pData, passwd, mode), which parses JL_KEY_2024 plus JL_EFUSE_DESC entries (u8,u8,u16,u32 KeyValue,u32 KeyValueMask). It reads JL_INTEST->CHIP_ID (0x10200) and the boot_info chip key, and returns user_id or a negative code. It takes no action on failure and nothing calls it. key_check_demo hashes 92 bytes at 0x0200012E, the stub that V1.2.8+ startup.S places after cpu0_start; nothing calls it either. [[verified]] — os_api.c.ll lines 784–1100. WL82.h JL_INTEST_BASE = lsfr + map_adr(0x02,0) = 0x10200. In the startup.S.o disassembly, the word at +8 relocates to isr_check_key and the 92-byte stub runs from +0xE to +0x6A.
- No application library touches the WL82 eFuse controller. There is no access to JL_EFUSE (0x13700–0x1371F) and no p33_* call on P3_EFUSE_CON0/CON1/RDAT (0xB0/0xB1/0xB2). The only 'efuse' functions belong to the external Realtek RTL8822 and AIC Wi-Fi drivers. rf_fcc_tool's clear_efuse() writes VM records, not eFuse. norflash_*_otp refer to SPI-NOR OTP, and update.a's 'burn_boot_info' writes flash. [[verified]] — Grep of every IR member for inttoptr 79616–79647 and for p33_*(176..178) / p33_buf(-80..-78). P33 access goes through SFR 0x13E08 (cpu.a p33.c.ll). apps/common/rf_fcc_tool/rf_fcc_main.c:1320.
- The SPL (uboot.boot release and debug, V1.1.9 through V1.2.13 including 2c73d71, 2559814 and 3bed429) only reads eFuse. It has one routine that selects a row via P33 0xB0, strobes 0xB1 with bit 1, reads 0xB2 and clears 0xB1. The chip key is row 1 bits 8–23. There is no programming sequence: no unlock of P33 0x62–0x65 with E7 58 B5 22 and no CON1 bits 0x81. [[verified] (bit meanings [inferred])] — Vendor objdump in ~/mvave-fm1/softkey-efuse/ub/*.dis. Every SPL has exactly 4 'r0 = 176..178' sites, all in the read routine, and 0 occurrences of 'r1 = 231'.
- The SPL key source changed over time:
- V1.1.9 (stock FM-1): eFuse key first; if it reads blank, the 'flash efuse page' key ('get_flash_chip_key'); if that page is invalid, 0xFFFF.
- V1.2.12/V1.2.13 (from 2559814 and 3bed429): also reads a 6-bit ECC field (row 1 bits 1–6). If it is burned (not 0x3F), the key is corrected with Hamming SECDED(22,16). If it is not burned, the eFuse key is compared with a 'flash key' halfword inside the SPL image (0xFFFF as shipped). When they differ by 2 bits or fewer in the flip-back direction, the SPL uses the flash key and prints 'use flash key!!!'. That is the commits' 'efuse 回弹' (bits flipping back) fix. [[verified] code structure; semantics [inferred]] — Debug-build disassembly around the efuse_read callers (V1.2.13 debug 0x1c04f74–0x1c05138). Strings are diffed across releases. Commit messages: 修复芯片未使用新版烧录器烧录ECC, 导致KEY错误下载失败 (2026-01-22) and 为兼容旧方案，ecc没有烧录的情况下，efuse回弹问题仍然使用旧的策略(使用flash key) (2026-02-06). The blank-key comparison value is inferred.
- The only eFuse-burning code found is JieLi's USB download loader wl82loader.bin, in every release. After CrcDecode in 512-byte blocks it contains:
- an efuse_program routine: P33 0x62–0x65 set to E7 58 B5 22, row/bit select on 0xB0, CON1 set to 0x81, a TIMER0-timed pulse, then relock;
- a field writer that can only clear bits (1 to 0), with up to 5 retries.
Two USB commands call it: dispatch 0xA1 (raw 24-bit write to a host-chosen row) and a chip-key write to row 1 bits 8–23 with a VPP argument checked to 3300–5500 mV. kagaimiq names the latter WRITE_KEY 0xFC12, vpp=5000. [[verified] code; command semantics [reported]/[inferred]] — ~/mvave-fm1/softkey-efuse/ldr/*_ldr.dis and crcdec.py. In V1.1.9: program routine at 0x1c036aa, field writer at 0x1c03774, callers at 0x1c041da and 0x1c0459c. The same two call sites exist in V1.2.13 (0x1c04206, 0x1c048cc). Command names from reference/jl-uboot-tool/jltech/uboot.py; that tool's burn-chipkey prompt warns the result may be key AND newkey.
- The OTA path cannot burn eFuse. The stock FM-1 usb_hid_ota loader has no P33 eFuse access. In the AC791N_OTA_loader libraries, get_page_eFuse() just returns get_flash_dec_key(), and key_check() decodes a chipkey.bin-style blob without writing anything. UPDATE_EFUSE / efuse_update are compiled only for CONFIG_CPU_BR40. [[verified]] — softkey/out/hidota.dis has 0 'r0 = 176..178' and 0 unlock sites. IR of usb_hid_ota cpu_lib key_driver.o and logic_lib key_efuse.o. reference/ac79-ota-loader/uboot/include_lib/lib_include.h:332–337.
- The stock FM-1 firmware contains the V1.1.9-style check, dormant:
- sdk_meky_check at 0x020362E0 calls sys_timeout_add(0, 0x020362F6, 8000);
- _mkey_check at 0x020362F6 has puk at 0x01C080C0, JKYS and 0xF36C3698 immediates, a hang loop at 0x2036418, P33 reset at 0x2036420, and the chip key read from boot_info 0x01C7FD50+28, with no &0x30 rule;
- there is exactly one reference to puk, and the SDK key blob is absent, so nothing registers a key.
V15 and FM-1_092 are identical at these addresses. V13 and V14 have the same pattern (8000 ms calls at 0x20344f0 and 0x2034c36). [[verified]] — Vendor objdump of the stock apps produced by the parallel lane in ~/mvave-fm1/softkey-efuse/softkey/out (read only). Byte search of scratch/*/files/app.bin: puk_init appears 3 times, the blob 0 times, JKYS once.
- M-VAVE's libraries are custom JieLi builds, not a public release:
- SYSTEM: '*modified #define CPU_CORE_NUM 1 *-fengshunjian-@20220920-$fdc21c0';
- DRIVER: '*modified*-liangyongxin-@20231109-$9aaf4e5';
- UPDATE: '*modified*-tanchiquan-@20230817-$2374938'.
UPDATE's hash equals public V1.1.9 update.a; SYSTEM and DRIVER match no release from V1.1.9 to V1.2.13. The SPL is the V1.1.9 one (730e54f0…). Side lead: 'CPU_CORE_NUM 1' may contradict the docs' two-core voice inference. [[verified] strings; interpretation [inferred]] — Strings in app.bin compared with the version strings of every release's system.a, cpu.a and update.a. Public strings have the form 'SYSTEM-$hash'.
- The FM-1 chip presents chip key 0x980F, so its key is programmed (blank reads 0xFFFF). Whether 0x980F comes from eFuse or from the last-4 KB 'flash efuse page' (docs list key_mac at 0xFF000) is not determined. With no key registered, _mkey_check passes whatever the chip key is. With the SDK blob registered, 0xFFFF would fail too. [[verified] key value; source [inferred]] — Package isd_config / jlfw.yaml give chip-key 38927. The app decrypts with it and the device runs. The V1.1.9 SPL falls back to the flash page only when the eFuse key reads blank.
- fm1-nes treats the check as present and unverified. Its audit_boot.py requires late_initcall to be exactly [sdk_meky_check], a 62-byte initializer with two request_irq(isr_check_key) calls, and sys_timeout_add specialised to _mkey_check with 8000 ms (bytes 42 e0 40 1f). It reports runtime_result_verified: False. app_main.c's diagnostic waits 20 s 'so as not to report before _mkey_check' and neither calls nor skips the check. VALIDATION.md says nothing explicit about the check, but its V14 run showed advancing frames 4058–4841 with zero faults, long past 8 s. fm1-nes also needed boot_compat.c because the stock SPL hands off 6 words while the V1.2.x boot_info_init reads to +92. [[reported] (fm1-nes); hand-off sizes [verified]] — reference/fm1-nes/firmware/nes/audit_boot.py lines 249–279 and 472–484; boot/app_main.c lines 120–130; boot/boot_compat.c; VALIDATION.md lines 18–29. Both SPLs copy 'rep 4 6' words plus a 32-byte header [verified]; V1.2.1+ boot.c reads _info+80 and +88 [verified].
- The SPL payload loads at 0x01C02000 starting from file offset 16; the 16-byte header (01 00 size, 0x01C02000, 0x10, crc) is not loaded. Any SPL disassembly based at file offset 0, including AL-255's analysis/device/uboot indexes and the parallel lane's uboot.dis, is 16 bytes too high. [[verified]] — String-pointer test (immediate plus offset hitting a NUL-preceded string): 129/144 hits with the 16-byte shift versus 8/144 without (V1.1.9 debug); 144/161 versus 8 (V1.2.13 debug); 12 versus 0 (stock release). My ub/*.dis use the unshifted frame, so subtract 0x10 from the SPL addresses quoted here.

## 4. Recommendation and safeguards for the SDK upgrade

1. Decision: adopt the V1.2.13 (e30b1ee) libraries for FM-1 builds. Do not stub sdk_meky_check or _mkey_check.

2. Add a post-link audit to the JieLi build (modelled on fm1-nes audit_boot.py) that fails the build if:
- the late_initcall group is not exactly [sdk_meky_check];
- sdk_meky_check does more than two request_irq(123, isr_check_key) calls and sys_timeout_add(_mkey_check, 8000);
- any of mkey_check, sdk_mkey_lock, sdk_mkey_lock_v2_cfun, key_check_demo or sdk_chip_key_verify_v2 survives LTO, or anything references them;
- any code loads or calls 0x0200012E or writes 0x01C80108–0x01C80110;
- the image contains the SDK blob bytes FE 23 A8 B1 28 D4 B4 29 or the key_check_demo hash 99 56 B6 46…;
- our code uses IRQ 123.

3. Port fm1-nes's boot_compat bridge: copy 6 words from the stock hand-off and zero words 6–22. Alternatively, prove that sdram_info and ex_app_info go unused when SDRAM_SIZE=0.

4. In package tooling, assert that top/uboot.boot SHA-256 is 730e54f0a439… and that isd_config.ini, ota.bin and cfg are byte-identical to stock. Keep the app encrypted with chip key 0x980F. Never take uboot*.boot, wl82loader.bin or ota.bin from any SDK release.

5. Add to docs/07 and docs/10 (owner to approve the edit): when the device is in UBOOT/USB download mode, the host tool must allowlist read-only loader commands and refuse 0xFC12 WRITE_KEY and the raw 0xA1 eFuse write. Never pass -key, -key1 or -mkey to isd_download for the FM-1. Note that the same commands would burn the dev kit's key.

6. Once a full dump is allowed under the one rule, read-only checks can settle where 0x980F comes from: loader READ_KEY 0xFC09 plus the last 4 KB of flash.

7. Optionally note the 16-byte SPL load-offset correction in our docs and offer it to AL-255 as an upstream candidate (owner sign-off needed).

8. Follow up the 'CPU_CORE_NUM 1' string in stock system.a against the docs' two-core inference.

## 5. Risks recorded by the investigation

- Under the one rule, the soft key is not allowed traffic today. CLAUDE.md allows only the identity query and passive captures. The soft key resets the chip, and the dump that follows writes the loader into RAM and runs JieLi's code on the FM-1. The owner must decide whether to allow these steps before anything is sent.
- The soft key resets the chip straight from the USB interrupt, with no coordination with other tasks. If a VM (settings) save or a Baud Girl preset write is under way across several flash steps, the reset can land between steps and lose settings [inferred]. A single erase or program cannot be interrupted, because flash-resident interrupt code cannot run during it [inferred].
- A one-bit slip (7D→7F) sends the OTA upgrade command, and OTA step 1 can write the loader flash area (docs/03 §5).
- The loader's flash init writes the flash status register (QE bit) if a config block selects quad mode and QE is clear. The default with no block is mode 2 [verified code / inferred default]. Never write anything into RAM after the loader (0x01C07E00+).
- The host operating system's mass-storage driver claims the 4C4A:8057 disk. macOS may offer to Initialize an 'unreadable disk', and clicking it would send standard SCSI writes, whose effect on UBOOT1.00 is unknown. Linux usb-storage only probes. Hosting through an RP2040 bypasses the OS entirely.
- Session fragility [reported]: a hub with another full-speed device, the host sleeping or suspending the port, or ~3 s idle under the loader ends the session (the chip resets and boots flash). This is harmless, but the dump is lost. After a warm reset the app does not attach to USB until a power cycle.
- Nobody has reported the soft key on FM-1_092; the claim that it behaves as on V15 is static analysis only.
- If the unit does not come back, the fallbacks are unproven on this unit. The USB_KEY dongle has been simulated but never used on hardware here. The stock updater and Baud Girl's installer work only while an app with the update service runs.
- The flash read path through the loader's device read op was traced statically only, and the ROM is undumped. 'No autonomous writes' rests on others' before/after dump comparisons.
- A dongle-less restore only works while a 7D-capable app is running. An interrupted erase or write in the app area removes the soft key, leaving only USB_KEY. Writing the head [0, 0x4000) wrongly could stop the SPL from booting. Writing VM, BTIF, USR or key_mac from another unit's image would clobber settings, Bluetooth pairing or the MAC address. FB 00/02/42 (block/chip erase), FC12/16/A0/A1 and the like must never be sent.
- Vendor binaries (app.bins and the deciphered loader) now sit on aeon under the build host's work directory. Never commit them; delete them when done.
- All of this is static analysis. Nothing ran on a JieLi chip, and the bit semantics of the eFuse controller and P33 (read strobe, program enable, the meaning of the E7 58 B5 22 unlock) come from code shape, not a datasheet.
- A future vendor library (codec, DSP, Wi-Fi, a newer system.a) could call sdk_mkey_lock, mkey_check or the 0x0200012E stub with a licence blob that 0x980F does not match. That would crash the FM-1 8 s after every boot (vector-table trash plus recursion in V1.2.x). The link audit must fail the build if that happens.
- Only V1.1.9 and V1.2.13 were scanned across all libraries. Releases V1.2.1–V1.2.12 were checked only in system/cpu/update/common_lib/cfg_tool.
- The decoy pass in _mkey_check misfires only if the random XORs cancel exactly (about 2^-32 per boot). It is the same in stock firmware, so in practice it is negligible.
- The V1.2.1+ boot_info_init reads sdram_info (+80) and ex_app_info (+88), which the stock V1.1.9 SPL never writes. Without a zero-fill bridge like fm1-nes's, these are uninitialised SPL RAM.
- Whether the FM-1's 0x980F key lives in eFuse or in the flash eFuse page is unknown. A V1.2.12+ SPL would take its new 'ECC not burned' path on this chip with unverified results, which is one more reason never to ship it.
- JieLi's PC tools and jl-uboot-tool upload wl82loader, which can burn eFuse. A mistaken -key/-mkey or WRITE_KEY run on the FM-1 would permanently change its key to (0x980F AND newkey). Stock images and OTA packages encrypted for 0x980F would then stop working: the update package key check would refuse them and the app would no longer decrypt.
- The same applies to the AC79 dev kit: isd_download with a key file burns that chip's key irreversibly.
- The commit messages are my translations from Chinese. The meaning of '回弹' as eFuse bits flipping back after programming is inferred.
- Root-owned scratch from the containers (about 2 GB, mostly ir-wt-1213) remains under the build host's work directory and needs a container to delete. The parallel lane's softkey/ subdirectory there was only read.
