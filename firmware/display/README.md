# Offline panel probe component

`panel_probe.c` is an independently authored MIT command emitter based on the
byte-verified stock V15 panel setup. It emits setup, a four-band 240×240 RGB565
word pattern and display-on through caller-supplied callbacks. It allocates no
framebuffer and accesses no registers, SDK services, ROM, flash or interrupts.

There is **no hardware backend or startup call**. This component is not an
observable diagnostic yet. A successful host trace establishes the protocol
and failure handling; it does not establish actual panel colors or timing.
The backend must supply finite transfer deadlines and calibrated delays,
release CS on failure, and establish the clock/power/current-core/watchdog and
exception contracts documented in
[`notes/2026-10-09-lcd-runtime-prerequisites.md`](../../notes/2026-10-09-lcd-runtime-prerequisites.md).
The existing inert and handover application variants remain unchanged.
