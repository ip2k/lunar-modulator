# External MIDI dispatch review — 2026-10-15

This is a read-only source review of the 9ec846 diagnostic target and its
shared application path. It explains what the source can and cannot distinguish;
it does not diagnose a physical MIDI connection or prove audible engine output.
The checkout was at `13227400a666c3745e73c45d58bb83e044a4a72c` while reviewing;
the relevant files match the requested source commit
`9ec846b0f4745345ab1d4da9700933be48e3d50e`. No firmware source was changed.

## Dispatch path

The target report `notes/2026-10-15-fresh-lunar-diagnostic-build.md` records
the exact 9ec846 build as all 13 sound engines / 54 modules, content-free,
`LUNAR_UART1_MIDI` enabled, and a one-shot Trio C4 pulse enabled. It is a
diagnostic build; the report says hardware admission, testing and installability
are false.

Both transports converge on `firmware/native/app_probe.c:156-175`:
`apply_midi_event` first calls `lunar_midi_input_accept`, then maps accepted
note-on (velocity > 0) to `fm1_app_note_on`, velocity-zero note-on and note-off
to `fm1_app_note_off`, pitch bend to the app, and only CC120/123 to all-notes-off.
Other control changes have no app action. `app_probe.c:199-217` reads the
current `app.settings.midi_in_channel`, pops at most 32 USB messages through
`midi_get`, and then polls UART if that build option is enabled. The diagnostic
counter increments for USB when a message is popped, not when a host claims to
have sent it. The UART byte counter increments only for bytes consumed by the
parser adapter.

USB travels through the real packet decoder in
`firmware/third_party/dinghy/src/usb.c:730-764`, then the shared MIDI ring and
`platform.c:midi_get` (`firmware/third_party/dinghy/src/platform.c:177-187`).
The decoder enqueues well-formed channel voice packets and selected realtime
transport packets; malformed channel packets increment `usb.rx_bad`, which is
not part of the app's exported MIDI counters. Realtime clock/start/continue/stop
packets can be dequeued and then rejected by the app filter, so the rejected
counter is not synonymous with a wrong-channel note. The USB receive ring is
shared; its EP1 path reserves slots to avoid starving UART input
(`usb.c:766-781`).

TRS MIDI is separately compiled under `LUNAR_UART1_MIDI`. The maintained HAL
configures UART1 RX on PH8 at 31,250 baud and starts DMA before TIMER5
(`firmware/third_party/dinghy/hal/fm1_uart.h:3-12,33-62`); it explicitly labels
this path “Untested on hardware.” The main loop drains a bounded 32-byte
snapshot through `midi_uart_stream.c:5-30`; a ring overrun discards pending
bytes and resets the parser, returning `-1`. In that case
`lunar_midi_uart_bytes` is not incremented and no dedicated overrun counter is
retained, so a flat B value cannot distinguish no received bytes from a
discarded overrun. This is a concrete measurement blind spot, not proof an
overrun occurred.

`midi_stream.cpp:32-57` uses the maintained Arduino MIDI parser in one-byte
mode, turns thru off, and emits complete channel messages. It resets parser
state on a new non-realtime status and rejects unsupported/system messages.
The UART adapter tests cover running status and overflow. The joined regression
`tests/test_native_midi_ingress_integration.py` extracts the actual USB packet
decoder, USB ring reader, common handler, UART poller and MIDI parser. Its
valid USB and UART cases reach the callback stub, velocity-zero releases are
handled, and channel mismatches are rejected. The test deliberately stubs
`fm1_app_note_on/off`; it proves neither a hardware receive nor a sounding
voice.

## App/filter interpretation

`lunar_midi_input_accept` in `firmware/native/midi_input.h:6-18` accepts only
note off, note on, CC, and pitch bend with 7-bit data. Setting 0 means omni;
settings 1–16 select a channel, and every other channel is rejected. For this
content-free target, `fm1_app_init` clears the app structure with `memset`
(`sim/web/src/fm1_app.c:627-670`), so the channel field starts at zero; no
project or SET is started by the module-only Trio path. A persisted or
different prepared project/settings image could alter this, so a future test
must bind its conclusion to the exact image/configuration rather than assume
all builds are omni.

