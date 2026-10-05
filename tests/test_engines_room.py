"""Tests for Room, the reverb and diffuser of Mutable Instruments Clouds
(engines/src/fx_room.cc, engines/README.md "Room"). The renders against the
upstream classes are in test_engines_reference_room.py.

Through fm1-render: registration and pages, the host contracts (deterministic
renders, any block size, any prior memory contents, any parameter value,
NaN included, bad input guarded, silence in gives silence out, Mix 0 passes
the input bit for bit), the tail and its bounds, and every knob doing what it
says. Through fm1-room-test (engines/test/room_test.cc): parameters changed
while audio runs, with block sizes that change between calls and bad input
mixed in, the glide, tails that end in exact zeros, the host rates it
accepts and the libm-free maths.
"""
import json
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import (BANNED, brightness, correlation, decay_db_per_s,
                                      echo_density, run)

TOOL = ENGINES / "build" / "fm1-room-test"

# Every parameter away from its default, Mix included.
BUSY = ["Mix=0.8", "Decay=0.8", "Damping=0.7", "Diffusion=0.3", "Blur=0.9", "Width=0.6"]
LONGEST = ["Mix=1", "Decay=1", "Damping=0", "Diffusion=1", "Blur=1", "Width=1"]


def fx(*params):
    return [("room", list(params))]


def cli(*params):
    args = ["--fx", "room"]
    for p in params:
        args += ["--fx-param", p]
    return args


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def listed(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return {x["id"]: x for x in json.loads(out)}["room"]


def test_room_is_registered(renderer):  # noqa: F811
    e = listed(renderer)
    assert (e["name"], e["kind"], e["max_voices"]) == ("Room", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "Emilie Gillet" in e["credits"] and "Clouds" in e["credits"]
    assert "MIT" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Mix", "Decay", "Damping", "Diffusion"], ["Blur", "Width"]]
    for p in e["params"]:
        assert p["type"] == 0 and (p["min"], p["max"]) == (0, 1) and len(p["name"]) <= 12
        assert sorted(p["flags"]) == ["mod", "smooth"]


def test_instance_size(renderer, tmp_path):  # noqa: F811
    # 32,768 bytes of 12-bit reverb words and 8,192 of diffuser floats, plus
    # the two classes and the glide state: 41,200 bytes on a 64-bit desktop
    # (engines/README.md has the 32-bit figure).
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"][0] % 16 == 0
    assert 32768 + 8192 < s["fx_bytes"][0] <= 41472


# --- host contracts ---------------------------------------------------------

def test_rendering_is_deterministic(renderer, tmp_path):  # noqa: F811
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="a")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="b")
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [BUSY, []])
def test_block_size_does_not_change_the_output(renderer, tmp_path, params):  # noqa: F811
    wavs = []
    for frames in ("64", "7", "1"):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*params),
                           name=f"f{frames}", extra=["--frames", frames])
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


def test_output_ignores_initial_memory(renderer, tmp_path):  # noqa: F811
    wavs = []
    for fill in ("0", "0xA5", "0xFF"):
        s, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY),
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
    params = listed(renderer)["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [[], BUSY, LONGEST])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


@pytest.mark.parametrize("params", [[], BUSY])
def test_mix_zero_passes_the_input_through(renderer, tmp_path, params):  # noqa: F811
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=fx(*params, "Mix=0"), name="dry")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


# Bad input from the host's noise, as test_engines_mi_fx.py builds it: NaN on
# every frame; 24 Test Gain stages of x2 (millions); 160 stages (infinity).
BAD_INPUT = {
    "nan": ["--fault", "0..0.5:nan"],
    "huge": [a for _ in range(24) for a in ["--fx", "test-gain", "--fx-param", "Gain=2"]],
    "inf": [a for _ in range(160) for a in ["--fx", "test-gain", "--fx-param", "Gain=2"]],
}


