# Engine integration review checkpoint

No implementation CI head was changed by this review; parent controls merges.

[verified: CI] Compare PR113 at b43960680760092bf1eb13ad2371b2039326abd9 completed12 functional SUCCESS, WebKit FAILURE, Pages SUCCESS and deploy SKIPPED. Run38024280948, WebKit job114131683631. The strict panel-follow latency gate failed at22frames/340ms. Saved exact failure detail: notes/data/compare-b439-webkit-panel-follow.json.

[verified: trace] Frames1–21 (through323ms) show unchanged audioTime0.7198185941043084 with audioState running, loading false, no pending changes/inflight and row value.30. First recorded main-port state329ms, changes331ms, editor-after334ms value.33, screen338ms, finalframe22/340ms. Main-thread frames continue while audio clock and port events are frozen; this matches the observed signature on other exact-head branches. It does not establish why the backend stopped advancing, CPU-pressure causation, or correctness of the pending WebKit lifecycle correction. Trace explicitly records timing perturbation.

[verified: CI] This same job passed external monitor/A-B30s (finite, no silence/channel mismatch, no transport-stop events) and page storm30s (codes_not_ok0,resyncs0,passtrue). This is not a listening pass for the owner's reported Safari crackles. No blind rerun or gate threshold change was made.

[verified: native/source] Repeat fix cc84475d00006f8e83f0d84edcfe0504366e1ca6 was independently re-read and probed on LAN gcc:12 against an immutable git-show snapshot. START/STOP/RESET/initial HoldOff now stay wet0/.5DC output. Repeated Mix preserves originaldeadline (mix1,left0). Rapid re-hold clearsvalidity; immediateBEAT cannot re-latch theoldwindow. One remaining analogous repeated HoldOff during a held release restarts wet deadline: nonrepeat wet0,held0,left0 vs repeat after5frames wet.0221154,held1,left5 at originaldeadline. Implementer was notified; no reviewer source edit. Existing generic smooth fixture does not fill the ring, so focused held-output/deadline coverage is needed. Previous exact3425 findings and reproducer remain historical evidence in the separate review note.

Current prerequisite order: exact green engine CI, parent-selected firstmerge, actual combined source regeneration/test for other engine branches, final Repeat native+Wasm checks and unchanged gates, then demo authoring/export/full-chain/listening checks. Offline firmware branches remain separate and cannot imply a running FM-1 application. Immutable owner PR128 preview remains http://127.0.0.1:8781/ at1c09c5a2; existing8778/8780 untouched.

[verified: native/source] Repeat checkpoint
`461eda052c517a304d2de0199c3c28cfcfe690ef` closes the remaining repeated
Hold Off finding. The same independent probe, built from an immutable source
snapshot on bounded LAN gcc:12, now reports both release paths at the
original deadline as `wet=0, held=0, left=0`. The source preserves the
pending release and STOP clear request; an explicit unchanged Hold On still
rearms after STOP. The new held-history regressions exercise both cases.
The documentation now qualifies the fresh-ring plus later-beat requirement
as applying while running. No further confirmed source finding arose from
this bounded re-review. This verifies the focused correction; generated
Wasm, complete native/parity/browser checks and CI remain separate gates.
Probe output is retained at `notes/data/repeat-461eda05-review-probe.txt`;
LAN snapshot is `/home/claude/mvave-fm1/repeat-review-461eda05`.
