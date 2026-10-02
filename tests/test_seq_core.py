"""The sequencer core's own contracts (engines/include/fm1_seq.h, engines/seq.md):
the FM-1 deviations D1-D7 of docs/13 §3.3 against compat mode, block-size
identity, memory figures, no heap, the verb parser, `movy1` fixtures and
routing. Movy's own tests, transcribed, are in test_seq_movy.py.
"""
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.seq_helpers import (ENGINES, SEQ_CHECK, TPB, TPS, Script, ccs, clip, kinds, notes, offs,
                               ons, run_script, seq_tools, track)  # noqa: F401

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "movy"
RATE = 44118                      # the FM-1's rate
THR = RATE * 6000                 # clock threshold, frames x bpm_x100 x PPQN per tick
HALF_BUDGET = 72 * 1024 // 2      # docs/13 §5: about half of 72 KiB at 4-8 tracks


def fm1(tracks=8, block=128):
    return Script(tracks=tracks, rate=RATE, block=block)


# ---- D1: every event at its own frame ------------------------------------------------

def d1_frame(play_frame, tick, bpm_x100=12000):
    """docs/13 D1: master tick m (0-based) after a Play at play_frame falls in
    frame play_frame + ceil((m+1)*thr/inc) - 1."""
    inc = bpm_x100 * 96
    return play_frame + -(-(tick + 1) * THR // inc) - 1


@pytest.mark.parametrize("bpm", [12000, 13333, 30000, 2000])
def test_d1_events_fall_on_their_own_frame(seq_tools, tmp_path, bpm):
    s = fm1().bpm(bpm).cmd("tog 0 0 60 100;tog 0 5 62 100;tog 0 9 64 100").cmd("cscl 0 3 2")
    s.cmd("alabel 0 0 synth:x;aset 0 0 3 99 1").cmd("metro 1").blocks(3).play()
    s.blocks(400 * 12000 // min(bpm, 12000))
    r = s.run(seq_tools, tmp_path, compat=False)
    timed = [e for e in r.events if e["kind"] in ("on", "off", "cc", "clock", "click")]
    assert len(timed) > 50
    for e in timed:
        assert e["frame"] == d1_frame(3 * 128, e["tick"], bpm), e
    r = s.run(seq_tools, tmp_path, compat=True, name="c")
    assert all(e["frame"] == e["block_start"] for e in r.events), "compat: block start, as Movy"


def identity_script(block):
    """Commands on multiples of 896 frames, a common multiple of 1, 7, 64 and
    128, so every block size applies them at the same frame."""
    s = fm1(block=block)
    s.cmd("tog 0 0 60 100 64 90;tog 0 3 62 100;tog 0 6 67 80").cmd("cscl 0 3 2").cmd("swing 66")
    s.cmd("alabel 0 0 synth:x;abase 0 0 40;aset 0 0 2 100 1;aset 0 0 7 20 1")
    s.cmd("tog 1 0 36 100;tog 1 4 38 100;eprob 1 4 4 -1 50;econd 1 0 0 -1 1 2")
    s.cmd("ltog 2 2 40 100;cq 2 50").cmd("metro 1")
    s.cmd("play")
    return s


@pytest.mark.parametrize("compat", [False, True])
def test_block_size_identity(seq_tools, tmp_path, compat):
    """docs/13 §7: the same events at host blocks of 1, 7, 64 and 128 frames;
    in the FM-1 mode the frames too (D1), in compat the ticks."""
    end = 896 * 400
    runs = {}
    for block in (1, 7, 64, 128):
        text = identity_script(block).text(end)
        text += "@" + str(896 * 150) + " launch 1 3;tog 1 2 44 100\n"
        text += "@" + str(896 * 210) + " stop\n@" + str(896 * 230) + " play\n"
        events, _ = run_script(seq_tools, tmp_path, text, compat=compat, name=f"b{block}")
        key = ("frame", "tick", "kind", "track", "a", "b") if not compat else \
              ("tick", "kind", "track", "a", "b")
        runs[block] = [tuple(e[k] for k in key) for e in events]
    assert len(runs[128]) > 300
    for block in (1, 7, 64):
        assert runs[block] == runs[128], f"block {block}"


def test_no_drift_over_ten_thousand_steps(seq_tools, tmp_path):
    """docs/13 §7: no drift over 10,000 steps at a tempo whose tick is not a
    whole number of frames."""
    s = fm1(tracks=1).bpm(13333).cmd("loop 0 0 16;clen 0 1;tog 0 0 60 100").play()
    frames = -(-10000 * TPS * THR // (13333 * 96)) + 128
    s.blocks(frames // 128 + 1)
    r = s.run(seq_tools, tmp_path, compat=False)
    got = ons(r.events)
    assert len(got) >= 10000
    for k, e in enumerate(got[:10000]):
        assert e["tick"] == k * TPS and e["frame"] == d1_frame(0, k * TPS, 13333)


# ---- D2: a step's locks before its notes, the first step too ------------------------------

def test_d2_first_step_locks_come_before_its_notes(seq_tools, tmp_path):
    """After Play (tick 0) and after a bar launch (tick 384), the first step's
    lock and its note-on share a frame; D2 puts the lock first, Movy after."""
    def run(compat):
        s = fm1().cmd("alabel 0 0 synth:x;abaseq 0 0 40").cmd("tog 0 0 60 100;aset 0 0 0 90 1")
        s.cmd("clipsel 0 1;tog 0 0 62 100;aset 0 0 0 70 1;clipsel 0 0").play().run_ticks(100)
        s.cmd("launch 0 1").run_ticks(TPB)
        r = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}")
        return [e for e in r.events if e["track"] == 0 and e["kind"] in ("on", "cc")
                and e["tick"] in (0, TPB)]
    key = lambda e: (e["tick"], e["kind"], e["a"], e["b"])  # noqa: E731
    movy, ours = run(True), run(False)
    assert [key(e) for e in movy] == [(0, "on", 60, 100), (0, "cc", 102, 90),
                                      (TPB, "on", 62, 100), (TPB, "cc", 102, 70)]
    assert [key(e) for e in ours] == [(0, "cc", 102, 90), (0, "on", 60, 100),
                                      (TPB, "cc", 102, 70), (TPB, "on", 62, 100)]
    assert ours[0]["frame"] == ours[1]["frame"] and ours[2]["frame"] == ours[3]["frame"]


# ---- D3: after a count-in, step 0 on the bar -----------------------------------------

def test_d3_count_in_starts_on_the_bar(seq_tools, tmp_path):
    for compat, tick in ((True, TPB - 1), (False, TPB)):
        s = fm1().cmd("tog 0 0 60 100").cmd("rec 0", starts=True).run_ticks(2 * TPB + 2)
        ev = ons(s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}").events)
        assert ev[0]["tick"] == tick
        assert ev[1]["tick"] == tick + TPB


# ---- D4: an overdub in the last half-step does not grow the clip ---------------------------

def test_d4_overdub_at_the_loop_end_keeps_the_length(seq_tools, tmp_path):
    for compat, length, step in ((True, 32, 16), (False, 16, 15)):
        s = fm1().cmd("tog 0 0 60 100").play().cmd("rec 0").run_ticks(TPB - 9)
        s.cmd("non 0 62 100").run_ticks(2).cmd("nof 0 62")
        e = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}").end
        n = [n for n in notes(e, 0) if n["pitch"] == 62][0]
        assert (clip(e, 0)["len"], n["step"]) == (length, step)


# ---- D5: caps from the loop end, so a window past step 0 neither crashes nor collapses -------

def test_d5_nudge_and_length_use_the_loop_end(seq_tools, tmp_path):
    def run(compat):
        s = fm1().cmd("tog 0 20 60 100").cmd("loop 0 16 16").cmd("enudge 0 20 20 -1 30")
        s.cmd("slen 0 20 20 -1 96")
        return s.run(seq_tools, tmp_path, compat=compat, end=0, name=f"c{compat}").end
    movy, ours = run(True), run(False)
    m, o = notes(movy, 0)[0], notes(ours, 0)[0]
    assert movy["stats"]["compat_divergence"] == 1, "Movy's clamp(lo, hi) panics here"
    assert (m["tick"], m["gate"]) == (20 * TPS, 1), "Movy: untouched, length cap of 1 tick"
    assert (o["tick"], o["gate"]) == (21 * TPS, 96)
    assert ours["stats"]["compat_divergence"] == 0


# ---- D6: Stop sends lanes back to their base ---------------------------------------

def test_d6_stop_reverts_locked_lanes(seq_tools, tmp_path):
    def run(compat):
        s = fm1().cmd("alabel 0 0 synth:x;alabel 0 1 synth:y;abaseq 0 0 40;abaseq 0 1 50")
        s.cmd("tog 0 0 60 100;slen 0 0 0 -1 300;aset 0 0 2 100 1").play().run_ticks(5 * TPS)
        s.mark("s").cmd("stop")
        s.blocks(2)
        return s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}")
    movy, ours = run(True), run(False)
    assert ccs(movy.between("s", 10 ** 12)) == []
    after = [e for e in ours.between("s", 10 ** 12) if e["kind"] in ("off", "cc")]
    assert [(e["kind"], e["a"], e["b"]) for e in after] == [("off", 60, None), ("cc", 102, 40)]
    assert ours.end["tracks"][0]["lanes"][0]["cur"] == -1


# ---- D7: fixed pools, refused edits, the oldest gate freed --------------------------------

def test_d7_full_pools_refuse_and_count(seq_tools, tmp_path):
    s = fm1().cmd("tog 0 0 60 100;tog 0 1 60 100;tog 0 2 60 100;tog 0 3 60 100")
    s.cmd("aset 0 0 0 1;aset 0 0 1 2;aset 0 0 2 3").cmd("eprob 0 0 1 -1 50")
    e = s.run(seq_tools, tmp_path, compat=False, end=0,
              extra=["--notes", "3", "--locks", "2", "--trigs", "1"]).end
    assert len(notes(e, 0)) == 3 and clip(e, 0)["locks"] == 2 and clip(e, 0)["trigs"] == 1
    assert e["stats"]["refused"] == 3
    assert (e["stats"]["notes_used"], e["stats"]["locks_used"], e["stats"]["trigs_used"]) == (3, 2, 1)


def test_d7_a_full_gate_pool_frees_the_oldest_note_first(seq_tools, tmp_path):
    s = fm1().cmd("tog 0 0 60 100;tog 0 1 62 100;tog 0 2 64 100").cmd("slen 0 0 2 -1 200")
    r = s.play().run_ticks(3 * TPS).run(seq_tools, tmp_path, compat=False, extra=["--gates", "2"])
    seq = [(e["kind"], e["a"]) for e in r.events if e["kind"] in ("on", "off")]
    assert seq == [("on", 60), ("on", 62), ("off", 60), ("on", 64)]
    assert r.end["stats"]["gates_evicted"] == 1


def test_per_clip_caps_drop_like_movy(seq_tools, tmp_path):
    """clip.rs note_cap_enforced (1142): 512 notes per clip, the rest dropped."""
    s = fm1()
    for k in range(520):
        s.cmd(f"ltog 0 {k % 256} {k // 256 + 40} 100")
    e = s.run(seq_tools, tmp_path, compat=True, end=0).end
    assert len(notes(e, 0)) == 512


# ---- Memory (docs/13 §5, §10 answer 3) -------------------------------------------------

def sizes(tool):
    return json.loads(subprocess.check_output([str(tool), "--sizes"]))


def test_memory_figures_for_four_and_eight_tracks(seq_tools):
    """The owner's budget: about half of docs/13's 72 KiB at the reduced
    track count. These are the figures engines/seq.md reports; a change to the
    layout must update both."""
    z = sizes(seq_tools)
    assert z["tracks"]["4"] == 14984
    assert z["tracks"]["8"] == 28808
    assert z["tracks"]["8"] <= HALF_BUDGET
    assert z["capture256"]["8"] - z["tracks"]["8"] == 256 * 20, "Capture: 20 bytes per event"
    assert z["limits8"] == {"notes": 1536, "locks": 1536, "trigs": 256, "gates": 64, "song": 64,
                            "rec_notes": 16, "pad_mutes": 16}
    assert z["event_bytes"] == 12


def test_size_is_linear_in_tracks(seq_tools):
    z = sizes(seq_tools)["tracks"]
    per = z["2"] - z["1"]
    assert all(z[str(t)] - z[str(t - 1)] == per for t in range(2, 17))
    # 192 notes x 12 + 192 locks x 3 + 32 trig rows x 5 + 8 clips x 20, the
    # track's 240 bytes and its 16 pad mutes
    assert per == 3456


# ---- No heap ---------------------------------------------------------------------------

HEAP = {"malloc", "calloc", "realloc", "free", "posix_memalign", "aligned_alloc", "strdup",
        "_Znwm", "_Znam", "_Znwj", "_Znaj", "_ZdlPv", "_ZdaPv", "_ZdlPvm", "_ZdaPvm",
        "printf", "fprintf", "snprintf", "sprintf", "fopen", "fwrite"}


def test_the_core_never_allocates(seq_tools):
    """docs/13 §7: no malloc in the link map. The core's objects import no
    allocator (nor stdio) at all."""
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    objs = sorted((ENGINES / "build" / "c" / "seq").glob("*.o"))
    assert len(objs) == 5
    for o in objs:
        out = subprocess.check_output([nm, "-u", str(o)], text=True)
        names = {line.split()[-1].lstrip("_") for line in out.splitlines() if line.strip()}
        names |= {n.lstrip("_") for n in names}
        bad = {n for n in names if n in HEAP or n.lstrip("_") in HEAP}
        assert not bad, f"{o.name} imports {sorted(bad)}"


# ---- Instance memory and determinism -----------------------------------------------------------

def test_output_does_not_depend_on_prior_memory(seq_tools, tmp_path):
    text = identity_script(128).text(896 * 200)
    logs = []
    for fill in ("0", "0xA5", "0xFF"):
        p = tmp_path / f"s{fill}.txt"
        p.write_text(text)
        log = tmp_path / f"l{fill}.jsonl"
        subprocess.run([str(seq_tools), "--cmd", str(p), "--log", str(log), "--fill", fill,
                        "--capture", "64"], check=True)
        logs.append(log.read_bytes())
    assert logs[0] == logs[1] == logs[2]


def random_script(rng, n=400, tracks=4):
    """Random edits and transport on a running sequence: what the oracle
    compares at scale (docs/13 §7); here, the checking build's invariants."""
    verbs = []
    for _ in range(n):
        t = rng.randrange(tracks)
        s0 = rng.randrange(64)
        k = rng.random()
        if k < 0.25:
            verbs.append(f"tog {t} {s0} {rng.randrange(36, 84)} {rng.randrange(1, 128)}")
        elif k < 0.32:
            verbs.append(f"ltog {t} {s0} {rng.randrange(36, 50)} 100")
        elif k < 0.38:
            verbs.append(f"enudge {t} {s0} {s0 + rng.randrange(4)} -1 {rng.randrange(-30, 30)}")
        elif k < 0.42:
            verbs.append(f"cq {t} {rng.randrange(101)}")
        elif k < 0.45:
            verbs.append(f"swing {rng.randrange(50, 81)}")
        elif k < 0.48:
            verbs.append(f"cscl {t} {rng.randrange(1, 5)} {rng.randrange(1, 5)}")
        elif k < 0.52:
            verbs.append(f"aset {t} {rng.randrange(8)} {s0} {rng.randrange(128)} 1")
        elif k < 0.55:
            verbs.append(f"alabel {t} {rng.randrange(8)} synth:p")
        elif k < 0.58:
            verbs.append(f"eprob {t} {s0} {s0} -1 {rng.randrange(101)}")
        elif k < 0.61:
            verbs.append(f"econd {t} {s0} {s0} -1 {rng.randrange(1, 5)} {rng.randrange(1, 5)}")
        elif k < 0.64:
            verbs.append(f"launch {t} {rng.randrange(8)}")
        elif k < 0.66:
            verbs.append(f"clipsel {t} {rng.randrange(8)}")
        elif k < 0.68:
            verbs.append(f"loop {t} {rng.randrange(0, 64)} {rng.randrange(1, 64)}")
        elif k < 0.70:
            verbs.append(f"clen {t} {rng.randrange(1, 70)}")
        elif k < 0.72:
            verbs.append(f"dbl {t}")
        elif k < 0.74:
            verbs.append(f"cpy {t} {s0} {s0 + rng.randrange(8)};pst {rng.randrange(tracks)} {rng.randrange(64)}")
        elif k < 0.76:
            verbs.append(f"clipcopy {t} {rng.randrange(8)};clippaste {rng.randrange(tracks)} {rng.randrange(8)}")
        elif k < 0.78:
            verbs.append(f"del {t} {s0} {s0 + rng.randrange(16)} -1")
        elif k < 0.80:
            verbs.append(f"rec {t}")
        elif k < 0.84:
            p = rng.randrange(40, 80)
            verbs.append(f"non {t} {p} 100" if rng.random() < 0.5 else f"nof {t} {p}")
        elif k < 0.86:
            verbs.append(f"song {rng.randrange(8)}")
        elif k < 0.88:
            verbs.append(f"songadd {rng.randrange(8)}")
        elif k < 0.90:
            verbs.append(f"mute {t} {rng.randrange(2)}")
        elif k < 0.92:
            verbs.append(rng.choice(["play", "stop"]))
        elif k < 0.94:
            verbs.append(f"slen {t} {s0} {s0} -1 {rng.randrange(1, 400)}")
        elif k < 0.96:
            verbs.append(f"clipdel {t}")
        elif k < 0.98:
            verbs.append(f"bpm {rng.randrange(2000, 30001)}")
        else:
            verbs.append(f"cap {t}")
    frame = 0
    lines = [f"#! rate={RATE} block=64 tracks={tracks}", "@0 play"]
    for v in verbs:
        frame += rng.randrange(0, 4000)
        lines.append(f"@{frame} {v}")
    return "\n".join(lines) + "\n", frame + 20000


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("compat", [False, True])
def test_random_scripts_keep_the_index_exact(seq_tools, tmp_path, seed, compat):
    """fm1-seq-check traps if a cached fire tick is stale or the fire-tick
    index unsorted at any scan; it must also log exactly what fm1-seq logs."""
    rng = random.Random(seed * 7919 + compat)
    text, end = random_script(rng)
    p = tmp_path / "r.txt"
    p.write_text(text)
    logs = []
    for tool in (seq_tools, SEQ_CHECK):
        log = tmp_path / f"{tool.name}.jsonl"
        cmd = [str(tool), "--cmd", str(p), "--log", str(log), "--end", str(end), "--capture", "64"]
        if compat:
            cmd.append("--compat")
        subprocess.run(cmd, check=True)
        logs.append(log.read_bytes())
    assert logs[0] == logs[1]
    assert logs[0].count(b'"on"') >= 5


# ---- The verb parser ----------------------------------------------------------------------

def test_arguments_parse_as_rust_integers(seq_tools, tmp_path):
    """command.rs parses each token with str::parse::<i64>: a '+' is fine,
    anything else that is not digits is an absent argument."""
    text = ("@0 tog +0 +4 +60 +100\n@0 tog 0 x 60 100\n@0 tog 0 5 60 1.0\n"
            "@0 tog 0 6 0x3C 100\n@0 bpm 99999999999999999999\n@0 tog 0 300 61 100\n"
            "@0 clen 1 70000\n@0 loop 1 65552 16\n@0 tog 0 7\t62 100\n")
    _, end = run_script(seq_tools, tmp_path, "#! tracks=4\n" + text, compat=True)
    got = sorted((n["step"], n["pitch"]) for n in notes(end, 0))
    assert got == [(4, 60), (7, 62), (255, 61)]
    assert end["bpm_x100"] == 12000, "an i64 overflow is an absent argument"
    c = clip(end, 1)
    assert (c["loop_start"], c["len"]) == (16, 16), "`loop` truncates `as u16`: 65552 -> 16"


def test_chords_are_capped_at_twelve_pitches(seq_tools, tmp_path):
    chord = " ".join(f"{48 + k} 100" for k in range(14))
    _, end = run_script(seq_tools, tmp_path, f"#! tracks=1\n@0 tog 0 0 {chord}\n", compat=True)
    assert len(notes(end, 0)) == 12


# ---- movy1: Movy's own set fixtures -------------------------------------------------------

FIXTURE_FILES = ["movy-chains.movy1", "schwung-tracks.movy1", "device-set.movy1"]


@pytest.mark.parametrize("name", FIXTURE_FILES)
def test_movy_fixtures_round_trip(seq_tools, tmp_path, name):
    """docs/13 §7: Movy's fixtures (tests/fixtures/movy/, MIT) export
    byte-identically apart from their envelope: `gen`/`end` lines and comments
    Movy's own loader ignores, and the format's later fields that a legacy
    hand-written file lacks (anchors, quantise, all sixteen tracks)."""
    src = (FIXTURES / name).read_text()
    out = tmp_path / "out.movy1"
    subprocess.run([str(seq_tools), "--compat", "--tracks", "16", "--seq", str(FIXTURES / name),
                    "--export", str(out)], check=True)
    got = out.read_text()
    envelope = [l for l in src.splitlines() if re.match(r"(gen|end) |#", l)]
    body = [l for l in src.splitlines() if l not in envelope]
    if name == "device-set.movy1":
        # Legacy: notes without anchors, five-field cp lines, four tracks.
        assert got.splitlines()[:5] == body[:5]
        assert "cl 0 0 16 0 0:24:60:100:0;96:24:64:100:4;192:24:67:100:8;288:24:72:100:12" in got
        assert "cp 1 0 1 1 0 0" in got and "tk 15 0 0" in got
    else:
        assert got.splitlines() == body
    again = tmp_path / "again.movy1"
    subprocess.run([str(seq_tools), "--compat", "--tracks", "16", "--seq", str(out), "--export",
                    str(again)], check=True)
    assert again.read_text() == got


def test_a_fixture_plays(seq_tools, tmp_path):
    """The movy-chains set (a real device set: off-grid notes, cp ... 100 and
    A:B rows) plays in both modes; compat and FM-1 differ only by D1-D7."""
    text = f"#! rate={RATE} block=128 tracks=16\n@0 play\n"
    p = tmp_path / "p.txt"
    p.write_text(text)
    out = {}
    for compat in (True, False):
        log = tmp_path / f"{compat}.jsonl"
        cmd = [str(seq_tools), "--cmd", str(p), "--seq", str(FIXTURES / "movy-chains.movy1"),
               "--log", str(log), "--end", str(RATE * 8)]
        subprocess.run(cmd + (["--compat"] if compat else []), check=True)
        out[compat] = [json.loads(l) for l in log.read_text().splitlines()]
    key = lambda e: (e["tick"], e["kind"], e["track"], e["a"], e["b"])  # noqa: E731
    assert [key(e) for e in out[True]] == [key(e) for e in out[False]]
    assert len(ons(out[True])) > 50


# ---- Routing (docs/13 §10, answer 2) ---------------------------------------------------------

def test_routing_is_stored_with_the_set(seq_tools, tmp_path):
    s = fm1(tracks=4).cmd("route 1 1 0;route 2 0 10;route 3 1 9;route 3 0 17")
    r = s.run(seq_tools, tmp_path, compat=False, end=0, extra=["--export", str(tmp_path / "o.movy1")])
    routes = [track(r.end, t)["route"] for t in range(4)]
    assert routes == [[0, 1], [1, 0], [0, 10], [0, 4]], "slot 9 and channel 17 are refused"
    out = (tmp_path / "o.movy1").read_text()
    assert "rt 1 1 0\n" in out and "rt 2 0 10\n" in out and "rt 0" not in out
    back = tmp_path / "b.movy1"
    subprocess.run([str(seq_tools), "--tracks", "4", "--seq", str(tmp_path / "o.movy1"),
                    "--export", str(back)], check=True)
    assert back.read_text() == out
    r = s.run(seq_tools, tmp_path, compat=True, end=0, name="c",
              extra=["--export", str(tmp_path / "c.movy1")])
    assert "rt " not in (tmp_path / "c.movy1").read_text(), "compat writes Movy's format only"


def test_tracks_past_the_limit_are_ignored(seq_tools, tmp_path):
    """A 4-track build drops what Movy's 16 tracks would hold beyond track 3,
    and plays the rest exactly as before."""
    text = "@0 tog 0 0 60 100;tog 5 0 61 100;watch 9;rec 7;launch 6 0\n@0 play\n"
    ev, end = run_script(seq_tools, tmp_path, f"#! tracks=4\n{text}", extra=["--end", "20000"])
    assert [(e["track"], e["a"]) for e in ons(ev)] == [(0, 60)]
    assert len(end["tracks"]) == 4 and not end["recording"]
