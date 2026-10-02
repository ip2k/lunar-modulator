"""The sequencer core's own contracts (engines/include/fm1_seq.h, engines/seq.md):
the FM-1 deviations D1-D13 of docs/13 §3.3 against compat mode, block-size
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
    assert movy["stats"]["movy_faults"] == 1, "Movy's clamp(lo, hi) panics here"
    assert (m["tick"], m["gate"]) == (20 * TPS, 1), "Movy: untouched, length cap of 1 tick"
    assert (o["tick"], o["gate"]) == (21 * TPS, 96)
    assert ours["stats"]["movy_faults"] == 0


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
    s.cmd("aset 0 0 0 1;aset 0 0 1 2;aset 0 0 2 3").cmd("eprob 0 0 1 -1 50").cmd("eprob 0 3 3 -1 50")
    e = s.run(seq_tools, tmp_path, compat=False, end=0,
              extra=["--notes", "3", "--locks", "2", "--trigs", "1"]).end
    assert len(notes(e, 0)) == 3 and clip(e, 0)["locks"] == 2 and clip(e, 0)["trigs"] == 1
    # eprob over steps 0-1 needs two rows and the pool holds one: refused
    # whole, so the row is step 3's, written after it.
    assert e["stats"]["refused"] == 3
    assert (e["stats"]["notes_used"], e["stats"]["locks_used"], e["stats"]["trigs_used"]) == (3, 2, 1)


@pytest.mark.parametrize("edit", [
    "tog 0 8 60 100 64 100 67 100",     # a chord
    "addp 0 4 7 72 100",                # a pitch over a range of steps
    "dbl 0",                            # Double Loop
    "cpy 0 0 3;pst 0 8",                # step copy and paste
    "asetr 0 0 4 7 99 1",               # locks over a range
])
def test_d7_a_multi_item_edit_is_all_or_nothing(seq_tools, tmp_path, edit):
    """An edit that adds several items either fits whole or changes nothing
    (D7), as a whole-clip copy does; Movy, with no pools, writes what fits."""
    base = "tog 0 0 60 100;tog 0 1 62 100;tog 0 2 64 100;alabel 0 0 synth:x;aset 0 0 0 5 1;aset 0 0 1 6 1"
    def run(pool):
        s = fm1(tracks=1).cmd(base).cmd(edit)
        e = s.run(seq_tools, tmp_path, compat=False, end=0, name=f"p{pool}",
                  extra=["--notes", str(pool), "--locks", str(pool)]).end
        return notes(e, 0), clip(e, 0)["locks"], e["stats"]["refused"]
    tight = run(5)        # room for two more notes and three more locks
    roomy = run(64)
    assert roomy[2] == 0
    added_notes = len(roomy[0]) - 3
    added_locks = roomy[1] - 2
    assert added_notes > 2 or added_locks > 3 or edit.startswith("cpy"), "the edit must overflow"
    # (cpy would put 3 more notes in the clipboard: refused, so pst has
    # nothing to paste.)
    assert (len(tight[0]), tight[1], tight[2]) == (3, 2, 1), "nothing written, one refusal"


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


# ---- D5 in compat: Movy's panic stops the edit and its batch ------------------------------

def test_d5_compat_stops_the_edit_at_the_panic(seq_tools, tmp_path):
    """Movy's nudge panics on the first matched note whose clamp has lo > hi;
    movy-dsp catches it, so the notes before it keep the nudge and the rest of
    the edit and of its batch are lost (fixture 22-nudge-panic-order)."""
    text = ("#! rate=44118 block=128 tracks=1\n@0 tog 0 0 60 100\n@0 tog 0 20 62 100\n"
            "@0 tog 0 1 64 100\n@0 clen 0 16\n@0 enudge 0 0 31 -1 5;tog 0 3 67 100\n"
            "@0 play\n@44118 stop\n")
    ev, end = run_script(seq_tools, tmp_path, text, compat=True)
    assert [(n["pitch"], n["tick"]) for n in notes(end, 0)] == [(60, 5), (62, 480), (64, 24)]
    assert [(e["tick"], e["a"]) for e in ons(ev)] == [(5, 60), (24, 64), (96, 62)]
    assert end["stats"]["movy_faults"] == 1
    ev, end = run_script(seq_tools, tmp_path, text, compat=False, name="d")
    # D5 skips only the note past the window, and D11 silences it.
    assert sorted((n["pitch"], n["tick"]) for n in notes(end, 0)) == [
        (60, 5), (62, 480), (64, 29), (67, 72)]
    assert [(e["tick"], e["a"]) for e in ons(ev)] == [(5, 60), (29, 64), (72, 67)]


# ---- D6: no lane left at a lock value -----------------------------------------------

@pytest.mark.parametrize("clear", ["aclr 0 0", "aclrs 0 0 4", "aclrstep 0 4", "clipdel 0"])
def test_d6_a_released_lane_returns_to_its_base(seq_tools, tmp_path, clear):
    """A lane whose last lock is cleared while it holds that lock's value is
    freed; the FM-1 sends its base first, Movy leaves the parameter there."""
    text = ("#! tracks=1\n@0 tog 0 0 60 100\n@0 tog 0 8 60 100\n@0 alabel 0 0 synth:cutoff\n"
            f"@0 abaseq 0 0 40\n@0 aset 0 0 4 100 1\n@0 play\n@30080 {clear}\n@60000 stop\n")
    clear_block = 30080 // 128
    for compat in (True, False):
        ev, end = run_script(seq_tools, tmp_path, text, compat=compat, name=f"c{compat}")
        before = [e["b"] for e in ev if e["kind"] == "cc" and e["block"] < clear_block]
        after = [(e["block"], e["b"]) for e in ev if e["kind"] == "cc" and e["block"] >= clear_block]
        assert before[-1] == 100, "the lane holds the lock's value when it is cleared"
        assert after == ([] if compat else [(clear_block, 40)])
        lane = end["tracks"][0]["lanes"][0]
        assert lane["assigned"] == 0 and lane["cur"] == -1


def test_d6_reverts_a_lane_last_at_zero(seq_tools, tmp_path):
    """A lock of 0 is a value like any other: Stop sends the base back."""
    text = ("#! tracks=1\n@0 tog 0 0 60 100\n@0 alabel 0 0 synth:x\n@0 abaseq 0 0 40\n"
            "@0 aset 0 0 2 0 1\n@0 play\n@20096 stop\n")
    ev, _ = run_script(seq_tools, tmp_path, text)
    stop_block = 20096 // 128
    assert ccs([e for e in ev if e["block"] < stop_block])[-1] == (0, 0)
    assert ccs([e for e in ev if e["block"] >= stop_block]) == [(0, 40)]


@pytest.mark.parametrize("how", ["stoptrk 0", "launch 0 3"])
def test_d6_a_track_stopping_at_the_bar_reverts_its_lanes(seq_tools, tmp_path, how):
    """A track stopped at the bar (stoptrk, or a launch of an empty slot)
    sends its locked lanes back to base after its note-offs, as Stop does."""
    s = fm1(tracks=2).cmd("alabel 0 0 synth:x;abaseq 0 0 40;tog 0 0 60 100;aset 0 0 12 99 1")
    s.cmd("tog 1 0 36 100").play().run_ticks(TPB - 20).cmd(how).run_ticks(60)
    for compat in (True, False):
        r = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}")
        at_bar = [(e["kind"], e["track"], e["a"], e["b"]) for e in r.events
                  if e["tick"] == TPB and e["track"] == 0]
        assert at_bar[:1] == [("off", 0, 60, None)] or not at_bar or at_bar[0][0] == "cc"
        locks = [x for x in at_bar if x[0] == "cc"]
        assert locks == ([] if compat else [("cc", 0, 102, 40)])
        assert track(r.end, 0)["playing"] is None


# ---- D8: clip speed within 1/8X-4X ------------------------------------------------------

def test_d8_clip_scale_stays_in_movys_ui_range(seq_tools, tmp_path):
    text = ("#! tracks=4\n@0 tog 0 0 60 100;cscl 0 255 1\n@0 tog 1 0 60 100;cscl 1 1 255\n"
            "@0 tog 2 0 60 100;cscl 2 9 2\n@0 tog 3 0 60 100;cscl 3 3 2\n")
    want = {True: [[255, 1], [1, 255], [9, 2], [3, 2]], False: [[4, 1], [1, 8], [8, 2], [3, 2]]}
    for compat in (True, False):
        _, end = run_script(seq_tools, tmp_path, text + "@0 play\n", compat=compat, name=f"c{compat}")
        assert [clip(end, t)["scale"] for t in range(4)] == want[compat]
    p = tmp_path / "in.movy1"
    p.write_text("movy1\nbpm 12000\nswing 50\nlink 0\ntk 0 0 0\ncl 0 0 16 0 0:24:60:100:0\n"
                 "cp 0 0 200 3 0 0\n")
    out = tmp_path / "out.movy1"
    subprocess.run([str(seq_tools), "--tracks", "1", "--seq", str(p), "--export", str(out)], check=True)
    assert "cp 0 0 12 3 0 0\n" in out.read_text()


def test_d8_a_burst_has_bounded_work(seq_tools, tmp_path):
    """Movy's core runs up to 255 step_ticks per master tick per track; the
    FM-1's at most 4."""
    s = fm1(tracks=1).cmd("tog 0 0 60 100;cscl 0 255 1").play().run_ticks(4)
    r = s.run(seq_tools, tmp_path, compat=False)
    assert track(r.end, 0)["pos"] <= 4 * 4
    r = s.run(seq_tools, tmp_path, compat=True, name="c")
    assert track(r.end, 0)["pos"] > 4 * 4


