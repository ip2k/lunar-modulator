"""Drums (engines/src/drums.cc, drum_voices.h; engines/README.md, "Drums"):
a 16-pad kit on MIDI notes 36-51.

Every pad of both kits and every model sounds cleanly; the kicks, toms and
hats have the character their voicings promise (a long deep kick, a short
swept punchy one, toms rising with their keys, short closed and long open
hats); the hats choke one another; velocity, Accent and the kit's knobs act;
twelve voices hold, a thirteenth pad steals; notes outside the pads and
note-offs do nothing; the per-pad knobs edit only the focused pad, a pad
given another model plays that model's own voicing, and Kit and Model are
read when a pad is struck. Per-note offsets as the other engines take them
(tests/test_engine_note_params.py), on the pads' notes. The output does not
depend on the host's block size or on what instance memory held, two pads
struck together are the two struck apart (each pad's noise is its own), and
the engine calls no transcendental function from libm.
"""
import json
import math
import shutil
import struct
import subprocess
import wave

import pytest

from tests.engine_helpers import (ENGINES, RATE, cents, render, renderer,  # noqa: F401
                                  rms)

KICK, RIM, SNARE, CLAP, SNARE2, LOW_TOM, CLOSED_HH, FLOOR_TOM, PEDAL_HH, MID_TOM, OPEN_HH, \
    LOW_MID, HIGH_MID, CRASH, HIGH_TOM, RIDE = range(36, 52)
TOMS = [LOW_TOM, FLOOR_TOM, MID_TOM, LOW_MID, HIGH_MID, HIGH_TOM]
MODELS = ["Kit", "Analog Drum", "Punch Drum", "Snare", "Snap Snare", "Hat", "Ring Hat",
          "Cymbal", "Clap", "Rim", "Cowbell"]


def run(renderer, tmp_path, name, params=(), notes=(), extra=(), seconds=0.8, engine="drums"):
    """(summary, WAV bytes, left channel as int16)."""
    s, _, wav = render(renderer, tmp_path, engine, params=list(params), notes=list(notes),
                       seconds=seconds, name=name, extra=list(extra))
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    left = [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), 4)]
    assert s["nonfinite"] == 0
    return s, wav.read_bytes(), left


def window_rms(x, t0, t1):
    seg = x[int(t0 * RATE):int(t1 * RATE)]
    return math.sqrt(sum(v * v for v in seg) / max(1, len(seg)))


def decay_time(x, db, win=0.005):
    """Seconds from the loudest 5 ms window until the level is db under it."""
    n = int(win * RATE)
    levels = [math.sqrt(sum(v * v for v in x[i:i + n]) / n) for i in range(0, len(x) - n, n)]
    peak = max(levels)
    top = levels.index(peak)
    floor = peak * 10 ** (-db / 20)
    return next((i - top for i in range(top, len(levels)) if levels[i] < floor), len(levels)) * win


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


# ---- the registry and the pads -----------------------------------------------------------

def test_drums_is_a_twelve_voice_pad_kit(listing):
    e = listing["drums"]
    assert e["name"] == "Drums" and e["kind"] == "sound" and e["max_voices"] == 12
    assert e["pads"] == {"first": 36, "count": 16} and e["per_note"]
    assert "Plaits" in e["credits"] and "Emilie Gillet" in e["credits"]
    params = {p["name"]: p for p in e["params"]}
    assert params["Pad"]["names"][0] == "1 Kick" and params["Pad"]["names"][15] == "16 Ride"
    assert params["Model"]["names"] == MODELS
    assert params["Kit"]["names"] == ["Deep", "Punch"]
    assert [p["page"] for p in e["params"]] == [0] * 4 + [1] * 4 + [2] * 4
    assert e["params"][-1]["name"] == "Volume"           # the last page ends with it, as elsewhere


def test_twelve_parameters_fit_the_modulation_records(listing):
    """Four sound units of the engine with the most parameters and ten of
    the largest effects share the modulation runtime's 180 records
    (tests/test_engines_mod_runtime.py): twelve, as many as Macro Heavy."""
    assert len(listing["drums"]["params"]) == 12


