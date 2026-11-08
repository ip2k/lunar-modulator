# Bounded TIMER4 delay component

Independent MIT implementation; prospective component, excluded from diagnostic
boot images. No device execution has occurred.

[verified: primary SDK source] AC79 SDK `e30b1ee`'s peripheral timer `test2.c`
selects oscillator source with CON bit 3, enables with bit 0 and stops/clears
pending with bit 14. Its divider table's index zero is divide by one.
The SDK time-delay example polls pending bit 15. These sources establish
register operations, not the oscillator frequency on the owner's FM-1.

The caller must establish exclusive ownership of disabled TIMER4, core/IRQ
policy and an integral-kHz oscillator frequency between 1 and 40 MHz. There
is no guessed default. Native word accesses use TIMER4 at `0x10800` with
`csync`; no IRQ is enabled or routed. Each millisecond is a separate period
of at most 40,000 ticks. This avoids assuming that a long period fits the
counter, or claiming a 32-bit counter from its register access width.

Requests are capped at 1000 ms. Both stale-pending clearance and completion
polls have finite bounds. Failure stops the timer, latches failure and does
not retry automatically. Poll limits bound work; they are not calibrated time.
Physical duration needs the caller-verified clock and includes software overhead.

[verified: Hera host checks] `tests/test_timer4_delay.py` passes 22 checks,
covering exact periods, stale pending, late completion, mid-request failure,
preowned timer refusal, invalid clocks and no implicit retry. Combined with
recovery checks: 36 pass with warnings treated as errors and cache disabled.
[verified: Hera target] Separate object SHA-256:
`c7a5a9f58888cd01cd42ad498aee0d2169c0d3924fb2ba93f04f7dedc1d8099e`.
Vendor disassembly confirms native word accesses and barriers, with no named
undefined helper. This is source/host/code-generation evidence, not device timing.

[verified: stock V15 binary] Raw offsets `0x1b6a..0x1b9e` read
`0x119a0`, mask bits 27:26, and choose 40 MHz for field value 2 or
24 MHz otherwise. This explains the supported upper bound; it is not a
measurement or permission to derive a clock from an unchecked inherited
register. No automatic clock selection or programming has been added.
