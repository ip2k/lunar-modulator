"""The song on whole entries (stage E1; notes/2026-10-06-song-and-scenes.md
§5.5, §10; engines/seq.md, "The song").

- The FM-1 verbs (sgins, sgdel, sgset, sgmov, sgclr, sgjump) against a
  Python model of Movy's flat list of presses, the joins and the 64-press
  refusal included, with the export equal to the model's after every edit.
- Edits while the song plays: the playing entry stays with its entry, a
  stale arm is redone, a deleted or recast playing entry hands over on the
  next bar, repeats cut short end on the next bar.
- sgjump while stopped and while playing; the three end modes.
- D15, D16 and D17, each both ways: the default mode, and compat mode
  keeping Movy's behaviour (the song note's scripts A-C of §3.2).
- D16's LOOP hold (`scene`, then `sgnew` and `songadd`) plays exactly what
  Movy's (`song`, then `songadd`) plays, whenever the second press comes.
- The `movy1` lines dq, se and sn round-trip outside compat mode and are
  neither written nor read in it; a 70-press Movy song loads 64 presses.
- ST11: a set import reseeds the RNG (compat: it runs on).
- The guide's 4-minute song at 116 BPM plays its 116 bars hands-free and
  stops the transport on the bar after its last entry, 240 s after its
  first note, through fm1-seq and fm1-render alike.
"""
import json
import random
import subprocess

import pytest

from tests.seq_helpers import RENDER, ons, seq_tools  # noqa: F401

RATE = 44118
TPB = 384
NAMES = ["Intro", "Verse", "Pre", "Chorus", "Drop", "Break", "Build", "Bridge", "Fill", "Outro"]


def tick_frames(bpm=120):
    return RATE * 60 / (bpm * 96)


def at(bar, frac=0.5, start=0, bpm=120):
    """A frame inside `bar` (0-based from the transport's start at frame
    `start`), `frac` of the way through it: clear of any block boundary."""
    return int(start + (bar + frac) * TPB * tick_frames(bpm))


def clip_ops(bars_by_slot, track=0):
    """One clip per slot, `bars` long, with a note of pitch 60 + slot on the
    first step of every bar, so each bar says which scene played it."""
    ops = []
    for slot, bars in bars_by_slot.items():
        ops += [f"clipsel {track} {slot}", f"loop {track} 0 {bars * 16}"]
        ops += [f"tog {track} {b * 16} {60 + slot} 100" for b in range(bars)]
    ops.append(f"clipsel {track} 0")
    return ";".join(ops)


def script(lines, end, tracks=4, bpm=None):
    head = f"#! rate={RATE} block=64 tracks={tracks} end={end}"
    body = ([f"@0 bpm {bpm * 100}"] if bpm else []) + list(lines)
    return "\n".join([head] + body) + "\n"


def run(tool, tmp_path, lines, end, compat=False, name="r", extra=(), tracks=4, bpm=None):
    """(events, end state, snaps by label)."""
    text = script(lines, end, tracks, bpm)
    path = tmp_path / f"{name}.txt"
    path.write_text(text)
    log, state = tmp_path / f"{name}.jsonl", tmp_path / f"{name}.json"
    cmd = [str(tool), "--cmd", str(path), "--log", str(log), "--state", str(state)]
    cmd += (["--compat"] if compat else []) + list(extra)
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    events = [json.loads(x) for x in log.read_text().splitlines()]
    doc = json.loads(state.read_text())
    snaps = {s["label"]: s for s in doc["snaps"] if s["kind"] == "label"}
    return events, doc["end"], snaps


