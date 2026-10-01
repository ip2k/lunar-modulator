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
  FM-1's 64-frame host blocks; plus host-block independence (odd sizes
  included), note-on timing, a retrigger's strike, the wrapper's velocity and
  release, and the shapes that draw random numbers, exactly against the same
  random stream and statistically against Braids' firmware, chords included.
  At 44,118 Hz, where Shapes runs Braids at 96 kHz and resamples, the struck
  shapes decay as upstream's; every shape at that rate is matched against
  upstream resampled in test_engines_resampler.py.
- Plate, Ensemble, Diffuse at their native rates, knobs mapped to the exact
  upstream coefficients, full wet and upstream's own mix; the wrappers'
  additions (Width, the tone filter, the wet gain, the mix law) modelled, at
  more than one point each.
- The same effects at 44,118 Hz against the upstream classes with the rate
  rule of engines/mi-fx.md applied, decay rates against the native rate, the
  Ensemble's delay measured in both, and a stereo input (Plate's output)
  through Ensemble and Diffuse.
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
# Shapes' resampler delays its output by this many host samples at any host
# rate but 96 kHz (FM1_RESAMPLER_DELAY; test_engines_resampler.py checks it).
RESAMPLER_DELAY = 30


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

# The shapes whose digital renderer writes two samples per loop pass (Vowel
# FOF, Harmonics, Pluck, Bowed, Bell, Drum, Kick, Snare, Wave x4, Twin Peaks,
# Particle): an odd render size runs off the end of the buffer.
TWO_PER_PASS = (23, 24, 28, 29, 32, 33, 34, 36, 40, 42, 45)

# The wrapper's scale from the oscillator's int16 to the WAV's LSB at Volume 1
# and velocity 127: pcm * 0.25 / 32768, written as lrintf(x * 32767).
PCM_TO_LSB = 32767.0 / 131072.0


def knob16(v):
    """The int16 the Shapes wrapper passes Braids for a 0..1 knob."""
    return int(f32(f32(v) * 32767.0))


def knob_seconds(knob):
    """The wrapper's attack and release time for a 0..1 knob: 1 ms .. 4 s."""
    return 0.001 * 4000.0 ** knob


def envelope(n, rate=BRAIDS_RATE, segments=None):
    """The wrapper's envelope, in double precision: a one-pole towards each
    segment's target, [(samples, target, time knob), ...]. By default the
    attack at Attack 0 (1 ms) towards velocity 127, held."""
    e, out = 0.0, []
    for count, target, knob in segments or [(n, 1.0, 0.0)]:
        k = 1.0 - math.exp(-1.0 / (knob_seconds(knob) * rate))
        for _ in range(count):
            e += (target - e) * k
            out.append(e)
    assert len(out) == n
    return out


def braids_ref(tmp_path, shape, key, point, samples, seed=None, strikes=None, jitter=False,
               name=""):
    wav = tmp_path / f"braids_{shape}_{key}_{seed}_{jitter}_{name}.wav"
    cmd = [REF, "braids", "--shape", shape, "--pitch", key * 128,
           "--timbre", knob16(point[0]), "--color", knob16(point[1]),
           "--samples", samples, "--out", wav]
    for b in strikes or ():
        cmd += ["--strike-block", b]
    if jitter:
        cmd += ["--jitter-draw", 1]
    if seed is not None:
        cmd += ["--seed", seed]
    summary = run_json(cmd)
    assert summary["block"] == 24 and summary["rate"] == BRAIDS_RATE
    assert summary["samples"] == samples
    return summary, read_wav(wav)[1][0]


def shapes_fm1(render, tmp_path, shape, key, point, seconds, frames=64, at=0.0, notes=None,
               params=(), rate=BRAIDS_RATE):
    wav = tmp_path / f"shapes_{shape}_{key}_{frames}_{len(notes or ())}.wav"
    cmd = [render, "--engine", "shapes", "--param", f"Shape={shape}",
           "--param", f"Timbre={point[0]}", "--param", f"Color={point[1]}",
           "--param", "Attack=0", "--param", "Volume=1"]
    for p in params:
        cmd += ["--param", p]
    for n in notes or [f"{at}:{key}:127:100"]:
        cmd += ["--note", n]
    cmd += ["--rate", rate, "--frames", frames, "--seconds", seconds, "--out", wav]
    summary = run_json(cmd)
    assert summary["raw_peak"] < 0.98            # the bus limiter stays out
    wav_rate, (left, right) = read_wav(wav)
    assert wav_rate == round(rate) and left == right
    return left, wav


