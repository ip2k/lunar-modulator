"""The arpeggiator core (engines/midi_fx/fm1_arp.h, engines/midi_fx/README.md),
driven through its test tool engines/build/fm1-arp.

Golden event streams for every note order; a Python model of Yarns'
ClockArpeggiator (yarns/part.cc 366-446) that the SPAN octave mode must match
step for step, rhythm masks and Euclidean patterns included; Yarns' rhythm
tables rebuilt from their x-o strings and generator; determinism per seed;
the same output at any block size; every note-on balanced by one note-off
(a seeded fuzz with mid-note setting changes and tiny output buffers);
latch, hold pedal, gate, swing, ratchets, repeats, TRG steps, LOOP, JOIN and
SYNC; no heap; output independent of the instance memory's prior contents.
Since 2026-10-06: each key's origin (played, or the sequencer's), which
latches apart and which STOP lets go; and the steps locked to the host
sequencer's grid while it runs (fm1_arp_process_at, the tool's `run`).
"""
import json
import os
import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"
ARP = ENGINES / "build" / "fm1-arp"
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "arp" / "golden.json"
YARNS = ROOT / "reference" / "mi-eurorack" / "yarns"

T = 100           # frames per tick in these scripts (96 PPQN)
STEP = 24 * T     # a 1/16 step


@pytest.fixture(scope="session")
def arp_tool():
    if not shutil.which("make") or not (shutil.which("cc") or shutil.which("gcc")):
        pytest.skip("no make / C compiler")
    subprocess.run(["make", "-C", str(ENGINES), "-j4", "build/fm1-arp"], check=True,
                   stdout=subprocess.DEVNULL)
    return ARP


@pytest.fixture(scope="session")
def tables(arp_tool):
    return json.loads(subprocess.check_output([str(arp_tool), "--list"]))


def run(tool, text, block=64, cap=64, fill=0, ppqn=96, end=None):
    """Plays a script; returns (events, summary)."""
    args = [str(tool), "--block", str(block), "--cap", str(cap), "--fill", str(fill),
            "--ppqn", str(ppqn)]
    if end is not None:
        args += ["--end", str(end)]
    out = subprocess.run(args, input=text, capture_output=True, text=True, check=True).stdout
    lines = [json.loads(line) for line in out.splitlines()]
    return lines[:-1], lines[-1]["summary"]


def script(*lines, ticks=400, period=T, start=0):
    return f"clock {start} {period} 1 {ticks}\n" + "\n".join(lines) + "\n"


def chord(frame, keys, vel=100):
    return [f"@{frame} on {k} {vel}" for k in keys]


def release(frame, keys):
    return [f"@{frame} off {k}" for k in keys]


def ons(events):
    return [e["key"] for e in events if e["kind"] == "on"]


def on_frames(events):
    return [e["frame"] for e in events if e["kind"] == "on"]


def steps_of(events):
    """Note-ons grouped by frame: [(frame, [keys])]."""
    out = []
    for e in events:
        if e["kind"] != "on":
            continue
        if out and out[-1][0] == e["frame"]:
            out[-1][1].append(e["key"])
        else:
            out.append((e["frame"], [e["key"]]))
    return out


def assert_balanced(events, summary):
    """Each key alternates on, off; nothing sounds at the end; frames ascend."""
    sounding = set()
    last = -1
    for e in events:
        assert e["frame"] >= last, e
        last = e["frame"]
        if e["kind"] == "on":
            assert e["key"] not in sounding, f"second note-on without a note-off: {e}"
            assert 1 <= e["vel"] <= 127
            sounding.add(e["key"])
        else:
            assert e["key"] in sounding, f"note-off with no note-on: {e}"
            sounding.discard(e["key"])
    assert not sounding, sorted(sounding)
    assert summary["sounding"] == 0
    assert summary["ons"] == summary["offs"]


# ---- Tables ------------------------------------------------------------------------------

def xox_to_mask(pattern):
    """Yarns' XoxTo16BitInt (yarns/resources/lookup_tables.py 107-118), rewritten."""
    mask, i = 0, 0
    for c in pattern:
        if c == "o":
            mask |= 1 << i
            i += 1
        elif c == "-":
            i += 1
    assert i == 16
    return mask


def euclid_pattern(k, n):
    """Yarns' EuclideanPattern (lookup_tables.py 169-188), rewritten."""
    pattern = [[1]] * k + [[0]] * (n - k)
    while k:
        cut = min(k, len(pattern) - k)
        k, pattern = cut, [pattern[i] + pattern[k + i] for i in range(cut)] + \
            pattern[cut:k] + pattern[k + cut:]
    mask = 0
    for i, bit in enumerate(b for group in pattern for b in group):
        mask |= bit << i
    return mask


def test_rhythm_masks_are_their_strings(tables):
    src = (ENGINES / "midi_fx" / "arp_rhythm.c").read_text()
    pairs = re.findall(r"(\d+)u,\s*/\* ([o\- ]+?) \*/", src)
    assert len(pairs) == 22
    for value, xox in pairs:
        assert int(value) == xox_to_mask(xox), xox
    assert tables["patterns"][0] == 0xFFFF
    assert tables["patterns"][1:] == [int(v) for v, _ in pairs]


def test_euclid_masks_match_the_generator(tables):
    for length in range(1, 33):
        for fill in range(32):
            assert tables["euclid"][length - 1][fill] == euclid_pattern(min(fill, length), length), \
                (length, fill)


def c_table(text, name):
    m = re.search(r"const uint\d+_t " + name + r"\[\] = \{(.*?)\};", text, re.S)
    return [int(v) for v in re.findall(r"\d+", m.group(1))]


@pytest.mark.skipif(not (YARNS / "resources.cc").exists(), reason="reference/mi-eurorack not cloned")
def test_tables_match_yarns(tables):
    """Against Yarns' own generated tables, when the reference clone is here."""
    text = (YARNS / "resources.cc").read_text()
    assert tables["patterns"][1:] == c_table(text, "lut_arpeggiator_patterns")
    lut = c_table(text, "lut_euclidean")
    assert len(lut) == 32 * 32
    assert [m for row in tables["euclid"] for m in row] == lut


