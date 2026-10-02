"""The sequencer through fm1-render (docs/13 §7 and stage M2, the parts that
need no engine API change): per-track routing to the sound engine or to
USB-MIDI, notes and locks at their own frame through split renders, locks
reaching the engine parameter their lane names, and the same audio at any
host block size.
"""
import json
import math
import subprocess
import wave

import pytest

from tests.seq_helpers import RENDER, ons, seq_tools  # noqa: F401
from tests.test_seq_core import d1_frame

RATE = 44118


def render(tmp_path, script, extra=(), name="r", engine="test-sine", seconds=None):
    cmd_file = tmp_path / f"{name}.txt"
    cmd_file.write_text(script)
    wav = tmp_path / f"{name}.wav"
    log = tmp_path / f"{name}.jsonl"
    cmd = [str(RENDER), "--cmd", str(cmd_file), "--out", str(wav), "--log-events", str(log)]
    if engine:
        cmd += ["--engine", engine]
    if seconds:
        cmd += ["--seconds", str(seconds)]
    cmd += list(extra)
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    summary = json.loads(res.stdout)
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    left = [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), 4)]
    events = [json.loads(line) for line in log.read_text().splitlines()]
    return summary, left, events, raw


def rms(x):
    return math.sqrt(sum(v * v for v in x) / max(len(x), 1))


TWO_TRACKS = (f"#! rate={RATE} block=64 tracks=4 end={RATE}\n"
              "@0 tog 0 0 84 100;tog 0 4 86 100;tog 1 2 76 100\n@0 play\n")


def test_track_zero_plays_the_engine_by_default(seq_tools, tmp_path):
    s, left, ev, _ = render(tmp_path, TWO_TRACKS)
    assert s["seq_notes_to_engine"] == len(ons(ev, 0)) > 0
    assert len(ons(ev, 1)) > 0, "track 1 goes to USB-MIDI: logged, not played"
    assert s["seq_bytes"] == 18056 and s["seq_refused"] == 0
    assert rms(left) > 100


def test_a_track_routed_to_midi_is_silent(seq_tools, tmp_path):
    s, left, ev, _ = render(tmp_path, TWO_TRACKS, extra=["--route", "0:midi:1"])
    assert s["seq_notes_to_engine"] == 0 and len(ons(ev, 0)) > 0
    assert max(abs(v) for v in left) == 0


def test_routes_choose_which_tracks_play_the_engine(seq_tools, tmp_path):
    s, _, ev, _ = render(tmp_path, TWO_TRACKS, extra=["--route", "1:engine"])
    assert s["seq_notes_to_engine"] == len(ons(ev, 1))
    s, _, ev, _ = render(tmp_path, TWO_TRACKS, extra=["--route", "0:engine", "--route", "1:engine"],
                         name="both")
    assert s["seq_notes_to_engine"] == len(ons(ev, 0)) + len(ons(ev, 1))
    s, _, ev, _ = render(tmp_path, TWO_TRACKS.replace("@0 play", "@0 route 1 1 0;play"), name="verb")
    assert s["seq_notes_to_engine"] == len(ons(ev, 0)) + len(ons(ev, 1)), "the verb adds track 1"


@pytest.mark.parametrize("compat", [False, True])
def test_a_note_sounds_from_its_own_frame(seq_tools, tmp_path, compat):
    """D1 through the renderer: the block is split at the note-on, so the
    first non-zero sample is the event's frame (229 at 120 BPM, 44,118 Hz);
    in compat mode it is the start of the 64-frame block the tick falls in."""
    script = f"#! rate={RATE} block=64 tracks=1 end=4410\n@0 tog 0 0 96 127\n@0 play\n"
    _, left, ev, _ = render(tmp_path, script, extra=["--compat"] if compat else [])
    frame = d1_frame(0, 0)
    assert frame == 229
    want = frame if not compat else frame // 64 * 64
    assert ons(ev)[0]["frame"] == want
    first = next(i for i, v in enumerate(left) if v)
    assert first == want


def test_locks_set_the_parameter_their_lane_names(seq_tools, tmp_path):
    """Lane 0 is labelled synth:Volume, so its locks set test-sine's Volume
    (0..1 from 0..127). A lock of 0 on step 2 silences the held note from that
    step's frame on; the latch holds it there until step 8's lock of 127."""
    script = (f"#! rate={RATE} block=64 tracks=1 end={2 * RATE}\n"
              "@0 tog 0 0 84 100;slen 0 0 0 -1 380\n"
              "@0 alabel 0 0 synth:Volume;abase 0 0 127;aset 0 0 2 0 1;aset 0 0 8 127 1\n@0 play\n")
    s, left, ev, _ = render(tmp_path, script)
    locks = [e for e in ev if e["kind"] == "cc"]
    assert [(e["tick"], e["b"]) for e in locks] == [(0, 127), (0, 127), (47, 0), (191, 127)]
    assert s["seq_locks_to_engine"] == 4
    off_at = locks[2]["frame"]
    on_at = locks[3]["frame"]
    assert off_at == d1_frame(0, 47)
    assert rms(left[off_at - 600:off_at]) > 1000
    assert max(abs(v) for v in left[off_at:on_at]) == 0
    assert rms(left[on_at + 300:on_at + 900]) > 1000
    s, _, _, _ = render(tmp_path, script.replace("synth:Volume", "synth:Cutoff"), name="none")
    assert s["seq_locks_to_engine"] == 0, "a lane naming no parameter of this engine is ignored"