def through_wrapper(ref, env=None):
    """The reference oscillator as the wrapper's envelope and gain scale it,
    in LSB of fm1's WAV."""
    env = env or envelope(len(ref))
    return [r * e * PCM_TO_LSB for r, e in zip(ref, env)]


def oscillator_error(ref, got, offset=0, env=None):
    """Worst and rms distance, in LSB, between fm1's samples from offset on and
    the reference oscillator through the wrapper's envelope and gain."""
    assert len(got) - offset == len(ref), (len(got), offset, len(ref))
    errs = [g - m for g, m in zip(got[offset:], through_wrapper(ref, env))]
    return max(abs(x) for x in errs), math.sqrt(sum(x * x for x in errs) / len(errs))


# Half an LSB of rounding, plus the float envelope, which settles a few
# parts per million under 1 (about 0.03 LSB at the largest samples). The
# rounding's rms is up to 0.34 LSB rather than 0.29, because the scaled
# int16 lies close to a quarter-LSB grid (Snare's retrigger: 0.339, all of
# it rounding).
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


@pytest.mark.parametrize("shape", sorted(set(BLOCK_SENSITIVE + TWO_PER_PASS)))
def test_shapes_output_does_not_depend_on_the_host_block(tools, tmp_path, shape):
    # 4,801 frames: every host block size here leaves an odd one, and 1 and 7
    # are odd throughout. Before the 24-sample fix the wrapper rendered those
    # sizes as they came, and the two-per-pass shapes overran their buffer
    # (SIGBUS here; a heap overflow under ASan).
    render, _ = tools
    renders = []
    for frames in (1, 7, 24, 64, 100):
        _, wav = shapes_fm1(render, tmp_path, shape, 57, POINTS[0], 0.050011, frames=frames)
        renders.append(wav.read_bytes())
    assert len(read_wav(wav)[1][0]) == 4801
    assert all(r == renders[0] for r in renders[1:])


def test_reference_renders_whole_even_blocks(tools, tmp_path):
    # The reference hands Braids only whole blocks of an even size: an odd
    # --block is refused, and an odd --samples ends with a whole block cut
    # short, so a render is a prefix of any longer one.
    for shape in TWO_PER_PASS:
        _, short = braids_ref(tmp_path, shape, 57, POINTS[0], 9601)
        _, long = braids_ref(tmp_path, shape, 57, POINTS[0], 9624, name="long")
        assert short == long[:9601]
    res = subprocess.run([str(REF), "braids", "--shape", "32", "--pitch", "7296", "--timbre",
                          "8191", "--color", "24575", "--block", "7", "--out",
                          str(tmp_path / "odd.wav")], capture_output=True)
    assert res.returncode == 2


@pytest.mark.parametrize("shape", [28, 32, 34, 44])
def test_note_on_starts_the_voice_at_a_braids_block_boundary(tools, tmp_path, shape):
    # A note at 0.0503 s reaches the engine with the host block at sample 4864
    # (76 x 64); Shapes has 8 samples of its current chunk left, so the voice
    # starts at 4872, a multiple of 24, exactly as a fresh Braids struck on
    # its first block (Pluck, Bell, Kick; Granular draws random numbers).
    render, _ = tools
    _, ref = braids_ref(tmp_path, shape, 57, POINTS[0], 9600 - 4872)
    got, _ = shapes_fm1(render, tmp_path, shape, 57, POINTS[0], 0.1, at=0.0503)
    assert not any(got[:4872])
    worst, rms_err = oscillator_error(ref, got, offset=4872)
    assert worst <= WORST_LSB and rms_err <= RMS_LSB