@pytest.mark.parametrize("bad", ["nan", "huge", "inf"])
def test_bad_input_is_guarded(renderer, tmp_path, bad):  # noqa: F811
    # NaN reads as 0 and everything else is clamped to +/-16, dry path
    # included; the guard is stateless, so half a second of nothing but bad
    # input with a finite output means no state was poisoned. The loop's
    # 12-bit words saturate at +/-8, which bounds the wet.
    source = ["--input", "noise", "--seconds", "0.5", *BAD_INPUT[bad]]
    for mix in ("0", "1"):
        summary, _, _, _ = run(renderer, tmp_path, [*source, *cli(*LONGEST[1:], f"Mix={mix}")],
                               f"room_{mix}")
        assert summary["nonfinite"] == 0
        if bad == "nan":
            assert summary["raw_peak"] == 0.0            # NaN reads as silence
        elif mix == "0":
            assert summary["raw_peak"] == 16.0           # the clamp, passed dry
        else:
            assert 0.0 < summary["raw_peak"] < 64.0


# --- the tail ---------------------------------------------------------------

def test_impulse_leaves_a_decaying_tail(renderer, tmp_path):  # noqa: F811
    # The default room (Decay 0.5) at full wet: 0.25 s windows falling.
    _, left, _ = render(renderer, tmp_path, input="impulse", seconds=1.5, fx=fx("Mix=1"))
    levels = [rms(left, a, a + 0.25) for a in (0.1, 0.35, 0.6)]
    assert levels[0] > 1e-4
    assert levels[0] > levels[1] > levels[2]


def test_maximum_feedback_on_noise_stays_bounded(renderer, tmp_path):  # noqa: F811
    # 14 s of noise at the longest, brightest, most diffuse setting. Test
    # Gain scales by 1/8 so the host's limiter never engages. Measured
    # (2026-10-05, left): the level builds up for about 10 s (RMS 0.24 in
    # the first 2 s, 0.41 from 8 to 10 s) and then holds at 0.415-0.426 for
    # 30 s more, against the input's 0.289; peak 2.2.
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--input", "noise", "--seconds", "14", *cli(*LONGEST),
         "--fx", "test-gain", "--fx-param", "Gain=0.125"], "max")
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    assert summary["raw_peak"] < 0.5
    for ch in (left, right):
        before, last = rms(ch, 10, 12), rms(ch, 12, 14)
        assert last < 1.05 * before                      # no longer growing
        assert 8 * last < 2 * 0.2887                     # within 6 dB of the input


def test_tail_after_an_engine(renderer, tmp_path):  # noqa: F811
    note = dict(params=["Decay=0.2"], notes=["0:60:100:0.3"], seconds=2.0)
    _, dry, _ = render(renderer, tmp_path, "macro", name="dry", **note)
    summary, wet, _ = render(renderer, tmp_path, "macro", name="wet",
                             fx=fx("Mix=0.5", "Decay=0.8"), **note)
    assert summary["fx"] == ["room"] and summary["nonfinite"] == 0
    assert summary["clipped"] == 0
    assert rms(dry, 1.2, 1.6) < 1e-4                     # Macro has died away...
    assert rms(wet, 1.2, 1.6) > 1e-3                     # ...the room has not


# --- every knob does what it says ---------------------------------------------

def burst_tail_slope(renderer, tmp_path, params, name):  # noqa: F811
    """dB/s of a 0.5 s noise burst's tail, 0.05 to 0.5 s after it."""
    _, left, right, _ = run(renderer, tmp_path,
                            ["--input", "noise", "--seconds", "2", "--fault", "0.5..2:0",
                             *cli("Mix=1", *params), "--fx", "test-gain",
                             "--fx-param", "Gain=0.5"], name)
    return decay_db_per_s(left, right, RATE, 0.55, 1.0)


