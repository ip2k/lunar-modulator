# Connect the worklet after initialization

[verified] A bounded actual-page probe measured 6–7 ms of synchronous
firmware/default-chain/catalog setup after instantiate, exceeding the
2.902-ms quantum at 44,100 Hz. The original page connected the node before
that work completed. Initialization completed and screens advanced with
connections gated until ready. The timing and failed interception probes are
preserved in `2026-10-10-chromium-startup-localization.md` and its data receipts.
Both timing variants had zero published events; the original CI event remains
unassigned.

[verified] `connectOnReady` now installs the existing message handler and connects
destination/analyser only on the current node's first ready. It ignores
messages from replaced nodes or closed contexts. Suspended contexts can connect;
the original gesture-driven wake and held-context handling remain intact.
No context suspension or ready-await is introduced. Initialization errors still
reach the page without joining outputs. Four focused ordering/error/stale/closed
regressions and the existing 13 diagnostic helpers pass (17 total).

[verified] The bounded LAN batch tested runtime/source checkpoint
`08c9f204f05c7d267e2bf453331bdf6dc54c5b37`, one attempt per test, with
4 CPUs/2 GiB in `docker-batch.slice` and a private Pulse null sink using
`norewinds=1`. Chromium 153, Firefox 155 and WebKit 26.6 each passed two actual
power cycles: destination/analyser connected after ready, the context ran, and
the screen and audio clock advanced. The 17 Node helper tests and 36 editor-unit
checks passed. CI now invokes this actual startup/restart regression as its own
step, with reports under the existing browser artifact directory.

[verified] The unchanged strict 30-second storms passed with 7,302 / 7,218 /
3,757 edits (Chromium / Firefox / WebKit), zero rejected codes or resyncs,
905 telemetry messages each, and valid 1,115-byte binary snapshots. Chromium
reported zero underrun events; Firefox/WebKit do not expose that counter.
External loopback passed respectively 32.012 / 32.006 / 32.006 active seconds,
with zero nonfinite samples, stereo mismatch, silence or bad periods. Each
browser completed eight project/Sound 2 A/B swaps without stopping transport.
The complete Chromium trace saved 88,050 events with zero drops and zero named
SyncReader timeouts, glitches or FIFO shortages/overruns. These are observations
of this instrumented run, not proof that tracing sees every browser glitch.
Metrics, unsupported fields, provenance and raw-evidence hashes are preserved in
`data/2026-10-10-worklet-startup-ready-browsers.json`. The container has stopped.

[verified] Fresh native/glibc, static musl and Emscripten builds completed in an
isolated aeon directory from `c44a808d`, capped at 2 CPUs/4 GiB with two compiler
jobs. All 108 parity scenarios passed, all 108 exact against JS and musl; 104
screens use glibc and four use musl, with zero accepted pixel differences.
The full screen sweep rendered 4,658 screens with zero layout faults. Metadata,
DX7 and edit parity checks passed; the build's 30-second storm reported zero
late quanta and resyncs. The rebuilt Wasm is byte-identical to the previous
PR142 artifact (`4667498f…76ec`, 1,561,532 bytes). The regenerated record's
engine/SIM input hashes match the actual tree; `CI=true` build-record pytest
passed without stale warnings. The browser/helper/diagnostic files changed here
are outside `source_hash.py`'s binary input list; unchanged input hashes do not
validate those files. The previous localization note is corrected accordingly.
Build provenance, measured results and raw-evidence hashes are in
`data/2026-10-10-worklet-startup-final-build.json`.

Pending: full exact-head CI and root review/integration. No tolerance, baseline,
drain or zero-underrun gate has changed. The original CI event remains
unassigned. No claim about hardware or human listening.
