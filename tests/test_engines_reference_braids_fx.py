"""Stage A's exit test for Shapes, Plate, Ensemble and Diffuse: renders
against the upstream Mutable Instruments classes they wrap (docs/11 §8,
engines/reference-braids-fx.md).

The upstream side is build/fm1-ref-braids-fx (engines/test/ref_braids_fx.cc):
the vendored braids::MacroOscillator driven as Braids' firmware drives it, and
rings::Reverb, plaits::Ensemble and plaits::Diffuser set up as Rings' part,
Plaits' string machine and Plaits' particle engine set them up. The fm1 side
is fm1-render, whose 16-bit output is the resolution of every comparison:
"within quantisation" below means no sample further than about half an LSB
from the reference scaled the way the wrapper scales it.

- Shapes, 96 kHz: all 47 shapes, two timbre/colour points, two pitches, in the
  FM-1's 64-frame host blocks; plus host-block independence, note-on timing,
  and the shapes that draw random numbers.
- Plate, Ensemble, Diffuse at their native rates, knobs mapped to the exact
  upstream coefficients, full wet and upstream's own mix; the wrappers'
  additions (Width, the tone filter, the wet gain, the mix law) modelled.
- The same effects at 44,118 Hz against the upstream classes with the rate
  rule of engines/mi-fx.md applied, decay rates against the native rate, and
  the Ensemble's delay measured in both.
"""
import json
import math
import struct
import subprocess
from array import array

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401

REF = ENGINES / "build" / "fm1-ref-braids-fx"

BRAIDS_RATE = 96000
RINGS_RATE = 48000.0
HOST_RATE = 44118.0


def f32(x):
    """x rounded to float32, as a Python float."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


PLAITS_RATE = f32(47872.34)            # plaits::kCorrectedSampleRate


@pytest.fixture(scope="session")
def tools(renderer):  # noqa: F811
    assert REF.exists(), "make -C engines builds build/fm1-ref-braids-fx"
    return renderer, REF


def read_wav(path):
    """(rate, [channel, ...]) for a 16-bit PCM or 32-bit float WAV."""
    data = path.read_bytes()
    pos, fmt = 12, None
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            tag, channels, rate, _, _, bits = fmt
            assert (tag, bits) in ((1, 16), (3, 32))
            samples = array("h" if tag == 1 else "f")
            samples.frombytes(body)
            return rate, [list(samples[c::channels]) for c in range(channels)]
        pos += 8 + size + (size & 1)
    raise ValueError(f"no data chunk in {path}")


def run_json(cmd):
    res = subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True)
    return json.loads(res.stdout)


# ---------------------------------------------------------------------------
# Shapes against braids::MacroOscillator
# ---------------------------------------------------------------------------

# Every shape at two timbre/colour points and two pitches: A2 and A6, which
# between them cross every pitch-dependent branch in the oscillators (above
# MIDI 80, 90 and 92).
POINTS = ((0.25, 0.75), (0.75, 0.25))
KEYS = (45, 93)

# The shapes that draw on stmlib::Random, found from the generator's state
# before and after a reference render (engines/reference-braids-fx.md).
RANDOM_SHAPES = (14, 22, 28, 30, 31, 33, 36, 40, 41, 42, 43, 44, 45)

# The wrapper's scale from the oscillator's int16 to the WAV's LSB at Volume 1
# and velocity 127: pcm * 0.25 / 32768, written as lrintf(x * 32767).
PCM_TO_LSB = 32767.0 / 131072.0


def knob16(v):
    """The int16 the Shapes wrapper passes Braids for a 0..1 knob."""
    return int(f32(f32(v) * 32767.0))


def envelope(n, rate=BRAIDS_RATE):
    """The wrapper's attack at Attack 0 (1 ms one-pole), in double precision."""
    k = 1.0 - math.exp(-1.0 / (0.001 * rate))
    e, out = 0.0, []
    for _ in range(n):
        e += (1.0 - e) * k
        out.append(e)
    return out


