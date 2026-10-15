# Trio56 pulse waveform review — 2026-10-15

[verified: offline WAV analysis] The private six-channel WAV is 48 kHz, signed
32-bit PCM, 7,200,000 frames (150 s), SHA-256
`0ca618c0f183bc78deba5fe86db26c9b77e2386e8a47b4098792ad0a3b88af05`.
Only KA6 input channels 1 and 2 were analyzed. A 10 ms RMS envelope with a
−54 dBFS threshold (about 12 dB above the measured idle median) identifies a
capture-relative event from 3.46 to 5.53 s on both channels. The 3.7–5.2 s
central region has no 10 ms block below that threshold. This excludes long
envelope dropouts in that interval, but not sub-10 ms gaps or modulation.

[verified: offline WAV analysis] In a 3.5–5.4 s pulse window, RMS is −19.08
dBFS on channel 1 and −18.92 dBFS on channel 2; the 9–14 s comparison window
is −66.14 and −65.70 dBFS. Peak magnitude over the full recording is 0.33885
and 0.34535 FS; the pulse-window peaks are 0.28989 and 0.29545 FS. Neither
channel has clipped samples. A 1.5 s Hann spectrum inside the pulse has strong
partial estimates near 130.41, 262.25 and 525.22 Hz (the C3/C4/C5 octave
series); the C4 partial is about +4 cents from 261.626 Hz. This is not a pure
sine or a calibrated pitch measurement.

[verified: capture log plus offline audio windows] The recorder's ready event
is at host wall time 1792029007.9758964. The app's one-shot C4 is scheduled
relative to its own audio-ready origin, which is not synchronized to the
recorder's first sample. Therefore the 3.46–5.53 s WAV interval is only a
capture-relative event, not an exact app onset/off measurement. The historical
install note reports three host TRS note submissions at capture-relative
16.473, 20.473 and 24.473 s, then USB submissions around 58.81, 62.82 and
66.83 s; those intervals showed no clear increase over idle. Host return code
zero does not prove device receipt. Other stronger audio events around
1.02–2.64 s and 120.43–121.65 s remain unexplained and are not attributed to
the diagnostic pulse.

Analysis was run offline on Hera in a networkless, read-only container with
one CPU, 2 GiB memory/swap and 128 pids. The private analysis scripts and WAV
remain outside Git. This measurement is not owner listening/perceptual
acceptance, electrical MIDI-reception proof, or a diagnosis of the audio path.