def test_decay_sets_the_decay_rate(renderer, tmp_path):  # noqa: F811
    # Measured (2026-10-05): -65, -45, -21 and -6 dB/s at Decay 0, 0.5, 0.8
    # and 1 (against Clouds' rate: test_engines_reference_room.py).
    slopes = [burst_tail_slope(renderer, tmp_path, [f"Decay={d}"], f"d{d}")
              for d in ("0", "0.5", "0.8", "1")]
    assert slopes[0] < slopes[1] < slopes[2] < slopes[3] < 0
    assert slopes[0] < -40 and slopes[3] > -10


def test_damping_darkens_the_tail(renderer, tmp_path):  # noqa: F811
    # The in-loop low-pass: brightness of the tail 0.1 to 0.6 s after a noise
    # burst. Measured (2026-10-05): 1.01, 0.59 and 0.35 at Damping 0, 0.5, 1.
    bright = []
    for damping in ("0", "0.5", "1"):
        _, left, _, _ = run(renderer, tmp_path,
                            ["--input", "noise", "--seconds", "1.2", "--fault", "0.5..1.2:0",
                             *cli("Mix=1", "Decay=0.8", f"Damping={damping}")], f"k{damping}")
        bright.append(brightness(left, 0.6, 1.1))
    assert bright[0] > bright[1] > bright[2]
    assert bright[2] < 0.5 * bright[0]


def test_diffusion_thickens_the_early_response(renderer, tmp_path):  # noqa: F811
    # The all-pass coefficient: echo density over the first 100 ms of the
    # impulse response, Blur 0 so only the reverb's own all-passes act.
    # Measured (2026-10-05): 0.318, 0.360 and 0.402 at Diffusion 0, 0.5 and 1.
    density = []
    for diffusion in ("0", "0.5", "1"):
        _, left, right, _ = run(renderer, tmp_path,
                                ["--input", "impulse", "--seconds", "0.2",
                                 *cli("Mix=1", "Blur=0", f"Diffusion={diffusion}")],
                                f"a{diffusion}")
        density.append(echo_density(left, right, 0.1))
    assert density[0] < density[1] < density[2]
    assert density[2] > 1.15 * density[0]


def test_blur_smears_the_onset(renderer, tmp_path):  # noqa: F811
    # The diffuser before the reverb: in the first 30 ms of the impulse
    # response the share of energy in the loudest 1 % of samples falls as
    # the impulse is spread. Measured (2026-10-05): 0.52, 0.45 and 0.13 at
    # Blur 0, 0.5 and 1.
    peaky = []
    for blur in ("0", "0.5", "1"):
        _, left, right, _ = run(renderer, tmp_path,
                                ["--input", "impulse", "--seconds", "0.05",
                                 *cli("Mix=1", f"Blur={blur}")], f"b{blur}")
        e = sorted((a * a + b * b for a, b in zip(left[:1323], right[:1323])), reverse=True)
        peaky.append(sum(e[:13]) / sum(e))
    assert peaky[0] > peaky[1] > peaky[2]
    assert peaky[2] < 0.6 * peaky[0]