def test_an_enum_lock_selects_a_bin(seq_tools, tmp_path):
    """A lock on Macro's Model (ENUM, eight models) picks bin floor(v*8/128):
    0 and 15 are both model 0, 16 is model 1."""
    script = (f"#! rate={RATE} block=64 tracks=1 end={RATE}\n"
              "@0 tog 0 0 57 100;slen 0 0 0 -1 300\n"
              "@0 alabel 0 0 synth:Model;abaseq 0 0 {v};play\n")
    raw = {}
    for v in (0, 15, 16):
        s, _, _, raw[v] = render(tmp_path, script.format(v=v), engine="macro", name=f"m{v}")
        assert s["seq_locks_to_engine"] == 1
    assert raw[0] == raw[15] and raw[0] != raw[16]


@pytest.mark.parametrize("engine", ["test-sine", "macro", "sixop"])
def test_audio_is_the_same_at_host_blocks_of_1_7_and_64(seq_tools, tmp_path, engine):
    """docs/13 stage M2's exit: the same output at host blocks of 1, 7 and
    64 frames. Commands sit on multiples of 448 frames (lcm of 7 and 64)."""
    script = ("#! rate={rate} block={block} tracks=2 end={end}\n"
              "@0 tog 0 0 60 100 64 90;tog 0 3 67 100;tog 0 6 72 80;cscl 0 3 2;swing 62\n"
              "@0 tog 1 1 48 100;tog 1 5 55 70\n"
              "@0 alabel 0 1 synth:Timbre;alabel 0 2 synth:Volume;abase 0 2 100;"
              "aset 0 1 3 20 1;aset 0 2 6 60 1\n"
              "@0 route 1 1 0;play\n@{stop} stop\n@{play} play\n")
    out = {}
    for block in (1, 7, 64):
        text = script.format(rate=RATE, block=block, end=448 * 100, stop=448 * 60, play=448 * 70)
        s, _, ev, raw = render(tmp_path, text, engine=engine, name=f"b{block}")
        out[block] = raw
        assert s["seq_notes_to_engine"] > 5
    assert out[1] == out[64] and out[7] == out[64]


def test_the_renderer_logs_what_fm1_seq_logs(seq_tools, tmp_path):
    script = (f"#! rate={RATE} block=64 tracks=4 end={RATE * 2}\n"
              "@0 tog 0 0 60 100;tog 1 4 62 100;alabel 0 0 synth:Timbre;aset 0 0 3 50\n"
              "@0 metro 1;play\n@44800 stop\n@50000 play\n")
    _, _, ev, _ = render(tmp_path, script, engine="macro")
    p = tmp_path / "s.txt"
    p.write_text(script)
    log = tmp_path / "s.jsonl"
    subprocess.run([str(seq_tools), "--cmd", str(p), "--log", str(log)], check=True)
    assert [json.loads(line) for line in log.read_text().splitlines()] == ev


def test_a_set_alone_plays_from_the_start(seq_tools, tmp_path):
    """--seq without --cmd: the set plays from frame 0 (an implicit `play`)."""
    from tests.test_seq_core import FIXTURES
    wav = tmp_path / "f.wav"
    log = tmp_path / "f.jsonl"
    res = subprocess.run([str(RENDER), "--engine", "macro", "--seq", str(FIXTURES / "movy-chains.movy1"),
                          "--seconds", "4", "--out", str(wav), "--log-events", str(log)],
                         check=True, capture_output=True, text=True)
    s = json.loads(res.stdout)
    ev = [json.loads(line) for line in log.read_text().splitlines()]
    assert s["seq_notes_to_engine"] == len(ons(ev, 0)) > 10


def test_plain_renders_are_unchanged(seq_tools, tmp_path):
    """Without --cmd or --seq the renderer is as it was: no sequencer keys in
    its summary, and the sequencer flags are refused on their own."""
    res = subprocess.run([str(RENDER), "--engine", "test-sine", "--note", "0:69:100:0.5",
                          "--seconds", "0.5"], check=True, capture_output=True, text=True)
    assert not [k for k in json.loads(res.stdout) if k.startswith("seq_")]
    bad = subprocess.run([str(RENDER), "--engine", "test-sine", "--route", "0:engine"],
                         capture_output=True, text=True)
    assert bad.returncode == 2
