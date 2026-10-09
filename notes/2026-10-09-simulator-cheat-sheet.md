# Simulator Cheat Sheet

Owner request, 2026-10-09: hide the informational text below the simulator
and preset controls behind a small Cheat Sheet icon at the bottom of the page.

Implemented on `feature/2026-10-09@simulator-cheat-sheet`, based on PR #99:
- Native closed-by-default `details`/`summary`, with an original inline document icon.
- Existing playing instructions, credits and runtime licence/source links remain available inside it.
- Saved/Recent/examples remains a separate operational control.
- Keyboard activation, visible focus and a minimum 44px control height.
- Existing embedded-mode help hiding is retained; no new JavaScript or preferences.

[verified] Local Chrome desktop (1280x1000) and phone viewport (390x844):
initially collapsed, Enter expands, pointer collapses, no horizontal overflow.
Rendered screenshots inspected for icon/text padding and collisions. This is
viewport validation, not an actual iPhone test. No DSP or Wasm changes.

Pending: exact-head CI, integration after PR #99, then public-site verification.
