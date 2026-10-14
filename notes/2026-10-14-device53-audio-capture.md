# Device53 audio and MIDI capture — 2026-10-14

[verified] Owner connected Komplete Audio 6 MIDI OUT to FM1 MIDI IN and moved analogue cables to inputs 1/2, with FM1 master and KA6 preamps at 100%. UART input is not wired in the installed application; a separate implementation is pending.

[verified] Private bench artifacts: `/home/claude/fm1-device53-audio-20261014` on bench01, outside Git. Fresh allowlisted paired full-flash reads both produced 1,048,576 bytes with SHA256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`. Read manifest SHA256 `2a5191ffefaf46de6c8ba7faabc0686ae436496c6564514ea82ca33b2db1f2ee`; read-command log `9a76b4f603d2b2477e283ea225a604e7d59ab4cb79bb1ee2c75c1cfe3e68d0a7`. No flash write occurred.

[verified] Fresh device53 boot preflight passed. One FC0C argument-1 boot command was attempted at Unix 1792019756.6439753. Completion was ambiguous (status0, host7, residual16); the attempt was consumed without retry. Native 1209:0001 appeared as device54, sound card3, ALSA sequencer28:0. Passive enumeration at 23:18:07 UTC showed ROM4c4a:8057 device55. This timed return does not prove independent recovery. Device53 campaigns are consumed; another command needs fresh device55 admission.

[verified] `inputs12-note-test.wav`: six-channel S32_LE, 48kHz, 6,960,000 frames (145 seconds), 167,040,044 bytes, SHA256 `fd7165bf1f8cbfa0add5fc2267895ef45b65effe41f434e3f4b57e9b3d42c7a9`. Recorder log contains no overrun report. Capture began at Unix1792019756.0015013.

[verified] Initial aseqsend calls incorrectly used `-s` with a hex string; that option names a file. Despite process return0, stderr reported file-open failures. Those attempts sent no notes and are excluded. The original log is retained. Corrected sends used a quoted space-separated hexadecimal argument, all with empty stderr: C4 on/off at1792019794.8114629/1792019796.8136344; E4 at1792019797.8159244/1792019799.8181732; G4 at1792019800.8204224/1792019802.8226383, channel1 velocity80. Corrected log SHA256 `de1154679b7793df97891eb127bccb2e77d9730d20a11e31c52a2794fd101eae`.

[verified] One-second input1/2 windows before/during/after those corrected notes stayed around -64 to -65 dBFS RMS, with peaks below0.0027FS and no samples at or above0.999FS. No clear note-energy increase was observed. This is a measured capture result, not proof of a particular MIDI/rendering fault or a complete clipping check over the entire recording. PLAY was not sent.

[verified] Separate FM1 USB audio capture `fm1-uac-note.wav`: stereo S16_LE48kHz,384,000 frames,1,536,044 bytes, SHA256 `46ea71da247c66a543a722efb94bc0008c5448bc6b03da650b8d818627c196ac`. All samples in the first seven seconds were exactly zero. Capture started1792019856.5050266; a verbose USB C4 send at1792019857.5051808 reported Sent:3bytes, release1792019859.5074477. Event log SHA256 `b6a94c72b070b5b5c854b11bab753b8d3e789a0b3ffae2a34c9e8747a1159986`. USB audio capture adds device load, so treat this as a separate condition. Host send success does not prove device MIDI decoding.

Next: integrate/review UART parser and input counters, instrument render/draw/underflow evidence, prepare a concrete fresh image with preservation/rollback verification, and compare USB/TRS MIDI with measured audio. SAVE, release, browser installation and independent corrupted-app recovery remain unaccepted. Goal ACTIVE.