# ---- A full event buffer never leaves a note sounding --------------------------------------

def test_a_short_event_buffer_drops_note_ons_not_note_offs(seq_tools, tmp_path):
    """Room is always kept for the note-off of every sounding gate: what does
    not fit is a note-on (dropped whole), a lock (sent at a later step) or a
    clock tick. 8 tracks of 12-note chords on every step at 4X, gates of one
    clip tick: a block's later step_ticks end the notes its first one started,
    after the chords have filled a 72-event buffer."""
    chords = ";".join(f"tog {{t}} {s} " + " ".join(f"{40 + 12 * (s % 4) + k} 100" for k in range(12))
                      for s in range(16))
    s = fm1(tracks=8).cmd("bpm 30000")
    for t in range(8):
        s.cmd(chords.format(t=t) + f";slen {t} 0 15 -1 1;cscl {t} 4 1;alabel {t} 0 synth:x;"
              f"aset {t} 0 1 9 1;aset {t} 0 2 19 1")
    s.play().run_ticks(2 * TPB).cmd("stop").blocks(2)
    r = s.run(seq_tools, tmp_path, compat=False, extra=["--events", "72"])
    assert r.end["stats"]["dropped_events"] > 1000
    sounding = {}
    for e in r.events:
        if e["kind"] in ("on", "off"):
            k = (e["track"], e["a"])
            sounding[k] = sounding.get(k, 0) + (1 if e["kind"] == "on" else -1)
            assert sounding[k] >= 0, e
    assert not any(sounding.values()), "every note-on has its note-off"
    assert len(ons(r.events)) > 1000