def test_lists(tables):
    names = [p["name"] for p in tables["params"]]
    assert names[:5] == ["mode", "order", "octaves", "oct_mode", "rate"]
    assert len(tables["modes"]) == 22 and tables["modes"][-1] == "chord"
    assert [r["ticks96"] % 4 for r in tables["rates"]] == [0] * 17, "24 PPQN needs multiples of 4"
    assert tables["rates"][4] == {"name": "1/16", "ticks96": 24}
    assert tables["size"] < 1024


# ---- Note orders -------------------------------------------------------------------------

C4 = [60, 64, 67, 71]    # s0..s3

ORDERS = {
    "up": [0, 1, 2, 3],
    "down": [3, 2, 1, 0],
    "up-down": [0, 1, 2, 3, 2, 1],
    "down-up": [3, 2, 1, 0, 1, 2],
    "up&down": [0, 1, 2, 3, 3, 2, 1, 0],
    "down&up": [3, 2, 1, 0, 0, 1, 2, 3],
    "converge": [0, 3, 1, 2],
    "diverge": [2, 1, 3, 0],
    "conv-div": [0, 3, 1, 2, 1, 3],
    "thumb-up": [0, 1, 0, 2, 0, 3],
    "thumb-down": [0, 3, 0, 2, 0, 1],
    "pinky-up": [0, 3, 1, 3, 2, 3],
    "pinky-down": [2, 3, 1, 3, 0, 3],
    "up-top-oct": [0, 1, 2, 3],
    "down-low-oct": [3, 2, 1, 0],
    "up-alt-oct": [0, 1, 2, 3],
    "down-alt-oct": [3, 2, 1, 0],
    "crawl": [0, 2, 1, 3, 2, 3],
}


@pytest.mark.parametrize("mode", sorted(ORDERS))
def test_each_mode_order(arp_tool, mode):
    """Golden orders over four keys in one octave (README, "Note orders")."""
    cycle = [C4[i] for i in ORDERS[mode]]
    n = 3 * len(cycle)
    ev, summ = run(arp_tool, script(f"@0 set mode {mode}", *chord(0, C4),
                                    f"@{n * STEP} flush", ticks=n * 24))
    assert ons(ev) == cycle * 3
    assert on_frames(ev) == [i * STEP for i in range(n)]
    assert_balanced(ev, summ)


@pytest.mark.parametrize("keys", [[60], [60, 67], [60, 64, 67, 71, 74]])
@pytest.mark.parametrize("mode", sorted(ORDERS))
def test_orders_cover_every_key(arp_tool, mode, keys):
    """Every key plays in each pass, whatever the chord size."""
    ev, _ = run(arp_tool, script(f"@0 set mode {mode}", *chord(0, keys), ticks=24 * 40))
    played = ons(ev)
    assert set(played) == set(keys), (mode, played)


LIFT = {   # MCL's octave-lift orders over 60 64 67 in two octaves
    "up-top-oct": [60, 64, 67, 60, 64, 79],
    "down-low-oct": [67, 64, 60, 67, 64, 72],
    "up-alt-oct": [60, 64, 67, 72, 64, 79],
    "down-alt-oct": [67, 64, 60, 79, 64, 72],
}


@pytest.mark.parametrize("mode", sorted(LIFT))
def test_octave_lift_modes(arp_tool, mode):
    ev, _ = run(arp_tool, script(f"@0 set mode {mode}", "@0 set octaves 2", *chord(0, [60, 64, 67]),
                                 ticks=24 * 12))
    assert ons(ev) == LIFT[mode] * 2


def test_octave_modes(arp_tool):
    keys = [60, 64, 67]
    base = [60, 64, 67, 64]  # up-down over one octave
    want = {
        "span": [60, 64, 67, 72, 76, 79, 84, 88, 91, 88, 84, 79, 76, 72, 67, 64],
        "up": base + [k + 12 for k in base] + [k + 24 for k in base],
        "down": [k + 24 for k in base] + [k + 12 for k in base] + base,
        "up-down": base + [k + 12 for k in base] + [k + 24 for k in base] + [k + 12 for k in base],
    }
    for om, cycle in want.items():
        ev, _ = run(arp_tool, script("@0 set mode up-down", "@0 set octaves 3", f"@0 set oct_mode {om}",
                                     *chord(0, keys), ticks=24 * len(cycle) * 2))
        assert ons(ev) == cycle * 2, om


def test_octave_random_is_one_octave_per_pass(arp_tool):
    ev, _ = run(arp_tool, script("@0 set octaves 4", "@0 set oct_mode random", "@0 set seed 9",
                                 *chord(0, [60, 64, 67]), ticks=24 * 3 * 40))
    played = ons(ev)
    shifts = set()
    for i in range(0, len(played) - 2, 3):
        p = played[i:i + 3]
        shift = p[0] - 60
        assert p == [60 + shift, 64 + shift, 67 + shift]
        shifts.add(shift)
    assert shifts == {0, 12, 24, 36}


def test_key_orders(arp_tool):
    keys = [67, 60, 64]   # pressed in this order
    want = {"pitch": [60, 64, 67], "played": [67, 60, 64], "reverse": [64, 60, 67]}
    for order, cycle in want.items():
        lines = [f"@0 set order {order}"] + [f"@{i} on {k} 100" for i, k in enumerate(keys)]
        ev, _ = run(arp_tool, script(*lines, ticks=24 * 6, start=3))
        assert ons(ev) == cycle * 2, order


def test_key_pressed_again_moves_to_newest(arp_tool):
    lines = ["@0 set order played", "@0 on 60 100", "@1 on 64 100", "@2 on 60 100"]
    ev, _ = run(arp_tool, script(*lines, ticks=24 * 4, start=3))
    assert ons(ev) == [64, 60, 64, 60]


def test_chord_mode(arp_tool):
    ev, summ = run(arp_tool, script("@0 set mode chord", *chord(0, [60, 64, 67]),
                                    "@0 set octaves 2", f"@{4 * STEP} flush", ticks=24 * 4))
    assert steps_of(ev) == [(0, [60, 64, 67]), (STEP, [72, 76, 79]), (2 * STEP, [60, 64, 67]),
                            (3 * STEP, [72, 76, 79])]
    assert_balanced(ev, summ)


