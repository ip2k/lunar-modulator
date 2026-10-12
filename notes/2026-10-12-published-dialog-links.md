# Published simulator dialog links

[verified] The post-merge deployment check for PR #147, merge
`612896b88d4fa8474b1f0af541ce29a5a02cf9d6`, found all representative
runtime assets matching their tracked sources, but `index.html` differed.
The Pages build intentionally adds manual links to that page. Inspection
also found malformed Copyright Info markup: the inserted Cheat Sheet
manual row shifted the already-captured lede offsets, so the replacement
overwrote the close button and part of the dialog header.

[verified] `tools/manual/build.py` now applies both substitutions in
descending source-position order. This preserves either document order
without changing the simulator source page or its runtime assets.

[verified] Three focused regression cases cover the help list before and
after the lede, and the actual simulator Copyright Info header. The old
source passed the lede-first case and failed both help-first cases; the
repair passes all three. The synthetic outputs are parsed as XML to
verify intact dialog structure and manual/PDF links. The actual-page
case compares the entire dialog header and dialog counts.

[verified] Pages CI installs pytest alongside the pinned manual
dependencies and runs these cases before building the site. Changes to
`tests/test_manual.py` also trigger the Pages workflow. Python compilation
and `git diff --check` passed locally. Required GitHub CI, independent
review, the next deployment and its visible browser check remain separate
acceptance gates.

The deployment proof must compare `index.html` against its expected
published copy, including the two intentional manual-link additions;
the other runtime assets remain byte-for-byte comparisons. Earlier failed
deployment and regression receipts are retained under ignored `scratch/`.
