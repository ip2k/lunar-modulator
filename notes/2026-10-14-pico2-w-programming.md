# Owner-supplied Pico 2 W programming

[verified] bench01's MicroPython serial device identified itself as Raspberry
Pi Pico 2 W with RP2350. Its USB serial is `560A5ACCF298BDCB`. Before programming,
two existing filesystem files (14,456 bytes total) were saved privately under
`/home/claude/fm1-pico2w-preflash-20261014` on bench01. Contents remain private.

[verified] One `machine.bootloader()` request entered RP2350 BOOTSEL, USB
`2e8a:000f`, bus 3 device 35. The mass-storage device was identified by model
RP2350 and that exact serial, separately from the FM1's zero-byte UBOOT disk.
A read-only mount returned `INFO_UF2.TXT` model Raspberry Pi RP2350 and board
ID RP2350 before the mount was made writable.

[verified] The reviewed Pico 2 W artifact SHA-256
`54b6157f1ff42c94834885ec9ccd37c4663365fdb2a71149f17d4bae0612e30c`
was checked on the Mac and bench01. Its exact 135-block layout was checked:
one RP2350-E10 absolute-family workaround record and 134 sequential ARM
Secure payload records. See `2026-10-14-pico2-w-dongle-build.md` for format
and primary-source references. The UF2 was copied once, fsynced and synced.

[verified] The device subsequently enumerated as USB `2e8a:0009`, bus 3
device 36, with serial link
`/dev/serial/by-id/usb-Raspberry_Pi_Pico_560A5ACCF298BDCB-if00`.
The host opened that serial device successfully, but its five-second capture
contained no bytes: startup messages had not been retained for a late console
attachment. Runtime status visibility is a follow-up; USB enumeration is not
proof of GPIO key exchange or successful FM1 recovery.

[verified] The FM1 remained in ROM USB mode, bus 1 device 44 `4c4a:8057`,
through this operation. No FM1 flash/write/reset command was issued during
Pico programming. The owner's separate GPIO recovery wiring question remains
pending. App-independent power-on recovery on this FM1 has not been accepted.

[verified] Private evidence includes `manifest.json`, `INFO_UF2.TXT`,
`program-receipt.json`, and `postflash-console.txt` under the backup directory.
No private filesystem contents or binary artifacts are committed.

## Late-console physical verification

[verified] Integrated status replay `dfc4894c` (worker `b6fe93e1`) was built
for both boards. Pico 2 W UF2 SHA-256 is
`8a89633eecd149b7b6422fdf815a9fc3efa0351b8aa7ca1e569dfcf788f2f717`,
69,632 bytes: one E10 workaround record and 135 sequential ARM Secure records.
The exact block layout and hash were checked before programming.

[verified] Live runtime36 descriptors included CDC plus reset interface2.
The SDK 2.1.1 [CDC magic-baud reset implementation](https://github.com/raspberrypi/pico-sdk/blob/2.1.1/src/rp2_common/pico_stdio_usb/reset_interface.c)
and [1200-baud default](https://github.com/raspberrypi/pico-sdk/blob/2.1.1/src/rp2_common/pico_stdio_usb/include/pico/stdio_usb.h)
were checked. One 1200-baud serial open returned the same serial-number Pico
to BOOTSEL37. Its RP2350 disk `/dev/sdc1` was identified afresh, mounted
read-only for INFO_UF2 verification, then remounted for one guarded UF2 copy.
No FM1 command was sent.

[verified] Runtime38 enumerated afterward. Two separate five-second CDC
attachments each returned 171 bytes: the `0x16EF`, 50 kHz banner and
`state=FAULT`. The late attachment/reconnection behavior works on hardware;
the GPIO self-test failed, so no successful USB_KEY exchange is claimed.
Missing GPIO pull-ups are a possible explanation [inferred]; owner wiring
confirmation remains pending. FM1 passive enumeration remained ROM44.

[verified] Evidence is retained privately as `status-reset-request.json`,
`status-INFO_UF2.TXT`, `status-program-receipt.json`, and both
`status-console-1.txt`/`status-console-2.txt` in the preflash directory.
