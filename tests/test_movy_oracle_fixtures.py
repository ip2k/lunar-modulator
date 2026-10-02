"""The Movy oracle fixtures are well-formed (docs/13 stage M3).

Checks the shared formats only (tools/movy-oracle/README.md): the verb
scripts, the event logs Movy's seq-core produced for them, and the movy1
sets. It does not run Movy; tools/movy-oracle/regen-fixtures.sh regenerates
the traces on aeon. The C core's own tests compare against these files.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

FIX = pathlib.Path(__file__).parent / "fixtures" / "movy"
SCRIPTS = sorted(FIX.glob("*.verbs"))
KEYS = ["block", "frame", "tick", "kind", "track", "a", "b"]
MOVY_TRACKS = 16

# Movy's `cmd` verbs at 9190e79 (seq-core/src/command.rs), split by whether
# their first argument is a track. `link` and `minject` drive the Move
# transport link, which the shared event log has no kind for.
TRACK_VERBS = {
    "tog", "ltog", "addp", "del", "evel", "elen", "enudge", "etrn", "slen",
    "eprob", "econd", "einv", "clen", "cscl", "ctr", "cq", "loop", "dbl",
    "rec", "cap", "non", "nof", "clipdup", "clipdel", "clipsel", "launch",
    "stoptrk", "clipcopy", "clippaste", "clipdelat", "cpy", "pst", "alabel",
    "abase", "abaseq", "aset", "asetr", "aclr", "aclrs", "aclrstep", "mute",
    "pmute", "psolo", "tdrum", "watch", "hold",
}
OTHER_VERBS = {
    "play", "stop", "bpm", "swing", "wlane", "metro", "dq", "song", "songadd",
    "capclr", "capsel", "capdone", "cpyclr", "usnap", "uswap", "ucommit",
    "udrop", "uclr",
}


def parse_script(path: pathlib.Path) -> dict:
    run = {"rate": 44118, "block": 128, "tracks": 8, "cmds": []}
    header = False
    last = 0
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        where = f"{path.name}:{n}"
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#!"):
            assert not header, f"{where}: a second header"
            assert not run["cmds"], f"{where}: header after a command"
            header = True
            for kv in line[2:].split():
                key, _, value = kv.partition("=")
                assert key in ("rate", "block", "tracks"), f"{where}: header key {key!r}"
                assert value.isdigit(), f"{where}: {kv!r}"
                run[key] = int(value)
            continue
        if line.startswith("#"):
            continue
        m = re.fullmatch(r"@(\d+)\s+(\S.*)", line)
        assert m, f"{where}: not '@<frame> <command>'"
        frame, cmd = int(m.group(1)), m.group(2).strip()
        assert ";" not in cmd and not cmd.startswith("#"), f"{where}: {cmd!r}"
        assert frame >= last, f"{where}: frame goes backwards"
        last = frame
        run["cmds"].append((n, frame, cmd))
    assert 1000 <= run["rate"] <= 768000
    assert 1 <= run["block"] <= 8192
    assert 1 <= run["tracks"] <= MOVY_TRACKS
    assert run["cmds"], f"{path.name}: no commands"
    # The last command lands before the first block starting at or after it,
    # and that block is the last one run.
    run["last_block"] = -(-run["cmds"][-1][1] // run["block"])
    return run


def load_log(path: pathlib.Path) -> list[dict]:
    events = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        ev = json.loads(line)
        assert list(ev) == KEYS, f"{path.name}:{n}: keys {list(ev)}"
        events.append(ev)
    return events


def test_fixtures_exist():
    assert len(SCRIPTS) >= 20
    readme = (FIX / "README.md").read_text(encoding="utf-8")
    for s in SCRIPTS:
        assert s.stem in readme, f"README.md does not describe {s.stem}"
    assert "9190e79" in readme and "megadake" in readme and "MIT" in readme


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_script_uses_movy_verbs(script):
    run = parse_script(script)
    for n, _, cmd in run["cmds"]:
        verb, *args = cmd.split()
        assert verb in TRACK_VERBS | OTHER_VERBS, f"{script.name}:{n}: verb {verb!r}"
        assert all(re.fullmatch(r"-?\d+", a) for a in args if verb != "alabel"), (
            f"{script.name}:{n}: {cmd!r}")
        if verb in TRACK_VERBS:
            assert args and 0 <= int(args[0]) < run["tracks"], (
                f"{script.name}:{n}: track outside tracks={run['tracks']}")


def check_event(ev: dict, run: dict, where: str) -> None:
    for key in ("block", "frame", "tick"):
        assert isinstance(ev[key], int) and ev[key] >= 0, where
    kind, track, a, b = ev["kind"], ev["track"], ev["a"], ev["b"]
    if kind in ("on", "off", "cc"):
        assert isinstance(track, int) and 0 <= track < run["tracks"], where
    else:
        assert track is None, where
    if kind == "on":
        assert 0 <= a <= 127 and 1 <= b <= 127, where
    elif kind == "off":
        assert 0 <= a <= 127 and b is None, where
    elif kind == "cc":
        assert 102 <= a <= 109 and 0 <= b <= 127, where  # CC 102 + lane 0..7
    elif kind == "click":
        assert a in (0, 1) and b is None, where
    else:
        assert kind in ("start", "stop", "clock"), f"{where}: kind {kind!r}"
        assert a is None and b is None, where


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_event_log(script):
    run = parse_script(script)
    events = load_log(script.with_suffix(".jsonl"))
    assert events, script.stem
    prev_block, prev_tick, prev_clock = 0, 0, None
    playing = False
    gates: dict[tuple[int, int], int] = {}
    for i, ev in enumerate(events, 1):
        where = f"{script.stem}.jsonl:{i}"
        check_event(ev, run, where)
        # Movy has no sample offsets: an event sits at its block's start.
        assert ev["frame"] == ev["block"] * run["block"], where
        assert prev_block <= ev["block"] <= run["last_block"], where
        # The master tick only goes back when the transport restarts at 0.
        assert ev["tick"] >= prev_tick or ev["tick"] == 0, where
        if ev["kind"] == "start":
            assert not playing, f"{where}: Start while playing"
            playing, prev_clock = True, None
        elif ev["kind"] == "stop":
            assert playing, f"{where}: Stop while stopped"
            playing = False
        elif ev["kind"] == "clock":
            assert playing and ev["tick"] % 4 == 0, where
            assert prev_clock is None or ev["tick"] in (prev_clock + 4, 0), where
            prev_clock = ev["tick"]
        elif ev["kind"] in ("on", "off"):
            key = (ev["track"], ev["a"])
            gates[key] = gates.get(key, 0) + (1 if ev["kind"] == "on" else -1)
            assert gates[key] >= 0, f"{where}: note-off without a note-on"
        prev_block, prev_tick = ev["block"], ev["tick"]
    # Every fixture ends with Stop, which flushes every gate.
    assert events[-1]["kind"] == "stop" and not playing, script.stem
    assert all(v == 0 for v in gates.values()), f"{script.stem}: unbalanced notes"


D1_SCRIPTS = [s for s in SCRIPTS if "# D1 trace:" in s.read_text(encoding="utf-8")]


@pytest.mark.parametrize("script", D1_SCRIPTS, ids=lambda p: p.stem)
def test_d1_trace(script):
    """The same events, each at the frame inside its block where its tick
    fell (the FM-1's D1 offsets); command events stay at the block start."""
    run = parse_script(script)
    block_log = load_log(script.with_suffix(".jsonl"))
    d1_log = load_log(script.with_name(script.stem + ".d1.jsonl"))
    assert len(d1_log) == len(block_log), script.stem
    for i, (x, y) in enumerate(zip(block_log, d1_log), 1):
        where = f"{script.stem}.d1.jsonl:{i}"
        assert {k: v for k, v in x.items() if k != "frame"} == {
            k: v for k, v in y.items() if k != "frame"}, where
        start = y["block"] * run["block"]
        assert start <= y["frame"] < start + run["block"], where


def test_d1_traces_present():
    assert len(D1_SCRIPTS) >= 3
    for p in FIX.glob("*.d1.jsonl"):
        assert FIX / (p.name[: -len(".d1.jsonl")] + ".verbs") in D1_SCRIPTS, p.name


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_movy1_sets(script):
    out = script.with_name(script.stem + ".out.movy1").read_text(encoding="utf-8")
    lines = out.splitlines()
    assert lines[0] == "movy1", script.stem
    assert [ln.split()[0] for ln in lines[1:4]] == ["bpm", "swing", "link"], script.stem
    # Movy's export lists every one of its 16 tracks.
    assert sum(ln.startswith("tk ") for ln in lines) == MOVY_TRACKS, script.stem
    known = {"bpm", "swing", "link", "sg", "tk", "pm", "ps", "au", "cl", "cp", "lk", "tg"}
    assert all(ln.split()[0] in known for ln in lines[1:]), script.stem
    state = script.with_name(script.stem + ".in.movy1")
    if state.exists():
        assert state.read_text(encoding="utf-8").splitlines()[0] == "movy1"


def test_oracle_summary():
    rows = [json.loads(line) for line in
            (FIX / "oracle-summary.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["script"] for r in rows] == [s.name for s in SCRIPTS]
    for r, s in zip(rows, SCRIPTS):
        run = parse_script(s)
        assert (r["rate"], r["block"], r["tracks"]) == (run["rate"], run["block"], run["tracks"])
        assert r["blocks"] == run["last_block"] + 1, s.stem
        assert r["events"] == len(load_log(s.with_suffix(".jsonl"))), s.stem
        # Only the D5 fixture is meant to reach Movy's nudge panic.
        if "panic" in s.stem:
            assert r["panics"], s.stem
            for p in r["panics"]:
                assert p["cmd"].startswith("enudge ") and "clip.rs" in p["panic"]
        else:
            assert r["panics"] == [], s.stem
