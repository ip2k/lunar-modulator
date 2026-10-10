# Simulator information dialogs

Owner request, 2026-10-09: keep the simulator panel/workbench/editor and its
controls near the top of the page. Move the long brand introduction, playing
instructions, saved/recent/examples library, runtime status, credits, and
licence offer into compact Cheat Sheet and Copyright Info dialogs at the
bottom. Keep errors visible outside the dialogs.

Implemented on `feature/2026-10-09@simulator-cheat-sheet`:

- `index.html` keeps the full interactive `#status`, `#library` and
  `#library-lists` under the Cheat Sheet dialog; all existing playing help is
  retained. Copyright Info keeps the complete brand introduction, credits,
  font licence links, and dynamic `#licence-note` GPL/source offer.
- Native `<dialog>` elements open from labelled 44px bottom buttons. Each has
  a named heading and close button, uses native Escape/focus containment, and
  restores focus to its opener on close. Dialog content scrolls internally on
  short and mobile viewports. Embedded simulator pages hide the information
  controls as before.
- Short audio, firmware, MIDI, held-context, and editor-load failures remain
  visible in a page-level alert; their complete diagnostic stays in `#status`
  inside Cheat Sheet. Normal runtime updates clear that alert.
- `sim/web/test/info-dialogs.mjs` checks the shortened page shell, closed-by-
  default state, Escape and close behavior, focus return, the 44px dynamic
  library disclosure, visible audio-start failure with its full diagnostic
  retained in the status paragraph, preserved text/links/live targets,
  dialog bounds and internal scrolling at desktop and phone sizes. It is in the
  Chromium/Firefox/WebKit page-test workflow.

Validation: `node --check` on the page and test scripts, `git diff --check`,
and an HTML nesting check passed. The focused Playwright 1.63 page test passed
in Chromium, Firefox, and WebKit on the documented aeon container (all shell,
desktop, licensing, focus, 44px library-target, and 390x844 internal-scroll
checks passed). I inspected the desktop Cheat Sheet and Copyright Info and
the phone Cheat Sheet screenshots; text is not clipped, the dialog stays
within the viewport, and the help body scrolls inside the dialog. Exact-head
GitHub CI is pending. No hardware, audio-device, or firmware actions were
performed.

CI follow-up: exact head `ef856a3809c1f52d6fc3cf61a13f1750cbcee114` failed
only the Chromium `files.mjs` page test. Its two library checks still clicked
the summary directly even though the requested UI now places it inside the
closed Cheat Sheet dialog. The failure was a hidden-element timeout, not audio
resource pressure. The test now opens the Cheat Sheet before using the library;
the full `files.mjs` test passes in the bounded aeon Playwright 1.63 container
with `files`, unavailable-storage, link/hash/embed/local, and desktop/phone
layout checks true and no browser logs. A new exact-head CI run is pending.

Semantic navigation limitation: the shared Rarefaction project still selected
the main checkout, not this isolated worktree; Serena activated this worktree
but had only its C++ language server and could not index the JavaScript page.
No shared project activation was changed; the HTML/JS/CSS changes were
inspected directly and covered with focused page tests.
