# Selected trio shallow-history regression

## Before and after

Before: `test_v1_canonical_bytes_and_rejection_stay_unchanged` also passed the hard-coded commit `7ab2810420999629d170531a6f2f78fd44a8484f` to the production prerequisite gate. Its tree tracked only four of the nine required native inputs, so the gate correctly refused it, but a shallow CI checkout lacked the commit and `git ls-tree` failed before that assertion.

After: the canonical v1 byte and v2-request rejection assertions remain independent. A separate regression creates a temporary Git repository, places all nine prerequisite files in its working tree, commits the same four historically tracked inventory paths, generates its SHA locally, and asserts the production gate raises its intended unavailable-prerequisites error. The temp repository uses pytest's `tmp_path` lifecycle.

## Tool coverage

Rarefaction and Serena were checked, but both are bound to `/Users/likwid/Developer/mvave-fm1-firmware`; Rarefaction could not resolve the assigned isolated worktree. Serena activation was not changed because its project selection is shared and the task prohibits shared-project switching. The test and validator were reviewed directly.

## Scope

Only `tests/test_installer_selected_trio_profile.py` and this dated note are changed. No production validator, checker relaxation, skips, full-history fetch, build, service or device operation is involved.

## Verification

`tests/test_installer_selected_trio_profile.py` passed in the isolated worktree's Python 3.13 environment (pytest 9.2.0 and the pinned installer test requirements). `git diff --check` passed. A depth-1 clone check is next; the CI failure in `scratch/ci-6ece-macos/job.log` confirms the old test failed at `git ls-tree` with exit 128 for the absent historical commit.
