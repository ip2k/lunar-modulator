# WebKit frozen audio clock investigation — 2026-10-09

[verified: GitHub logs] PR #125 head `540ed3cf0008cc2c3a01e0eaf913339d7827319c`,
CI run `38016847016`, WebKit job `114108904554`, fails the panel-follow
latency and panel history checks. Its observer reports 60 frames / 960 ms,
`AudioContext.currentTime` fixed at `0.7169160997732427`, state `running`,
no main/editor port observations, loading false, no pending changes or
inflight work, and the original/current row still connected and unchanged.
Reach, Map and editor-v1 subsequently pass. This is shared browser/audio
path evidence, not proof of a CSS, Picks or semantic configuration regression.

[verified: source] The ordinary worklet returns true from every `process()`
path and connects to the context destination. Encoder input is handled by
its main port, while change publication occurs in render callbacks. The page
resumes a held context on input only when its reported state is not running.
A frozen clock with a running state does not establish why callbacks or
message delivery paused. No production fix is justified by these observations
alone; the 12-frame acceptance, 60-frame observation maximum and zero-event
storm gate are preserved.

[reported: upstream] WebKit [bug 296843](https://bugs.webkit.org/show_bug.cgi?id=296843)
records GStreamer/PulseAudio silent-buffer playback failures and was fixed in
September 2025. It is a candidate comparison, not identification of this
October 2026 failure; its original idle duration and symptom differ.

[verified: tooling] Rarefaction oriented `start` at the primary workspace,
with `powerOn` and the expected context/worklet helpers; Serena found the
same symbol. Shared project selection was not changed. Exact investigation
worktree source was read directly; those MCP results do not prove this
worktree's index or coverage.

## Reproduction checkpoint

Baseline is main `67d5e12dee561abca5d0a2256fec85d75522a806` on
`fix/2026-10-09@webkit-audio-lifecycle`. A bounded independent run uses aeon's
existing Playwright 1.63.0 installation and image
`mcr.microsoft.com/playwright@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27`,
a private container and PulseAudio null sink at 48 kHz, two CPU quota,
4 GiB memory and `docker-batch.slice`. It runs the unchanged 30-second
external audio test followed by the unchanged editor UI test. GStreamer
category diagnostics are enabled for the UI run. Files persist at
`/home/claude/mvave-fm1/webkit-lifecycle-20261009/`; current command is running.
No hardware, shared service restart, MCP activation or upstream posting occurs.
