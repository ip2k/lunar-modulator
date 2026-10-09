"""Comet Kit (engines/src/comet_kit.cc; engines/README.md, "Comet Kit"): a
16-pad kit after the TR-909 on fm1-x0x's 909 kit (Charles Vestal,
GPL-3.0-only; engines/third_party/fm1-x0x), built only with the GPL switch on.

Against its sources: the vendored files are fm1-x0x's plus local.patch and
the generated headers its own script writes (when reference/ has the
clones); the generated headers are what the vendored script writes from the
vendored recordings (always); the patched kit gives fm1-x0x's own samples at
44.1 kHz; the engine is its vendored unit driven as fm1-x0x drives it, with
9W9's integer pots set at each hit, on a 16-sample grid, bit for bit, at
host blocks of 1, 7, 64 and 448 frames and at three rates (fm1-comet-oracle
--twin); and each knob of each pad reaches its voice as 9W9's pot curves
say (--fields).

How it plays: every pad of both kits sounds, cleanly and under full scale;
notes outside 36-51 and note-offs do nothing; the six toms rise with their
keys; the closed and pedal hats choke the open one and nothing else;
velocity, Velocity, Accent, Volume and the per-pad knobs act, a knob only on
its pad; Kit and Drive Type are read when a pad is struck; SMOOTH knobs
reach a sounding pad; the kick's Tone moves its pitch once Sweep is up. The
output does not depend on the host's block size or on what instance memory
held; it is finite at every extreme, has no subnormal sample and leaves none
in the unit's state, returns to zero, and the engine calls no libm.
"""
import cmath
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.engine_helpers import (ENGINES, RATE, ROOT, cents, gpl_only, render,  # noqa: F401
                                  renderer, rms)

pytestmark = gpl_only

ORACLE = ENGINES / "build" / "fm1-comet-oracle"
X0X = ROOT / "reference" / "fm1-x0x"
S303 = ROOT / "reference" / "schwung-303"
VENDOR = ENGINES / "third_party" / "fm1-x0x"
NAMES = ["Pad", "Tune", "Decay", "Level", "Tone", "Snap", "Sweep", "Drive", "Drive Type",
         "Accent", "Velocity", "Volume", "Kit"]
KICK, RIM, SNARE, CLAP, SNARE2, LOW_TOM, CLOSED_HH, FLOOR_TOM, PEDAL_HH, MID_TOM, OPEN_HH, \
    LOW_MID, HIGH_MID, CRASH, HIGH_TOM, RIDE = range(36, 52)
TOMS = [LOW_TOM, FLOOR_TOM, MID_TOM, LOW_MID, HIGH_MID, HIGH_TOM]

# 9W9's panel, as fm1-x0x ports it (third_party/fm1-x0x/dsp/drum909.c,
# d9_*_p): per voice, its pots by name: (curve, lo, hi, default pot).
LIN, EXP = "lin", "exp"
DRIVE = (EXP, 0.85, 12.0)
POTS = {
    "bd": {"Tune": (LIN, 6, 32, 34), "Attack": (LIN, 0, 1, 13), "Decay": (EXP, 100, 4000, 90),
           "Level": (LIN, 0, 1.35, 94), "P.Dpth": (LIN, 0, 1, 0), "Pitch": (EXP, 0.43, 4.7, 45),
           "Drive": DRIVE + (0,)},
    "sd": {"Tune": (EXP, 130, 320, 64), "Tone": (EXP, 300, 4000, 68), "Snappy": (LIN, 0, 1, 64),
           "Level": (LIN, 0, 1.35, 58), "Drive": DRIVE + (36,)},
    "lt": {"Tune": (EXP, 50, 90, 66), "Decay": (EXP, 80, 2600, 111), "Level": (LIN, 0, 1.35, 52),
           "Attack": (LIN, 0, 1, 23), "Drive": DRIVE + (41,)},
    "mt": {"Tune": (EXP, 80, 125, 69), "Decay": (EXP, 70, 2200, 100), "Level": (LIN, 0, 1.35, 52),
           "Attack": (LIN, 0, 1, 23), "Drive": DRIVE + (41,)},
    "ht": {"Tune": (EXP, 110, 170, 53), "Decay": (EXP, 60, 2000, 105), "Level": (LIN, 0, 1.35, 52),
           "Attack": (LIN, 0, 1, 23), "Drive": DRIVE + (41,)},
    "rs": {"Level": (LIN, 0, 1.35, 103), "Tune": (EXP, 150, 300, 62), "Drive": DRIVE + (24,)},
    "cp": {"Level": (LIN, 0, 1.35, 122), "Tune": (EXP, 650, 1400, 63), "Tail": (EXP, 120, 1000, 63),
           "Drive": DRIVE + (30,)},
    "ch": {"Decay": (EXP, 15, 300, 84), "Level": (LIN, 0, 1.35, 89), "Tune": (EXP, 0.25, 4, 64),
           "Drive": DRIVE + (0,)},
    "oh": {"Decay": (EXP, 20, 1200, 97), "Level": (LIN, 0, 1.35, 80), "Tune": (EXP, 0.25, 4, 64),
           "Drive": DRIVE + (0,)},
    "cr": {"Tune": (EXP, 0.25, 4, 64), "Level": (LIN, 0, 1.35, 47), "Decay": (EXP, 100, 3000, 108),
           "Drive": DRIVE + (0,)},
    "rd": {"Tune": (EXP, 0.25, 4, 64), "Level": (LIN, 0, 1.35, 42), "Decay": (EXP, 100, 3000, 108),
           "Drive": DRIVE + (0,)},
}
VOICES = ["bd", "sd", "lt", "mt", "ht", "rs", "cp", "ch", "oh", "cr", "rd"]
PAD_VOICE = ["bd", "rs", "sd", "cp", "sd", "lt", "ch", "lt", "ch", "mt", "oh", "mt", "ht", "cr",
             "ht", "rd"]