# ---- D9: no look-ahead lock for a step a bar launch replaces ---------------------------------

def test_d9_no_lock_for_a_step_that_never_plays(seq_tools, tmp_path):
    """Fixture 05's case: a bar launch replaces the playing clip. Movy sends
    the outgoing clip's step-0 lock one tick before the bar, then the new
    clip's; the FM-1 sends only the new clip's (before its note, D2)."""
    s = fm1().cmd("alabel 0 0 synth:x;abaseq 0 0 40;tog 0 0 60 100;aset 0 0 0 100 1;aset 0 0 8 50 1")
    s.cmd("clipsel 0 1;tog 0 0 67 100;aset 0 0 0 5 1;clipsel 0 0").play().run_ticks(200)
    s.cmd("launch 0 1").run_ticks(TPB)
    got = {}
    for compat in (True, False):
        r = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}")
        got[compat] = [(e["tick"], e["kind"], e["a"], e["b"]) for e in r.events
                       if e["track"] == 0 and e["kind"] in ("cc", "on") and TPB - 2 <= e["tick"] <= TPB]
    assert got[True] == [(TPB - 1, "cc", 102, 100), (TPB, "on", 67, 100), (TPB, "cc", 102, 5)]
    assert got[False] == [(TPB, "cc", 102, 5), (TPB, "on", 67, 100)]


# ---- D10: a recorded off-beat replays where it was played ------------------------------------

def test_d10_recorded_ticks_are_stored_without_the_swing(seq_tools, tmp_path):
    """Played near a swung off-beat (step 7 swung by 10 ticks to 178 at 75 %),
    a note at clip tick 172 anchors to step 7. Movy stores 172 and replays it
    at 172 + 10 (the swing again); the FM-1 stores 162 and replays it at 172."""
    s = fm1(tracks=1).cmd("swing 75;tog 0 0 60 100").play().run_ticks(TPB).cmd("rec 0")
    s.run_ticks(172).cmd("non 0 65 100").run_ticks(10).cmd("nof 0 65").run_ticks(2 * TPB)
    for compat, stored, replay in ((True, 172, 182), (False, 162, 172)):
        r = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}")
        n = [n for n in notes(r.end, 0) if n["pitch"] == 65][0]
        assert (n["step"], n["tick"]) == (7, stored)
        later = [e["tick"] % TPB for e in ons(r.events, pitch=65)]
        assert later and all(t == replay for t in later)


# ---- D11: notes outside the loop window stay silent ------------------------------------------

def test_d11_notes_outside_the_window_are_silent(seq_tools, tmp_path):
    """clen shrinks a clip under its notes: Movy folds a note up to one window
    length past the end back in (step 20 of 16 plays as step 4); the FM-1
    leaves it silent until the window grows again."""
    s = fm1(tracks=1).cmd("tog 0 0 60 100;tog 0 20 62 100;clen 0 16").play().run_ticks(2 * TPB)
    for compat, heard in ((True, [60, 62, 60, 62]), (False, [60, 60])):
        r = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}")
        assert [e["a"] for e in ons(r.events)] == heard


def test_d11_an_early_note_on_the_window_start_plays_there(seq_tools, tmp_path):
    """With the window at step 16, the first step's note nudged early fires
    before the loop start: Movy never plays it, the FM-1 plays it on the
    loop start, as Movy does when the window starts at step 0."""
    s = fm1(tracks=1).cmd("tog 0 16 60 100;loop 0 16 16;enudge 0 16 16 -1 -5").play().run_ticks(2 * TPB)
    assert ons(s.run(seq_tools, tmp_path, compat=True, name="c").events) == []
    assert [e["tick"] for e in ons(s.run(seq_tools, tmp_path, compat=False).events)] == [0, TPB]


# ---- D12: a restart closes and reopens the clock -------------------------------------------

def test_d12_play_while_playing_sends_stop_and_start(seq_tools, tmp_path):
    s = fm1(tracks=1).cmd("tog 0 0 60 100").play().run_ticks(100).mark("r").play().run_ticks(10)
    for compat, want in ((True, ["start"]), (False, ["start", "stop", "start"])):
        r = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}")
        assert [e["kind"] for e in r.events if e["kind"] in ("start", "stop")] == want
        clocks = [e["tick"] for e in kinds(r.events, "clock")]
        assert clocks[-3:] == [0, 4, 8], "F8 restarts from tick 0 in both"


# ---- D13: aclr resets the lane as a freed lane is reset ------------------------------------

