"""Tests for the Mutable-derived audio effects (engines/src/mi_fx.cc, notes in
engines/mi-fx.md): Plate, Ensemble and Diffuse, the first FM1_KIND_AUDIO_FX
engines (docs/11 §4, §8 stage A).

Each effect is driven by the renderer's test inputs (impulse, noise, sine) or
by a sound engine, and checked for its tail, stability at maximum feedback,
pass-through at Mix 0, its wet level, the input guard against NaN,
infinite and huge input, stereo output from a mono source, determinism, block-size
independence, instance size, that every parameter does what it says, and, for
Plate and Diffuse, decay time against the upstream code at its native rate.
"""
import json
import math
import subprocess
import wave

import pytest

from tests.engine_helpers import RATE, render, renderer, rms  # noqa: F401

FX = ("plate", "ensemble", "diffuse")

# The longest, brightest, widest setting of each effect.
MAX_FEEDBACK = {
    "plate": ["Mix=1", "Decay=1", "Damping=0", "Diffusion=1"],
    "ensemble": ["Mix=1", "Depth=1", "Width=1"],
    "diffuse": ["Mix=1", "Time=1", "Tone=1", "Width=1"],
}

# Every parameter away from its default except Mix, which the test sets.
BUSY = {
    "plate": ["Decay=1", "Damping=0.9", "Diffusion=0.1"],
    "ensemble": ["Depth=1", "Width=0.3"],
    "diffuse": ["Time=1", "Tone=0.2", "Width=0.4"],
}

# Mutable Instruments asks that derivatives not use its name or module names.
BANNED = ("mutable", "plaits", "braids", "rings", "clouds", "elements")


def fx_args(fx, params):
    return [(fx, list(params))]


def run(renderer, tmp_path, args, name):
    """Render with arbitrary arguments; return (summary, left, right, rate)."""
    wav = tmp_path / f"{name}.wav"
    res = subprocess.run([str(renderer), *args, "--out", str(wav)], check=True,
                         capture_output=True, text=True)
    with wave.open(str(wav), "rb") as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    samples = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767.0
               for i in range(0, len(raw), 2)]
    return json.loads(res.stdout), samples[0::2], samples[1::2], rate


def cli_fx(fx, params):
    args = ["--fx", fx]
    for p in params:
        args += ["--fx-param", p]
    return args