# Our knobs on 9W9's pots (engines/README.md, "Comet Kit").
KNOB_POTS = {"Tune": ["Tune"], "Decay": ["Decay", "Tail"], "Level": ["Level"],
             "Tone": ["Tone", "Pitch"], "Snap": ["Attack", "Snappy"], "Sweep": ["P.Dpth"],
             "Drive": ["Drive"]}
# The oracle's names for the unit's fields, by 9W9 pot and voice kind.
FIELD = {"Tune": "tune", "Decay": "decay", "Tail": "tail_decay", "Level": "level", "Tone": "noise_decay",
         "Pitch": "pitch_mod", "Attack": "attack", "Snappy": "snappy", "P.Dpth": "sweep_depth",
         "Drive": "drive"}
SMP_FIELD = {"Tune": "pitch", "Decay": "decay", "Level": "volume", "Drive": "drive"}
# Where a pad's voicing differs from 9W9's panel: (kit or None, pad, knob) -> pot.
VOICING = {(None, 4, "Tune"): 80, (None, 4, "Tone"): 90, (None, 4, "Snap"): 96,
           (None, 7, "Tune"): 104, (None, 8, "Decay"): 100, (None, 11, "Tune"): 101,
           (None, 12, "Tune"): 19,
           (1, 0, "Level"): 61, (1, 0, "Decay"): 80, (1, 0, "Drive"): 30, (1, 10, "Level"): 60}


def run(renderer, tmp_path, name, params=(), notes=(), extra=(), seconds=1.0):
    """(summary, WAV bytes, left channel as floats)."""
    s, left, wav = render(renderer, tmp_path, "comet", params=list(params), notes=list(notes),
                          seconds=seconds, name=name, extra=list(extra))
    assert s["nonfinite"] == 0
    return s, wav.read_bytes(), left