def test_only_the_kits_say_they_are_pad_kits(listing):
    """The pad property (fm1_engine_t.pad_first_note, pad_count) is additive:
    Sophie and Drums declare 16 pads from note 36, every other engine none."""
    kits = {i: e["pads"] for i, e in listing.items() if e["pads"]}
    assert kits == {"sw-sophie": {"first": 36, "count": 16}, "drums": {"first": 36, "count": 16}}


@pytest.mark.parametrize("kit", [0, 1])
def test_every_pad_of_both_kits_sounds_cleanly(renderer, tmp_path, kit):
    for key in range(36, 52):
        s, _, x = run(renderer, tmp_path, f"k{kit}-{key}", [f"Kit={kit}"], [f"0:{key}:127:0.1"],
                      seconds=0.6)
        assert s["raw_clipped"] == 0 and 0.05 < s["raw_peak"] < 0.9, (kit, key, s["raw_peak"])


@pytest.mark.parametrize("model", range(1, len(MODELS)))
def test_every_model_sounds_on_any_pad(renderer, tmp_path, model):
    """Every model on the kick's pad and on a tom's. A pad given a model
    other than its kit's plays that model's own voicing, so the cowbell
    (which draws no noise) is the same on both."""
    outs = []
    for pad, key in ((0, KICK), (12, HIGH_MID)):
        s, _, x = run(renderer, tmp_path, f"m{model}-{pad}", [f"Pad={pad}", f"Model={model}"],
                      [f"0:{key}:127:0.1"], seconds=0.5)
        assert s["raw_clipped"] == 0 and 0.05 < s["raw_peak"] < 0.9, (model, pad)
        outs.append(x)
    if MODELS[model] == "Cowbell":   # no noise, and the model's own voicing on both pads
        assert outs[0] == outs[1]


def test_notes_outside_the_pads_and_note_offs_do_nothing(renderer, tmp_path):
    _, silent, _ = run(renderer, tmp_path, "out", notes=["0:35:127:0.2", "0.1:52:127:0.2",
                                                         "0.2:60:127:0.2"], seconds=0.5)
    _, none, _ = run(renderer, tmp_path, "none", seconds=0.5)
    assert silent == none
    _, short, _ = run(renderer, tmp_path, "short", notes=[f"0:{CRASH}:100:0.05"], seconds=1.0)
    _, long_, _ = run(renderer, tmp_path, "long", notes=[f"0:{CRASH}:100:0.9"], seconds=1.0)
    assert short == long_, "a hit rings out for its decay whatever the note's length"


# ---- the sounds' character ---------------------------------------------------------------

def test_deep_kick_is_low_and_long(renderer, tmp_path):
    _, _, x = run(renderer, tmp_path, "deep", notes=[f"0:{KICK}:127:0.1"], seconds=3.0)
    assert zc_hz(x, 0.1, 0.5) == pytest.approx(55.0, rel=0.03)       # the voicing's A1
    assert decay_time(x, 40) > 1.0


def test_punch_kick_sweeps_down_and_is_short(renderer, tmp_path):
    _, _, x = run(renderer, tmp_path, "punch", ["Kit=1"], [f"0:{KICK}:127:0.1"], seconds=2.0)
    early, late = zc_hz(x, 0.005, 0.045), zc_hz(x, 0.08, 0.2)
    assert late == pytest.approx(58.3, rel=0.03) and early > 1.3 * late
    assert decay_time(x, 40) < 0.5


def test_sweep_moves_the_deep_kicks_pitch_drop(renderer, tmp_path):
    def drop(sweep):
        _, _, x = run(renderer, tmp_path, f"s{sweep}", [f"Sweep={sweep}", "Snap=0"],
                      [f"0:{KICK}:127:0.1"], seconds=0.6)
        return zc_hz(x, 0.01, 0.06) / zc_hz(x, 0.3, 0.5)
    assert drop(1) > drop(0.5) > drop(0)


