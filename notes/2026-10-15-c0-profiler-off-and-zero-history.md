# c0 profiler-overhead comparison and zero-history experiment

[verified: owner observation] A physical power cycle booted Lunar, but the
waveform remained very laggy and the audio distorted. Cold-boot musical
acceptance failed. A loader-started boot alone cannot explain this failure.

[verified: physical installation and independent transcript review] The
profiler-OFF comparison was installed from the ROM103 one-use campaign at
`/home/claude/fm1-c0-profiler-off-v2-20261015` on bench01. Two fresh 1 MiB
pre-write reads matched the prior c0 image
`c7afa08c1a66fe82458359cd0750133b755d7247e0904e6fedd18402f71418c6`.
All 4,096 final 256-byte page hashes match target
`1b6a0fc519d784cef96f1946a266fd7cf9d1785bb8f625a75c1a1238b447bbae`.
The install transcript has clean SG completions and SHA-256
`3932b3d452fb6211826ac5fd38c329218f5b219a17b9f9372887f5be3d8ada0e`.
Independent result: `scratch/c0-profiler-off-result/independent-readback.json`.
The sole FC0C received host=7, resid=16, info=1: ambiguous, never retried.
Lunar native USB device104 appeared afterward. Passive capture was armed
before reset. Both capture processes completed successfully (110-second
input-only telemetry and 180-second six-channel audio), and the device returned
automatically to mask-ROM USB device105. No notes or transport commands were
sent.

[verified: passive device telemetry] The OFF run produced 51,840 64-frame
blocks across 109.327 seconds of device uptime: **474.173809 blocks/s** with
**215.171001 underruns/s**. The required rate is 689.34375 blocks/s. This is
68.786% of the required production rate, versus the matched detailed-profiler
ON result of 464.450147 blocks/s: a 2.094% improvement. Detailed profiling
overhead therefore does not explain most of this measured shortfall. No
clock frequency or musical quality is established by these counter rates.
All eleven clock and eleven PLL snapshots were constant; detailed stage/IRQ/
engine profiling frames were absent as expected. Captured event-stream SHA:
`83b8a0343d879ee7c701f734aee966506ceaeb1c22cc3c96c60c9e4ecbdede16`.
Raw SysEx SHA:
`5d47ea93df823bf74762468be190091f650e74cfc9eb98aba99b1f4ebd90f3e3`.
Evidence: `scratch/c0-profiler-off-result/physical-capture/` and
`scratch/c0-profiler-off-result/audio-rate-summary.json`.

[verified: offline build, tests and preparation] The isolated resampler
experiment skips FIR arithmetic only when both input and intermediate
histories are empty, while advancing the same phase and mirrored ring state.
Source `a503b6ce340ab07a5efef0f1220fd144628dcad7` includes the additive restored
independent numerical oracle. Both full-state variants and that reference
test passed on the coordinator (three pytest cases). Its branch
`codex/c0-zero-pop-target-20261015` is backed up to GitHub with matching SHA.

All sixteen bounded Hera compile shards and the link passed. The app is 853,928 bytes
and leaves 6,716 bytes of the existing app budget; this is target code-generation
and fit evidence, not hardware speed evidence. Frozen receipt SHA-256
`71e4ac4d3e8c1ae45f7068cc8f6b347d9019c6b5bbece634e62209eef886e9f4`.
Raw export SHA-256
`e96e31f6692649ff33f6ad87e036d9575ab959f10b6a9b917ab2a76bdfe0ca35`.
The separately prepared private target is
`f3a9b18e3bead7171659b739545c1e191ac8724875d0b86ff3f953b021953f57`;
it changes fifteen sectors from the profiler-OFF target and preserves protected
bytes. Its template is deliberately unbound to a live ROM/fresh read. Handoff:
`scratch/c0-zero-pop-target-deployment/HANDOFF.md`.

[verified: offline review limits] Queue geometry matches four 64-frame stereo
blocks per 256-frame ALNK half. The 44,118/44,100 naming difference is about
0.041%, insufficient to explain the observed deficit. Thirteen linked engines
are a selectable catalogue; the app dispatches loaded sound slots. These
reviews do not prove the cause of starvation. Saved reviews:
`scratch/c0-queued-audio-review/review.md` and
`scratch/c0-all-engine-render-review.md`.

A separate exact-silence mix-bus limiter experiment is backed up at
`111dabe5eda07ef31c7ffa303a292864ee585ad8`, branch
`fix/2026-10-15@limiter-exact-zero-fastpath`. It is not integrated or built for
the target. Host equivalence and timing are recorded in
`scratch/c0-limiter-zero-review/`; no device benefit is claimed. This bus guard
is distinct from the configured master-effect limiter.

SAVE remains disarmed. Physical musical acceptance, release/installability
and the overall goal remain incomplete. Next: stage and review the isolated
zero-history candidate, then admit it only through a new ROM105 campaign with
fresh paired backups. ROM103 is consumed; its ambiguous reset must never be
retried.

## Resampler integration and additional review

[verified: review and host checks] Independent review of exact a503 against c0
found no blocking correctness issue; 192 focused resampler tests passed from
an isolated source archive. The review notes the default round-to-nearest
assumption and missing explicit subnormal test; it does not establish target
performance. Review: `scratch/c0-zero-pop-review.md`. The change was merged
into the working firmware branch as
`f1a2af9dd69d67b649bc0d4ee2dae836e53f3ff7`; origin branch SHA was verified
after push. This is not main/release integration.

