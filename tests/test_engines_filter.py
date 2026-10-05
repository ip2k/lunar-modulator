"""Tests for Filter, the multimode filter effect (engines/src/fx_filter.cc,
parameters in engines/README.md, "Filter").

Through fm1-render: registration and pages, the host contracts for every
type (deterministic renders, any block size, any prior memory contents, any
parameter value, NaN included, bad input guarded and not latched, silence in
gives silence out), Mix and Level, and a chain after an engine. Through
fm1-filter-test (engines/test/filter_test.cc): parameters and types changed
while audio runs at four host rates, the glide and the Type crossfade,
frequency responses of every type and mode, self-oscillation pitch and
level, Drive's harmonics, and the tails flushing to exact silence.
"""
import json
import math
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, brightness, run

TOOL = ENGINES / "build" / "fm1-filter-test"
LSB = 1 / 32767.0
TYPES = ["SVF", "Ladder", "Diode", "Sallen-Key", "SK Mixed", "Comb", "Formant"]

# Every parameter away from its default except Type, Mix and Level; nothing
# near self-oscillation, so a disturbance dies away.
BUSY = ["Cutoff=900", "Resonance=0.6", "Drive=0.4", "Mode=0.7", "Morph=0.3"]


def fx(*params):
    return [("filter", list(params))]


def cli(*params):
    args = ["--fx", "filter"]
    for p in params:
        args += ["--fx-param", p]
    return args


def busy(t):
    return [f"Type={t}", *BUSY]


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def gains(tool, case):
    return {hz: db for hz, db in tool["response"][case]}


def test_filter_is_registered(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    e = {x["id"]: x for x in json.loads(out)}["filter"]
    assert (e["name"], e["kind"], e["max_voices"]) == ("Filter", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Zavalishin" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Type", "Cutoff", "Resonance", "Drive"], ["Mode", "Morph", "Mix", "Level"]]
    t = e["params"][0]
    assert t["type"] == 1 and t["names"] == TYPES
    # Generic names: what each circuit is, never a maker's, a person's or a
    # part number (the filters they follow are credited in the README), and
    # short enough for the screen: the Type row leaves 14 characters for its
    # value, the ALGORITHM popup 18.
    assert all(len(n) <= 10 for n in TYPES)
    makers = ("korg", "k35", "ms-20", "ms20", "steiner", "parker", "synthacon", "moog", "roland",
              "303", "oberheim")
    assert not any(m in n.lower() for n in TYPES for m in makers)
    assert all(len(p["name"]) <= 12 for p in e["params"])
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])
    cutoff = e["params"][1]
    assert (cutoff["min"], cutoff["max"], cutoff["unit"]) == (20, 18000, "hz")


def test_instance_size(renderer, tmp_path, tool):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    # 688 bytes of state and two delay lines of fs / 20 Hz + 4 floats for Comb.
    assert s["fx_bytes"] == [18368]
    sizes = {rate: size for rate, ok, size in tool["rates"] if ok}
    assert sizes == {"8000": 3920, "44118": 18368, "48000": 19920, "96000": 39120,
                     "384000": 154320}
    assert all(size % 16 == 0 for size in sizes.values())


# --- host contracts, every type ----------------------------------------------

def test_rendering_is_deterministic(renderer, tmp_path):  # noqa: F811
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*busy(4)), name="a")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*busy(4)), name="b")
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("t", range(len(TYPES)))
def test_block_size_does_not_change_the_output(renderer, tmp_path, t):  # noqa: F811
    wavs = []
    for frames in ("64", "7", "1"):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.4, fx=fx(*busy(t)),
                           name=f"f{frames}", extra=["--frames", frames])
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


