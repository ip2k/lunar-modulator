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