def oracle(*args):
    out = subprocess.run([str(ORACLE), *args], capture_output=True, text=True)
    lines = [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
    return out.returncode, lines


def peak(x, t0=0.0, t1=None):
    seg = x[int(t0 * RATE):None if t1 is None else int(t1 * RATE)]
    return max((abs(v) for v in seg), default=0.0)


def zc_hz(x, t0, t1):
    """Rising zero crossings per second over [t0, t1)."""
    seg = x[int(t0 * RATE):int(t1 * RATE)]
    c = [i for i in range(1, len(seg)) if seg[i - 1] < 0 <= seg[i]]
    assert len(c) > 2, "no periodic signal"
    return (len(c) - 1) * RATE / (c[-1] - c[0])


@pytest.fixture(scope="module")
def listing(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True, text=True)
    return {e["id"]: e for e in json.loads(out.stdout)}


# ---- What it is ------------------------------------------------------------------------------

def test_it_lists_as_a_gpl_eleven_voice_pad_kit(listing):
    e = listing["comet"]
    assert (e["kind"], e["max_voices"], e["per_note"], e["name"]) == ("sound", 11, False, "Comet Kit")
    assert e["pads"] == {"first": 36, "count": 16}
    assert e["licence"] == "GPL-3.0-only AND MIT" and e["source"] == "engines/third_party/fm1-x0x"
    for who in ("Charles Vestal", "athousanddetails", "Matthew Cieplak", "ER-99", "9W9", "TR-909"):
        assert who in e["credits"], who
    assert [p["name"] for p in e["params"]] == NAMES
    assert [p["page"] for p in e["params"]] == [0] * 4 + [1] * 4 + [2] * 4 + [3]
    assert all(len(p["name"]) <= 12 and len(p["abbr"]) <= 6 for p in e["params"])
    flags = {p["name"]: set(p["flags"]) for p in e["params"]}
    assert flags["Pad"] == {"focus"}                       # the edit focus: lockable, no MOD
    # Engine API v4: each pad keeps its own sound (PER_FOCUS), read back by
    # get_param, so a saved kit holds all sixteen pads.
    for n in ("Tune", "Decay", "Level", "Tone", "Snap", "Sweep", "Drive"):
        assert flags[n] == {"smooth", "mod", "per_focus"}, n
    assert flags["Volume"] == {"smooth", "mod"}
    assert flags["Drive Type"] == {"latch", "mod", "per_focus"}
    for n in ("Accent", "Velocity", "Kit"):
        assert flags[n] == {"latch", "mod"}, n
    assert e["get_param"]
    assert e["params"][0]["names"][0] == "1 Kick" and len(e["params"][0]["names"]) == 16
    assert e["params"][8]["names"] == ["Diode", "Clip", "Saturate", "Fuzz", "Crunch", "Fold",
                                            "Crush"]
    assert e["params"][12]["names"] == ["Classic", "Big Beat"]


# ---- Against its sources -------------------------------------------------------------------

def test_the_vendored_files_are_upstreams_plus_the_local_patch():
    if not (X0X / ".git").exists() or not (S303 / ".git").exists():
        pytest.skip("reference/fm1-x0x and reference/schwung-303 are not cloned")
    subprocess.run(["python3", str(VENDOR / "vendor.py"), str(X0X), str(S303), "--check"],
                   check=True, capture_output=True)


def test_the_generated_headers_are_the_vendored_scripts_output(tmp_path):
    """gen/ is committed so no build needs Python; it is what the vendored
    tools/gen_drum_samples.py writes from the vendored recordings, byte for
    byte (the same on macOS, musl and glibc Pythons, UPSTREAM.md)."""
    out = tmp_path / "x0x_drum_samples.h"
    subprocess.run(["python3", str(VENDOR / "tools" / "gen_drum_samples.py"), str(out)],
                   check=True, capture_output=True)
    for name in ("x0x_drum_samples.h", "x0x_drum_tables.h"):
        assert (tmp_path / name).read_bytes() == (VENDOR / "gen" / name).read_bytes(), name


@pytest.fixture(scope="module")
def int16_gen(tmp_path_factory):
    """The cymbals as fm1-x0x writes them, int16: the vendored script with
    --int16 (UPSTREAM.md, local change 7), in a directory of their own."""
    out = tmp_path_factory.mktemp("int16") / "x0x_drum_samples.h"
    subprocess.run(["python3", str(VENDOR / "tools" / "gen_drum_samples.py"), "--int16", str(out)],
                   check=True, capture_output=True)
    return out.parent


def build_cymbals(tmp_path, name, *flags):
    cc = shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("no C compiler")
    exe = tmp_path / name
    subprocess.run([cc, "-std=c99", "-O2", "-ffp-contract=off", "-w", *flags, "-I", str(VENDOR / "dsp"),
                    "-I", str(VENDOR / "gen"), str(ENGINES / "test" / "drum909_cymbals.c"),
                    str(VENDOR / "dsp" / "drum909.c"), "-o", str(exe)], check=True)
    return exe


def test_the_patched_kit_gives_upstreams_samples(tmp_path, int16_gen):
    """drum909_drive.c, upstream's API only (integer pots, 256- and 37-frame
    calls at 44.1 kHz; the panel's defaults, every pot moved, every
    distortion type, soft hits under Accent and Velocity), built against
    fm1-x0x's own drum909.c and against ours, both reading upstream's int16
    cymbals (X0X_SMP_INT16; the kit plays them as 8-bit mu-law): the same
    bytes."""
    src = X0X / "firmware" / "src" / "dsp"
    if not (src / "drum909.c").is_file():
        pytest.skip("reference/fm1-x0x is not cloned")
    cc = shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("no C compiler")
    outs = []
    for name, d in (("upstream", src), ("vendored", VENDOR / "dsp")):
        exe = tmp_path / name
        subprocess.run([cc, "-std=c99", "-O2", "-ffp-contract=off", "-w", "-DX0X_SMP_INT16", "-I", str(d),
                        "-I", str(int16_gen), "-I", str(VENDOR / "gen"),
                        str(ENGINES / "test" / "drum909_drive.c"), str(d / "drum909.c"), "-o", str(exe)],
                       check=True)
        outs.append(subprocess.run([str(exe)], check=True, capture_output=True).stdout)
    assert len(outs[0]) > 4 * 44100 * 30 and outs[0] == outs[1]


@pytest.mark.parametrize("rate,block", [(44118, 1), (44118, 7), (44118, 64), (44118, 448),
                                        (44100, 64), (44100, 448), (48000, 64), (48000, 448)])
def test_the_engine_is_its_unit_on_a_16_sample_grid(renderer, rate, block):
    """fm1-comet-oracle --twin: six lines (every pad with accents, soft hits
    and the hats choking; the Big Beat kit; every drive type at full drive;
    every knob at an end; the kit's Accent, Velocity and Volume; rolls inside
    a chunk) through the engine and through a copy of its unit driven as
    fm1-x0x drives it, with 9W9's integer pots set at each hit and each hit
    on the chunk after its frame. No sample is subnormal, nor any float of
    the engine's unit after a render call; the default kit's lines stay
    under full scale."""
    code, lines = oracle("--twin", "--rate", str(rate), "--block", str(block))
    assert code == 0 and len(lines) == 6, lines
    for line in lines:
        assert line["differ"] == 0 and line["left_right_differ"] == 0, line
        assert line["nonfinite"] == 0 and line["subnormal_out"] == 0, line
        assert line["subnormal_state_max"] == 0, line
        assert line["peak"] > 0.2, line
        if line["line"] in ("defaults", "big-beat", "rolls"):
            assert line["peak"] < 1.0, line


def pot_value(spec, x):
    """9W9's pot curve at pot x (0..127, a float): LIN linear, EXP its table
    at the integers and linear between them, as drum909_set_value reads it."""
    curve, lo, hi = spec[:3]
    if curve == LIN:
        return lo + (hi - lo) * x / 127
    k = int(x)
    at = [lo * (hi / lo) ** (n / 127) for n in (k, min(k + 1, 127))]
    return at[0] + (at[1] - at[0]) * (x - k)


def expected_pot(knob, u, at):
    if knob in ("Sweep", "Drive"):
        return at + (127 - at) * u
    return at * 2 * u if u < 0.5 else at + (127 - at) * (2 * u - 1)


def test_each_knob_reaches_its_voice_on_9w9s_curves(renderer):
    """--fields: every knob of every pad of both kits at 0, 0.25, 0.5, 0.75
    and 1, with the pad struck: the unit's value on the pad's voice is 9W9's
    pot curve at the pot the knob names (0.5: the pad's voicing; Sweep and
    Drive 0: the voicing), and the other pots stay at the voicing. Drive
    Type is 9W9's switch. Accent and Velocity reach the kit."""
    code, rows = oracle("--fields", "--rate", "44100")
    assert code == 0
    seen = 0
    for r in rows:
        if "kit_accent" in r:
            assert r["accent"] == pytest.approx(r["kit_accent"], rel=1e-5)
            assert r["vel_depth"] == pytest.approx(r["kit_velocity"] / 100, abs=1e-5)
            continue
        voice, pad, kit, knob, u = PAD_VOICE[r["pad"]], r["pad"], r["kit"], r["knob"], r["value"]
        assert VOICES[r["voice"]] == voice
        pots = POTS[voice]
        fields = SMP_FIELD if voice in ("ch", "oh", "cr", "rd") else FIELD
        if knob == "Drive Type":
            assert r["dist"] == int(u)
            continue
        for k, names in KNOB_POTS.items():
            for pot in names:
                if pot not in pots:
                    continue
                at = VOICING.get((kit, pad, k), VOICING.get((None, pad, k), pots[pot][3]))
                x = expected_pot(k, u, at) if k == knob else at
                want = pot_value(pots[pot], x)
                got = r[fields[pot]]
                assert got == pytest.approx(want, rel=2e-5, abs=1e-6), (r, pot, want)
                seen += 1
    assert seen > 2000


# ---- How it plays ----------------------------------------------------------------------------

@pytest.mark.parametrize("kit", [0, 1])
def test_every_pad_of_both_kits_sounds_cleanly(renderer, tmp_path, kit):
    for key in range(36, 52):
        s, _, x = run(renderer, tmp_path, f"k{kit}p{key}", [f"Kit={kit}"], [f"0:{key}:127:0.1"],
                      seconds=0.6)
        assert 0.1 < s["raw_peak"] < 0.75, (key, s["raw_peak"])
        assert s["raw_clipped"] == 0


def test_notes_outside_the_pads_and_note_offs_do_nothing(renderer, tmp_path):
    s, _, x = run(renderer, tmp_path, "out", [], ["0:35:127:0.1", "0:52:127:0.1", "0.1:60:127:0.1"],
                  seconds=0.4)
    assert peak(x) == 0
    _, a, _ = run(renderer, tmp_path, "short", [], [f"0:{OPEN_HH}:127:0.01"], seconds=0.8)
    _, b, _ = run(renderer, tmp_path, "long", [], [f"0:{OPEN_HH}:127:0.6"], seconds=0.8)
    assert a == b                                  # the hit rings for its decay


def test_the_toms_rise_with_their_keys_inside_9w9s_ranges(renderer, tmp_path):
    """After their 160-200 ms sweeps the six toms sit at their tunes: 9W9's
    low, mid and high toms on 41, 45 and 50, and ours between them."""
    want = [67.9, 80.9, 102.0, 114.1, 117.4, 131.9]
    got = []
    for key, hz in zip(TOMS, want):
        _, _, x = run(renderer, tmp_path, f"t{key}", [], [f"0:{key}:127:0.1"], seconds=0.7)
        f = zc_hz(x, 0.35, 0.6)
        assert abs(cents(f, hz)) < 25, (key, f, hz)
        got.append(f)
    assert got == sorted(got)


def test_the_closed_and_pedal_hats_choke_the_open_one(renderer, tmp_path):
    """A closed or pedal hat at 50 ms fades the open hat out within 3 ms (one
    pair of cymbals, as on the machine): afterwards the two together are the
    closed hat alone. The crash rings on under a closed hat."""
    _, _, alone = run(renderer, tmp_path, "oh", [], [f"0:{OPEN_HH}:127:0.1"], seconds=0.4)
    assert rms(alone, 0.06, 0.2) > 0.003
    for cutter in (CLOSED_HH, PEDAL_HH):
        _, _, cut = run(renderer, tmp_path, f"c{cutter}", [],
                        [f"0:{OPEN_HH}:127:0.1", f"0.05:{cutter}:127:0.1"], seconds=0.4)
        _, _, solo = run(renderer, tmp_path, f"s{cutter}", [], [f"0.05:{cutter}:127:0.1"], seconds=0.4)
        diff = [a - b for a, b in zip(cut, solo)]
        assert rms(diff, 0.06, 0.4) < 0.01 * rms(alone, 0.06, 0.4)
    _, _, cr = run(renderer, tmp_path, "cr", [], [f"0:{CRASH}:127:0.1"], seconds=0.6)
    _, _, both = run(renderer, tmp_path, "crch", [], [f"0:{CRASH}:127:0.1", f"0.05:{CLOSED_HH}:127:0.1"],
                     seconds=0.6)
    assert rms(both, 0.4, 0.5) == pytest.approx(rms(cr, 0.4, 0.5), rel=1e-3)


def test_velocity_velocity_depth_and_accent(renderer, tmp_path):
    loud = run(renderer, tmp_path, "v127", [], [f"0:{KICK}:127:0.1"], seconds=0.3)[0]["raw_peak"]
    soft = run(renderer, tmp_path, "v64", [], [f"0:{KICK}:64:0.1"], seconds=0.3)[0]["raw_peak"]
    assert soft / loud == pytest.approx(64 / 127, rel=0.02)        # Velocity 100 %: gain = vel
    flat = run(renderer, tmp_path, "flat", ["Velocity=0"], [f"0:{KICK}:64:0.1"], seconds=0.3)[0]
    assert flat["raw_peak"] == pytest.approx(loud, rel=1e-6)       # Velocity 0: every hit at Accent
    hot = run(renderer, tmp_path, "acc", ["Accent=4"], [f"0:{KICK}:127:0.1"], seconds=0.3)[0]
    assert hot["raw_peak"] > 1.5 * loud


def test_volume_is_a_square_law_about_0_7(renderer, tmp_path):
    _, _, a = run(renderer, tmp_path, "v07", [], [f"0:{SNARE}:127:0.1"], seconds=0.3)
    _, _, b = run(renderer, tmp_path, "v035", ["Volume=0.35"], [f"0:{SNARE}:127:0.1"], seconds=0.3)
    assert peak(b) == pytest.approx(0.25 * peak(a), rel=2e-3)


def test_a_knob_edits_only_the_focused_pad(renderer, tmp_path):
    _, _, alone = run(renderer, tmp_path, "alone", [], [f"0.3:{SNARE}:127:0.1"], seconds=0.6)
    _, _, y = run(renderer, tmp_path, "mute", ["Pad=0", "Level=0"],
                  [f"0:{KICK}:127:0.1", f"0.3:{SNARE}:127:0.1"], seconds=0.6)
    assert peak(y, 0, 0.29) == 0 and y == alone       # the kick silent, the snare untouched
    # The second snare is its own pad on the snare's voice: higher, and
    # striking the first snare again plays the first snare's voicing.
    _, _, s1 = run(renderer, tmp_path, "s1", [], [f"0:{SNARE}:127:0.1"], seconds=0.4)
    _, _, s2 = run(renderer, tmp_path, "s2", [], [f"0:{SNARE2}:127:0.1"], seconds=0.4)
    assert s1 != s2
    _, _, s3 = run(renderer, tmp_path, "s3", ["Pad=4", "Level=0"],
                   [f"0:{SNARE2}:127:0.1", f"0.2:{SNARE}:127:0.1"], seconds=0.6)
    assert peak(s3, 0, 0.19) == 0 and peak(s3, 0.2) > 0.2


def test_kit_and_drive_type_are_read_when_a_pad_is_struck(renderer, tmp_path):
    notes = [f"0:{KICK}:127:0.1", f"1.0:{KICK}:127:0.1"]
    _, _, classic = run(renderer, tmp_path, "c", [], notes, seconds=1.6)
    _, _, big = run(renderer, tmp_path, "b", ["Kit=1"], notes, seconds=1.6)
    _, _, turned = run(renderer, tmp_path, "t", [], notes, ["--param-at", "0.5:Kit=1"], seconds=1.6)
    n = int(1.0 * RATE)
    # The sounding kick keeps the kit it was struck in; the next is Big
    # Beat's (Level 61 of 94: quieter).
    assert turned[:n] == classic[:n]
    assert peak(turned, 1.0, 1.3) == pytest.approx(peak(big, 1.0, 1.3), rel=0.01)
    assert peak(turned, 1.0, 1.3) < 0.8 * peak(classic, 1.0, 1.3)
    _, _, fold = run(renderer, tmp_path, "f", ["Drive Type=5", "Drive=0.6"], notes, seconds=1.6)
    _, _, late = run(renderer, tmp_path, "l", ["Drive=0.6"], notes,
                     ["--param-at", "0.5:Drive Type=5"], seconds=1.6)
    _, _, diode = run(renderer, tmp_path, "d", ["Drive=0.6"], notes, seconds=1.6)
    assert late[:n] == diode[:n] and fold[:n] != diode[:n]
    assert max(abs(a - b) for a, b in zip(late[n + 64:], fold[n + 64:])) < 1e-3


@pytest.mark.parametrize("latched", ["Kit=1", "Drive Type=5"])
def test_hit_latched_controls_stay_latched_during_a_smooth_ramp(renderer, tmp_path, latched):
    notes = [f"0:{KICK}:127:0.1", f"0.5:{KICK}:127:0.1"]
    ramp = ["--param-at", "0.2:Drive=0.9"]
    _, _, unchanged = run(renderer, tmp_path, "ramp", [], notes, ramp, seconds=0.8)
    _, _, changed = run(renderer, tmp_path, "latch", [], notes,
                        ramp + ["--param-at", f"0.201:{latched}"], seconds=0.8)
    n = int(0.5 * RATE)
    assert changed[:n] == unchanged[:n]
    assert changed[n + 64:] != unchanged[n + 64:]


def test_a_smooth_knob_reaches_a_sounding_pad(renderer, tmp_path):
    notes = [f"0:{KICK}:127:0.1"]
    _, _, plain = run(renderer, tmp_path, "p", [], notes, seconds=0.8)
    _, _, turned = run(renderer, tmp_path, "d", [], notes, ["--param-at", "0.3:Drive=1"], seconds=0.8)
    n = int(0.3 * RATE)
    assert turned[:n] == plain[:n] and turned[n + 512:] != plain[n + 512:]


def test_the_kicks_tone_moves_its_pitch_once_sweep_is_up(renderer, tmp_path):
    """9W9's Pitch and P.Dpth on the kick (our Tone and Sweep): at Sweep 0
    the kick is 9W9's 49 Hz whatever Tone says; at Sweep 1 Tone sets it
    (pitch 0.43..4.7 times 49 Hz)."""
    hz = {}
    for name, ps in (("plain", []), ("tone", ["Tone=1"]), ("swept", ["Sweep=1", "Tone=0.7"])):
        _, _, x = run(renderer, tmp_path, name, ps, [f"0:{KICK}:127:0.1"], seconds=1.0)
        hz[name] = zc_hz(x, 0.4, 0.8)
    assert abs(cents(hz["plain"], 49.0)) < 25 and hz["tone"] == pytest.approx(hz["plain"], rel=1e-3)
    assert hz["swept"] > 1.5 * hz["plain"]


def at(frame):
    """A time just before frame (a multiple of 448, which 1, 7, 64 and 448
    all divide): fm1-render applies an event at the first block start at or
    after its time, so at every host block size it reaches the engine at
    frame - 1 or frame, both on the same side of the 16-sample chunk grid."""
    return f"{(frame - 1) / RATE:.9f}"


GROOVE = [f"{at(448 * k)}:{key}:{vel}:0.1" for k, key, vel in
          [(1, KICK, 127), (2, CLOSED_HH, 90), (4, SNARE, 110), (6, OPEN_HH, 120),
           (7, PEDAL_HH, 70), (9, CLAP, 127), (10, RIM, 100), (12, LOW_MID, 127),
           (15, CRASH, 100), (17, SNARE2, 127), (19, RIDE, 90), (21, KICK, 80),
           (23, FLOOR_TOM, 127), (26, HIGH_MID, 100), (30, KICK, 127), (31, OPEN_HH, 127),
           (33, CLOSED_HH, 127)]]


def turns():
    return ["--param-at", f"{at(1344)}:Pad=0", "--param-at", f"{at(1344)}:Drive=0.7",
            "--param-at", f"{at(2240)}:Volume=0.5", "--param-at", f"{at(3136)}:Kit=1",
            "--param-at", f"{at(4032)}:Pad=10", "--param-at", f"{at(4032)}:Decay=0.9",
            "--param-at", f"{at(4480)}:Drive Type=6", "--param-at", f"{at(4928)}:Accent=3",
            "--param-at", f"{at(8960)}:Pad=2", "--param-at", f"{at(8960)}:Snap=0.9"]


def test_the_output_does_not_depend_on_the_host_block_or_memory(renderer, tmp_path):
    outs = set()
    for frames in ("1", "7", "64", "448"):
        for fill in ("0x00", "0xA5", "0xFF"):
            if frames != "64" and fill != "0x00":
                continue
            _, w, _ = run(renderer, tmp_path, f"b{frames}{fill}", [], GROOVE,
                          turns() + ["--frames", frames, "--fill", fill], seconds=0.8)
            outs.add(w)
    assert len(outs) == 1


@pytest.mark.parametrize("rate,ok", [(44100, True), (48000, True), (96000, True), (32000, False),
                                     (192000, False)])
def test_rates(renderer, tmp_path, rate, ok):
    """The host's own rate, 40-96 kHz: a tom keeps its pitch and a crash its
    recording's pitch (its zero crossings, read faster or slower)."""
    wav = tmp_path / "r.wav"
    res = subprocess.run([str(renderer), "--engine", "comet", "--rate", str(rate), "--note",
                          f"0:{LOW_TOM}:127:0.1", "--seconds", "0.7", "--out", str(wav)],
                         capture_output=True, text=True)
    assert (res.returncode == 0) == ok, res.stderr
    if ok:
        import wave
        with wave.open(str(wav), "rb") as w:
            raw = w.readframes(w.getnframes())
        x = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767 for i in range(0, len(raw), 4)]
        k = rate / RATE                  # zc_hz counts in RATE
        assert abs(cents(zc_hz(x, 0.35 * k, 0.6 * k) * k, 67.9)) < 25