@pytest.mark.parametrize("kit", [0, 1])
def test_toms_rise_with_their_keys(renderer, tmp_path, kit):
    """Six toms, a fourth above their keys: 41 sounds as 46 (116.5 Hz)."""
    for key in TOMS:
        _, _, x = run(renderer, tmp_path, f"t{key}", [f"Kit={kit}"], [f"0:{key}:127:0.1"],
                      seconds=0.5)
        want = 440.0 * 2 ** ((key + 5 - 69) / 12)
        assert abs(cents(zc_hz(x, 0.08, 0.2), want)) < 35, (kit, key)


def test_closed_hat_short_open_hat_long(renderer, tmp_path):
    times = {}
    for key in (CLOSED_HH, PEDAL_HH, OPEN_HH):
        _, _, x = run(renderer, tmp_path, f"h{key}", notes=[f"0:{key}:127:0.1"], seconds=2.0)
        times[key] = decay_time(x, 40)
    assert times[CLOSED_HH] < 0.12 < times[PEDAL_HH] < 0.4 < times[OPEN_HH]


def test_cowbell_rings_at_its_two_pitches(renderer, tmp_path):
    """The cowbell model: two squares at 540 and 800 Hz (Werner et al.); the
    band-pass near 880 Hz leaves the upper one the clearer."""
    _, _, x = run(renderer, tmp_path, "cb", ["Pad=0", "Model=10"], [f"0:{KICK}:127:0.1"],
                  seconds=1.0)
    assert zc_hz(x, 0.05, 0.3) == pytest.approx(800.0, rel=0.02)


# ---- choke groups ------------------------------------------------------------------------

@pytest.mark.parametrize("cutter", [CLOSED_HH, PEDAL_HH])
def test_closed_and_pedal_hats_choke_the_open_one(renderer, tmp_path, cutter):
    """The open hat alone rings on past 0.4 s; struck under a closed or pedal
    hat it is cut within 4 ms of the hit, so only the short hat is left."""
    _, _, open_ = run(renderer, tmp_path, "open", notes=[f"0:{OPEN_HH}:127:0.1"], seconds=1.0)
    _, _, cut = run(renderer, tmp_path, "cut", notes=[f"0:{OPEN_HH}:127:0.1",
                                                      f"0.2:{cutter}:100:0.1"], seconds=1.0)
    _, _, alone = run(renderer, tmp_path, "alone", notes=[f"0.2:{cutter}:100:0.1"], seconds=1.0)
    assert window_rms(open_, 0.4, 0.6) > 30
    assert window_rms(cut, 0.4, 0.6) < 0.2 * window_rms(open_, 0.4, 0.6)
    # From 5 ms after the hit, the choked hat is gone: only the short hat sounds.
    t = int(0.2 * RATE) + int(0.005 * RATE) + 64
    assert max(abs(a - b) for a, b in zip(cut[t:], alone[t:])) <= 2


def test_only_the_hats_choke(renderer, tmp_path):
    """The open hat's pad stays in the hats' group whatever model it plays
    (a Hat by its Model in the Punch kit, whose own is the Ring Hat); a crash
    under a closed hat, or a ride under the crash, is never cut: the render
    is the two pads rendered apart, summed."""
    notes = [f"0:{OPEN_HH}:127:0.1", f"0.2:{CLOSED_HH}:100:0.1"]
    params = ["Kit=1", "Pad=10", "Model=5", "Volume=0.3"]
    _, _, cut = run(renderer, tmp_path, "cut", params, notes, seconds=1.0)
    _, _, alone = run(renderer, tmp_path, "alone", params, notes[1:], seconds=1.0)
    t = int(0.2 * RATE) + int(0.005 * RATE) + 64
    assert max(abs(a - b) for a, b in zip(cut[t:], alone[t:])) <= 2
    for pair in ([f"0:{CRASH}:127:0.1", f"0.2:{CLOSED_HH}:100:0.1"],
                 [f"0:{CRASH}:127:0.1", f"0.3:{RIDE}:100:0.1"]):
        quiet = ["Volume=0.3"]
        _, _, both = run(renderer, tmp_path, "both", quiet, pair, seconds=1.0)
        _, _, a = run(renderer, tmp_path, "a", quiet, pair[:1], seconds=1.0)
        _, _, b = run(renderer, tmp_path, "b", quiet, pair[1:], seconds=1.0)
        assert max(abs(x - (y + z)) for x, y, z in zip(both, a, b)) <= 3


