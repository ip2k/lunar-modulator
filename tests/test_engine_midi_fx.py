"""MIDI effects in engine API v3 (FM1_KIND_MIDI_FX, engines/include/fm1_engine.h)
and the host stage that runs them in front of the sounds on the sequencer's
bridge (engines/include/fm1_mfx_host.h, engines/seq/mfx_host.c), driven
through fm1-render --mfx with the arpeggiator (engines/midi_fx/arp_engine.c).

The contract: the arp lists as a MIDI effect with its parameters; a
bypassed chain changes nothing; the output is the same at blocks of 1, 7, 64
and 448 frames; its ticks are the sequencer's (and run on at the tempo while
it is stopped, or at --tempo without one); Start restarts it and Stop
flushes it; every note-on an engine gets has its note-off, whatever is
switched, latched or stopped in between (a seeded fuzz); a note-off follows
its note-on into or past the chain; chains of two; bad flags are refused;
the host stage and the wrapper never allocate, print or call libm. Since
2026-10-06 (owner): while the sequencer plays the arp's steps fall on its
grid, Sync Key and Free coherent with it, and Stop lets go of what the
sequencer gave a latched arp while the keys latched by hand play on.
"""
import json
import random
import shutil
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, renderer  # noqa: F401

STEP16 = RATE * 60 / (120 * 4)        # a 1/16 step at 120 BPM, in frames
BOUND = 448                           # a block boundary at 1, 7, 64 and 448 frames


def at(frame):
    """A time fm1-render applies at the block that starts at `frame` (just
    before it, so rounding never pushes it a block later)."""
    return f"{(frame - 0.25) / RATE:.9f}"


def note(frame, key, vel, frames, sound=None):
    start, dur = at(frame), f"{frames / RATE:.9f}"
    if sound is None:
        return ["--note", f"{start}:{key}:{vel}:{dur}"]
    return ["--sound-note", f"{sound}:{start}:{key}:{vel}:{dur}"]


def mfx_run(renderer, tmp_path, args, name="r", log=True, script=None):
    """fm1-render with `args`; returns (summary, wav bytes, arp events)."""
    wav, arp = tmp_path / f"{name}.wav", tmp_path / f"{name}.jsonl"
    cmd = [str(renderer), *args, "--out", str(wav)]
    if script is not None:
        path = tmp_path / f"{name}.verbs"
        path.write_text(script)
        cmd += ["--cmd", str(path)]
    if log:
        cmd += ["--log-mfx", str(arp)]
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    events = [json.loads(line) for line in arp.read_text().splitlines()] if log else []
    return json.loads(res.stdout.strip().splitlines()[-1]), wav.read_bytes(), events


def ons(events, unit=0):
    return [(e["t"], e["key"]) for e in events if e["k"] == "on" and e["u"] == unit]


def listed(renderer):
    return {e["id"]: e for e in json.loads(subprocess.run(
        [str(renderer), "--list"], check=True, capture_output=True, text=True).stdout)}


# ---- What the arp is -----------------------------------------------------------------------

def test_the_arp_lists_as_a_midi_effect(renderer):
    e = listed(renderer)["arp"]
    assert (e["kind"], e["max_voices"], e["per_note"], e["render_ext"], e["pads"]) == \
        ("midi_fx", 0, False, False, None)
    assert "Yarns" in e["credits"] and "MCL" in e["credits"] and "Super Arp" in e["credits"]
    params = {p["name"]: p for p in e["params"]}
    # 24: the core's 25 less SWING, which follows the set's swing (owner, 2026-10-06)
    assert len(params) == 24 and len(e["params"]) == 24 and "Swing" not in params
    pages = [p["page"] for p in e["params"]]
    assert pages == sorted(pages) and set(pages) == set(range(7))   # knob order is page order
    # PLAY, as the options note §2.4 lays it out: MODE, RATE, GATE, OCT
    assert [p["name"] for p in e["params"] if p["page"] == 0] == ["Mode", "Rate", "Gate", "Octaves"]
    assert params["Rate"]["names"][int(params["Rate"]["def"])] == "1/16"
    assert all(len(p["name"]) <= 10 for p in e["params"]), "a screen label holds 10 characters"


def test_its_lists_are_the_cores(renderer):
    """The wrapper's list names are the core's (fm1-arp --list), capitalised."""
    subprocess.run(["make", "-C", str(ENGINES), "-j4", "build/fm1-arp"], check=True,
                   stdout=subprocess.DEVNULL)
    core = json.loads(subprocess.check_output([str(ENGINES / "build" / "fm1-arp"), "--list"]))
    params = {p["name"]: p for p in listed(renderer)["arp"]["params"]}

    def norm(names):
        return [n.lower().replace(" ", "-") for n in names]
    assert norm(params["Mode"]["names"]) == core["modes"]
    assert norm(params["Order"]["names"]) == core["orders"]
    assert norm(params["Oct Mode"]["names"]) == core["oct_modes"]
    assert norm(params["Rate"]["names"]) == [r["name"] for r in core["rates"]]
    assert len(params["Pattern"]["names"]) == len(core["patterns"]) == 23   # All, then Yarns' 22


