# CI lifecycle disk fixture handoff — 2026-11-01

## Outcome

Fixed the test-local environment for `tests/test_build_on_aeon_lifecycle.py`. The fixture now installs fake `uname` and `df` commands in its private PATH. `uname -s` deterministically reports Darwin; the Mac data-volume probe defaults to 900 GiB and can be set with `FAKE_MAC_FREE_GB`; the simulated remote `df -Pk` reports 20 GiB. Added a test that supplies 499 GiB and proves the production wrapper refuses before transport, Docker, or log creation. Production code and its 500 GiB floor were not changed.

## Before / after insight

Before: fake `ssh`, `scp`, `docker`, and `tar` were isolated, but the wrapper's platform and disk-space probes were inherited from the host. On macOS CI the real runner volume could therefore stop every fake-transport case at the production safeguard.

After: both local Mac disk capacity and simulated remote capacity are deterministic in the fixture on macOS and Linux. Normal cases exercise the intended fake transport flow; the low-space case exercises refusal explicitly.

## Files and Git

- `tests/test_build_on_aeon_lifecycle.py`
- `scratch/performance/devkit-20261023/audit-20261101/ci-lifecycle-disk-fixture/HANDOFF.md`
- Branch: `fix/2026-11-01@ci-lifecycle-disk-fixture`, based on `6ece5032bb4a2e7f3856350c89015725f727a473`.
- Commit and remote SHA: pending at note creation; update after push.

## Checks and limits

- `python -m pytest -q tests/test_build_on_aeon_lifecycle.py`: 18 passed on macOS, using CPython 3.12.14 and pytest 9.2.0 installed into a temporary `.test-venv`; the venv was removed after the run.
- `git diff --check`: passed.
- No SSH transport, real Docker, LAN build, or hardware operation was performed. This local result does not replace GitHub Actions CI.
- Rarefaction status was available but rooted at `/Users/likwid/Developer/mvave-fm1-firmware`; its API rejected the assigned worktree because it lies outside that workspace. Serena was active on that same shared checkout. I did not switch either shared project; source was inspected directly in the assigned worktree.
- The supplied `scratch/ci-6ece-macos/job.log` was not present at the named path in the source checkout or the assigned worktree, so CI's detailed failure lines were not independently re-read. The reported failure context came from the parent task brief.

## Cleanup and next dependency

The fixture's per-test scratch trees, generated build outputs, and temporary pytest environment were cleaned by the test fixture/run. No test scratch remains. Built-in volume had 1,114 GiB available at check time.

Next: commit and push this branch, verify the remote SHA, then return it for coordinator review and integration. The coordinator should run/observe required exact-head CI before merging.
