# USB-MIDI OUT receive path review — 2026-10-15

Read-only source trace at coordinator checkout HEAD
`93a575a74b2f5fe9ebf0821e2dbd64d0c34a5879`. No firmware or device was
changed or accessed. This explains how a USB-MIDI OUT message would reach the
diagnostic counters; it does not establish that a host submission reached the
device.

## Receive route

The Dinghy configuration descriptor declares MIDI Streaming interface 1 with
two bulk endpoints: `0x01` OUT and `0x81` IN, both with 64-byte maximum packet
size (`firmware/third_party/dinghy/src/usb.c:203-216`). On SET_CONFIGURATION
1, `ep1_config()` binds EP1 buffers, enables its RX interrupt bit, and enables
endpoint 1 (`usb.c:395-407`, called at `usb.c:548-555`). TIMER5 polls the SIE
at 2 kHz (`platform.c:194-220`); `usb_poll()` remembers an EP1 RX interrupt
and calls `ep1_rx()` (`usb.c:1247-1253`). That handler reads at most 64 bytes,
synchronizes the DMA buffer, and passes whole four-byte event packets to
`midi_in_event()` (`usb.c:784-805`).

For channel voice events, `midi_in_event()` accepts CIN 8–E only when the
status high nibble matches the CIN and data bytes are 7-bit; accepted events
are placed on the shared 64-event ring (`usb.c:730-764`). `platform.c`'s
`midi_get()` pops that ring (`platform.c:176-187`). The app drains at most 32
events on each main-loop pass and increments `lunar_midi_usb_messages` only
after a successful pop (`firmware/native/app_probe.c:199-217`). Then the
common filter accepts only note off, note on, CC, and pitch bend, with channel
0 meaning omni and 1–16 selecting one channel
(`firmware/native/midi_input.h:6-18`). A nonzero accepted note-on increments
`lunar_midi_accepted_noteons` immediately before `fm1_app_note_on`
(`app_probe.c:156-175`). The TFT displays U/B/N/A only on alternating seconds;
U is a dequeued-message count, not an endpoint packet count
(`app_probe.c:397-414`).

## What a zero U means

If U is sampled during its display interval and remains zero, the source places
the failure before the app's USB-ring pop. Channel filtering and synth dispatch
cannot explain that observation: those occur after U increments. The current
telemetry cannot distinguish these earlier cases because `usb.rx_pkts`,
`usb.rx_bad`, and `usb.rx_held` are private USB-driver fields and are not
exported in the diagnostic frame:

- The host program accepted a queued ALSA send, but did not submit a USB OUT
  transfer to this FM-1 connection. Host-side usbmon S/C records for the exact
  bus/device/endpoint are needed to establish submission and HCD completion;
  even successful completion does not prove firmware parsing.
- Endpoint 1 was not configured/enabled after the latest bus reset. USB
  enumeration/ALSA registration alone does not show that the SET_CONFIGURATION
  request succeeded for this connection. The firmware enables EP1 RX on that
  request and disables it on reset (`usb.c:1218-1245`, `548-555`).
- EP1 OUT traffic arrived but the USB-MIDI event bytes were malformed or used
  an unexpected cable/CIN layout. The parser silently rejects invalid CIN,
  status/CIN mismatches, and high-bit data; `rx_bad` is not in telemetry
  (`usb.c:753-764`).
- The ring had fewer than 24 free slots, so EP1 remains pending/NAKed until the
  main loop drains it (`usb.c:766-805`). This is intended back-pressure; a
  sustained backlog could delay visibility, though the consumer runs each
  main-loop pass and drains up to 32 messages.
- USB receive processing/polling was not running for the interval, or the
  observation was from the wrong image/port. Firmware polls from TIMER5, not a
  dedicated USB IRQ (`platform.c:194-220`). A port label or ALSA send return
  alone does not bind a transfer to the current firmware image.

Once U increases, compare N and the full telemetry's rejected-message count:
U rising with no N can indicate filtering or non-note messages; N rising means
the common filter called the app note API, not that a voice sounded. The
current TFT omits rejected count, which is present in the diagnostic SysEx
frame. The content-free diagnostic starts with zeroed app settings, making
channel 0/omni the expected source-level default for that exact startup path;
do not assume this for a project/settings-bearing image.

## Next discriminator

The coordinator reports that, during the six `aseqsend -p 28:0` stimuli, the
exact-filtered usbmon capture for the current bus/device and EP1 OUT contained
no payload bytes; telemetry stayed USB=0, UART=0, accepted=0. The coordinator
also reports that a passive full-bus usbmon sample taken after the stimuli
confirmed the text format, but that sample does not establish full-bus coverage
during the sends. Sysfs reportedly showed the native interface and EP1 bulk
endpoints, with ALSA client 28 port 0 named “Lunar Modulator MIDI 1”. This is
coordinator evidence, not independently inspected here. It moves the immediate
diagnostic boundary to the host ALSA-to-USB output path: a zero-byte OUT capture
does not exercise the firmware EP1 parser at all. A successful `aseqsend`
process exit establishes only that the program returned zero; it does not
establish that ALSA accepted/queued the event or submitted a hardware transfer.