# ---- velocity and the kit's knobs ---------------------------------------------------------

def test_velocity_and_accent(renderer, tmp_path):
    """At Accent 0 velocity changes nothing; at 0.5 (the default) a softer hit
    is quieter, and more so at 1."""
    def peak(vel, accent):
        s, _, _ = run(renderer, tmp_path, f"v{vel}-{accent}", [f"Accent={accent}"],
                      [f"0:{SNARE}:{vel}:0.1"], seconds=0.4)
        return s["raw_peak"]
    assert peak(40, 0) == peak(127, 0)
    assert peak(40, 0.5) < 0.75 * peak(127, 0.5)
    assert peak(40, 1) < 0.5 * peak(40, 0.5)


def test_volume_level_and_decay(renderer, tmp_path):
    def kick(*params, seconds=2.0):
        return run(renderer, tmp_path, "-".join(params) or "plain", list(params),
                   [f"0:{KICK}:127:0.1"], seconds=seconds)
    base, _, x = kick()
    half, _, _ = kick("Volume=0.35")
    assert half["raw_peak"] == pytest.approx(base["raw_peak"] / 2, rel=0.01)
    lvl, _, _ = kick("Level=0.4")
    assert lvl["raw_peak"] == pytest.approx(base["raw_peak"] / 2, rel=0.01)
    _, _, short = kick("Decay=0")
    _, _, long_ = kick("Decay=1", seconds=4.0)
    assert decay_time(short, 40) < 0.5 * decay_time(x, 40) < decay_time(long_, 40)


def test_tune_and_bend_move_a_pad(renderer, tmp_path):
    _, _, x = run(renderer, tmp_path, "t0", notes=[f"0:{LOW_TOM}:127:0.1"], seconds=0.5)
    _, _, up = run(renderer, tmp_path, "t7", ["Tune=7"], notes=[f"0:{KICK}:127:0.1"], seconds=0.5)
    _, _, k = run(renderer, tmp_path, "k", notes=[f"0:{KICK}:127:0.1"], seconds=0.5)
    assert cents(zc_hz(up, 0.1, 0.4), zc_hz(k, 0.1, 0.4)) == pytest.approx(700, abs=15)
    _, _, bent = run(renderer, tmp_path, "b", notes=[f"0:{LOW_TOM}:127:0.1"],
                     extra=["--bend", "0:12"], seconds=0.5)
    assert cents(zc_hz(bent, 0.08, 0.2), zc_hz(x, 0.08, 0.2)) == pytest.approx(1200, abs=15)


# ---- voices --------------------------------------------------------------------------------

def long_decays(keys):
    """Each pad's Decay at 1 (Pad focuses it first), so its hits ring long."""
    return sum(([f"Pad={k - 36}", "Decay=1"] for k in keys), [])


def test_twelve_voices_then_a_steal(renderer, tmp_path):
    """Twelve long pads hold together; a thirteenth steals the oldest (the
    kick) and sounds; the bus limiter keeps the sum under full scale."""
    pads = [KICK, SNARE, CLAP, SNARE2, LOW_TOM, FLOOR_TOM, MID_TOM, LOW_MID, HIGH_MID,
            CRASH, HIGH_TOM, RIDE]
    held = [f"{0.01 * i:.2f}:{k}:110:0.1" for i, k in enumerate(pads)]
    s, _, _ = run(renderer, tmp_path, "loud", long_decays(pads), held, seconds=1.0)
    assert s["peak"] <= 0.98 + 1e-6
    params = long_decays(pads) + ["Volume=0.1"]   # under the bus limiter: renders add up
    _, _, full = run(renderer, tmp_path, "twelve", params, held, seconds=1.0)
    _, _, stolen = run(renderer, tmp_path, "steal", params, held + [f"0.5:{RIM}:127:0.1"],
                       seconds=1.0)
    _, _, others = run(renderer, tmp_path, "others", params, held[1:], seconds=1.0)
    t = int(0.5 * RATE)
    assert stolen[:t - 64] == full[:t - 64]
    # What the steal leaves beside the eleven others: the kick before the
    # rim's hit, the rim after it, then nothing: the kick is gone.
    diff = [a - b for a, b in zip(stolen, others)]
    assert window_rms(diff, 0.3, 0.45) > 100
    assert window_rms(diff, 0.502, 0.53) > 20
    assert window_rms(diff, 0.7, 0.9) < 2