def test_d13_aclr_resets_base_and_carry(seq_tools, tmp_path):
    """Movy's aclr unassigns a lane but keeps its base and carried value, so a
    lane labelled again resumes from them; the FM-1 resets both."""
    text = ("#! tracks=1\n@0 tog 0 0 60 100\n@0 alabel 0 0 synth:x\n@0 abaseq 0 0 40\n"
            "@0 aset 0 0 2 99 1\n@0 play\n@20000 aclr 0 0\n@20000 alabel 0 0 synth:y\n@40000 stop\n")
    for compat, base, cur in ((True, 40, 99), (False, 0, -1)):
        _, end = run_script(seq_tools, tmp_path, text.replace("@40000 stop\n", ""), compat=compat,
                            name=f"c{compat}", extra=["--end", "20200"])
        lane = end["tracks"][0]["lanes"][0]
        assert (lane["assigned"], lane["base"], lane["cur"]) == (1, base, cur)


# ---- D4: a first take that ends before it grows ----------------------------------------------

def test_d4_a_full_length_first_take_keeps_its_last_note(seq_tools, tmp_path):
    """A first take anchors a note in its last half-step on the loop end and
    grows the clip a bar to hold it (record_note). A 16-bar clip cannot grow:
    Movy stores step 256, which only R5's fold-back plays, on step 0; the
    FM-1 clamps it to step 255, as an overdub's (D4)."""
    # Play and Rec together: the take starts on tick 0, a bar.
    s = fm1(tracks=1).bpm(30000).cmd("clen 0 256").play().cmd("rec 0").run_ticks(16 * TPB - 8)
    s.cmd("non 0 64 100").run_ticks(2).cmd("nof 0 64").run_ticks(4)
    for compat, step in ((True, 256), (False, 255)):
        e = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}").end
        assert clip(e, 0)["len"] == 256
        assert [n["step"] for n in notes(e, 0)] == [step]


def test_a_first_take_grows_only_from_whole_bars(seq_tools, tmp_path):
    """R4 c: a first take grows a bar at each loop end, but only while its
    length is a whole number of bars (engine.rs 2193)."""
    s = fm1(tracks=1).cmd("clen 0 12").play().cmd("rec 0").run_ticks(TPB + 30)
    s.cmd("non 0 60 100").run_ticks(5).cmd("nof 0 60").run_ticks(3 * TPB)
    for compat in (True, False):
        e = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}").end
        assert e["recording"] and clip(e, 0)["len"] == 12


# ---- D5: Capture into a window past step 0 -----------------------------------------------------

def test_d5_capture_keeps_notes_inside_an_offset_window(seq_tools, tmp_path):
    """A stopped Capture into a clip with notes keeps its length and clamps
    anchors to Movy's `len_steps - 1`: before a window that starts at step
    16. The FM-1 clamps to the window's last step."""
    s = fm1(tracks=1).cmd("tog 0 16 60 100;loop 0 16 16").blocks(4)
    for k in range(8):
        s.cmd(f"non 0 {62 + k} 100").blocks(40).cmd(f"nof 0 {62 + k}").blocks(40)
    s.cmd("cap 0").blocks(2)
    for compat in (True, False):
        e = s.run(seq_tools, tmp_path, compat=compat, name=f"c{compat}",
                  extra=["--capture", "64"]).end
        steps = [n["step"] for n in notes(e, 0) if n["pitch"] >= 62]
        assert steps, "Capture wrote the take"
        if compat:
            assert set(steps) == {15}
        else:
            assert all(16 <= st <= 31 for st in steps)


# ---- Capture's packed events (seq_capture.c): nothing Movy reads is lost -----------------------

def capture_state(tool, tmp_path, text, compat, name, extra=()):
    """Runs a script for its end state only (the long runs log too much)."""
    path, state = tmp_path / f"{name}.txt", tmp_path / f"{name}.json"
    path.write_text(text)
    cmd = [str(tool), "--cmd", str(path), "--state", str(state)] + (["--compat"] if compat else [])
    subprocess.run(cmd + list(extra), check=True, capture_output=True, text=True)
    return json.loads(state.read_text())


def snaps(doc):
    return {s["label"]: s for s in doc["snaps"]}


def long_cycle_script(speed, f1, f3):
    """A muted one-step loop at 300 BPM and 48 kHz (a tick is 100 frames):
    a note at frame f1, a MIDI Start 69 blocks later (the transport restarts,
    cycle 1, and the ring is kept; with no clock after it, the internal clock
    resumes 24,000 frames on), a note at f3, then Capture. One command per
    line and every timing on a block, as the Movy oracle needs."""
    fa = f1 + 69 * 64
    return (f"#! rate=48000 block=64 tracks=1 end={f3 + 30016}\n@0 bpm 30000\n@0 tog 0 0 60 100\n"
            f"@0 clen 0 1\n@0 cscl 0 {speed}\n@0 mute 0 1\n@0 play\n"
            f"#?@{f1} before\n@{f1} non 0 70 100\n@{f1 + 2048} nof 0 70\n@{fa} rt FA\n"
            f"#?@{f3} after\n@{f3} non 0 72 100\n@{f3 + 2048} nof 0 72\n@{f3 + 4096} cap 0\n")


