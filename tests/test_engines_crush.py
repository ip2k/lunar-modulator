"""Tests for Crush (engines/src/fx_crush.cc), the bitcrusher and sample-rate
reducer: an audio-rate sample-and-hold, a mid-tread quantiser, a one-pole
low-pass and a level, crossfaded with the dry signal.

Every parameter is checked against what it claims (hold interval, number of
levels, jitter spread, tone, level, mix), and the effect against the engine
API's contracts: deterministic renders, any block size, any prior memory
contents, any parameter value, silence in gives silence out, and bad input
(NaN, infinities, huge values) never latches.

Samples are compared as the 16-bit integers fm1-render writes, so equality
here is exact at the WAV's resolution.
"""
import json
import math
import subprocess
import wave

import pytest

from tests.engine_helpers import RATE, renderer  # noqa: F401  (fixture)

BUSY = ["Bits=5.5", "Rate=0.4", "Jitter=0.6", "Mix=0.8", "Tone=0.7", "Level=1.3"]
CLEAN = ["Bits=16", "Rate=1", "Jitter=0", "Mix=1", "Tone=1", "Level=1"]   # all but transparent


def run(renderer, tmp_path, params, name, source=("--input", "noise"), seconds=0.5,
        extra=(), fx=True):
    """Render the source through Crush; return (summary, left, right) with the
    channels as 16-bit integers."""
    wav = tmp_path / f"{name}.wav"
    args = [str(renderer), *source, "--seconds", str(seconds), "--out", str(wav)]
    if fx:
        args += ["--fx", "crush"]
        for p in params:
            args += ["--fx-param", p]
    else:                                 # the source alone, through a unity gain
        args += ["--fx", "test-gain", "--fx-param", "Gain=1"]
    args += list(extra)                   # further effects come after Crush
    res = subprocess.run(args, check=True, capture_output=True, text=True)
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    s = [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), 2)]
    return json.loads(res.stdout), s[0::2], s[1::2]


def hold_runs(samples):
    """Lengths of the runs of equal samples, without the first and last
    (which the render's ends may cut short)."""
    runs, n = [], 1
    for a, b in zip(samples, samples[1:]):
        if a == b:
            n += 1
        else:
            runs.append(n)
            n = 1
    return runs[1:]


def rms(samples):
    return math.sqrt(sum(x * x for x in samples) / len(samples))


def brightness(samples):
    """RMS of the first difference over RMS: sqrt(2) for white noise, lower
    for a darker sound."""
    diff = sum((b - a) ** 2 for a, b in zip(samples, samples[1:]))
    return math.sqrt(diff / sum(x * x for x in samples))


