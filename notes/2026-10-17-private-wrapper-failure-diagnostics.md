# Private trusted-wrapper failure diagnostics

Personal, non-commercial Lunar work. Base: `ba3f60d13d35d4c34e67a9ac0d067ff085f5b9d2`.
Branch: `fix/2026-10-17@private-wrapper-failure-diagnostics`.

[verified] `_run_trusted_wrapper` previously discarded a nonzero child's captured
stdout/stderr and raised only its generic failure. It now saves private diagnostic
prefixes under the new run's fixed `trusted-wrapper-failure/` directory:
`stdout.bin`, `stderr.bin`, and `failure.json`. Each stream file is capped at
1 MiB. Metadata records the actual captured byte count, retained byte count,
truncation, prefix policy, SHA-256, and return code. Empty streams remain valid
empty private files. Logs are diagnostic data, never executable instructions.

[verified] The parent directory must resolve without symlinks, belong to the
current effective user, and have no group/other permissions. It is opened before
launch; subsequent directory/file creation uses that descriptor, fixed names,
exclusive creation, and no-follow opens. The new directory is mode 0700 and its
files mode 0600. Existing directories, files, and dangling/live symlinks are
rejected before launch. A child-created redirect cannot redirect diagnostic
writes. No cleanup deletes the request or any preexisting content. An unsafe or
occupied retention destination fails closed with the original generic error.

[verified] The existing `subprocess.run` command, separate PIPE captures,
1500-second timeout, and timeout propagation are retained. Success creates no
failure directory. **The byte bound applies to retained files, not child output
captured in memory.** This patch does not implement bounded subprocess memory,
post-exit pipe draining, process-tree supervision, Docker lifecycle cleanup, or
timeout diagnostic retention. A broader execution-policy change was deliberately
left outside this logging fix. No shell, new runtime flags, or user-selected log
paths are introduced. Child output and diagnostic paths never enter the generic
nonzero error; root-acquisition OS errors are also mapped to that generic error.

[verified] Existing API/provenance, raw app/ELF identity checks, trusted tuple and
packaging policies, and all hardware/updater/installability/release flags are
unchanged. These files are private operator artifacts; nothing exposes them in
the public receipt summary. No target build, container, Hera contact, device,
USB, MIDI, power, flash, deployment, or acceptance operation was performed.

Validation uses actual lightweight Python child processes for nonzero binary
output, success, oversized saved prefixes, and a child-created symlink. Tests
also exercise occupied destinations and missing/unsafe/symlinked roots without
launching a child. Final focused result: **209 passed, 1 skipped**, with the
existing Starlette/httpx deprecation warning. Command:

```sh
python -m pytest -o addopts='' -q tests/test_private_package_candidate.py tests/test_installer_service.py tests/test_installer_continuous_profile.py
```

The interpreter was the existing integration checkout's `.venv/bin/python`.
`git diff --check` also passed.

Semantic-tool limits: Rarefaction's Python server is rooted at the sibling
primary checkout and its bounded orient request for this worktree-only file
returned ENOENT. Serena likewise selects the primary checkout (C++ configuration)
and could not find this file. Neither shared server was retargeted; the actual
isolated source and tests were read directly. These checks do not validate the
JieLi target ABI or hardware behavior.

Next dependency: coordinator review/integration and the normal CI gates. Retained
diagnostics can inform a separately authorized future failure investigation;
this change does not authorize rerunning a pipeline or changing acceptance gates.