def test_width_sets_the_stereo_image(renderer, tmp_path):  # noqa: F811
    # The host's noise is mono. Width 1 gives upstream's two outputs (taken
    # from different points of the loop), Width 0 their mean on both sides,
    # exactly. Measured correlation (2026-10-05): 0.23 at Width 1, 0.73 at
    # Width 0.5.
    corr = {}
    for width in ("1", "0.5", "0"):
        _, left, right, _ = run(renderer, tmp_path,
                                ["--input", "noise", "--seconds", "1",
                                 *cli("Mix=1", f"Width={width}")], f"w{width}")
        if width == "0":
            assert left == right
        else:
            corr[width] = correlation(left[RATE // 4:], right[RATE // 4:])
    assert corr["1"] < 0.4 < corr["0.5"] < 0.95


def test_mix_blends_dry_and_wet(renderer, tmp_path):  # noqa: F811
    lsb = 1 / 32767.0
    tracks = {}
    for mix in ("0", "1", "0.5"):
        _, left, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name=f"m{mix}",
                            fx=fx(f"Mix={mix}"))
        tracks[mix] = left
    worst = max(abs(m - 0.5 * (d + w))
                for m, d, w in zip(tracks["0.5"], tracks["0"], tracks["1"]))
    assert worst <= 1.5 * lsb


# --- fm1-room-test: what fm1-render cannot drive ---------------------------------

def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise (0.5 peak) with up to two parameters jumping to any value,
    # NaN and infinities included, between blocks of 1-64 frames; then 20 s
    # more with NaN, infinities and 1e30 mixed into one block in eight.
    s = tool["sweep"]
    assert s["samples"] > 40 * RATE
    assert s["nonfinite"] == 0 and s["peak"] < 2.0
    assert s["bad_nonfinite"] == 0 and s["bad_peak"] <= 16.0 + 1e-3
    # Nothing latched: at Decay 0.9 with silent input the output then reaches
    # exact zeros (measured 10.9 s, the clamped bursts having filled the loop).
    assert 0 < s["silent_after_s"] < 30 and s["last_peak"] == 0.0


def test_glide_is_block_size_independent_and_lands_on_dry(tool):
    g = tool["glide"]
    assert g["block_independent"]
    # Mix 1 -> 0 fades over ~5 ms rather than cutting: within its first
    # millisecond the output is still far from the dry input...
    assert g["first_ms"] > 0.25 * g["before"]
    # ...and 60 ms on the glide has snapped: the input, bit for bit.
    assert g["after"] == 0.0 and g["dry_exact"]


def test_output_bits_are_the_same_from_every_build(tool):
    # FNV-1a of the glide render's float output (2 s, every knob moved, the
    # classes' coefficients gliding on their grid). The same from Apple
    # clang on arm64 (-O0, -O2, and -O1 under ASan + UBSan), GCC 14.2 on
    # x86-64 (static musl) and Emscripten 6.0.10's WebAssembly under Node
    # [verified, 2026-10-05]; CI's Linux, macOS and 32-bit (SSE) jobs check
    # it too. A build that fuses multiply-adds, or a libm call, changes it.
    assert tool["glide"]["hash"] == "3699e6dd"


def test_tails_end_in_exact_zeros(tool):
    # After 0.5 s of full-scale noise, silence: the 12-bit loop truncates to
    # zero and the wrapper flushes the wet below 1e-20, so the output becomes
    # exactly 0 and stays there (2 s checked), on both sides of the damping
    # coefficient 0.5 (Damping 1 at 44,118 Hz is 0.23, where the vendored
    # damping state can stop on a subnormal). Measured (2026-10-05): 0.9 to
    # 3.1 s. The smallest nonzero sample is the flush threshold's size, never
    # a subnormal.
    for s in tool["silence"]:
        assert s["held"] and 0.0 < s["zero_after_s"] < 6.0, s
        assert s["smallest"] >= 1e-20, s


def test_host_rates(tool):
    accepted = {rate: ok for rate, ok in tool["rates"]}
    assert accepted == {"0": False, "7999": False, "8000": True, "32000": True,
                        "44118": True, "48000": True, "384000": True, "400000": False,
                        "nan": False, "inf": False, "-44118": False}


def test_maths_without_libm(tool):
    # fx_room_math.h against libm in double precision. Log2's error is the
    # rounding of results up to 20 in size (one ulp there is 1.9e-6); pow's
    # is that times the exponent (up to 4 at an 8 kHz host).
    m = tool["maths"]
    assert m["log2_abs"] < 1.2e-6
    assert m["exp2_rel"] < 2e-7
    assert m["pow_rel"] < 2e-6
    assert m["identity"]                                  # g^1 is g, bit for bit
    assert m["subnormal_rel"] < 1e-5
    assert m["exp2_low"] == 0.0 and m["exp2_high"] == pytest.approx(2.0 ** 127, rel=1e-8)