def test_a_pad_struck_again_sounds_in_its_own_voice(renderer, tmp_path):
    """Struck 24 times while eleven other pads ring, the kick never takes a
    second voice: the other pads are never stolen (they render as without
    the repeats, less the kick's own sound)."""
    pads = [SNARE, CLAP, SNARE2, LOW_TOM, FLOOR_TOM, MID_TOM, LOW_MID, HIGH_MID, CRASH,
            HIGH_TOM, RIDE]
    held = [f"0:{k}:110:0.1" for k in pads]
    kicks = [f"{0.02 + 0.02 * i:.2f}:{KICK}:100:0.01" for i in range(24)]
    params = long_decays(pads + [KICK]) + ["Volume=0.1"]   # under the bus limiter: renders add up
    _, _, a = run(renderer, tmp_path, "a", params, held + kicks, seconds=0.8)
    _, _, b = run(renderer, tmp_path, "b", params, held, seconds=0.8)
    _, _, c = run(renderer, tmp_path, "c", params, kicks, seconds=0.8)
    assert max(abs(x - (y + z)) for x, y, z in zip(a, b, c)) <= 3


def test_voices_end_and_the_output_returns_to_zero(renderer, tmp_path):
    _, _, x = run(renderer, tmp_path, "end", notes=[f"0:{k}:127:0.1" for k in (RIM, CLAP,
                                                                           CLOSED_HH)],
                  seconds=1.5)
    assert not any(x[int(1.2 * RATE):])


# ---- parameters ----------------------------------------------------------------------------

def test_per_pad_knobs_edit_only_the_focused_pad(renderer, tmp_path):
    """With Pad on the snare, Tone, Decay and Tune turned (before the kick
    and while it rings) leave the kick as it was; on the kick they change it."""
    turns = ["--param-at", "0:Pad=2", "--param-at", "0:Tone=0.9", "--param-at", "0.2:Decay=0.1",
             "--param-at", "0.3:Tune=-12"]
    _, kick, _ = run(renderer, tmp_path, "kick", notes=[f"0:{KICK}:127:0.1"], seconds=0.6)
    _, kick_t, _ = run(renderer, tmp_path, "kick-t", notes=[f"0:{KICK}:127:0.1"], extra=turns,
                       seconds=0.6)
    assert kick_t == kick
    on_kick = [t.replace("Pad=2", "Pad=0") for t in turns]
    _, moved, _ = run(renderer, tmp_path, "kick-m", notes=[f"0:{KICK}:127:0.1"], extra=on_kick,
                      seconds=0.6)
    assert moved != kick


def test_a_ramp_stays_on_its_pad_when_pad_moves(renderer, tmp_path):
    """A Decay turn on the ringing kick ramps (2.5 ms); moving Pad on at once
    does not stop it or move it to the new pad."""
    turn = ["--param-at", "0.2:Decay=0.1"]
    _, a, _ = run(renderer, tmp_path, "a", notes=[f"0:{KICK}:127:0.1"], extra=turn, seconds=0.5)
    _, b, _ = run(renderer, tmp_path, "b", notes=[f"0:{KICK}:127:0.1"],
                  extra=turn + ["--param-at", "0.2:Pad=5"], seconds=0.5)
    assert a == b


