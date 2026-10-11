# Bounded TIMER4 delay component

Independent MIT implementation; prospective component, excluded from diagnostic
boot images. No device execution has occurred.

[verified: primary SDK source] AC79 SDK `e30b1ee`'s peripheral timer `test2.c`
selects oscillator source with CON bit 3, enables with bit 0 and stops/clears
pending with bit 14. Its divider table's index zero is divide by one.
The SDK time-delay example polls pending bit 15. These sources establish
register operations, not the oscillator frequency on the owner's FM-1.

The caller must establish exclusive ownership of disabled TIMER4, core/IRQ
policy and an integral-kHz oscillator frequency between 1 and 32 MHz. There
is no guessed default. Native word accesses use TIMER4 at `0x10800` with
`csync`; no IRQ is enabled or routed. Each millisecond is a separate period
of at most 32,000 ticks. This avoids assuming that a long period fits the
counter, or claiming a 32-bit counter from its register access width.

Requests are capped at 1000 ms. Both stale-pending clearance and completion
polls have finite bounds. Failure stops the timer, latches failure and does
not retry automatically. Poll limits bound work; they are not calibrated time.
Physical duration needs the caller-verified clock and includes software overhead.

[verified: Hera host checks] `tests/test_timer4_delay.py` passes 18 checks,
covering exact periods, stale pending, late completion, mid-request failure,
preowned timer refusal, invalid clocks and no implicit retry. Combined with
recovery checks: 32 pass with warnings treated as errors and cache disabled.
[verified: Hera target] Separate object SHA-256:
`b3f094838bdf7eb1c05259b1c74333c87e4a6bd15bae0e3a7f161cf1b99cac55`.
Vendor disassembly confirms native word accesses and barriers, with no named
undefined helper. This is source/host/code-generation evidence, not device timing.
