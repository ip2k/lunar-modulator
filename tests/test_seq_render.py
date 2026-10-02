"""The sequencer through fm1-render (docs/13 §7 and stage M2, the parts that
need no engine API change): per-track routing to the sound engine or to
USB-MIDI, notes and locks at their own frame through split renders, locks
reaching the engine parameter their lane names, and the same audio at any
host block size. fm1-render hosts the core through the shared bridge
(engines/include/fm1_seq_host.h), so these are its tests too: lane labels,
locks that split a block only when the engine takes them, the event log of
every oracle script, and a buffer the size the virtual FM-1 will use.
"""
import json
import math
import re
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from tests.seq_helpers import RENDER, ons, seq_tools  # noqa: F401
from tests.test_seq_core import d1_frame

RATE = 44118
FIX = Path(__file__).resolve().parent / "fixtures" / "movy"
ORACLE = sorted(FIX.glob("*.verbs")) + sorted((FIX / "random").glob("*.verbs"))


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
    bad = subprocess.run([str(RENDER), "--engine", "test-sine", "--events", "256"],
                         capture_output=True, text=True)
    assert bad.returncode == 2 and "--events needs --cmd or --seq" in bad.stderr


# ---- The host bridge (engines/include/fm1_seq_host.h) ---------------------------------------

LANE = (f"#! rate={RATE} block=64 tracks=1 end={RATE}\n"
        "@0 tog 0 0 60 100;slen 0 0 0 -1 380\n"
        "@0 alabel 0 0 {label};abase 0 0 {base};aset 0 0 2 {a} 1;aset 0 0 6 {b} 1\n@0 play\n")


@pytest.mark.parametrize("engine,name,values", [("macro", "Timbre", (0, 127, 20)),
                                                ("test-sine", "Volume", (127, 0, 90))])
def test_a_lane_label_names_the_parameter_after_its_last_colon(seq_tools, tmp_path, engine, name,
                                                               values):
    """The part after the last ':' names the parameter, without ASCII case:
    three spellings lock the same parameter, and a label naming none of the
    engine's is sent and skipped, which sounds different."""
    base, a, b = values
    locks, raws = [], []
    for k, label in enumerate([f"synth:{name.upper()}", name.lower(), f"a:b:{name}"]):
        s, _, _, raw = render(tmp_path, LANE.format(label=label, base=base, a=a, b=b), engine=engine,
                              name=f"l{k}")
        locks.append(s["seq_locks_to_engine"])
        raws.append(raw)
    assert locks[0] > 0 and locks[0] == locks[1] == locks[2]
    assert raws[0] == raws[1] == raws[2]
    s, _, ev, raw = render(tmp_path, LANE.format(label="synth:Nothing", base=base, a=a, b=b),
                           engine=engine, name="none")
    assert s["seq_locks_to_engine"] == 0 and len([e for e in ev if e["kind"] == "cc"]) >= 2
    assert raw != raws[0], "the locks change the sound"


@pytest.mark.parametrize("v", [127, 64, 1])
def test_a_float_lock_sets_min_plus_range_times_v_over_127(seq_tools, tmp_path, v):
    """fm1_seq_lock_value's float expression, which fm1-render always used: a
    lock of v on test-sine's Volume (0..1), sent before the note, sounds
    exactly like Volume set to the float v/127 at the start."""
    want = struct.unpack("<f", struct.pack("<f", v / 127))[0]
    plain = f"#! rate={RATE} block=64 tracks=1 end=8820\n@0 tog 0 0 69 100\n@0 play\n"
    locked = plain.replace("@0 play", f"@0 alabel 0 0 synth:Volume;abase 0 0 {v};play")
    s, _, _, raw = render(tmp_path, locked, name="locked")
    _, _, _, ref = render(tmp_path, plain, extra=["--param", f"Volume={want:.17g}"], name="param")
    assert s["seq_locks_to_engine"] > 0 and raw == ref


