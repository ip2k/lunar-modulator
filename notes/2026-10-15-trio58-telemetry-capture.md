# Native58 installation and telemetry capture

[verified] The one-use ROM57 cycle completed all 199 planned sectors and a
complete 1 MiB readback matched target SHA-256
`222164721a323bce80a3fd3a0444588c93ef734e577940ddb80b7432402d1ab6`.
The transaction journal is complete with no outstanding intent. The sole
FC0C reset produced an ambiguous reply and the runner exited unsuccessfully;
no retry was sent. Independent enumeration observed native USB device58
(`1209:0001`, physical `1-1`) with Lunar Modulator branding. After its bounded
diagnostic runtime it returned to ROM device59 (`4c4a:8057`) without an owner
power cycle. This proves this diagnostic's timed recovery transition, not
app-independent recovery from arbitrary corruption.

[verified] The capture helper and both children are terminal. The telemetry
recorder exited 0 after 100 seconds with 100 valid frames; arecord exited 0
with the requested 150-second, six-channel, 48 kHz S32_LE recording. Private
bench evidence is under
`/home/claude/fm1-trio-telemetry-9ec846-20261015/diagnostic-audio/`.
The WAV was copied privately to Hera and hashes match on both hosts:
`87fd49ebee02aa0e4ab49bb6b56e17fd8099bb5da223fab0b42ed08dd937d48c`.
No recording or firmware binary is committed.

[verified] Coordinator analysis of the complete telemetry gives:

| Measurement | Observation |
| --- | --- |
| Device uptime covered | 1,006 through 100,963 ms |
| Audio underruns | 84 in every frame; no observed increment during sampling |
| Produced blocks | 212 through 69,116 (68,904 additional blocks) |
| Maximum render time | 27,625 ticks / 24 = 1,151.04 microseconds |
| Maximum draw time | 154,136 ticks / 24 = 6,422.33 microseconds |
| USB decoded input messages | 0 throughout |
| Consumed UART bytes | 0 throughout |
| Accepted note-ons / rejected messages | 0 / 0 throughout |
| Master ADC | 1,023 throughout |
| Minimum reported user / system stack margins | 15,064 / 7,724 bytes |

[inferred] The render maximum is below the nominal 64-frame deadline of
1,450.66 microseconds at 44,118 Hz for this content-free Trio diagnostic.
It does not prove full-song/all-engine workload acceptance or exclude shorter
unobserved timing faults. The initial 84 underruns predate the first sample;
starting I2S before application initialization is a source-backed possible
cause, not a demonstrated diagnosis. Stack margins are sampled observations,
not complete worst-case stack proofs.

[verified] The helper submitted three TRS and three USB notes with successful
host process exits, but telemetry reports no decoded input. Consequently those
commands are not accepted MIDI-path tests. A subsequent isolated host loopback
using bench `aseqsend` 1.2.14 and `aseqdump` on Midi Through 14:0 received the
exact note-on 60/64 and note-off 60/0 sent by the same command syntax. This
rules out the claim that this installed aseqsend supports only SysEx; it does
not establish delivery to either physical destination. USB OUT packet/URB
capture and firmware receive-state review are the next discriminating checks.
The bench already exposes usbmon; no module/configuration change was needed.

[verified] Evidence hashes: telemetry JSONL
`c500cc9f7cef408cfa58bf4e178be0b5e6c92e363d3dd1c05e7d527564790d41`,
helper JSONL `fadc0d93b1bd5c7194453f21f978ff952358b2094aedf6190291818c8da96457`,
coordinator analyzer JSON
`c3012aaf2633b46b009440dc3792fbb38ffe6a900b33a857d2721ca7805e07f6`.
The recorder uses its own monotonic origin. Helper wall timestamps bound
capture startup, but do not establish exact WAV sample-zero alignment.
Analogue waveform review remains separate. No screen, listening, MIDI,
full-song, persistence, independent recovery or release acceptance is claimed.

SAVE remains disarmed. Preserve the consumed ROM57 campaign; any further
device operation must identify ROM59 and use a newly reviewed campaign.
