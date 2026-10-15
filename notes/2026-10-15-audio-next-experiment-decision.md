# Audio experiment priorities after the Hall measurement

[verified: source review] The audio producer already fills available queue
capacity. An empty queue causes silence without advancing its read index;
it does not replay an old block. The measured 498.453 produced blocks/s versus
689.344 required is a sustained deficit. Increasing buffer depth alone cannot
resolve it. Private review: `scratch/audio-scheduler-buffer-ownership-review.md`,
SHA256 `4fb0a55c6639c13d7258a1b56afbebb9d0f2ac270cfe1055fa37b5f84a170a64`.

[verified: source review] Stopped transport still dispatches four configured
sound slots and Hall plus limiter. Inactive voice kernels are already skipped;
smoothing, LFOs, delay history and resampler phase still advance. Transport STOP
is not a certificate that this graph can be bypassed. Private review:
`scratch/stopped-EH-engine-quiescence-review.md`, SHA256
`95875cd8ef4ddc6bf3740505a5554dee9cf21b4170d075b2ddccb03b6900c11f`.

[verified: linked-artifact review] The e42 Drums RenderBlock experiment leaves
8,832 bytes below the dedicated DSP RAM limit. Its 3,104-byte RenderVoice plus
six separately linked model render bodies total 8,822 bytes before remaining
models, helpers and alignment. That is not a complete closure that fits. Private
review: `scratch/native-hot-dsp-ram/render-voice-closure-review.md`, SHA256
`7d1deabdd59455774121292fec9b7bf83427d896ff3de8048ccf1655b16b1f03`.
The new RenderVoice child changes inlining and therefore needs its own linked
size/callee review; the e42 sum must not be reused as its fit calculation.

[verified: independently reviewed offline build] Child source
`6dbed50ece518514bc41d0ac241ac3cbbae0123e` completed all 16 Hera compilation
shards and link, with 107 focused checks. Worker reports app 855,688 bytes,
RAM DSP 15,360 bytes, and RenderVoice 998 bytes in RAM, with model calls still
in XIP. Frozen bundle SHA256
`f557f09c6188324202b14e029c13613a9bec7517e596f2d426352f67b9ac9294`.
Independent review checked the exact source/tree, frozen receipt, ten output
hashes, RAM extent and call sites; 21 policy/candidate checks passed. Review:
`scratch/drums-rendervoice-ram-independent-review.md`, SHA256
`ad0b91481b475929a345e82a5433e152748791b2fec407162c0e889984de83c0`.
Integrated as `adb8c4f5`; no deployment package or hardware speed claim follows.

[verified: root linked-code inspection] The exact e42 vendor disassembly
contains software double helpers, but their presence alone is not evidence of
a hot-path bug. Direct call sites include resampler construction, formatting
and math-library internals. No arithmetic replacement is justified from this
inventory without tracing an active render caller and measuring its cost.

## Decision and remaining evidence

[inferred] Prioritize optimizations that reduce active-audio work. A Hall
startup-silence shortcut would improve an idle diagnostic but would not repair
Event Horizon playback once sound begins. Any silence shortcut must preserve
control/modulation state and prove exact history emptiness; useful re-entry
after tails also needs a cheap certificate and an active-path overhead check.
The offline invariant review rejects the startup-only optimization for this
milestone: exact re-entry would require checking 49,152 bytes of rings or
maintaining nonzero-cell counters on active writes, without a demonstrated
benefit. Review `scratch/hall-zero-history-review/review.md`, SHA256
`375e8fbba34c78738cb6954f215be54c16a04de4456f2bfbff19b34526788fa8`.
A separate active Hall code-generation review is assigned. No production Hall
silence shortcut is implemented.

The RenderVoice child passed independent review and was integrated; a physical
campaign is deferred. Its inactive-voice bypass means that an
active-drum measurement and idle negative control are needed to interpret it.
Do not spend a flash campaign expecting this alone to fix stopped throughput.

[verified: acceptance limit] Latest physical throughput still fails. Owner
cold-boot listening failed. All-thirteen/default full song, persistence,
interrupted-write recovery, selectable web installation and public release
remain required. SAVE and autoplay remain disarmed in diagnostics. No device
write, reset or clock change was performed for this decision review.
