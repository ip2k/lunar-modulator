"""Crater Kit (engines/src/crater_kit.cc; engines/README.md, "Crater Kit"): a
16-pad kit after the TR-808 on fm1-x0x's 808 (Charles Vestal, GPL-3.0-only;
ported from 8W8 by athousanddetails; engines/third_party/fm1-x0x), built only
with the GPL switch on.

Against its sources: the vendored files are fm1-x0x's plus local.patch; the
patched kit gives fm1-x0x's own samples through upstream's API (both when
reference/ has the clones); fm1-x0x's own test of its 808 against 8W8's
engine passes with the vendored file (when reference/schwung-8W8 is cloned);
the engine is its vendored kit driven as fm1-x0x drives it, on a 16-sample
grid, bit for bit, at host blocks of 1, 7, 64 and 448 frames (fm1-crater-oracle
--twin); and each parameter reaches the kit as its law says (--fields).

How it plays: every pad sounds, cleanly, louder at the accent; notes outside
the pads and note-offs do nothing; a tom and its conga share a channel, while
the rim shot and claves, and the clap and maracas, do not; the hats choke as
Choke says; Tune is in semitones on every pad; velocity follows fm1-x0x's
law; Accent 0 plays every hit as the accent; the bend reaches the hits struck
while it is held; LATCH values wait for a hit, Dist for its pad's next one;
Level, Drive and Volume move a ringing hit. The output does not depend on the
host's block size or on what instance memory held; it is finite at every
extreme, has no subnormal sample, and the engine calls no libm; rates near
44.1 kHz only.
"""
import json
import math
import re
import shutil
import subprocess

import pytest

from tests.engine_helpers import (ENGINES, RATE, ROOT, cents, gpl_only, pitch_hz, render,  # noqa: F401
                                  renderer, rms)

pytestmark = gpl_only

ORACLE = ENGINES / "build" / "fm1-crater-oracle"
X0X = ROOT / "reference" / "fm1-x0x"
S303 = ROOT / "reference" / "schwung-303"
S8W8 = ROOT / "reference" / "schwung-8W8"
VENDOR = ENGINES / "third_party" / "fm1-x0x"
NAMES = ["Pad", "Tune", "Decay", "Level", "Tone", "Snap", "Drive", "Dist", "Accent", "Choke",
         "Volume"]
KICK, RIM, SNARE, CLAP, CLAVES, LOW_TOM, CLOSED_HH, LOW_CONGA, MARACAS, MID_TOM, OPEN_HH, \
    MID_CONGA, HIGH_TOM, CYMBAL, HIGH_CONGA, COWBELL = range(36, 52)


def run(renderer, tmp_path, name, params=(), notes=(), extra=(), seconds=1.0):
    """(summary, WAV bytes, left channel as floats)."""
    s, left, wav = render(renderer, tmp_path, "crater", params=list(params), notes=list(notes),
                          seconds=seconds, name=name, extra=list(extra))
    assert s["nonfinite"] == 0
    return s, wav.read_bytes(), left


def oracle(*args):
    out = subprocess.run([str(ORACLE), *args], capture_output=True, text=True)
    lines = [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
    return out.returncode, lines


def first_diff(a, b):
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)


def peak(x, t0=0.0, t1=None):
    seg = x[int(t0 * RATE):None if t1 is None else int(t1 * RATE)]
    return max(abs(v) for v in seg) if seg else 0.0


@pytest.fixture(scope="module")
def listing(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True, text=True)
    return {e["id"]: e for e in json.loads(out.stdout)}


# ---- What it is ------------------------------------------------------------------------------

