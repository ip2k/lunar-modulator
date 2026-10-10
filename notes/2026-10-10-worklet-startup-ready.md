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

Pending: bounded actual startup/restart smoke, unchanged strict 30-second storm
and external loopback for Chromium/Firefox/WebKit on LAN; actual build-record
regeneration and full exact-head CI by the parent integration stream. The current
Wasm is the exact PR142 artifact retained for runtime observation, not a new
source-hash acceptance record. No tolerance, baseline, drain or zero-underrun
gate has changed. No claim about hardware or human listening.