# The shapes a strike visibly changes when it lands on a running oscillator
# (Clocked Noise only at timbre 0.75), and four it leaves alone.
STRUCK = (14, 22, 28, 29, 30, 31, 32, 33, 34, 36, 40, 43)
UNSTRUCK = (0, 15, 35, 46)


@pytest.mark.parametrize("shape", STRUCK + UNSTRUCK)
def test_retrigger_strikes_the_running_voice(tools, tmp_path, shape):
    # The same key again while it is held reuses its voice, whose note-on
    # strikes it, as a Braids trigger strikes its one running oscillator. The
    # first note needs no Strike() of the wrapper's: DigitalOscillator::Init
    # sets the strike flag and set_shape strikes on the change from shape 0.
    # The second note, at 0.3003 s, reaches the engine with the host block at
    # 28,864 (451 x 64), and the voice's next chunk is Braids block 1,203.
    render, _ = tools
    point = POINTS[1] if shape == 43 else POINTS[0]
    n, block = 38400, 1203
    _, once = braids_ref(tmp_path, shape, 57, point, n)
    _, twice = braids_ref(tmp_path, shape, 57, point, n, strikes=(0, block), name="twice")
    change = max(abs(a - b) for a, b in zip(once, twice)) * PCM_TO_LSB
    assert once[:24 * block] == twice[:24 * block]
    if shape in STRUCK:
        assert change > 100, "a strike that changes nothing proves nothing"
    else:
        assert change == 0
    got, _ = shapes_fm1(render, tmp_path, shape, 57, point, 0.4,
                        notes=["0:57:127:100", "0.3003:57:127:100"])
    worst, rms_err = oscillator_error(twice, got)
    assert worst <= WORST_LSB and rms_err <= RMS_LSB, (worst, rms_err)


@pytest.mark.parametrize("shape", [0, 32])
def test_velocity_and_release_are_the_documented_envelope(tools, tmp_path, shape):
    # The wrapper's own envelope around the oscillator: velocity 64 sets its
    # target to 64/127, and the note-off at 0.0499 s reaches the engine with
    # the host block at 4,800, a chunk boundary, from which the voice falls
    # with Release 0.3's one-pole (0.001 x 4000^0.3 = 12.0 ms).
    render, _ = tools
    _, ref = braids_ref(tmp_path, shape, 57, POINTS[0], 9600)
    got, _ = shapes_fm1(render, tmp_path, shape, 57, POINTS[0], 0.1,
                        notes=["0:57:64:0.0499"], params=["Release=0.3"])
    env = envelope(9600, segments=[(4800, 64 / 127.0, 0.0), (4800, 0.0, 0.3)])
    worst, rms_err = oscillator_error(ref, got, env=env)
    assert worst <= WORST_LSB and rms_err <= RMS_LSB, (worst, rms_err)
    held = math.sqrt(sum(v * v for v in got[2400:4800]) / 2400)
    released = math.sqrt(sum(v * v for v in got[7200:]) / 2400)
    assert released < 0.1 * held


def level_and_brightness(samples):
    """Level in dB and rms of the first difference over rms."""
    r = math.sqrt(sum(v * v for v in samples) / len(samples))
    d = math.sqrt(sum((b - a) ** 2 for a, b in zip(samples, samples[1:])) / len(samples))
    return 20 * math.log10(r), d / r


def assert_statistically_close(got, references):
    """Level within 2 dB and brightness within 25 % of the references' mean."""
    stats = [level_and_brightness(r) for r in references]
    lv, br = level_and_brightness(got)
    mean_lv = sum(s[0] for s in stats) / len(stats)
    mean_br = sum(s[1] for s in stats) / len(stats)
    assert abs(lv - mean_lv) < 2.0, (lv, stats)
    assert abs(br / mean_br - 1.0) < 0.25, (br, stats)


def random_point(shape):
    # Clocked Noise draws its seed at the strike but uses it only when its
    # timbre-set period wraps, which at timbre 0.25 takes longer than a
    # second: timbre 0.75 for that one.
    return POINTS[1] if shape == 43 else POINTS[0]