def test_it_lists_as_a_gpl_pad_kit(listing):
    e = listing["crater"]
    assert (e["kind"], e["max_voices"], e["per_note"], e["pads"], e["name"]) == \
        ("sound", 13, False, {"first": 36, "count": 16}, "Crater Kit")
    assert e["licence"] == "GPL-3.0-only AND MIT" and e["source"] == "engines/third_party/fm1-x0x"
    for who in ("Charles Vestal", "8W8", "athousanddetails", "Werner, Abel and Smith", "sc808",
                "Yoshinosuke Horiuchi", "Sam Aaron", "TR-808"):
        assert who in e["credits"], who
    assert [p["name"] for p in e["params"]] == NAMES
    assert [p["page"] for p in e["params"]] == [0] * 4 + [1] * 4 + [2] * 3
    assert all(len(p["name"]) <= 12 for p in e["params"])
    params = {p["name"]: p for p in e["params"]}
    assert params["Pad"]["names"] == ["1 Kick", "2 Rim Shot", "3 Snare", "4 Clap", "5 Claves",
                                      "6 Low Tom", "7 Closed HH", "8 Low Conga", "9 Maracas",
                                      "10 Mid Tom", "11 Open HH", "12 Mid Conga", "13 High Tom",
                                      "14 Cymbal", "15 Hi Conga", "16 Cowbell"]
    assert all(len(n) <= 12 for n in params["Pad"]["names"])
    assert params["Dist"]["names"] == ["Diode", "Clip", "Sat", "Fuzz", "Cubic", "Fold", "Crush"]
    assert params["Choke"]["names"] == ["Off", "Closed>Open", "Both"]
    flags = {n: set(p["flags"]) for n, p in params.items()}
    assert {n for n, f in flags.items() if "smooth" in f} == {"Level", "Drive", "Volume"}
    assert {n for n, f in flags.items() if "latch" in f} == {"Tune", "Decay", "Tone", "Snap", "Dist",
                                                            "Accent", "Choke"}
    assert params["Tune"]["unit"] == "semi" and params["Accent"]["unit"] == "pct"
    # The first list is Pad, so ALGORITHM steps through the pads, as on Drums.
    assert next(p["name"] for p in e["params"] if p["type"] == 1) == "Pad"


# ---- Against its sources -------------------------------------------------------------------

def test_the_vendored_files_are_upstreams_plus_the_local_patch():
    if not (X0X / ".git").exists() or not (S303 / ".git").exists():
        pytest.skip("reference/fm1-x0x and reference/schwung-303 are not cloned")
    subprocess.run(["python3", str(VENDOR / "vendor.py"), str(X0X), str(S303), "--check"],
                   check=True, capture_output=True)


def cc():
    c = shutil.which("cc") or shutil.which("gcc")
    if not c:
        pytest.skip("no C compiler")
    return c


def test_the_patched_kit_gives_upstreams_samples(tmp_path):
    """drum808_drive.c, upstream's API only (integer pots, the switches, the
    sends, 256-frame calls at 44.1 kHz, four settings including every
    distortion and the mutual choke), built against fm1-x0x's own drum808.c
    and against ours: the same bytes, the dry bus and both sends."""
    src = X0X / "firmware" / "src" / "dsp"
    if not (src / "drum808.c").is_file():
        pytest.skip("reference/fm1-x0x is not cloned")
    outs = []
    for name, d in (("upstream", src), ("vendored", VENDOR / "dsp")):
        exe = tmp_path / name
        subprocess.run([cc(), "-std=c99", "-O2", "-ffp-contract=off", "-I", str(d),
                        str(ENGINES / "test" / "drum808_drive.c"), str(d / "drum808.c"), "-o", str(exe)],
                       check=True)
        outs.append(subprocess.run([str(exe)], check=True, capture_output=True).stdout)
    assert len(outs[0]) > 4 * 3 * 44100 * 4 * 4 and outs[0] == outs[1]