# ---- The chain changes nothing it does not touch -------------------------------------------

SCRIPT = (f"#! rate={RATE} block=64 tracks=8 end={BOUND * 300}\n"
          "@0 tog 0 0 48 100 55 100;slen 0 0 0 -1 160;tog 0 8 50 90 57 90;slen 0 8 8 -1 160\n"
          f"@{BOUND * 50} play\n@{BOUND * 250} stop\n")


def test_a_bypassed_arp_changes_nothing(renderer, tmp_path):
    base = ["--engine", "macro", *note(BOUND * 10, 60, 100, BOUND * 100),
            *note(BOUND * 120, 64, 90, BOUND * 40)]
    plain, a, _ = mfx_run(renderer, tmp_path, base, "plain", log=False, script=SCRIPT)
    off, b, ev = mfx_run(renderer, tmp_path, base + ["--mfx", "0:arp:off", "--mfx-param", "0:Rate=2"],
                         "off", script=SCRIPT)
    assert a == b and ev == [] and off["mfx_notes_in"] == 0
    assert plain["seq_notes_to_engine"] == off["seq_notes_to_engine"] > 0
    # ...and with the slots of several sounds
    multi = ["--sound", "1:shapes", *note(BOUND * 5, 67, 100, BOUND * 50, sound=1)]
    _, c, _ = mfx_run(renderer, tmp_path, base + multi, "m", log=False, script=SCRIPT)
    _, d, _ = mfx_run(renderer, tmp_path, base + multi + ["--mfx", "1:arp:off"], "m2", script=SCRIPT)
    assert c == d


# ---- Block size ------------------------------------------------------------------------------

def busy_args(block):
    """Live notes, the sequencer, toggles, latch, two sounds, a chain of two,
    everything on block boundaries common to 1, 7, 64 and 448 frames."""
    return (["--engine", "test-sine", "--sound", "1:test-sine", "--frames", str(block),
             "--mfx", "0:arp", "--mfx-param", "0:Mode=2", "--mfx-param", "0:Rate=2",
             "--mfx-param", "0:Octaves=1", "--mfx-param", "0:Ratchet=1",
             "--mfx-param", "0:Ratchet %=60", "--mfx-param", "0:Chance=80",
             "--mfx", "1:arp", "--mfx-param", "1:Mode=18", "--mfx-param", "1:Seed=5",
             "--mfx", "1:arp", "--mfx-param", "1:Rate=1",
             *note(BOUND * 3, 60, 100, BOUND * 90), *note(BOUND * 4, 64, 90, BOUND * 80),
             *note(BOUND * 30, 67, 80, BOUND * 30), *note(BOUND * 8, 72, 100, BOUND * 60, sound=1),
             *note(BOUND * 9, 75, 100, BOUND * 40, sound=1),
             "--mfx-param-at", f"0:{at(BOUND * 60)}:Latch=1",
             "--mfx-on-at", f"0:{at(BOUND * 140)}:0", "--mfx-on-at", f"0:{at(BOUND * 160)}:1",
             "--mfx-param-at", f"1.2:{at(BOUND * 100)}:Gate=150",
             "--mfx-on-at", f"0:{at(BOUND * 280)}:0", "--mfx-on-at", f"1:{at(BOUND * 280)}:0",
             "--mfx-on-at", f"1.2:{at(BOUND * 280)}:0"])


def test_the_output_is_the_same_at_any_block_size(renderer, tmp_path):
    runs = []
    for block in (1, 7, 64, 448):
        script = SCRIPT.replace("block=64", f"block={block}")
        s, wav, ev = mfx_run(renderer, tmp_path, busy_args(block), f"b{block}", script=script)
        assert s["notes_hung"] == 0 and s["mfx_dropped"] == 0
        runs.append((wav, ev, s["mfx_notes_out"], s["mfx_ticks"]))
    assert len(runs[0][1]) > 50, "the arps played little"
    assert all(r == runs[0] for r in runs[1:])


# ---- Time -------------------------------------------------------------------------------------

def test_the_ticks_are_the_sequencers(renderer, tmp_path):
    """With the sequencer playing, a 1/16 arp steps on the frames where the
    sequencer services ticks 0, 24, 48... (its clock events), and its first
    step is the first tick after Start."""
    script = (f"#! rate={RATE} block=64 tracks=8 end={BOUND * 200}\n"
              f"@0 bpm 13300\n@{BOUND * 20} play\n")
    log = tmp_path / "ev.jsonl"
    _, _, ev = mfx_run(renderer, tmp_path, ["--engine", "test-sine", "--mfx", "0:arp",
                                            "--mfx-param", "0:Sync=0",
                                            *note(BOUND * 2, 60, 100, BOUND * 190),
                                            "--log-events", str(log)], script=script)
    seq = [json.loads(line) for line in log.read_text().splitlines()]
    steps = [e["frame"] for e in seq if e["kind"] == "clock" and e["tick"] % 24 == 0]
    played = [t for t, _ in ons(ev) if t >= BOUND * 20]
    assert len(played) > 10
    assert played == steps[:len(played)]