@pytest.mark.parametrize("shape", RANDOM_SHAPES)
def test_random_shapes_match_given_the_same_random_stream(tools, tmp_path, shape):
    # Exact against the oscillator fed the stream fm1-render gives a lone
    # voice: stmlib's generator from its initial state, 0x21, with nothing
    # else drawing. That is a convention of the comparison, not Braids'
    # firmware (next test). From another starting state the output is
    # visibly different, so the exact match does depend on the numbers.
    render, _ = tools
    point = random_point(shape)
    got, _ = shapes_fm1(render, tmp_path, shape, 69, point, 1.0)
    summary, same = braids_ref(tmp_path, shape, 69, point, 96000)
    assert summary["random_start"] == 0x21 and summary["random_end"] != 0x21
    assert oscillator_error(same, got)[0] <= WORST_LSB
    _, other = braids_ref(tmp_path, shape, 69, point, 96000, seed=1)
    assert oscillator_error(other, got)[0] > 2.0


@pytest.mark.parametrize("shape", RANDOM_SHAPES)
def test_random_shapes_match_braids_firmware_statistically(tools, tmp_path, shape):
    # Braids' firmware draws one random word per block for its VCO jitter
    # before the oscillator renders, whatever the drift setting (braids.cc
    # RenderBlock, vco_jitter_source.h), and its generator's state at a
    # trigger depends on how long the module has run. Against that firmware
    # (--jitter-draw) at three starting states, over one second at A4: one
    # voice, and a two-voice chord (A4, E5) whose voices interleave their
    # draws, so neither sees a lone voice's stream. Level within 2 dB,
    # brightness within 25 % of the mean.
    render, _ = tools
    point = random_point(shape)
    solo, _ = shapes_fm1(render, tmp_path, shape, 69, point, 1.0)
    chord, _ = shapes_fm1(render, tmp_path, shape, 69, point, 1.0,
                          notes=["0:69:127:100", "0:76:127:100"])
    fw69 = [through_wrapper(braids_ref(tmp_path, shape, 69, point, 96000, seed=s, jitter=True)[1])
            for s in (0x21, 1, 2)]
    fw76 = [through_wrapper(braids_ref(tmp_path, shape, 76, point, 96000, seed=s, jitter=True)[1])
            for s in (3, 4, 5)]
    # The firmware's stream is not the lone voice's, even from 0x21.
    assert max(abs(a - b) for a, b in zip(solo, fw69[0])) > 2.0
    # In the chord, the voices' draws interleave: it is not two lone voices.
    lone76 = through_wrapper(braids_ref(tmp_path, shape, 76, point, 96000)[1])
    assert max(abs(c - a - b) for c, a, b in zip(chord, solo, lone76)) > 2.0
    assert_statistically_close(solo, fw69)
    assert_statistically_close(chord, [[a + b for a, b in zip(x, y)] for x, y in zip(fw69, fw76)])


def edc_times(x, rate, levels=(10, 20, 30)):
    """Seconds from the start until the energy still to come (the Schroeder
    integral) is 10, 20 and 30 dB below the total: immune to the beating of
    Bell's partials, unlike a fit to a short-window envelope."""
    tail, acc = [0.0] * len(x), 0.0
    for i in range(len(x) - 1, -1, -1):
        acc += x[i] * x[i]
        tail[i] = acc
    out = []
    for level in levels:
        threshold = tail[0] * 10.0 ** (-level / 10.0)
        out.append(next(i for i, v in enumerate(tail) if v < threshold) / rate)
    return out


@pytest.mark.parametrize("shape,low,high", [(32, 0.999, 1.001), (33, 0.999, 1.001),
                                            (34, 0.99, 1.02)], ids=["bell", "drum", "kick"])