def test_fm1_x0xs_own_808_test_against_8w8_passes_with_the_vendored_kit(tmp_path):
    """fm1-x0x's tests/host/drum808_test.c (its run_drum808.sh) with our
    vendored, patched drum808.c: every sound and pot against 8W8's
    sc808_engine.cpp built from its sources in double, 436 cases, none over
    1e-3 of the reference's RMS. Built with fm1-x0x's warning flags."""
    ref = S8W8 / "src" / "dsp"
    test = X0X / "tests" / "host" / "drum808_test.c"
    if not (ref / "sc808_engine.cpp").is_file() or not test.is_file():
        pytest.skip("reference/schwung-8W8 or reference/fm1-x0x is not cloned")
    cxx = shutil.which("c++") or shutil.which("g++")
    if not cxx:
        pytest.skip("no C++ compiler")
    warn = ["-Wall", "-Wextra", "-Wdouble-promotion", "-Werror"]
    dsp = VENDOR / "dsp"
    subprocess.run([cxx, "-std=c++14", "-O2", "-ffp-contract=off", "-w", f"-I{ref}", "-c",
                    str(ref / "sc808_engine.cpp"), "-o", str(tmp_path / "ref.o")], check=True)
    subprocess.run([cc(), "-std=c99", "-O2", "-ffp-contract=off", *warn, "-DD8_TAIL_DB=0", f"-I{dsp}",
                    "-c", str(dsp / "drum808.c"), "-o", str(tmp_path / "port.o")], check=True)
    subprocess.run([cc(), "-std=c99", "-O2", "-ffp-contract=off", *warn, f"-I{dsp}", f"-I{ref}", "-c",
                    str(test), "-o", str(tmp_path / "test.o")], check=True)
    subprocess.run([cxx, "-o", str(tmp_path / "t"), str(tmp_path / "test.o"), str(tmp_path / "port.o"),
                    str(tmp_path / "ref.o"), "-lm"], check=True)
    out = subprocess.run([str(tmp_path / "t"), str(tmp_path / "demo.wav")], capture_output=True,
                         text=True, cwd=tmp_path)
    assert out.returncode == 0, out.stdout[-2000:]
    assert "436 cases, 0 over 1e-03" in out.stdout, out.stdout[-2000:]


@pytest.mark.parametrize("rate,block", [(44118, 1), (44118, 7), (44118, 64), (44118, 448),
                                        (44100, 64), (44100, 448)])
def test_the_engine_is_its_kit_on_a_16_sample_grid(renderer, rate, block):
    """fm1-crater-oracle --twin: five patterns (a groove, every pad from soft
    to accented, the toms and congas on their channels with the rim, claves,
    clap and maracas, settings on six pads with every distortion, and every
    pad on every 16th) through the engine and through a copy of its kit
    driven as fm1-x0x drives it, each hit on the chunk after its frame. No
    sample is subnormal; the subnormal floats the kit's running circuits
    carry while tails ring out are counted (R7 of the study: harmless on
    this desktop, unmeasured on pi32v2)."""
    code, lines = oracle("--twin", "--rate", str(rate), "--block", str(block))
    assert code == 0 and len(lines) == 5, lines
    for line in lines:
        assert line["differ"] == 0 and line["left_right_differ"] == 0, line
        assert line["nonfinite"] == 0 and line["subnormal_out"] == 0, line
        assert line["subnormal_running_max"] <= 16, line
        # every pad on every 16th, accented on the beats, sums past full scale
        # (the host's bus limiter is there for that); a groove stays near 0.4
        assert 0.1 < line["peak"] < (2.5 if line["pattern"] == "dense" else 0.9), line
        assert line["silent_at_end"] or line["pattern"] == "dense", line


