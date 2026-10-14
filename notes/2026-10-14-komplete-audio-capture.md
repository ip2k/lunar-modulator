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