def test_struck_shapes_at_host_rate_decay_as_upstream(tools, tmp_path, shape, low, high):
    # Shapes runs Braids at 96 kHz whatever the host's rate and resamples the
    # mix (engines/resampler.md), so at 44,118 Hz the struck shapes ring as
    # long as upstream's. Before that change Braids ran at the host's rate
    # with only its pitch corrected, and Bell and Drum, whose partials decay
    # once per 24-sample block, rang 2.1-2.2 times as long (ratios 0.458-0.468
    # here). Ratio of the times to reach each level, A4, timbre/colour
    # 0.5/0.5, 2 s, upstream through the same 1 ms attack, fm1 less the
    # resampler's group delay of 30 output samples. Measured: Bell
    # 0.9999, Drum 0.9999-1.0000, Kick 0.9995-1.0062 (with the delay left
    # in, 0.9954-0.9986, 0.9954-0.9983 and 0.966-0.995: 0.68 ms of each
    # time). Kick is the loosest while its strike's excitation sounds (the
    # first 10 dB, a few milliseconds).
    # This resolves the rate to about 0.1 %, as do the tuning and bend tests
    # (5 cents is 0.29 %): a native rate wrong by 0.1 % (96,096 Hz) passes
    # them. The exact guard on the rate is
    # test_engines_resampler.py::test_shape_at_host_rate_is_braids_resampled,
    # which compares every shape against upstream resampled at the right
    # ratio and fails a 0.03 % error.
    render, _ = tools
    point = (0.5, 0.5)
    _, ref = braids_ref(tmp_path, shape, 69, point, 2 * BRAIDS_RATE)
    got, _ = shapes_fm1(render, tmp_path, shape, 69, point, 2.0, rate=HOST_RATE)
    up = edc_times(through_wrapper(ref), BRAIDS_RATE)
    fm1 = edc_times(got[RESAMPLER_DELAY:], HOST_RATE)
    ratios = [u / f for u, f in zip(up, fm1)]
    assert all(low < r < high for r in ratios), ratios


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


def fx_chain_fm1(render, tmp_path, input, seconds, rate, chain, name):
    """fm1-render's input through the effects [(id, [param, ...]), ...] in
    order, then the post gain."""
    wav = tmp_path / f"fm1_{name}.wav"
    cmd = [render, "--input", input, "--seconds", seconds, "--rate", repr(rate)]
    for effect, params in chain:
        cmd += ["--fx", effect]
        for p in params:
            cmd += ["--fx-param", p]
    cmd += ["--fx", "test-gain", "--fx-param", f"Gain={POST_GAIN}", "--out", wav]
    summary = run_json(cmd)
    assert summary["raw_peak"] < 0.98 and summary["nonfinite"] == 0
    _, (left, right) = read_wav(wav)
    return summary, left, right


def fx_fm1(render, tmp_path, effect, input, seconds, rate, params, name):
    return fx_chain_fm1(render, tmp_path, input, seconds, rate, [(effect, params)], name)


def write_float_wav(path, channels, rate):
    """A 32-bit float WAV of one or two channels, for the reference's
    --input-file."""
    frames = [v for frame in zip(*channels) for v in frame]
    data = struct.pack(f"<{len(frames)}f", *frames)
    n = len(channels)
    path.write_bytes(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE" + b"fmt "
                     + struct.pack("<IHHIIHH", 16, 3, n, round(rate), round(rate) * 4 * n,
                                   4 * n, 32)
                     + b"data" + struct.pack("<I", len(data)) + data)
    return path


def lsb_error(got, model):
    """Worst and rms distance, in LSB, between fm1's 16-bit output and a float
    model of it before the post gain."""
    assert len(got) == len(model), (len(got), len(model))
    errs = [g - POST_GAIN * 32767.0 * m for g, m in zip(got, model)]
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


def plate_knobs(ref, damping, diffusion=0.5):
    """Plate's knobs for the coefficients Rings' part.cc computed: Decay is
    Rings' damping (the same 0.35 + 0.63 x), Damping the value whose
    0.9 - 0.6 x lands on Rings' 0.3 + 0.6 brightness, Diffusion the knob whose
    0.5 + 0.25 x is the reference's (0.5 gives Rings' 0.625)."""
    lp = f32(ref["lp"])
    knob = knob_for(lp, lambda d: {f32(1.0 - f32(1.0 - k)) for k in affine(0.9, -0.6, d)},
                    (0.9 - lp) / 0.6)
    assert f32(ref["diffusion"]) == f32(0.5 + 0.25 * diffusion)
    assert f32(ref["input_gain"]) == f32(0.2)
    return [f"Mix={ref['amount']!r}", f"Decay={f32(damping)!r}", f"Damping={knob!r}",
            f"Diffusion={diffusion!r}"]


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