def test_crush_is_registered(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    e = {x["id"]: x for x in json.loads(out)}["crush"]
    assert e["name"] == "Crush" and e["kind"] == "audio_fx" and e["max_voices"] == 0
    assert "DaisySP" in e["credits"] and "Electro-Smith" in e["credits"]
    assert "MIT" in e["credits"]
    pages = {}
    for p in e["params"]:
        pages.setdefault(p["page"], []).append(p["name"])
        assert len(p["name"]) <= 12 and p["min"] <= p["def"] <= p["max"]
    assert pages == {0: ["Bits", "Rate", "Jitter", "Mix"], 1: ["Tone", "Level"]}
    bits = e["params"][0]
    assert (bits["min"], bits["max"]) == (1, 16)


def test_instance_is_small_and_aligned(renderer, tmp_path):
    summary, _, _ = run(renderer, tmp_path, [], "size", seconds=0.01)
    (size,) = summary["fx_bytes"]
    assert size % 16 == 0 and size <= 128


@pytest.mark.parametrize("params", [
    [], BUSY, CLEAN, ["Bits=1", "Rate=0", "Jitter=1"], ["Bits=1", "Tone=0", "Level=2"],
    ["Bits=nan", "Rate=nan", "Jitter=nan", "Mix=nan", "Tone=nan", "Level=nan"],
    ["Bits=-100", "Rate=-5", "Jitter=-1", "Mix=-1", "Tone=-1", "Level=-1"],
    ["Bits=1e9", "Rate=1e9", "Jitter=1e9", "Mix=1e9", "Tone=1e9", "Level=1e9"],
])
def test_silence_stays_silent(renderer, tmp_path, params):
    # The quantiser is mid-tread: zero is a level, so no setting adds DC or
    # idle noise to silence.
    summary, left, right = run(renderer, tmp_path, params, "silence",
                               source=("--input", "silence"), extra=["--frames", "7"])
    assert summary["nonfinite"] == 0 and summary["raw_peak"] == 0.0
    assert not any(left) and not any(right)


@pytest.mark.parametrize("setting", ["min", "max", "beyond", "nan"])
def test_any_parameter_value_gives_finite_bounded_output(renderer, tmp_path, setting):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    e = {x["id"]: x for x in json.loads(out)}["crush"]
    values = {"min": lambda p: p["min"], "max": lambda p: p["max"],
              "beyond": lambda p: 4 * p["max"] - 3 * p["min"] + 1, "nan": lambda p: "nan"}
    params = [f"{p['name']}={values[setting](p)}" for p in e["params"]]
    summary, _, _ = run(renderer, tmp_path, params, setting, extra=["--frames", "7"])
    assert summary["nonfinite"] == 0
    assert summary["raw_peak"] <= 2.0       # Level 2 on the host's +/-0.5 noise, quantised


def test_nan_parameters_fall_back_to_the_defaults(renderer, tmp_path):
    _, dl, dr = run(renderer, tmp_path, [], "defaults")
    _, nl, nr = run(renderer, tmp_path, ["Bits=nan", "Rate=nan", "Jitter=nan", "Mix=nan",
                                         "Tone=nan", "Level=nan"], "nans")
    assert (nl, nr) == (dl, dr)


def test_mix_zero_passes_the_input_through(renderer, tmp_path):
    _, rl, rr = run(renderer, tmp_path, [], "ref", fx=False)
    _, left, right = run(renderer, tmp_path, ["Mix=0", *BUSY[:3], *BUSY[4:]], "dry")
    assert (left, right) == (rl, rr)


def test_clean_settings_are_transparent(renderer, tmp_path):
    # Bits 16 is a step of 2^-15, the WAV's own; Rate 1 takes every sample.
    _, rl, _ = run(renderer, tmp_path, [], "ref", fx=False)
    _, left, right = run(renderer, tmp_path, CLEAN, "clean")
    assert left == right
    assert max(abs(a - b) for a, b in zip(left, rl)) <= 1


@pytest.mark.parametrize("rate,host", [(0.0, 44118), (0.5, 44118), (0.75, 44118),
                                       (1.0, 44118), (0.0, 48000), (0.5, 48000)])
def test_rate_sets_the_hold_interval(renderer, tmp_path, rate, host):
    # Rate is log from 100 Hz to the host rate: a hold of (host / 100)^(1 - Rate)
    # samples, kept as a running count so holds last its floor or its ceiling
    # and average to it exactly. Noise at Bits 16 rarely repeats a value, so
    # equal neighbours mark one hold.
    expected = (host / 100.0) ** (1.0 - rate)
    _, left, right = run(renderer, tmp_path, ["Bits=16", f"Rate={rate}"], f"rate_{rate}_{host}",
                         seconds=1.0, extra=["--rate", str(host)])
    assert left == right                      # one clock for both channels
    runs = hold_runs(left)
    lo, hi = math.floor(expected), math.ceil(expected)
    exact = [r for r in runs if lo <= r <= hi]
    assert len(exact) >= 0.99 * len(runs)     # the rest: two holds that drew equal values
    assert sum(exact) / len(exact) == pytest.approx(expected, rel=0.005)


@pytest.mark.parametrize("jitter,spread", [(0.0, 0.0), (0.5, 0.45), (1.0, 0.9)])
def test_jitter_varies_each_hold_but_not_the_mean_rate(renderer, tmp_path, jitter, spread):
    # Jitter J draws each hold from interval * (1 + 0.9 J u), u uniform in
    # [-1, 1): at Rate 0.5 a 21-sample hold spreads over 2..40 samples at J 1.
    expected = (RATE / 100.0) ** 0.5
    _, left, _ = run(renderer, tmp_path, ["Bits=16", "Rate=0.5", f"Jitter={jitter}"],
                     f"jitter_{jitter}", seconds=2.0)
    runs = hold_runs(left)
    assert len(runs) == pytest.approx(len(left) / expected, rel=0.03)
    lo, hi = math.floor(expected * (1 - spread)), math.ceil(expected * (1 + spread))
    inside = [r for r in runs if lo <= r <= hi]
    assert len(inside) >= 0.99 * len(runs)
    if jitter > 0:
        assert min(runs) <= expected * (1 - 0.8 * spread)
        assert max(inside) >= expected * (1 + 0.8 * spread)


def test_jitter_never_holds_less_than_a_sample(renderer, tmp_path):
    # At Rate 1 the mean hold is one sample, so jitter's shorter draws are
    # clamped to one and only the longer ones count: holds of 1 or 2
    # samples. Without the clamp the countdown would wander like a random
    # walk and hold for hundreds of samples at a time.
    _, left, _ = run(renderer, tmp_path, ["Bits=16", "Rate=1", "Jitter=1"], "fast", seconds=2.0)
    runs = hold_runs(left)
    assert sum(1 for r in runs if r <= 2) >= 0.999 * len(runs) and max(runs) <= 4
    assert len(left) / len(runs) == pytest.approx(1.225, rel=0.02)   # E[max(1, 1 + 0.9u)]


def test_jitter_is_deterministic_and_seeded_per_instance(renderer, tmp_path):
    # Two runs agree, and two Crush instances in one chain start from the
    # same seed: the second re-holds the first's output at the same instants,
    # so the chain equals one stage.
    params = ["Bits=16", "Rate=0.4", "Jitter=1"]
    _, a, _ = run(renderer, tmp_path, params, "a")
    _, b, _ = run(renderer, tmp_path, params, "b")
    assert a == b
    _, two, _ = run(renderer, tmp_path, params, "two",
                    extra=["--fx", "crush", *[x for p in params for x in ("--fx-param", p)]])
    assert two == a


def test_channels_are_crushed_separately(renderer, tmp_path):
    # Ensemble before Crush makes the host's mono noise stereo. Each channel
    # keeps its own samples; only the hold clock is shared.
    source = ("--input", "noise", "--fx", "ensemble", "--fx-param", "Mix=1")
    _, rl, rr = run(renderer, tmp_path, [], "ref", source=source, fx=False)
    _, left, right = run(renderer, tmp_path, CLEAN, "clean", source=source)
    assert rl != rr
    assert max(abs(a - b) for a, b in zip(left, rl)) <= 1
    assert max(abs(a - b) for a, b in zip(right, rr)) <= 1
    _, left, right = run(renderer, tmp_path, ["Bits=16", "Rate=0.5"], "held", source=source)
    assert left != right and hold_runs(left) == hold_runs(right)


@pytest.mark.parametrize("bits,levels", [(16, None), (4, 9), (3.5, 7), (3, 5), (2, 3)])
def test_bits_sets_the_quantiser_step(renderer, tmp_path, bits, levels):
    # The host's sine has amplitude 0.5. A step of 2^(1 - Bits), rounded to
    # the nearest level: 9 levels at 4 bits (step 1/8), 5 at 3, 3 at 2, and 7
    # at 3.5 bits (step 0.177), so fractional values sweep smoothly.
    _, ref, _ = run(renderer, tmp_path, [], "ref", source=("--input", "sine"), fx=False)
    _, left, _ = run(renderer, tmp_path, ["Rate=1", f"Bits={bits}"], f"bits_{bits}",
                     source=("--input", "sine"))
    step = 32767 * 2.0 ** (1 - bits)
    assert max(abs(a - b) for a, b in zip(left, ref)) <= step / 2 + 1
    if levels is None:
        assert len(set(left)) > 1000
    else:
        assert len(set(left)) == levels


def test_low_bits_silence_quiet_input(renderer, tmp_path):
    # At 1 bit the levels are -1, 0 and +1: the host's +/-0.5 noise stays
    # under the first step, as on any fixed-range converter.
    summary, left, _ = run(renderer, tmp_path, ["Rate=1", "Bits=1"], "one_bit")
    assert summary["raw_peak"] == 0.0 and not any(left)


def test_tone_darkens_the_wet_signal(renderer, tmp_path):
    # The one-pole low-pass after the quantiser: Tone 1 is no filter, Tone 0
    # a cutoff of 150 Hz.
    _, ref, _ = run(renderer, tmp_path, [], "ref", fx=False)
    bright = {}
    for tone in ("0", "0.5", "0.9", "1"):
        _, left, _ = run(renderer, tmp_path, ["Bits=16", "Rate=1", f"Tone={tone}"], f"tone_{tone}")
        bright[tone] = brightness(left[2000:])
        if tone == "1":
            assert max(abs(a - b) for a, b in zip(left, ref)) <= 1
    assert bright["0"] < bright["0.5"] < bright["0.9"] < bright["1"]
    assert bright["0"] < 0.2 * bright["1"]    # 0.20 against 1.41: a 150 Hz one-pole


@pytest.mark.parametrize("level", [0.0, 0.5, 2.0])
def test_level_scales_the_wet_signal(renderer, tmp_path, level):
    # Test Gain quarters the result so Level 2 stays clear of the limiter.
    quarter = ["--fx", "test-gain", "--fx-param", "Gain=0.25"]
    _, unity, _ = run(renderer, tmp_path, ["Bits=16", "Rate=0.5"], "unity", extra=quarter)
    _, left, _ = run(renderer, tmp_path, ["Bits=16", "Rate=0.5", f"Level={level}"],
                     f"level_{level}", extra=quarter)
    if level == 0.0:
        assert not any(left)
    else:
        assert rms(left) / rms(unity) == pytest.approx(level, rel=0.01)


def test_mix_crossfades(renderer, tmp_path):
    # With the wet path muted (Level 0), Mix 0.25 leaves three quarters of
    # the dry signal.
    _, ref, _ = run(renderer, tmp_path, [], "ref", fx=False)
    _, left, _ = run(renderer, tmp_path, ["Mix=0.25", "Level=0"], "mix")
    assert rms(left) / rms(ref) == pytest.approx(0.75, rel=0.01)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "1e30"])