def correlation(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den


def decay_db_per_s(left, right, rate, t0, t1):
    """Slope of the Schroeder energy-decay curve between t0 and t1."""
    energy = [a * a + b * b for a, b in zip(left, right)]
    tail = [0.0] * (len(energy) + 1)
    for i in range(len(energy) - 1, -1, -1):
        tail[i] = tail[i + 1] + energy[i]
    edc = [10 * math.log10(tail[int(t * rate)] + 1e-20) for t in (t0, t1)]
    return (edc[1] - edc[0]) / (t1 - t0)


def brightness(samples, t0, t1):
    """RMS of the first difference over RMS: sqrt(2) for white noise, lower
    for a darker sound."""
    seg = samples[int(t0 * RATE):int(t1 * RATE)]
    diff = sum((b - a) ** 2 for a, b in zip(seg, seg[1:]))
    return math.sqrt(diff / sum(x * x for x in seg))


def echo_density(left, right, t1, window=882):
    """Normalised echo density (Abel and Huang, 2006), averaged over 0..t1 s:
    the share of samples beyond one standard deviation in each 20 ms window,
    over the 0.3173 of a Gaussian. Sparse early echoes score low."""
    etas = []
    for ch in (left, right):
        for start in range(0, int(t1 * RATE) - window + 1, window // 2):
            seg = ch[start:start + window]
            sd = math.sqrt(sum(x * x for x in seg) / window)
            if sd > 0.0:
                etas.append(sum(1 for x in seg if abs(x) > sd) / window / 0.3173)
    return sum(etas) / len(etas)


def level_variation(samples, t0, t1, window=441):
    """Relative standard deviation of the level in 10 ms windows."""
    levels = [rms(samples, s / RATE, (s + window) / RATE)
              for s in range(int(t0 * RATE), int(t1 * RATE), window)]
    mean = sum(levels) / len(levels)
    return math.sqrt(sum((x - mean) ** 2 for x in levels) / len(levels)) / mean


def test_effects_are_registered(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True,
                         capture_output=True, text=True).stdout
    engines = {e["id"]: e for e in json.loads(out)}
    for fx in FX:
        e = engines[fx]
        assert e["kind"] == "audio_fx" and e["max_voices"] == 0
        assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
        assert "Emilie Gillet" in e["credits"] and "MIT" in e["credits"]
        names = [p["name"] for p in e["params"]]
        assert names[0] == "Mix"
        knobs = [p for p in e["params"] if p["type"] == 0]          # the FLOATs
        assert all(p["page"] == 0 for p in knobs) and len(knobs) <= 4
        assert all(p["min"] == 0 and p["max"] == 1 for p in e["params"])
    # Plate's Freeze switch, appended on page 1 (tests/test_engines_plate_freeze.py).
    assert [p["name"] for p in engines["plate"]["params"]][4:] == ["Freeze"]


@pytest.mark.parametrize("fx,params,windows", [
    # Plate at its default Decay: 0.5 s windows sit near -58, -69 and -84 dBFS.
    ("plate", ["Mix=1"], [(0.5, 1.0), (1.0, 1.5), (1.5, 2.0)]),
    # Diffuse's loop is shorter: 0.25 s windows near -56, -63 and -75 dBFS.
    ("diffuse", ["Mix=1", "Time=0.8"], [(0.5, 0.75), (0.75, 1.0), (1.0, 1.25)]),
])
def test_impulse_leaves_a_decaying_tail(renderer, tmp_path, fx, params, windows):
    _, left, _ = render(renderer, tmp_path, input="impulse", seconds=2.5,
                        fx=fx_args(fx, params))
    levels = [rms(left, a, b) for a, b in windows]
    assert levels[0] > 1e-4                      # energy after 0.5 s
    assert levels[0] > levels[1] > levels[2] > 0.0   # and falling
    assert rms(left, 0.0, 0.5) > levels[0]


def test_ensemble_impulse_response_is_finite(renderer, tmp_path):
    # Ensemble is feed-forward: its longest path is 192 + 176 samples of
    # modulated delay plus Width's 131-sample offset, about 11 ms. There is no
    # tail to decay, so the right check is that the response ends.
    _, left, right, _ = run(renderer, tmp_path,
                            ["--input", "impulse", "--seconds", "0.5",
                             *cli_fx("ensemble", MAX_FEEDBACK["ensemble"])], "ens")
    for ch in (left, right):
        assert any(x != 0.0 for x in ch[10:int(0.02 * RATE)])   # wet taps
        assert all(x == 0.0 for x in ch[int(0.05 * RATE):])


@pytest.mark.parametrize("fx", FX)
def test_maximum_feedback_on_noise_stays_bounded(renderer, tmp_path, fx):
    # 10 s of noise at the longest, brightest setting. Test Gain scales the
    # result by 1/8 so the host's limiter never engages and the WAV shows
    # the effect's own level. Plate at Decay 1 takes about 8 s to build up
    # (its low end decays slowest) and then holds flat: measured 0.465 RMS
    # from 8 s to 20 s, against the input's 0.289.
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--input", "noise", "--seconds", "10", *cli_fx(fx, MAX_FEEDBACK[fx]),
         *cli_fx("test-gain", ["Gain=0.125"])], f"max_{fx}")
    assert summary["nonfinite"] == 0
    assert summary["raw_peak"] < 0.5             # the effect's own peak < 4.0
    assert summary["clipped"] == 0
    for ch in (left, right):
        before, last = rms(ch, 6, 8), rms(ch, 8, 10)
        assert last < 1.05 * before              # no longer growing
        assert 8 * last < 2 * 0.2887             # within 6 dB of the input


@pytest.mark.parametrize("fx", FX)
def test_mix_zero_passes_the_input_through(renderer, tmp_path, fx):
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=fx_args(fx, ["Mix=0", *BUSY[fx]]), name=fx)
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


# Bad input built from the host's noise: NaN on every frame from the host's
# fault injection; 24 Test Gain stages of x2 take the noise to millions, past
# where the vendored loops' float-to-int32 stores overflow (for a mono source
# about 160,000 for Plate, 520,000 for Diffuse); 160 stages overflow it to
# +/-infinity.
BAD_INPUT = {
    "nan": ["--fault", "0..0.5:nan"],
    "huge": [a for _ in range(24) for a in cli_fx("test-gain", ["Gain=2"])],
    "inf": [a for _ in range(160) for a in cli_fx("test-gain", ["Gain=2"])],
}


