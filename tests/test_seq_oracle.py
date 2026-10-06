"""The C core against Movy's own traces (docs/13 stage M3).

tests/fixtures/movy/ holds verb scripts with the event logs, `movy1` exports
and D1 traces that Movy's seq-core (schwung-movy by megadake, MIT, at
9190e79) produced for them, run by tools/movy-oracle in a container on aeon;
random/ holds a few seeded random scripts (gen_scripts.py --no-undo) with
theirs, gzipped. Here the C core replays each one:

- fm1-seq --compat and fm1-render --compat log exactly Movy's events and
  export Movy's set for the tracks the script declares;
- fm1-seq --compat-frames logs exactly Movy's D1 trace, each tick at the
  frame where Movy, fed one frame at a time, fires it;
- the FM-1 default mode logs the D1 trace too, apart from the deviations of
  docs/13 §3.3 that a script reaches, which are checked as such.

18-undo is an expected failure: the undo ring is not ported (docs/13 M4).
"""
import gzip
import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.seq_helpers import ENGINES, RENDER, seq_tools  # noqa: F401

FIX = Path(__file__).resolve().parent / "fixtures" / "movy"
SCRIPTS = sorted(FIX.glob("*.verbs"))
RANDOM = sorted((FIX / "random").glob("*.verbs"))
D1 = [s for s in SCRIPTS if (FIX / f"{s.stem}.d1.jsonl").exists()]
TRACK_LINES = {"tk", "pm", "ps", "au", "cl", "cp", "lk", "tg", "rt"}


def read(path):
    if not path.exists():
        path = path.with_name(path.name + ".gz")
        return gzip.decompress(path.read_bytes()).decode("utf-8")
    return path.read_text(encoding="utf-8")


