# Test server file boundary — 2026-10-09

Audit batch 5 identified a sibling-prefix traversal in the local page-test
server. Replaced string-prefix containment with resolved path-relative
containment, including the final real path so symlinks cannot escape the
served tree. Malformed percent encoding returns HTTP 400 instead of throwing
out of the request handler. Normal directory index and asset serving remain.

[verified] Two actual HTTP regression cases (root and /preview/ hosting) pass:
index/assets, encoded sibling traversal, outside symlink, missing file,
malformed encoding and a successful request after malformed input. Node syntax
and git diff checks pass. No production bundle or hardware changes.

Branch `chore/2026-10-09@audit-tool-safety`; CI must pass before merge.
Rarefaction oriented the original-checkout server; Serena activation succeeded
but its new-worktree language configuration ignored this JavaScript file, so
semantic navigation there was unavailable. Source inspection continued.
