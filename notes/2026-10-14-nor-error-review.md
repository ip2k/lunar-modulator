# Independent review: Dinghy SPI NOR transfer failures

Date: 2026-10-14
Reviewed commit: d81bca95677703167b216c66b7b1327cd5fb3e77
Reviewed tree: isolated Hera worktree /home/claude/worktrees/nor-error-review
Owned scope: failure behavior after erase/program transfer errors; no source changes.

## Finding: fail-closed gap after a possibly accepted destructive command

**Blocker for enabling or relying on the writer.** The new status return is useful, but a failed SPI wait does not establish that the flash rejected all bits sent before the wait timed out. When the operation has selected the flash and sent an erase/program opcode, address, or program data, raising CS may end a partially or fully received command. The patch has no flash-state model or evidence that such a transfer failure means the command was not accepted.

In firmware/third_party/dinghy/hal/fm1_flash.h, fl_erase4k_ram lines 231–240 and fl_prog_ram lines 257–267 deassert CS after the first error. Because rc is nonzero, they skip cache invalidation and fl_wait_ready, call fl_exit, and return the error. fl_exit lines 152–159 restores the saved SPI state, pin ownership and saved SFC_CON, explicitly re-enabling XIP. The outer fl_erase4k / fl_write wrappers then restore interrupts regardless of the returned code. A caller therefore resumes ordinary XIP execution although an erase/program operation could still be in progress.

This is a **new early-exit path** relative to the parent 620cc306a83addb0104fc2c3f328e53e070a0446: the older implementation ignored SPI wait results but, after sending the destructive transaction and releasing CS, did call fl_wait_ready. The old path was not safe evidence either: status-transfer timeouts returned stale/untrusted bytes, so it could falsely report ready. The reviewed change improves error reporting and stops further bytes, but creates a route that omits even that existing ready poll. Both versions also restore XIP after a ready-poll timeout/error.

The same unresolved state exists when fl_wait_ready itself returns -4 (deadline elapsed while WIP remains set) or -5 (could not read status). Returning those errors after restoring XIP is not fail-closed: neither result proves WIP is clear. The function has a bounded 500 ms erase or 10 ms program poll, but those bounds only stop polling; they do not prove the NOR has stopped or make XIP safe.

## Evidence and test coverage

- fl_spi_wait reports only whether the controller's pending bit appeared before its counter expired. Its error is not tied to a flash-level command-rejection guarantee.
- fl_cs(1) ends the selected command frame after each failed transfer. No NOR state machine is modeled in this HAL or in the fake test.
- tests/native/test_dinghy_flash_transport.c injects failures at each transfer index and, for erase/program errors, asserts assert_restored(...). That helper requires reg_sfc == 0 (the mock's saved XIP mode), original SPI restored, and CS high. This proves cleanup/restoration behavior, not safe behavior while WIP may be set.
- The fake test_spi_wait returns a timeout before assigning RX data but does not model partial bit shifts, CS-edge command acceptance, flash busy/WIP, or XIP read behavior during WIP. test_status_poll_transfer_errors_cleanup also asserts state restoration after failed status polling.
- Focused check run on Hera: pytest -q tests/test_dinghy_flash_transport.py — **1 passed**. This validates the current harness only; it does not close the identified hardware-state gap.
- firmware/third_party/dinghy/hal/fm1_sys.h provides a reset-mode watchdog (fm1_wdt_arm, timeout selector 0xD used at startup) and a feed call in the ordinary platform main loop. The flash RAM routines do not feed it. The code documents a core/chip reset and UBOOT entry, but this review found no evidence that a watchdog or software reset while the flash is busy makes the subsequent SPL/XIP fetch safe. I do not recommend reset/ROM entry as a remedy absent a separately verified recovery route.
- The driver already places XIP-off routines in .ram_text; app.ld loads that section into RAM. This supports continued RAM execution while XIP is off, but there is no reviewed terminal-state routine or proof that a post-timeout reset is safe.

## Required control before writer use

Treat any failure after a destructive opcode may have been issued as **operation outcome unknown**, not as “no write happened.” Do not restore XIP or ordinary interrupt-driven execution until a valid status transaction positively observes WIP clear. This must cover opcode/address/data transfer failures as well as status-read failure and ready timeout. The present bounded poll can return a diagnostic error, but no evidence in the reviewed code establishes a safe way to leave that state if readiness cannot be established. A reviewed fail-stop/recovery mechanism and its actual boot/XIP behavior are therefore a prerequisite; do not paper over it by merely adding one more best-effort status read or returning -5 to an XIP caller.

Required tests should model a flash that may accept a command despite a controller timeout, assert that no XIP restoration/normal IRQ return occurs before positively confirmed ready, and exercise status failure and persistent WIP. They should distinguish “operation may have taken effect” from verified success. Any terminal/reset design needs separate source/disassembly evidence for its safe continuation/recovery path before it can be called fail-closed.

## Limits

This is source and host-mock review, not a NOR datasheet conclusion, physical timing result, or statement that a particular transfer failure does commit on FM-1 hardware. The part identity 0x856014 and Puya attribution were not used to assert an atomicity guarantee. No device, USB, MIDI, flash, power, or reboot operation was performed. No writer enablement, recovery guarantee, or storage admission is implied.