def test_kit_and_model_are_read_when_a_pad_is_struck(renderer, tmp_path):
    """A sounding hit keeps the kit and model it started with (LATCH); the
    next hit takes the new ones."""
    one = [f"0:{KICK}:127:0.1"]
    _, deep, _ = run(renderer, tmp_path, "deep", notes=one, seconds=0.6)
    _, kept, _ = run(renderer, tmp_path, "kept", notes=one,
                     extra=["--param-at", "0.1:Kit=1", "--param-at", "0.15:Model=10"], seconds=0.6)
    assert kept == deep
    _, punch, _ = run(renderer, tmp_path, "punch", ["Kit=1"], one, seconds=0.6)
    _, later, _ = run(renderer, tmp_path, "later", notes=[f"0.3:{KICK}:127:0.1"],
                      extra=["--param-at", "0.1:Kit=1"], seconds=0.9)
    _, later_p, _ = run(renderer, tmp_path, "later-p", ["Kit=1"], [f"0.3:{KICK}:127:0.1"],
                        seconds=0.9)
    assert later == later_p and punch != deep


def test_drive_is_clean_at_zero_and_saturates(renderer, tmp_path):
    s0, _, _ = run(renderer, tmp_path, "d0", notes=[f"0:{SNARE}:127:0.1"], seconds=0.4)
    s1, _, _ = run(renderer, tmp_path, "d1", ["Pad=2", "Drive=1"], [f"0:{SNARE}:127:0.1"],
                   seconds=0.4)
    assert s1["rms"] > 1.5 * s0["rms"]


# ---- determinism, memory, noise, libm ------------------------------------------------------

def t(frame):
    return 0.0 if frame == 0 else (frame - 0.5) / RATE


GROOVE = [f"{t(448 * i):.9f}:{k}:{70 + 9 * (i % 6)}:0.05"
          for i, k in enumerate([KICK, CLOSED_HH, SNARE, CLOSED_HH, KICK, OPEN_HH, CLAP,
                                 PEDAL_HH, LOW_TOM, RIM, CRASH, HIGH_TOM, KICK, RIDE])]
TURNS = ["--param-at", f"{t(1344):.9f}:Pad=6", "--param-at", f"{t(1344):.9f}:Tone=0.8",
         "--param-at", f"{t(2240):.9f}:Volume=0.5", "--param-at", f"{t(3136):.9f}:Kit=1",
         "--param-at", f"{t(4032):.9f}:Pad=0", "--param-at", f"{t(4032):.9f}:Model=2",
         "--param-at", f"{t(4480):.9f}:Sweep=0.9", "--bend", f"{t(4928):.9f}:3",
         "--note-param-at", f"{t(5376):.9f}:{KICK}:Decay=-0.3",
         "--note-pitch-at", f"{t(5376):.9f}:{KICK}:-5"]


def test_output_does_not_depend_on_the_host_block(renderer, tmp_path):
    outs = [run(renderer, tmp_path, f"b{n}", notes=GROOVE, extra=TURNS + ["--frames", n],
                seconds=0.4)[1] for n in ("1", "7", "64")]
    assert outs[1] == outs[0] and outs[2] == outs[0]


def test_any_initial_memory(renderer, tmp_path):
    outs = [run(renderer, tmp_path, f"f{fill}", notes=GROOVE, extra=TURNS + ["--fill", fill],
                seconds=0.4)[1] for fill in ("0", "0xA5", "0xFF")]
    assert outs[1] == outs[0] and outs[2] == outs[0]


def test_two_pads_together_are_the_two_apart(renderer, tmp_path):
    """Each pad draws its noise from its own generator, so the snare and the
    hats struck together sound as each struck alone, summed (3 LSB of
    rounding), however their noise draws interleave."""
    a, b = [f"0:{SNARE}:127:0.1", f"0.05:{CLAP}:100:0.1"], [f"0:{OPEN_HH}:110:0.1",
                                                           f"0.02:{CRASH}:90:0.1"]
    quiet = ["Volume=0.3"]                   # under the bus limiter, so renders add up
    _, _, both = run(renderer, tmp_path, "both", quiet, a + b, seconds=0.5)
    _, _, x = run(renderer, tmp_path, "a", quiet, a, seconds=0.5)
    _, _, y = run(renderer, tmp_path, "b", quiet, b, seconds=0.5)
    assert max(abs(s - (p + q)) for s, p, q in zip(both, x, y)) <= 3


def test_instance_size(renderer, tmp_path):
    s, _, _ = run(renderer, tmp_path, "size", seconds=0.01)
    assert s["instance_bytes"] < 12_000      # 7,616 on 64-bit and 32-bit when written


