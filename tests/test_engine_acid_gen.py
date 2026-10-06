"""Acid Gen (engines/midi_fx/acid_gen.c; engines/midi_fx/README.md, "Acid
Gen"): TB-3PO, fm1-x0x's generator of 303 lines (Charles Vestal,
GPL-3.0-only; engines/third_party/fm1-x0x/seq), as a MIDI effect of engine
API v3, built only with the GPL switch on.

Against its source: the line it plays is the line TB-3PO writes for the same
settings (test/tb3po_line.c, built against the vendored file, and against
fm1-x0x's own when reference/fm1-x0x is cloned, which must agree), step for
step, played as fm1-x0x's sequencer plays a 303 part: a note holds half its
step, a slide holds into the next step whose note-on comes first and the
held note's note-off a tick later, a slide into the same note is a tie,
accents at velocity 118 and plain notes at 72, in every rate, direction,
octave range, key and mutation count.

The MIDI-effect contract (fm1_engine.h): the same output at host blocks of
1, 7, 64 and 448; every note-on gets one note-off; Start restarts the line,
Stop ends its notes, a bypass ends them at once. How it plays: a held key
starts it and sets its pitch, letting go stops it unless Latch is on; Keys =
Run plays it with the transport; Root and Scale can follow the project key.
No allocation, stdio or libm.
"""
import json
import shutil
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, ROOT, gpl_only, renderer  # noqa: F401
from tests.test_engine_midi_fx import BOUND, at, mfx_run, note

pytestmark = gpl_only

SEQ = ENGINES / "third_party" / "fm1-x0x" / "seq"
UPSTREAM_SEQ = ROOT / "reference" / "fm1-x0x" / "firmware" / "src" / "seq"
RATE_TICKS = {"1/16": 24, "1/16T": 16, "1/32": 12, "1/8T": 32}
TICK = RATE * 60 / (120 * 96)          # a tick at 120 BPM, in frames
NAMES = ["Density", "Accent", "Slide", "Octaves", "Root", "Scale", "Octave", "Keys", "Rate",
         "Length", "Direction", "Latch", "Seed", "Mutations", "Mut Every"]
ROOTS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SCALES = ["Minor", "Phrygian", "Harm Minor", "Min Pent", "Dorian", "Major"]


@pytest.fixture(scope="module")
def line_tool(tmp_path_factory):
    cc = shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("no C compiler")
    out = tmp_path_factory.mktemp("tb3po")
    tools = {}
    for name, d in (("vendored", SEQ), ("upstream", UPSTREAM_SEQ)):
        if not (d / "tb3po.c").is_file():
            continue
        exe = out / name
        subprocess.run([cc, "-std=c99", "-O2", "-I", str(d), str(ENGINES / "test" / "tb3po_line.c"),
                        str(d / "tb3po.c"), "-o", str(exe)], check=True)
        tools[name] = exe
    return tools