def test_each_parameter_reaches_the_kit_by_its_law(renderer):
    """--fields: 8W8's pot (potx) and value (potv) for the pad's sound after
    set_param. Tune is semitones about the default on every pad, on 8W8's own
    laws (12 semitones a half-turn of the pot, 2 on the toms, the metal's
    ratio exponential); the relative knobs put 8W8's default pot at 0.5 and
    its ends at 0 and 1; Tone and Snap reach the kick's, the snare's and the
    maracas' own pots and nothing else; Drive is 0..10; Accent is the
    velocity depth and Choke the kit's switch."""
    code, rows = oracle("--fields")
    assert code == 0
    by = {(r["pad"], r["param"], r["value"]): r for r in rows}
    TUNE, DECAY, LEVEL, DRIVE, DIST, X1, X2 = 1, 2, 0, 3, 4, 7, 8
    base = by[(0, "", 0)]
    assert base["potx"][:5] == [64, 64, 87, 0, 0] and base["vel_depth"] == 1 and base["choke"] == 1
    # Tune: semitones relative to the default, on every family.
    d0 = base["potv"][TUNE]
    for st in (-12, 7, 12):
        assert by[(0, "Tune", st)]["potv"][TUNE] - d0 == pytest.approx(st, abs=1e-4)
    tom0 = 2.0 * (64 / 127) * 2 - 2.0             # 8W8's tom tune at pot 64: -2 + 4 x 64/127
    for st in (-12, 2, 12):
        assert by[(5, "Tune", st)]["potv"][TUNE] - tom0 == pytest.approx(st, abs=1e-4)
    cy0 = 0.5 * 4 ** (64 / 127)                   # the cymbal's ratio at pot 64
    assert 12 * math.log2(by[(13, "Tune", -12)]["potv"][TUNE] / cy0) == pytest.approx(-12, abs=1e-3)
    assert 12 * math.log2(by[(13, "Tune", 12)]["potv"][TUNE] / cy0) == pytest.approx(12, abs=1e-3)
    assert 12 * math.log2(by[(15, "Tune", 5)]["potv"][TUNE] / cy0) == pytest.approx(5, abs=1e-3)
    # Relative knobs: the default pot at 0.5, 0 and 127 at the ends, linear between.
    assert [by[(0, "Decay", u)]["potx"][DECAY] for u in (0, 0.25, 0.75, 1)] == [0, 43.5, 107, 127]
    assert by[(10, "Decay", 0.25)]["potx"][DECAY] == 37 and by[(10, "Decay", 1)]["potx"][DECAY] == 127
    assert by[(0, "Level", 0)]["potv"][LEVEL] == 0 and by[(0, "Level", 1)]["potv"][LEVEL] == 2
    assert by[(4, "Level", 0.25)]["potx"][LEVEL] == 32
    # Tone and Snap: the kick's tone (X1) and attack (X2), the snare's tone (X2)
    # and snappy (X1), the maracas' attack (X1); the closed hat has neither.
    assert by[(0, "Tone", 1)]["potx"][X1] == 127 and by[(0, "Tone", 0)]["potx"][X1] == 0
    assert by[(0, "Snap", 1)]["potx"][X2] == 127 and by[(2, "Tone", 0)]["potx"][X2] == 0
    assert by[(2, "Snap", 1)]["potx"][X1] == 127 and by[(8, "Snap", 1)]["potx"][X1] == 127
    assert by[(6, "Tone", 1)]["potx"] == by[(6, "Snap", 1)]["potx"] == \
        [64, 64, 47, 0, 0, 0, 0, 0, 0]
    assert by[(0, "Drive", 0.5)]["drive"] == 5 and by[(0, "Drive", 1)]["drive"] == 10
    assert by[(0, "Dist", 3)]["potx"][DIST] == 3 and by[(0, "Dist", 6)]["potx"][DIST] == 6
    assert by[(0, "Accent", 0)]["vel_depth"] == 0
    assert by[(0, "Accent", 50)]["vel_depth"] == pytest.approx(64 / 127)
    assert by[(0, "Choke", 0)]["choke"] == 0 and by[(0, "Choke", 2)]["choke"] == 2
    assert all(r["vol"] == pytest.approx(100 / 127) for r in rows)   # 8W8's kit level, untouched


# ---- How it plays ------------------------------------------------------------------------

def test_every_pad_sounds_cleanly_and_ends(renderer):
    """--pads: each pad alone at 88 and at 127. Every one sounds, well
    under full scale (the cowbell accented, the loudest, near 0.75), louder
    at the accent, and ends (the kit goes silent) within eight seconds: the
    cymbal, the longest, after about 1.7 s."""
    code, rows = oracle("--pads")
    assert code == 0 and len(rows) == 32
    by = {(r["key"], r["vel"]): r for r in rows}
    for key in range(36, 52):
        normal, accent = by[(key, 88)], by[(key, 127)]
        assert 0.05 < normal["peak"] < accent["peak"] < 0.9, (key, normal, accent)
        assert 0 < normal["ends_after"] < 8 * 44118 and 0 < accent["ends_after"] < 8 * 44118, key
    assert max(by.values(), key=lambda r: r["ends_after"])["key"] == CYMBAL


def test_notes_outside_the_pads_and_note_offs_do_nothing(renderer, tmp_path):
    _, silent, _ = run(renderer, tmp_path, "out", notes=["0:35:127:0.2", "0.1:52:127:0.2",
                                                         "0.2:60:127:0.2"], seconds=0.5)
    _, none, _ = run(renderer, tmp_path, "none", seconds=0.5)
    assert silent == none
    _, short, _ = run(renderer, tmp_path, "short", notes=[f"0:{CYMBAL}:100:0.05"], seconds=1.5)
    _, long_, _ = run(renderer, tmp_path, "long", notes=[f"0:{CYMBAL}:100:1.4"], seconds=1.5)
    assert short == long_, "a hit rings out whatever the note's length"