The target selects Trio at sound unit 0 (`app_probe.c:323`). Its built-in pulse
calls `fm1_app_note_on(&app, 60, 100)` directly (`app_probe.c:345-351`). External
accepted MIDI notes call that same function in the same app state via
`apply_midi_event`. The app note path clamps velocity and invokes `play_on` on
the current sound (`sim/web/src/fm1_app.c:1527-1543,1613-1623`); `play_on`
dispatches to the selected engine's `note_on` unless a live MIDI effect takes
the note. The initial app has its default bypassed arpeggiator
(`fm1_app.c:679-683`). This makes a heard pulse evidence that app startup,
Trio selection, the C4/velocity-100 note API path, and audio output worked at
that pulse time. It does not show that an external event reached the common
handler, or that another pitch/velocity/effect route sounds. Conversely, an
increase in accepted-note-on count occurs immediately before the app call; it
proves dispatch to the app API, not that the synth allocated a voice or emitted
audible samples.

The content-free target's channel setting is therefore not a source-supported
leading explanation for silence. For a different image, a channel mismatch is
still possible and should be checked against the actual loaded setting. No
source defect in the USB packet decoder, parser, or common dispatch is shown by
this review. The previous host reports that a sender transmitted notes do not
establish device receipt.

## Telemetry discriminators

The one-second SysEx frame assembled in `app_probe.c:220-245` reports fields
in this order: elapsed milliseconds, render maximum, draw maximum, audio
underruns, USB messages popped, UART bytes consumed, accepted nonzero note-ons,
rejected complete messages, raw MASTER ADC sample, user/system stack margins,
stack sample count, initial engine result, and audio frames written. The TFT
alternates the `U/B/N/A` row and render/draw/underrun row every second
(`app_probe.c:397-414`). Rejected-message count is in SysEx, not the short TFT
row. The builder transform records raw ADC separately while preserving its
existing `k10` to `lunar_master_raw` application gain path
(`tools/native/build_application_probe.py:436-447`); raw A is diagnostic input,
not itself the effective app gain.

For a separated single-note observation, compare before/after deltas from the
same exact image and record a matched waveform window:

| Observation | What source counters can establish | What remains unresolved |
| --- | --- | --- |
| USB sender says “sent”, but U and N stay flat | Nothing entered the app's USB-pop/accepted-note path during the window. | Device enumeration, endpoint delivery, malformed packet count (`rx_bad` is not exported), or timing of the sample. |
| U rises, N stays flat, rejected rises | USB messages were popped but not accepted as note-ons; realtime/system or unsupported/status/channel-filter messages are among the causes. | Which rejected messages were notes without a correlated decoded message log. |
| UART B rises, N stays flat, rejected rises | Bytes were parsed into complete messages that the shared filter rejected. | Exact rejected status/channel without a transport event log. |
| UART B rises, N/rejected stay flat | UART bytes were consumed but did not yield accepted or filter-rejected complete messages in the interval. | Partial message, system/realtime handling, malformed/incomplete stream, or parser/ring loss. |
| B stays flat | No bytes were counted as consumed. | No electrical arrival, DMA tally behavior, or discarded overrun; overrun has no exposed counter. |
| N rises while the external-note waveform is absent | The shared filter accepted nonzero note-ons and called the app note API. | Engine voice allocation/output, note lifetime, pitch/velocity response, or capture alignment. |
| Underruns rise with the stimulus | Audio blocks were missed in that interval. | Whether that caused the absent note or was incidental; the pulse at another time does not answer that. |

The next useful discriminator is one known note (ideally C4, matching the
built-in pulse) in a separately timestamped USB window and TRS window, while
capturing the existing SysEx telemetry and analogue output. Compare U/B/N,
rejected, underruns, A, and waveform against a pulse window at comparable
MASTER level. Preserve the exact image hash and report the route separately.
If N rises without audio, the next investigation moves downstream of ingress;
if N does not rise, collect transport-specific evidence before proposing an
app or synth change. The current counters cannot positively count UART
overruns or expose USB `rx_bad`, so those cases remain ambiguous.

## Checks and limits

Read-only source and test inspection was performed in the coordinator worktree;
`git diff 9ec846b0 --` for the reviewed app/MIDI source files was empty. No
physical device or port was accessed. `python3 -m pytest -q
tests/test_native_midi_ingress_integration.py` could not run because the active
Xcode Python has no `pytest` module. The prior `HANDOFF.md` records the focused
joined-ingress suite as passing, but this turn did not rerun it. The source and
host regression establish software routing only; they do not establish
electrical TRS reception, USB device receipt, real-engine voice response, or
audible/perceptual acceptance.
