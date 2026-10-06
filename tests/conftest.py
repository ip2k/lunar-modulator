"""Guards for every tool the tests start.

Why: a pytest run that is killed (an interrupted agent, a closed terminal)
leaves the tools it started running. On 2026-10-06 an fm1-limit-test from
a stale worktree was found spinning one core at ~99 % with no parent, after
almost four days; it had kept another project's overnight benches from
running. No test call had a timeout.

What: every child started through subprocess.run (check_output goes
through it too) gets
- a wall-clock timeout when the call gives none (FM1_TEST_TIMEOUT seconds,
  default 1200), so a hung tool fails its test instead of hanging the run;
- a CPU-time limit set inside the child (`ulimit -t`, FM1_TEST_CPU_SECONDS,
  default 1800), so a child that spins dies on SIGXCPU even after pytest is
  gone. It is set by a one-line /bin/sh launcher rather than preexec_fn,
  which is unsafe with the thread pools some tests use.
0 turns either guard off. Calls with shell=True, an executable= or a
string command are left as they are (none in the tree today).
"""
from __future__ import annotations

import os
import subprocess

_RUN = subprocess.run
_LAUNCH = 'ulimit -t "$0" && exec "$@"'


def _seconds(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def _guarded_run(args, *rest, **kwargs):
    if kwargs.get("timeout") is None:
        wall = _seconds("FM1_TEST_TIMEOUT", 1200)
        if wall:
            kwargs["timeout"] = wall
    cpu = _seconds("FM1_TEST_CPU_SECONDS", 1800)
    if (cpu and isinstance(args, (list, tuple)) and args
            and not kwargs.get("shell") and kwargs.get("executable") is None):
        args = ["/bin/sh", "-c", _LAUNCH, str(cpu), *map(os.fspath, args)]
    return _RUN(args, *rest, **kwargs)


subprocess.run = _guarded_run