def test_no_transcendental_libm_calls():
    """No sinf, expf, powf and the like in the engine's object, so the
    browser's module renders the same samples as the native build (sqrtf is
    correctly rounded everywhere, and the Plaits classes take it twice a
    block). Our own drum_voices.h is inline in drums.o."""
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    obj = ENGINES / "build" / "our" / "src" / "drums.o"
    syms = subprocess.run([nm, "-u", str(obj)], check=True, capture_output=True, text=True).stdout
    names = {line.split()[-1].lstrip("_") for line in syms.splitlines() if line.strip()}
    banned = {f + s for f in ("sin", "cos", "tan", "exp", "exp2", "log", "log2", "log10", "pow",
                               "tanh", "atan", "atan2", "sinh", "cosh") for s in ("", "f")}
    assert not names & banned, names & banned


# ---- per-note offsets ----------------------------------------------------------------------

def poly(listing):
    return [p for p in listing["drums"]["params"] if "poly" in p["flags"]]


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def exact(x):
    return f"{f32(x):.9g}"


def test_every_float_is_poly(listing):
    assert [p["name"] for p in poly(listing)] == [p["name"] for p in listing["drums"]["params"]
                                                  if p["type"] == 0]


def test_zero_offsets_are_a_no_op(renderer, tmp_path, listing):
    notes = [f"{0.03 * i:.2f}:{k}:{80 + 5 * i}:0.1" for i, k in enumerate([KICK, SNARE, OPEN_HH,
                                                                           CRASH, CLAP, LOW_TOM])]
    extra = []
    for i, n in enumerate(notes):
        key = n.split(":")[1]
        for p in poly(listing):
            extra += ["--note-param-at", f"{0.03 * i:.2f}:{key}:{p['name']}={'-0' if i % 2 else '0'}"]
        extra += ["--note-pitch-at", f"0.25:{key}:0"]
    _, plain, _ = run(renderer, tmp_path, "plain", notes=notes)
    _, zero, _ = run(renderer, tmp_path, "zero", notes=notes, extra=extra)
    assert zero == plain


@pytest.mark.parametrize("key,pad", [(KICK, 0), (OPEN_HH, 10), (CLAP, 3)])
def test_an_offset_on_a_lone_hit_is_a_base_change(renderer, tmp_path, listing, key, pad):
    """From the hit, each POLY parameter's offset is the pad's (or the kit's)
    base moved by as much, byte for byte; bases set before the hit apply at
    once (no voice sounds), so no ramp runs on either side."""
    for p in poly(listing):
        span = p["max"] - p["min"]
        x = span / 4 if p["def"] + span / 4 <= p["max"] else -span / 4
        _, a, _ = run(renderer, tmp_path, "a", [f"Pad={pad}"], [f"0:{key}:110:0.1"],
                      ["--note-param-at", f"0:{key}:{p['name']}={exact(x)}"], seconds=0.5)
        _, b, _ = run(renderer, tmp_path, "b", [f"Pad={pad}", f"{p['name']}={exact(p['def'] + x)}"],
                      [f"0:{key}:110:0.1"], seconds=0.5)
        assert a == b, p["name"]


def test_a_pitch_offset_on_a_lone_hit_is_a_bend(renderer, tmp_path):
    for semis in (7, -12, 0.5):
        _, a, _ = run(renderer, tmp_path, "a", notes=[f"0:{LOW_TOM}:110:0.1"],
                      extra=["--note-pitch-at", f"0:{LOW_TOM}:{semis}",
                             "--note-pitch-at", f"0.2:{LOW_TOM}:-3"])
        _, b, _ = run(renderer, tmp_path, "b", notes=[f"0:{LOW_TOM}:110:0.1"],
                      extra=["--bend", f"0:{semis}", "--bend", "0.2:-3"])
        assert a == b, semis


