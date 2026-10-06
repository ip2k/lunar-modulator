"""Shared helpers for the sequencer tests (tests/test_seq*.py).

`Script` writes a timed verb script (engines/host/seq_script.h) the way
Movy's own tests drive its engine: commands between blocks, `run_ticks(n)`
advancing whole blocks until n master ticks have fired. It keeps an exact
model of Movy's integer clock (clock.rs) so it knows which frame that is; the
model resets wherever the script starts the transport, which the test says
with `starts=True` (play, launch or record from stopped, a scene from stopped).

`run()` plays it through engines/build/fm1-seq and returns the event log and
the state dumps: `snap(name)` is the state at the current frame after that
frame's commands, `peek(name)` the state before them.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"
SEQ = ENGINES / "build" / "fm1-seq"
SEQ_CHECK = ENGINES / "build" / "fm1-seq-check"
RENDER = ENGINES / "build" / "fm1-render"

PPQN = 96
TPS = 24            # ticks per step
TPB = 384           # ticks per bar
MOVY_RATE = 44100   # Movy's tests run at 44.1 kHz in 128-frame blocks
MOVY_BLOCK = 128


@pytest.fixture(scope="session")
def seq_tools():
    if not shutil.which("make") or not (shutil.which("cc") or shutil.which("gcc")):
        pytest.skip("no make / C compiler")
    subprocess.run(["make", "-C", str(ENGINES), "-j4"], check=True, stdout=subprocess.DEVNULL)
    return SEQ


class Result:
    def __init__(self, events, states, marks, end):
        self.events = events
        self._states = states
        self._marks = marks
        self.end = end

    def state(self, name):
        for s in self._states:
            if s["kind"] == "label" and s["label"] == name:
                return s
        raise KeyError(name)

    def between(self, a, b):
        """Events of blocks whose start frame lies in [frame(a), frame(b))."""
        fa = self._marks[a][1] if isinstance(a, str) else a
        fb = self._marks[b][1] if isinstance(b, str) else b
        return [e for e in self.events if fa <= e["block_start"] < fb]


def track(state, t):
    return state["tracks"][t]


def notes(state, t, slot=None):
    tr = state["tracks"][t]
    slot = tr["active"] if slot is None else slot
    clip = tr["clips"].get(str(slot))
    if not clip:
        return []
    return [dict(zip(("tick", "gate", "pitch", "vel", "step", "suppress", "fired"), n))
            for n in clip["notes"]]


def clip(state, t, slot=None):
    tr = state["tracks"][t]
    slot = tr["active"] if slot is None else slot
    return tr["clips"].get(str(slot))


def ons(events, track=None, pitch=None):
    return [e for e in events if e["kind"] == "on" and (track is None or e["track"] == track)
            and (pitch is None or e["a"] == pitch)]


def offs(events, track=None, pitch=None):
    return [e for e in events if e["kind"] == "off" and (track is None or e["track"] == track)
            and (pitch is None or e["a"] == pitch)]


def ccs(events, track=0):
    """(lane, value) of every lock, as Movy's tests' ccs0 helper."""
    return [(e["a"] - 102, e["b"]) for e in events if e["kind"] == "cc" and e["track"] == track]


def kinds(events, kind):
    return [e for e in events if e["kind"] == kind]


class Script:
    def __init__(self, tracks=16, rate=MOVY_RATE, block=MOVY_BLOCK, bpm_x100=12000):
        self.tracks = tracks
        self.rate = rate
        self.block = block
        self.bpm_x100 = bpm_x100
        self.frame = 0
        self.accum = 0
        self.tick = 0            # Movy's clock.tick: fires whether or not playing
        self.lines = []
        self.marks = {}

    # -- commands ---------------------------------------------------------
    def cmd(self, ops, starts=False):
        self.lines.append(f"@{self.frame} {ops}")
        if starts:
            self.accum = 0
            self.tick = 0
        return self

    def play(self):
        return self.cmd("play", starts=True)

    def bpm(self, v):
        self.bpm_x100 = min(max(v, 2000), 30000)
        return self.cmd(f"bpm {v}")

    # -- time ---------------------------------------------------------------
    def blocks(self, n=1, frames=None):
        f = self.block if frames is None else frames
        thr = self.rate * 6000
        for _ in range(n):
            self.accum += f * self.bpm_x100 * PPQN
            fired = self.accum // thr
            self.accum -= fired * thr
            self.tick += fired
            self.frame += f
        return self

    def run_ticks(self, n):
        target = self.tick + n
        while self.tick < target:
            self.blocks(1)
        return self

    def run_bars(self, n):
        return self.run_ticks(n * TPB)

    # -- observation --------------------------------------------------------
    def snap(self, name):
        """State dump here: after the commands written so far at this frame,
        before the ones written after it."""
        self.lines.append(f"#?@{self.frame} {name}")
        self.marks[name] = ("label", self.frame)
        return self

    peek = snap

    def mark(self, name):
        """A frame to slice events at (state not needed)."""
        self.marks[name] = ("mark", self.frame)
        return self

    def text(self, end=None):
        head = f"#! rate={self.rate} block={self.block} tracks={self.tracks}"
        if end is not None:
            head += f" end={end}"
        return "\n".join([head] + self.lines) + "\n"

    def run(self, tool, tmp_path, compat=True, end=None, extra=(), name="s", seq=None):
        end = self.frame if end is None else end
        path = tmp_path / f"{name}.txt"
        path.write_text(self.text(end))
        log = tmp_path / f"{name}.jsonl"
        state = tmp_path / f"{name}.json"
        cmd = [str(tool), "--cmd", str(path), "--log", str(log), "--state", str(state)]
        if compat:
            cmd.append("--compat")
        if seq is not None:
            set_path = tmp_path / f"{name}.movy1"
            set_path.write_text(seq)
            cmd += ["--seq", str(set_path)]
        cmd += list(extra)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        events = []
        for line in log.read_text().splitlines():
            e = json.loads(line)
            events.append(e)
        # block start frames, for slicing (the log's frame is the event's own)
        for e in events:
            e["block_start"] = e["block"] * self.block
        doc = json.loads(state.read_text())
        marks = {k: v for k, v in self.marks.items()}
        return Result(events, doc["snaps"], marks, doc["end"])


def run_script(tool, tmp_path, text, compat=False, extra=(), name="r"):
    """Run a literal script; returns (events, end_state)."""
    path = tmp_path / f"{name}.txt"
    path.write_text(text)
    log = tmp_path / f"{name}.jsonl"
    state = tmp_path / f"{name}.json"
    cmd = [str(tool), "--cmd", str(path), "--log", str(log), "--state", str(state)]
    if compat:
        cmd.append("--compat")
    cmd += list(extra)
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    events = [json.loads(line) for line in log.read_text().splitlines()]
    return events, json.loads(state.read_text())["end"]
