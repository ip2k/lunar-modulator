# Editor save durability — 2026-10-09

The confirmed IndexedDB false-save finding in `notes/2026-10-07-full-code-audit.md`
is addressed on `fix/2026-10-09@editor-save-durability`. User-requested project
and library saves, plus autosave, require the IndexedDB transaction to complete;
an unavailable database or failed transaction rejects instead of becoming a
memory-only success. SAVE reports `NOT SAVED` to the worklet, displays that the
project remains unsaved, and does not claim the file is in the browser library.
Failed autosave writes keep the dirty state and do not advance the saved byte
cache, so a later retry writes again. Autosave and panel/library saves capture
project identity before their asynchronous snapshot; a changed project is not
reported as saved. Other background writes retain their visit-memory fallback.

`sim/web/test/files.mjs` now injects a quota-style IndexedDB transaction error
for panel SAVE and autosave, checks the failed SAVE response and absent library
record, verifies panel SAVE succeeds after storage recovers, and verifies a
blocked IndexedDB cannot report success. On aeon, Chromium 153 ran
`sim/web/test/files.mjs`: all seven sections passed (`files`, unavailable
storage, load links, hash, embed, local-origin rules and layout), with no page
errors. In the full LAN run, the remaining page checks and 104 native/Wasm
parity scenarios passed; its first files run exposed overlapping simulated
SAVE key-downs, corrected by waiting for key-up before the retry. No hardware
traffic was used. This is a branch checkpoint, not a merge to `main`; CI is
pending.
