"""Room against the upstream Mutable Instruments classes it wraps
(engines/src/fx_room.cc, engines/README.md "Room"): clouds::Diffuser and
clouds::Reverb, vendored unmodified, driven by build/fm1-ref-room
(engines/test/ref_room.cc) the way Clouds' granular processor drives them,
the diffuser and then the reverb in place, in 32-frame blocks.

The fm1 side is fm1-render, whose 16-bit output is the resolution of every
comparison: "within quantisation" means no sample further than about half an
LSB from the reference scaled the way the wrapper scales it. The loop stores
12-bit words, so a coefficient one ulp away from the reference's would
eventually flip a truncation and miss by whole LSBs (4.4 LSB in the run that
found a constant typed in double precision here); every match below is
therefore exact up to the 16-bit rounding.

- At Clouds' rate (32,000 Hz): the knobs mapped to the coefficients they
  set, Mix 1 and Width 1, against the classes at full wet, with the diffuser
  (Blur) off, half and full; and with Clouds' own settings for its reverb
  and feedback knobs, Mix at Clouds' own amount.
- The wrapper's additions, modelled on the reference's output: Mix against
  the dry input rather than the diffused one, and Width.
- At the FM-1's rate (44,118 Hz): the classes with Room's rate rule applied
  (the reference calls the same libm-free functions), a stereo input (Plate's
  output) through Room, and decay rates in seconds against Clouds' rate.
"""
import json
import math
import struct
import subprocess

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401
from tests.test_engines_reference_braids_fx import (
    HOST_RATE, POST_GAIN, assert_quantisation_only, edc_slope, f32, fm1_input,
    fx_chain_fm1, fx_ref, plate_knobs, read_wav, run_json, write_float_wav)

REF = ENGINES / "build" / "fm1-ref-room"
CLOUDS_RATE = 32000.0
INPUTS = ("impulse", "noise", "sine")


@pytest.fixture(scope="session")
def tools(renderer):  # noqa: F811
    assert REF.exists(), "make -C engines builds build/fm1-ref-room"
    return renderer, REF


@pytest.fixture(scope="session")
def room_binary():
    subprocess.run(["make", "-C", str(ENGINES), "build/fm1-ref-room"], check=True,
                   stdout=subprocess.DEVNULL)
    return REF


def room_ref(tmp_path, input, seconds, args, name, rate=CLOUDS_RATE):
    wav = tmp_path / f"ref_{name}.wav"
    summary = run_json([REF, "--input", input, "--seconds", seconds, "--rate", repr(rate),
                        *args, "--out", wav])
    assert summary["nonfinite"] == 0 and summary["block"] == 32
    _, (left, right) = read_wav(wav)
    return summary, left, right


def room_fm1(render, tmp_path, input, seconds, rate, params, name):
    return fx_chain_fm1(render, tmp_path, input, seconds, rate, [("room", params)], name)


def test_room_rejects_unrepresentable_sample_requests(room_binary, tmp_path):
    ref = room_binary
    cases = [
        ("--rate", "inf", "finite and positive"),
        ("--rate", "nan", "finite and positive"),
        ("--rate", "1e20", "representable WAV range"),
        ("--seconds", "inf", "finite and positive"),
        ("--seconds", "nan", "finite and positive"),
        ("--seconds", "536870912", "representable WAV frame count"),
        ("--seconds", "1e308", "representable WAV frame count"),
    ]
    for index, (option, value, diagnostic) in enumerate(cases):
        out = tmp_path / f"invalid-{index}.wav"
        result = subprocess.run(
            [str(ref), "--input", "silence", option, value, "--out", str(out)],
            capture_output=True, text=True)
        assert result.returncode == 2, (option, value, result.stderr)
        assert diagnostic in result.stderr, (option, value, result.stderr)
        assert not out.exists(), "invalid request must be rejected before creating output"


def test_room_accepts_a_small_valid_render(room_binary, tmp_path):
    ref = room_binary
    out = tmp_path / "small.wav"
    result = subprocess.run(
        [str(ref), "--input", "impulse", "--seconds", "0.004", "--rate", "8000",
         "--out", str(out)], check=True, capture_output=True, text=True)
    summary = json.loads(result.stdout)
    wav_rate, channels = read_wav(out)
    assert summary["frames"] == 32
    assert wav_rate == 8000
    assert len(channels) == 2 and all(len(channel) == 32 for channel in channels)


