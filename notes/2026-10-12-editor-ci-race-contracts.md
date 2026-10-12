# Editor CI race contracts, 2026-10-12

## Scope and inventory [verified]

Read all four actual failing job logs in GitHub Actions run 38223359215,
head `ef55216b47b7f55eca96609af347fba31b332a06`. Overall run and Firefox/
32-bit jobs were cancelled, but their failing steps emitted complete failures.
This is not a claim that cancelled macOS/ASan jobs passed.

| Actual failure | Browsers/profile | Owner and disposition |
| --- | --- | --- |
| RAM/CPU/title layout in editor-ui | Chromium, Firefox, WebKit | Browser contracts stream integrated in 969259d4 |
| Toolbar landscape menu clipped | All three | Same integrated container/settled-grid fixture repairs |
| Two polite status regions, preview horizontal scroll at 320px | All three | CI accessibility stream 9a85aa76 |
| CPU visible/accessibility label mismatch | All three | CI accessibility stream 9a85aa76 |
| editor-v1 header overlaps underlying desktop text | Chromium, Firefox | This test-only repair |
| Native sequencer redo repeats timeout | Firefox | This test-only repair |
| New pause harness linked i386 objects as x86-64 | Native 32-bit | Details forwarded; CI accessibility stream 9a85aa76 |

Native MIDI transport (10 checks), MIDI map/project UI, song shortcuts,
sequencer-sync, initial view, resources and 30-second storm passed in all
three browser job logs. Other completed native/module/dongle jobs succeeded;
Ubuntu pytest completed successfully before cancellation. No additional
unowned failing testcase was identified in these logs.

## Runtime cause and narrow changes [verified]

Native model restoration becomes visible before `restoreHistory` completes
its final serialized project save. The fixture read the expected restored
model then immediately issued redo while `sequenceBusy` remained true.
The product intentionally ignores history commands during that transaction.
The fixture now waits for its existing bounded idle contract after each
observed undo/redo value, covering both track names and section repeats.
Commands are still issued once; expected native values and download checks
are retained.

A separate real Firefox diagnostic held only the final `files.saveText`
call, leaving native Wasm restoration intact. At native song length 1,
`sequenceBusy` was true, the real Redo button was disabled, its click and
public redo command were inert. The actual `nativeTarget(Redo)` registered
in `MidiMap` reported unavailable, consumed a mapped CC31 message, and left
song length 1. Releasing the save and waiting for idle allowed one redo to
restore length 3. The diagnostic is preserved in ignored scratch receipts;
it does not alter the product or add retries to the main regression.

The desktop geometry failure compared labels underneath the intentional
sticky app bar with visible header controls. `editor.select` normally
smooth-scrolls selected content. A real Chromium experiment at scrollY0/80
had no layout faults; at 140/180/240 the strict probe reported the covered
content as overlapping. Screenshots confirm opaque sticky coverage. Layout
and axe fixture selection now uses the existing `noScroll` option and starts
at scroll0. Functional selection elsewhere is unchanged; geometry rules
and the phone open-menu check remain strict. Scrolled controls and overlays
have separate native MIDI toolbar coverage in the parent stream.

A baseline Firefox run also timed out looking for Clip playhead after the
fader edit. It is preserved, without claiming a proven separate product
cause. Two subsequent instrumented native runs completed the same matrix,
fader, Clip playhead and six WAV checks. Full three-browser fixed native
runs completed those checks as well. No playhead assertion was removed or
relaxed.

## Evidence and acceptance boundaries

Base: `969259d4bc9fb2bf7030daa1eb34d01e6573cdf3`.
Browser stage overlays 9a85aa76 editor.js/editor.css/actual rebuilt Wasm
metadata, with this branch's test changes. Native Wasm SHA256 remains
`761b18d3e9a676494a02e2d87867aa0eeab45bad6ab82062fad385a2f8bc2ebc`.
Hera containers: Playwright 1.63.0, 3 CPU and 3 GiB each, private networks;
verified axe-core dependencies mounted read-only from the accessibility
agent's dependency directory.

Remote stage:
`/home/claude/mvave-fm1/editor-browser-contracts-20261012/ci-969-9a`.
Local durable ignored receipts:
`scratch/browser-contracts/ci-inventory-38223359215/` containing original
job logs, baseline failures, results-diagnostic3/firefox/results.json,
results-sticky/chromium.json and chromium-{0,80,140,180,240}.png, plus
results-fixed/{chromium,firefox,webkit}/{native,v1} and logs.

Validation [verified]: Chromium 153, Firefox 155, WebKit 26.6 each passed
native sequencer 14/14 with six WAVs and editor-v1 99/99 with no layout or
axe failures. `node --check` for both changed test scripts and
`git diff --check` pass. The only edits after staging these runs are comments,
indentation and this receipt. Product sources were unchanged by this branch.

Shared Rarefaction/Serena roots remain untouched; previous readiness checks
selected the primary checkout, with Serena C-only. Source inspection and
native browser execution cover this isolated JavaScript test work.
No hardware, listening, deployed page or eventual combined CI acceptance is
claimed. Parent's later Arrangement changes are independently owned and
not included in this snapshot's receipts.
