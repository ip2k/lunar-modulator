# Native58 MIDI zero-counter source review — 2026-10-15

This is a read-only source review of the telemetry-enabled 9ec846 candidate.
It does not diagnose a physical port or claim that any MIDI event reached the
FM-1. The active coordinator checkout was at `8670ddf5af6647d734e91a9d438faf51a5bb319d`; the checked `app_probe.c` bytes match 9ec846
(`90774449c817fdbc47f6ae442e55c4feb3facab221c35a6a8aee2240e3a36218`). No
source or device operation was performed.

## What the counters mean

The exact 9ec846 build record explicitly enables `LUNAR_UART1_MIDI`, alongside
the content-free Trio diagnostic (`notes/2026-10-15-fresh-lunar-diagnostic-build.md`).
UART being compiled out is therefore not an explanation for a flat `B` on
this candidate. `fm1_cstart()` calls the UART initializer before TIMER5
(`firmware/third_party/dinghy/src/platform.c:339-345`); the initializer maps
PH8 to UART1 RX, selects the PLL48M clock, sets the 31,250-baud divisor,
configures the DMA ring, then enables UART RX (`firmware/third_party/dinghy/hal/fm1_uart.h:33-53`).
This is source configuration only: the HAL explicitly labels the path
untested on hardware and documents its polled receive tally may miss a byte
(`fm1_uart.h:3-11`).

`B` is not the HAL's raw received-byte total. `app_probe.c:189-195` samples
`fm1_uart1_rx_take()`, passes that value to the stream adapter with a 32-byte
per-loop budget, and increments the reported counter only by bytes the parser
adapter consumed. A software-detected ring overrun returns `-1`, resets the
parser, and adds nothing to `B`; no overrun counter is exported. A zero `B`
therefore does not separate “no electrical bytes” from an unobserved hardware
tally problem or a software discard.

`U` also counts after transport decoding, not endpoint traffic. USB MIDI has
class-specific bulk OUT `0x01` and IN `0x81` endpoints (`usb.c:203-212`). EP1
OUT is configured with an RX buffer, packet size, and RX interrupt enable
(`usb.c:395-407`), and the 2 kHz `usb_poll()` services EP1 RX when the RX
interrupt is pending (`platform.c:197-220`, `usb.c:1176-1253`). Its USB-MIDI
decoder queues valid channel-voice packets and selected realtime events;
malformed channel packets increment internal `usb.rx_bad` instead
(`usb.c:730-764`). The app increments `U` only when `midi_get()` removes a
queued message (`app_probe.c:199-217`, `platform.c:177-187`). `rx_pkts`,
`rx_bad`, and `rx_held` are not present in the exported telemetry frame.

The device's telemetry traveling over USB MIDI IN proves a functioning
device-to-host route. It does not prove host-to-device delivery over USB MIDI
OUT. Likewise, coordinator-reported `aseqsend`→MIDI-Through→`aseqdump`
loopback with C4 Note On/Off confirms that the sender arguments are parsed as
intended; it does not prove the event was routed to this FM-1's ALSA output
port. Earlier failed `aseqsend -s <hex>` attempts are separate and should not
be used to explain later correctly formatted sends.

## Finding and next discriminator

No source-confirmed defect was found in the USB OUT descriptor/configuration,
EP1 polling, or the common app dispatch path. Since `U` increments before the
channel/message filter, a wrong MIDI channel cannot by itself explain a flat
`U`; it can explain `U` rising with accepted-note count `N` flat and rejects
rising. With both `U` and `B` flat, current telemetry cannot distinguish
wrong host routing from transport receive/polling or the UART tally/discard
blind spots. The host loopback test narrows sender-format uncertainty only.

The next coordinator-owned capture should bind each stimulus to the exact
USB-MIDI ALSA output port or TRS path and compare counter deltas over that
window. To separate USB endpoint arrival from parser decoding in a later
offline-reviewed diagnostic revision, export bounded deltas for EP1 packets,
malformed packets, and ring-held packets. For UART, report the sampled raw
hardware tally separately from bytes consumed and count software overruns.
Keep the existing `U`, `B`, accepted-note and rejected-message fields; they
answer later stages. Do not infer that either interface is physically broken
from zero counters alone.

Rarefaction's C profile remained rooted at the primary Developer checkout and
refused the coordinator worktree path; it was not retargeted. Serena had
previously selected the coordinator worktree, but no new semantic result is
claimed here. Direct source line inspection was used. The established host
tests exercise modeled packet parsing and UART stream behavior; they do not
test endpoint registers, ALSA physical routing, PH8 electrical reception,
target DMA behavior, or audible output. No tests or hardware commands were
run for this review.
