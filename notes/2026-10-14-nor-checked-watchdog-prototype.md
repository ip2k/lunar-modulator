# Checked watchdog gate around the offline NOR writer

**Status: bounded HAL prototype; SAVE remains unbound and unadmitted.** Source base: `3f3dde0896e76a5b8b072d7b41924490eeca4045`. No USB, MIDI, flash, power, reboot, or device operation was performed.

## What changed

`fm1_sys.h` now has checked P33 transaction helpers and checked watchdog stop/re-arm operations. A transfer timeout returns an error instead of being used as received data; a checked multi-byte operation stops after the first failed byte and always de-selects the P33 transaction. Watchdog stop reads the current watchdog and VLD mode, refuses an enabled exception-mode watchdog, sends the stop command, and requires a completed readback showing the enable bit clear. Re-arm restores the prior reset-mode timeout and verifies the enabled bits.

`fm1_flash.h` wraps both actual NOR entry points, `fl_erase4k` and `fl_write`, in the following order: save and mask the current ICFG value; stop and read back the watchdog; enter the RAM NOR operation only after that check; return from the RAM routine only after a completed status read observed WIP clear (or before XIP was disabled); re-arm the previously enabled watchdog after the RAM writer has restored XIP; finally restore the exact saved ICFG value. A stop/readback failure returns `-6` before issuing any NOR SPI byte. A re-arm failure after an otherwise successful operation returns `-7`. If both the NOR operation and re-arm fail, the original NOR error has precedence; the current API does not separately encode the second failure.

The guarded paths are the only in-tree callers of `fl_erase4k_ram` and `fl_prog_ram`; `platform.c` reaches them through `fl_erase4k` and `fl_write`. This does not change SAVE admission or bind the path to an application service.

## Evidence and checks

The focused host harness in `tests/native/test_dinghy_flash_transport.c` passed with strict GCC warnings and with ASan/UBSan. Its P33 fixture models byte-level WDT/VLD state and transfer timeouts. Cases cover a successful stop/erase/ready/re-arm sequence, refusing exception-mode WDT before NOR traffic, P33 timeout propagation, failed stop/readback with zero NOR bytes, preserved incoming ICFG, and re-arm failure reported only after positive ready and SFC/XIP restoration.

The pinned pi32v2 compiler also compiled a small translation unit that includes `fm1_flash.h` and calls both wrappers. Toolchain: `/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1/common/bin/clang`, flags `-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin`. Probe object SHA-256: `a60f41f8e179c019724b1155b10cbb314cb416feac31c9f4b79ed63015dd2dbc`. Vendor `objdump -t` placed `fl_erase4k_ram` (`0x35c`, size `0x3fe`) and `fl_prog_ram` (`0x75a`, size `0x44e`) in `.ram_text`; `fm1_wdt_stop_checked` (`0x102`, size `0x54`) and `fm1_wdt_restore_checked` (`0x160`, size `0x58`) were in `.text`. The wrapper disassembly showed the stop check before the indirect RAM-writer call, then re-arm before restoring saved ICFG.

These are host-fixture and single-translation-unit compile/disassembly checks. They are not a final firmware link, full RAM closure audit, target execution, NOR datasheet guarantee, SAVE admission, or physical recovery proof. The `fm1_wdt_stop_checked` failure case can leave watchdog state unknown if the stop command may have landed but P33 readback timed out; it still sends no NOR bytes, and no NOR WIP operation has begun. The caller receives `-6`, but this prototype does not prove the watchdog was restored on that early transport failure.

If WDT re-arm fails after the NOR routine returns, XIP has already been restored only after positive WIP-clear observation; the wrapper reports an error and restores the original ICFG. If a status transaction never positively observes ready, the existing RAM wait loop does not return, restore XIP, re-arm, or restore ICFG. With the watchdog intentionally stopped for that interval, this is a non-returning RAM wait, not a proven hardware fail-stop or recovery mechanism. Watchdog hardware behavior during such an indefinite wait and reset/power-loss interaction remain untested.

`inventory.json` and `UPSTREAM.md` record local SHA-256 values and provenance for both modified GPL HAL files. The default watchdog startup call and other legacy P33 users are unchanged; their callers do not all inspect the newly available checked status APIs.

## Next dependency

Before enabling or binding SAVE, review the diff and test semantics, then repeat a final linked pi32v2 build and complete RAM/control/data/call closure audit for the production source set. Resolve the early stop-transport case and re-arm error reporting policy. This prototype does not establish a bounded recovery from persistent WIP/status failure; that remains a separate runtime-safety decision.