def test_a_lock_the_engine_cannot_take_does_not_split_the_block(seq_tools, tmp_path):
    """The engines render a block cut into pieces exactly as a whole one (the
    same WAV at blocks of 1, 7 and 64, above), so the WAV cannot show a
    split; seq_splits (render calls starting inside a block) can. A lane
    naming no parameter adds no split; one naming Volume does."""
    plain = (f"#! rate={RATE} block=64 tracks=1 end={RATE}\n"
             "@0 tog 0 0 84 100;tog 0 4 86 100\n@0 play\n")
    lane = plain.replace("@0 play", "@0 alabel 0 0 synth:Nothing;abase 0 0 0;aset 0 0 2 90 1;"
                                    "aset 0 0 6 30 1\n@0 play")
    s0, _, _, raw0 = render(tmp_path, plain, name="plain")
    s1, _, ev1, raw1 = render(tmp_path, lane, name="lane")
    s2, _, _, _ = render(tmp_path, lane.replace("synth:Nothing", "synth:Volume"), name="known")
    assert len([e for e in ev1 if e["kind"] == "cc"]) >= 2 and s1["seq_locks_to_engine"] == 0
    assert s1["seq_splits"] == s0["seq_splits"] > 0
    assert raw1 == raw0
    assert s2["seq_locks_to_engine"] > 0 and s2["seq_splits"] > s0["seq_splits"]


def script_block(script):
    return int(re.search(r"\bblock=(\d+)", script.read_text().splitlines()[0]).group(1))


@pytest.mark.parametrize("script", ORACLE, ids=lambda p: p.stem)
def test_every_oracle_script_logs_as_fm1_seq_and_drops_nothing(seq_tools, tmp_path, script):
    """fm1-render, through the bridge, logs byte for byte what fm1-seq logs:
    at 64-frame blocks and at the script's own, in both modes. Nothing is
    dropped, and in the default mode a 64-frame block holds at most 7 events
    (measured), far inside the 256 the virtual FM-1 is to have. Integer-only,
    so it holds at 32 bits and under the sanitizers too."""
    state = script.with_name(script.stem + ".in.movy1")
    extra = ["--seq", str(state)] if state.exists() else []
    rlog, slog = tmp_path / "r.jsonl", tmp_path / "s.jsonl"
    for compat in (False, True):
        mode = ["--compat"] if compat else []
        for block in sorted({64, script_block(script)}):
            res = subprocess.run([str(RENDER), "--cmd", str(script), *extra, *mode, "--engine",
                                  "test-sine", "--frames", str(block), "--log-events", str(rlog)],
                                 check=True, capture_output=True, text=True)
            subprocess.run([str(seq_tools), "--cmd", str(script), *extra, *mode, "--block",
                            str(block), "--log", str(slog)], check=True, capture_output=True)
            assert rlog.read_bytes() == slog.read_bytes(), (compat, block)
            s = json.loads(res.stdout)
            assert s["seq_dropped"] == 0, (compat, block)
            if not compat and block == 64:
                assert 0 < s["seq_max_block_events"] <= 7


def full_stop_script(tracks=8, stop_at=4096):
    """Every track plays an 8-note chord with all 8 lanes locked away from
    their base: 64 gates and 64 lanes, both full at 8 tracks."""
    lines = [f"#! rate={RATE} block=64 tracks={tracks} end={stop_at + 640}"]
    for t in range(tracks):
        chord = " ".join(f"{48 + 3 * t + k} 100" for k in range(8))
        lines.append(f"@0 tog {t} 0 {chord};slen {t} 0 0 -1 380")
        lines.append("@0 " + ";".join(f"alabel {t} {lane} synth:L{lane};aset {t} {lane} 0 100 1"
                                      for lane in range(8)))
    lines += ["@0 play", f"@{stop_at} stop"]
    return "\n".join(lines) + "\n"


