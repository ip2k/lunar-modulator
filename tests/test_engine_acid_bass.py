"""Acid Bass (engines/src/acid_bass.cc; engines/README.md, "Acid Bass"): a
monophonic bass after the TB-303 on fm1-x0x's 303 bass (Charles Vestal,
GPL-3.0-only; engines/third_party/fm1-x0x), built only with the GPL switch on.

Against its sources: the vendored files are fm1-x0x's plus local.patch, and
the patched bass gives fm1-x0x's own samples at 44.1 kHz (both when
reference/ has the clones); the engine is its vendored unit driven as
fm1-x0x's sequencer drives it, on a 16-sample grid, bit for bit, at host
blocks of 1, 7, 64 and 448 frames and at three rates (fm1-acid-oracle
--twin); and each parameter reaches the unit as the value its unit says
(--fields).

How it plays: a velocity of 100 or more accents, and velocity does nothing
else; a key played over a held one slides, letting go slides back, the last
release releases; the Slide time is the glide's; Tune, the bend and a
per-note pitch offset move the pitch, and a pitch offset is a bend; POLY
offsets ride on the sounding key only and restart on a new key; LATCH
values wait for a note-on, the switches for a note that is not a slide;
SMOOTH values apply at once while silent. The output does not depend on the
host's block size or on what instance memory held; it is finite at every
extreme, has no subnormal sample, and the engine calls no libm.
"""
import json
import math
import shutil
import subprocess
import wave

import pytest

from tests.engine_helpers import (ENGINES, RATE, ROOT, cents, gpl_only, pitch_hz, render,  # noqa: F401
                                  renderer, rms)

pytestmark = gpl_only

ORACLE = ENGINES / "build" / "fm1-acid-oracle"
X0X = ROOT / "reference" / "fm1-x0x"
S303 = ROOT / "reference" / "schwung-303"
VENDOR = ENGINES / "third_party" / "fm1-x0x"
NAMES = ["Cutoff", "Resonance", "Env Mod", "Decay", "Accent", "Wave", "Tune", "Volume",
         "Drive", "Drive Type", "Slide", "Acc Decay"]
# A clean tone to measure pitch on: the filter open and still, no resonance.
CLEAN = ["Env Mod=0", "Resonance=0", "Cutoff=314", "Decay=2000"]


def run(renderer, tmp_path, name, params=(), notes=(), extra=(), seconds=1.0):
    """(summary, WAV bytes, left channel as floats)."""
    s, left, wav = render(renderer, tmp_path, "acid-bass", params=list(params), notes=list(notes),
                          seconds=seconds, name=name, extra=list(extra))
    assert s["nonfinite"] == 0
    return s, wav.read_bytes(), left