# The wrapper's knob laws, in float32 as fx_room.cc computes them (one
# rounding per operation: the file has contraction off).
F98, F97, F67 = f32(0.98), f32(0.97), f32(0.67)


def decay_time(x):
    return f32(F98 * f32(f32(x) * f32(x)))


def damping_lp(x):
    return f32(F97 - f32(F67 * f32(x)))


def diffusion_kap(x):
    return f32(0.5 + f32(0.25 * f32(x)))


def knobs(decay, damping, diffusion, blur, mix=1.0, width=1.0):
    return [f"Mix={mix!r}", f"Decay={decay!r}", f"Damping={damping!r}",
            f"Diffusion={diffusion!r}", f"Blur={blur!r}", f"Width={width!r}"]


def coefficients(decay, damping, diffusion, blur, amount=1.0):
    """The reference's options for the coefficients those knobs set."""
    return ["--time", repr(decay_time(decay)), "--lp", repr(damping_lp(damping)),
            "--diffusion", repr(diffusion_kap(diffusion)), "--blur", repr(blur),
            "--amount", repr(amount)]


def exact_knob(target, law, guess):
    """The float32 knob value nearest guess that the law maps exactly onto
    target, or None."""
    guess = min(max(guess, 0.0), 1.0)
    bits = struct.unpack("<I", struct.pack("<f", f32(guess)))[0]
    for step in range(64):
        for b in (bits + step, bits - step):
            if b < 0:
                continue
            x = struct.unpack("<f", struct.pack("<I", b))[0]
            if law(x) == target:
                return x
    return None


# Decay, Damping, Diffusion: the default room, a long bright one at low
# diffusion, a short dark one at full diffusion.
PATCHES = ((0.5, 0.4, 0.8), (0.9, 0.1, 0.2), (0.25, 0.9, 1.0))