[verified: source review; inferred frequency] The pinned SDK formula yields a
cached 360 MHz system value from the captured PLL words, but this does not
calibrate effective CPU execution frequency. Neither nominal 240 MHz nor
a misclock explanation is established. No PLL/power register changes were made.
Review: `scratch/c0-profiler-off-clock-misclock-review.md`.

[verified: source review] Skipping the configured master FX limiter on zero
input was rejected: its delay line, controls, envelopes, hold queues, filter
history and fade state still evolve during silence. This is distinct from the
separate stateless bus-guard experiment. No configured-effect shortcut was
implemented. Review: `scratch/c0-configured-limiter-silence-review.md`.

The ROM105 bundle remains offline pending complete runtime-path hash closure,
independent review, target file-only preflight and fresh paired current reads.
No new device operation or musical acceptance follows from these reviews.

## ROM105 staging and preflight corrections

[verified: remote file staging only] The original frozen 53-file archive
`011c3501ff19c3bebc5f722d73711b81e64d247fc30301584cef38861bd8ab65`
was staged privately at
`/home/claude/fm1-c0-zero-pop-target-a503b6ce-20261015` on bench01.
Its native and tools source staging checks passed. File-only preflight
refused before any device operation: it selected the native-export staging
helper (`build/stage_native_sources.py`, caac926d…) instead of the pinned
full-source verifier (`stage_native_sources.py`, 03cfcf36…). A separate
review also found the launcher rejected the nested paths present in its own
deployment inventory. Both corrections require an explicit old/new hash
overlay and independent review; the frozen archive is retained unchanged.

[verified: passive observation] USB port 1-1 still identified as ROM105,
`4c4a:8057`, bus 1, device 105. No new flash write or boot occurred during
this failed preflight. The installed image remains 1b6a… pending fresh paired
reads in a new one-use campaign.

[verified: recorded audio artifact transfer] The existing ROM103 WAV was
copied from bench01 for offline analysis, with matching local/remote SHA-256
`f74b09b88e46418888f2ef5bfe76c7435fcae78a3325259879c4bc5af03380b4`.
It was omitted from the earlier metadata-only capture tar. This copy does
not create new physical observations or establish musical acceptance.

[verified: correction and launch] Independent review and the coordinator's
seven overlay tests passed. The three-file correction index is
`c6aa27c48fb8ffb17ce1d0ad4d8f8b2e052ba539fa541ea055b3331c5a86a0fa`;
the guarded applier is
`464b8ea8a571e90d09cddea63faf9e06bc221513b830e1f991aaf8efb69250f0`.
It preserves original file bytes and leaves campaign/image pins unchanged.
Remote file-only preflight then passed. The one-use launcher passed its own
preflight and started PID 231468, campaign `rom105-c0-zero-pop-cycle`.
Fresh paired reads began; this entry alone does not establish completed
reads, installation, reset, or capture. Never retry this consumed launcher.

[verified: passive waveform analysis] The previous ROM103 recording has no
clipped input samples on channels 1/2. Whole-record RMS is approximately
0.00529/0.00546 full scale, with two unexplained bursts and no accepted notes
or scheduled musical stimulus. It cannot establish musical quality. Private
analysis: `scratch/c0-profiler-off-result/audio-capture-review.md` and
`audio-waveform-analysis.json` in that directory.

## ROM105 zero-history result: installed, recovery observed, performance FAIL

[verified: paired reads and independent transcript check] Fresh paired full
flash reads matched the expected installed 1b6a0fc5… image. The guarded
campaign wrote 15 transition sectors, directory 0x4000 last. Independent
verification matched all 4,096 final 256-byte response hashes against target
`f3a9b18e3bead7171659b739545c1e191ac8724875d0b86ff3f953b021953f57`.
Adapter transcript SHA-256:
`4c778d9c9e97736566be74d6d16b6bca5508da7acb61b3bdb88f496f6f762e09`.
The legacy result wrapper retains non-admission/mock wording despite
`simulated:false`; physical readback evidence is the independently checked
transcript, not those misleading wrapper labels.

[verified: single reset and passive capture] The sole FC0C response was
ambiguous (host7/info1/residual16); it was never retried. Native USB device106
appeared. Input-only telemetry completed rc0 after110s; KA6 audio completed
rc0 after180s. Port1-1 now identifies 4c4a:8057, bus1 device107: timed recovery
was observed. ROM105 launcher is consumed; never run it again.

[verified: device-time counter analysis] 108 diagnostic frames yield107 valid
intervals,109.616 device seconds and53,952 produced blocks. Throughput is
492.190921 blocks/device-second with197.142753 underruns/device-second.
Required rate remains689.34375. Relative to the matched profiler-OFF baseline
474.173809, this is a3.800% throughput improvement and still a performance
FAIL. No detailed stage instrumentation or accepted musical stimulus was
present. This run does not establish musical quality, exact CPU frequency,
or successful owner acceptance. SAVE stays disarmed; release goal ACTIVE.

Private evidence: `scratch/c0-zero-pop-target-result/independent-readback.json`,
`audio-rate-summary.json`, `physical-install/`, and `capture-metadata/`.
Next work: execution-rate calibration without PLL/power changes and bounded
review of remaining render/effects/bookkeeping cost; new hardware experiments
require fresh independently bound campaigns on observed ROM107.
