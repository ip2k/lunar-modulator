# Hot DSP campaign and target instruction decoding

[verified: live coordinator, 2026-10-15 04:52 UTC] The one-shot campaign at
`bench01:/home/claude/fm1-hot-dsp-f524e019-20261015/rom69-cycle` is running.
Its two fresh complete reads matched baseline SHA-256
`52d6846a1a57c253caa6b4ab4dc927761928271a603be13383961936f8b2420b`.
The journal records installation in progress; this is **not** a completed
installation, readback, boot, or audio acceptance claim. Do not invoke the
consumed runner again. Observe its existing process and transaction journal.

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