def braids_ref(tmp_path, shape, key, point, samples, seed=None):
    wav = tmp_path / f"braids_{shape}_{key}_{seed}.wav"
    cmd = [REF, "braids", "--shape", shape, "--pitch", key * 128,
           "--timbre", knob16(point[0]), "--color", knob16(point[1]),
           "--samples", samples, "--out", wav]
    if seed is not None:
        cmd += ["--seed", seed]
    summary = run_json(cmd)
    assert summary["block"] == 24 and summary["rate"] == BRAIDS_RATE
    return summary, read_wav(wav)[1][0]


def shapes_fm1(render, tmp_path, shape, key, point, seconds, frames=64, at=0.0):
    wav = tmp_path / f"shapes_{shape}_{key}_{frames}.wav"
    summary = run_json([render, "--engine", "shapes", "--param", f"Shape={shape}",
                        "--param", f"Timbre={point[0]}", "--param", f"Color={point[1]}",
                        "--param", "Attack=0", "--param", "Volume=1",
                        "--note", f"{at}:{key}:127:100", "--rate", BRAIDS_RATE,
                        "--frames", frames, "--seconds", seconds, "--out", wav])
    assert summary["raw_peak"] < 0.98            # the bus limiter stays out
    rate, (left, right) = read_wav(wav)
    assert rate == BRAIDS_RATE and left == right
    return left, wav


def oscillator_error(ref, got, offset=0):
    """Worst and rms distance, in LSB, between fm1's samples from offset on and
    the reference oscillator through the wrapper's envelope and gain."""
    env = envelope(len(ref))
    errs = [g - r * e * PCM_TO_LSB for g, r, e in zip(got[offset:], ref, env)]
    return max(abs(x) for x in errs), math.sqrt(sum(x * x for x in errs) / len(errs))


# Half an LSB of rounding, plus the float envelope, which settles a few
# parts per million under 1 (about 0.03 LSB at the largest samples).
WORST_LSB = 0.55
RMS_LSB = 0.35


@pytest.mark.parametrize("point", POINTS, ids=["t25c75", "t75c25"])
@pytest.mark.parametrize("shape", range(47))
def test_shape_matches_braids(tools, tmp_path, shape, point):
    render, _ = tools
    for key in KEYS:
        ref_summary, ref = braids_ref(tmp_path, shape, key, point, 9600)
        got, _ = shapes_fm1(render, tmp_path, shape, key, point, 0.1)
        assert ref_summary["peak"] > 100, "a silent reference proves nothing"
        worst, rms_err = oscillator_error(ref, got)
        assert worst <= WORST_LSB and rms_err <= RMS_LSB, (key, worst, rms_err)


# Shapes that step once per Braids block (struck envelopes, phase-increment
# interpolation, comb, vowel, wave line, granular): 64-frame host blocks
# rendered as 24 + 24 + 16 moved every one of them off upstream.
BLOCK_SENSITIVE = (0, 15, 22, 32, 33, 39, 44)


@pytest.mark.parametrize("shape", BLOCK_SENSITIVE)
def test_shapes_output_does_not_depend_on_the_host_block(tools, tmp_path, shape):
    render, _ = tools
    renders = []
    for frames in (1, 7, 24, 64, 100):
        _, wav = shapes_fm1(render, tmp_path, shape, 57, POINTS[0], 0.05, frames=frames)
        renders.append(wav.read_bytes())
    assert all(r == renders[0] for r in renders[1:])


@pytest.mark.parametrize("shape", [28, 32, 34, 44])
def test_note_on_starts_the_voice_at_a_braids_block_boundary(tools, tmp_path, shape):
    # A note at 0.0503 s reaches the engine with the host block at sample 4864
    # (76 x 64); Shapes has 8 samples of its current chunk left, so the voice
    # starts at 4872, a multiple of 24, exactly as a fresh Braids struck on
    # its first block (Pluck, Bell, Kick; Granular draws random numbers).
    render, _ = tools
    _, ref = braids_ref(tmp_path, shape, 57, POINTS[0], 4800)
    got, _ = shapes_fm1(render, tmp_path, shape, 57, POINTS[0], 0.1, at=0.0503)
    assert not any(got[:4872])
    worst, rms_err = oscillator_error(ref, got, offset=4872)
    assert worst <= WORST_LSB and rms_err <= RMS_LSB