@pytest.mark.parametrize("blur", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("patch", PATCHES, ids=lambda p: "d%s-k%s-a%s" % p)
@pytest.mark.parametrize("input", INPUTS)
def test_room_matches_clouds_at_its_rate(tools, tmp_path, input, patch, blur):
    # Mix 1 and Width 1: the classes' output, sample for sample. The reverb
    # runs at full wet in both (amount 1); the wrapper's crossfade from the
    # dry at Mix 1 rounds no further than a few ulps of the input.
    render, _ = tools
    ref, rl, rr = room_ref(tmp_path, input, 1.0, coefficients(*patch, blur), "c")
    assert f32(ref["time"]) == decay_time(patch[0]) and f32(ref["input_gain"]) == f32(0.2)
    _, gl, gr = room_fm1(render, tmp_path, input, 1.0, CLOUDS_RATE, knobs(*patch, blur), "c")
    assert_quantisation_only((gl, gr), (rl, rr))


def test_blur_changes_the_output(tools, tmp_path):
    # A comparison that Blur did not change would prove nothing about it.
    _, a, _ = room_ref(tmp_path, "noise", 0.5, coefficients(0.5, 0.4, 0.8, 0.0), "b0")
    _, b, _ = room_ref(tmp_path, "noise", 0.5, coefficients(0.5, 0.4, 0.8, 1.0), "b1")
    assert max(abs(x - y) for x, y in zip(a, b)) > 0.05


# Clouds' reverb and feedback knobs (freeze off): reverb_amount 0.95 R,
# time 0.35 + 0.63 reverb_amount, lp 0.6 + 0.37 F, diffusion 0.7, amount
# 0.54 reverb_amount. The R values are ones whose time Decay's square law
# reaches exactly: 11 of R = 0.05, 0.10, ... 1.00 are (Damping's affine law
# reaches every lp of F = 0, 0.05, ... 1).
CLOUDS_PATCHES = ((0.2, 0.0), (0.5, 0.5), (0.95, 1.0))


@pytest.mark.parametrize("patch", CLOUDS_PATCHES, ids=lambda p: "r%s-f%s" % p)
@pytest.mark.parametrize("input", INPUTS)
def test_room_with_clouds_own_settings(tools, tmp_path, input, patch):
    # Room's knobs set to the values that give Clouds' coefficients exactly,
    # Mix at Clouds' own amount, Blur 0 (Clouds' granular mode below Texture
    # 0.75), against the reverb crossfading in place as Clouds runs it.
    render, _ = tools
    reverb, feedback = patch
    ref, rl, rr = room_ref(tmp_path, input, 1.0,
                           ["--reverb", repr(reverb), "--feedback", repr(feedback)], "cs")
    time, lp = f32(ref["time"]), f32(ref["lp"])
    assert f32(ref["diffusion"]) == f32(0.7) == diffusion_kap(0.8)
    decay = exact_knob(time, decay_time, math.sqrt(time / 0.98))
    damping = exact_knob(lp, damping_lp, (0.97 - lp) / 0.67)
    assert decay is not None and damping is not None, (time, lp)
    _, gl, gr = room_fm1(render, tmp_path, input, 1.0, CLOUDS_RATE,
                         knobs(decay, damping, 0.8, 0.0, mix=f32(ref["amount"])), "cs")
    assert_quantisation_only((gl, gr), (rl, rr))


@pytest.mark.parametrize("width", [0.0, 0.5])
@pytest.mark.parametrize("mix,blur", [(0.5, 0.0), (0.3, 0.5), (0.7, 1.0)])
@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_mix_and_width_are_the_documented_additions(tools, tmp_path, input, mix, blur, width):
    # The reference at full wet gives the classes' two outputs w; Room then
    # narrows them towards their mean m (Width 0: m on both sides; otherwise
    # w + (1 - Width)(m - w)) and crossfades from the undiffused input:
    # dry + Mix (wet - dry). The default room otherwise.
    render, _ = tools
    patch = (0.5, 0.4, 0.8)
    _, rl, rr = room_ref(tmp_path, input, 0.5, coefficients(*patch, blur), "mw")
    _, gl, gr = room_fm1(render, tmp_path, input, 0.5, CLOUDS_RATE,
                         knobs(*patch, blur, mix=mix, width=width), "mw")
    dry = fm1_input(input, len(rl))
    narrow = 1.0 - width
    out_l, out_r = [], []
    for d, wl, wr in zip(dry, rl, rr):
        m = 0.5 * (wl + wr)
        ol, orr = (m, m) if width == 0.0 else (wl + narrow * (m - wl), wr + narrow * (m - wr))
        out_l.append(d + mix * (ol - d))
        out_r.append(d + mix * (orr - d))
    assert_quantisation_only((gl, gr), (out_l, out_r))
    if width == 0.0:
        assert gl == gr


# ---------------------------------------------------------------------------
# At the FM-1's rate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("patch", PATCHES, ids=lambda p: "d%s-k%s-a%s" % p)
@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_room_at_host_rate_is_clouds_with_the_loop_rescaled(tools, tmp_path, input, patch):
    # At 44,118 Hz Room is the two classes with exactly two coefficients
    # changed, time^r and 1 - (1 - lp)^r, r = 32,000 / 44,118, sample for
    # sample: every delay and LFO keeps its length in samples.
    render, _ = tools
    native, _, _ = room_ref(tmp_path, input, 0.05, coefficients(*patch, 0.5), "hn")
    ref, rl, rr = room_ref(tmp_path, input, 1.0,
                           [*coefficients(*patch, 0.5), "--compensate", repr(HOST_RATE)], "hh",
                           rate=HOST_RATE)
    assert ref["native_over_host"] == pytest.approx(CLOUDS_RATE / HOST_RATE)
    assert f32(ref["time"]) > f32(native["time"]) and f32(ref["lp"]) < f32(native["lp"])
    _, gl, gr = room_fm1(render, tmp_path, input, 1.0, HOST_RATE, knobs(*patch, 0.5), "hh")
    assert_quantisation_only((gl, gr), (rl, rr))


def test_room_after_plate_at_host_rate(tools, tmp_path):
    # Plate (Rings' reverb, already checked against upstream) into Room at
    # its defaults, 44,118 Hz: upstream's plate output rebuilt by the
    # Braids/FX reference tool, fed to fm1-ref-room as a stereo file with the
    # rate rule applied; Room's dry side is Plate's output, each side its own.
    render, _ = tools
    args = ["--damping", "0.5", "--brightness", "0.5", "--amount", "1"]
    native, _, _ = fx_ref(tmp_path, "plate", "noise", 0.1, args, "pn")
    _, pl, pr = fx_ref(tmp_path, "plate", "noise", 0.5,
                       args + ["--rate", repr(HOST_RATE), "--compensate", repr(HOST_RATE)], "ph")
    assert max(abs(a - b) for a, b in zip(pl, pr)) > 1e-3, "not a stereo input"
    wav = write_float_wav(tmp_path / "plate.wav", [pl, pr], HOST_RATE)
    defaults = (0.5, 0.4, 0.8, 0.5)
    _, rl, rr = room_ref(tmp_path, "silence", 0.5,
                         ["--input-file", wav, *coefficients(*defaults),
                          "--compensate", repr(HOST_RATE)], "pr", rate=HOST_RATE)
    _, gl, gr = fx_chain_fm1(render, tmp_path, "noise", 0.5, HOST_RATE,
                             [("plate", plate_knobs(native, 0.5)), ("room", [])], "pr")
    mix = 0.3
    ml = [d + mix * (w - d) for d, w in zip(pl, rl)]
    mr = [d + mix * (w - d) for d, w in zip(pr, rr)]
    assert_quantisation_only((gl, gr), (ml, mr))


def burst(rate, seconds, on=0.5):
    """fm1-render's noise for `on` seconds, then silence."""
    x = fm1_input("noise", int(on * rate))
    return x + [0.0] * (int(seconds * rate) - len(x))


def burst_fm1(render, tmp_path, rate, seconds, params, name, on=0.5):
    """The same burst through Room in fm1-render: its noise, the bus set to
    silence from `on` seconds (the host's fault option acts before the
    effects), then the post gain."""
    wav = tmp_path / f"fm1_{name}.wav"
    cmd = [render, "--input", "noise", "--seconds", seconds, "--rate", repr(rate),
           "--fault", f"{on}..{seconds}:0", "--fx", "room"]
    for p in params:
        cmd += ["--fx-param", p]
    cmd += ["--fx", "test-gain", "--fx-param", f"Gain={POST_GAIN}", "--out", wav]
    summary = run_json(cmd)
    assert summary["nonfinite"] == 0 and summary["raw_peak"] < 0.98
    _, (left, right) = read_wav(wav)
    return left, right


# Measured ratios of Room's decay rate (dB/s) to Clouds' (2026-10-05): 1.49,
# 1.40, 1.20, 1.11, 1.08, 1.05 and 1.04 at Decay 0, 0.25, 0.5, 0.7, 0.8, 0.9
# and 0.95. The rule rescales the loop gain and the damping; the all-passes'
# own ring (Diffusion, and Clouds' fixed 0.625 in the diffuser) is not
# rescaled, as in Plate, so where the loop gain is small and the all-passes
# set the tail, Room decays about as much faster as the room is smaller.
DECAY_RATIO = {0.0: (1.3, 1.6), 0.5: (1.1, 1.3), 0.8: (1.0, 1.12), 0.95: (1.0, 1.1)}


@pytest.mark.parametrize("decay", sorted(DECAY_RATIO))
def test_rate_rule_keeps_the_decay_rate_in_seconds(tools, tmp_path, decay):
    # A noise burst's tail, Schroeder-integrated from 0.05 to 0.5 s after the
    # burst: Room at 44,118 Hz against the classes at Clouds' rate. The same
    # upstream samples played at 44,118 Hz decay 44,118 / 32,000 = 1.38 times
    # as fast in dB per second (the loop is that much shorter in seconds);
    # with the loop gain and damping rescaled, Room's tail decays at Clouds'
    # rate within 12 % from Decay 0.8 up.
    render, _ = tools
    patch = (decay, 0.4, 0.8, 0.5)
    seconds, on = 2.0, 0.5
    wav = write_float_wav(tmp_path / "burst.wav", [burst(CLOUDS_RATE, seconds, on)], CLOUDS_RATE)
    _, ul, ur = room_ref(tmp_path, "silence", seconds,
                         ["--input-file", wav, *coefficients(*patch)], "up")
    gl, gr = burst_fm1(render, tmp_path, HOST_RATE, seconds, knobs(*patch), "fm", on)
    t0, t1 = on + 0.05, on + 0.5
    up = edc_slope((ul, ur), CLOUDS_RATE, t0, t1)
    ratio = edc_slope((gl, gr), HOST_RATE, t0, t1) / up
    uncompensated = edc_slope((ul, ur), HOST_RATE, t0 * CLOUDS_RATE / HOST_RATE,
                              t1 * CLOUDS_RATE / HOST_RATE) / up
    assert up < -5
    assert uncompensated == pytest.approx(HOST_RATE / CLOUDS_RATE, rel=1e-3)
    low, high = DECAY_RATIO[decay]
    assert low < ratio < high, ratio
