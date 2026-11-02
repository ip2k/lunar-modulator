# Shared renderer pipeline protocol — 2026-11-01

The finite two-work/eight-output transport now has one MIT implementation in
`firmware/common/renderer_pipeline_core.c`. It is included exactly once by an
explicit adapter translation unit, preserving the SDK compiler's opportunity
to inline the synchronization hooks and the existing hot/cold section boundary.
This is an implementation file, not an additional object to link alongside its
adapter. `renderer_pipeline_core.h` carries the common API and
`renderer_pipeline_port.h` describes the compile-time platform contract.
[verified: source]

`firmware/devkit/renderer_pipeline_sdk.c` retains task allocation, counted
semaphore wakes, IRQ save/restore, SDK reporting and public SDK entry points.
Its platform header preserves the prior volatile-word/csync convention. The
shared core retains sequence checks, callback order, separate work and output
retirement, finite lifetime, permanent refusal and late-callback retention.
`core_finish` reports a drained worker-exit acknowledgment; the SDK wrapper
continues to check faults and parent affinity before reporting success.
[verified: source]

The host fixture now compiles the actual shared source through two adapters:
the actual SDK wrapper with atomic mock primitives, and an independent host
polling adapter. It no longer generates a rewritten copy of the protocol.
Host control words use C11 atomics; there is no portable-thread claim for the
SDK's volatile words. A core compilation without an explicit port fails.
No SDK-free native CPU1 startup, register writes, cache implementation or new
hardware admission is supplied. [verified: source and host checks]

The extraction changes no app/engine arithmetic, event ordering, fixed-layout
admission, eight-voice policy, sample rate or slot/buffer capacities. It does
not turn the fixed mixed arrangement into a general interactive runtime.
Target ABI/code generation, interrupt legality, memory visibility and deadline
acceptance still require the target build/review and coordinator's separate
hardware gates. The previous 30-minute SDK/internal-DAC result remains evidence
for that prior artifact, not acceptance of a newly compiled image.

## Focused validation

The combined focused run passed 40 pytest cases (88 protocol-mode executions
across the two adapters and two sanitizer configurations). Four full engine
replay/VCF cases were deliberately excluded from this bounded run. [verified]

- `tests/test_devkit_renderer_pipeline.py`: normal and ASan/UBSan, both adapters,
  22 protocol modes each. Existing lease, output-full, refusal and late-callback
  cases remain; additions cover work-full backpressure, duplicate start/bind,
  wrong core, clock/tag wrap, lifetime expiry, malformed callback tag and finish
  with a held output lease or unharvested completion. Every successful output
  sample is checked against its expected tag/index value. [verified]
- Build selector, C/C++ public-header and missing-port refusal checks pass.
  [verified]
- Preparation fixtures carry/hash `firmware/common` and compile the actual SDK
  wrapper from the prepared source using its atomic host platform. [verified]
- DAC fixture normal and ASan/UBSan: nine ARM offsets and 198,468 blocks per run,
  exact PCM/order, zero drain/idle and fault refusal. Worker recovery/idle and
  pipeline bounds checks pass. These are host fixtures, not physical output.
  [verified]

Commands (use the project's Python environment):

```sh
python -m pytest -q -rA tests/test_devkit_renderer_pipeline.py
python -m pytest -q -rA tests/test_prepare_pipeline_devkit.py \
  tests/test_renderer_pipeline_dac.py tests/test_renderer_pipeline_worker.py \
  tests/test_pipeline_bounds.py -k 'not full_pcm and not vcf_main'
```

Full engine replays, vendor compilation and target timing were not run for this
bounded extraction. Replay-fixture edits only stage the new shared include
directory. No engine/app source was changed. Test products live under the lane's
ignored scratch directory and are removed after recording logs; no new
persistent cache or background service is introduced.

Rarefaction scope and Serena symbol lookup found `worker_step` on the identical
primary baseline. Their shared root was not switched to this isolated worktree;
absolute-path file inspection supplied the edit/reference checks. Missing target
compilation flags limit semantic indexing; neither tool proves the pi32v2 ABI.