@pytest.mark.parametrize("diffusion", [0.0, 1.0])
@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_plate_diffusion_spans_0_5_to_0_75(tools, tmp_path, input, diffusion):
    # Plate's Diffusion is the all-pass coefficient 0.5 + 0.25 x, exact in
    # float at its ends: 0.5 and 0.75 (Rings fixes 0.625, Diffusion 0.5,
    # tested above).
    render, _ = tools
    args = ["--damping", "0.5", "--brightness", "0.5", "--amount", "1",
            "--diffusion", 0.5 + 0.25 * diffusion]
    ref, rl, rr = fx_ref(tmp_path, "plate", input, 1.0, args, "pdif")
    _, gl, gr = fx_fm1(render, tmp_path, "plate", input, 1.0, RINGS_RATE,
                       plate_knobs(ref, 0.5, diffusion), "pdif")
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


@pytest.mark.parametrize("width", [1.0, 0.5])
@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_ensemble_width_and_mix_are_the_documented_additions(tools, tmp_path, input, width):
    # Mix 0.5 and Depth 0.5 (the defaults), Width 1 (the default) and 0.5:
    # upstream at amount 1 fed the input on the left and, on the right, the
    # line x + width (late - x), late being the input 131 samples later; then
    # the wet recovered as out - line / 2 and mixed with Plaits' law against
    # the undelayed dry: wet * mix + dry * (1 - mix / 2).
    render, _ = tools
    ref, rl, rr = fx_ref(tmp_path, "ensemble", input, 0.5,
                         ["--amount", "1", "--depth", "0.5", "--right-delay", "131",
                          "--right-width", width], "ensw")
    assert f32(ref["right_width"]) == f32(width)
    _, gl, gr = fx_fm1(render, tmp_path, "ensemble", input, 0.5, PLAITS_RATE,
                       [f"Width={width}"], "ensw")
    dry = fm1_input(input, len(rl))
    late = [0.0] * 131 + dry[:-131]
    line = [x + width * (y - x) for x, y in zip(dry, late)]
    mix = 0.5
    ml = [(a - 0.5 * x) * mix + x * (1 - mix / 2) for a, x in zip(rl, dry)]
    mr = [(a - 0.5 * y) * mix + x * (1 - mix / 2) for a, x, y in zip(rr, dry, line)]
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
    one-pole tone filter, and a crossfade from the dry, one list for both
    sides or a (left, right) pair."""
    w = [0.5 * v for v in wet]
    k = tone_k(tone, rate)
    out = []
    for n, dry_side in zip((241, 349), dry if isinstance(dry, tuple) else (dry, dry)):
        side = w if width == 0.0 else [a + width * (b - a) for a, b in zip(w, schroeder(w, n, 0.5))]
        wet_side = one_pole(side, k)
        out.append([d + mix * (s - d) for d, s in zip(dry_side, wet_side)])
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


@pytest.mark.parametrize("width", [1.0, 0.5])
@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_diffuse_defaults_are_the_documented_additions(tools, tmp_path, input, width):
    # Mix 0.5, Tone 0.75 (about 9.5 kHz), Width 1 (the default) and 0.5, and
    # rt 0.375 (the particle engine at morph 0.25).
    render, _ = tools
    ref, rl, _ = fx_ref(tmp_path, "diffuse", input, 0.5, ["--morph", "0.25", "--amount", "1"],
                        "difd")
    _, gl, gr = fx_fm1(render, tmp_path, "diffuse", input, 0.5, PLAITS_RATE,
                       [f"Time={diffuse_time_knob(ref)!r}", f"Width={width}"], "difd")
    dry = fm1_input(input, len(rl))
    assert_quantisation_only((gl, gr), diffuse_model(rl, dry, PLAITS_RATE, mix=0.5,
                                                     tone=0.75, width=width))


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


def plate_stereo(tmp_path, input, seconds, name):
    """Plate's stereo output inside a chain at 44,118 Hz, as upstream gives it
    (Rings' patch 0.5 / 0.5, full wet, the rate rule applied), and Plate's
    knobs for it."""
    args = ["--damping", "0.5", "--brightness", "0.5", "--amount", "1"]
    native, _, _ = fx_ref(tmp_path, "plate", input, 0.1, args, name + "_n")
    _, pl, pr = fx_ref(tmp_path, "plate", input, seconds,
                       args + ["--rate", repr(HOST_RATE), "--compensate", repr(HOST_RATE)], name)
    assert max(abs(a - b) for a, b in zip(pl, pr)) > 1e-3, "not a stereo input"
    return plate_knobs(native, 0.5), pl, pr


@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_diffuse_sums_a_stereo_input_and_keeps_each_side_s_dry(tools, tmp_path, input):
    # fm1-render's own inputs are mono; Plate's output is not. Plate then
    # Diffuse at its defaults, 44,118 Hz: upstream's plate, the wrapper's mono
    # sum 0.5 (L + R) through upstream's diffuser (both with the rate rule),
    # then Diffuse's additions with each side crossfaded from its own dry.
    render, _ = tools
    knobs, pl, pr = plate_stereo(tmp_path, input, 0.5, "cd")
    mono = [f32(0.5 * f32(a + b)) for a, b in zip(pl, pr)]
    wav = write_float_wav(tmp_path / "cd_in.wav", [mono], HOST_RATE)
    native, _, _ = fx_ref(tmp_path, "diffuse", "impulse", 0.1,
                          ["--morph", "0.25", "--amount", "1"], "cd_dn")
    _, wet, _ = fx_ref(tmp_path, "diffuse", "silence", 0.5,
                       ["--input-file", wav, "--morph", "0.25", "--amount", "1",
                        "--rate", repr(HOST_RATE), "--compensate", repr(HOST_RATE)], "cd_d")
    _, gl, gr = fx_chain_fm1(render, tmp_path, input, 0.5, HOST_RATE,
                             [("plate", knobs),
                              ("diffuse", [f"Time={diffuse_time_knob(native)!r}"])], "cd")
    assert_quantisation_only((gl, gr), diffuse_model(wet, (pl, pr), HOST_RATE, mix=0.5,
                                                     tone=0.75, width=1.0))


@pytest.mark.parametrize("input", ["impulse", "noise"])
def test_ensemble_keeps_a_stereo_input_apart(tools, tmp_path, input):
    # Plate then Ensemble at its defaults (Mix 0.5, Depth 0.5, Width 1),
    # 44,118 Hz: upstream fed Plate's left, and on the right Plate's right
    # 131 samples late; each side's wet recovered against its own line and
    # mixed with its own dry.
    render, _ = tools
    knobs, pl, pr = plate_stereo(tmp_path, input, 0.5, "ce")
    wav = write_float_wav(tmp_path / "ce_in.wav", [pl, pr], HOST_RATE)
    _, rl, rr = fx_ref(tmp_path, "ensemble", "silence", 0.5,
                       ["--input-file", wav, "--amount", "1", "--depth", "0.5",
                        "--right-delay", "131", "--rate", repr(HOST_RATE)], "ce_e")
    _, gl, gr = fx_chain_fm1(render, tmp_path, input, 0.5, HOST_RATE,
                             [("plate", knobs), ("ensemble", [])], "ce")
    late = [0.0] * 131 + pr[:-131]
    mix = 0.5
    ml = [(a - 0.5 * x) * mix + x * (1 - mix / 2) for a, x in zip(rl, pl)]
    mr = [(a - 0.5 * y) * mix + x * (1 - mix / 2) for a, x, y in zip(rr, pr, late)]
    assert_quantisation_only((gl, gr), (ml, mr))


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
    # rate, 2 s renders. Measured: Plate 0.961 / 0.967 / 0.970 at Rings
    # damping 0.3 / 0.5 / 0.7 (uncompensated 0.914 / 0.921 / 0.927, the same
    # upstream samples read at 44,118 Hz); Diffuse at rt 0.75 0.961
    # (uncompensated 0.916).
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