A plausible host-side cause is that `aseqsend -p 28:0` sends a direct
sequencer event without establishing an ALSA write subscription. In upstream
alsa-utils v1.2.14, `aseqsend` creates only its own READ-capable source port,
sets each event's explicit destination, then calls `snd_seq_event_output` and
`snd_seq_drain_output` without checking their return values. ALSA's sequencer
documentation says MIDI output devices are opened on write subscription; the
Linux v6.18 `seq_midi` driver installs a `use` callback that opens the raw-MIDI
output and returns `-ENODEV` from event dispatch when that output substream is
null. This makes the missing-subscription hypothesis source-supported, but the
bench kernel's exact source revision has not been independently matched here.
A follow-up should use a persistent mido/python-rtmidi output connection that
subscribes to the exact identity-resolved ALSA output for the entire NoteOn,
hold, and NoteOff sequence, then observe usbmon again. This would test host
submission; it still would not prove firmware consumption. Keep usbmon bound to the current bus/device and EP1 OUT. Only after
host URBs appear should the firmware path be tested. Interpret the combined
evidence as follows:

1. No matching OUT submission: investigate host port direction/capability,
   subscription, and ALSA backend queue delivery first.
2. Submission without successful completion: investigate USB transfer/endpoint
   state; do not call it device receipt.
3. Successful completion but U remains zero: instrument or expose bounded
   driver counters for EP1 packet count, malformed events, ring occupancy and
   configuration state in a future diagnostic build; keep the app filter and
   synth unchanged.
4. U rises but N does not: inspect full-frame rejected count and message
   channel/status; only then consider the app-level filter.
5. N rises: investigate note lifetime/voice/audio output downstream.

The previous ALSA stimulus log records `send` return code 0 and
`device_acceptance:false`; the new no-payload observation further indicates
that no EP1 OUT transfer was visible in that capture interval, but does not
identify why ALSA did not submit one. This review did not inspect the usbmon
capture bytes or physical endpoint state, and did not access hardware. It used
direct source inspection because the configured semantic project selection is
not safe to retarget during concurrent work.


## ALSA subscription source check and ROM61 follow-up

The upstream source check supports a specific host-side hypothesis. In
[alsa-utils v1.2.14 `aseqsend.c`](https://github.com/alsa-project/alsa-utils/blob/v1.2.14/seq/aseqsend/aseqsend.c), `create_port()` creates the sender's port with only `SND_SEQ_PORT_CAP_READ` (lines 212–220). The send path uses an explicit destination and direct delivery (lines 291–324), then increments its byte count without checking the return value of either `snd_seq_event_output()` or `snd_seq_drain_output()`; `main()` later exits success (lines 422–435). It does not establish a sequencer write subscription to the destination.

ALSA's [sequencer documentation](https://www.alsa-project.org/alsa-doc/alsa-lib/seq.html) distinguishes direct-address event delivery from activation of a hardware MIDI output: its subscription section says the MIDI output device is opened when the associated port is write-subscribed (around lines 118–149). In upstream [Linux v6.18 `seq_midi.c`](https://github.com/torvalds/linux/blob/v6.18/sound/core/seq/seq_midi.c), `event_process_midi()` returns `-ENODEV` when the raw-MIDI output substream is null (lines 113–124); the output `use` callback opens that substream (lines 198–222), and the registered port callbacks include `use`/`unuse` (lines 354–362). The coordinator reports the bench kernel as `6.18.34+rpt-rpi-2712`; I reviewed upstream v6.18 source, not the exact Raspberry Pi downstream source package, so downstream divergence remains untested. This is a strong explanation for why `aseqsend` may report success without an EP1 USB submission, not a proven cause until the next trace shows that opening a subscribed output produces a host OUT URB.

The maintained [RtMidi ALSA backend](https://github.com/thestk/rtmidi/blob/master/RtMidi.cpp), used by python-rtmidi/mido, calls `snd_seq_port_subscribe()` in `MidiOutAlsa::openPort()` (lines 2975–3035), and errors if subscription creation fails. This is the concrete reason to test a live output connection rather than direct-address `aseqsend`; it does not itself prove the installed mido backend/version selected on the bench has identical behavior. The private ROM61 helper copy at `scratch/trio61-usbmon-cycle/capture-stimuli.py` changes both stimulus destinations to exact identity-resolved mido output names and sends each NoteOn, two-second hold and NoteOff inside one child process that keeps `mido.open_output()` alive for the entire pair. Child lifetime is bounded and tracked; SIGTERM enters its `finally` path to attempt NoteOff before closing the output. This remains a host-submission diagnostic and does not prove FM-1 consumption. No device operation was run.