def test_a_tom_and_its_conga_share_a_channel(renderer, tmp_path):
    """The conga, struck while its tom rings, takes the tom's channel: the
    tom does not ring on beside it (the two together are far from the two
    apart, summed). The rim shot and the claves, and the clap and the
    maracas, each have a circuit of their own: struck together they are the
    two struck apart, summed."""
    _, _, tom = run(renderer, tmp_path, "tom", notes=[f"0:{LOW_TOM}:127:0.1"], seconds=0.8)
    _, _, both = run(renderer, tmp_path, "both", notes=[f"0:{LOW_TOM}:127:0.1",
                                                        f"0.2:{LOW_CONGA}:127:0.1"], seconds=0.8)
    _, _, conga = run(renderer, tmp_path, "conga", notes=[f"0.2:{LOW_CONGA}:127:0.1"], seconds=0.8)
    a, b = int(0.22 * RATE), int(0.5 * RATE)
    apart = [x - t - c for x, t, c in zip(both[a:b], tom[a:b], conga[a:b])]
    assert rms(tom, 0.22, 0.5) > 0.002
    assert math.sqrt(sum(v * v for v in apart) / len(apart)) > 0.7 * rms(tom, 0.22, 0.5)
    for one, other in ((RIM, CLAVES), (CLAP, MARACAS)):
        _, _, x = run(renderer, tmp_path, f"a{one}", notes=[f"0:{one}:110:0.1"], seconds=0.6)
        _, _, y = run(renderer, tmp_path, f"b{other}", notes=[f"0:{other}:110:0.1"], seconds=0.6)
        _, _, z = run(renderer, tmp_path, f"c{one}", notes=[f"0:{one}:110:0.1", f"0:{other}:110:0.1"],
                      seconds=0.6)
        assert max(abs(p + q - r) for p, q, r in zip(x, y, z)) < 3 / 32767, (one, other)


@pytest.mark.parametrize("choke,cuts_open,cuts_closed", [(0, False, False), (1, True, False),
                                                          (2, True, True)])
def test_the_hats_choke_as_choke_says(renderer, tmp_path, choke, cuts_open, cuts_closed):
    def level(first, then):
        _, _, x = run(renderer, tmp_path, f"c{choke}{first}{then}", [f"Choke={choke}", "Pad=6", "Decay=1"],
                      [f"0:{first}:127:0.1", f"0.1:{then}:1:0.1"], seconds=0.4)
        _, _, alone = run(renderer, tmp_path, f"a{choke}{first}", [f"Choke={choke}", "Pad=6", "Decay=1"],
                          [f"0:{first}:127:0.1"], seconds=0.4)
        return rms(x, 0.12, 0.2) / rms(alone, 0.12, 0.2)
    # the second hat struck at velocity 1, so its own sound is tiny
    assert (level(OPEN_HH, CLOSED_HH) < 0.2) == cuts_open
    assert (level(CLOSED_HH, OPEN_HH) < 0.2) == cuts_closed


def test_tune_is_in_semitones_on_every_pad(renderer, tmp_path):
    """The low tom (8W8's own range is 2 semitones; the law runs on) and the
    kick, an octave either way, measured after their pitch sweeps."""
    for pad, key, t0, t1 in ((5, LOW_TOM, 0.08, 0.4), (0, KICK, 0.15, 0.5)):
        def hz(tune):
            _, _, x = run(renderer, tmp_path, f"t{key}{tune}", [f"Pad={pad}", f"Tune={tune}", "Decay=1"],
                          [f"0:{key}:100:0.1"], seconds=0.6)
            return pitch_hz(x, t0, t1 - t0)
        f0 = hz(0)
        assert abs(cents(hz(12), 2 * f0)) < 25 and abs(cents(hz(-12), f0 / 2)) < 25, (key, f0)