@pytest.mark.parametrize("fx", FX)
@pytest.mark.parametrize("bad", ["nan", "huge", "inf"])
def test_bad_input_is_guarded(renderer, tmp_path, fx, bad):
    # Before the input guard, one NaN or infinite sample latched Plate's and
    # Diffuse's loops at NaN for good, even at Mix 0 (their crossfades compute
    # NaN * 0), and huge input was undefined behaviour in the vendored
    # float-to-int32 stores. The guard reads NaN as 0 and clamps everything
    # else to +/-16, dry path included. It is stateless, so a finite output
    # for half a second of nothing but bad input means no state was poisoned.
    # engines/mi-fx.md, "Input guard".
    source = ["--input", "noise", "--seconds", "0.5", *BAD_INPUT[bad]]
    summary, _, _, _ = run(renderer, tmp_path, source, "source")
    total = 2 * summary["frames"]
    if bad == "huge":                                    # the input is as bad as meant
        assert summary["nonfinite"] == 0 and summary["raw_peak"] > 4e6
    else:
        assert summary["nonfinite"] > 0.99 * total
    for mix in ("0", "1"):
        params = [*MAX_FEEDBACK[fx][1:], f"Mix={mix}"]
        summary, _, _, _ = run(renderer, tmp_path, [*source, *cli_fx(fx, params)],
                               f"{fx}_{mix}")
        assert summary["nonfinite"] == 0
        if bad == "nan":
            assert summary["raw_peak"] == 0.0            # NaN reads as silence
        elif mix == "0":
            assert summary["raw_peak"] == 16.0           # the clamp, passed dry
        else:
            assert 0.0 < summary["raw_peak"] < 64.0


@pytest.mark.parametrize("fx,low,high", [
    # Measured against the host's noise at the default settings: Plate -2.9,
    # Ensemble -3.3, Diffuse -3.5 dB (engines/mi-fx.md, finding 2).
    ("plate", -4.5, -1.5),
    ("ensemble", -4.8, -1.8),
    ("diffuse", -5.0, -2.0),
])
def test_wet_level_against_noise(renderer, tmp_path, fx, low, high):
    # Test Gain halves the output so the host's limiter never engages.
    _, left, right, _ = run(renderer, tmp_path,
                            ["--input", "noise", "--seconds", "2", *cli_fx(fx, ["Mix=1"]),
                             *cli_fx("test-gain", ["Gain=0.5"])], f"level_{fx}")
    for ch in (left, right):
        db = 20 * math.log10(2 * rms(ch, 0.5, 2.0) / (0.5 / math.sqrt(3)))
        assert low < db < high


@pytest.mark.parametrize("fx", FX)
def test_mono_source_comes_out_stereo(renderer, tmp_path, fx):
    # The host's noise is the same on both channels, like every sound engine
    # so far. Plate is always stereo; Ensemble and Diffuse through Width.
    _, left, right, _ = run(renderer, tmp_path,
                            ["--input", "noise", "--seconds", "1",
                             *cli_fx(fx, ["Mix=1"])], f"wide_{fx}")
    assert correlation(left[RATE // 4:], right[RATE // 4:]) < 0.9


@pytest.mark.parametrize("fx", ["ensemble", "diffuse"])
def test_width_zero_keeps_a_mono_source_mono(renderer, tmp_path, fx):
    _, left, right, _ = run(renderer, tmp_path,
                            ["--input", "noise", "--seconds", "0.5",
                             *cli_fx(fx, ["Mix=1", "Width=0"])], f"mono_{fx}")
    assert left == right


@pytest.mark.parametrize("fx,params", [
    ("plate", ["Mix=0.5", "Decay=0.7"]),
    ("diffuse", ["Mix=0.5", "Time=0.8"]),
])
def test_tail_after_an_engine(renderer, tmp_path, fx, params):
    note = dict(params=["Decay=0.2"], notes=["0:60:100:0.3"], seconds=2.0)
    _, dry, _ = render(renderer, tmp_path, "macro", name="dry", **note)
    summary, wet, _ = render(renderer, tmp_path, "macro", name="wet",
                             fx=fx_args(fx, params), **note)
    assert summary["engine"] == "macro" and summary["fx"] == [fx]
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    assert rms(dry, 1.2, 1.6) < 1e-4             # Macro has died away...
    assert rms(wet, 1.2, 1.6) > 1e-3             # ...the effect has not


def test_ensemble_after_an_engine(renderer, tmp_path):
    args = ["--engine", "macro", "--param", "Decay=0.2", "--note", "0:60:100:0.3",
            "--seconds", "1.0"]
    _, dry_l, dry_r, _ = run(renderer, tmp_path, args, "dry")
    summary, left, right, _ = run(renderer, tmp_path,
                                  [*args, *cli_fx("ensemble", [])], "ens")
    assert dry_l == dry_r and left != right
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    ratio = rms(left, 0.05, 0.3) / rms(dry_l, 0.05, 0.3)
    assert 0.5 < ratio < 2.0


def test_full_chain(renderer, tmp_path):
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=4", "--note", "0:57:100:0.5",
         "--note", "0:60:100:0.5", "--note", "0:64:100:0.5", "--seconds", "2.0",
         *cli_fx("ensemble", []), *cli_fx("diffuse", []), *cli_fx("plate", ["Mix=0.4"])],
        "chain")
    assert summary["fx"] == ["ensemble", "diffuse", "plate"]
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.2, 1.6) > 1e-3
    assert left != right


