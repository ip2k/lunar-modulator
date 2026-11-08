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

## SPI1 transport and the M5 pattern (2026-11-08)

- `spi1_transport.{c,h}` (MIT, Codex, verbatim from
  `feature/2026-10-11@installable-firmware` commit `85348309`) is the hardware
  backend for these callbacks: SPI1 at `0x11D00`, CS PC7, D/C PC8, SCK PC9,
  MOSI PC10, every wait bounded by a poll limit and every failure releasing CS.
  Its native register access is built only with `LUNAR_PI32V2`.
- `panel_probe.c` now exports `lunar_panel_setup` (sleep-out and the 21 stock
  setup records) and `lunar_panel_command`, so other patterns reuse the same
  verified setup; `lunar_panel_probe`'s trace is unchanged.
- `m5_pattern.{c,h}` (MIT, glyphs drawn here) draws the M5 test pattern: a
  border, "LUNAR M5", the build id, "TEST PATTERN" and eight colour bars,
  streamed row by row without a framebuffer.
- PR #161's `firmware/native/diagnostic_display.*` is a host-side row-lease
  layer with no transport; its submit step would bind to `spi1_transport`.
  The two do not overlap.

The transport and the pattern have been built for pi32v2 and checked on the
desktop. Neither has driven a panel.