@pytest.mark.parametrize("end", ["min", "max", "nan", "inf", "-inf"])
def test_every_parameter_at_an_extreme_renders_finite(renderer, tmp_path, listing, end):
    params = []
    for pad in range(16):
        params.append(f"Pad={pad}")
        for p in listing["comet"]["params"][1:]:
            v = {"min": p["min"], "max": p["max"], "nan": "nan", "inf": "inf", "-inf": "-inf"}[end]
            params.append(f"{p['name']}={v}")
    notes = [f"{0.01 * k:.2f}:{36 + k}:127:0.1" for k in range(16)]
    s, _, x = run(renderer, tmp_path, end, params, notes, seconds=1.0)
    assert s["nonfinite"] == 0 and s["raw_peak"] < 32


def test_it_returns_to_zero(renderer, tmp_path):
    """Every pad at its longest decays and full drive: by 4 s every voice's
    countdown has run out (the crash and ride at 3 s, 9W9's longest)."""
    params = []
    for pad in range(16):
        params += [f"Pad={pad}", "Decay=1", "Tone=1", "Drive=1"]
    s, _, x = run(renderer, tmp_path, "zero", params, [f"0:{k}:127:0.1" for k in range(36, 52)],
                  seconds=4.5)
    assert peak(x, 4.2) == 0