def test_velocity_and_accent(renderer, tmp_path):
    """fm1-x0x's law: below 88 a hit is quieter in proportion (the kick at
    44 is half its 88), 127 is the accent, louder and harder; Accent 0 plays
    every hit as the accent."""
    def kick(vel, params=()):
        _, w, x = run(renderer, tmp_path, f"k{vel}{len(params)}", list(params), [f"0:{KICK}:{vel}:0.1"],
                      seconds=0.5)
        return w, x
    _, half = kick(44)
    _, normal = kick(88)
    _, accent = kick(127)
    assert peak(half) / peak(normal) == pytest.approx(0.5, abs=0.01)
    assert peak(accent) > 1.5 * peak(normal)
    flat88, _ = kick(88, ["Accent=0"])
    flat127, _ = kick(127, ["Accent=0"])
    assert flat88 == flat127


def test_the_bend_reaches_the_hits_struck_while_it_is_held(renderer, tmp_path):
    notes = [f"0:{LOW_TOM}:100:0.1", f"0.5:{LOW_TOM}:100:0.1"]
    _, _, plain = run(renderer, tmp_path, "nb", ["Pad=5", "Decay=1"], notes, seconds=0.9)
    _, _, bent = run(renderer, tmp_path, "b", ["Pad=5", "Decay=1"], notes, ["--bend", "0.2:12"],
                     seconds=0.9)
    assert first_diff(plain, bent) >= int(0.5 * RATE)          # the ringing hit keeps its pitch
    assert abs(cents(pitch_hz(bent, 0.58, 0.17), 2 * pitch_hz(plain, 0.58, 0.17))) < 25


def test_latch_values_wait_for_a_hit_and_dist_for_its_pads_next(renderer, tmp_path):
    """Decay and Tune turned while the kick rings change nothing until the
    next kick; Dist (with Drive up) likewise, though a snare struck between
    is another pad. Level and Drive move the ringing kick at once."""
    notes = [f"0:{KICK}:110:0.1", f"0.3:{SNARE}:110:0.1", f"0.6:{KICK}:110:0.1"]
    _, _, ref = run(renderer, tmp_path, "ref", ["Drive=0.5"], notes, seconds=1.0)
    for change in ("Decay=0.9", "Tune=5", "Dist=5"):
        _, _, x = run(renderer, tmp_path, "l", ["Drive=0.5"], notes, ["--param-at", f"0.1:{change}"],
                      seconds=1.0)
        i = first_diff(ref, x)
        assert i is not None and int(0.6 * RATE) <= i < int(0.601 * RATE), (change, i)
    for change in ("Level=0.8", "Drive=0.9"):
        _, _, x = run(renderer, tmp_path, "s", ["Drive=0.5"], notes, ["--param-at", f"0.1:{change}"],
                      seconds=1.0)
        i = first_diff(ref, x)
        assert i is not None and int(0.1 * RATE) <= i < int(0.101 * RATE), (change, i)


def test_a_change_while_silent_applies_at_once(renderer, tmp_path):
    notes = [f"0.3:{KICK}:110:0.1", f"0.3:{OPEN_HH}:110:0.1"]
    params = ["Pad=0", "Dist=3", "Drive=0.6", "Level=0.3", "Pad=10", "Decay=0.2", "Volume=0.4"]
    _, a, _ = run(renderer, tmp_path, "s0", params, notes, seconds=0.8)
    _, b, _ = run(renderer, tmp_path, "s1", [], notes,
                  [x for p in params for x in ("--param-at", f"0.1:{p}")], seconds=0.8)
    assert a == b


def test_per_pad_knobs_edit_only_the_focused_pad(renderer, tmp_path):
    notes = [f"0:{KICK}:110:0.1", f"0:{SNARE}:110:0.1"]
    _, _, ref = run(renderer, tmp_path, "r", [], notes, seconds=0.6)
    _, _, kick_only = run(renderer, tmp_path, "k", [], [notes[0]], seconds=0.6)
    _, _, x = run(renderer, tmp_path, "x", ["Pad=2", "Level=0"], notes, seconds=0.6)
    assert max(abs(p - q) for p, q in zip(x, kick_only)) < 2 / 32767   # the snare muted, the kick not
    assert ref != x