def oracle(*args):
    out = subprocess.run([str(ORACLE), *args], capture_output=True, text=True)
    lines = [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
    return out.returncode, lines


@pytest.fixture(scope="module")
def listing(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True, text=True)
    return {e["id"]: e for e in json.loads(out.stdout)}


# ---- What it is ------------------------------------------------------------------------------

def test_it_lists_as_a_gpl_mono_sound(listing):
    e = listing["acid-bass"]
    assert (e["kind"], e["max_voices"], e["per_note"], e["pads"], e["name"]) == \
        ("sound", 1, True, None, "Acid Bass")
    assert e["licence"] == "GPL-3.0-only AND MIT" and e["source"] == "engines/third_party/fm1-x0x"
    for who in ("Charles Vestal", "Robin Schmidt", "midilab", "Dave Mollen", "TB-303"):
        assert who in e["credits"], who
    assert [p["name"] for p in e["params"]] == NAMES          # fm1-x0x's own order and pages
    assert [p["page"] for p in e["params"]] == [0] * 4 + [1] * 4 + [2] * 4
    assert all(len(p["name"]) <= 12 for p in e["params"])
    flags = {p["name"]: set(p["flags"]) for p in e["params"]}
    assert {n for n, f in flags.items() if "poly" in f} == {"Cutoff", "Resonance", "Env Mod",
                                                           "Volume", "Drive"}
    assert {n for n, f in flags.items() if "latch" in f} == {"Decay", "Accent", "Wave",
                                                            "Drive Type", "Acc Decay"}


# ---- Against its sources -------------------------------------------------------------------

def test_the_vendored_files_are_upstreams_plus_the_local_patch():
    if not (X0X / ".git").exists() or not (S303 / ".git").exists():
        pytest.skip("reference/fm1-x0x and reference/schwung-303 are not cloned")
    subprocess.run(["python3", str(VENDOR / "vendor.py"), str(X0X), str(S303), "--check"],
                   check=True, capture_output=True)


def test_the_patched_bass_gives_upstreams_samples(tmp_path):
    """bass303_drive.c, upstream's API only (integer pots, 256-frame calls at
    44.1 kHz, five settings including both drives and the Devilfish ranges),
    built against fm1-x0x's own bass303.c and against ours: the same bytes."""
    src = X0X / "firmware" / "src" / "dsp"
    if not (src / "bass303.c").is_file():
        pytest.skip("reference/fm1-x0x is not cloned")
    cc = shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("no C compiler")
    outs = []
    for name, d in (("upstream", src), ("vendored", VENDOR / "dsp")):
        exe = tmp_path / name
        subprocess.run([cc, "-std=c99", "-O2", "-ffp-contract=off", "-I", str(d),
                        str(ENGINES / "test" / "bass303_drive.c"), str(d / "bass303.c"), "-o", str(exe)],
                       check=True)
        outs.append(subprocess.run([str(exe)], check=True, capture_output=True).stdout)
    assert len(outs[0]) > 4 * 44100 * 5 and outs[0] == outs[1]


@pytest.mark.parametrize("rate,block", [(44118, 1), (44118, 7), (44118, 64), (44118, 448),
                                        (44100, 64), (44100, 448), (48000, 64), (48000, 448)])
def test_the_engine_is_its_unit_on_a_16_sample_grid(renderer, rate, block):
    """fm1-acid-oracle --twin: six lines (the defaults, a squelchy setting,
    the square with long Devilfish slides and accent decay, both drives, and
    ties) through the engine and through a copy of its unit driven as
    fm1-x0x's sequencer drives it, each event on the chunk after its frame.
    No sample is subnormal, and the state's decaying floats are measured."""
    code, lines = oracle("--twin", "--rate", str(rate), "--block", str(block))
    assert code == 0 and len(lines) == 6, lines
    for line in lines:
        assert line["differ"] == 0 and line["left_right_differ"] == 0, line
        assert line["nonfinite"] == 0 and line["subnormal_out"] == 0, line
        assert line["subnormal_state_max"] == 0, line      # none seen after a render call
        assert 0.1 < line["peak"] < 1.0, line


def test_each_parameter_reaches_the_unit_in_its_unit(renderer):
    """--fields: the unit's own values after set_param, against X0X's
    mappings written out in the parameters' units."""
    code, rows = oracle("--fields", "--rate", "44100")
    assert code == 0
    by = {(r["param"], r["value"]): r for r in rows}
    sr = 44100.0

    def rc(ms):
        return math.exp(-1000.0 / (ms * sr))

    def close(a, b, rel=2e-5):
        return abs(a - b) <= rel * max(abs(a), abs(b), 1e-30)
    base = by[("", 0)]
    assert base["sr"] == sr and close(base["cutoff"], 870) and base["tuning"] == 440
    assert close(base["amp_scaler"], 10 ** ((-60 + 60 * 96 / 127) / 20), 1e-5)   # X0X's pot 96
    for hz in (314, 1000, 2394):
        assert close(by[("Cutoff", hz)]["cutoff"], hz), hz
    for pct in (0, 37.5, 100):
        want = (1 - math.exp(-3 * pct / 100)) / 0.950212932
        assert abs(by[("Resonance", pct)]["reso"] - want) < 2e-6, pct
    assert by[("Env Mod", 0)]["env_scaler"] < by[("", 0)]["env_scaler"] < by[("Env Mod", 100)]["env_scaler"]
    for ms in (200, 1000, 2000):
        assert close(by[("Decay", ms)]["decay_c"], rc(ms), 1e-6), ms
    for ms in (30, 200, 3000):
        assert close(by[("Acc Decay", ms)]["accdec_c"], rc(ms), 1e-6), ms
    for ms in (2, 60, 360):
        assert close(by[("Slide", ms)]["slew_c"], rc(0.2 * ms), 1e-6), ms   # the slew's tau is 0.2 x the time
    assert close(base["accdec_c"], rc(200), 1e-6) and close(base["slew_c"], rc(12), 1e-6)
    assert by[("Accent", 25)]["accent"] == 0.25 and close(by[("Drive", 40)]["drv_amt"], 0.4, 1e-6)
    assert by[("Drive Type", 2)]["drv_type"] == 2 and by[("Wave", 1)]["wave"] == 1
    assert base["drv_type"] == 1 and base["wave"] == 0 and base["idle"] == 1


# ---- How it plays ------------------------------------------------------------------------

def test_velocity_accents_from_100_and_does_nothing_else(renderer, tmp_path):
    _, quiet, a = run(renderer, tmp_path, "v1", notes=["0:45:1:0.4"], seconds=0.5)
    _, same, _ = run(renderer, tmp_path, "v99", notes=["0:45:99:0.4"], seconds=0.5)
    _, loud, b = run(renderer, tmp_path, "v100", notes=["0:45:100:0.4"], seconds=0.5)
    _, also, _ = run(renderer, tmp_path, "v127", notes=["0:45:127:0.4"], seconds=0.5)
    assert quiet == same and loud == also and quiet != loud
    assert rms(b, 0.0, 0.2) > 1.3 * rms(a, 0.0, 0.2)


def test_a_key_played_over_a_held_one_slides_to_it(renderer, tmp_path):
    """A2 held, A3 over it: the pitch moves from 110 to 220 Hz and the sound
    goes on through the change; A3 after A2 is let go is a new note, after a
    gap. (That a slide restarts no envelope, as in Open303, the twin test
    holds to the bit.)"""
    p = CLEAN + ["Slide=60"]
    _, _, glide = run(renderer, tmp_path, "slide", p, ["0:45:80:1.0", "0.4:57:80:0.6"], seconds=1.0)
    _, _, fresh = run(renderer, tmp_path, "fresh", p, ["0:45:80:0.39", "0.4:57:80:0.6"], seconds=1.0)
    assert abs(cents(pitch_hz(glide, 0.25, 0.1), 110.0)) < 10
    assert abs(cents(pitch_hz(glide, 0.75, 0.15), 220.0)) < 10
    assert abs(cents(pitch_hz(fresh, 0.75, 0.15), 220.0)) < 10
    assert rms(glide, 0.394, 0.4) > 10 * rms(fresh, 0.394, 0.4)


def test_slide_time(renderer, tmp_path):
    """From 15 to 75 ms after the slide starts, a 2 ms slide has arrived
    and a 360 ms one is still on its way (its slew's time constant is a fifth
    of the time, 72 ms: about 540 cents up on average there)."""
    def at(slide):                         # A3 to A4, enough periods in 60 ms
        _, _, x = run(renderer, tmp_path, f"s{slide}", CLEAN + ["Cutoff=600", f"Slide={slide}"],
                      ["0:57:80:1.0", "0.4:69:80:0.6"], seconds=0.8)
        return cents(pitch_hz(x, 0.415, 0.06), 220.0)
    assert at(2) > 1180 and 300 < at(360) < 800


def test_letting_go_slides_back_and_the_last_release_releases(renderer, tmp_path):
    p = CLEAN + ["Slide=20"]
    _, _, x = run(renderer, tmp_path, "back", p, ["0:45:80:1.2", "0.3:57:80:0.4"], seconds=1.6)
    assert abs(cents(pitch_hz(x, 0.5, 0.15), 220.0)) < 10
    assert abs(cents(pitch_hz(x, 0.85, 0.2), 110.0)) < 10    # back to A2, still sounding
    assert rms(x, 0.85, 1.0) > 0.01 and rms(x, 1.35, 1.5) < 1e-3


def test_twenty_keys_held_then_let_go(renderer, tmp_path):
    notes = [f"{0.02 * k:.2f}:{40 + k}:80:{1.0 - 0.02 * k:.2f}" for k in range(20)]
    s, _, x = run(renderer, tmp_path, "many", notes=notes, seconds=1.6)
    assert s["notes_hung"] == 0 and rms(x, 1.4, 1.6) < 1e-4


def test_tune_bend_and_a_pitch_offset(renderer, tmp_path):
    _, _, up = run(renderer, tmp_path, "tune", CLEAN + ["Tune=12"], ["0:45:80:0.8"], seconds=0.8)
    assert abs(cents(pitch_hz(up, 0.3, 0.3), 220.0)) < 10
    _, bend, b = run(renderer, tmp_path, "bend", CLEAN, ["0:45:80:0.8"], ["--bend", "0:7"], seconds=0.8)
    assert abs(cents(pitch_hz(b, 0.3, 0.3), 110.0 * 2 ** (7 / 12))) < 10
    _, off, _ = run(renderer, tmp_path, "off", CLEAN, ["0:45:80:0.8"],
                    ["--note-pitch-at", "0:45:7"], seconds=0.8)
    assert off == bend                         # a pitch offset on the note is a bend
    _, tuned, _ = run(renderer, tmp_path, "t7", CLEAN + ["Tune=7"], ["0:45:80:0.8"], seconds=0.8)
    assert tuned == bend                       # and Tune, set before, is the same pitch path


def test_offsets_ride_on_the_sounding_key_only(renderer, tmp_path):
    base, _, _ = run(renderer, tmp_path, "b0", ["Cutoff=1200"], ["0:45:80:0.6"], seconds=0.6)
    _, moved, _ = run(renderer, tmp_path, "b1", ["Cutoff=1200"], ["0:45:80:0.6"], seconds=0.6)
    _, off, _ = run(renderer, tmp_path, "o1", ["Cutoff=900"], ["0:45:80:0.6"],
                    ["--note-param-at", "0:45:Cutoff=300"], seconds=0.6)
    assert off == moved                        # an offset on a lone note is a base change
    _, other, _ = run(renderer, tmp_path, "o2", [], ["0:45:80:0.6"],
                      ["--note-param-at", "0:50:Cutoff=900"], seconds=0.6)
    _, plain, _ = run(renderer, tmp_path, "o3", [], ["0:45:80:0.6"], seconds=0.6)
    assert other == plain                      # a key that is not sounding: ignored
    # A slide to a new key starts its offsets at 0: an offset sent to the old
    # key after the slide changes nothing.
    _, slid, _ = run(renderer, tmp_path, "o4", [], ["0:45:80:0.8", "0.3:52:80:0.5"], seconds=0.8)
    _, late, _ = run(renderer, tmp_path, "o5", [], ["0:45:80:0.8", "0.3:52:80:0.5"],
                     ["--note-param-at", "0.4:45:Cutoff=900"], seconds=0.8)
    assert late == slid


def test_latch_values_wait_for_a_note_on_and_switches_for_a_trigger(renderer, tmp_path):
    notes = ["0:45:80:0.6", "0.3:50:80:0.25", "0.7:45:80:0.3"]   # a slide at 0.3, a trigger at 0.7
    _, plain, a = run(renderer, tmp_path, "l0", notes=notes, seconds=1.0)
    for change in ("Wave=1", "Drive Type=2"):
        _, _, b = run(renderer, tmp_path, "l1", ["Drive=50"] if "Drive" in change else [],
                      notes, ["--param-at", f"0.15:{change}"], seconds=1.0)
        _, _, ref = run(renderer, tmp_path, "l2", ["Drive=50"] if "Drive" in change else [],
                        notes, seconds=1.0)
        first = next(i for i, (x, y) in enumerate(zip(b, ref)) if x != y)
        assert first >= int(0.7 * RATE), (change, first / RATE)   # not at 0.15, not at the slide
    _, _, d = run(renderer, tmp_path, "l3", notes=notes, extra=["--param-at", "0.15:Decay=200"], seconds=1.0)
    first = next(i for i, (x, y) in enumerate(zip(d, a)) if x != y)
    assert int(0.3 * RATE) <= first < int(0.31 * RATE)             # Decay: the slide's note-on reads it


def test_a_change_while_silent_applies_at_once(renderer, tmp_path):
    _, a, _ = run(renderer, tmp_path, "s0", ["Cutoff=500", "Volume=0.4"], ["0.3:45:80:0.4"], seconds=0.8)
    _, b, _ = run(renderer, tmp_path, "s1", [], ["0.3:45:80:0.4"],
                  ["--param-at", "0.1:Cutoff=500", "--param-at", "0.1:Volume=0.4"], seconds=0.8)
    assert a == b


def test_volume(renderer, tmp_path):
    _, _, a = run(renderer, tmp_path, "v7", [], ["0:45:80:0.4"], seconds=0.5)
    _, _, b = run(renderer, tmp_path, "v35", ["Volume=0.35"], ["0:45:80:0.4"], seconds=0.5)
    _, _, z = run(renderer, tmp_path, "v0", ["Volume=0"], ["0:45:80:0.4"], seconds=0.5)
    assert abs(rms(b, 0.05, 0.3) / rms(a, 0.05, 0.3) - 0.25) < 0.01 and max(map(abs, z)) == 0


def at(k):
    """A time fm1-render applies at the block that starts at frame 448 k: a
    block boundary at 1, 7, 64 and 448 frames (just before it, so rounding
    never pushes it a block later). 448 is no multiple of the engine's 16, so
    the events fall inside its chunks."""
    return f"{(448 * k - 0.25) / RATE:.9f}"


def test_the_output_does_not_depend_on_the_host_block_or_memory(renderer, tmp_path):
    def note(k0, k1, key, vel):                # from block 448 k0 to 448 k1
        return f"{at(k0)}:{key}:{vel}:{448 * (k1 - k0) / RATE:.9f}"
    notes = [note(1, 31, 45, 120), note(20, 60, 52, 80), note(33, 52, 57, 100), note(70, 120, 40, 70)]
    extra = ["--param-at", f"{at(10)}:Cutoff=1500", "--param-at", f"{at(45)}:Resonance=90",
             "--param-at", f"{at(50)}:Tune=-3", "--bend", f"{at(60)}:1.5",
             "--note-pitch-at", f"{at(75)}:40:-2", "--note-param-at", f"{at(80)}:40:Drive=30",
             "--param-at", f"{at(52)}:Drive Type=2"]
    outs = set()
    for frames in ("1", "7", "64", "448"):
        for fill in ("0x00", "0xFF", "0xA5"):
            if frames != "64" and fill != "0x00":
                continue
            _, w, _ = run(renderer, tmp_path, f"b{frames}{fill}", ["Drive=20"], notes,
                          extra + ["--frames", frames, "--fill", fill], seconds=1.4)
            outs.add(w)
    assert len(outs) == 1


@pytest.mark.parametrize("rate,ok", [(44100, True), (48000, True), (96000, True), (32000, False),
                                     (192000, False)])
def test_rates(renderer, tmp_path, rate, ok):
    wav = tmp_path / "r.wav"
    res = subprocess.run([str(renderer), "--engine", "acid-bass", "--rate", str(rate),
                          "--param", "Env Mod=0", "--param", "Resonance=0", "--param", "Cutoff=314",
                          "--note", "0:45:80:0.8", "--seconds", "0.8", "--out", str(wav)],
                         capture_output=True, text=True)
    assert (res.returncode == 0) == ok, res.stderr
    if ok:
        with wave.open(str(wav), "rb") as w:
            raw = w.readframes(w.getnframes())
        x = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767 for i in range(0, len(raw), 4)]
        # pitch_hz counts in RATE: 0.3 s of this file is 0.3 x rate / RATE of RATE's
        k = rate / RATE
        assert abs(cents(pitch_hz(x, 0.3 * k, 0.3 * k) * k, 110.0)) < 10