@pytest.mark.parametrize("fx", FX)
def test_rendering_is_deterministic(renderer, tmp_path, fx):
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.5,
                     fx=fx_args(fx, BUSY[fx]), name="a")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.5,
                     fx=fx_args(fx, BUSY[fx]), name="b")
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("fx", FX)
def test_block_size_does_not_change_the_output(renderer, tmp_path, fx):
    # The API allows any 1..max_frames per call; the effects run per sample.
    wavs = []
    for frames in ("64", "7", "1"):
        wav = tmp_path / f"{fx}_{frames}.wav"
        subprocess.run([str(renderer), "--input", "noise", "--seconds", "0.5",
                        "--frames", frames, *cli_fx(fx, BUSY[fx]), "--out", str(wav)],
                       check=True, capture_output=True)
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


def test_instance_sizes_are_bounded(renderer, tmp_path):
    summary, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05,
                           fx=[(fx, []) for fx in FX])
    plate, ensemble, diffuse = summary["fx_bytes"]
    # Delay memory lives in the instance: 64 KB of 16-bit words for Plate,
    # 4 KB of floats for Ensemble, 16 KB of 12-bit words for Diffuse. Figures
    # are for a 64-bit host; engines/mi-fx.md has the 32-bit estimates.
    assert 65536 < plate <= 66048
    assert 4096 < ensemble <= 5120
    assert 16384 < diffuse <= 19456
    assert all(n % 16 == 0 for n in summary["fx_bytes"])


def test_plate_decay_is_rate_compensated(renderer, tmp_path):
    # At 48 kHz the wrapper leaves Rings' reverb exactly as upstream runs it.
    # At 44,118 Hz its delays are 8.8 % longer, so without compensation the
    # tail would decay 8 % slower (measured ratio 0.914-0.926). The wrapper
    # rescales the loop gain and damping; the impulse tail then decays at
    # 0.96-0.97 of the native rate. The rest is 16-bit truncation in the
    # loop, which costs more per second at the higher rate (a louder noise
    # burst measures 0.98-0.99).
    slopes = {}
    for rate in (44118, 48000):
        _, left, right, got = run(renderer, tmp_path,
                                  ["--input", "impulse", "--seconds", "2", "--rate", str(rate),
                                   *cli_fx("plate", ["Mix=1", "Decay=0.5"])], f"rt_{rate}")
        assert got == rate
        slopes[rate] = decay_db_per_s(left, right, rate, 0.05, 0.6)
    assert slopes[48000] < -10
    assert 0.95 < slopes[44118] / slopes[48000] < 1.05


# Every knob does what it says: each test below fails if its parameter is
# disconnected (the review of this stream found five that could be).