def test_no_subnormal_floats_in_the_state(renderer):
    """--state: every pad struck at once, twice, in both kits, and the tails
    to their end: no float of the engine's unit is ever subnormal (the
    kick's sweep offset, the one that would be, is flushed at 1e-20 Hz,
    where it no longer moves a bit of the kick's frequency)."""
    for rate in ("44118", "48000"):
        code, rows = oracle("--state", "--rate", rate)
        assert code == 0 and rows[0]["subnormal_state_max"] == 0 and rows[0]["subnormal_out"] == 0, rows


def test_instance_size_and_cost(renderer, tmp_path):
    notes = [f"{0.12 * k:.2f}:{key}:110:0.1" for k in range(32)
             for key in (KICK, RIM, SNARE, CLAP, LOW_TOM, CLOSED_HH, MID_TOM, OPEN_HH, CRASH,
                         HIGH_TOM, RIDE)]
    s, _, _ = run(renderer, tmp_path, "dense", ["Volume=0.2"], notes, seconds=4.0)
    assert s["instance_bytes"] <= 11 * 1024
    assert s["ns_per_block"] < 64 / 44118 * 1e9 / 20          # far under real time, on any desktop


def test_no_transcendental_libm_calls():
    """No sinf, expf and the like in the wrapper or the vendored kit, so the
    browser's module renders the same samples as the native build."""
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    banned = {f + s for f in ("sin", "cos", "tan", "exp", "exp2", "log", "log2", "log10", "pow",
                               "tanh", "atan", "atan2", "sinh", "cosh", "sqrt", "floor", "ceil")
              for s in ("", "f")}
    for obj in (ENGINES / "build" / "our" / "src" / "comet_kit.o",
                ENGINES / "build" / "gpl" / "fm1-x0x" / "dsp" / "drum909.o"):
        syms = subprocess.run([nm, "-u", str(obj)], check=True, capture_output=True, text=True).stdout
        names = {line.split()[-1].lstrip("_") for line in syms.splitlines() if line.strip()}
        assert not names & banned, (obj.name, names & banned)
        assert not names & {"malloc", "free", "calloc", "realloc", "printf", "fprintf", "puts"}, obj.name