def test_an_offset_reaches_only_its_hit(renderer, tmp_path):
    a, b = f"0:{LOW_TOM}:110:0.1", f"0:{HIGH_TOM}:90:0.1"
    offs = ["--note-param-at", f"0:{LOW_TOM}:Tone=0.4", "--note-pitch-at", f"0.1:{LOW_TOM}:5"]
    _, _, both = run(renderer, tmp_path, "both", notes=[a, b], extra=offs)
    _, _, a_moved = run(renderer, tmp_path, "a1", notes=[a], extra=offs)
    _, _, a_plain = run(renderer, tmp_path, "a0", notes=[a])
    _, _, b_plain = run(renderer, tmp_path, "b0", notes=[b])
    assert max(abs(s - (p + q)) for s, p, q in zip(both, a_moved, b_plain)) <= 3
    assert max(abs(p - q) for p, q in zip(a_moved, a_plain)) > 300


def test_a_new_hit_starts_at_no_offset(renderer, tmp_path):
    notes = [f"0:{LOW_TOM}:110:0.1", f"0.3:{LOW_TOM}:110:0.1"]
    first = ["--note-param-at", f"0:{LOW_TOM}:Decay=0.3", "--note-pitch-at", f"0:{LOW_TOM}:3"]
    _, a, _ = run(renderer, tmp_path, "a", notes=notes, extra=first)
    _, b, _ = run(renderer, tmp_path, "b", notes=notes,
                  extra=first + ["--note-param-at", f"0.3:{LOW_TOM}:Decay=0",
                                 "--note-pitch-at", f"0.3:{LOW_TOM}:0"])
    assert a == b


def test_nan_inf_offsets_and_ignored_indices(renderer, tmp_path):
    note = [f"0:{SNARE}:110:0.1"]
    _, plain, _ = run(renderer, tmp_path, "plain", notes=note)
    _, nan, _ = run(renderer, tmp_path, "nan", notes=note,
                    extra=["--note-param-at", f"0:{SNARE}:Tone=nan",
                           "--note-pitch-at", f"0:{SNARE}:nan"])
    assert nan == plain
    for value, end in (("inf", 1), ("-inf", 0)):
        _, a, _ = run(renderer, tmp_path, "a", notes=note,
                      extra=["--note-param-at", f"0:{SNARE}:Tone={value}"])
        _, b, _ = run(renderer, tmp_path, "b", ["Pad=2", f"Tone={end}"], note)
        assert a == b, value
    ignored = []
    for idx in ("#0", "#8", "#9", "#12", "#999", "#65534"):   # Pad, Model, Kit, past the table
        ignored += ["--note-param-at", f"0:{SNARE}:{idx}=0.7"]
    ignored += ["--note-param-at", f"0:60:Tone=0.4", "--note-pitch-at", f"0:{RIDE}:12"]
    _, a, _ = run(renderer, tmp_path, "ign", notes=note, extra=ignored)
    assert a == plain


@pytest.mark.parametrize("sign", ["inf", "-inf"])
def test_extreme_values_render_finite(renderer, tmp_path, listing, sign):
    """Every POLY parameter pinned at an end, the pitch at +/-48 over a +/-48
    bend, every model on its pad and both kits; also every parameter at its
    ends set on the kick's pad and the kit, with all sixteen pads struck."""
    for kit in (0, 1):
        for model in range(len(MODELS)):
            extra = ["--bend", f"0:{'' if sign == 'inf' else '-'}48", "--frames", "7",
                     "--note-pitch-at", f"0:{KICK}:{sign}"]
            for p in poly(listing):
                extra += ["--note-param-at", f"0:{KICK}:{p['name']}={sign}"]
            s, _, _ = run(renderer, tmp_path, "x", [f"Kit={kit}", f"Model={model}"],
                          [f"0:{KICK}:127:0.1"], extra, seconds=0.3)
            assert s["nonfinite"] == 0, (kit, model)
        ends = [f"{p['name']}={p['max'] if sign == 'inf' else p['min']}"
                for p in listing["drums"]["params"] if p["type"] == 0]
        s, _, _ = run(renderer, tmp_path, "y", [f"Kit={kit}", *ends],
                      [f"{0.01 * i:.2f}:{k}:127:0.1" for i, k in enumerate(range(36, 52))],
                      seconds=0.5)
        assert s["nonfinite"] == 0, kit