def test_volume(renderer, tmp_path):
    _, _, a = run(renderer, tmp_path, "v7", [], [f"0:{SNARE}:110:0.1"], seconds=0.4)
    _, _, b = run(renderer, tmp_path, "v35", ["Volume=0.35"], [f"0:{SNARE}:110:0.1"], seconds=0.4)
    _, _, z = run(renderer, tmp_path, "v0", ["Volume=0"], [f"0:{SNARE}:110:0.1"], seconds=0.4)
    assert abs(rms(b, 0.0, 0.2) / rms(a, 0.0, 0.2) - 0.25) < 0.01 and max(map(abs, z)) == 0


def at(k):
    """A time fm1-render applies at the block that starts at frame 448 k (a
    block boundary at 1, 7, 64 and 448 frames, just before it so rounding
    never pushes it a block later); 448 is no multiple of 16, so the events
    fall inside the engine's chunks."""
    return f"{(448 * k - 0.25) / RATE:.9f}"


def test_the_output_does_not_depend_on_the_host_block_or_memory(renderer, tmp_path):
    notes = [f"{at(k)}:{36 + (5 * k) % 16}:{60 + (7 * k) % 68}:0.05" for k in range(1, 90, 3)]
    extra = ["--param-at", f"{at(10)}:Pad=6", "--param-at", f"{at(10)}:Level=0.9",
             "--param-at", f"{at(20)}:Drive=0.4", "--param-at", f"{at(30)}:Dist=6",
             "--param-at", f"{at(40)}:Volume=0.5", "--param-at", f"{at(45)}:Choke=2",
             "--bend", f"{at(50)}:3", "--param-at", f"{at(60)}:Tune=-4"]
    outs = set()
    for frames in ("1", "7", "64", "448"):
        for fill in ("0x00", "0xFF", "0xA5"):
            if frames != "64" and fill != "0x00":
                continue
            _, w, _ = run(renderer, tmp_path, f"b{frames}{fill}", [], notes,
                          extra + ["--frames", frames, "--fill", fill], seconds=1.4)
            outs.add(w)
    assert len(outs) == 1


@pytest.mark.parametrize("rate,ok", [(44100, True), (44118, True), (44145, True), (48000, False),
                                     (43000, False), (22050, False)])
def test_rates_near_44_1_khz_only(renderer, tmp_path, rate, ok):
    """fm1-x0x's 808 is built for 44,100 Hz: the engine runs it at a host's
    rate near that (the FM-1's 44,118, fm1-x0x's device at about 44,145) and
    refuses others, as the Plaits engines refuse rates above theirs."""
    wav = tmp_path / "r.wav"
    res = subprocess.run([str(renderer), "--engine", "crater", "--rate", str(rate),
                          "--note", f"0:{LOW_TOM}:100:0.1", "--seconds", "0.5", "--out", str(wav)],
                         capture_output=True, text=True)
    assert (res.returncode == 0) == ok, res.stderr


@pytest.mark.parametrize("end", ["min", "max", "nan", "inf", "-inf"])
def test_every_parameter_at_an_extreme_renders_finite(renderer, tmp_path, listing, end):
    params = []
    for pad in (0, 2, 6, 10, 13, 15):
        params.append(f"Pad={pad}")
        for p in listing["crater"]["params"]:
            if p["name"] == "Pad":
                continue
            v = {"min": p["min"], "max": p["max"], "nan": "nan", "inf": "inf", "-inf": "-inf"}[end]
            params.append(f"{p['name']}={v}")
    notes = [f"{0.05 * k:.2f}:{36 + k}:127:0.1" for k in range(16)]
    s, _, _ = run(renderer, tmp_path, end, params, notes, ["--bend", "0.3:48"], seconds=1.5)
    assert s["nonfinite"] == 0 and s["raw_peak"] < 8


def test_instance_size_and_cost(renderer, tmp_path):
    """The dense case (every pad on every 16th at 125 BPM, accents on the
    beats) far under real time; the instance a few kilobytes."""
    step = 60 / 125 / 4
    notes = [f"{i * step:.6f}:{key}:{127 if i % 4 == 0 else 88}:0.05"
             for i in range(16) for key in range(36, 52)]
    s, _, _ = run(renderer, tmp_path, "dense", [], notes, seconds=2.0)
    assert s["instance_bytes"] <= 6144
    assert s["ns_per_block"] < 64 / 44118 * 1e9 / 20