@pytest.mark.parametrize("compat,speed,f1,f3,k", [
    (True, "24 1", 104887552, 104945920, 300),    # 24X: one wrap per master tick
    (False, "4 1", 629169600, 629222016, 41),     # the FM-1's fastest, 4X (D8)
])
@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_capture_tells_a_long_cycle_from_its_low_bits(seq_tools, tmp_path, compat, speed, f1,
                                                      f3, k, tool):
    """A packed event keeps a cycle's low 20 bits and a flag for 2^20 or more.
    A note played on cycle 2^20 + k, a restart that keeps the ring, then a
    note on cycle k at the same playhead: the cycles differ, so Movy's stale
    rule (capture_push) drops the first note and Capture keeps only the
    second [verified for the compat case: the Movy oracle, 2026-10-01]. Low
    bits alone would call the cycles equal and keep both."""
    text = long_cycle_script(speed, f1, f3)
    doc = capture_state(ENGINES / "build" / tool, tmp_path, text, compat, "c")
    before, after = (next(s for s in doc["snaps"] if s["label"] == n) for n in ("before", "after"))
    assert track(before, 0)["cycle"] == 2 ** 20 + k and track(after, 0)["cycle"] == k
    assert sorted(n["pitch"] for n in notes(doc["end"], 0)) == [60, 72]


def periodic_capture(bars, playing):
    """One bar of four notes on a clipless track, repeated for `bars` bars at
    300 BPM and 48 kHz (a bar is exactly 38,400 frames, 600 blocks), then
    Capture: what the ring holds then, 8 bars of it, does not depend on how
    long the pattern ran."""
    bar = 38400
    lines = ["@0 bpm 30000", "@0 watch 1"] + (["@0 play"] if playing else [])
    for b in range(bars):
        for i, p in enumerate((60, 64, 67, 72)):
            f = b * bar + i * 9600
            lines += [f"@{f} non 1 {p} {90 + i}", f"@{f + 4800} nof 1 {p}"]
    end = bars * bar + 640
    lines.append(f"@{end} cap 1")
    return f"#! rate=48000 block=64 tracks=2 end={end + 64}\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("playing", [True, False])
@pytest.mark.parametrize("compat", [True, False])
@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_capture_after_a_long_run_is_the_same_take(seq_tools, tmp_path, playing, compat, tool):
    """1,900 bars (25 minutes, 73 million frames) move the packed frames'
    base twice, and while playing (729,600 master ticks) store the ticks as
    offsets from a base that moves as the ring rolls; the take must come out
    as it does after 16 bars. The checking build also compares every
    unpacked value."""
    tool = ENGINES / "build" / tool
    short = capture_state(tool, tmp_path, periodic_capture(16, playing), compat, "short")["end"]
    long_ = capture_state(tool, tmp_path, periodic_capture(1900, playing), compat, "long")["end"]
    got = notes(long_, 1)
    assert len(got) == 32 and got == notes(short, 1)
    assert clip(long_, 1)["len"] == clip(short, 1)["len"]
    assert long_["capture"] == short["capture"]
    assert long_["bpm_x100"] == short["bpm_x100"]


def full_ring_capture(bars):
    """32 notes a bar on a clipless track, playing at 300 BPM and 48 kHz: 64
    events a bar, so the 256-event ring, not the 8-bar window, bounds what is
    kept (the last 4 bars), and the ring is full and wrapped at every push."""
    bar = 38400
    lines = ["@0 bpm 30000", "@0 watch 1", "@0 play"]
    for b in range(bars):
        for i in range(32):
            f = b * bar + i * 1200
            lines += [f"@{f} non 1 {40 + i} {60 + i}", f"@{f + 600} nof 1 {40 + i}"]
    end = bars * bar + 640
    lines += [f"#?@{end} before", f"@{end} cap 1"]
    return f"#! rate=48000 block=64 tracks=2 end={end + 64}\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("compat", [True, False])
@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_a_full_ring_wraps_and_rebases(seq_tools, tmp_path, compat, tool):
    """At 256 events (compat too, with --capture 256) the newest replaces the
    oldest. 1,000 bars (38.4 million frames, 384,000 master ticks) move both
    packed bases while the ring is full and wrapped; the take, the last 128
    note-ons, must come out as it does after 12 bars."""
    tool = ENGINES / "build" / tool
    extra = ["--capture", "256"]
    short = capture_state(tool, tmp_path, full_ring_capture(12), compat, "short", extra)
    long_ = capture_state(tool, tmp_path, full_ring_capture(1000), compat, "long", extra)
    for doc in (short, long_):
        assert snaps(doc)["before"]["capture"]["pending"] == 128
    got = notes(long_["end"], 1)
    assert len(got) == 128 and got == notes(short["end"], 1)
    assert [n["pitch"] for n in got[:32]] == list(range(40, 72))
    assert clip(long_["end"], 1)["len"] == clip(short["end"], 1)["len"] == 64


# Each packed field at the edge of its range (seq_capture.c gives the ranges). Narrowing any
# field by one bit fails one of these; the scripts are block-aligned for the Movy oracle, and
# Movy's outcome for each was checked through it.