@pytest.mark.parametrize("bpm", [100, 90])
def test_it_free_runs_at_the_tempo(renderer, tmp_path, bpm):
    """Without a sequencer the stage's own clock runs at --tempo; with one
    stopped, the sequencer's clock runs on at its tempo. A 1/16 step is
    rate x 60 / (bpm x 4) frames either way."""
    args = ["--engine", "test-sine", "--mfx", "0:arp", *note(0, 60, 100, RATE * 2)]
    script = None
    if bpm == 100:
        args += ["--tempo", "100", "--seconds", "2.2"]
    else:
        script = f"#! rate={RATE} block=64 tracks=8 end={int(RATE * 2.2)}\n@0 bpm 9000\n"
    _, _, ev = mfx_run(renderer, tmp_path, args, f"t{bpm}", script=script)
    frames = [t for t, _ in ons(ev)]
    gaps = {b - a for a, b in zip(frames, frames[1:])}
    step = RATE * 60 / (bpm * 4)
    assert len(frames) >= 10 and gaps <= {int(step), int(step) + 1}


def test_start_restarts_and_stop_leaves_the_keys(renderer, tmp_path):
    """A key held while stopped plays on the free-running clock; Play resets
    the arp, whose next step is the sequencer's first tick; Stop lets go of
    what the sequencer gave the arp, and nothing else (owner, 2026-10-06):
    the keys' note sounding then plays to its gate, and the arp plays on
    from the clock."""
    play, stop = BOUND * 41, BOUND * 160
    script = (f"#! rate={RATE} block=64 tracks=8 end={BOUND * 240}\n"
              f"@{play} play\n@{stop} stop\n")
    log = tmp_path / "ev.jsonl"
    s, _, ev = mfx_run(renderer, tmp_path, ["--engine", "test-sine", "--mfx", "0:arp",
                                            "--mfx-param", "0:Gate=200",
                                            *note(BOUND, 60, 100, BOUND * 230),
                                            *note(BOUND, 67, 100, BOUND * 230),
                                            "--mfx-on-at", f"0:{at(BOUND * 236)}:0",   # the last overlap
                                            "--log-events", str(log)], script=script)
    seq = [json.loads(line) for line in log.read_text().splitlines()]
    first_tick = min(e["frame"] for e in seq if e["kind"] == "clock")
    before = [t for t, _ in ons(ev) if t < play]
    after = [t for t, _ in ons(ev) if t >= play]
    assert before and after[0] == first_tick, "Play does not restart the arp on the first tick"
    assert ons(ev)[len(before)][1] == 60, "the restart does not begin the order again"
    offs_at_stop = [e for e in ev if e["k"] == "off" and e["t"] == stop]
    assert offs_at_stop == [], "Stop cut a note the keys made"
    assert [t for t, _ in ons(ev) if t > stop], "the arp stops with the sequencer"
    assert s["notes_hung"] == 0


# ---- Locked to the beat (owner, 2026-10-06) ---------------------------------------------------

TICK = RATE * 6000 / (12000 * 96)      # frames a tick at 120 BPM