def level_and_brightness(samples):
    """Level in dB and rms of the first difference over rms."""
    r = math.sqrt(sum(v * v for v in samples) / len(samples))
    d = math.sqrt(sum((b - a) ** 2 for a, b in zip(samples, samples[1:])) / len(samples))
    return 20 * math.log10(r), d / r


@pytest.mark.parametrize("shape", RANDOM_SHAPES)
def test_random_shapes_match_because_the_generator_state_matches(tools, tmp_path, shape):
    # Exact with the generator where fm1-render leaves it (0x21, as a fresh
    # Braids); visibly different from another starting state, so the exact
    # match depends on the random numbers; and, over one second, within 2 dB
    # and 25 % in brightness of three other starting states, which is how a
    # voice whose draws interleave with other voices' will relate to upstream.
    # Clocked Noise draws its seed at the strike but uses it only when its
    # timbre-set period wraps, which at timbre 0.25 takes longer than a
    # second: timbre 0.75 for that one.
    render, _ = tools
    point, key = POINTS[1] if shape == 43 else POINTS[0], 69
    got, _ = shapes_fm1(render, tmp_path, shape, key, point, 1.0)
    _, same = braids_ref(tmp_path, shape, key, point, 96000)
    assert oscillator_error(same, got)[0] <= WORST_LSB
    levels, brightness = [], []
    for seed in (1, 2, 3):
        _, other = braids_ref(tmp_path, shape, key, point, 96000, seed=seed)
        if seed == 1:
            assert oscillator_error(other, got)[0] > 2.0
        lv, br = level_and_brightness([v * PCM_TO_LSB for v in other])
        levels.append(lv)
        brightness.append(br)
    lv, br = level_and_brightness(got)
    assert abs(lv - sum(levels) / 3) < 2.0, (lv, levels)
    assert abs(br / (sum(brightness) / 3) - 1.0) < 0.25, (br, brightness)


# ---------------------------------------------------------------------------
# Effects against rings::Reverb, plaits::Ensemble and plaits::Diffuser
# ---------------------------------------------------------------------------

INPUTS = ("impulse", "noise", "sine")

# fm1-render's output goes through the bus limiter, which engages above 0.98;
# a Test Gain of 0.5 after the effect keeps it out of the way, and a factor
# of 0.5 is exact in float.
POST_GAIN = 0.5


def fx_ref(tmp_path, effect, input, seconds, args, name):
    wav = tmp_path / f"ref_{name}.wav"
    summary = run_json([REF, "fx", "--effect", effect, "--input", input,
                        "--seconds", seconds, *args, "--out", wav])
    assert summary["nonfinite"] == 0
    rate, (left, right) = read_wav(wav)
    return summary, left, right


def fx_fm1(render, tmp_path, effect, input, seconds, rate, params, name):
    wav = tmp_path / f"fm1_{name}.wav"
    cmd = [render, "--input", input, "--seconds", seconds, "--rate", repr(rate),
           "--fx", effect]
    for p in params:
        cmd += ["--fx-param", p]
    cmd += ["--fx", "test-gain", "--fx-param", f"Gain={POST_GAIN}", "--out", wav]
    summary = run_json(cmd)
    assert summary["raw_peak"] < 0.98 and summary["nonfinite"] == 0
    _, (left, right) = read_wav(wav)
    return summary, left, right


def lsb_error(got, model):
    """Worst and rms distance, in LSB, between fm1's 16-bit output and a float
    model of it before the post gain."""
    errs = [g - POST_GAIN * 32767.0 * m for g, m in zip(got, model)]
    assert len(errs) == len(model)
    return max(abs(x) for x in errs), math.sqrt(sum(x * x for x in errs) / len(errs))