def tb3po(tool, seed=0xBEEF, density=70, accent=40, slide=25, octs=2, root=9, scale=0, base=1,
          length=16, muts=0):
    out = subprocess.run([str(tool), str(seed), str(density), str(accent), str(slide), str(octs),
                          str(root), str(scale), str(base), str(length), str(muts)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def expected(steps, ticks, rate_ticks, transpose=0, order=None):
    """The events fm1-x0x's sequencer would play for `steps`, from tick 0 for
    `ticks` ticks: (tick, kind, key, velocity)."""
    out, sounding, slides, gate, slide_off = [], None, False, -1, None
    order = order or (lambda i: i % len(steps))
    for t in range(ticks):
        if slide_off is not None:
            out.append((t, "off", slide_off, 0))
            slide_off = None
        if gate > 0:
            gate -= 1
            if gate == 0:
                out.append((t, "off", sounding, 0))
                sounding, slides, gate = None, False, -1
        if t % rate_ticks:
            continue
        st = steps[order(t // rate_ticks)]
        if not st["gate"]:
            if sounding is not None:
                out.append((t, "off", sounding, 0))
            sounding, slides, gate = None, False, -1
            continue
        key = max(0, min(127, st["note"] + transpose))
        vel = 118 if st["accent"] else 72
        if sounding is not None and slides:
            if key != sounding:
                out.append((t, "on", key, vel))
                slide_off, sounding = sounding, key
        else:
            if sounding is not None:
                out.append((t, "off", sounding, 0))
            out.append((t, "on", key, vel))
            sounding = key
        slides = bool(st["slide"])
        gate = -1 if slides else rate_ticks // 2
    return out


def played(events, first):
    """The log as (tick, kind, key, velocity), ticks counted from frame `first`."""
    return [(round((e["t"] - first) / TICK), e["k"], e["key"], e.get("vel", 0)) for e in events]


def run_gen(renderer, tmp_path, params=(), key=45, hold_s=4.0, seconds=None, extra=(), name="g"):
    args = ["--engine", "test-sine", "--mfx", "0:acid-gen", "--tempo", "120",
            "--seconds", str(seconds or hold_s + 0.5), *note(0, key, 100, int(hold_s * RATE))]
    for p in params:
        args += ["--mfx-param", f"0:{p}"]
    return mfx_run(renderer, tmp_path, args + list(extra), name)


@pytest.fixture(scope="module")
def listing(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True, text=True)
    return {e["id"]: e for e in json.loads(out.stdout)}


# ---- What it is ------------------------------------------------------------------------------

def test_it_lists_as_a_gpl_midi_effect(listing):
    e = listing["acid-gen"]
    assert (e["kind"], e["max_voices"], e["per_note"], e["pads"], e["name"]) == \
        ("midi_fx", 0, False, None, "Acid Gen")
    assert e["licence"] == "GPL-3.0-only AND MIT" and e["source"] == "engines/third_party/fm1-x0x"
    for who in ("Charles Vestal", "djphazer", "Phazerville", "TB-3PO"):
        assert who in e["credits"], who
    assert [p["name"] for p in e["params"]] == NAMES
    assert [p["page"] for p in e["params"]] == [0] * 4 + [1] * 4 + [2] * 4 + [3] * 3
    assert all(len(p["name"]) <= 10 for p in e["params"]), "a screen label holds 10 characters"
    params = {p["name"]: p for p in e["params"]}
    assert params["Root"]["names"] == ["Project"] + ROOTS
    assert params["Scale"]["names"] == ["Project"] + SCALES
    assert params["Rate"]["names"] == list(RATE_TICKS)


# ---- The line is TB-3PO's -------------------------------------------------------------------

def test_the_vendored_generator_is_upstreams(line_tool):
    if "upstream" not in line_tool:
        pytest.skip("reference/fm1-x0x is not cloned")
    for seed in (1, 0xBEEF, 12345, 65535):
        for setting in ({}, {"density": 100, "slide": 80, "octs": 3, "scale": 3, "length": 32, "muts": 7}):
            args = dict(seed=seed, **setting)
            assert tb3po(line_tool["vendored"], **args) == tb3po(line_tool["upstream"], **args)


SETTINGS = [
    ({}, {}),
    (["Density=100", "Slide=60", "Accent=70", "Octaves=2", "Root=3", "Scale=2", "Length=13",
      "Mutations=5", "Seed=777"],
     dict(density=100, slide=60, accent=70, octs=3, root=2, scale=1, length=13, muts=5, seed=777)),
    (["Density=45", "Slide=0", "Octaves=0", "Root=1", "Scale=6", "Octave=2", "Length=32", "Seed=4"],
     dict(density=45, slide=0, octs=1, root=0, scale=5, base=2, length=32, seed=4)),
]


@pytest.mark.parametrize("params,cfg", SETTINGS, ids=["defaults", "dense-slides", "major-32"])
def test_it_plays_tb3pos_line_as_x0x_plays_it(renderer, tmp_path, line_tool, params, cfg):
    """A key held for 4 s: the line, from step 1 at the first tick, in the
    key's pitch (the line's root note moves to the key), every step as
    fm1-x0x's sequencer plays a 303 part, through two or more passes."""
    steps = tb3po(line_tool["vendored"], **cfg)
    s, _, ev = run_gen(renderer, tmp_path, params, key=45)
    assert s["notes_hung"] == 0 and s["mfx_dropped"] == 0
    base = cfg.get("base", 1)
    own = 12 * (base + 1) + cfg.get("root", 9)
    got = played(ev, ev[0]["t"])
    ticks = got[-1][0] + 1
    want = expected(steps, ticks, 24, transpose=45 - own)
    # The key's release stops the line: compare what played before it.
    release = round((4.0 * RATE - ev[0]["t"]) / TICK)
    assert [g for g in got if g[0] < release] == [w for w in want if w[0] < release]
    assert any(w[2] for w in want if w[1] == "on")


@pytest.mark.parametrize("rate", list(RATE_TICKS))
def test_every_rate(renderer, tmp_path, line_tool, rate):
    steps = tb3po(line_tool["vendored"])
    _, _, ev = run_gen(renderer, tmp_path, [f"Rate={list(RATE_TICKS).index(rate)}"], hold_s=3.0)
    got = played(ev, ev[0]["t"])
    release = round((3.0 * RATE - ev[0]["t"]) / TICK)
    want = expected(steps, release, RATE_TICKS[rate], transpose=45 - 33)
    assert [g for g in got if g[0] < release] == want


@pytest.mark.parametrize("direction", ["Reverse", "Ping-Pong"])
def test_directions(renderer, tmp_path, line_tool, direction):
    steps = tb3po(line_tool["vendored"], length=8)
    n = len(steps)
    if direction == "Reverse":
        def order(i):
            return (n - 1 - i) % n
    else:
        cycle = list(range(n)) + list(range(n - 2, 0, -1))

        def order(i):
            return cycle[i % len(cycle)]
    _, _, ev = run_gen(renderer, tmp_path, ["Length=8", f"Direction={['Forward', 'Reverse', 'Ping-Pong'].index(direction)}"],
                       hold_s=3.0)
    got = played(ev, ev[0]["t"])
    release = round((3.0 * RATE - ev[0]["t"]) / TICK)
    assert [g for g in got if g[0] < release] == expected(steps, release, 24, transpose=12, order=order)


def test_mut_every_re_rolls_each_pass(renderer, tmp_path, line_tool):
    """Mut Every 1: the second pass is the line mutated once, the third
    twice, continuing the line's random stream (TB-3PO's own)."""
    _, _, ev = run_gen(renderer, tmp_path, ["Mut Every=1", "Length=8", "Density=100"], hold_s=3.5)
    got = played(ev, ev[0]["t"])
    for k in range(3):
        steps = tb3po(line_tool["vendored"], length=8, density=100, muts=k)
        want = [(t + 192 * k, kind, key, vel) for t, kind, key, vel in expected(steps, 192, 24, 12)]
        assert [g for g in got if 192 * k <= g[0] < 192 * (k + 1) and not (g[0] == 192 * k and g[1] == "off")] == \
            [w for w in want if not (w[0] == 192 * k and w[1] == "off")], k


# ---- The keys --------------------------------------------------------------------------------

def test_a_key_transposes_the_line(renderer, tmp_path):
    _, _, a = run_gen(renderer, tmp_path, key=45, name="a")
    _, _, b = run_gen(renderer, tmp_path, key=52, name="b")
    assert [(e["t"], e["k"], e["key"] + 7) for e in a] == [(e["t"], e["k"], e["key"]) for e in b]


@pytest.mark.parametrize("latch", [0, 1])
def test_letting_go_stops_unless_latched(renderer, tmp_path, latch):
    s, _, ev = run_gen(renderer, tmp_path, [f"Latch={latch}"], hold_s=1.0, seconds=3.0)
    after = [e for e in ev if e["t"] > 1.0 * RATE + 1]
    if latch:
        assert any(e["k"] == "on" for e in after)
    else:
        assert not [e for e in after if e["k"] == "on"]
    assert s["notes_hung"] == 0 or latch                # latched: the last note may still sound


def test_run_plays_with_the_transport(renderer, tmp_path, line_tool):
    """Keys = Run: nothing while stopped; from step 1 on the first tick after
    Start, in its own key with no key held; Stop ends the note at its frame."""
    play, stop = BOUND * 41, BOUND * 300
    script = (f"#! rate={RATE} block=64 tracks=8 end={BOUND * 340}\n@{play} play\n@{stop} stop\n")
    log = tmp_path / "seq.jsonl"
    s, _, ev = mfx_run(renderer, tmp_path, ["--engine", "test-sine", "--mfx", "0:acid-gen",
                                            "--mfx-param", "0:Keys=1", "--log-events", str(log)],
                       script=script)
    seq = [json.loads(line) for line in log.read_text().splitlines()]
    first_tick = min(e["frame"] for e in seq if e["kind"] == "clock" and e["frame"] >= play)
    assert ev and ev[0]["t"] == first_tick and all(e["t"] >= play for e in ev)
    assert all(e["t"] <= stop for e in ev) and s["notes_hung"] == 0
    steps = tb3po(line_tool["vendored"])
    got = played(ev, first_tick)
    end = round((stop - first_tick) / TICK)
    assert [g for g in got if g[0] < end] == expected(steps, end, 24, transpose=0)


def test_root_and_scale_can_follow_the_project_key(renderer, tmp_path):
    _, _, own = run_gen(renderer, tmp_path, ["Root=3", "Scale=1"], name="own")          # D minor
    _, _, proj = run_gen(renderer, tmp_path, ["Root=0", "Scale=0"], extra=["--key", "2:1"], name="proj")
    assert own == proj
    _, _, maj = run_gen(renderer, tmp_path, ["Root=0", "Scale=0"], extra=["--key", "2:0"], name="maj")
    _, _, dmaj = run_gen(renderer, tmp_path, ["Root=3", "Scale=6"], name="dmaj")       # D major
    assert maj == dmaj and maj != own


# ---- The contract ------------------------------------------------------------------------

def busy(block):
    return ["--engine", "acid-bass", "--mfx", "0:acid-gen", "--tempo", "137", "--frames", str(block),
            "--mfx-param", "0:Direction=3", "--mfx-param", "0:Mut Every=2",
            "--mfx-param", "0:Slide=60", "--mfx-param", "0:Rate=1",
            *note(BOUND * 3, 45, 100, BOUND * 90), *note(BOUND * 50, 50, 100, BOUND * 20),
            "--mfx-param-at", f"0:{at(BOUND * 70)}:Seed=99",
            "--mfx-param-at", f"0:{at(BOUND * 80)}:Latch=1",
            "--mfx-on-at", f"0:{at(BOUND * 150)}:0", "--mfx-on-at", f"0:{at(BOUND * 170)}:1",
            "--mfx-param-at", f"0:{at(BOUND * 175)}:Latch=0",
            *note(BOUND * 180, 40, 100, BOUND * 30), "--seconds", str(BOUND * 260 / RATE)]


def test_the_same_at_any_block_size(renderer, tmp_path):
    outs = set()
    for block in (1, 7, 64, 448):
        s, wav, ev = mfx_run(renderer, tmp_path, busy(block), f"b{block}")
        assert s["notes_hung"] == 0 and s["mfx_dropped"] == 0
        outs.add((wav, json.dumps(ev)))
    assert len(outs) == 1


def test_every_note_on_gets_one_note_off(renderer, tmp_path):
    """In the log, each key's note-offs follow its note-ons one for one; the
    note sounding when the bypass comes ends through the host's sink, not
    the log, and the sound is left with nothing hanging."""
    s, _, ev = mfx_run(renderer, tmp_path, busy(64))
    sounding, bypass, bypassed = {}, BOUND * 150, False
    for e in ev:
        if e["t"] > bypass and not bypassed:     # what sounded then ended in the sink
            sounding, bypassed = {}, True
        if e["k"] == "on":
            assert sounding.get(e["key"], 0) == 0, e        # never two at once on one key
            sounding[e["key"]] = 1
        else:
            assert sounding.get(e["key"], 0) == 1, e
            sounding[e["key"]] = 0
    assert not any(sounding.values()) and s["notes_hung"] == 0 and s["mfx_dropped"] == 0


def test_a_bypass_ends_the_note_at_once(renderer, tmp_path):
    cut = BOUND * 40
    s, _, ev = mfx_run(renderer, tmp_path, ["--engine", "test-sine", "--mfx", "0:acid-gen", "--tempo", "120",
                                            "--mfx-param", "0:Slide=100", "--mfx-param", "0:Density=100",
                                            *note(BOUND, 45, 100, BOUND * 100),
                                            "--mfx-on-at", f"0:{at(cut)}:0", "--seconds", "1.5"])
    assert all(e["t"] <= cut for e in ev) and ev[-1]["k"] == "off" and s["notes_hung"] == 0


def test_the_wrapper_and_generator_never_allocate_print_or_call_libm():
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    banned = {"malloc", "free", "calloc", "realloc", "printf", "fprintf", "puts", "putchar", "fopen"}
    banned |= {f + s for f in ("sin", "cos", "exp", "exp2", "log", "log2", "pow", "tanh") for s in ("", "f")}
    for obj in (ENGINES / "build" / "midi_fx" / "acid_gen.o",
                ENGINES / "build" / "gpl" / "fm1-x0x" / "seq" / "tb3po.o"):
        syms = subprocess.run([nm, "-u", str(obj)], check=True, capture_output=True, text=True).stdout
        names = {line.split()[-1].lstrip("_") for line in syms.splitlines() if line.strip()}
        assert not names & banned, (obj.name, names & banned)