@pytest.mark.parametrize("tone,settle", [("1", 0.21), ("0.3", 0.4)])
def test_bad_input_never_latches(renderer, tmp_path, value, tone, settle):
    # A tenth of a second of bad input (0.1-0.2 s). The guard reads NaN as 0
    # and clamps the rest to +/-16, so the output stays finite and bounded;
    # the hold clock and its generator never see the samples, so once the
    # next hold and the low-pass have moved on the output is the clean
    # render's again. Test Gain takes 1/32 after Crush so the clamped +/-16
    # never reaches the host's limiter, whose own recovery would show.
    params = ["Bits=6", "Rate=0.4", "Jitter=0.7", "Mix=0.6", f"Tone={tone}", "Level=1"]
    after = ["--fx", "test-gain", "--fx-param", "Gain=0.03125"]
    _, clean, _ = run(renderer, tmp_path, params, "clean", seconds=0.6, extra=after)
    summary, left, right = run(renderer, tmp_path, params, f"bad_{value}", seconds=0.6,
                               extra=[*after, "--fault", f"0.1..0.2:{value}"])
    assert summary["nonfinite"] == 0
    assert summary["raw_peak"] <= 16.0 / 32
    if value != "nan":
        assert summary["raw_peak"] == 16.0 / 32         # the guard's clamp, passed on
    start = int(settle * RATE)
    if tone == "1":                           # no filter: exact from the next hold
        assert left[start:] == clean[start:] and right[start:] == clean[start:]
    else:                                     # the low-pass converges within rounding
        assert max(abs(a - b) for a, b in zip(left[start:], clean[start:])) <= 1


def test_output_does_not_depend_on_block_size_or_prior_memory(renderer, tmp_path):
    first = None
    for frames in ("64", "7", "1"):
        for fill in ("0", "0xA5", "0xFF"):
            summary, left, right = run(renderer, tmp_path, BUSY, f"b{frames}_{fill}",
                                       extra=["--frames", frames, "--fill", fill])
            assert summary["nonfinite"] == 0
            if first is None:
                first = (left, right)
            assert (left, right) == first, (frames, fill)


def test_after_an_engine(renderer, tmp_path):
    args = ("--engine", "macro", "--note", "0:57:100:0.4", "--note", "0:64:100:0.4")
    _, dry, _ = run(renderer, tmp_path, [], "dry", source=args, seconds=0.8, fx=False)
    summary, wet, _ = run(renderer, tmp_path, ["Bits=4", "Rate=0.5", "Jitter=0.3"], "wet",
                          source=args, seconds=0.8)
    assert summary["engine"] == "macro" and summary["fx"] == ["crush"]
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    assert wet != dry and len(set(wet)) < 20      # at most 17 levels at 4 bits
    assert 0.5 < rms(wet[:int(0.4 * RATE)]) / rms(dry[:int(0.4 * RATE)]) < 2.0