def wide_tracks_capture(cap_track):
    """Notes on tracks 1, 9 and 15 in turn while stopped (16 tracks, Movy's
    count), then Capture of one of them."""
    lines = [f"@0 watch {cap_track}"]
    f = 6400
    for i in range(4):
        for t, base in ((1, 50), (9, 70), (15, 90)):
            p = base + 2 * i
            lines += [f"@{f} non {t} {p} {80 + t}", f"@{f + 2560} nof {t} {p}"]
            f += 7360
    f += 12800
    lines += [f"#?@{f} before", f"@{f} cap {cap_track}"]
    return f"#! rate=44118 block=64 tracks=16 end={f + 64}\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("cap_track,base", [(1, 50), (9, 70), (15, 90)])
@pytest.mark.parametrize("compat", [True, False])
@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_capture_keeps_tracks_past_eight_apart(seq_tools, tmp_path, cap_track, base, compat,
                                               tool):
    """The packed track is 4 bits, tracks 0-15: the take holds the captured
    track's notes and no other's [verified: the Movy oracle, 2026-10-01]."""
    tool = ENGINES / "build" / tool
    doc = capture_state(tool, tmp_path, wide_tracks_capture(cap_track), compat, "w")
    assert snaps(doc)["before"]["capture"]["pending"] == 4
    end = doc["end"]
    assert [(n["pitch"], n["vel"]) for n in notes(end, cap_track)] == \
        [(base + 2 * i, 80 + cap_track) for i in range(4)]
    assert not any(notes(end, t) for t in range(16) if t != cap_track)


def note_off_first_capture():
    """A note held past the gap (4 s at 120 BPM): its note-off clears the ring
    and leads the take that follows, eight notes a beat apart."""
    beat = 22016
    off = 64 + 5 * 44118 // 64 * 64
    lines = ["@0 watch 0", "@64 non 0 50 100", f"@{off} nof 0 50"]
    for i in range(8):
        f = off + (i + 1) * beat
        lines += [f"@{f} non 0 {60 + i} 100", f"@{f + beat // 2} nof 0 {60 + i}"]
    f = off + 10 * beat
    lines += [f"#?@{f} before", f"@{f} cap 0"]
    return f"#! rate=44118 block=64 tracks=1 end={f + 64}\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("compat", [True, False])
@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_a_take_starts_at_its_first_note_on(seq_tools, tmp_path, compat, tool):
    """A stopped take's time zero is its first note-on (Movy's
    cap_take_first), which the packed ring recomputes rather than stores;
    here a stray note-off comes first [verified: the Movy oracle,
    2026-10-01]."""
    tool = ENGINES / "build" / tool
    doc = capture_state(tool, tmp_path, note_off_first_capture(), compat, "o")
    assert snaps(doc)["before"]["capture"]["pending"] == 8
    got = notes(doc["end"], 0)
    assert [n["pitch"] for n in got] == list(range(60, 68))
    assert [n["tick"] for n in got] == [0, 96, 192, 287, 383, 479, 575, 671]


