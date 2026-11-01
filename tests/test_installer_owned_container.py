# SPDX-License-Identifier: MIT
"""Synthetic Docker protocol responses; no daemon is contacted."""
import json
from pathlib import Path

import pytest

from tools.installer_service import owned_container as cleanup
from tools.installer_service.process_capture import Capture

NAME = "lunar-continuous-" + "a" * 24


def result(stdout=b"", *, code=0, reason=None, observed=None):
    return Capture(code, {"stdout": stdout, "stderr": b""},
                   {"stdout": len(stdout) if observed is None else observed, "stderr": 0}, reason)


def responses(monkeypatch, *sequence):
    calls = []
    remaining = iter(sequence)
    def capture(command, **limits):
        calls.append(command)
        assert limits["timeout_seconds"] == 10
        assert limits["max_stream_bytes"] == cleanup.MAX_DOCKER_OUTPUT
        value = next(remaining)
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(cleanup, "run_bounded", capture)
    return calls


def test_scoped_removal_requires_exact_owner_label(tmp_path, monkeypatch):
    calls = responses(monkeypatch, result(json.dumps({"lan.owner": NAME}).encode()), result())
    assert cleanup.cancel_owned_container(NAME, cwd=tmp_path)
    assert calls == [["docker", "container", "inspect", "--format", "{{json .Config.Labels}}", NAME],
                     ["docker", "rm", "--force", NAME]]


@pytest.mark.parametrize("labels", [{}, {"lan.owner": "someone-else"}, [], None])
def test_name_collision_never_authorizes_removal(tmp_path, monkeypatch, labels):
    calls = responses(monkeypatch, result(json.dumps(labels).encode()))
    assert not cleanup.cancel_owned_container(NAME, cwd=tmp_path)
    assert len(calls) == 1


@pytest.mark.parametrize("name", ["", "unrelated", NAME + "extra", "-f", NAME + "/", None])
def test_invalid_owned_name_never_runs_docker(tmp_path, monkeypatch, name):
    monkeypatch.setattr(cleanup, "run_bounded", lambda *_args, **_kw: pytest.fail("must refuse before Docker"))
    with pytest.raises(ValueError, match="parent-owned"):
        cleanup.cancel_owned_container(name, cwd=tmp_path)


@pytest.mark.parametrize("names, absent", [(b"", True), (b"unrelated\n", True),
    ((NAME + "-extra\n").encode(), True), ((NAME + "\n").encode(), False),
    (("/" + NAME + "\n").encode(), False), (("alias," + NAME + "\n").encode(), False)])
def test_missing_inspect_requires_successful_exact_name_absence(tmp_path, monkeypatch, names, absent):
    calls = responses(monkeypatch, result(code=1), result(names))
    assert cleanup.cancel_owned_container(NAME, cwd=tmp_path) is absent
    assert calls[-1] == ["docker", "ps", "--all", "--filter", "name=" + NAME, "--format", "{{.Names}}"]
    assert not any("rm" in call for call in calls)


@pytest.mark.parametrize("listing", [result(code=1), result(reason="timeout"),
    result(b"", observed=cleanup.MAX_DOCKER_OUTPUT+1), result(b"bad name\n")])
def test_unavailable_truncated_or_ambiguous_listing_is_not_removal(tmp_path, monkeypatch, listing):
    responses(monkeypatch, result(code=1), listing)
    assert not cleanup.cancel_owned_container(NAME, cwd=tmp_path)


def test_failed_remove_requires_confirmed_absence(tmp_path, monkeypatch):
    responses(monkeypatch, result(json.dumps({"lan.owner": NAME}).encode()),
              result(code=1), result((NAME + "\n").encode()))
    assert not cleanup.cancel_owned_container(NAME, cwd=tmp_path)


def test_capture_exception_is_an_unconfirmed_cleanup(tmp_path, monkeypatch):
    responses(monkeypatch, OSError("unavailable"))
    assert not cleanup.cancel_owned_container(NAME, cwd=tmp_path)
