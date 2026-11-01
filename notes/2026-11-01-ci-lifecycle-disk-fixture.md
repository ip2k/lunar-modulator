# Mac CI lifecycle fixture isolation — 2026-11-01

CI job 124921216033 on run 41331077051 reported 95 GiB free on its macOS data volume. The existing build wrapper correctly enforced its 500 GiB workstation safeguard, but the lifecycle tests inherited the runner's real `uname` and `df` because only SSH, SCP, Docker, and tar were faked. Nine lifecycle cases consequently stopped before their fake transport paths.

The test fixture now fakes Darwin and deterministic local and simulated remote disk readings. Normal scenarios receive 900 GiB local free space and 20 GiB remote stage space; a dedicated case verifies that 499 GiB is refused before remote I/O. The production safeguard remains unchanged.

The focused suite passed all 18 tests on macOS with CPython 3.12.14 and pytest 9.2.0. GitHub Actions exact-head rerun remains with the coordinator. Detailed handoff and private log location are kept in the owner's Codex worktree scratch.