def arrays(path, ctype):
    import re
    text = Path(path).read_text()
    return {m.group(1): [int(v) for v in m.group(3).replace("\n", " ").split(",") if v.strip()]
            for m in re.finditer(r"static const %s (\w+)\[(\d+)\] = \{(.*?)\};" % ctype, text, re.S)}


def test_the_cymbals_are_er99s_recordings_in_8_bit_mu_law():
    """The flash the samples take, as the generated header declares them
    (owner's decision, 2026-10-06): hi-hat 20,250, ride 46,999 and crash
    43,300 frames as 8-bit mu-law codes (110,549 B, half fm1-x0x's int16),
    and a 256-entry int16 decode table (512 B)."""
    path = VENDOR / "gen" / "x0x_drum_samples.h"
    text = path.read_text()
    lens = {}
    for line in text.splitlines():
        if line.startswith("#define X0X_SMP_"):
            _, name, v = line.split()
            lens[name] = int(v.rstrip("u"))
    assert lens == {"X0X_SMP_HH_LEN": 20250, "X0X_SMP_RIDE_LEN": 46999, "X0X_SMP_CRASH_LEN": 43300}
    codes = arrays(path, "uint8_t")
    assert {n: len(v) for n, v in codes.items()} == {"x0x_smp_hh": 20250, "x0x_smp_ride": 46999,
                                                     "x0x_smp_crash": 43300}
    assert sum(map(len, codes.values())) == 110_549 and all(0 <= c < 256 for v in codes.values() for c in v)
    dec = arrays(path, "int16_t")["x0x_mulaw_dec"]
    assert len(dec) == 256 and dec[0] == dec[128] == 0 and dec[127] == 32767
    assert dec[128:] == [-v for v in dec[:128]] and all(a < b for a, b in zip(dec[:127], dec[1:128]))
    assert "8-bit mu-law codes" in text
    assert Path(VENDOR / "assets" / "909" / "README.txt").read_text().startswith("909 cymbal samples")


