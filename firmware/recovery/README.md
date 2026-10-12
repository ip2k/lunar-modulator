# Bounded recovery request component

Independent MIT implementation; the component uses no vendor or GPL HAL.
The SDK-free diagnostic build compiles it separately and excludes it from
the boot image. The private SDK diagnostic built by
`tools/jieli/build-sdk-diagnostic.py` links it and calls it once from its
worker [verified: source]. That integration does not establish physical
recovery or make the image hardware-qualified.

## Contract and provenance

[verified: stock binary] Stock V15's soft-key handler writes the 16 bytes
`usb_update_mode\0` to retained RAM `0x01c7fd80`, then requests chip reset via
P33 register `P3_PR_PWR` (`0xa0`) bit 4. The owner's FM-1_092 handler matches.
See [the stock analysis](../../notes/2026-10-05-softkey-efuse.md) and
[the authorized bench receipt](../../notes/2026-10-07-fm1-softkey-bench.md).
Those stock handlers reached UBOOT; this new component has not run on hardware.
The ROM's marker-consumption implementation remains inferred.

[verified: primary SDK] P33 CON/DAT word addresses `0x13e08`/`0x13e0c`,
selection bit 0, RTC selection bit 8, busy bit 1 and start bit 4 are checked
against pinned AC79 SDK `e30b1ee` headers and fresh vendor IR for `p33.c`.
Its OR operation sends `0x20`, the low register address, then the bit mask.
The native backend uses a real pi32v2 `csync` instruction and volatile accesses.
This request uses that fixed OR operation instead of exposing general P33 IO.

Binding performs no hardware IO. A request refuses an already-selected P33
bus, bounds waits to 1–65,536 control-register reads, writes and reads back all
16 mailbox bytes before P33 writes, and stops sending at the first timeout.
Cleanup deasserts its selection and clears the start strobe, preserving other
control bits. Failure is latched; another call performs no IO until explicitly
rebound. The marker can remain after a failed transfer. Do not blindly retry.

A return value of 1 means the three bytes were transmitted; it does **not**
prove reset or USB recovery enumeration. No flash operation, second-core
release, write-guard change or arbitrary reset register is exposed.

## Verification and integration gates

[verified: Hera target compile] The pinned pi32v2 compiler builds `request.o`
without named unresolved symbols. Vendor disassembly confirms word MMIO,
byte mailbox access and `csync`. The diagnostic link/audit still passes, with
its binary unchanged because this object is deliberately excluded from that
SDK-free profile. See [the private SDK profile](../sdk-diagnostic/README.md)
for the later integration and its separate native audits.

Host fault simulation covers exact marker/byte order, readiness on the last
allowed poll, timeout at each byte, held start-strobe cleanup, preexisting bus
ownership, mailbox corruption, invalid binding and no implicit retries.
Run `python3 -m pytest tests/test_recovery_request.py` in the bounded Hera test
container; the C shim uses the container's native compiler, not a device.

The private SDK worker uses the vendor cross-core P33 lock and nested IRQ
masking. The lock can wait indefinitely if the other core stops while holding
it; finite transfer polling does not bound lock acquisition or scheduler
delays. The contract requires a healthy SDK runtime. Display failure still
reaches the one recovery attempt [verified: source], but a CPU/scheduler hang
has no proven rescue through this component.

Establish retained mailbox writability/protection, inherited clock/power state,
and reset behavior from the actual entry context. Observe UBOOT on the bench
and verify the reviewed restore route before treating this as recovery.
Source/target tests do not close those gates. Exact artifacts and continuation
state are recorded in [the session note](../../notes/2026-10-11-installable-firmware.md).