def free_tick(k):
    """The frame of the k-th tick of the sequencer's clock while it is
    stopped (its sum runs from frame 0 at 120 BPM)."""
    return -(-k * RATE * 6000 // (12000 * 96)) - 1


def seq_ticks(log):
    """{tick: frame} of the sequencer's clock events (every fourth tick)."""
    return {e["tick"]: e["frame"] for e in (json.loads(x) for x in log.read_text().splitlines())
            if e["kind"] == "clock"}


def grid_runs(renderer, tmp_path, block):
    play, key = BOUND * 10, BOUND * 41      # the key: about tick 60, the next 1/16 is tick 72
    script = f"#! rate={RATE} block={block} tracks=8 end={BOUND * 160}\n@{play} play\n"
    runs = {}
    for name, extra, step, swing in (
            ("1/16", [], 24, 0),
            ("on-mid-bar", ["--mfx-on-at", f"0:{at(BOUND * 38)}:1"], 24, 0),
            ("1/8t", ["--mfx-param", "0:Rate=5"], 32, 0),
            ("swing", [], 24, 4)):        # the set's swing (owner, 2026-10-06)
        log = tmp_path / f"{name.replace('/', '')}-{block}.jsonl"
        mfx = ["--mfx", "0:arp:off" if name == "on-mid-bar" else "0:arp"]
        s, wav, ev = mfx_run(renderer, tmp_path, [
            "--engine", "test-sine", "--frames", str(block), *mfx, *extra,
            *note(BOUND, 48, 100, BOUND * 3), *note(key, 60, 100, BOUND * 100),
            "--mfx-on-at", f"0:{at(BOUND * 150)}:0", "--log-events", str(log)],
            name.replace("/", "") + str(block),
            script=script.replace("\n@", "\n@0 swing 60\n@", 1) if name == "swing" else script)
        ticks = seq_ticks(log)
        grid = {f for t, f in ticks.items() if t % (2 * step) in (0, step + swing)}
        played = [t for t, _ in ons(ev) if t >= play]
        if name != "on-mid-bar":                      # stopped: the next tick
            assert ons(ev)[0] == (min(free_tick(k) for k in range(1, 50) if free_tick(k) >= BOUND), 48)
        assert played[0] == min(f for f in grid if f >= key), name
        assert played[0] - key > 2 * TICK, f"{name}: the key started at the next tick"
        assert len(played) > 5 and set(played) <= grid, name
        assert s["notes_hung"] == 0
        runs[name] = (wav, ev)
    return runs


def test_the_arp_locks_to_the_beat_while_the_sequencer_plays(renderer, tmp_path):
    """While the sequencer plays, the arp's steps fall on its grid: a key
    pressed between steps waits for the next one of the rate (ticks counted
    from Start), not for the next tick; so does an arp switched on mid-bar;
    swing delays the odd steps as the grid's; 1/8 triplets fall on their
    own grid. Stopped, a key starts at the next tick, as before. The same at
    blocks of 1, 7 and 64 frames."""
    out = [grid_runs(renderer, tmp_path, b) for b in (1, 7, 64)]
    assert out[0] == out[1] == out[2]


def test_the_arp_swings_with_the_set_while_stopped(renderer, tmp_path):
    """The arp follows the set's swing (owner, 2026-10-06), stopped too:
    fm1-render's --swing without a sequencer, the set's `swing` with one.
    At 66 % an odd 1/16 step starts 6 ticks late, an even one on time."""
    def gaps(args, script=None, name="s"):
        _, _, ev = mfx_run(renderer, tmp_path, ["--engine", "test-sine", "--mfx", "0:arp", *args,
                                                *note(BOUND, 60, 100, BOUND * 60)],
                           name, script=script)
        t = [f for f, _ in ons(ev)]
        return [b - a for a, b in zip(t, t[1:])][:6]
    straight = gaps([], name="straight")
    assert max(straight) - min(straight) <= 1                # 24 ticks each, to a frame
    late = 6 * TICK
    for name, args, script in (("flag", ["--swing", "66"], None),
                               ("set", [], f"#! rate={RATE} block=64 tracks=8 end={BOUND * 70}\n@0 swing 66\n")):
        g = gaps(args, script, name)
        assert all(abs(a - (b + late)) <= 1 for a, b in zip(g[0::2], straight[0::2])), (name, g)
        assert all(abs(a - (b - late)) <= 1 for a, b in zip(g[1::2], straight[1::2])), (name, g)
    r = subprocess.run([str(renderer), "--engine", "test-sine", "--swing", "81"], capture_output=True)
    assert r.returncode == 2 and b"50..80" in r.stderr


@pytest.mark.parametrize("rate, step", [(4, 24), (5, 32)])
def test_the_beat_holds_through_tempo_changes(renderer, tmp_path, rate, step):
    """The tempo changes twice while the sequencer plays (slower, then
    faster, off any round tick): the arp's steps stay on the grid of ticks
    counted from Start, one on every step of the rate and none skipped or
    doubled across a change. The same at blocks of 1, 7 and 64 frames."""
    play, key = BOUND * 10, BOUND * 41
    runs = []
    for block in (1, 7, 64):
        script = (f"#! rate={RATE} block={block} tracks=8 end={BOUND * 400}\n@{play} play\n"
                  f"@{BOUND * 77} bpm 9137\n@{BOUND * 181} bpm 17311\n")
        log = tmp_path / f"seq-t{rate}-{block}.jsonl"
        s, wav, ev = mfx_run(renderer, tmp_path, [
            "--engine", "test-sine", "--frames", str(block), "--mfx", "0:arp",
            "--mfx-param", f"0:Rate={rate}", *note(key, 60, 100, BOUND * 340),
            "--mfx-on-at", f"0:{at(BOUND * 390)}:0", "--log-events", str(log)],
            f"t{rate}-{block}", script=script)
        ticks = seq_ticks(log)
        played = [t for t, _ in ons(ev) if t >= play]
        grid = sorted(f for t, f in ticks.items() if t % step == 0 and played[0] <= f <= played[-1])
        assert len(played) > 20 and played == grid, f"block {block}: off the grid, or a step lost"
        assert s["notes_hung"] == 0
        runs.append((wav, ev))
    assert runs[0] == runs[1] == runs[2]


@pytest.mark.parametrize("sync, first", [("Key", 48), ("Free", 96)])
def test_sync_key_and_free_on_the_beat(renderer, tmp_path, sync, first):
    """A Euclidean rhythm of one in four steps (Length 4, Fill 1), the
    sequencer playing, a key after tick 30. Sync at Key restarts the
    pattern at the next 1/16 of the grid (tick 48); at Free the pattern has
    run on from Start, so the key's first note waits for the rhythm's next
    onset, on the beat (tick 96). Both on the grid."""
    play = BOUND * 10
    key = play + int(33 * TICK)
    script = f"#! rate={RATE} block=64 tracks=8 end={BOUND * 200}\n@{play} play\n"
    log = tmp_path / "ev.jsonl"
    _, _, ev = mfx_run(renderer, tmp_path, [
        "--engine", "test-sine", "--mfx", "0:arp", "--mfx-param", f"0:Sync={0 if sync == 'Free' else 1}",
        "--mfx-param", "0:Length=4", "--mfx-param", "0:Fill=1", *note(key, 60, 100, BOUND * 150),
        "--log-events", str(log)], script=script)
    ticks = seq_ticks(log)
    assert ons(ev)[0][0] == ticks[first]
    assert [t for t, _ in ons(ev)][:3] == [ticks[first], ticks[first + 96], ticks[first + 192]]


# ---- Stop lets go of what the sequencer gave (owner, 2026-10-06) -----------------------------

def latch_stop_run(renderer, tmp_path, block):
    play, stop = BOUND * 20, BOUND * 200
    script = (f"#! rate={RATE} block={block} tracks=8 end={BOUND * 300}\n"
              "@0 tog 0 0 48 100;tog 0 8 55 100;slen 0 0 0 -1 60;slen 0 8 8 -1 60\n"
              f"@{play} play\n@{stop} stop\n")
    s, wav, ev = mfx_run(renderer, tmp_path, [
        "--engine", "test-sine", "--frames", str(block), "--mfx", "0:arp",
        "--mfx-param", "0:Latch=1", "--mfx-param", "0:Gate=150",
        *note(BOUND * 5, 60, 100, BOUND * 2), *note(BOUND * 5, 64, 100, BOUND * 2),
        "--mfx-on-at", f"0:{at(BOUND * 290)}:0"], f"s{block}", script=script)
    before = {k for t, k in ons(ev) if play <= t < stop}
    after = {k for t, k in ons(ev) if t >= stop}
    assert {48, 55} & before and {60, 64} <= before, before
    assert not ({48, 55} & before) - {48, 55}
    assert after == {60, 64}, "Stop kept the sequencer's notes, or dropped the hand's"
    sounding = set()
    for e in ev:                                 # what sounds just after Stop
        if e["t"] > stop:
            break
        (sounding.add if e["k"] == "on" else sounding.discard)(e["key"])
    assert not sounding & {48, 55}, sounding
    assert s["notes_hung"] == 0 and s["mfx_dropped"] == 0
    return wav, ev


def test_stop_releases_what_the_sequencer_fed_a_latched_arp(renderer, tmp_path):
    """A latched arp: a chord played by hand before Play, then track 1's
    notes, which join it while the sequencer plays (each origin latches
    against its own later notes, so the track's next note replaces its last
    and leaves the hand's chord). At Stop the track's notes leave the arp at
    once, latched or not, and their sounding note ends there; the hand's
    chord plays on. The same at blocks of 1, 7 and 64 frames; nothing hangs
    once the arp is bypassed."""
    runs = [latch_stop_run(renderer, tmp_path, b) for b in (1, 7, 64)]
    assert runs[0] == runs[1] == runs[2]


# ---- Notes are never left hanging ------------------------------------------------------------

def fuzz_args(seed, block):
    rnd = random.Random(seed)
    end = BOUND * 300
    args = ["--engine", "test-sine", "--sound", "1:test-sine", "--frames", str(block),
            "--mfx", f"0:arp{'' if rnd.random() < 0.5 else ':off'}",
            "--mfx", f"1:arp{'' if rnd.random() < 0.5 else ':off'}"]
    chain = rnd.random() < 0.4
    if chain:
        args += ["--mfx", "0:arp"]              # a chain of two
    for _ in range(rnd.randint(4, 14)):         # live notes on either sound
        start = rnd.randint(0, 250)
        args += note(BOUND * start, rnd.randint(48, 84), rnd.randint(1, 127),
                     BOUND * rnd.randint(1, 280 - start), sound=rnd.choice([None, 1]))
    params = [("Latch", 0, 1), ("Rate", 0, 16), ("Mode", 0, 21), ("Gate", 1, 200),
              ("Ratchet", 0, 3), ("Repeat", 0, 7), ("Octaves", 0, 3), ("Join", 0, 1),
              ("Sync", 0, 1), ("Chance", 0, 100), ("Chord %", 0, 100), ("Loop", 0, 8)]
    for _ in range(rnd.randint(3, 12)):         # turns and switches mid-run, either place in a chain
        unit = rnd.choice(["0", "1", "0.2"] if chain else ["0", "1"])
        t = at(BOUND * rnd.randint(1, 270))
        if rnd.random() < 0.35:
            args += ["--mfx-on-at", f"{unit}:{t}:{rnd.randint(0, 1)}"]
        else:
            name, lo, hi = rnd.choice(params)
            args += ["--mfx-param-at", f"{unit}:{t}:{name}={rnd.randint(lo, hi)}"]
    # the end: every arp bypassed (a latched one plays on otherwise)
    args += ["--mfx-on-at", f"0:{at(BOUND * 285)}:0", "--mfx-on-at", f"1:{at(BOUND * 285)}:0"]
    if chain:
        args += ["--mfx-on-at", f"0.2:{at(BOUND * 285)}:0"]
    lines = [f"#! rate={RATE} block={block} tracks=8 end={end}"]
    chord = " ".join(f"{rnd.randint(40, 70)} {rnd.randint(30, 127)}" for _ in range(rnd.randint(1, 4)))
    lines.append(f"@0 tog 0 0 {chord};slen 0 0 0 -1 {rnd.randint(10, 300)};route 0 1 {rnd.randint(0, 1)};"
                 f"tog 1 4 {rnd.randint(40, 80)} 100;route 1 1 {rnd.randint(0, 1)}")
    t = 0
    for _ in range(rnd.randint(1, 4)):          # Start and Stop, any number of times
        t += rnd.randint(5, 60)
        if t >= 270:
            break
        lines.append(f"@{BOUND * t} play")
        t = min(t + rnd.randint(5, 60), 280)    # stopped before the end: its notes end
        lines.append(f"@{BOUND * t} stop")
    return args, "\n".join(lines) + "\n"


@pytest.mark.parametrize("seed", range(24))
def test_every_note_on_gets_its_note_off(renderer, tmp_path, seed):
    """Seeded mixes of keys, the sequencer's notes on two sounds, Start and
    Stop, bypasses, latch and every kind of turn (TRG included), with a
    chain of two now and then, either of whose effects switches: when
    everything is let go and bypassed, no engine is left with a note-on that
    had no note-off, and nothing was dropped. Every third seed also runs at
    blocks of 7 and must match."""
    args, script = fuzz_args(seed, 64)
    s, wav, ev = mfx_run(renderer, tmp_path, args, f"f{seed}", script=script)
    assert s["notes_hung"] == 0, f"seed {seed}: {s['notes_hung']} notes hang"
    assert s["mfx_dropped"] == 0 and s["seq_dropped"] == 0
    if seed % 3 == 0:
        args7, script7 = fuzz_args(seed, 7)
        s7, wav7, ev7 = mfx_run(renderer, tmp_path, args7, f"g{seed}", script=script7)
        assert (wav7, ev7) == (wav, ev) and s7["notes_hung"] == 0


def test_a_note_off_follows_its_note_on(renderer, tmp_path):
    """A key pressed before the arp is switched on is the sound's, and its
    release goes there: the arp never hears it. A key the arp took and
    still held when it is bypassed ends with the bypass, and its release
    goes nowhere."""
    s, _, ev = mfx_run(renderer, tmp_path, [
        "--engine", "test-sine", "--mfx", "0:arp:off",
        *note(BOUND * 2, 55, 100, BOUND * 60),               # before: the sound's
        "--mfx-on-at", f"0:{at(BOUND * 10)}:1",
        *note(BOUND * 20, 60, 100, BOUND * 80),              # the arp's
        "--mfx-on-at", f"0:{at(BOUND * 50)}:0",              # bypassed while 60 is held
        *note(BOUND * 70, 64, 100, BOUND * 10)])             # after: the sound's
    keys = {k for _, k in ons(ev)}
    assert keys == {60}
    assert s["notes_hung"] == 0
    assert [e for e in ev if e["t"] > BOUND * 50] == []


def test_a_key_and_a_track_on_one_pitch_keep_their_own_note_offs(renderer, tmp_path):
    """The sequencer's note 60 starts with the arp off (so the sound plays
    it); the arp goes on; a key 60 goes to the arp. The track's note-off
    must still reach the sound, and the key's the arp: the chain keeps the
    two sources' notes apart."""
    script = (f"#! rate={RATE} block=64 tracks=8 end={BOUND * 120}\n"
              f"@0 tog 0 0 60 100;slen 0 0 0 -1 90;play\n@{BOUND * 100} stop\n")
    s, _, ev = mfx_run(renderer, tmp_path, [
        "--engine", "test-sine", "--mfx", "0:arp:off",
        "--mfx-on-at", f"0:{at(BOUND * 3)}:1",
        *note(BOUND * 4, 60, 100, BOUND * 80)], script=script)   # held past the track's off
    assert s["notes_hung"] == 0
    # the track's note-off at about frame 20,900 is the sound's: the arp
    # plays the key on until its own release at 37,632, its last step on the
    # sequencer's grid at 33,318 (tick 144)
    assert max(t for t, k in ons(ev) if k == 60) > BOUND * 70


def test_a_chain_of_two(renderer, tmp_path):
    """The second arp arpeggiates the first's notes, so the chain's output
    differs from the first's alone; bypassing the first hands later keys
    straight to the second."""
    keys = [*note(BOUND, 60, 100, BOUND * 150), *note(BOUND, 67, 100, BOUND * 150)]
    one = ["--engine", "test-sine", "--mfx", "0:arp", "--mfx-param", "0:Rate=7", *keys]
    _, a, ev1 = mfx_run(renderer, tmp_path, one, "one")
    two = one + ["--mfx", "0:arp", "--mfx-param", "0:Rate=2", "--mfx-param", "0:Octaves=1"]
    s, b, ev2 = mfx_run(renderer, tmp_path, two, "two")
    assert a != b and ev1 != ev2 and s["notes_hung"] == 0
    assert {k for _, k in ons(ev2)} >= {60, 67, 72, 79}
    # Bypassing the first ends what it held; a key after that goes straight
    # to the second, which plays it over two octaves.
    s3, _, ev3 = mfx_run(renderer, tmp_path, two + ["--mfx-on-at", f"0:{at(BOUND * 40)}:0",
                                                    *note(BOUND * 60, 62, 100, BOUND * 60)], "three")
    assert s3["notes_hung"] == 0
    assert {k for t, k in ons(ev3) if t > BOUND * 40} == {62, 74}


def test_switching_on_a_later_effect_leaves_no_note_hanging(renderer, tmp_path):
    """The first arp sounds a long note into the sound; the second is
    switched on behind it. That note's note-off would now reach the second
    arp, which never heard its note-on: the first ends what it sounds before
    the switch, so the sound is left with nothing."""
    s, _, ev = mfx_run(renderer, tmp_path, [
        "--engine", "test-sine", "--mfx", "0:arp", "--mfx-param", "0:Gate=200",
        "--mfx-param", "0:Rate=10", "--mfx", "0:arp:off",
        *note(BOUND, 60, 100, BOUND * 100), *note(BOUND, 64, 100, BOUND * 100),
        "--mfx-on-at", f"0.2:{at(BOUND * 20)}:1",                 # mid-note (it ends at ~BOUND x 100)
        "--mfx-on-at", f"0.2:{at(BOUND * 150)}:0",
        "--mfx-on-at", f"0:{at(BOUND * 200)}:0"])
    assert s["notes_hung"] == 0       # (its note-offs at the switch go straight to the sound)
    assert ons(ev) and min(t for t, _ in ons(ev)) < BOUND * 20 < max(t for t, _ in ons(ev))


def test_switching_on_an_earlier_effect_lets_go_of_the_keys(renderer, tmp_path):
    """Keys went into the second arp (the first bypassed); the first is
    switched on while they are held, so their releases would reach it, which
    never heard them: the second hears them let go at the switch, and plays
    nothing after its last note ends."""
    s, _, ev = mfx_run(renderer, tmp_path, [
        "--engine", "test-sine", "--mfx", "0:arp:off", "--mfx", "0:arp",
        *note(BOUND, 60, 100, BOUND * 60), *note(BOUND, 67, 100, BOUND * 60),
        "--mfx-on-at", f"0:{at(BOUND * 20)}:1",
        "--mfx-on-at", f"0:{at(BOUND * 150)}:0", "--mfx-on-at", f"0.2:{at(BOUND * 150)}:0"])
    assert s["notes_hung"] == 0
    assert ons(ev) and max(t for t, _ in ons(ev)) < BOUND * 20, "the arp plays keys let go long ago"


def test_a_flood_of_keys_keeps_every_note_off(renderer, tmp_path):
    """128 keys in two blocks, all let go at once: the chain queues 64 live
    note-offs for the next block and owes the other 64 (after the queue);
    every one reaches the arp, which then falls silent."""
    keys = [*(a for k in range(64) for a in note(BOUND, k, 100, BOUND * 20)),
            *(a for k in range(64, 128) for a in note(BOUND + 64, k, 100, BOUND * 20 - 64))]
    s, _, ev = mfx_run(renderer, tmp_path, ["--engine", "test-sine", "--mfx", "0:arp",
                                            "--mfx-param", "0:Rate=1", *keys,
                                            "--seconds", f"{BOUND * 40 / RATE:.6f}"])
    assert s["mfx_deferred_offs"] == 64 and s["notes_hung"] == 0 and s["mfx_direct"] == 0
    assert max(t for t, _ in ons(ev)) < BOUND * 22, "a key's release was lost"


TRG = (f"#! rate={RATE} block=64 tracks=8 end={BOUND * 620}\n"
       "@0 tog 0 0 48 100 55 100 60 100;slen 0 0 0 -1 380;tog 0 4 48 100;tog 0 8 48 100;"
       "tog 0 10 48 100;tog 0 12 48 100;play\n"
       f"@{BOUND * 610} stop\n")


def test_rate_trg_steps_on_the_sequencers_trigs(renderer, tmp_path):
    """RATE TRG: every frame where the sequencer starts notes for the sound
    is one step of the arp, whatever the block size; keys alone hold. In a
    chain, the second arp steps on the same trigs."""
    runs = []
    for block in (1, 7, 64):
        script = TRG.replace("block=64", f"block={block}")
        log = tmp_path / f"e{block}.jsonl"
        s, wav, ev = mfx_run(renderer, tmp_path, ["--engine", "test-sine", "--frames", str(block),
                                                  "--mfx", "0:arp", "--mfx-param", "0:Rate=0",
                                                  "--log-events", str(log)], f"trg{block}", script=script)
        assert s["notes_hung"] == 0
        runs.append((wav, ev))
    seq = [json.loads(line) for line in log.read_text().splitlines()]
    trigs = sorted({e["frame"] for e in seq if e["kind"] == "on"})
    assert len(trigs) > 10 and [t for t, _ in ons(runs[0][1])] == trigs
    assert all(r == runs[0] for r in runs[1:])
    # at one frame, note-offs before note-ons
    for t in trigs:
        kinds = [e["k"] for e in runs[0][1] if e["t"] == t]
        assert kinds == sorted(kinds, key=lambda k: k != "off"), (t, kinds)
    # keys alone: nothing
    s, _, ev = mfx_run(renderer, tmp_path, ["--engine", "test-sine", "--mfx", "0:arp",
                                            "--mfx-param", "0:Rate=0", *note(BOUND, 60, 100, BOUND * 50),
                                            "--seconds", "1"], "keys")
    assert ons(ev) == [] and s["notes_hung"] == 0
    # a chain: the first at 1/32, the second at TRG
    s, _, ev = mfx_run(renderer, tmp_path, ["--engine", "test-sine", "--mfx", "0:arp",
                                            "--mfx-param", "0:Rate=2", "--mfx", "0:arp",
                                            "--mfx-param", "0:Rate=0"], "chain", script=TRG)
    assert s["notes_hung"] == 0 and {t for t, _ in ons(ev)} <= set(trigs) and len(ons(ev)) > 10


# ---- Flags -----------------------------------------------------------------------------------

@pytest.mark.parametrize("bad, code", [
    (["--mfx", "9:arp"], 2),
    (["--mfx", "0:nope"], 1),
    (["--mfx", "0:arp:on"], 2),
    (["--mfx", "0:arp", "--mfx-param", "0:Nope=1"], 1),
    (["--mfx", "0:arp", "--mfx-param-at", "0.2:0.1:Rate=1"], 2),
    (["--mfx", "0:arp", "--mfx-on-at", "0:0.1"], 2),
    (["--log-mfx", "x.jsonl"], 2),
    (["--mfx", "0:arp"] * 5, 2),
])
def test_bad_mfx_flags_are_refused(renderer, tmp_path, bad, code):
    res = subprocess.run([str(renderer), "--engine", "test-sine", "--seconds", "0.1",
                          "--out", str(tmp_path / "x.wav"), *bad],
                         capture_output=True, text=True, cwd=tmp_path)
    assert res.returncode == code, res.stderr


# ---- With per-voice modulation (MG9) -----------------------------------------------------------

def test_a_flush_ends_the_modulation_voices_of_its_own_sound(renderer, tmp_path):
    """A latched arp on Sound 2 under a per-voice cable, switched off while
    its notes sound: the flush's note-offs end the voices on Sound 2, not
    on Sound 1 (where they once went, leaving two voices running for good)."""
    mod = tmp_path / "v.mod"
    mod.write_text("rack default\nset 3 attack=0.01 decay=0.2 sustain=0.5 release=0.05\n"
                   "slot 1 env3 > snd2:Timbre amt=60 voice\n")
    log = tmp_path / "v.jsonl"
    res = subprocess.run([str(renderer), "--engine", "macro", "--sound", "1:shapes", "--slots",
                          *note(BOUND, 60, 100, 4410, sound=1), *note(BOUND, 64, 100, 4410, sound=1),
                          "--mfx", "1:arp", "--mfx-param", "1:Latch=1", "--mfx-param", "1:Gate=200",
                          "--mfx-on-at", "1:0.6:0", "--mod", str(mod), "--log-mod", str(log),
                          "--seconds", "2.0", "--out", str(tmp_path / "x.wav")],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    s = json.loads(res.stdout)
    assert s["mfx_notes_out"] > 4 and s["notes_hung"] == 0
    assert s["mod_voice_starts"] == 2 and s["mod_voice_ends"] == 2
    last = json.loads(log.read_text().splitlines()[-1])
    assert last["vo"] == []


# ---- No heap, no stdio, no libm --------------------------------------------------------------

HEAP = {"malloc", "calloc", "realloc", "free", "posix_memalign", "aligned_alloc", "strdup",
        "printf", "fprintf", "snprintf", "sprintf", "fopen", "fwrite", "puts", "putchar"}
LIBM = {"sinf", "cosf", "tanf", "floorf", "ceilf", "roundf", "lrintf", "lroundf", "powf", "expf",
        "exp2f", "logf", "log2f", "log10f", "sqrtf", "fmodf", "floor", "ceil", "round", "lrint",
        "pow", "exp", "log", "log2", "sqrt", "fmod", "sin", "cos", "tanhf", "atanf"}


def test_the_host_stage_and_the_wrapper_never_allocate_print_or_call_libm(renderer):
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    objs = [ENGINES / "build" / "c" / "seq" / "mfx_host.o",
            ENGINES / "build" / "c" / "seq" / "seq_host.o",
            ENGINES / "build" / "midi_fx" / "arp_engine.o",
            ENGINES / "build" / "midi_fx" / "registry.o",
            ENGINES / "build" / "midi_fx" / "fm1_arp.o"]
    for o in objs:
        assert o.exists(), o
        out = subprocess.check_output([nm, "-u", str(o)], text=True)
        names = {line.split()[-1].lstrip("_") for line in out.splitlines() if line.strip()}
        assert not names & (HEAP | LIBM), f"{o.name} imports {sorted(names & (HEAP | LIBM))}"