@pytest.mark.parametrize("t", range(len(TYPES)))
def test_output_ignores_initial_memory(renderer, tmp_path, t):  # noqa: F811
    wavs = []
    for fill in ("0", "0xA5", "0xFF"):
        s, _, wav = render(renderer, tmp_path, input="noise", seconds=0.4, fx=fx(*busy(t)),
                           name=f"fill{fill}", extra=["--fill", fill])
        assert s["nonfinite"] == 0
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


@pytest.mark.parametrize("value,same_as", [
    ("nan", None),            # NaN is the default (fm1_param_clamp)
    ("1e9", "max"),
    ("-1e9", "min"),
    ("inf", "max"),
])
def test_out_of_range_parameters_clamp(renderer, tmp_path, value, same_as):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    params = {x["id"]: x for x in json.loads(out)}["filter"]["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("t", range(len(TYPES)))
def test_silence_in_is_silence_out(renderer, tmp_path, t):  # noqa: F811
    # From rest, nothing excites a filter, even one set to self-oscillate.
    hot = [f"Type={t}", "Resonance=1", "Drive=1", "Mode=1.5", "Morph=0.6", "Level=2"]
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*hot))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("t", range(len(TYPES)))
@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, t, bad):  # noqa: F811
    # The input guard reads NaN as 0 and clamps everything else to +/-16, the
    # dry path included, so no state is poisoned: 0.7 s after the fault ends
    # the output is the fault-free output again, within one LSB.
    base = ["--input", "noise", "--seconds", "1.5", *cli(*busy(t))]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.2..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    tail = slice(int(1.2 * RATE), None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= LSB


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*busy(2)),
                     extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


def test_mix_zero_passes_the_input_through(renderer, tmp_path):  # noqa: F811
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=fx(*busy(4), "Mix=0", "Level=1.5"), name="dry")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


def test_level_scales_the_wet_signal(renderer, tmp_path):  # noqa: F811
    _, full, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="full",
                        fx=fx("Type=0", "Level=1"))
    _, half, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="half",
                        fx=fx("Type=0", "Level=0.5"))
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="none",
                     fx=fx("Type=0", "Level=0"))
    assert rms(half, 0.2, 1.0) / rms(full, 0.2, 1.0) == pytest.approx(0.5, rel=0.002)
    assert s["raw_peak"] == 0.0                          # Mix 1, Level 0: nothing


def test_mix_blends_dry_and_wet(renderer, tmp_path):  # noqa: F811
    common = ["Type=1", "Cutoff=600", "Resonance=0.5"]
    _, dry, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name="m0",
                       fx=fx(*common, "Mix=0"))
    _, wet, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name="m1",
                       fx=fx(*common, "Mix=1"))
    _, mid, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name="m5",
                       fx=fx(*common, "Mix=0.5"))
    worst = max(abs(m - 0.5 * (d + w)) for m, d, w in zip(mid, dry, wet))
    assert worst <= 1.5 * LSB