# Half an LSB plus float rounding in the wrappers' own arithmetic.
FX_WORST_LSB = 0.51
FX_RMS_LSB = 0.30


def assert_quantisation_only(got_lr, model_lr):
    for got, model in zip(got_lr, model_lr):
        worst, rms_err = lsb_error(got, model)
        assert worst <= FX_WORST_LSB and rms_err <= FX_RMS_LSB, (worst, rms_err)


def affine(c0, c1, x):
    """float32 c0 + c1 * x, with and without a fused multiply-add: the knob
    mappings are compiled either way."""
    c0, c1, x = f32(c0), f32(c1), f32(x)
    return {f32(c0 + f32(c1 * x)), f32(c0 + c1 * x)}


def knob_for(target, mapping, guess):
    """The float32 knob value nearest guess for which the wrapper's mapping
    gives exactly the upstream coefficient target, however it is compiled."""
    bits = struct.unpack("<I", struct.pack("<f", f32(guess)))[0]
    for step in range(400):
        for b in (bits + step, bits - step):
            x = struct.unpack("<f", struct.pack("<I", b))[0]
            if mapping(x) == {target}:
                return x
    raise AssertionError(f"no knob value gives {target}")


def plate_knobs(ref, damping):
    """Plate's knobs for the coefficients Rings' part.cc computed: Decay is
    Rings' damping (the same 0.35 + 0.63 x), Damping the value whose
    0.9 - 0.6 x lands on Rings' 0.3 + 0.6 brightness, Diffusion 0.5 (0.625)."""
    lp = f32(ref["lp"])
    knob = knob_for(lp, lambda d: {f32(1.0 - f32(1.0 - k)) for k in affine(0.9, -0.6, d)},
                    (0.9 - lp) / 0.6)
    assert f32(ref["diffusion"]) == 0.625 and f32(ref["input_gain"]) == f32(0.2)
    return [f"Mix={ref['amount']!r}", f"Decay={f32(damping)!r}", f"Damping={knob!r}",
            "Diffusion=0.5"]


def diffuse_time_knob(ref):
    """Diffuse's Time for the rt Plaits' particle engine computed."""
    rt = f32(ref["rt"])
    return knob_for(rt, lambda t: affine(0.25, 0.65, t), (rt - 0.25) / 0.65)


# Rings' damping and brightness: dark and short, the middle, long and darker.
RINGS_PATCHES = ((0.3, 0.8), (0.5, 0.5), (0.7, 0.4))


@pytest.mark.parametrize("full_wet", [True, False], ids=["wet", "rings-amount"])
@pytest.mark.parametrize("patch", RINGS_PATCHES, ids=lambda p: f"d{p[0]}b{p[1]}")
@pytest.mark.parametrize("input", INPUTS)
def test_plate_matches_rings_reverb(tools, tmp_path, input, patch, full_wet):
    # Plate is rings::Reverb with Rings' settings, at Mix 1 or at the amount
    # Rings itself uses (0.1 + 0.5 damping); its input guard does nothing to
    # finite input within +/-16. Within quantisation, both channels.
    render, _ = tools
    damping, brightness = patch
    args = ["--damping", damping, "--brightness", brightness]
    if full_wet:
        args += ["--amount", "1"]
    ref, rl, rr = fx_ref(tmp_path, "plate", input, 1.0, args, "plate")
    _, gl, gr = fx_fm1(render, tmp_path, "plate", input, 1.0, RINGS_RATE,
                       plate_knobs(ref, damping), "plate")
    assert_quantisation_only((gl, gr), (rl, rr))