def bar_pitches(events, track=0, bpm=120):
    """{bar: pitch} of the note-ons on the first tick of each bar."""
    return {e["tick"] // TPB: e["a"] for e in ons(events, track) if e["tick"] % TPB == 0}


# ---- A Python model of the list -----------------------------------------------------

def entries(song):
    out = []
    for s in song:
        if out and out[-1][0] == s:
            out[-1][1] += 1
        else:
            out.append([s, 1])
    return out


def flatten(es):
    return [s for s, r in es for _ in range(r)]


def model(song, jump, op, args, lim=64):
    """(song, jump, refused) after one verb on a stopped core."""
    es = entries(song)
    n = len(es)
    if op == "sgclr":
        return [], None, 0
    if op == "sgjump":
        (e,) = args
        return song, (e if 0 <= e < n else jump), 0
    if op == "sgins":
        e, s, r = args
        if not (0 <= e <= n and 0 <= s < 8 and r >= 1):
            return song, jump, 0
        if len(song) + r > lim:
            return song, jump, 1
        es.insert(e, [s, r])
        if jump is not None and jump >= e:
            jump += 1
    elif op == "sgdel":
        (e,) = args
        if not 0 <= e < n:
            return song, jump, 0
        del es[e]
        if jump == e:
            jump = None
        elif jump is not None and jump > e:
            jump -= 1
    elif op == "sgset":
        e, s, r = args
        if not (0 <= e < n and 0 <= s < 8 and r >= 1):
            return song, jump, 0
        if len(song) - es[e][1] + r > lim:
            return song, jump, 1
        es[e] = [s, r]
    elif op == "sgmov":
        e, d = args
        if not 0 <= e < n:
            return song, jump, 0
        to = min(max(e + d, 0), n - 1)
        es.insert(to, es.pop(e))
        if jump == e:
            jump = to
        elif jump is not None and e < to and e < jump <= to:
            jump -= 1
        elif jump is not None and to < e and to <= jump < e:
            jump += 1
    joined, new_jump = [], None
    for i, (s, r) in enumerate(es):
        if joined and joined[-1][0] == s:
            joined[-1][1] += r
        else:
            joined.append([s, r])
        if jump == i:
            new_jump = len(joined) - 1
    return flatten(joined), new_jump, 0


def random_op(rng, song):
    n = len(entries(song))
    k = rng.random()
    e_any = lambda: rng.randint(-1, n + 1)  # noqa: E731
    if k < 0.40:
        return "sgins", (rng.randint(0, n) if rng.random() < 0.9 else e_any(), rng.randint(0, 8),
                         rng.choice([1, 1, 1, 2, 3, 4, 9, 20, 30]))
    if k < 0.55:
        return "sgdel", (e_any(),)
    if k < 0.72:
        return "sgset", (e_any(), rng.randint(0, 7), rng.choice([1, 2, 3, 5, 40]))
    if k < 0.90:
        return "sgmov", (e_any(), rng.randint(-4, 4))
    if k < 0.97:
        return "sgjump", (e_any(),)
    return "sgclr", ()


@pytest.mark.parametrize("seed", range(8))
def test_entry_edits_follow_the_model_of_the_flat_list(seq_tools, tmp_path, seed):
    """Every edit, joins and the 64-press refusal included, against the
    model, with the jump target riding along; and the set's `sg` line is the
    model's list after the last one."""
    rng = random.Random(seed)
    song, jump, refused = [], None, 0
    lines, want = [], []
    for i in range(240):
        op, args = random_op(rng, song)
        song, jump, r = model(song, jump, op, args)
        refused += r
        lines.append(f"@0 {op} {' '.join(map(str, args))}".rstrip())
        lines.append(f"#?@0 e{i}")
        want.append((list(song), jump, refused))
    out = tmp_path / "out.movy1"
    _, end, snaps = run(seq_tools, tmp_path, lines, 0, extra=["--export", str(out)])
    for i, (s, j, r) in enumerate(want):
        got = snaps[f"e{i}"]
        assert (got["song"], got["song_jump"], got["stats"]["refused"]) == (s, j, r), (i, lines[2 * i])
        assert got["song_entries"] == len(entries(s))
    sg = [x for x in out.read_text().splitlines() if x.startswith("sg")]
    assert sg == ([f"sg {' '.join(map(str, song))}"] if song else [])
    assert refused > 0, "the seeds reach the 64-press limit"


def test_a_refused_edit_changes_nothing_and_is_counted(seq_tools, tmp_path):
    lines = ["@0 sgins 0 1 60", "@0 sgins 1 2 4", "#?@0 a", "@0 sgins 0 3 1", "@0 sgset 0 1 61",
             "@0 sgset 1 2 5", "#?@0 b", "@0 sgset 0 1 59", "@0 sgins 2 4 1", "#?@0 c"]
    _, _, s = run(seq_tools, tmp_path, lines, 0)
    assert s["a"]["song"] == [1] * 60 + [2] * 4 and s["a"]["stats"]["refused"] == 0
    assert s["b"]["song"] == s["a"]["song"] and s["b"]["stats"]["refused"] == 3
    assert s["c"]["song"] == [1] * 59 + [2] * 4 + [4] and s["c"]["stats"]["refused"] == 3


def test_an_edit_that_puts_one_scene_side_by_side_joins_it(seq_tools, tmp_path):
    lines = ["@0 sgins 0 1 1", "@0 sgins 1 2 2", "@0 sgins 2 1 1", "#?@0 a",
             "@0 sgdel 1", "#?@0 b", "@0 sgins 1 3 1", "@0 sgins 1 1 2", "#?@0 c",
             "@0 sgmov 1 -1", "#?@0 d"]
    _, _, s = run(seq_tools, tmp_path, lines, 0)
    assert s["a"]["song"] == [1, 2, 2, 1] and s["a"]["song_entries"] == 3
    assert s["b"]["song"] == [1, 1] and s["b"]["song_entries"] == 1
    assert s["c"]["song"] == [1, 1, 1, 1, 3] and s["c"]["song_entries"] == 2
    assert s["d"]["song"] == [3, 1, 1, 1, 1]


def test_a_song_made_on_the_song_page_launches_nothing(seq_tools, tmp_path):
    """sgins on an empty song creates it without launching: stopped, it is
    ready for Play; playing, it waits detached until Play or sgjump."""
    clips = clip_ops({0: 1, 1: 1, 2: 1})
    lines = [f"@0 {clips}", "@0 sgins 0 1 1", "@0 sgins 1 2 1", "#?@0 stopped",
             f"@{at(0, 0.0, 1000)} play", f"@{at(1, 0.5, 1000)} clipsel 0 0",
             "@100000 stop", "@110000 launch 0 0", f"@{110000 + at(0)} sgclr",
             f"@{110000 + at(0)} sgins 0 1 1", f"#?@{110000 + at(0)} running"]
    ev, end, s = run(seq_tools, tmp_path, lines, 110000 + at(3))
    assert not s["stopped"]["playing"] and s["stopped"]["song"] == [1, 2]
    assert s["stopped"]["song_follow"] == 1
    r = s["running"]
    assert r["song"] == [1] and r["song_follow"] == 0 and r["tracks"][0]["queued"] is None
    late = [e["a"] for e in ons(ev, 0) if e["frame"] > 110000 + at(0)]
    assert set(late) == {60}, "the new song launched nothing"


# ---- Playing: jumps, edits, the end -------------------------------------------------

THREE = clip_ops({0: 1, 1: 1, 2: 1, 3: 1})


def play_song(presses, *lines, end_bar=6, compat=False, tool=None, tmp_path=None, name="p"):
    pre = [f"@0 {THREE}"] + [f"@0 sgins {e} {s} {r}" for e, (s, r) in enumerate(entries(presses))]
    pre.append("@0 play")
    return run(tool, tmp_path, pre + list(lines), at(end_bar, 0.0), compat=compat, name=name)


def test_sgjump_while_playing_relaunches_on_the_next_bar(seq_tools, tmp_path):
    ev, end, s = play_song([0, 1, 2], f"@{at(0)} sgjump 2", f"#?@{at(0)} armed",
                           f"@{at(2)} sgjump 0", f"#?@{at(2)} again", tool=seq_tools,
                           tmp_path=tmp_path)
    p = bar_pitches(ev)
    assert [p[b] for b in range(6)] == [60, 62, 60, 60, 61, 62]
    assert s["armed"]["tracks"][0]["queued"] == 2 and s["armed"]["song_pos"] == 2
    assert s["again"]["tracks"][0]["queued"] == 0, "relaunched even while it plays"


def test_sgjump_while_stopped_starts_the_next_play_there(seq_tools, tmp_path):
    lines = [f"@0 {THREE}", "@0 sgins 0 0 1", "@0 sgins 1 1 1", "@0 sgins 2 2 1",
             "@0 sgjump 1", "#?@0 set", "@0 stop", "#?@0 stopped", "@0 sgjump 2", "@0 sgdel 2",
             "#?@0 deleted", "@0 sgjump 1", "@0 play", "#?@0 played"]
    ev, end, s = run(seq_tools, tmp_path, lines, at(3, 0.0))
    assert s["set"]["song_jump"] == 1 and s["stopped"]["song_jump"] is None
    assert s["deleted"]["song_jump"] is None, "an edit that removes the entry clears it"
    assert s["played"]["song_jump"] is None and s["played"]["song_pos"] == 1
    assert [bar_pitches(ev)[b] for b in range(3)] == [61, 60, 61]


def test_the_next_entry_changed_while_armed_redoes_the_arm(seq_tools, tmp_path):
    ev, _, s = play_song([0, 1], f"#?@{at(0)} before", f"@{at(0)} sgset 1 2 1",
                         f"#?@{at(0)} after", tool=seq_tools, tmp_path=tmp_path)
    assert s["before"]["tracks"][0]["queued"] == 1 and s["before"]["song_armed"]
    assert s["after"]["tracks"][0]["queued"] == 2 and s["after"]["song_armed"]
    assert [bar_pitches(ev)[b] for b in range(4)] == [60, 62, 60, 62]


def test_an_armed_entry_given_more_repeats_withdraws_its_arm(seq_tools, tmp_path):
    ev, _, s = play_song([0, 1], f"@{at(0)} sgset 0 0 2", f"#?@{at(0)} grown",
                         tool=seq_tools, tmp_path=tmp_path)
    assert s["grown"]["tracks"][0]["queued"] is None and not s["grown"]["song_armed"]
    assert [bar_pitches(ev)[b] for b in range(5)] == [60, 60, 61, 60, 60]


def test_edits_elsewhere_keep_the_playing_entry_and_its_arm(seq_tools, tmp_path):
    ev, _, s = play_song([0, 1], f"@{at(0)} sgins 0 3 1", f"#?@{at(0)} a", f"@{at(1)} sgmov 0 2",
                         f"#?@{at(1)} b", tool=seq_tools, tmp_path=tmp_path)
    assert s["a"]["song"] == [3, 0, 1] and s["a"]["song_entry"] == 1
    assert s["a"]["tracks"][0]["queued"] == 1
    assert s["b"]["song"] == [0, 1, 3] and s["b"]["song_entry"] == 1
    assert [bar_pitches(ev)[b] for b in range(5)] == [60, 61, 63, 60, 61]


def test_the_playing_entry_deleted_hands_over_on_the_next_bar(seq_tools, tmp_path):
    ev, _, s = play_song([0, 1, 2], f"@{at(0, 0.2)} sgdel 0", f"#?@{at(0, 0.2)} a",
                         tool=seq_tools, tmp_path=tmp_path)
    assert s["a"]["song"] == [1, 2] and s["a"]["song_pos"] == 0
    assert s["a"]["tracks"][0]["queued"] == 1
    assert [bar_pitches(ev)[b] for b in range(5)] == [60, 61, 62, 61, 62]


def test_the_playing_entrys_scene_changed_falls_in_on_the_next_bar(seq_tools, tmp_path):
    ev, _, _ = play_song([0, 0, 0, 1], f"@{at(0)} sgset 0 3 3", tool=seq_tools, tmp_path=tmp_path)
    assert [bar_pitches(ev)[b] for b in range(6)] == [60, 63, 63, 63, 61, 63]


def test_a_handover_leaves_no_selection_from_the_withdrawn_arm(seq_tools, tmp_path):
    """Track 1 has no clip in scene 2, so the arm that queued scene 2 left
    it a deferred selection of that column. The playing entry recast to
    scene 3 hands over on the next bar; nothing of the old arm survives."""
    clips = clip_ops({0: 1, 1: 1, 2: 1}) + ";" + clip_ops({0: 1, 2: 1}, track=1)
    lines = [f"@0 {clips}", "@0 sgins 0 0 1", "@0 sgins 1 1 1", "@0 play",
             f"#?@{at(0)} armed", f"@{at(0)} sgset 0 2 1", f"#?@{at(1)} after"]
    ev, _, s = run(seq_tools, tmp_path, lines, at(3, 0.0))
    assert s["armed"]["tracks"][1]["pending_select"] == 1
    a = s["after"]["tracks"][1]
    assert (a["playing"], a["active"]) == (2, 2), "not moved to the withdrawn arm's column"
    assert bar_pitches(ev, 1)[1] == 62


def test_repeats_cut_below_the_passes_played_end_on_the_next_bar(seq_tools, tmp_path):
    ev, _, s = play_song([0, 0, 0, 0, 1], f"#?@{at(2)} pass", f"@{at(2)} sgset 0 0 1",
                         tool=seq_tools, tmp_path=tmp_path)
    assert (s["pass"]["song_pass"], s["pass"]["song_pass_bar"]) == (3, 1)
    assert [bar_pitches(ev)[b] for b in range(5)] == [60, 60, 60, 61, 60]


def test_the_pass_and_bar_readout(seq_tools, tmp_path):
    clips = clip_ops({0: 2, 1: 1})
    lines = [f"@0 {clips}", "@0 sgins 0 0 2", "@0 sgins 1 1 1", "@0 play"]
    lines += [f"#?@{at(b)} b{b}" for b in range(6)]
    _, _, s = run(seq_tools, tmp_path, lines, at(6, 0.0))
    got = [(s[f"b{b}"]["song_entry"], s[f"b{b}"]["song_pass"], s[f"b{b}"]["song_pass_bar"])
           for b in range(6)]
    assert got == [(0, 1, 1), (0, 1, 2), (0, 2, 1), (0, 2, 2), (1, 1, 1), (0, 1, 1)]
    assert [s[f"b{b}"]["song_armed"] for b in range(6)] == [0, 0, 0, 1, 1, 0]


@pytest.mark.parametrize("compat", [False, True])
def test_end_loop_wraps_to_the_first_entry(seq_tools, tmp_path, compat):
    ev, end, _ = play_song([0, 1], end_bar=5, compat=compat, tool=seq_tools, tmp_path=tmp_path)
    assert [bar_pitches(ev)[b] for b in range(5)] == [60, 61, 60, 61, 60]
    assert end["playing"] and end["song_end"] == 0


def test_end_park_stops_every_track_and_keeps_the_transport(seq_tools, tmp_path):
    ev, end, s = play_song([0, 1], "@0 sgend 1", f"#?@{at(2)} parked", end_bar=5,
                           tool=seq_tools, tmp_path=tmp_path)
    assert [bar_pitches(ev)[b] for b in range(2)] == [60, 61]
    assert not [e for e in ons(ev) if e["tick"] >= 2 * TPB]
    p = s["parked"]
    assert p["playing"] and p["song_parked"] and p["song_entry"] == p["song_entries"] == 2
    assert all(t["playing"] is None for t in p["tracks"])
    assert end["playing"], "the transport runs"


def test_end_stop_stops_the_transport_on_the_bar_after_the_last_entry(seq_tools, tmp_path):
    """With D6's revert and the note-offs, as `stop` gives them; then the song
    is ready for Play from the top."""
    lines = ["@0 alabel 0 0 synth:Cutoff", "@0 abase 0 0 10", "@0 aset 0 0 0 90 1",
             "@0 clipsel 0 1", "@0 aset 0 0 0 100 1", "@0 clipsel 0 0", "@0 sgend 2"]
    ev, end, _ = play_song([0, 1], *lines, f"@{at(3)} play", end_bar=5, tool=seq_tools,
                           tmp_path=tmp_path)
    stop = [e for e in ev if e["kind"] == "stop"]
    assert stop[0]["tick"] == 2 * TPB
    first = [e for e in ev if e["frame"] <= stop[0]["frame"]]
    assert first[-1]["kind"] == "stop" and first[-2] == {**first[-2], "kind": "cc", "a": 102, "b": 10}
    assert [e["a"] for e in ons(ev) if e["frame"] < stop[0]["frame"]] == [60, 61]
    assert not [e for e in ev if e["frame"] > stop[0]["frame"] and e["frame"] < at(3)]
    assert [bar_pitches([e for e in ev if e["frame"] > at(3)])[b] for b in range(2)] == [60, 61]
    assert end["playing"] and end["song_pos"] == 1


def test_end_stop_with_the_last_entry_deleted_stops_on_the_next_bar(seq_tools, tmp_path):
    ev, end, _ = play_song([0, 1], "@0 sgend 2", f"@{at(1)} sgdel 1", end_bar=4,
                           tool=seq_tools, tmp_path=tmp_path)
    assert [e["tick"] for e in ev if e["kind"] == "stop"] == [2 * TPB]
    assert not end["playing"]


def test_the_end_mode_changed_in_the_last_bar_redoes_the_arm(seq_tools, tmp_path):
    ev, end, s = play_song([0, 1], "@0 sgend 1", f"#?@{at(1)} park", f"@{at(1)} sgend 0",
                           f"#?@{at(1)} loop", end_bar=4, tool=seq_tools, tmp_path=tmp_path)
    assert s["park"]["tracks"][0]["pending_stop"] and s["park"]["song_armed"]
    assert s["loop"]["tracks"][0]["queued"] == 0 and not s["loop"]["tracks"][0]["pending_stop"]
    assert [bar_pitches(ev)[b] for b in range(4)] == [60, 61, 60, 61]


# ---- D15, D16, D17: the song note's scripts A-C (§3.2), both ways --------------------

AC = ["@0 tog 0 0 60 100", "@0 clipsel 0 1", "@0 tog 0 0 67 100", "@0 clipsel 0 0",
      "@0 song 0", "@0 songadd 1", "@1000 stop"]


def first_ons(ev, after, n=2):
    return [(e["tick"], e["a"]) for e in ons(ev, 0) if e["frame"] > after][:n]


@pytest.mark.parametrize("compat", [False, True])
def test_d15_a_count_in_does_not_use_up_the_songs_first_bar(seq_tools, tmp_path, compat):
    """Script A. Movy counts the count-in as the first entry's bar, so after
    REC from stopped scene 2 plays first (its scene-1 note on tick 383 is
    D3's off-by-one); the FM-1 plays scene 1 in the bar the count-in ends on."""
    ev, _, _ = run(seq_tools, tmp_path, AC + ["@2000 rec 0"], 700000, compat=compat)
    if compat:
        assert first_ons(ev, 2000) == [(383, 60), (384, 67)]
    else:
        assert first_ons(ev, 2000) == [(384, 60), (768, 67)]


@pytest.mark.parametrize("compat", [False, True])
def test_d17_a_stopped_capture_with_a_song_plays_the_take(seq_tools, tmp_path, compat):
    """Script B. Movy's Play plays the song, so the take is never heard; the
    FM-1 plays the take as a clip launched by hand, and keeps the song
    detached (D16)."""
    notes = [(10000, 72), (40000, 74), (70000, 76), (100000, 77)]
    lines = AC + ["@2000 clipsel 0 2"]
    for f, p in notes:
        lines += [f"@{f} non 0 {p} 100", f"@{f + 10000} nof 0 {p}"]
    ev, end, _ = run(seq_tools, tmp_path, lines + ["@150000 cap 0"], 400000, compat=compat,
                     extra=["--export", str(tmp_path / "b.movy1")])
    set_ = (tmp_path / "b.movy1").read_text()
    assert "cl 0 2 32 0 0:40:72:100:0;" in set_, "the take is written to slot 3 either way"
    played = [e["a"] for e in ons(ev, 0) if e["frame"] > 150000]
    if compat:
        assert played[:3] == [60, 67, 60] and end["song"] == [0, 1] and end["song_follow"]
        assert end["tracks"][0]["playing"] == 0
    else:
        assert played[:4] == [72, 74, 76, 77] and end["tracks"][0]["playing"] == 2
        assert end["song"] == [0, 1] and end["song_follow"] == 0


@pytest.mark.parametrize("compat", [False, True])
def test_d17_rec_from_stopped_makes_no_clip_where_the_song_leaves(seq_tools, tmp_path, compat):
    """Script C. Movy records into the song's scene and leaves an empty clip
    in the slot chosen, which then no longer counts as an empty END scene."""
    lines = AC + ["@2000 clipsel 0 2", "@3000 rec 0", "@100000 non 0 72 100",
                  "@105000 nof 0 72", "@150000 rec 0"]
    _, _, _ = run(seq_tools, tmp_path, lines, 400000, compat=compat,
                  extra=["--export", str(tmp_path / "c.movy1")])
    cl = [x for x in (tmp_path / "c.movy1").read_text().splitlines() if x.startswith("cl ")]
    if compat:
        assert cl == ["cl 0 0 16 0 0:24:60:100:0", "cl 0 1 16 0 0:24:67:100:0;38:21:72:100:2",
                      "cl 0 2 16 0 "]
    else:
        assert cl == ["cl 0 0 16 0 0:24:60:100:0;38:21:72:100:2", "cl 0 1 16 0 0:24:67:100:0"]


@pytest.mark.parametrize("compat", [False, True])
def test_d16_a_hand_launch_detaches_the_song(seq_tools, tmp_path, compat):
    """Default: the song keeps its list and stops following, and STOP then
    PLAY follows it again. Compat: Movy deletes it ("taking the wheel")."""
    ev, end, s = play_song([0, 1], f"@{at(0)} launch 0 3", f"#?@{at(0)} launched",
                           f"@{at(3)} stop", f"@{at(3) + 2000} play", end_bar=6, compat=compat,
                           tool=seq_tools, tmp_path=tmp_path)
    a = s["launched"]
    pitches = [e["a"] for e in ons(ev, 0) if e["frame"] < at(3)]
    assert pitches == [60, 63, 63, 63], "the launched clip plays on, as Movy's"
    later = [e["a"] for e in ons(ev, 0) if e["frame"] > at(3)]
    if compat:
        assert a["song"] == [] and later[:2] == [63, 63]
    else:
        assert a["song"] == [0, 1] and a["song_follow"] == 0 and not a["song_armed"]
        assert later[:3] == [60, 61, 60]


@pytest.mark.parametrize("compat", [False, True])
def test_d18_a_hand_launch_from_stopped_plays_the_clip_launched(seq_tools, tmp_path, compat):
    """Stop in a song's last bar leaves its arm queued. Movy's launch from
    stopped then plays the queued scene from the first tick, so the clip
    launched never sounds; the FM-1 plays the clip launched."""
    ev, _, s = play_song([0, 1], f"@{at(0)} stop", f"#?@{at(0)} stopped",
                         f"@{at(0) + 3000} launch 0 2", end_bar=3, compat=compat,
                         tool=seq_tools, tmp_path=tmp_path)
    assert s["stopped"]["tracks"][0]["queued"] == 1, "the arm outlives Stop, in both modes"
    later = [e["a"] for e in ons(ev, 0) if e["frame"] > at(0) + 3000]
    assert later[:2] == ([61, 61] if compat else [62, 62])


def test_d16_one_scene_press_keeps_the_list(seq_tools, tmp_path):
    ev, end, s = play_song([0, 1], f"@{at(0)} scene 2", f"#?@{at(0)} a", end_bar=4,
                           tool=seq_tools, tmp_path=tmp_path)
    assert s["a"]["song"] == [0, 1] and s["a"]["song_follow"] == 0
    assert [bar_pitches(ev)[b] for b in range(4)] == [60, 62, 62, 62]


def test_scene_in_compat_mode_clears_the_song_as_a_hand_launch(seq_tools, tmp_path):
    ev, _, s = play_song([0, 1], f"@{at(0)} scene 2", f"#?@{at(0)} a", end_bar=3, compat=True,
                         tool=seq_tools, tmp_path=tmp_path)
    assert s["a"]["song"] == []
    assert [bar_pitches(ev)[b] for b in range(3)] == [60, 62, 62]


@pytest.mark.parametrize("delay", [0.0, 0.1, 0.6, 1.0, 1.4, 2.3, 3.7, 5.2])
@pytest.mark.parametrize("bars", [1, 2])
@pytest.mark.parametrize("from_stopped", [False, True])
def test_d16_a_two_press_hold_plays_what_movys_hold_plays(seq_tools, tmp_path, delay, bars,
                                                          from_stopped):
    """LOOP held, scenes 2 then 3. Movy sends `song 1` at the first press
    and `songadd 2` at the second; D16 sends `scene 1`, then `sgnew 1` and
    `songadd 2`. Whenever the second press comes (before the first scene
    lands, in its first pass, or passes later), the events are the same and
    the first scene is never relaunched."""
    clips = clip_ops({0: 1, 1: bars, 2: 1})
    pre = [f"@0 {clips}", "@0 sgins 0 0 1", "@0 sgins 1 3 1"]
    first = 2000 if from_stopped else at(0, 0.3, 1000)
    if not from_stopped:
        pre.append("@1000 play")
    second = first + int(delay * TPB * tick_frames())
    movy = pre + [f"@{first} song 1", f"@{second} songadd 2"]
    d16 = pre + [f"@{first} scene 1", f"@{second} sgnew 1", f"@{second} songadd 2"]
    end = second + at(6, 0.0)
    ev_m, end_m, _ = run(seq_tools, tmp_path, movy, end, name="movy")
    ev_d, end_d, _ = run(seq_tools, tmp_path, d16, end, name="d16")
    assert ev_d == ev_m
    assert end_d["song"] == end_m["song"] == [1, 2]
    assert end_d["song_entry"] == end_m["song_entry"]
    assert end_d["tracks"] == end_m["tracks"]


# ---- Files: dq, se, sn -----------------------------------------------------------------

def export(tool, tmp_path, lines, compat=False, seq=None, name="x"):
    out = tmp_path / f"{name}.movy1"
    extra = ["--export", str(out)]
    if seq is not None:
        (tmp_path / f"{name}.in.movy1").write_text(seq)
        extra += ["--seq", str(tmp_path / f"{name}.in.movy1")]
    _, end, _ = run(tool, tmp_path, lines, 0, compat=compat, name=name, extra=extra)
    return out.read_text(), end


def test_the_fm1_lines_are_written_only_when_set_and_outside_compat(seq_tools, tmp_path):
    plain, _ = export(seq_tools, tmp_path, ["@0 tog 0 0 60 100", "@0 sgins 0 0 2"], name="p")
    assert plain == "movy1\nbpm 12000\nswing 50\nlink 0\nsg 0 0\ntk 0 0 0\n" \
                    "cl 0 0 16 0 0:24:60:100:0\ncp 0 0 1 1 0 0\ntk 1 0 0\ntk 2 0 0\ntk 3 0 0\n"
    lines = ["@0 tog 0 0 60 100", "@0 sgins 0 0 2", "@0 sgins 1 3 1", "@0 dq 35", "@0 sgend 2",
             "@0 sgname 3 4", "@0 sgname 0 1"]
    text, _ = export(seq_tools, tmp_path, lines, name="f")
    head = text.splitlines()[:9]
    assert head == ["movy1", "bpm 12000", "swing 50", "link 0", "dq 35", "sg 0 0 3", "se 2",
                    "sn 0 Intro", "sn 3 Chorus"]
    compat, _ = export(seq_tools, tmp_path, lines, compat=True, name="c")
    assert "dq" not in compat and "\nse " not in compat and "\nsn " not in compat


def test_dq_se_and_sn_round_trip(seq_tools, tmp_path):
    lines = ["@0 tog 0 0 60 100", "@0 sgins 0 0 1", "@0 dq 35", "@0 sgend 1", "@0 sgname 7 10",
             "@0 sgname 2 3"]
    text, _ = export(seq_tools, tmp_path, lines, name="a")
    again, end = export(seq_tools, tmp_path, [], seq=text, name="b")
    assert again == text
    assert end["default_quant"] == 35 and end["song_end"] == 1
    assert end["scene_names"] == ["", "", "Pre", "", "", "", "", "Outro"]
    # The default quantize reaches the empty clips, as `dq` does.
    assert end["tracks"][1]["clips"] == {} and "cp 1" not in again


@pytest.mark.parametrize("compat", [False, True])
def test_an_import_resets_what_the_set_does_not_say(seq_tools, tmp_path, compat):
    """A set without dq, se or sn lines has quantize 0, Loop and no names
    (fm1-seq --import loads it mid-run). Compat mode resets only what is
    the set's in Movy too: the default quantize stays the engine's."""
    (tmp_path / "plain.movy1").write_text("movy1\nbpm 9000\nsg 1 1\n")
    lines = ["@0 dq 35", "@0 sgend 2", "@0 sgname 1 2", "#?@0 before", "#?@1000 after"]
    _, _, s = run(seq_tools, tmp_path, lines, 2000, compat=compat,
                  extra=["--import", f"1000:{tmp_path / 'plain.movy1'}"])
    assert (s["before"]["default_quant"], s["before"]["song_end"]) == (35, 2)
    a = s["after"]
    assert a["song"] == [1, 1] and a["song_end"] == 0 and a["scene_names"][1] == ""
    assert a["default_quant"] == (35 if compat else 0)


def test_compat_mode_reads_none_of_the_fm1_lines(seq_tools, tmp_path):
    """Movy ignores unknown lines: a set with them imports in compat mode as
    it would in Movy (its song loops), and the default quantize is the
    engine's own, kept across the load."""
    seq = "movy1\ndq 70\nsg 0 1\nse 2\nsn 0 Intro\ntk 0 0 0\ncl 0 0 16 0 0:24:60:100:0\n" \
          "cl 0 1 16 0 0:24:61:100:0\n"
    _, end = export(seq_tools, tmp_path, ["@0 dq 20"], compat=True, seq=seq, name="m")
    assert (end["default_quant"], end["song_end"], end["scene_names"][0]) == (20, 0, "")
    ev, end, _ = run(seq_tools, tmp_path, ["@0 play"], at(4, 0.0), compat=True, name="mp",
                     extra=["--seq", str(tmp_path / "m.in.movy1")])
    assert [bar_pitches(ev)[b] for b in range(4)] == [60, 61, 60, 61] and end["playing"]


def test_scene_names_from_files_keep_six_printable_characters(seq_tools, tmp_path):
    seq = "movy1\nsn 0 Verse2b\nsn 1 Ab\x01c\nsn 9 Out\nsn 2 Drop\nsn 2\n"
    _, end = export(seq_tools, tmp_path, [], seq=seq, name="n")
    assert end["scene_names"][:3] == ["Verse2", "", "Drop"]


def test_the_name_picks_are_sg6s_list(seq_tools, tmp_path):
    lines = [f"@0 sgname 0 {k}" + f"\n#?@0 k{k}" for k in range(12)]
    _, _, s = run(seq_tools, tmp_path, lines, 0)
    assert [s[f"k{k}"]["scene_names"][0] for k in range(11)] == [""] + NAMES
    assert s["k11"]["scene_names"][0] == "Outro", "an out-of-range pick does nothing"


@pytest.mark.parametrize("compat", [False, True])
def test_a_seventy_press_movy_song_loads_its_first_sixty_four(seq_tools, tmp_path, compat):
    presses = [k % 8 for k in range(70)]
    seq = "movy1\nsg " + " ".join(map(str, presses)) + "\n"
    out = tmp_path / "s.movy1"
    (tmp_path / "in.movy1").write_text(seq)
    cmd = [str(seq_tools), "--seq", str(tmp_path / "in.movy1"), "--export", str(out),
           "--state", str(tmp_path / "s.json"), "--song", "64"] + (["--compat"] if compat else [])
    subprocess.run(cmd, check=True, capture_output=True)
    end = json.loads((tmp_path / "s.json").read_text())["end"]
    assert end["song"] == presses[:64] and end["stats"]["refused"] == 6


# ---- ST11 -------------------------------------------------------------------------------

@pytest.mark.parametrize("compat", [False, True])
def test_st11_an_import_reseeds_the_rng(seq_tools, tmp_path, compat):
    """A song with probability trigs plays the same notes after every load:
    four bars, Stop, the set loaded again, Play, four bars. In compat mode
    the RNG runs on, as Movy's does, so the second pass rolls differently."""
    steps = ";".join(f"{k * 24}:12:{60 + k % 12}:100:{k}" for k in range(16))
    trigs = ";".join(f"{k}:-1:50:1:1:0" for k in range(16))
    path = tmp_path / "st11.movy1"
    path.write_text(f"movy1\nsg 0\ntk 0 0 0\ncl 0 0 16 0 {steps}\ncp 0 0 1 1 0 0\n"
                    f"tg 0 0 {trigs}\n")
    again = at(4, 0.5) + 2000
    lines = ["@0 play", f"@{at(4, 0.5)} stop", f"@{again} play"]
    ev, _, _ = run(seq_tools, tmp_path, lines, again + at(4, 0.5), compat=compat,
                   extra=["--seq", str(path), "--import", f"{again}:{path}"])
    first = [(e["tick"], e["a"]) for e in ons(ev, 0) if e["frame"] < at(4, 0.5)]
    second = [(e["tick"], e["a"]) for e in ons(ev, 0) if e["frame"] > again]
    assert 10 < len(first) < 4 * 16 and len(second) > 10
    assert (first == second) is (not compat)


# ---- The guide's 4-minute song -------------------------------------------------------------

# Song note §9: seven scenes at 116 BPM, ten entries, 20 presses, 116 bars.
SONG4_BARS = {0: 4, 1: 4, 2: 8, 3: 8, 4: 4, 5: 8, 6: 4}
SONG4 = [(0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (2, 1), (1, 1), (3, 2), (5, 2), (6, 4)]
SONG4_NAMES = {0: 1, 1: 7, 2: 2, 3: 4, 4: 6, 5: 5, 6: 10}


def song4_lines():
    lines = ["@0 bpm 11600", f"@0 {clip_ops(SONG4_BARS)}"]
    lines += [f"@0 sgins {e} {s} {r}" for e, (s, r) in enumerate(SONG4)]
    lines += ["@0 sgend 2"] + [f"@0 sgname {s} {k}" for s, k in SONG4_NAMES.items()]
    return lines + ["#?@0 built", "@0 play"]


def test_the_four_minute_song_plays_through_and_stops(seq_tools, tmp_path):
    end = int(250 * RATE)
    ev, end_state, s = run(seq_tools, tmp_path, song4_lines(), end, name="song4",
                           extra=["--export", str(tmp_path / "song4.movy1")])
    b = s["built"]
    assert b["song"] == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 2, 1, 3, 3, 5, 5, 6, 6, 6, 6]
    assert b["song_entries"] == 10 and b["song_bars"] == 116
    # Every bar plays the scene its entry names, and nothing else plays.
    want = [s_ for s_, r in SONG4 for _ in range(SONG4_BARS[s_] * r)]
    assert len(want) == 116
    pitches = bar_pitches(ev)
    assert [pitches[k] for k in range(116)] == [60 + x for x in want]
    assert len(ons(ev)) == 116
    stop = [e for e in ev if e["kind"] == "stop"]
    assert len(stop) == 1 and stop[0]["tick"] == 116 * TPB
    first = ons(ev)[0]["frame"]
    assert abs((stop[0]["frame"] - first) - 240 * RATE) <= 1, "4:00 from the first note"
    assert not end_state["playing"] and end_state["song_pos"] == 0
    text = (tmp_path / "song4.movy1").read_text().splitlines()
    assert text[4:6] == ["sg 0 0 1 1 2 2 3 3 4 4 2 1 3 3 5 5 6 6 6 6", "se 2"]
    assert text[6:13] == ["sn 0 Intro", "sn 1 Build", "sn 2 Verse", "sn 3 Chorus", "sn 4 Break",
                          "sn 5 Drop", "sn 6 Outro"]


def test_the_four_minute_song_through_fm1_render(seq_tools, tmp_path):
    """The verbs in an fm1-render command script: the same events, sounded."""
    text = script(song4_lines(), int(250 * RATE))
    path = tmp_path / "song4.txt"
    path.write_text(text)
    rlog, slog = tmp_path / "r.jsonl", tmp_path / "s.jsonl"
    res = subprocess.run([str(RENDER), "--cmd", str(path), "--engine", "test-sine", "--frames",
                          "64", "--log-events", str(rlog), "--out", str(tmp_path / "o.wav")],
                         check=True, capture_output=True, text=True)
    subprocess.run([str(seq_tools), "--cmd", str(path), "--log", str(slog)], check=True,
                   capture_output=True)
    assert rlog.read_bytes() == slog.read_bytes()
    s = json.loads(res.stdout)
    assert s["seq_notes_to_engine"] == 116 and s["seq_dropped"] == 0 and s["notes_hung"] == 0