def test_plate_decay_sets_the_decay_rate(renderer, tmp_path):
    # Impulse tails, Schroeder slope over 0.05-0.6 s: measured -43, -23 and
    # -6 dB/s at Decay 0, 0.5 and 1.
    slopes = []
    for decay in ("0", "0.5", "1"):
        _, left, right, _ = run(renderer, tmp_path,
                                ["--input", "impulse", "--seconds", "3",
                                 *cli_fx("plate", ["Mix=1", f"Decay={decay}"])], f"decay_{decay}")
        slopes.append(decay_db_per_s(left, right, RATE, 0.05, 0.6))
    assert slopes[0] < slopes[1] < slopes[2] < 0
    assert slopes[0] < -30 and slopes[2] > -10


def test_plate_damping_darkens_the_tail(renderer, tmp_path):
    # The in-loop low-pass: the impulse tail from 0.3 to 1 s measured 1.10,
    # 0.77 and 0.46 in brightness at Damping 0, 0.5 and 1.
    bright = []
    for damping in ("0", "0.5", "1"):
        _, left, _ = render(renderer, tmp_path, input="impulse", seconds=1.0,
                            fx=fx_args("plate", ["Mix=1", f"Damping={damping}"]),
                            name=f"damp_{damping}")
        bright.append(brightness(left, 0.3, 1.0))
    assert bright[0] > bright[1] > bright[2]
    assert bright[2] < 0.6 * bright[0]


def test_plate_diffusion_thickens_the_early_response(renderer, tmp_path):
    # The all-pass coefficient: echo density over the first 100 ms of the
    # impulse response measured 0.31, 0.44 and 0.49 at Diffusion 0, 0.5, 1.
    density = []
    for diffusion in ("0", "0.5", "1"):
        _, left, right, _ = run(renderer, tmp_path,
                                ["--input", "impulse", "--seconds", "0.2",
                                 *cli_fx("plate", ["Mix=1", f"Diffusion={diffusion}"])],
                                f"diff_{diffusion}")
        density.append(echo_density(left, right, 0.1))
    assert density[0] < density[1] < density[2]
    assert density[2] > 1.3 * density[0]


def test_ensemble_depth_sets_the_modulation(renderer, tmp_path):
    # A 440 Hz sine through the ensemble alone (Width 0): with the taps still
    # (Depth 0) the level is steady; the swept taps beat against each other.
    # Level variation in 10 ms windows measured 0.008, 0.45 and 0.51 at
    # Depth 0, 0.5 and 1.
    variation = []
    for depth in ("0", "0.5", "1"):
        _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0,
                            fx=fx_args("ensemble", ["Mix=1", f"Depth={depth}", "Width=0"]),
                            name=f"depth_{depth}")
        variation.append(level_variation(left, 0.1, 0.9))
    assert variation[0] < 0.05
    assert variation[0] < variation[1] < variation[2]
    assert variation[1] > 0.2


def test_diffuse_tone_sets_the_brightness(renderer, tmp_path):
    # The one-pole low-pass on the wet: brightness against the host's noise
    # measured 0.17, 0.55 and 1.04 at Tone 0, 0.5 and 1 (white noise: 1.41).
    bright = []
    for tone in ("0", "0.5", "1"):
        _, left, _ = render(renderer, tmp_path, input="noise", seconds=1.0,
                            fx=fx_args("diffuse", ["Mix=1", f"Tone={tone}"]), name=f"tone_{tone}")
        bright.append(brightness(left, 0.25, 1.0))
    assert bright[0] < bright[1] < bright[2]
    assert bright[0] < 0.3 * bright[2]


def test_diffuse_decay_is_rate_compensated(renderer, tmp_path):
    # As for the Plate: at 48 kHz the wrapper runs Plaits' diffuser almost
    # exactly as upstream (47,872 Hz). At 44,118 Hz its delays are 8.5 %
    # longer; with the loop gain rescaled the tail decays at 0.967 of the
    # 48 kHz rate, without it at 0.915 (measured). The rest is the in-loop
    # damping, fixed upstream and not compensated, and the 12-bit loop's
    # truncation.
    slopes = {}
    for rate in (44118, 48000):
        _, left, right, got = run(renderer, tmp_path,
                                  ["--input", "impulse", "--seconds", "2", "--rate", str(rate),
                                   *cli_fx("diffuse", ["Mix=1", "Time=0.8"])], f"drt_{rate}")
        assert got == rate
        slopes[rate] = decay_db_per_s(left, right, rate, 0.05, 0.5)
    assert slopes[48000] < -10
    assert 0.94 < slopes[44118] / slopes[48000] < 1.05
