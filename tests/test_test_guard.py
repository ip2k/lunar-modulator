"""The guards in tests/conftest.py: a tool that spins dies on its CPU limit,
a tool that hangs fails its call, and ordinary calls are unchanged."""
from __future__ import annotations

import signal
import subprocess
import sys
import time

import pytest

SPIN = [sys.executable, "-c", "while True: pass"]
SLEEP = [sys.executable, "-c", "import time; time.sleep(30)"]


def test_a_spinning_child_dies_on_its_cpu_limit(monkeypatch):
    monkeypatch.setenv("FM1_TEST_CPU_SECONDS", "1")
    start = time.monotonic()
    done = subprocess.run(SPIN, capture_output=True)
    assert done.returncode == -signal.SIGXCPU
    assert time.monotonic() - start < 20


def test_a_hanging_child_fails_on_the_default_timeout(monkeypatch):
    monkeypatch.setenv("FM1_TEST_TIMEOUT", "1")
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(SLEEP, capture_output=True)


def test_a_timeout_the_caller_gives_wins(monkeypatch):
    monkeypatch.setenv("FM1_TEST_TIMEOUT", "60")
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(SLEEP, capture_output=True, timeout=1)
    assert time.monotonic() - start < 20


def test_ordinary_calls_are_unchanged(tmp_path):
    out = subprocess.run([sys.executable, "-c", "import sys; print(sys.argv[1:])", "a b", str(tmp_path)],
                         check=True, capture_output=True, text=True).stdout
    assert out.strip() == repr(["a b", str(tmp_path)])
    assert subprocess.check_output([sys.executable, "-c", "print(7)"], text=True).strip() == "7"
    failed = subprocess.run([sys.executable, "-c", "raise SystemExit(3)"])
    assert failed.returncode == 3


def test_the_limit_reaches_the_child_and_zero_turns_it_off(monkeypatch):
    import resource
    probe = [sys.executable, "-c", "import resource; print(resource.getrlimit(resource.RLIMIT_CPU)[0])"]
    monkeypatch.setenv("FM1_TEST_CPU_SECONDS", "77")
    assert int(subprocess.check_output(probe, text=True)) == 77
    monkeypatch.setenv("FM1_TEST_CPU_SECONDS", "0")
    assert int(subprocess.check_output(probe, text=True)) == resource.getrlimit(resource.RLIMIT_CPU)[0]
