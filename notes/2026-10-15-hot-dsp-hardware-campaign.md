# Hot DSP campaign and target instruction decoding

[verified: completed physical campaign, 2026-10-15 UTC] The one-shot campaign
at `bench01:/home/claude/fm1-hot-dsp-f524e019-20261015/rom69-cycle` completed
programming of 210 sectors, with the app header written last, and full readback
matched target `e77cc3c12ba29dbc703f57dd3b3c775ea7aaf8254ecb943437ed9991ecd8c65e`.
The completed journal record hash is
`1790eb9042a18e93a8f4000aae0443914eb9b7ec9bd67bbeb5f6e3f650f395b8`.
Two fresh complete reads had matched baseline
`52d6846a1a57c253caa6b4ab4dc927761928271a603be13383961936f8b2420b`.
The single reset request returned an ambiguous SG completion (host=7, residual=16),
so the coordinator did not retry it. Native USB device70 (1209:0001) appeared;
the timed diagnostic returned to mask ROM device71 (4c4a:8057). The parent runner
exited on the ambiguous reset; this does not negate the completed installation
and separately observed boot. Never rerun the consumed ROM69 campaign.

[verified: completed passive recordings] KA6 captured 180 seconds, six-channel
48 kHz signed 32-bit PCM. Recorder exit was zero; the helper recorded
`passive_capture_complete`. WAV SHA-256:
`212b5a57eda81f3bce5f6cba7190b085aeab71e8d394d5273b48d445cce266cd`.
The input-only MIDI recorder completed its 110-second deadline with 55 diagnostic
and 56 render-profile frames. Events SHA-256:
`d6488ea816b57cfce5f510ad6fd77b1dde6318f346cadb043aa51dec88fbd4c6`.
Private copies and offline analyses are in `scratch/hot-dsp-result/physical/`.
No MIDI output/stimulus was sent. Neither receipt proves musical acceptance.

[verified: device-counter calculation, timer calibration assumed] Over 108.089
seconds of device uptime, production averaged 259.1198 blocks/s and underruns
430.2288/s, against the configured 689.34375 required blocks/s. The prior
70367650 run produced 248.8426 blocks/s: this is about 4.1% improvement, still
severe starvation. Maximum reported render time was 4835.67 microseconds against
a 1450.66 microsecond block budget, assuming the diagnostic 24 ticks/us scale.
Observed stack minima were 5888 user / 7720 system bytes, not worst-case bounds.
KA6 channel peaks were 0.9725 / 0.9897 full scale, with no exactly clipped samples;
this does not establish undistorted or acceptable sound. Clock/scheduling and DSP
investigation continue; do not release this image as working firmware.

The frozen candidate is from source
`f524e0193323aac4f5a0db1c08eed218f2e5a2fe`, with Event Horizon Showcase,
its companion SET, all thirteen engines and the selected effects. Target image
SHA-256 is `e77cc3c12ba29dbc703f57dd3b3c775ea7aaf8254ecb943437ed9991ecd8c65e`;
210 sectors differ from the paired baseline. The app is 853,108 bytes,
SHA-256 `76dc05e2cef3df7c7b2eee19db295bbf5877e83ba64386de47d1f1ad337f9654`.
The runner admits passive KA6 audio capture before its single boot attempt,
then input-only diagnostic telemetry. It must not retry an ambiguous reset.
The bounded diagnostic should return to recovery after approximately 120 s.

[verified: exact target ELF and vendor decoder] The pinned objdump needs
`-mcpu=r3`. Without it, the f524 ELF listing has 15,743 unknown instructions;
with it, there are zero, including decoded floating-point arithmetic. The ELF
SHA-256 is `6c2a4edc3db9301a1fc3c5d4d77d735e290efd3ea738744dd5031c4782fbaece`.
The separately decoded listing on Hera is
`/home/claude/mvave-fm1/scratch/pi32v2-float-codegen-review/r3.dis`, SHA-256
`ad3448b88c6c4d6709100f54d257779ad80ab5d633ddbe35307c0bbb918fa38c`.
The frozen campaign's original listing and its pins were preserved. Commit
`f999b29095ddfe5f206fb60dc47f28c5707d18b0` corrects future artifact generation;
the GitHub feature-branch SHA was verified equal to that commit. This establishes
instruction decoding and native floating-point code generation, not the calling
convention, running CPU frequency, or measured target speed.

[verified: source and host] USB and UART/TRS realtime transport reaches the
shared native app handler before channel filtering. FA starts from the beginning,
FC pauses and releases notes, FB continues. The five focused MIDI suites plus
artifact tests passed all 81 cases. This does not replace physical Start rewind
and TRS transport acceptance. MIDI Clock tempo synchronization remains separate.

[inferred: reviewed source, not measured throughput] The flash path repeats
whole pinned-evidence checks several times per page and synchronously persists
command intent/completion. That is a plausible contributor to long programming
cycles. No checks, durable logging, binding, or readback were weakened during
the active transaction. A future throughput change needs measured phase timings
and adversarial evidence-mutation coverage.

Next: inspect completed install/readback, single boot result, passive recording
receipts and device-counter rates against the earlier 70367650 baseline. Prepare
the separate 5c4502ee raw-clock diagnostic only with fresh runtime, candidate,
identity and paired-read admission. Audio starvation, SAVE, independent recovery,
full-song physical acceptance and browser release gates remain open. Goal ACTIVE.