def test_an_app_sized_event_buffer_takes_a_full_stop(seq_tools, tmp_path):
    """256 events per block, the size the virtual FM-1 is to use: a stop at
    full load sends 64 note-offs and 64 base reverts (D6) at once, and the
    block's advance adds the transport's Stop: 129 events, which is
    fm1_seq_cmd_max_events at 8 tracks and 64 gates. Nothing is dropped and
    every note closes. A 100-event buffer does drop, and says so."""
    script = full_stop_script()
    s, _, ev, _ = render(tmp_path, script, extra=["--events", "256"], name="app")
    assert s["seq_dropped"] == 0 and s["seq_refused"] == 0
    stop = [e for e in ev if e["block"] == 4096 // 64]
    assert len([e for e in stop if e["kind"] == "off"]) == 64
    assert len([e for e in stop if e["kind"] == "cc" and e["b"] == 0]) == 64
    assert [e["kind"] for e in stop][-1] == "stop" and len(stop) == 64 + 8 * 8 + 1
    sounding = {}
    for e in ev:
        if e["kind"] in ("on", "off"):
            k = (e["track"], e["a"])
            sounding[k] = sounding.get(k, 0) + (1 if e["kind"] == "on" else -1)
    assert len(sounding) == 64 and not any(sounding.values()), "a note left sounding"
    assert s["seq_max_block_events"] >= len(stop)
    s, _, _, _ = render(tmp_path, script, extra=["--events", "100"], name="small")
    assert s["seq_dropped"] > 0


def test_the_default_event_buffer_holds_more_than_an_app_sized_one(seq_tools, tmp_path):
    """fm1-render's default stays 65,536 events: 16 tracks at full load put
    more than 256 events in one block, which the default holds whole and an
    app-sized buffer does not. --events takes a decimal count, nothing else."""
    script = full_stop_script(tracks=16)
    s, _, _, _ = render(tmp_path, script, name="default")
    assert s["seq_dropped"] == 0 and s["seq_max_block_events"] > 256
    s, _, _, _ = render(tmp_path, script, extra=["--events", "256"], name="app")
    assert s["seq_dropped"] > 0 and s["seq_max_block_events"] <= 256
    cmd_file = tmp_path / "default.txt"
    for bad in ("0", "65537", "0x100", "256k", ""):
        res = subprocess.run([str(RENDER), "--cmd", str(cmd_file), "--events", bad],
                             capture_output=True, text=True)
        assert res.returncode == 2 and "--events wants 1..65536" in res.stderr, bad


MIDI_LANE = (f"#! rate={RATE} block=64 tracks=2 end={RATE}\n"
             "@0 tog 0 0 84 100;slen 0 0 0 -1 380;tog 1 0 60 100;tog 1 4 64 100\n"
             "@0 alabel 1 0 synth:Volume;abase 1 0 127;aset 1 0 2 0 1;aset 1 0 6 64 1\n"
             "@0 play\n")


def test_a_lane_on_a_midi_track_never_reaches_the_engine(seq_tools, tmp_path):
    """Track 1 goes to USB-MIDI: its locks are logged (CC 102+lane) even
    though the lane names the engine's Volume, but the engine never gets
    them, so the sound is that of the same script without the lane. Routed
    to the engine, the same locks reach it."""
    s, _, ev, raw = render(tmp_path, MIDI_LANE, name="midi")
    assert len([e for e in ev if e["kind"] == "cc" and e["track"] == 1]) >= 2
    assert s["seq_locks_to_engine"] == 0 and s["seq_notes_to_engine"] > 0
    lines = MIDI_LANE.splitlines(keepends=True)
    _, _, _, ref = render(tmp_path, "".join(lines[:2] + lines[3:]), name="nolane")
    assert raw == ref
    s, _, _, _ = render(tmp_path, MIDI_LANE.replace("@0 play", "@0 route 1 1 0;play"), name="routed")
    assert s["seq_locks_to_engine"] >= 2


def test_with_no_engine_the_events_are_logged_and_the_input_passes(seq_tools, tmp_path):
    """No --engine: the bridge gets no sink, so nothing is rendered or split
    and the --input signal goes through untouched, while the log holds the
    events an engine would have had."""
    common = ["--input", "sine", "--rate", str(RATE), "--frames", "64", "--seconds", "0.75"]
    s, _, ev, raw = render(tmp_path, TWO_TRACKS, extra=common, engine=None, name="none")
    assert s["engine"] is None and s["seq_notes_to_engine"] == 0 and s["seq_splits"] == 0
    assert s["seq_events"] == len(ev) > 0 and len(ons(ev, 0)) > 0
    _, _, ev_engine, _ = render(tmp_path, TWO_TRACKS, extra=common[2:], name="engine")
    assert ev == ev_engine
    wav = tmp_path / "plain.wav"
    subprocess.run([str(RENDER), *common, "--out", str(wav)], check=True, capture_output=True)
    with wave.open(str(wav), "rb") as w:
        assert w.readframes(w.getnframes()) == raw


def test_the_bridge_checks_itself(seq_tools):
    """engines/test/seq_host_test.c drives the bridge where fm1-render does
    not: typed commands, realtime input and live notes against the same text
    lines (same events every block, same set), every sink call at its
    event's frame and in order, the room figures, the length-bounded `rt`
    parser, lane labels and lock values."""
    res = subprocess.run([str(seq_tools.parent / "fm1-seq-host-test")], capture_output=True,
                         text=True)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["ok"] and out["events"] > 100 and out["sink_calls"] > 20 and out["splits"] > 10