def test_no_transcendental_libm_calls():
    """No sinf, expf and the like in the wrapper or the vendored kit, so the
    browser's module renders the same samples as the native build."""
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    banned = {f + s for f in ("sin", "cos", "tan", "exp", "exp2", "log", "log2", "log10", "pow",
                               "tanh", "atan", "atan2", "sinh", "cosh", "sqrt", "expm1") for s in ("", "f")}
    for obj in (ENGINES / "build" / "our" / "src" / "crater_kit.o",
                ENGINES / "build" / "gpl" / "fm1-x0x" / "dsp" / "drum808.o"):
        syms = subprocess.run([nm, "-u", str(obj)], check=True, capture_output=True, text=True).stdout
        names = {line.split()[-1].lstrip("_") for line in syms.splitlines() if line.strip()}
        assert not names & banned, (obj.name, names & banned)
        assert not names & {"malloc", "free", "calloc", "realloc", "printf", "fprintf", "puts"}, obj.name


# A symbol table line of `objdump -t` (GNU objdump on ELF, llvm-objdump on
# Mach-O): value, seven flag columns, section, (ELF) size, name.
OBJDUMP_SYM = re.compile(r"^[0-9a-fA-F]+ (?P<flags>.{7}) (?P<section>\S+)\s+(?:[0-9a-fA-F]+\s+)?(?P<name>\S+)$")


def writable_section(section):
    """Whether a symbol's section is data a program may write: .data, .bss
    and common on ELF, __DATA's __data, __bss and __common on Mach-O. Read-only
    data with relocations (a table of string pointers) is not: ELF puts it in
    .data.rel.ro, which nm marks d like .data, and Mach-O in __DATA,__const."""
    if section.startswith(".data.rel.ro"):
        return False
    if section in (".data", ".bss", ".sdata", ".sbss", "*COM*") or section.startswith((".data.", ".bss.")):
        return True
    return section in ("__DATA,__data", "__DATA,__bss", "__DATA,__common")


def writable_symbols(obj):
    """The data symbols of obj in writable sections, by `objdump -t`."""
    out = subprocess.run(["objdump", "-t", str(obj)], check=True, capture_output=True, text=True).stdout
    names = []
    for line in out.splitlines():
        m = OBJDUMP_SYM.match(line.strip())
        if m and "O" in m["flags"] and writable_section(m["section"]):
            names.append(m["name"])
    return names


def test_writable_section_classes():
    assert writable_section(".data") and writable_section(".bss") and writable_section("__DATA,__data")
    assert writable_section(".bss.drum808_quiet") and writable_section("*COM*")
    assert not writable_section(".data.rel.ro.local") and not writable_section("__DATA,__const")
    assert not writable_section(".rodata") and not writable_section("__TEXT,__const")
    m = OBJDUMP_SYM.match("0000000000000000 l     O .data.rel.ro.local\t0000000000000018 k_choke_names")
    assert m and m["section"] == ".data.rel.ro.local" and m["name"] == "k_choke_names"
    m = OBJDUMP_SYM.match("0000000000009270 l     O __DATA,__const _k_choke_names")
    assert m and m["section"] == "__DATA,__const" and m["name"] == "_k_choke_names"
    m = OBJDUMP_SYM.match("0000000000000004 g     O .data\t0000000000000004 drum808_quiet")
    assert m and writable_section(m["section"]) and m["name"] == "drum808_quiet"


def test_no_writable_global_in_the_vendored_kit():
    """fm1-x0x's silence threshold was a global its overload guard moves;
    here it is a constant (local.patch), so no two instances share state.
    No data symbol the vendored file defines is in a writable section
    (`objdump -t`: nm's letters cannot tell .data from .data.rel.ro on
    ELF, where a static const table of string pointers lives)."""
    if not shutil.which("objdump"):
        pytest.skip("no objdump")
    obj = ENGINES / "build" / "gpl" / "fm1-x0x" / "dsp" / "drum808.o"
    source = (VENDOR / "dsp" / "drum808.c").read_text()
    # a sanitizer build adds data of its own: only names the source defines count
    ours = [n for n in writable_symbols(obj)
            if re.search(r"\b%s\b" % re.escape(n[1:] if n.startswith("_") else n), source)]
    assert ours == [], ours