@pytest.mark.parametrize("timbre", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("input", INPUTS)
def test_ensemble_matches_plaits_ensemble(tools, tmp_path, input, timbre):
    # Width 0 is upstream's mono behaviour; Depth is upstream's depth
    # (0.35 + 0.65 timbre in the string machine), Mix 1 its amount 1. The
    # wrapper runs upstream at amount 1 and remixes the recovered wet itself.
    render, _ = tools
    ref, rl, rr = fx_ref(tmp_path, "ensemble", input, 1.0,
                         ["--timbre", timbre, "--amount", "1"], "ens")
    _, gl, gr = fx_fm1(render, tmp_path, "ensemble", input, 1.0, PLAITS_RATE,
                       ["Mix=1", f"Depth={ref['depth']!r}", "Width=0"], "ens")
    assert_quantisation_only((gl, gr), (rl, rr))


def fm1_input(kind, n):
    """fm1-render's impulse and noise inputs, sample for sample."""
    if kind == "impulse":
        return [1.0] + [0.0] * (n - 1)
    state, out = 0x12345678, []
    for _ in range(n):
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        signed = state - (1 << 32) if state & 0x80000000 else state
        out.append(f32(0.5 * f32(f32(float(signed)) / 2147483648.0)))
    return out


@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_ensemble_width_and_mix_are_the_documented_additions(tools, tmp_path, input):
    # Default settings (Mix 0.5, Depth 0.5, Width 1): upstream at amount 1 fed
    # the input on the left and the input 131 samples later on the right, then
    # the wet recovered as out - line / 2 and mixed with Plaits' law against
    # the undelayed dry: wet * mix + dry * (1 - mix / 2).
    render, _ = tools
    ref, rl, rr = fx_ref(tmp_path, "ensemble", input, 0.5,
                         ["--amount", "1", "--depth", "0.5", "--right-delay", "131"], "ensw")
    _, gl, gr = fx_fm1(render, tmp_path, "ensemble", input, 0.5, PLAITS_RATE, [], "ensw")
    dry = fm1_input(input, len(rl))
    late = [0.0] * 131 + dry[:-131]
    mix = 0.5
    ml = [(a - 0.5 * x) * mix + x * (1 - mix / 2) for a, x in zip(rl, dry)]
    mr = [(a - 0.5 * y) * mix + x * (1 - mix / 2) for a, x, y in zip(rr, dry, late)]
    assert_quantisation_only((gl, gr), (ml, mr))


def one_pole(x, k):
    y, out = 0.0, []
    for v in x:
        y += k * (v - y)
        out.append(y)
    return out


def schroeder(x, n, g):
    line, pos, out = [0.0] * n, 0, []
    for v in x:
        delayed = line[pos]
        w = v + g * delayed
        line[pos] = w
        pos = (pos + 1) % n
        out.append(delayed - g * w)
    return out


def tone_k(tone, rate):
    fc = 250.0 * 2.0 ** (7.0 * tone)
    return 1.0 - math.exp(-2.0 * math.pi * fc / rate)


def diffuse_model(wet, dry, rate, mix=1.0, tone=1.0, width=0.0):
    """Diffuse's documented additions around upstream's wet: half its level,
    the decorrelating all-passes (241 and 349 samples, g 0.5) at Width, the
    one-pole tone filter, and a crossfade from the dry."""
    w = [0.5 * v for v in wet]
    k = tone_k(tone, rate)
    out = []
    for n in (241, 349):
        side = w if width == 0.0 else [a + width * (b - a) for a, b in zip(w, schroeder(w, n, 0.5))]
        wet_side = one_pole(side, k)
        out.append([d + mix * (s - d) for d, s in zip(dry, wet_side)])
    return out


# Plaits' particle engine's morph: 0.5 gives rt 0.25 (Time 0), 0.25 rt 0.375,
# 0 its longest, rt 0.75.
MORPHS = (0.5, 0.25, 0.0)


@pytest.mark.parametrize("morph", MORPHS)
@pytest.mark.parametrize("input", INPUTS)
def test_diffuse_matches_plaits_diffuser(tools, tmp_path, input, morph):
    # Width 0 and Tone 1 (a one-pole at 32 kHz: not flat, so modelled), Mix
    # 1, Time mapped to the particle engine's rt; upstream at amount 1.
    render, _ = tools
    ref, rl, rr = fx_ref(tmp_path, "diffuse", input, 1.0,
                         ["--morph", morph, "--amount", "1"], "dif")
    assert rl == rr
    _, gl, gr = fx_fm1(render, tmp_path, "diffuse", input, 1.0, PLAITS_RATE,
                       ["Mix=1", f"Time={diffuse_time_knob(ref)!r}", "Tone=1", "Width=0"],
                       "dif")
    assert_quantisation_only((gl, gr), diffuse_model(rl, [0.0] * len(rl), PLAITS_RATE))


@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_diffuse_defaults_are_the_documented_additions(tools, tmp_path, input):
    # Mix 0.5, Tone 0.75 (about 9.5 kHz), Width 1, and rt 0.375 (the
    # particle engine at morph 0.25).
    render, _ = tools
    ref, rl, _ = fx_ref(tmp_path, "diffuse", input, 0.5, ["--morph", "0.25", "--amount", "1"],
                        "difd")
    _, gl, gr = fx_fm1(render, tmp_path, "diffuse", input, 0.5, PLAITS_RATE,
                       [f"Time={diffuse_time_knob(ref)!r}"], "difd")
    dry = fm1_input(input, len(rl))
    assert_quantisation_only((gl, gr), diffuse_model(rl, dry, PLAITS_RATE, mix=0.5,
                                                     tone=0.75, width=1.0))


# ---------------------------------------------------------------------------
# At the FM-1's rate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("damping", [0.3, 0.5, 0.7])
@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_plate_at_host_rate_is_rings_with_the_loop_rescaled(tools, tmp_path, input, damping):
    # At 44,118 Hz Plate is rings::Reverb with exactly two settings changed,
    # time^(48000/44118) and 1 - (1 - lp)^(48000/44118) (mi-fx.md), sample
    # for sample: every delay and LFO keeps its length in samples.
    render, _ = tools
    args = ["--damping", damping, "--brightness", "0.5", "--amount", "1"]
    native, _, _ = fx_ref(tmp_path, "plate", input, 1.0, args, "pn")
    ref, rl, rr = fx_ref(tmp_path, "plate", input, 1.0,
                         args + ["--rate", "44118", "--compensate", "44118"], "ph")
    assert f32(ref["time"]) < f32(native["time"]) and f32(ref["lp"]) > f32(native["lp"])
    _, gl, gr = fx_fm1(render, tmp_path, "plate", input, 1.0, HOST_RATE,
                       plate_knobs(native, damping), "ph")
    assert_quantisation_only((gl, gr), (rl, rr))


@pytest.mark.parametrize("morph", [0.0, 0.25])
def test_diffuse_at_host_rate_is_plaits_with_the_loop_rescaled(tools, tmp_path, morph):
    render, _ = tools
    args = ["--morph", morph, "--amount", "1"]
    native, _, _ = fx_ref(tmp_path, "diffuse", "noise", 1.0, args, "dn")
    ref, rl, _ = fx_ref(tmp_path, "diffuse", "noise", 1.0,
                        args + ["--rate", "44118", "--compensate", "44118"], "dh")
    _, gl, gr = fx_fm1(render, tmp_path, "diffuse", "noise", 1.0, HOST_RATE,
                       ["Mix=1", f"Time={diffuse_time_knob(native)!r}", "Tone=1", "Width=0"],
                       "dh")
    assert_quantisation_only((gl, gr), diffuse_model(rl, [0.0] * len(rl), HOST_RATE))


@pytest.mark.parametrize("depth", ["0", "1"])
def test_ensemble_at_host_rate_is_plaits_unchanged(tools, tmp_path, depth):
    # Nothing in the Ensemble is rate-compensated: at 44,118 Hz it is the
    # upstream class sample for sample, so its delays and LFOs are 8.5 %
    # longer and slower in seconds.
    render, _ = tools
    _, rl, rr = fx_ref(tmp_path, "ensemble", "noise", 1.0,
                       ["--amount", "1", "--depth", depth, "--rate", "44118"], "eh")
    _, gl, gr = fx_fm1(render, tmp_path, "ensemble", "noise", 1.0, HOST_RATE,
                       ["Mix=1", f"Depth={depth}", "Width=0"], "eh")
    assert_quantisation_only((gl, gr), (rl, rr))


def edc_slope(channels, rate, t0, t1):
    """Slope in dB/s of the Schroeder energy-decay curve between t0 and t1."""
    energy = [sum(c[i] * c[i] for c in channels) for i in range(len(channels[0]))]
    tail = [0.0] * (len(energy) + 1)
    for i in range(len(energy) - 1, -1, -1):
        tail[i] = tail[i + 1] + energy[i]
    level = [10 * math.log10(tail[int(t * rate)] + 1e-30) for t in (t0, t1)]
    return (level[1] - level[0]) / (t1 - t0)


def test_rate_compensation_keeps_most_of_the_decay_rate(tools, tmp_path):
    # Impulse tails, fm1 at 44,118 Hz against the upstream class at its own
    # rate. Measured: Plate 0.961 / 0.967 / 0.970 at Rings damping 0.3 / 0.5
    # / 0.7 (uncompensated 0.915 / 0.921 / 0.927, the same upstream samples
    # read at 44,118 Hz); Diffuse at rt 0.75 0.961 (uncompensated 0.917).
    render, _ = tools
    for damping in (0.3, 0.5, 0.7):
        args = ["--damping", damping, "--brightness", "0.5", "--amount", "1"]
        native, rl, rr = fx_ref(tmp_path, "plate", "impulse", 2.0, args, "pd")
        _, gl, gr = fx_fm1(render, tmp_path, "plate", "impulse", 2.0, HOST_RATE,
                           plate_knobs(native, damping), "pd")
        up = edc_slope((rl, rr), RINGS_RATE, 0.05, 0.6)
        ratio = edc_slope((gl, gr), HOST_RATE, 0.05, 0.6) / up
        uncompensated = edc_slope((rl, rr), HOST_RATE, 0.05, 0.6) / up
        assert 0.95 < ratio < 0.99 and 0.90 < uncompensated < 0.935, (damping, ratio)
    native, rl, _ = fx_ref(tmp_path, "diffuse", "impulse", 2.0, ["--morph", "0", "--amount", "1"],
                           "dd")
    _, gl, gr = fx_fm1(render, tmp_path, "diffuse", "impulse", 2.0, HOST_RATE,
                       ["Mix=1", f"Time={diffuse_time_knob(native)!r}", "Tone=1", "Width=0"],
                       "dd")
    up = edc_slope((rl,), PLAITS_RATE, 0.05, 0.5)
    ratio = edc_slope((gl, gr), HOST_RATE, 0.05, 0.5) / up
    uncompensated = edc_slope((rl,), HOST_RATE, 0.05, 0.5) / up
    assert 0.95 < ratio < 0.98 and 0.90 < uncompensated < 0.93, ratio


def test_ensemble_delay_is_192_samples_at_any_rate(tools, tmp_path):
    # Depth 0 holds the three taps at their centre, 192 samples: 4.01 ms at
    # Plaits' rate, 4.35 ms at 44,118 Hz. The wet is the output less the dry
    # half (Mix 1), and the three taps of 0.33 sum to 0.99.
    render, _ = tools
    delays = {}
    for rate in (PLAITS_RATE, HOST_RATE):
        _, gl, _ = fx_fm1(render, tmp_path, "ensemble", "impulse", 0.02, rate,
                          ["Mix=1", "Depth=0", "Width=0"], "eir")
        wet = [g / (POST_GAIN * 32767.0) for g in gl]
        wet[0] -= 0.5
        peak = max(range(len(wet)), key=lambda i: abs(wet[i]))
        assert abs(wet[peak] - 0.99) < 1e-4
        assert sum(w * w for i, w in enumerate(wet) if i != peak) < 1e-8
        delays[rate] = peak / rate * 1000.0
        assert peak == 192
    assert abs(delays[PLAITS_RATE] - 4.011) < 0.001
    assert abs(delays[HOST_RATE] - 4.352) < 0.001
