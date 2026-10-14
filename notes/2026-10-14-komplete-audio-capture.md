# FM1 analogue capture preparation

[reported] Owner confirms individual notes were bad-sounding and sluggish before
PLAY, and connected FM1 audio to Komplete Audio 6 inputs 3/4 on bench01. MASTER
is around 3 o'clock (owner estimates 75%); keep this position for comparisons.
No request to alter its setting has been made.

[verified] Passive enumeration sees Native Instruments 17cc:1001 at bus1/device51,
ALSA card K6/device0. Capture hardware accepts six interleaved S32_LE channels;
`/proc/asound/K6/stream0` reports 24 significant bits and rates 44100, 48000,
88200 and 96000 Hz. A three-second 48000 Hz six-channel WAV capture completed
without a reported ALSA overrun. Channels 3/4 are zero-based indices 2/3; retain
the six-channel original before extracting a listening copy. Physical input
assignment follows the owner's wiring report and still needs signal validation.

[verified] Private bench evidence (not committed):
`/home/claude/fm1-audio-capture-20261014/rom-baseline.wav`, SHA-256
`c44fa0457e603bf4225add4121430cb2f7f61a04cec9a0aaf7ddcacdf277cdaf`.
144000 frames, six channels, four bytes per sample. Capture log is adjacent.
ROM 4c4a:8057 device50 was present; this is capture-path evidence, not a Lunar
playback recording. Inputs3/4 normalized peak was 0.05409/0.05368, RMS
0.00658/0.00675. Nonzero background does not establish musical signal, clipping,
noise origin, or firmware behavior.

The proven capture command is:

```sh
arecord -D hw:CARD=K6,DEV=0 -f S32_LE -r 48000 -c 6 -d 3 -t wav OUTPUT.wav
```

For the next separately admitted boot, start a bounded recording before boot,
preserve the boot timestamp and recording stderr, then correlate note-only and
PLAY intervals with firmware render/draw maxima and missing-block counters.
Do not claim a clean capture if ALSA reports overruns. Recording through the
external interface avoids intentionally enabling FM1 USB Audio capture.

[inferred] Bad notes before PLAY do not isolate one synth's workload: the loaded
project's configured sound slots, inserts and master effects continue through
`render_sounds`/`fm1_app_render` while transport is stopped. Compare against the
proven smaller Trio configuration before attributing the failure to song events.
No FM1 read, reset, flash, MIDI, power or boot command occurred during this
capture preparation. Device48 campaigns remain consumed; device50 needs fresh
admission before any further boot.

## Recorded device50 repeat (23:01 UTC)

[verified] The separately reviewed device50 adapters completed 8,757 allowlisted
commands and two full 1 MiB reads, both matching target
`145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`.
Private campaign root: `/home/claude/fm1-device50-audio-20261014`.
Read campaign SHA `ee708999caa9fddec689893aa15db57736f3ce577bfeb043f9cdd35ee780884a`;
manifest SHA `2d57bd254bbec629b883205ec922320af435a8ee52f4dbaebddecb9509680472`;
command transcript SHA `1d6be4e21062160fe2c78679007f7fd1fce1bb666837e4bc172d599235d48c2a`.
Fresh same-connection boot preflight passed. One FC0C argument-1 request was
issued at approximately Unix `1792018916.1296802`; completion was ambiguous,
latched and not retried. Boot campaign SHA
`17ae91e3304deced5d6818042dda044b30e8e11282d8939ef6d73c5cac15ca89`.
Native USB `1209:0001` then appeared at bus1/device52. No flash programming.

[verified] A bounded 145-second K6 six-channel recording started at
23:01:54 UTC, before the boot request. Its path is
`/home/claude/fm1-audio-capture-20261014/device50-note-test.wav`; retain the
adjacent `.log` and `.started` files. After confirming the fresh USB identity,
sound-card sysfs path and ALSA sequencer port 28:0 (Felucca MIDI 1), three
note-on/off pairs were sent: notes 60, 64, 67, velocity 80, two seconds each
with one-second gaps. First note-on Unix `1792018938.0071669`; final note-off
`1792018946.0404625`. All six aseqsend processes returned zero, which proves
host submission rather than device reception or audible quality. Exact times
and messages are in `device50-midi-notes.jsonl` beside the recording.
No PLAY message was sent. MASTER remained at the owner's reported 3 o'clock.
The currently installed image predates the new R/D/U footer; this recording
cannot supply those counter values. Device50 read and boot campaigns consumed.

[verified] Recording completed: 6,960,000 frames, 48,000 Hz, six S32_LE
channels, 145 seconds; SHA-256
`97f2bff5bff2be35b5ce940429ffa45673764c5613e8b678fd8375550233814c`.
ALSA stderr contains its format banner and no overrun/error. At 24.2, 27.2,
and 30.2 seconds (one-second windows within the submitted notes), channels
3/4 RMS is only approximately 0.000024–0.000025 of full scale; peaks remain
below 0.000112, with no samples at or above 99.9% full scale. Channels1/2
are similarly quiet and channels5/6 zero. These windows do not establish a
received/sounding note, an audio glitch, latency, or the cause of the owner's
earlier audible failure. Do not request MASTER reduction on this evidence.
MIDI delivery and the musical signal path require independent confirmation.

[verified] Passive 23:04:02 UTC enumeration showed ROM `4c4a:8057` at
bus1/device53. Timed return required no physical power cycle; this does not
prove app-independent recovery. No later device command has been issued.
Local ignored evidence copy:
`scratch/audio-capture-20261014/device50-note-test.wav`, with note log and
an unnormalised stereo inputs3/4 excerpt `device50-inputs34-notes.wav`.