def snr_db(x, y):
    s = sum(v * v for v in x)
    e = sum((a - b) ** 2 for a, b in zip(x, y))
    return 10 * math.log10(s / e)


def test_the_mu_law_cymbals_keep_37_8_db_of_the_int16(int16_gen):
    """Each recording decoded from its mu-law codes against fm1-x0x's int16
    (the vendored script's --int16): 37.8 dB of SNR or more, no sample off
    by more than 600 of 32,768 (the step at full scale is 1,404), and quiet
    samples within 3 (the smallest step is 6)."""
    path = VENDOR / "gen" / "x0x_drum_samples.h"
    codes, dec = arrays(path, "uint8_t"), arrays(path, "int16_t")["x0x_mulaw_dec"]
    for name, x in arrays(int16_gen / "x0x_drum_samples.h", "int16_t").items():
        y = [dec[c] for c in codes[name]]
        assert len(y) == len(x)
        assert snr_db(x, y) > 37.75, name
        assert max(abs(a - b) for a, b in zip(x, y)) < 600, name
        assert all(abs(a - b) <= 3 for a, b in zip(x, y) if abs(a) < 6), name


def fft(x):
    n = len(x)
    if n == 1:
        return x
    ev, od = fft(x[0::2]), fft(x[1::2])
    tw = [cmath.exp(-2j * math.pi * k / n) * od[k] for k in range(n // 2)]
    return [ev[k] + tw[k] for k in range(n // 2)] + [ev[k] - tw[k] for k in range(n // 2)]


OCTAVES = [0, 250, 500, 1000, 2000, 4000, 8000, 16000, 22050]


def octave_snr(x, y, rate=44100, n=2048):
    """Per band of OCTAVES: (SNR in dB, the band's share of the signal in
    dB), from Hann-windowed 2048-point spectra of x and of x - y."""
    win = [0.5 - 0.5 * math.cos(2 * math.pi * i / n) for i in range(n)]
    s, e = [0.0] * (len(OCTAVES) - 1), [0.0] * (len(OCTAVES) - 1)
    for f0 in range(0, len(x) - n + 1, n):
        sx = fft([x[f0 + i] * win[i] for i in range(n)])
        sd = fft([(x[f0 + i] - y[f0 + i]) * win[i] for i in range(n)])
        for k in range(1, n // 2):
            b = next(j for j in range(len(OCTAVES) - 1) if OCTAVES[j] <= k * rate / n < OCTAVES[j + 1])
            s[b] += abs(sx[k]) ** 2
            e[b] += abs(sd[k]) ** 2
    return [(10 * math.log10(s[j] / e[j]), 10 * math.log10(s[j] / sum(s))) for j in range(len(s))]


def test_the_kits_cymbals_with_mu_law_against_int16(tmp_path, int16_gen):
    """drum909_cymbals.c: the closed and open hat, crash and ride, each struck
    alone on the panel's defaults at three tunings and with drive, through
    the kit with the mu-law cymbals and with fm1-x0x's int16 ones. In the
    kit's output the mu-law error is noise that follows the signal: 38.3 dB
    or more under each hit (38.5-44.2 dB measured), at -54 dBFS or less; in
    every octave holding an eighth or more of a hit's energy (2-16 kHz on
    the hats) it is 35 dB or more under the signal; the octaves where it
    comes within 22-31 dB (under 250 Hz and over 16 kHz) hold 1/40 or less
    of it (engines/README.md, "Comet Kit")."""
    import array
    mu = build_cymbals(tmp_path, "mu")
    i16 = build_cymbals(tmp_path, "i16", "-DX0X_SMP_INT16", "-I", str(int16_gen))
    a, b = array.array("f"), array.array("f")
    a.frombytes(subprocess.run([str(i16)], check=True, capture_output=True).stdout)
    b.frombytes(subprocess.run([str(mu)], check=True, capture_output=True).stdout)
    seg = 88200
    assert len(a) == len(b) == 16 * seg and a != b
    for k, voice in enumerate(["closed hat", "open hat", "crash", "ride"]):
        for s, setting in enumerate(["tune 0", "tune 64", "tune 127", "drive 100"]):
            x, y = a[(4 * k + s) * seg:(4 * k + s + 1) * seg], b[(4 * k + s) * seg:(4 * k + s + 1) * seg]
            err = sum((u - v) ** 2 for u, v in zip(x, y)) / seg
            assert snr_db(x, y) > 38.3, (voice, setting, snr_db(x, y))
            assert 10 * math.log10(err) < -54.0, (voice, setting)
            if s == 1:
                for (lo, hi), (snr, share) in zip(zip(OCTAVES, OCTAVES[1:]), octave_snr(x, y)):
                    assert snr > (35.0 if share > -9.0 else 20.0 if share < -17.0 else 28.0), \
                        (voice, lo, hi, snr, share)


def mu_law_8bit(x):
    """Each sample through 8-bit mu-law (mu 255: a sign and 7 bits of the
    companded magnitude) and back."""
    k = math.log1p(255.0)
    out = []
    for v in x:
        c = math.log1p(255.0 * abs(v) / 32768.0) / k
        q = round(c * 127) / 127
        out.append(round(math.copysign(math.expm1(q * k) / 255.0, v) * 32768.0))
    return out


IMA_STEPS = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60,
             66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371,
             408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707,
             1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484,
             7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385,
             24623, 27086, 29794, 32767]
IMA_INDEX = [-1, -1, -1, -1, 2, 4, 6, 8]


def ima_adpcm(x):
    """Each sample through 4-bit IMA ADPCM and back (the encoder's own
    reconstruction)."""
    pred, idx, out = 0, 0, []
    for v in x:
        step, diff, code = IMA_STEPS[idx], v - pred, 0
        if diff < 0:
            code, diff = 8, -diff
        d = step >> 3
        for bit in (4, 2, 1):
            if diff >= step:
                code |= bit
                diff -= step
                d += step
            step >>= 1
        pred = max(-32768, min(32767, pred - d if code & 8 else pred + d))
        idx = max(0, min(88, idx + IMA_INDEX[code & 7]))
        out.append(pred)
    return out


def test_the_cymbal_budget_options_measure_as_documented(int16_gen):
    """The options the study weighed (engines/README.md, "Comet Kit"): 8-bit
    mu-law, rounded in the companded domain, keeps 37.8 dB or more of SNR
    against the int16 on each recording; 4-bit IMA ADPCM would quarter the
    flash but keeps under 19 dB, too lossy for cymbals."""
    for name, x in arrays(int16_gen / "x0x_drum_samples.h", "int16_t").items():
        assert snr_db(x, mu_law_8bit(x)) > 37.7, name
        assert snr_db(x, ima_adpcm(x)) < 19.0, name