def frame_limit_capture(rate=349525):
    """At 20 BPM the 8-bar window is 96 s, 33,554,400 frames at 349,525 Hz:
    the highest rate whose window fits the packed frame's 25 bits. Note-ons
    every 6 s from the first to one 33,554,368 frames after it (2^25 - 64),
    all inside the window, then Capture while stopped."""
    span = (8 * rate * 24000 // 2000) // 64 * 64
    f0, step = 640, 6 * rate // 64 * 64
    starts = list(range(f0, f0 + span, step)) + [f0 + span]
    pushes = []
    for i, f in enumerate(starts):
        pushes.append((f, f"non 0 {40 + i} 100"))
        if f + 64000 < f0 + span:
            pushes.append((f + 64000, f"nof 0 {40 + i}"))
    end = f0 + span + 64
    lines = ["@0 bpm 2000", "@0 watch 0"] + [f"@{f} {v}" for f, v in sorted(pushes)]
    lines += [f"#?@{end} before", f"@{end} cap 0"]
    return f"#! rate={rate} block=64 tracks=1 end={end + 64}\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("compat", [True, False])
@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_capture_keeps_a_96_s_window_at_349525_hz(seq_tools, tmp_path, compat, tool):
    """All 18 note-ons stay in the ring, and the take starts with the first
    [verified: the Movy oracle, 2026-10-01]."""
    doc = capture_state(ENGINES / "build" / tool, tmp_path, frame_limit_capture(), compat, "f")
    assert snaps(doc)["before"]["capture"]["pending"] == 18
    got = notes(doc["end"], 0)
    assert [(n["tick"], n["pitch"]) for n in got] == [(1152 * i, 40 + i) for i in range(6)]


def tick_span_capture():
    """Playing at 300 BPM and 48 kHz (480 master ticks a second) to tick
    67,200, past 2^16, then a note on a clipless track every 3 s for 96 s,
    each sent at 20 BPM so that the 96-s window keeps every one: their master
    ticks, stored as offsets from a base, span 46,080, the most the window
    can hold."""
    rate = 48000
    t0, window = 140 * rate, 8 * rate * 24000 // 2000
    pushes = []
    for i, f in enumerate(range(t0, t0 + window, 3 * rate)):
        pushes += [(f, f"non 1 {40 + i} 100"), (f + rate, f"nof 1 {40 + i}")]
    pushes.append((t0 + window, "non 1 99 100"))
    lines = ["@0 bpm 30000", "@0 watch 1", "@0 play"]
    for f, v in sorted(pushes):
        lines += [f"@{f} bpm 2000", f"@{f} {v}", f"@{f} bpm 30000"]
    end = t0 + window + 64
    lines += [f"#?@{end} before", f"@{end} cap 1"]
    return f"#! rate={rate} block=64 tracks=2 end={end + 64}\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("compat", [True, False])
@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_capture_keeps_46080_master_ticks(seq_tools, tmp_path, compat, tool):
    """All 33 note-ons stay in the ring; the take starts with the first and
    lands in tick order [verified: the Movy oracle, 2026-10-01]."""
    doc = capture_state(ENGINES / "build" / tool, tmp_path, tick_span_capture(), compat, "t")
    before = snaps(doc)["before"]
    assert before["capture"]["pending"] == 33 and before["master_tick"] == 67200 + 46080
    got = notes(doc["end"], 1)
    assert [(n["tick"], n["gate"], n["pitch"]) for n in got] == \
        [(1440 * i, 480, 40 + i) for i in range(5)]


def deep_playhead_capture():
    """48 kHz at 120 BPM, a tick every 250 frames. An empty clip with its loop
    at step 240; a Capture while playing writes a take into it, which makes
    it 256 steps long from there, and it launches on the next bar (tick 768).
    2,688 ticks later its playhead is at 8,448, past 2^13, and a note is
    played and captured there."""
    tick = 250
    lines = ["@0 watch 0", "@0 loop 0 240 16", "@0 play"]
    for i, at in enumerate((192, 288, 384, 480)):
        lines += [f"@{at * tick} non 0 {60 + i} 100", f"@{(at + 60) * tick} nof 0 {60 + i}"]
    lines.append(f"@{720 * tick} cap 0")
    f = (768 + 2688) * tick
    lines += [f"#?@{f} here", f"@{f} non 0 72 100", f"@{f + 40 * tick} nof 0 72",
              f"@{f + 100 * tick} cap 0"]
    end = f + 100 * tick + 64
    return f"#! rate=48000 block=64 tracks=1 end={end}\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("compat", [True, False])
@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_capture_reads_a_playhead_past_8191(seq_tools, tmp_path, compat, tool):
    """The note lands at its playhead modulo the clip's span, 8,448 mod
    6,144 = 2,304, step 96 [verified: the Movy oracle, 2026-10-01]."""
    doc = capture_state(ENGINES / "build" / tool, tmp_path, deep_playhead_capture(), compat, "p")
    assert track(snaps(doc)["here"], 0)["pos"] == 8448
    c = clip(doc["end"], 0)
    assert (c["len"], c["loop_start"]) == (256, 240)
    got = [(n["tick"], n["step"]) for n in notes(doc["end"], 0) if n["pitch"] == 72]
    assert got == [(2304, 96)]


def fast_loop(k1, k2, cap, between=()):
    """Compat (Movy's 255X; the FM-1 allows 4X, D8): 48 kHz in 100-frame
    blocks at 300 BPM, one master tick a block, and a muted one-step loop at
    254X on track 0, which wraps 127/12 times a tick. A note on track 0 after
    k1 ticks and another after k2, then Capture of track `cap`; `between`
    pushes (block offsets from the first note, verbs, labels) go to clipless
    track 1. Every push is sent at 20 BPM, whose window is 96 s."""
    play, block = 100, 100
    b1, b2 = play + k1, play + k2
    pushes = [(b1, "non 0 70 100", "first"), (b1 + 10, "nof 0 70", None)]
    pushes += [(b1 + d, v, label) for d, v, label in between]
    pushes.append((b2, "non 0 72 100", "second"))
    lines = ["@0 bpm 30000", "@0 tog 0 0 60 100", "@0 clen 0 1", "@0 cscl 0 254 1",
             "@0 mute 0 1", "@0 watch 1", f"@{play * block} play"]
    for b, v, label in sorted(pushes):
        f = b * block
        if label:
            lines.append(f"#?@{f} {label}_before")
        lines += [f"@{f} bpm 2000", f"@{f} {v}"]
        if label:
            lines.append(f"#?@{f} {label}")
        lines.append(f"@{f} bpm 30000")
    f = (b2 + 10) * block
    lines += [f"@{f} nof 0 72", f"@{f} cap {cap}"]
    return f"#! rate=48000 block={block} tracks=2 end={f + block}\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_capture_tells_cycles_2_19_apart(seq_tools, tmp_path, tool):
    """Cycles 2^19 + 646 and 2^20 + 646, 103.2 s apart: as far apart as two
    cycles a note can be compared with get (window and gap, 104 s). Notes on
    track 1 every 4 s, the last exactly 96 s after the first, keep the ring
    from the gap rule. Movy's stale rule sees different cycles at one
    playhead and clears the ring, track 1's notes with it [verified: the Movy
    oracle, 2026-10-01]; 19 low bits and a flag would call them equal."""
    between = []
    for i, d in enumerate(range(40, 46060, 1920)):
        between += [(d, f"non 1 {40 + i} 100", None), (d + 20, f"nof 1 {40 + i}", None)]
    between.append((46080, "non 1 99 100", "last"))
    tool = ENGINES / "build" / tool
    doc = capture_state(tool, tmp_path, fast_loop(49600, 99139, 1, between), True, "y")
    sn = snaps(doc)
    assert track(sn["first"], 0)["cycle"] == 2 ** 19 + 646
    assert track(sn["second"], 0)["cycle"] == 2 ** 20 + 646
    assert sn["second_before"]["capture"]["pending"] == 25
    assert sn["second"]["capture"]["pending"] == 0
    assert not notes(doc["end"], 1), "Capture of track 1 found nothing"


@pytest.mark.parametrize("tool", ["fm1-seq", "fm1-seq-check"])
def test_the_gap_rule_comes_before_the_stale_rule(seq_tools, tmp_path, tool):
    """A note on cycle 2^20 + 1,291, 206.6 s of silence, then one exactly 2^20
    cycles later: the gap rule ends the phrase, so the stale rule never
    compares two cycles that far apart (the checking build trapped on that
    comparison when the stale rule came first). Movy keeps only the second
    note [verified: the Movy oracle, 2026-10-01]."""
    tool = ENGINES / "build" / tool
    doc = capture_state(tool, tmp_path, fast_loop(99200, 198278, 0), True, "g")
    sn = snaps(doc)
    assert track(sn["first"], 0)["cycle"] == 2 ** 20 + 1291
    assert track(sn["second"], 0)["cycle"] == 2 ** 21 + 1291
    assert sorted(n["pitch"] for n in notes(doc["end"], 0)) == [60, 72]


# ---- movy1 integers: Rust's FromStr (F7) --------------------------------------------------

@pytest.mark.parametrize("line,check", [
    ("bpm 18446744073709551621", "bpm 12000"),            # u32 overflow: ignored, not wrapped
    ("swing 18446744073709551676", "swing 50"),
    ("tk 0 0 18446744073709551615", "tk 0 0 1"),          # a usize on the Move: 64 bits
    ("tk 0 0 40000000000000000000", "tk 0 0 0"),          # past u64: no tk line applies
    ("lk 0 0 0:0:18446744073709551716", "!lk 0 0"),       # u8 overflow: the lock is dropped
    ("cl 0 1 16 0 18446744073709551640:24:64:100:1", "cl 0 1 16 0 "),   # no note
    ("pm 0 18446744073709551676", "!pm 0"),
    ("cl 0 2 16 0 0:24:64:0:0", "cl 0 2 16 0 0:24:64:1:0"),   # velocity 0 loads as 1
])
def test_movy1_integers_parse_as_rust_does(seq_tools, tmp_path, line, check):
    """The reviewer's probes, against Movy's output through the oracle."""
    p = tmp_path / "in.movy1"
    p.write_text("movy1\nbpm 12000\nswing 50\nlink 0\ntk 0 0 0\n"
                 "cl 0 0 16 0 0:24:60:100:0;96:24:62:100:4\ncp 0 0 1 1 0 0\n" + line + "\n")
    out = tmp_path / "out.movy1"
    subprocess.run([str(seq_tools), "--compat", "--tracks", "4", "--seq", str(p), "--export",
                    str(out)], check=True)
    text = out.read_text()
    if check.startswith("!"):
        assert not any(l.startswith(check[1:]) for l in text.splitlines()), text
    else:
        assert check in text.splitlines(), text


# ---- Realtime input lines ------------------------------------------------------------------

def test_realtime_lines_are_checked(seq_tools, tmp_path):
    for bad in ("rt F9", "rt 0xF8", "rt F8 1", "rt"):
        p = tmp_path / "b.txt"
        p.write_text(f"@0 {bad}\n")
        r = subprocess.run([str(seq_tools), "--cmd", str(p)], capture_output=True, text=True)
        assert (r.returncode != 0) == (bad != "rt"), bad   # a bare "rt" is a Movy verb (unknown)


# ---- Memory (docs/13 §5, §10 answer 3) -------------------------------------------------

def sizes(tool):
    return json.loads(subprocess.check_output([str(tool), "--sizes"]))


def test_memory_figures_for_four_and_eight_tracks(seq_tools):
    """The owner's budget: about half of docs/13's 72 KiB at the reduced
    track count, Capture included (the owner's decision of 2026-10-01: 256
    packed events, on by default). These are the figures engines/seq.md and
    docs/13 §10 report; a change to the layout must update all three."""
    z = sizes(seq_tools)
    assert z["tracks"]["4"] == 18056
    assert z["tracks"]["8"] == 31880
    assert z["tracks"]["8"] <= HALF_BUDGET
    assert z["no_capture"]["4"] == 14984
    assert z["no_capture"]["8"] == 28808
    for t in range(1, 17):
        assert z["tracks"][str(t)] - z["no_capture"][str(t)] == 256 * 12, \
            "Capture: 256 events of 12 bytes"
    assert z["limits8"] == {"notes": 1536, "locks": 1536, "trigs": 256, "gates": 64, "song": 64,
                            "rec_notes": 16, "pad_mutes": 16, "capture": 256}
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
    """docs/13 §7: no malloc in the link map. The core's objects, and the host
    bridge every host shares (seq_host.o, fm1_seq_host.h), import no
    allocator (nor stdio) at all."""
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    objs = sorted((ENGINES / "build" / "c" / "seq").glob("*.o"))
    assert len(objs) == 6 and "seq_host.o" in [o.name for o in objs]
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
    A:B rows) plays in both modes; compat and FM-1 differ only by D1-D13."""
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