def test_random_modes(arp_tool):
    keys = [60, 62, 64, 65, 67]
    for mode in ("random", "shuffle", "walk"):
        ev, _ = run(arp_tool, script(f"@0 set mode {mode}", "@0 set seed 3", *chord(0, keys),
                                     ticks=24 * 200))
        played = ons(ev)
        assert len(played) == 200 and set(played) == set(keys), mode
        if mode == "shuffle":
            for i in range(0, 200, 5):
                assert sorted(played[i:i + 5]) == keys, "each key once per pass"
        if mode == "walk":
            idx = [keys.index(k) for k in played]
            assert all(abs(a - b) == 1 for a, b in zip(idx, idx[1:])), "a neighbour each step"
        if mode == "random":
            assert played != (keys * 40)


# ---- Yarns -------------------------------------------------------------------------------

UP, DOWN, UP_DOWN, AS_PLAYED = 0, 1, 2, 4


def yarns_arp(sorted_keys, played_keys, direction, rng, steps, pattern, plen, rotate=0,
              euclid=False):
    """Part::ClockArpeggiator (yarns/part.cc 366-446) and Part::Start (270-290),
    rewritten in Python: one entry per step, the note or None."""
    n = len(sorted_keys)
    if direction == DOWN:
        note, octave, d = n - 1, rng - 1, -1
    else:
        note, octave, d = 0, 0, 1
    step, out = 0, []
    for _ in range(steps):
        bit = (step + rotate) % plen if euclid else step
        if (pattern >> bit) & 1 and n:
            if n == 1 and rng == 1:
                note, octave = 0, 0
            else:
                wrapped = True
                while wrapped:
                    if note >= n or note < 0:
                        octave += d
                        note = 0 if d > 0 else n - 1
                    wrapped = False
                    if octave >= rng or octave < 0:
                        octave = 0 if d > 0 else rng - 1
                        if direction == UP_DOWN:
                            d = -d
                            note = 1 if d > 0 else n - 2
                            octave = 0 if d > 0 else rng - 1
                            wrapped = True
            key = (played_keys if direction == AS_PLAYED else sorted_keys)[note] + 12 * octave
            while key > 127:
                key -= 12
            out.append(key)
            note += d
        else:
            out.append(None)
        step = step + 1 if step + 1 < plen else 0
    return out


def our_steps(ev, steps):
    by_frame = {f: k for f, k in steps_of(ev)}
    out = []
    for i in range(steps):
        keys = by_frame.get(i * STEP)
        assert keys is None or len(keys) == 1
        out.append(keys[0] if keys else None)
    return out


@pytest.mark.parametrize("direction", [UP, DOWN, UP_DOWN, AS_PLAYED])
def test_span_matches_yarns(arp_tool, tables, direction):
    """OCT SPAN is Yarns' arpeggiator: same notes, same rests, over 1-5 keys,
    1-4 octaves, Yarns' 22 rhythm masks and its Euclidean patterns."""
    mode = {UP: "up", DOWN: "down", UP_DOWN: "up-down", AS_PLAYED: "up"}[direction]
    order = "played" if direction == AS_PLAYED else "pitch"
    rng = random.Random(direction)
    steps = 64
    cases = 0
    for n in range(1, 6):
        for octaves in range(1, 5):
            played = rng.sample([60, 62, 63, 65, 67, 70, 72, 100, 115], n)
            rhythms = [("pattern", p) for p in (1, 8, 13, 22)] + [("euclid", None)]
            for kind, p in rhythms:
                lines = [f"@0 set mode {mode}", f"@0 set order {order}", f"@0 set octaves {octaves}"]
                if kind == "pattern":
                    lines.append(f"@0 set pattern {p}")
                    mask, plen, rot, euc = tables["patterns"][p], 16, 0, False
                else:
                    plen, fill, rot = rng.randint(3, 32), rng.randint(0, 31), rng.randint(0, 31)
                    lines += [f"@0 set euclid_len {plen}", f"@0 set euclid_fill {fill}",
                              f"@0 set euclid_rotate {rot}"]
                    mask, euc = tables["euclid"][plen - 1][fill], True
                lines += [f"@{i} on {k} 100" for i, k in enumerate(played)]
                ev, _ = run(arp_tool, script(*lines, ticks=24 * steps, start=len(played)), block=128)
                want = yarns_arp(sorted(played), played, direction, octaves, steps, mask, plen, rot, euc)
                shift = [None if k is None else k for k in want]
                got = our_steps([dict(e, frame=e["frame"] - len(played)) for e in ev], steps)
                assert got == shift, (n, octaves, kind, p, played)
                cases += 1
    assert cases == 100


# ---- Timing: gate, swing, ratchets, repeats, rate ---------------------------------------------

def test_gate_lengths(arp_tool):
    for gate, off in ((50, 1200), (1, 100), (100, 2400), (25, 600)):
        ev, _ = run(arp_tool, script(f"@0 set gate {gate}", *chord(0, [60, 64]), ticks=24 * 2 + 1))
        assert ev[:2] == [{"frame": 0, "kind": "on", "key": 60, "vel": 100},
                          {"frame": off, "kind": "off", "key": 60}], gate