def events(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def tracks_of(script):
    m = re.search(r"tracks=(\d+)", script.read_text().splitlines()[0])
    return int(m.group(1)) if m else 8


def set_lines(text, tracks):
    """A movy1 set's lines for the first `tracks` tracks: Movy writes all 16."""
    out = []
    for line in text.splitlines():
        words = line.split()
        if words and words[0] in TRACK_LINES and int(words[1]) >= tracks:
            continue
        out.append(line)
    return out


def run_seq(tool, script, tmp_path, *flags):
    log, exp = tmp_path / "c.jsonl", tmp_path / "c.movy1"
    cmd = [str(tool), "--cmd", str(script), "--log", str(log), "--export", str(exp), *flags]
    state = script.with_name(script.stem + ".in.movy1")
    if state.exists():
        cmd += ["--seq", str(state)]
    subprocess.run(cmd, check=True, capture_output=True)
    return events(log.read_text()), exp.read_text()


def first_difference(got, want):
    i = next((k for k, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    return (f"first difference at event {i} of {len(want)} (ours {len(got)}): "
            f"ours {got[i] if i < len(got) else None}, Movy {want[i] if i < len(want) else None}")


def xfail_undo(script):
    if script.stem == "18-undo":
        pytest.xfail("the undo ring is not ported (docs/13 M4)")


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_golden_compat(seq_tools, tmp_path, script):
    xfail_undo(script)
    got, movy1 = run_seq(seq_tools, script, tmp_path, "--compat")
    want = events(read(FIX / f"{script.stem}.jsonl"))
    assert got == want, first_difference(got, want)
    n = tracks_of(script)
    assert set_lines(movy1, n) == set_lines(read(FIX / f"{script.stem}.out.movy1"), n)


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_golden_render_compat(seq_tools, tmp_path, script):
    """fm1-render drives the same core, block by block, beside an engine."""
    xfail_undo(script)
    log = tmp_path / "r.jsonl"
    cmd = [str(RENDER), "--compat", "--cmd", str(script), "--log-events", str(log)]
    state = script.with_name(script.stem + ".in.movy1")
    if state.exists():
        cmd += ["--seq", str(state)]
    subprocess.run(cmd, check=True, capture_output=True)
    got, want = events(log.read_text()), events(read(FIX / f"{script.stem}.jsonl"))
    assert got == want, first_difference(got, want)


@pytest.mark.parametrize("script", D1, ids=lambda p: p.stem)
def test_golden_d1_frames(seq_tools, tmp_path, script):
    """D1's offsets, in Movy's own terms: the frame inside the block where a
    tick fell, from the internal clock and from an external one."""
    got, _ = run_seq(seq_tools, script, tmp_path, "--compat-frames")
    want = events(read(FIX / f"{script.stem}.d1.jsonl"))
    assert got == want, first_difference(got, want)


def drop_restart_pairs(evs):
    """D12: Play while playing sends Stop and then Start at the restart."""
    out, i = [], 0
    while i < len(evs):
        e = evs[i]
        if (e["kind"] == "stop" and i + 1 < len(evs) and evs[i + 1]["kind"] == "start"
                and evs[i + 1]["frame"] == e["frame"]):
            i += 2
            continue
        out.append(e)
        i += 1
    return out


# What the FM-1 default mode adds to each D1 fixture (docs/13 §3.3).
DEFAULT_DEVIATIONS = {
    "06-conditions": "D12",   # Play while playing
    "24-ext-clock-stale": "D2 D6",   # the first step's lock before its notes; base at Stop
}


@pytest.mark.parametrize("script", D1, ids=lambda p: p.stem)
def test_golden_default_mode(seq_tools, tmp_path, script):
    got, _ = run_seq(seq_tools, script, tmp_path)
    want = events(read(FIX / f"{script.stem}.d1.jsonl"))
    rows = DEFAULT_DEVIATIONS.get(script.stem, "")
    if not rows:
        assert got == want, first_difference(got, want)
        return
    if "D12" in rows:
        assert len(got) > len(drop_restart_pairs(got)), "D12 sent nothing"
        got = drop_restart_pairs(got)
        assert got == want, first_difference(got, want)
    if "D2" in rows or "D6" in rows:
        def key(e):
            return (e["block"], e["frame"], e["tick"], e["kind"], e["track"], e["a"], e["b"])
        plain = [key(e) for e in got if e["kind"] != "cc"]
        assert plain == [key(e) for e in want if e["kind"] != "cc"], "notes and clock"
        locks, movy_locks = sorted(key(e) for e in got if e["kind"] == "cc"), \
            sorted(key(e) for e in want if e["kind"] == "cc")
        extra = list(locks)
        for k in movy_locks:
            extra.remove(k)
        stop = [e for e in got if e["kind"] == "stop"][-1]
        # D6: the only lock Movy does not send is the base at the last Stop.
        assert extra and all(k[0] == stop["block"] and k[2] == stop["tick"] for k in extra)
        # D2: on the first step after a (re)start, tick 0, a track's locks
        # come before its note-ons (Movy: after them).
        first = [e for e in got if e["tick"] == 0 and e["kind"] in ("on", "cc")]
        assert any(e["kind"] == "cc" for e in first)
        for i, e in enumerate(first):
            if e["kind"] == "cc":
                assert not any(o["kind"] == "on" and o["track"] == e["track"]
                               and o["frame"] == e["frame"] for o in first[:i]), e


def test_random_fixtures_present():
    assert len(RANDOM) >= 8, "random/ holds the seeded scripts with Movy's traces"


@pytest.mark.parametrize("script", RANDOM, ids=lambda p: p.stem)
def test_random_compat(seq_tools, tmp_path, script):
    """Seeded random scripts: edits, locks, conditions, recording, launches,
    songs, Capture, tempo and transport, interleaved (gen_scripts.py)."""
    got, movy1 = run_seq(seq_tools, script, tmp_path, "--compat")
    want = events(read(script.with_suffix(".jsonl")))
    assert got == want, first_difference(got, want)
    n = tracks_of(script)
    assert set_lines(movy1, n) == set_lines(read(script.with_name(script.stem + ".out.movy1")), n)


@pytest.mark.parametrize("script", RANDOM, ids=lambda p: p.stem)
def test_random_default_mode_runs_clean(tmp_path, script):
    """The FM-1 default on the same scripts: the checking build (index
    invariants) runs them to the end, with every note closed."""
    got, _ = run_seq(ENGINES / "build" / "fm1-seq-check", script, tmp_path)
    sounding = {}
    for e in got:
        if e["kind"] in ("on", "off"):
            k = (e["track"], e["a"])
            sounding[k] = sounding.get(k, 0) + (1 if e["kind"] == "on" else -1)
            assert sounding[k] >= 0, e
    assert not any(sounding.values()), "a note left sounding after Stop"
