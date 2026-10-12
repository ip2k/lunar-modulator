# Four new showcase exact runtime and browser receipt

All four source assets at18a301853c31f3885339c3cfa4b4f9c6fdfdb6f0 passed native/Wasm full-song and Chromium153.0.8010.12 workflow. Raw runtime.json contains exact asset/module hashes, memory, zero repairs/skips/drops, expected complete stopped durations, roundtrip equality and native results. browser.json verifies listing, playback, Save download and fresh Open equality, no exceptions.

Isolated aeon stage /home/claude/mvave-fm1/showcase-18a30185. Generic harness source346d416a; browser catalog source9adec4f5 with only Afterglow/Event paths substituted to new -showcase files. No UI engine changes. Playwright1.63.0 installed in stage pw with pinned container mcr.microsoft.com/playwright:v1.63.0-noble,2CPU/2GiB. WAVs, saved projects and screenshots remain in stage audio-final/work-final/browser. Satellite screenshot inspected: no new label collision.

First full render completed all assertions but final receipt write failed missing receipts directory. Re-run with existing output WAV refused EEXIST. Final successful run used newly created receipts directory and fresh audio-final/work-final paths; no assertion was waived.

Independent source critic returned two Event improvements after this passed snapshot: replace its suspended ending chord with F minor, and lower the final chorus saw flourish from C7 max to C6. A later Event asset supersedes this receipt and requires its own runtime/browser recheck. Owner listening is pending for all four. Numeric audio results are not musical approval.
