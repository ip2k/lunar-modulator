# Trio58 pulse and ingress audio review — 2026-10-15

[verified: offline WAV analysis] Hera's transferred six-channel capture is
150 s at 48 kHz, signed 32-bit PCM (7,200,000 frames), SHA-256
`87fd49ebee02aa0e4ab49bb6b56e17fd8099bb5da223fab0b42ed08dd937d48c`.
Analysis used only KA6 input channels 1 and 2. Peak magnitudes are 0.33765 and
0.34432 FS with no clipped samples. The built-in pulse's 10 ms envelope is
above −54 dBFS from 4.27 to 6.34 s on both channels. In the central 4.3–6.2 s
span, the lowest 10 ms RMS is −21.34/−21.17 dBFS; there are no central
10 ms dropouts. Pulse RMS over 4.27–6.34 s is −19.18/−19.01 dBFS. The idle
9–14 s window is −65.87/−65.44 dBFS. Thus the pulse is about 46.7 dB over
idle on both channels.

[verified: offline WAV analysis] A 1.5 s Hann spectrum from 4.6 s gives the
same prominent components on both channels: approximately 130.41, 262.26 and
525.23 Hz. The C4 component is about +4.2 cents from 261.626 Hz, with a
strong octave-related component near 130.4 Hz. It is not a pure sine or a
calibrated tuning test. No sample clipping or long central envelope dropout
was found; sub-10 ms dropouts and audible/perceptual quality were not assessed.

[verified: capture timestamps plus offline WAV windows] The capture helper
logged `audio_capture_ready` at host wall time 1792029007.9758964 and the
stimulus epoch at 1792029009.512207, a 1.536 s offset. The six TRS events
(pitches 60/64/67 at stimulus elapsed 15/19/23 s) therefore fall at about
16.545/20.541/24.541 s in the WAV; the six USB events at 38/42/46 s fall at
39.541/43.541/47.541 s. Corresponding 2.2 s windows remain at idle level:
TRS RMS −65.89/−65.82/−65.84 dBFS on channel 1 and −65.46/−65.36/−65.42 on
channel 2; USB RMS −65.91/−65.83/−65.86 and −65.47/−65.43/−65.47. This is no
clear acoustic response to those submissions. Host sends with return code
zero are not proof of MIDI receipt.

[verified: retained diagnostic telemetry] `scratch/trio58-results/events.jsonl`
contains 100 validated diagnostic frames across about 99.72 s; its SHA-256 is
`c500cc9f7cef408cfa58bf4e178be0b5e6c92e363d3dd1c05e7d527564790d41`. Across
the capture, `usb_messages`, `uart_bytes`, `accepted_noteons` and
`rejected_messages` remain zero. `audio_underruns` is already 84 in the first
frame and remains 84 throughout, so no additional underruns were observed
after that first sample; it does not establish that the initial 84 occurred
during this recording. `produced_audio_blocks` rises steadily (about 696 per
roughly 1.00 s after startup, versus 689.34/s nominal at 44,118 Hz and
64-frame blocks). Telemetry samples and WAV are not sample-clock synchronized;
alignment above uses helper host wall timestamps and has recorder-start
uncertainty.

[verified: offline cross-capture comparison] Trio56's corresponding pulse was
3.46–5.53 s, with RMS −19.08/−18.92 dBFS and spectral components near
130.41/262.25/525.22 Hz. Trio58's pulse is about 0.81 s later in capture-relative
time, but its level differs by less than 0.1 dB and the measured spectral
components are effectively the same at this analysis resolution. The onset
offset is not evidence of changed firmware timing because each recorder start
was not tied to the app's readiness clock. Both captures contain stronger,
unexplained activity around 1–2.6 s and 120.5–122.1 s; it is not attributed to
the pulse or MIDI stimuli.

Telemetry source interpretation is documented in
`notes/2026-10-15-trio-telemetry-capture-interpretation.md`: `U` counts USB
messages returned by `midi_get`, `B` counts UART bytes consumed by the parser,
and `N` counts filtered accepted Note Ons before the app callback. All being
zero narrows this run to no ingress observed at those counters, but cannot
distinguish transmitter/path failure from parser or timing conditions before
the counters. This does not prove the jack is electrically silent or identify
a single root cause.

The WAV and private analysis scripts stayed outside Git. DSP ran on Hera in a
networkless, read-only container with one CPU, 2 GiB memory/swap and 128 pids.
Results are signal measurements only, not owner listening/perceptual
acceptance, electrical MIDI-reception proof, firmware recovery proof, or
release acceptance.
