# Offline panel probe component

`panel_probe.c` is an independently authored MIT command emitter based on the
byte-verified stock V15 panel setup. It emits setup, a four-band 240×240 RGB565
word pattern and display-on through caller-supplied callbacks. It allocates no
framebuffer and accesses no registers, SDK services, ROM, flash or interrupts.

The protocol emitter has no startup call. The prospective SPI1 backend below
has not been activated on hardware. This component is not an
observable diagnostic yet. A successful host trace establishes the protocol
and failure handling; it does not establish actual panel colors or timing.
The backend must supply finite transfer deadlines and calibrated delays,
release CS on failure, and establish the clock/power/current-core/watchdog and
exception contracts documented in
[`notes/2026-10-09-lcd-runtime-prerequisites.md`](../../notes/2026-10-09-lcd-runtime-prerequisites.md).
The existing inert and handover application variants remain unchanged.

## Prospective SPI1 transport

[verified: source and host tests] `spi1_transport.c` adds a separately activated
MIT transport with a native 32-bit volatile MMIO backend restricted to SPI1
CON/BAUD/BUF, PORTC OUT/DIR and IOMAP CON1. Software binding performs no MMIO.
Explicit configuration preserves unrelated GPIO/mux bits, uses PC7 CS and PC8
D/C, selects PC9/PC10 SPI1 port B, and uses recovered CON `0x4021` and BAUD 4.
The address/layout facts come from JieLi's WL82 primary header; stock setup
provenance is in the runtime prerequisites note above. SDK demo
`spi_nomask_interrupt.c` independently identifies CON bit 14 as clear-pending.
No vendor implementation or GPL HAL was copied.

[verified: host simulation] Each byte first clears/checks the old completion
flag, then sends and waits for the new completion flag. Each phase permits
1–65,536 register reads, as selected by the caller. A timeout disables SPI,
releases CS and latches failure; subsequent panel callbacks send no traffic.
The limit is an iteration bound, **not a calibrated time deadline**. The caller
must supply bounded IO callbacks and calibrated delays, use exclusive pin/SPI
ownership, and start from a quiescent peripheral. Binding is only for fresh or
quiescent storage, never to abandon an active transport. Configuration cannot
be repeated on a configured instance; failure recovery requires a deliberate
rebind after the owner has established peripheral quiescence.

[inferred; hardware verification pending] Stopping SPI before raising CS is intended to prevent
later clocks escaping a failed transaction. GPIO pad readiness, clocks, power,
current core, exception policy, watchdog handling and PA2's electrical role are
still prerequisites. PA2 is not touched. There is no boot invocation and no
hardware activation in the existing inert, handover or panel-protocol variants.
The diagnostic build compiles this as a separate object/disassembly for review;
it is intentionally absent from the linked application. The source component
is not an installable firmware milestone.