def test_gate_over_100_overlaps_and_retriggers(arp_tool):
    ev, summ = run(arp_tool, script("@0 set gate 150", *chord(0, [60, 64]), f"@{3 * STEP} flush",
                                    ticks=24 * 3))
    assert [(e["frame"], e["kind"], e["key"]) for e in ev] == [
        (0, "on", 60), (STEP, "on", 64), (STEP + STEP // 2, "off", 60), (2 * STEP, "on", 60),
        (2 * STEP + STEP // 2, "off", 64), (3 * STEP, "off", 60)]
    ev, summ = run(arp_tool, script("@0 set gate 150", *chord(0, [60]), f"@{2 * STEP} flush",
                                    ticks=24 * 2))
    assert [(e["frame"], e["kind"], e["key"]) for e in ev] == [
        (0, "on", 60), (STEP, "off", 60), (STEP, "on", 60), (2 * STEP, "off", 60)]
    assert_balanced(ev, summ)


def test_swing_follows_fm1_seq(arp_tool):
    """Odd steps start (SWING-50)*step/60 ticks late (docs/13 R6)."""
    for swing, late in ((50, 0), (66, 6), (80, 12)):
        ev, _ = run(arp_tool, script(f"@0 set swing {swing}", *chord(0, [60]), ticks=24 * 4))
        assert on_frames(ev) == [0, STEP + late * T, 2 * STEP, 3 * STEP + late * T], swing
        offs = [e["frame"] for e in ev if e["kind"] == "off"]
        assert offs[0] == (24 + late) * T // 2 and offs[1] == STEP + late * T + (24 - late) * T // 2


def test_ratchets(arp_tool):
    ev, _ = run(arp_tool, script("@0 set ratchet 3", *chord(0, [60, 64]), ticks=24 * 2))
    assert [(e["frame"], e["kind"], e["key"]) for e in ev[:6]] == [
        (0, "on", 60), (400, "off", 60), (800, "on", 60), (1200, "off", 60), (1600, "on", 60),
        (2000, "off", 60)]
    assert on_frames(ev)[3] == STEP
    # 1/32t at 24 PPQN is 2 ticks: four ratchets become two
    ev, _ = run(arp_tool, script("@0 set ratchet 4", "@0 set rate 1/32t", *chord(0, [60]),
                                 ticks=4, period=400), ppqn=24)
    assert on_frames(ev) == [0, 400, 800, 1200]


def test_ratchet_probability(arp_tool):
    ev, _ = run(arp_tool, script("@0 set ratchet 2", "@0 set ratchet_prob 50", "@0 set seed 1",
                                 *chord(0, [60]), ticks=24 * 64))
    per_step = {}
    for f in on_frames(ev):
        per_step[f // STEP] = per_step.get(f // STEP, 0) + 1
    assert set(per_step.values()) == {1, 2} and len(per_step) == 64


def test_repeat(arp_tool):
    ev, _ = run(arp_tool, script("@0 set repeat 2", *chord(0, [60, 64, 67]), ticks=24 * 12))
    assert ons(ev) == [60, 60, 64, 64, 67, 67] * 2


def test_rates_and_ppqn(arp_tool, tables):
    for i, r in enumerate(tables["rates"][1:], start=1):
        ev96, _ = run(arp_tool, script(f"@0 set rate {r['name']}", *chord(0, [60]), ticks=r["ticks96"] * 3))
        assert on_frames(ev96) == [0, r["ticks96"] * T, 2 * r["ticks96"] * T], r
        ev24, _ = run(arp_tool, script(f"@0 set rate {i}", *chord(0, [60]), ticks=r["ticks96"] * 3 // 4,
                                       period=4 * T), ppqn=24)
        assert on_frames(ev24) == on_frames(ev96), r


def test_rate_change_takes_effect_at_the_next_step(arp_tool):
    ev, _ = run(arp_tool, script(*chord(0, [60]), f"@{STEP // 2} set rate 1/8", ticks=24 * 6))
    assert on_frames(ev) == [0, STEP, 3 * STEP, 5 * STEP]


# ---- Rhythm, chance and LOOP -------------------------------------------------------------

def test_pattern_and_euclid(arp_tool, tables):
    ev, _ = run(arp_tool, script("@0 set pattern 8", *chord(0, [60]), ticks=24 * 16))
    assert [f // STEP for f in on_frames(ev)] == [i for i in range(16) if tables["patterns"][8] >> i & 1]
    ev, _ = run(arp_tool, script("@0 set euclid_len 8", "@0 set euclid_fill 3", "@0 set euclid_rotate 1",
                                 *chord(0, [60]), ticks=24 * 16))
    mask = tables["euclid"][7][3]
    assert mask == 0b00101001                                           # x--x-x--
    assert [f // STEP for f in on_frames(ev)] == [2, 4, 7, 10, 12, 15]  # read one step ahead


def test_probability(arp_tool):
    ev, _ = run(arp_tool, script("@0 set prob 0", *chord(0, [60]), ticks=24 * 32))
    assert ev == []
    ev, _ = run(arp_tool, script("@0 set prob 50", "@0 set seed 4", *chord(0, [60, 64, 67]), ticks=24 * 200))
    assert 70 < len(ons(ev)) < 130
    # a skipped step still moves the order on
    for f, (k,) in steps_of(ev):
        assert k == [60, 64, 67][(f // STEP) % 3]


def test_chord_probability_and_octave_jump(arp_tool):
    ev, _ = run(arp_tool, script("@0 set chord_prob 100", *chord(0, [60, 64]), ticks=24 * 2))
    assert steps_of(ev) == [(0, [60, 64]), (STEP, [60, 64])]
    ev, _ = run(arp_tool, script("@0 set oct_jump 100", *chord(0, [60, 64]), ticks=24 * 2))
    assert ons(ev) == [72, 76]


def test_velocity_and_spreads(arp_tool):
    ev, _ = run(arp_tool, script("@0 set velocity 90", *chord(0, [60], vel=30), ticks=24))
    assert ev[0]["vel"] == 90
    ev, _ = run(arp_tool, script("@0 set vel_spread 20", "@0 set seed 2", *chord(0, [60], vel=100),
                                 ticks=24 * 64))
    vels = [e["vel"] for e in ev if e["kind"] == "on"]
    assert min(vels) >= 80 and max(vels) <= 120 and len(set(vels)) > 10
    ev, _ = run(arp_tool, script("@0 set gate_spread 40", "@0 set seed 2", *chord(0, [60]), ticks=24 * 64))
    lengths = [b["frame"] - a["frame"] for a, b in zip(ev[::2], ev[1::2])]
    assert min(lengths) >= 2 * T and max(lengths) <= 22 * T and len(set(lengths)) > 5


def test_loop_repeats_the_phrase(arp_tool):
    ev, _ = run(arp_tool, script("@0 set mode random", "@0 set loop 8", "@0 set seed 7",
                                 "@0 set vel_spread 30", "@0 set prob 70",
                                 *chord(0, [60, 62, 64, 67, 69]), ticks=24 * 64))
    by_step = {f // STEP: (e_key, vel) for f, e_key, vel in
               ((e["frame"], e["key"], e["vel"]) for e in ev if e["kind"] == "on")}
    phrase = [by_step.get(s) for s in range(8)]
    assert len(set(phrase)) > 3
    for s in range(64):
        assert by_step.get(s) == phrase[s % 8]
    ev, _ = run(arp_tool, script("@0 set loop 4", *chord(0, [60, 64, 67]), ticks=24 * 8))
    assert ons(ev) == [60, 64, 67, 60] * 2


# ---- Seeds and golden streams ------------------------------------------------------------

def busy_script():
    lines = ["@0 set mode random", "@0 set octaves 3", "@0 set seed 1234", "@0 set ratchet 3",
             "@0 set ratchet_prob 40", "@0 set gate_spread 30", "@0 set vel_spread 15",
             "@0 set swing 66", "@0 set chord_prob 10", "@0 set oct_jump 15", "@0 set prob 85"]
    lines += chord(10, [60, 63, 67, 70])
    lines += [f"@{5 * STEP + 37} set mode shuffle", f"@{9 * STEP + 5} off 63",
              f"@{11 * STEP} set mode walk", f"@{13 * STEP + 900} on 74 80",
              f"@{16 * STEP + 1} set euclid_len 7", f"@{16 * STEP + 1} set euclid_fill 4",
              f"@{20 * STEP + 3} set rate 1/8t", f"@{24 * STEP} set mode converge",
              f"@{24 * STEP} set oct_mode up-down", f"@{30 * STEP + 77} set latch 1"]
    lines += release(31 * STEP, [60, 67, 70, 74])
    lines += [f"@{36 * STEP + 11} on 48 127", f"@{40 * STEP} set gate 180", f"@{44 * STEP} flush"]
    return script(*lines, ticks=24 * 44, start=3)


GOLDEN_CASES = {
    "busy": busy_script,
    "walk_loop": lambda: script("@0 set mode walk", "@0 set loop 12", "@0 set seed 99",
                                "@0 set octaves 2", *chord(0, [57, 60, 64, 67, 71]),
                                f"@{30 * STEP} flush", ticks=24 * 30),
    "trg_steps": lambda: script("@0 set rate trg", "@0 set ratchet 2", *chord(0, [60, 65]),
                                *[f"@{i * 1750} step" for i in range(12)], f"@{12 * 1750} flush",
                                ticks=12 * 1750 // T + 1),
}


@pytest.mark.parametrize("name", sorted(GOLDEN_CASES))
def test_golden_streams(arp_tool, name):
    """Pinned streams: a seed must replay the same notes on every build
    (32- and 64-bit, sanitizers) and after any refactor. FM1_ARP_REGOLD=1
    rewrites the fixture."""
    ev, summ = run(arp_tool, GOLDEN_CASES[name]())
    assert_balanced(ev, summ)
    got = [[e["frame"], e["kind"], e["key"], e.get("vel", 0)] for e in ev]
    gold = json.loads(GOLDEN.read_text()) if GOLDEN.exists() else {}
    if os.environ.get("FM1_ARP_REGOLD"):
        gold[name] = got
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text("{\n" + ",\n".join(
            f'"{k}": [\n' + ",\n".join(json.dumps(r) for r in gold[k]) + "\n]" for k in sorted(gold))
            + "\n}\n")
    assert gold.get(name) == got


def test_seed_decides(arp_tool):
    text = busy_script()
    a, _ = run(arp_tool, text)
    b, _ = run(arp_tool, text)
    c, _ = run(arp_tool, text.replace("set seed 1234", "set seed 1235"))
    assert a == b
    assert a != c


# ---- Block size, memory, heap --------------------------------------------------------------

def test_same_output_at_any_block_size(arp_tool):
    text = busy_script()
    base, _ = run(arp_tool, text, block=128)
    assert len(base) > 100
    for block in (1, 7, 64, 1000, 65535):
        ev, _ = run(arp_tool, text, block=block, cap=4096)
        assert ev == base, block


def test_output_does_not_depend_on_prior_memory(arp_tool):
    text = busy_script()
    runs = [run(arp_tool, text, fill=f)[0] for f in (0, 0xA5, 0xFF)]
    assert runs[0] == runs[1] == runs[2]


HEAP = {"malloc", "calloc", "realloc", "free", "posix_memalign", "aligned_alloc", "strdup",
        "printf", "fprintf", "snprintf", "sprintf", "fopen", "fwrite", "rand", "srand"}


def test_the_core_never_allocates(arp_tool):
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    objs = sorted((ENGINES / "build" / "midi_fx").glob("*.o"))
    objs = [o for o in objs if o.name != "arp_tool.o"]
    # the core, and its engine API wrapper and registry (the MIDI effect
    # the hosts run, tests/test_engine_midi_fx.py)
    assert [o.name for o in objs] == ["arp_engine.o", "arp_rhythm.o", "fm1_arp.o", "registry.o"]
    for o in objs:
        out = subprocess.check_output([nm, "-u", str(o)], text=True)
        names = {line.split()[-1].lstrip("_") for line in out.splitlines() if line.strip()}
        assert not names & HEAP, f"{o.name} imports {sorted(names & HEAP)}"


# ---- Latch, hold pedal, JOIN, SYNC ---------------------------------------------------------

def test_latch(arp_tool):
    s = 4 * STEP
    lines = ["@0 set latch 1", *chord(0, [60, 64, 67]), *release(100, [60, 64, 67]),
             # all keys up: a new key replaces the latched chord
             f"@{s} on 62 100",
             # a key added while one is down joins
             f"@{2 * s} on 65 100", *release(2 * s + 100, [62, 65]),
             # Yarns: hold two, let one go, press another: the released one goes
             *chord(3 * s, [48, 52]), f"@{3 * s + 100} off 52", f"@{3 * s + 200} on 55 100",
             f"@{3 * s + 300} off 48", f"@{3 * s + 300} off 55",
             # latch off: the released keys go, the arp stops
             f"@{4 * s + 100} set latch 0", f"@{6 * s} flush"]
    ev, summ = run(arp_tool, script(*lines, ticks=24 * 24))
    played = steps_of(ev)

    def keys_between(a, b):
        return {k for f, ks in played if a <= f < b for k in ks}
    assert keys_between(0, s) == {60, 64, 67}
    assert keys_between(s, 2 * s) == {62}
    assert keys_between(2 * s + STEP, 3 * s) == {62, 65}
    assert keys_between(3 * s + STEP, 4 * s) == {48, 55}
    assert keys_between(4 * s + STEP, 6 * s) == set()
    assert_balanced(ev, summ)


def test_hold_pedal(arp_tool):
    s = 4 * STEP
    lines = ["@0 on 60 100", "@0 sus 1", "@100 off 60", f"@{s} on 64 100",
             f"@{2 * s} sus 0", f"@{3 * s} off 64", f"@{4 * s} flush"]
    ev, summ = run(arp_tool, script(*lines, ticks=24 * 16))
    played = steps_of(ev)
    first = {k for f, ks in played if 0 <= f < s for k in ks}
    both = {k for f, ks in played if s <= f < 2 * s for k in ks}
    after = {k for f, ks in played if 2 * s + STEP <= f < 3 * s for k in ks}
    tail = {k for f, ks in played if 3 * s + STEP <= f for k in ks}
    assert (first, both, after, tail) == ({60}, {60, 64}, {64}, set())
    assert_balanced(ev, summ)


def test_join_at_the_next_pass(arp_tool):
    for join, want in ((0, [60, 64, 67, 71, 60, 64, 67, 71]), (1, [60, 64, 67, 60, 64, 67, 71, 60])):
        lines = [f"@0 set join {join}", *chord(0, [60, 64, 67]), f"@{STEP + 1} on 71 100"]
        ev, _ = run(arp_tool, script(*lines, ticks=24 * 8))
        got = ons(ev)
        if join == 0:
            assert got[:2] == [60, 64] and got[2:] == [67, 71, 60, 64, 67, 71]
        else:
            assert got == want


def test_join_waits_for_a_loop_restart(arp_tool):
    """LOOP shorter than the pass restarts the pass, and lets waiting keys in."""
    lines = ["@0 set join 1", "@0 set loop 2", *chord(0, [60, 64, 67]), f"@{STEP + 1} on 71 100"]
    ev, _ = run(arp_tool, script(*lines, ticks=24 * 6))
    assert ons(ev) == [60, 64, 60, 64, 60, 64]
    ev, _ = run(arp_tool, script(*lines, "@0 set mode down", ticks=24 * 4))
    assert ons(ev) == [67, 64, 71, 67]


def test_sync_key_and_free(arp_tool):
    late = 10 * STEP + 1050
    ev, _ = run(arp_tool, script(*chord(late, [60]), ticks=24 * 14))
    assert on_frames(ev)[:2] == [late + 50, late + 50 + STEP], "key: the next tick is step 0"
    ev, _ = run(arp_tool, script("@0 set sync 0", *chord(late, [60]), ticks=24 * 14))
    assert on_frames(ev)[:2] == [11 * STEP, 12 * STEP], "free: the grid runs on"
    ev, _ = run(arp_tool, script("@0 set sync 0", *chord(late, [60]), f"@{late} reset", ticks=24 * 14))
    assert on_frames(ev)[0] == late + 50, "reset rejoins at the next tick"


# ---- Origins and Stop (owner, 2026-10-06) ----------------------------------------------------

def seq_chord(frame, keys, vel=90):
    return [f"@{frame} on {k} {vel} seq" for k in keys]


def seq_release(frame, keys):
    return [f"@{frame} off {k} seq" for k in keys]


def test_stop_lets_go_of_the_sequencers_keys_and_keeps_the_played_ones(arp_tool):
    """Latched: a chord played by hand, then the sequencer's notes, which join
    it (each origin latches against its own later keys only), then STOP: the
    sequencer's keys go and their sounding note ends at once; the hand's
    latched chord plays on. The notes the sequencer's keys made carry its
    mark out ("seq": 1)."""
    s = 4 * STEP
    lines = ["@0 set latch 1", *chord(0, [60, 64]), *release(100, [60, 64]),
             *seq_chord(s, [72]), *seq_release(s + 100, [72]),
             # the sequencer's next chord replaces its own latched one, not the hand's
             *seq_chord(2 * s, [74]), *seq_release(2 * s + 100, [74]),
             f"@{3 * s + STEP // 4} stop", f"@{5 * s} set latch 0"]
    ev, summ = run(arp_tool, script(*lines, ticks=24 * 22))
    played = steps_of(ev)

    def keys_between(a, b):
        return {k for f, ks in played if a <= f < b for k in ks}
    assert keys_between(0, s) == {60, 64}
    assert keys_between(s + STEP, 2 * s) == {60, 64, 72}
    assert keys_between(2 * s + STEP, 3 * s) == {60, 64, 74}
    assert keys_between(3 * s + STEP, 5 * s) == {60, 64}, "Stop kept a key of the sequencer's"
    assert all(e.get("seq") == 1 for e in ev if e["key"] in (72, 74))
    assert not any(e.get("seq") for e in ev if e["key"] in (60, 64))
    stop = 3 * s + STEP // 4
    at_stop = [(e["kind"], e["key"]) for e in ev if e["frame"] == stop]
    assert at_stop in ([], [("off", 74)]), at_stop
    assert summ["held_seq"] == 0
    assert_balanced(ev, summ)


def test_stop_ends_only_the_sequencers_notes(arp_tool):
    """Gate 200 %: at STOP a note of the hand's and one of the sequencer's
    sound together; only the sequencer's ends there. A key both played and
    given by the sequencer is the hand's too, and stays."""
    lines = ["@0 set gate 200", "@0 set mode chord", *chord(0, [60, 67]), *seq_chord(0, [67, 72]),
             f"@{STEP + 600} stop", *release(4 * STEP, [60, 67]), f"@{6 * STEP} flush"]
    ev, summ = run(arp_tool, script(*lines, ticks=24 * 8))
    at_stop = sorted(e["key"] for e in ev if e["frame"] == STEP + 600)
    assert at_stop == [72]
    after = {e["key"] for e in ev if e["kind"] == "on" and e["frame"] > STEP + 600}
    assert after == {60, 67}
    assert_balanced(ev, summ)


def test_stop_ends_a_trg_note_waiting_for_a_step(arp_tool):
    """RATE TRG: a key's first note waits for the next STEP, which no
    stopped sequencer sends: STOP ends it."""
    ev, summ = run(arp_tool, script("@0 set rate trg", *chord(0, [60]), "@0 step", "@900 stop", ticks=20))
    assert [(e["frame"], e["kind"]) for e in ev] == [(0, "on"), (900, "off")]
    assert summ["held"] == 1 and summ["held_seq"] == 0
    ev, summ = run(arp_tool, script("@0 set rate trg", *chord(0, [60]), "@0 step", "@900 flush",
                                    "@1000 stop", ticks=20))
    assert_balanced(ev, summ)


def test_a_key_held_by_both_origins_stays_until_both_let_go(arp_tool):
    """Unlatched: the hand and a track hold one pitch; the track's release
    leaves it to the hand, the hand's ends it."""
    lines = [*chord(0, [60]), *seq_chord(0, [60]), *seq_release(STEP + 100, [60]),
             *release(4 * STEP + 100, [60])]
    ev, summ = run(arp_tool, script(*lines, ticks=24 * 8))
    assert on_frames(ev) == [0, STEP, 2 * STEP, 3 * STEP, 4 * STEP]
    assert_balanced(ev, summ)


# ---- The sequencer's grid (owner, 2026-10-06) -------------------------------------------------

@pytest.mark.parametrize("block", [1, 7, 64])
def test_steps_lock_to_the_sequencers_grid_while_it_runs(arp_tool, block):
    """`run POS`: the first tick is the sequencer's tick POS. A key between
    grid steps waits for the next one (Sync Key or Free), not the next tick;
    swing delays the odd steps as the grid's; `halt` lets it run on from the
    last step, as when stopped."""
    lines = ["@0 run 10", *chord(550, [60])]        # tick 10 at frame 0: the next 1/16 is tick 24
    ev, _ = run(arp_tool, script(*lines, ticks=24 * 5), block=block)
    assert on_frames(ev)[:3] == [14 * T, 38 * T, 62 * T]
    ev, _ = run(arp_tool, script("@0 set sync 0", *lines, ticks=24 * 5), block=block)
    assert on_frames(ev)[:2] == [14 * T, 38 * T]
    ev, _ = run(arp_tool, script(*chord(550, [60]), ticks=24 * 3), block=block)
    assert on_frames(ev)[:2] == [6 * T, 30 * T], "stopped: at the next tick, as before"
    # 1/8 triplets (32 ticks) from tick 70: the next is tick 96, then 128
    ev, _ = run(arp_tool, script("@0 set rate 1/8t", "@0 run 70", *chord(0, [60]), ticks=24 * 4),
                block=block)
    assert on_frames(ev)[:2] == [26 * T, 58 * T]
    # swing 60 on 1/16: even steps on multiples of 24, odd ones 4 ticks late
    ev, _ = run(arp_tool, script("@0 set swing 60", "@0 run 0", *chord(0, [60]), ticks=24 * 5),
                block=block)
    assert on_frames(ev)[:4] == [0, 28 * T, 48 * T, 76 * T]
    # running, then halted: the steps run on from the last grid step
    ev, _ = run(arp_tool, script("@0 run 5", *chord(0, [60]), f"@{30 * T} halt", ticks=24 * 4),
                block=block)
    assert on_frames(ev)[:3] == [19 * T, 43 * T, 67 * T]


def test_the_grid_is_kept_through_rate_changes(arp_tool):
    """A rate turned while the sequencer runs takes the new rate's grid at
    once: its next step, never in between."""
    lines = ["@0 run 0", *chord(0, [60]), f"@{30 * T} set rate 1/8"]
    ev, _ = run(arp_tool, script(*lines, ticks=24 * 8))
    assert on_frames(ev)[:4] == [0, 24 * T, 48 * T, 96 * T]


# ---- TRG -------------------------------------------------------------------------------------

def test_trg_steps(arp_tool):
    lines = ["@0 set rate trg", *chord(0, [60, 64, 67])] + [f"@{i * 3000} step" for i in range(4)]
    ev, summ = run(arp_tool, script(*lines, f"@{12000} flush", ticks=121))
    assert [(e["frame"], e["kind"], e["key"]) for e in ev] == [
        (0, "on", 60), (3000, "off", 60),                     # first: no measured step yet
        (3000, "on", 64), (4500, "off", 64),                  # then 30 ticks, gate 50 %
        (6000, "on", 67), (7500, "off", 67), (9000, "on", 60), (10500, "off", 60)]
    assert_balanced(ev, summ)
    ev, _ = run(arp_tool, "@0 set rate trg\n@0 on 60 100\n@0 step\n@500 step\n@900 flush\n")
    assert [(e["frame"], e["kind"]) for e in ev] == [(0, "on"), (500, "off"), (500, "on"), (900, "off")]
    ev, _ = run(arp_tool, script(*chord(0, [60]), *[f"@{i * 300} step" for i in range(8)], ticks=48))
    assert on_frames(ev) == [0, STEP], "STEP is ignored unless RATE is TRG"


@pytest.mark.parametrize("block", [1, 64, 3000])
def test_a_trg_step_on_a_tick_ends_notes_first(arp_tool, block):
    """A STEP on a tick's frame: the notes whose gates end at that tick go
    out before the step's note-on, as at a rate's step (note-offs before
    note-ons at one frame); the gates, ratchets and the measured step are
    as they were (a gate of 100 % ends on the next step, a ratchet of 2 at
    its half)."""
    lines = ["@0 set rate trg", "@0 set gate 100", *chord(0, [60, 64, 67])]
    lines += [f"@{i * 3000} step" for i in range(5)]
    ev, summ = run(arp_tool, script(*lines, f"@{15000} flush", ticks=151), block=block)
    assert [(e["frame"], e["kind"], e["key"]) for e in ev] == [
        (0, "on", 60), (3000, "off", 60), (3000, "on", 64), (6000, "off", 64), (6000, "on", 67),
        (9000, "off", 67), (9000, "on", 60), (12000, "off", 60), (12000, "on", 64), (15000, "off", 64)]
    assert_balanced(ev, summ)
    lines = ["@0 set rate trg", "@0 set ratchet 2", "@0 set gate 100", *chord(0, [60])]
    lines += [f"@{i * 3000} step" for i in range(3)]
    ev, _ = run(arp_tool, script(*lines, "@9000 flush", ticks=91), block=block)
    assert [(e["frame"], e["kind"]) for e in ev] == [
        (0, "on"), (3000, "off"), (3000, "on"), (4500, "off"), (4500, "on"), (6000, "off"),
        (6000, "on"), (7500, "off"), (7500, "on"), (9000, "off")]


# ---- The ledger --------------------------------------------------------------------------

PARAM_FUZZ = [("mode", 0, 21), ("order", 0, 2), ("octaves", 1, 4), ("oct_mode", 0, 4), ("rate", 0, 16),
              ("gate", 1, 200), ("swing", 50, 80), ("pattern", 0, 22), ("euclid_len", 0, 32),
              ("euclid_fill", 0, 32), ("euclid_rotate", 0, 31), ("latch", 0, 1), ("join", 0, 1),
              ("sync", 0, 1), ("repeat", 1, 8), ("ratchet", 1, 4), ("ratchet_prob", 0, 100),
              ("prob", 0, 100), ("chord_prob", 0, 100), ("oct_jump", 0, 100), ("velocity", 0, 127),
              ("vel_spread", 0, 127), ("gate_spread", 0, 100), ("loop", 0, 64), ("seed", 0, 65535)]


def fuzz_script(seed, origins=False):
    """A seeded script. With `origins`, half the notes are the sequencer's,
    STOP lands anywhere, and the sequencer runs and halts (its grid)."""
    rng = random.Random(seed)
    frames = sorted(rng.randrange(0, 60000) for _ in range(rng.randint(40, 160)))
    lines = []
    down = set()
    for f in frames:
        r = rng.random()
        if r < 0.30:
            k = rng.choice([24, 48, 60, 62, 64, 67, 71, 72, 96, 120, 127])
            src = " seq" if origins and rng.random() < 0.5 else ""
            lines.append(f"@{f} on {k} {rng.randint(0, 127)}{src}")
            down.add((k, src))
        elif r < 0.50 and down:
            k, src = rng.choice(sorted(down))
            lines.append(f"@{f} off {k}{src}")
            down.discard((k, src))
        elif r < 0.85:
            name, lo, hi = rng.choice(PARAM_FUZZ)
            lines.append(f"@{f} set {name} {rng.randint(lo, hi)}")
        elif origins and r < 0.92:
            lines.append(f"@{f} " + rng.choice(["stop", "run 0", f"run {rng.randrange(0, 1 << 40)}",
                                                 "halt"]))
        else:
            lines.append(f"@{f} " + rng.choice(["step", "step", "reset", "flush", "panic",
                                                 "sus 1", "sus 0"]))
    lines += [f"@60000 off {k}{src}" for k, src in sorted(down)] + ["@60001 flush"]
    period = rng.choice([7, 50, 100, 333])
    return f"clock 0 {period} 1 {60001 // period + 1}\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("seed", range(40))
def test_every_note_on_gets_one_note_off(arp_tool, seed):
    """Settings change mid-note, keys come and go, the rate switches to TRG
    and back, the pedal, PANIC and RESET land anywhere: each note-on still
    gets exactly one note-off, at any block size, and with an output buffer
    of one, two or 64 events (offs deferred, ons dropped and counted)."""
    text = fuzz_script(seed)
    base, summ = run(arp_tool, text, block=64, cap=4096)
    assert_balanced(base, summ)
    assert summ["dropped_ons"] == 0 and summ["deferred_offs"] == 0
    ev, _ = run(arp_tool, text, block=[1, 7, 500][seed % 3], cap=4096)
    assert ev == base
    for cap in (1, 2, 64):
        ev, summ = run(arp_tool, text, block=[3, 64][seed % 2], cap=cap)
        assert_balanced(ev, summ)


@pytest.mark.parametrize("seed", range(24))
def test_every_note_on_gets_one_note_off_with_origins_and_the_grid(arp_tool, seed):
    """The same, with the sequencer's notes beside the hand's, STOP, and the
    grid's runs and halts at any position: balanced, the same at any block
    size, nothing left of the sequencer's after a final STOP."""
    text = fuzz_script(1000 + seed, origins=True)
    base, summ = run(arp_tool, text, block=64, cap=4096)
    assert_balanced(base, summ)
    assert summ["dropped_ons"] == 0 and summ["deferred_offs"] == 0
    ev, _ = run(arp_tool, text, block=[1, 7, 500][seed % 3], cap=4096)
    assert ev == base
    for cap in (1, 64):
        ev, summ = run(arp_tool, text, block=[3, 64][seed % 2], cap=cap)
        assert_balanced(ev, summ)
    _, summ = run(arp_tool, text.replace("@60001 flush", "@60001 stop\n@60002 flush"), cap=4096)
    assert summ["held_seq"] == 0


def test_ledger_steals_the_oldest(arp_tool):
    """A whole-note chord at gate 200 % is still sounding when the rate drops
    to 1/32 and two more 16-key chords arrive: 48 notes for a 32-note ledger,
    so the oldest end early, each with its note-off."""
    a, b, c = list(range(30, 46)), list(range(50, 66)), list(range(70, 86))
    lines = ["@0 set mode chord", "@0 set gate 200", "@0 set rate 1/1", "@0 set sync 0", *chord(0, a),
             "@100 set rate 1/32", *release(200, a), *chord(200, b),
             *release(38500, b), *chord(38500, c), "@41000 flush"]
    ev, summ = run(arp_tool, script(*lines, ticks=410))
    assert_balanced(ev, summ)
    assert steps_of(ev)[:3] == [(0, a), (38400, b), (39600, c)]
    assert summ["stolen"] == 16 and summ["dropped_ons"] == 0
    stolen = [e for e in ev if e["kind"] == "off" and e["frame"] == 39600]
    assert [e["key"] for e in stolen] == a
