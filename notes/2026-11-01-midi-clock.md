# Browser MIDI realtime input — 2026-11-01

Personal/non-commercial Lunar Modulator work. Coordinator task: complete missing
S10 browser input from base `a1b7823b`; no device, USB, MIDI output, native build,
or hardware operations. Branch `feature/2026-11-01@midi-clock`; own checkout
`/Users/likwid/.codex/worktrees/lunar-midi-clock-20261101`.

## Result and checks

- [verified: source] `onMidi` accepts exactly one-byte F8/FA/FB/FC before MIDI
  learn, rejects malformed/short channel input, and retains channel/realtime
  arrival order through the same worklet port.
- [verified: source] `fm1w_seq_realtime` gates on the native saved set `link`
  setting. Link off consumes realtime without calling the core (which otherwise
  changes tempo/position even with Link off). Link on uses the existing app/core
  realtime parser and its event-room check; there is no new clock.
- [verified: Node tests] Worklet native-backpressure retry preserves message
  order and applies every retained message once. Retry occurs before each native
  64-frame render block. Normal arrival jitter remains up to one 128-frame
  quantum; backpressure can defer longer. No timestamp interpolation added.
- [verified: Node tests] Retry queue and startup queue each have a 1024-message
  bound. Overflow clears pending input, releases notes (or schedules a reset on
  startup), and reports a visible error. Disconnect clears stale inputs, releases
  notes, and sends native Stop when Link is selected. Power-off destroys its
  AudioWorklet; new init clears its retry queue.
- [verified] `node --test sim/web/test/midi-realtime-routing.test.mjs`: 5 passed.
  `node --check` for app/worklet/runtime test, `bash -n sim/web/build.sh`, and
  `git diff --check` passed.

## Required next dependency

The coordinator requested one final WASM rebuild on the merged integration tree,
shared with the DX7-bank export lane. No generated binary/hash was edited here.
**This source branch is not release-ready until that actual rebuild passes.**
`build.sh` now runs the routing tests and `test/midi-realtime.mjs`, which requires
`fm1w_seq_realtime` in the actual rebuilt module and checks default internal
clock independence, linked tempo/follow, Start vs Continue, Stop, note-offs and
native dropped events. Runtime assertions are pending that rebuild; they are not
reported passed. Command after rebuild:

```
node --test sim/web/test/midi-realtime-routing.test.mjs
node sim/web/test/midi-realtime.mjs sim/web/www/fm1.wasm
```

Shared integration files: `sim/web/src/fm1_web.c` (new wrapper beside seq_text),
`sim/web/mk/sim.mk` (new export), `sim/web/build.sh` (new tests), README limits.
DX7 lane owns separate export functions and files.js/shadow.worker.js.

## Tool coverage and lifecycle

[verified] Rarefaction status selected main absolute checkout. Its attempted
external-worktree project was rejected because it is outside the fixed root.
Bounded `onMidi` orient/scope on exact-base main found the real attach caller;
Serena find_symbol matched that function and `fm1w_seq_text` to source. Serena
was already main-selected; no global root switch was made. C named Rarefaction
query hit its 200-file search limit and returned no result; source inspection
and Serena were used, without claiming complete C caller coverage. No graph
build was requested or performed.

No new scratch/build products, containers, downloaded data, or hardware state
left behind. Owned worktree retained for parent integration; parent removes it
with `git worktree remove` after integration. Mac Data volume had 1129 GiB free
at start (500 GiB floor satisfied).