@pytest.mark.parametrize("end", ["min", "max", "nan", "inf", "-inf"])
def test_every_parameter_at_an_extreme_renders_finite(renderer, tmp_path, listing, end):
    params = []
    for p in listing["acid-bass"]["params"]:
        v = {"min": p["min"], "max": p["max"], "nan": "nan", "inf": "inf", "-inf": "-inf"}[end]
        params.append(f"{p['name']}={v}")
    s, _, x = run(renderer, tmp_path, end, params, ["0:24:127:0.5", "0.2:96:127:0.5", "0.25:12:127:0.5"],
                  ["--bend", "0.3:48", "--note-pitch-at", "0.35:12:48"], seconds=1.0)
    assert s["nonfinite"] == 0 and s["raw_peak"] < 8


def test_it_goes_quiet_and_idle(renderer, tmp_path):
    s, _, x = run(renderer, tmp_path, "idle", ["Resonance=100", "Decay=2000"], ["0:45:127:0.3"], seconds=2.5)
    assert max(abs(v) for v in x[int(1.5 * RATE):]) == 0


def test_instance_size_and_cost(renderer, tmp_path):
    s, _, _ = run(renderer, tmp_path, "size", [], ["0:45:120:0.5"], seconds=0.5)
    assert s["instance_bytes"] <= 1536
    assert s["ns_per_block"] < 64 / 44118 * 1e9 / 20          # far under real time, on any desktop


def test_no_transcendental_libm_calls():
    """No sinf, expf and the like in the wrapper or the vendored bass, so the
    browser's module renders the same samples as the native build."""
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    banned = {f + s for f in ("sin", "cos", "tan", "exp", "exp2", "log", "log2", "log10", "pow",
                               "tanh", "atan", "atan2", "sinh", "cosh", "sqrt") for s in ("", "f")}
    for obj in (ENGINES / "build" / "our" / "src" / "acid_bass.o",
                ENGINES / "build" / "gpl" / "fm1-x0x" / "dsp" / "bass303.o"):
        syms = subprocess.run([nm, "-u", str(obj)], check=True, capture_output=True, text=True).stdout
        names = {line.split()[-1].lstrip("_") for line in syms.splitlines() if line.strip()}
        assert not names & banned, (obj.name, names & banned)
        assert not names & {"malloc", "free", "calloc", "realloc", "printf", "fprintf", "puts"}, obj.name