@pytest.mark.parametrize("t", range(5))
def test_cutoff_darkens_every_low_pass(renderer, tmp_path, t):  # noqa: F811
    bright = []
    for hz in ("8000", "1500", "300"):
        _, left, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name=f"c{hz}",
                            fx=fx(f"Type={t}", f"Cutoff={hz}", "Resonance=0.2"))
        bright.append(brightness(left, 0.1, 0.5))
    assert bright[0] > bright[1] > bright[2]
    assert bright[2] < 0.3 * bright[0]


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.5",
         "--note", "0:52:100:0.5", "--seconds", "1.5", *cli("Type=2", "Resonance=0.8"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["filter", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4


# --- fm1-filter-test: parameters while audio runs ----------------------------

def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 10 s of noise per host rate, with bursts at the guard's limit (16);
    # between blocks of 1-64 frames, up to two parameters (Type included)
    # jump to their minimum, maximum, default, a random value, beyond the
    # range, NaN or an infinity. 16 is the dry path at Mix 0.
    for s in tool["sweep"]:
        assert s["samples"] >= 10 * s["rate"]
        assert s["nonfinite"] == 0 and s["peak"] <= 16.0


def test_every_type_stays_bounded_when_pushed(tool):
    # Resonance 1, Drive 1, Level 2, every Mode, Cutoff 60 Hz and 18 kHz with
    # full Spread, noise at the guard's limit and then its ringing.
    for e in tool["extremes"]:
        assert e["nonfinite"] == 0 and e["peak"] < 2.0, e


def test_glide_is_block_size_independent_and_reaches_its_target(tool):
    g = tool["glide"]
    assert g["block_independent"]
    # Level 1 -> 0 (and Mix 0.6 -> 1) fades over ~5 ms instead of cutting...
    assert g["first_ms"] > 0.25 * g["before"]
    # ...and 50 ms later the glide has snapped to its target: exact silence.
    assert g["tail"] == 0.0


def test_type_changes_crossfade_without_a_click(tool):
    # All 42 ordered pairs, a 440 Hz sine at 0.5 through Cutoff 1.5 kHz: the
    # largest step between neighbouring samples across the switch is no
    # larger than either type's own (measured: at most 4 % above).
    assert len(tool["switch"]) == 42
    for s in tool["switch"]:
        assert s["across"] <= 1.1 * s["steady"], s


def test_tails_flush_to_exact_silence(tool):
    for s in tool["silence"]:
        assert s["rest_peak"] == 0.0, s                     # from rest, at any setting
        assert 0.0 <= s["silent_after_s"] < 0.5, s           # measured 0.01-0.19 s


def test_host_rates(tool):
    accepted = {rate: ok for rate, ok, _ in tool["rates"]}
    assert accepted == {"0": False, "7999": False, "8000": True, "44118": True,
                        "48000": True, "96000": True, "384000": True, "400000": False,
                        "nan": False, "inf": False, "-44118": False}


# --- frequency responses ------------------------------------------------------

def test_svf_modes(tool):
    lp, bp, hp = gains(tool, "svf_lp"), gains(tool, "svf_bp"), gains(tool, "svf_hp")
    notch = gains(tool, "svf_notch")
    # Butterworth at Resonance 0: -3 dB at Cutoff, 12 dB/octave beyond.
    assert lp[50] == pytest.approx(0.0, abs=0.05) and lp[1000] == pytest.approx(-3.01, abs=0.05)
    assert lp[4000] - lp[8000] == pytest.approx(13.6, abs=1.0)   # 12 dB/oct, warped near fs/2
    assert hp[15000] == pytest.approx(0.0, abs=0.1) and hp[1000] == pytest.approx(-3.01, abs=0.05)
    assert hp[250] - hp[125] == pytest.approx(12.0, abs=0.3)
    assert bp[1000] == pytest.approx(0.0, abs=0.05) and bp[125] < -14 and bp[8000] < -14
    assert notch[1000] < -60 and notch[100] > -5 and notch[10000] > -5
    q = gains(tool, "svf_lp_q")
    assert q[1000] - q[50] > 15                         # Resonance 0.8: an 18 dB peak


def test_ladder_slope_per_pole_count(tool):
    # Resonance 0: each pole is -3 dB at Cutoff, and n poles fall 6n dB per
    # octave above it (measured between 2 and 4 kHz, Cutoff 500 Hz).
    for poles, case in ((4, "ladder_4"), (3, "ladder_3"), (2, "ladder_2"), (1, "ladder_1")):
        g = gains(tool, case)
        assert g[30] == pytest.approx(0.0, abs=0.1)
        assert g[500] == pytest.approx(-3.01 * poles, abs=0.1)
        assert g[2000] - g[4000] == pytest.approx(6.0 * poles, abs=0.5)
    r = gains(tool, "ladder_res")
    assert r[1000] - r[30] > 15 and r[30] > -6          # the peak, and the bass kept


def test_diode(tool):
    g = gains(tool, "diode_0")
    # Normalised so that Cutoff is the -3 dB point with no resonance.
    assert g[30] == pytest.approx(0.0, abs=0.05) and g[1000] == pytest.approx(-3.0, abs=0.2)
    assert g[4000] > g[8000] + 8
    r = gains(tool, "diode_res")
    assert r[1000] - r[30] > 20 and r[1000] > r[500] + 15 and r[1000] > r[2000] + 30
    one = gains(tool, "diode_1p")                       # Mode 3: the first stage's tap
    assert one[4000] > -6 and one[4000] - one[8000] < 3


def test_sallen_key(tool):
    lp, hp, bp = gains(tool, "sk_lp"), gains(tool, "sk_hp"), gains(tool, "sk_bp")
    # Two coincident poles at Resonance 0: -6 dB at Cutoff, 12 dB/octave.
    assert lp[30] == pytest.approx(0.0, abs=0.05) and lp[1000] == pytest.approx(-6.02, abs=0.05)
    assert lp[4000] - lp[8000] == pytest.approx(13.2, abs=1.0)
    assert hp[15000] == pytest.approx(0.0, abs=0.1) and hp[1000] == pytest.approx(-6.02, abs=0.05)
    assert hp[250] - hp[125] == pytest.approx(11.7, abs=0.5)
    assert bp[1000] == pytest.approx(0.0, abs=0.05) and bp[100] < -12 and bp[10000] < -12
    r = gains(tool, "sk_res")
    assert r[1000] - r[30] > 8


def test_sk_mixed_inputs(tool):
    lp, hp, bp = gains(tool, "skmix_lp"), gains(tool, "skmix_hp"), gains(tool, "skmix_bp")
    notch = gains(tool, "skmix_notch")
    # Sallen-Key Q 1/3 at Resonance 0: -9.5 dB at Cutoff.
    assert lp[30] == pytest.approx(0.0, abs=0.05) and lp[1000] == pytest.approx(-9.54, abs=0.1)
    # The high-pass input: (s^2 + 2 s) / D, a 6 dB/octave skirt below Cutoff.
    assert hp[15000] == pytest.approx(0.0, abs=0.1)
    assert hp[125] - hp[62.5] == pytest.approx(5.7, abs=0.5)
    assert bp[1000] > bp[100] + 15 and bp[1000] > bp[10000] + 15
    assert notch[1000] < -60 and notch[30] > -1 and notch[15000] > -1


def test_comb(tool):
    pos, neg, ff = gains(tool, "comb_pos"), gains(tool, "comb_neg"), gains(tool, "comb_ff")
    f = 441.18                                          # 100 samples
    # Positive feedback: peaks at multiples of Cutoff, troughs between.
    assert pos[f] - pos[1.5 * f] > 18 and pos[2 * f] - pos[2.5 * f] > 18
    # Negative: the reverse, peaks at odd multiples of Cutoff / 2.
    assert neg[f / 2] - neg[f] > 18 and neg[1.5 * f] - neg[2 * f] > 18
    # Feedforward: notches at odd multiples of Cutoff / 2, -34 dB at Resonance 1.
    assert ff[f] > 5 and ff[f / 2] < -30 and ff[1.5 * f] < -30


def test_formant_vowels(tool):
    a, i = gains(tool, "formant_a"), gains(tool, "formant_i")
    # Men's A (hod): 730, 1090, 2440 Hz; I (heed): 270, 2290, 3010 Hz.
    assert a[730] > a[270] + 15 and a[1090] > a[1700] + 10 and a[2440] > a[2290] + 5
    assert i[270] > i[730] + 15 and i[2290] > i[1090] + 20 and i[3010] > -6
    up = gains(tool, "formant_a_up")                    # Cutoff 4 kHz: an octave up
    assert up[1460] > up[730] + 15


def test_spread(tool):
    left, right = gains(tool, "spread_l"), gains(tool, "spread_r")
    assert left[500] == pytest.approx(-3.01, abs=0.05)    # an octave down
    assert right[2000] == pytest.approx(-3.01, abs=0.05)  # an octave up


@pytest.mark.parametrize("case", ["svf_lp_8k", "svf_lp_96k", "svf_lp_384k"])
def test_cutoff_holds_at_other_rates(tool, case):
    g = gains(tool, case)
    assert g[50] == pytest.approx(0.0, abs=0.05) and g[1000] == pytest.approx(-3.01, abs=0.05)


def test_cutoff_stays_below_nyquist(tool):
    g = gains(tool, "svf_lp_8k_top")                    # 18 kHz asked at 8 kHz: 3.6 kHz
    assert g[3600] == pytest.approx(-3.0, abs=0.1) and g[100] == pytest.approx(0.0, abs=0.05)


def test_resonance_compensation_keeps_the_pass_band(tool):
    # Resonance 0.9 (Cutoff 2 kHz): the pass band within 4-8 dB of unity.
    for t in ("svf", "ladder", "diode", "sk", "skmix"):
        db = gains(tool, f"pass_{t}")[40]
        assert -8.0 < db < -3.5, (t, db)


# --- self-oscillation ---------------------------------------------------------

def test_self_oscillation_tracks_cutoff(tool):
    tol = {"svf": 0.1, "ladder": 1.0, "diode": 1.0, "sk": 4.0}   # cents
    for o in tool["osc"]:
        if o.get("res") is not None:
            continue
        c = 1200 * math.log2(o["hz"] / o["cutoff"])
        if o["type"] == "skmix":
            assert -25 < c < -5, o                      # the diodes pull it ~20 cents flat
        else:
            assert abs(c) < tol[o["type"]], (o, c)
        assert 0.3 < o["peak"] < 0.65, o                # -10 to -4 dBFS


def test_no_oscillation_below_the_threshold(tool):
    quiet = [o for o in tool["osc"] if o.get("res") == 0.85]
    assert len(quiet) == 4 and all(o["peak"] == 0.0 for o in quiet)


def test_self_oscillation_at_other_rates(tool):
    rated = [o for o in tool["osc"] if "rate" in o]
    assert len(rated) == 12
    for o in rated:
        tol = 4.0 if o["type"] == "sk" else 1.0
        assert abs(1200 * math.log2(o["hz"] / 440.0)) < tol, o


# --- Drive and character ------------------------------------------------------

def test_drive_adds_harmonics(tool):
    h = {(x["type"], x["drive"]): x for x in tool["harmonics"]}
    for t in ("svf", "ladder", "diode", "sk", "skmix"):
        clean, driven = h[(t, 0)], h[(t, 1)]
        assert driven["h3"] > clean["h3"] + 30, t       # third harmonic up by 30 dB or more
        assert driven["h3"] > -30, t
    for t in ("svf", "diode", "sk"):
        assert h[(t, 0)]["h3"] < -80, t                 # at Drive 0, 0.5 in: all but clean
    assert h[("ladder", 0)]["h3"] < -60                 # the ladder's loop colours a little


def test_sk_mixed_is_not_sallen_key(tool):
    h = {(x["type"], x["drive"]): x for x in tool["harmonics"]}
    # SK Mixed's asymmetric clip makes even harmonics; Sallen-Key's symmetric one none.
    assert h[("skmix", 0)]["h2"] > -70 and h[("sk", 0)]["h2"] < -100
    lv = {(x["type"], x["amp"]): x for x in tool["level"]}

    def tilt(t, a):
        return lv[(t, a)]["g2000"] - lv[(t, a)]["g250"]
    # A louder input darkens SK Mixed (its diodes saturate); Sallen-Key's tilt holds.
    assert tilt("skmix", 0.5) < tilt("skmix", 0.01) - 1.5
    assert abs(tilt("sk", 0.5) - tilt("sk", 0.01)) < 0.2
