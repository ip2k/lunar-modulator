"""The resampler (engines/include/fm1_resampler.h, engines/resampler.md), and
Shapes at the host's rate through it.

engines/build/fm1-resampler-test measures the resampler on its own: its
coefficient tables against the design below, frequency response, group delay
and alias rejection from sine sweeps at 96,000 and 47,872.34 -> 44,118 Hz
(and three other ratios), pass-through at equal rates, independence from how
input and output are chunked, extreme input, refused ratios, its cost, and
the header as C99 and C++11.

Shapes now runs Braids and its own envelope at 96 kHz whatever the host's
rate and resamples the voice mix. At 44,118 Hz: every shape against upstream
Braids at 96 kHz through the wrapper's envelope and the same resampler, note
timing at Braids' 24-sample blocks, the envelope's times, host-block
independence, the refused host rates, and the aliases of a high CSaw note.
The struck shapes' decay against upstream is in
test_engines_reference_braids_fx.py.
"""
import json
import math
import shutil
import struct
import subprocess

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401
from tests.test_engines_reference_braids_fx import (BLOCK_SENSITIVE, BRAIDS_RATE,  # noqa: F401
                                                    HOST_RATE, KEYS, POINTS, RESAMPLER_DELAY,
                                                    RMS_LSB, TWO_PER_PASS, WORST_LSB, braids_ref,
                                                    envelope, read_wav, run_json,
                                                    through_wrapper, tools, write_float_wav)

TOOL = ENGINES / "build" / "fm1-resampler-test"
HEADER = ENGINES / "include" / "fm1_resampler.h"

# The design. engines/include/fm1_resampler.h holds these tables as const
# float arrays; `python -m tests.test_engines_resampler` prints them, and
# test_tables_are_the_documented_design checks the header against them.
SPAN = 12            # stage-1 kernel span, in intermediate samples (twice the output rate)
PHASES = 128         # kernel table entries per intermediate sample
KERNEL_BETA = 11.0
KERNEL_CUTOFF = 0.96   # of the intermediate rate's Nyquist, which is the output rate
LP_DELAY = 30        # stage 2: a low-pass of 4 D + 3 = 123 taps, centred D output samples back
LP_LEN = 4 * LP_DELAY + 3
LP_PAIRS = 2 * LP_DELAY + 1   # its symmetric pairs; plus the centre tap
LP_BETA = 9.3
LP_CUTOFF = 0.4522   # of the output rate: 19,950 Hz at 44,118 Hz

DELAY = LP_DELAY     # group delay, output samples
PASS_EDGE = 18000.0 / 44118.0   # of the output rate: 18 kHz at 44,118 Hz
PLAITS_RATE = 47872.34


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def bessel_i0(x):
    s = t = 1.0
    k = 1
    while True:
        t *= (x / (2 * k)) ** 2
        s += t
        if t < 1e-21 * s:
            return s
        k += 1


def kaiser(x, half_width, beta):
    if abs(x) > half_width:
        return 0.0
    r = x / half_width
    return bessel_i0(beta * math.sqrt(max(0.0, 1.0 - r * r))) / bessel_i0(beta)


def sinc(x):
    return 1.0 if x == 0 else math.sin(math.pi * x) / (math.pi * x)


def kernel_table():
    """Half of the stage-1 kernel, c sinc(c u) x Kaiser(u) for u = 0 .. SPAN/2
    intermediate samples in steps of 1/PHASES, c = KERNEL_CUTOFF: a low-pass
    at 0.96 of the intermediate rate's Nyquist (the output rate), whose
    integral is 1."""
    c = KERNEL_CUTOFF
    return [f32(c * sinc(c * u) * kaiser(u, SPAN / 2, KERNEL_BETA))
            for u in (i / PHASES for i in range(SPAN // 2 * PHASES + 1))]


def lowpass_table():
    """Stage 2's taps, outermost first: 2 f sinc(2 f m) x Kaiser(m) at the
    offsets m = LP_PAIRS .. 1 from the centre tap, then the centre tap (m = 0),
    f = LP_CUTOFF / 2 cycles per intermediate sample; scaled so that the
    centre and twice the sides sum to 1 (unity gain at DC)."""
    f = LP_CUTOFF / 2
    raw = [2 * f * sinc(2 * f * m) * kaiser(m, LP_PAIRS + 1, LP_BETA)
           for m in range(LP_PAIRS, -1, -1)]
    total = raw[-1] + 2 * sum(raw[:-1])
    return [f32(v / total) for v in raw]


def c_float(v):
    """A C float literal that reads back as exactly v (nine significant
    digits round-trip any float32)."""
    s = f"{v:.9g}"
    return (s if any(c in s for c in ".e") else s + ".0") + "f"


def c_values(values, per_line):
    return "\n".join("  " + ", ".join(c_float(v) for v in values[i:i + per_line]) + ","
                     for i in range(0, len(values), per_line))


# ---------------------------------------------------------------------------
# The resampler on its own
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tool(renderer):  # noqa: F811
    assert TOOL.exists(), "make -C engines builds build/fm1-resampler-test"
    return TOOL


def run_tool(tool, *args):
    res = subprocess.run([str(tool), *map(str, args)], check=True, capture_output=True, text=True)
    return json.loads(res.stdout)


def sweep(tool, in_rate, start, stop, step, out_rate=HOST_RATE):
    return run_tool(tool, "sweep", "--in-rate", in_rate, "--out-rate", out_rate, "--from", start,
                    "--to", stop, "--step", step)


def test_tables_are_the_documented_design(tool):
    t = run_tool(tool, "tables")
    assert (t["span"], t["phases"], t["delay"], t["lp_len"]) == (SPAN, PHASES, LP_DELAY, LP_LEN)
    assert RESAMPLER_DELAY == LP_DELAY    # what the struck-decay test takes out
    for got, want in ((t["kernel"], kernel_table()), (t["lowpass"], lowpass_table())):
        assert len(got) == len(want)
        # Equal as float32; one ulp of slack for another platform's libm.
        assert all(abs(g - w) <= 1.2e-7 * abs(w) + 1e-30 for g, w in zip(got, want))
    lp = t["lowpass"]
    assert len(lp) == LP_PAIRS + 1
    assert abs(lp[-1] + 2 * sum(lp[:-1]) - 1.0) < 1e-6           # unity at DC
    print("state", t["state_bytes"], "bytes; tables",
          4 * (len(t["kernel"]) + len(lp)), "bytes")


@pytest.mark.parametrize("lang,flags", [
    ("c", ["-std=c99", "-pedantic"]),
    ("c++", ["-std=c++11", "-fno-exceptions", "-fno-rtti", "-pedantic"]),
])
def test_header_is_warning_free_c99_and_cxx11(tmp_path, lang, flags):
    compiler = shutil.which("cc" if lang == "c" else "c++")
    if not compiler:
        pytest.skip(f"no {lang} compiler")
    src = tmp_path / ("check.c" if lang == "c" else "check.cc")
    src.write_text('#include "fm1_resampler.h"\n'
                   "float check(const float *in, float *out) {\n"
                   "  fm1_resampler_t r;\n"
                   "  uint32_t used = 0;\n"
                   "  if (!fm1_resampler_init(&r, 96000.0f, 44118.0f)) return 0.0f;\n"
                   "  fm1_resampler_push(&r, in, fm1_resampler_needed(&r));\n"
                   "  out[0] = fm1_resampler_pop(&r);\n"
                   "  fm1_resampler_process(&r, in, 64, &used, out, 16);\n"
                   "  return fm1_resampler_delay(&r);\n"
                   "}\n")
    res = subprocess.run([compiler, *flags, "-Wall", "-Wextra", "-Werror", "-fsyntax-only",
                          "-I", str(HEADER.parent), str(src)], capture_output=True, text=True)
    assert res.returncode == 0 and not res.stderr, res.stderr


# The engines that will use it: Braids, Plaits, Rings' 48 kHz, an exact 2:1 and
# the 4:1 limit, all to the FM-1's rate.
RATES = (BRAIDS_RATE, PLAITS_RATE, 48000.0, 2 * HOST_RATE, 4 * HOST_RATE)


@pytest.mark.parametrize("in_rate", RATES)
def test_passband_is_flat_and_linear_phase(tool, in_rate):
    # Unit sines every 250 Hz from 250 Hz to 18 kHz, a fit at each: gain
    # within 0.005 dB (measured -0.0043 to +0.0003, the low-pass's droop at
    # 18 kHz the most), the group delay 30 output samples at every frequency
    # (linear phase), and every other component, wherever it lands below the
    # output's Nyquist, at least 95 dB down (measured: -101.2 dB at Plaits'
    # rate, -109.2 at 48 kHz, -111.6 at Braids', -156 or less at 2:1 and 4:1).
    pts = sweep(tool, in_rate, 0, 18001, 250)["points"]
    assert len(pts) == 72 and pts[-1]["f"] == 18000
    assert max(abs(p["gain_db"]) for p in pts) < 0.005
    assert max(abs(p["delay_err"]) for p in pts) < 0.001
    assert max(max(p["pass_db"], p["upper_db"]) for p in pts) < -95.0


@pytest.mark.parametrize("in_rate", RATES)
def test_top_of_the_band_rolls_off_without_spurs(tool, in_rate):
    # Unit sines every 20 Hz from 18 kHz to the output's Nyquist, the
    # low-pass's transition band: its gain falls as designed (-0.004 dB at
    # 18 kHz, -0.74 at 19, -6.5 at 20, -24.4 at 21, -79.7 at 22), and nothing
    # else these tones leave anywhere below the Nyquist comes within 95 dB.
    # Measured: -101.0 dB at Plaits' rate, -102.2 at 48 kHz, -108.8 at
    # Braids', -152 or less at 2:1 and 4:1. At ratios below 2 the first
    # stage's images of these tones (at the input rate less the tone, 26 to
    # 30 kHz at Plaits' rate) reach the second stage, which must stop them.
    pts = sweep(tool, in_rate, 18000, HOST_RATE / 2, 20)["points"]
    assert len(pts) == 202
    gains = {p["f"]: p["gain_db"] for p in pts}
    for f, db, tol in ((18000, -0.0043, 0.001), (19000, -0.743, 0.01), (20000, -6.53, 0.01),
                       (21000, -24.36, 0.05), (22000, -79.7, 1.0)):
        assert gains[f] == pytest.approx(db, abs=tol), (f, gains[f])
    assert max(max(p["pass_db"], p["upper_db"]) for p in pts) < -95.0


@pytest.mark.parametrize("in_rate", RATES)
def test_content_above_the_output_nyquist_is_90_db_down(tool, in_rate):
    # Unit sines from the output's Nyquist to the input's, every 7 Hz across
    # the low-pass's stopband edge (22,059 Hz) and every 97 Hz above it:
    # their aliases, wherever they land below the Nyquist (18..22 kHz
    # included), and everything else they leave there, at least 90 dB down.
    # Measured: the main alias -93.3 dB at worst at every ratio (near
    # 22,174 Hz, the stopband's first sidelobe); other components -98.3 dB
    # or less.
    pts = (sweep(tool, in_rate, HOST_RATE / 2 + 5, 22500, 7)["points"]
           + sweep(tool, in_rate, 22500, 1e9, 97)["points"])
    assert len(pts) > 60
    worst = max(max(p["gain_db"], p["pass_db"], p["upper_db"]) for p in pts)
    assert worst < -90.0, worst


def test_pass_through_at_equal_rates_is_bit_exact(tool):
    r = run_tool(tool, "passthrough")
    assert r == {"samples": 100000, "mismatches": 0, "delay": 0}


@pytest.mark.parametrize("in_rate", (BRAIDS_RATE, PLAITS_RATE, 2 * HOST_RATE))
def test_output_does_not_depend_on_chunking(tool, in_rate):
    # One sample at a time against fm1_resampler_process with input chunks
    # of 1, 7, 24, uneven and 1,000, and output chunks of 1, 64 and uneven:
    # 25 patterns, all bit-identical.
    r = run_tool(tool, "blocks", "--in-rate", in_rate)
    assert r["patterns"] == 25 and r["differing"] == 0


@pytest.mark.parametrize("in_rate", (BRAIDS_RATE, PLAITS_RATE, 4 * HOST_RATE, 44119.0))
def test_extreme_input_stays_finite(tool, in_rate):
    # Inputs up to the largest float over the worst-case gain (the kernel's
    # L1 norm, doubled for the low-pass's pre-added pairs, or times the
    # low-pass's L1 norm, 2.11, whichever is larger: 3.1 to 4.3 by ratio)
    # never overflow; a burst of NaN and infinities spoils about 69 outputs
    # and is then forgotten, the output bit-identical to the clean run's (a
    # FIR has no memory beyond its taps).
    r = run_tool(tool, "extreme", "--in-rate", in_rate)
    assert r["finite_input_nonfinite_outputs"] == 0
    assert r["peak_gain"] <= r["gain_bound"]
    assert 2.5 < r["gain_bound"] < 4.6
    assert 0 < r["to"] - r["burst_outputs_differing_from"] < 75
    assert r["nonfinite"] <= r["to"] - r["burst_outputs_differing_from"] + 1


def test_an_output_reads_only_the_inputs_it_asked_for(tool):
    # After every push, NaN goes into the ring slot the next push will fill:
    # it holds the oldest input, and its second copy sits where the input not
    # yet received would be. At 3,006 ratios from just above 1 to 4, 3,000
    # outputs each, every output stays finite: no output reads an input
    # fm1_resampler_needed did not ask for first (the one-input margin in
    # `lead`, the rounding up in needed), nor one the ring has dropped
    # (FM1_RESAMPLER_IN_CAP). The read window itself, the fewest newest
    # inputs an output can do with: 27 of the ring's 32, at the 4:1 limit.
    r = run_tool(tool, "window")
    assert (r["cap"], r["ratios"], r["outputs"]) == (32, 3006, 3000)
    assert r["nonfinite"] == 0 and r["failing_ratios"] == 0
    assert r["window"] == 27


def test_unsupported_ratios_are_refused(tool):
    # 1..4 times the output rate, or equal; a refused instance takes and gives
    # nothing, whatever its memory held before (0xA5 throughout).
    got = run_tool(tool, "refuse")
    accepted = {("96000", "44118"), ("96000", "96000"), ("47872.3398", "44118"),
                ("176472", "44118")}
    assert len(got) == 14
    for r in got:
        assert r["ok"] == ((r["in"], r["out"]) in accepted), r
        if not r["ok"]:
            assert (r["needed"], r["took"], r["pop"]) == (0, 0, 0), r
    assert {(r["in"], r["out"]) for r in got if r["ok"]} == accepted


def test_cost_per_output_sample(tool):
    # Desktop timing, best of seven over 2^20 outputs; it says nothing about
    # pi32v2 and only catches something pathological. Measured on an Apple
    # M1 Max: 45 ns per output at 96 kHz, 36 ns at Plaits' rate.
    for in_rate in (BRAIDS_RATE, PLAITS_RATE):
        r = run_tool(tool, "bench", "--in-rate", in_rate)
        print(in_rate, r["ns_per_output"], "ns per output")
        assert 0 < r["ns_per_output"] < 20000


# ---------------------------------------------------------------------------
# Shapes at the host's rate
# ---------------------------------------------------------------------------

def resampler_constants(in_rate=BRAIDS_RATE, out_rate=HOST_RATE):
    """fm1_resampler_init's fixed-point step and lead, the same double
    arithmetic: inputs per intermediate sample, and the input an output
    needs past the next intermediate sample's position, both 32.32."""
    ratio = float(in_rate) / float(out_rate)
    rho = 2.0 / ratio
    step = int(ratio / 2.0 * 4294967296.0 + 0.5)
    reach = int(SPAN / (2.0 * rho) * 4294967296.0 + 0.5)
    return step, step + reach + (1 << 32)


def inputs_pulled(outputs):
    """The 96 kHz samples Shapes' resampler has pulled once it has made the
    given number of output samples: output j needs ceil((2 j step + lead) /
    2^32) inputs."""
    if outputs == 0:
        return 0
    step, lead = resampler_constants()
    return -(-(2 * (outputs - 1) * step + lead) >> 32)


def first_free_chunk(host_sample):
    """The 24-sample chunk a note reaching Shapes before output host_sample
    starts on: the first one not yet rendered."""
    return -(-inputs_pulled(host_sample) // 24)


def shapes_at(render, tmp_path, name, shape, point, seconds, notes, rate=HOST_RATE, frames=64,
              params=()):
    wav = tmp_path / f"{name}.wav"
    cmd = [render, "--engine", "shapes", "--param", f"Shape={shape}",
           "--param", f"Timbre={point[0]}", "--param", f"Color={point[1]}",
           "--param", "Attack=0", "--param", "Volume=1"]
    for p in params:
        cmd += ["--param", p]
    for n in notes:
        cmd += ["--note", n]
    cmd += ["--rate", rate, "--frames", frames, "--seconds", seconds, "--out", wav]
    summary = run_json(cmd)
    assert summary["raw_peak"] < 0.98 and summary["nonfinite"] == 0
    wav_rate, (left, right) = read_wav(wav)
    assert wav_rate == round(rate) and left == right
    return left, wav


def resampled(tool, tmp_path, lsb, name):
    """A 96 kHz signal in LSB of fm1's WAV, through the resampler to
    44,118 Hz, in the same LSB."""
    src = write_float_wav(tmp_path / f"{name}_96k.wav", [[v / 32767.0 for v in lsb]], BRAIDS_RATE)
    dst = tmp_path / f"{name}_44k.wav"
    run_tool(tool, "file", "--in-rate", BRAIDS_RATE, "--out-rate", HOST_RATE, "--in", src,
             "--out", dst)
    return [v * 32767.0 for v in read_wav(dst)[1][0]]


def lsb_error(got, model):
    n = min(len(got), len(model))
    assert n > 0.95 * len(got), (len(got), len(model))
    errs = [g - m for g, m in zip(got[:n], model[:n])]
    return max(abs(e) for e in errs), math.sqrt(sum(e * e for e in errs) / n)


@pytest.mark.parametrize("point", POINTS, ids=["t25c75", "t75c25"])
@pytest.mark.parametrize("shape", range(47))
def test_shape_at_host_rate_is_braids_resampled(tools, tool, tmp_path, shape, point):
    # The exit test at the FM-1's rate: every shape at 44,118 Hz is upstream
    # Braids at 96 kHz, through the wrapper's envelope and gain and the same
    # resampler, within fm1-render's 16-bit rounding. A2 and A6, 0.1 s.
    render, _ = tools
    for key in KEYS:
        ref_summary, ref = braids_ref(tmp_path, shape, key, point, 9600)
        assert ref_summary["peak"] > 100
        got, _ = shapes_at(render, tmp_path, f"s{shape}_{key}", shape, point, 0.1,
                           [f"0:{key}:127:100"])
        model = resampled(tool, tmp_path, through_wrapper(ref), f"m{shape}_{key}")
        worst, rms_err = lsb_error(got, model)
        assert worst <= WORST_LSB and rms_err <= RMS_LSB, (key, worst, rms_err)


@pytest.mark.parametrize("shape", [28, 32, 34, 44])
def test_note_on_at_host_rate_starts_on_a_braids_block(tools, tool, tmp_path, shape):
    # A note at 0.0503 s reaches Shapes before host sample 2,240 (35 x 64).
    # By then the resampler has pulled 4,881 samples at 96 kHz, so the voice
    # starts on the next unrendered 24-sample chunk, at 4,896 (0.25 ms
    # granularity), exactly as a fresh Braids struck on its first block; its
    # onset is centred 30 output samples (the group delay) after
    # 4,896 x 44,118 / 96,000 = 2,250.02. From the note's arrival that is
    # 40 output samples, 0.91 ms. No output before 2,247 reads the chunk at
    # all (output k reads 96 kHz samples up to (2 k + 1) x 96,000 / 88,236
    # plus the kernel's reach, 6.53), so they are exactly silent.
    render, _ = tools
    start = 24 * first_free_chunk(2240)
    assert (inputs_pulled(2240), start) == (4881, 4896)
    _, ref = braids_ref(tmp_path, shape, 57, POINTS[0], 9600 - start)
    model = resampled(tool, tmp_path, [0.0] * start + through_wrapper(ref), "late")
    got, _ = shapes_at(render, tmp_path, "late", shape, POINTS[0], 0.1, ["0.0503:57:127:100"])
    assert not any(got[:2247])
    worst, rms_err = lsb_error(got, model)
    assert worst <= WORST_LSB and rms_err <= RMS_LSB, (worst, rms_err)
    onset = start * HOST_RATE / BRAIDS_RATE + DELAY
    assert onset - 2240 == pytest.approx(40.018, abs=0.001)


@pytest.mark.parametrize("shape", [0, 32])
def test_envelope_times_are_braids_samples_at_host_rate(tools, tool, tmp_path, shape):
    # The wrapper's envelope runs at 96 kHz too, so its times do not depend
    # on the host's rate: velocity 64, Attack 0.2 (0.001 x 4000^0.2 =
    # 5.25 ms) and, from the note-off at 0.0499 s (before host sample 2,240,
    # so at the chunk starting at 96 kHz sample 4,896), Release 0.3 (12.0 ms),
    # modelled in double precision at 96 kHz against fm1 at 44,118 Hz.
    render, _ = tools
    off = 24 * first_free_chunk(2240)
    _, ref = braids_ref(tmp_path, shape, 57, POINTS[0], 9600)
    env = envelope(9600, segments=[(off, 64 / 127.0, 0.2), (9600 - off, 0.0, 0.3)])
    model = resampled(tool, tmp_path, through_wrapper(ref, env), "env")
    got, _ = shapes_at(render, tmp_path, "env", shape, POINTS[0], 0.1, ["0:57:64:0.0499"],
                       params=["Attack=0.2", "Release=0.3"])
    worst, rms_err = lsb_error(got, model)
    assert worst <= WORST_LSB and rms_err <= RMS_LSB, (worst, rms_err)


@pytest.mark.parametrize("shape", sorted(set(BLOCK_SENSITIVE + TWO_PER_PASS)))
def test_shapes_at_host_rate_do_not_depend_on_the_host_block(tools, tmp_path, shape):
    # 1, 7 and 64 frames per call, byte-identical: a note at 0, a second at
    # host sample 4,480 and the first's note-off at 8,960, sample counts all
    # three block sizes reach exactly. 0.3 s (13,235 frames, an odd total).
    render, _ = tools
    t1, t2 = (4480 - 0.5) / HOST_RATE, (8960 - 0.5) / HOST_RATE
    notes = [f"0:57:127:{t2}", f"{t1}:64:100:100"]
    renders = []
    for frames in (1, 7, 64):
        _, wav = shapes_at(render, tmp_path, f"b{frames}", shape, POINTS[0], 0.3, notes,
                           frames=frames, params=["Release=0.1"])
        renders.append(wav.read_bytes())
    assert len(read_wav(wav)[1][0]) == 13235
    assert renders[1] == renders[0] and renders[2] == renders[0]


@pytest.mark.parametrize("rate,accepted", [(24000, True), (23999, False), (96000, True),
                                           (96001, False), (48000, True)])
def test_shapes_refuses_host_rates_the_resampler_cannot_serve(tools, tmp_path, rate, accepted):
    render, _ = tools
    res = subprocess.run([str(render), "--engine", "shapes", "--note", "0:57:100:0.05",
                          "--rate", str(rate), "--seconds", "0.05",
                          "--out", str(tmp_path / "r.wav")], capture_output=True, text=True)
    assert (res.returncode == 0) == accepted, res.stderr
    if not accepted:
        assert "refused this host" in res.stderr


def fold(f, rate):
    g = f % rate
    return rate - g if g > rate / 2 else g


@pytest.mark.parametrize("key,inband_hz,measurable", [(120, [8372, 16744], 3), (127, [12544], 0)])
def test_high_note_aliases_are_below_the_measurement_floor(tools, tool, tmp_path, key, inband_hz,
                                                            measurable):
    # CSaw at MIDI 120 (8,372 Hz) and 127 (12,544 Hz), timbre and colour 0.
    # At 96 kHz their harmonics and Braids' own aliases above 22,059 Hz reach
    # -32 dBFS (MIDI 120: 25.1, 29.0, 33.5, 37.4, 41.9 and 45.8 kHz) and
    # -25.5 dBFS (MIDI 127's second harmonic, 25,088 Hz). At 44,118 Hz, at
    # each frequency where one of them aliases, anywhere below the output's
    # Nyquist (18..22 kHz included), fm1's output holds no more than the
    # 96 kHz render's own content there, plus -90 dB of the source, plus a
    # floor of -125 dBFS (the 16-bit render's DFT floor is about -135 dBFS;
    # MIDI 127's render carries content of its own at about -116 dBFS
    # everywhere). Where the floor leaves room to see 90 dB (the source
    # 100 dB above the 96 kHz render's content at its alias: three of MIDI
    # 120's), each alias is more than 90 dB below its source: measured -99.2
    # (25.1 kHz to 19.0 kHz), -105.5 and -103.3 dB. MIDI 127's 25,088 Hz
    # reads -120.2 dBFS at 19,030 Hz, under the 96 kHz render's -116.0
    # there. (The half-band design this replaced let both through to 19 kHz
    # 44 dB down: -78.0 and -69.5 dBFS.) The in-band harmonics keep their
    # level within 0.05 dB.
    render, _ = tools
    point, notes = (0.0, 0.0), [f"0:{key}:127:100"]
    _, w96 = shapes_at(render, tmp_path, "csaw96", 0, point, 1.6, notes, rate=BRAIDS_RATE)
    _, w44 = shapes_at(render, tmp_path, "csaw44", 0, point, 1.6, notes)
    peaks = run_tool(tool, "peaks", "--in", w96, "--start", 9600, "--floor", -75)["peaks"]
    sources = [p for p in peaks if p["f"] > HOST_RATE / 2]
    inband = [p for p in peaks if p["f"] < PASS_EDGE * HOST_RATE and p["db"] > -30]
    assert len(sources) >= 6 and max(p["db"] for p in sources) > -35
    assert [round(p["f"]) for p in inband] == inband_hz
    freqs = [fold(p["f"], HOST_RATE) for p in sources] + [p["f"] for p in inband]
    args = [a for f in freqs for a in ("--freq", f)]
    a44 = run_tool(tool, "tones", "--in", w44, "--start", 4412, "--length", 65536, *args)["tones"]
    a96 = run_tool(tool, "tones", "--in", w96, "--start", 9600, "--length", 131072, *args)["tones"]
    floor = 10 ** (-125 / 20)
    seen = []
    for src, t44, t96 in zip(sources, a44, a96):
        allowed = 1.1 * t96["amp"] + 10 ** ((src["db"] - 90) / 20) + floor
        assert t44["amp"] <= allowed, (src, t44, t96)
        if src["db"] - 20 * math.log10(t96["amp"] + 1e-30) > 100:   # 90 dB is visible
            seen.append(20 * math.log10(t44["amp"]) - src["db"])
    assert len(seen) == measurable and all(db < -90.0 for db in seen), seen
    for p, t44, t96 in zip(inband, a44[len(sources):], a96[len(sources):]):
        assert 20 * math.log10(t44["amp"] / t96["amp"]) == pytest.approx(0.0, abs=0.05), p


if __name__ == "__main__":
    print("kernel", len(kernel_table()))
    print(c_values(kernel_table(), 6))
    print("lowpass", len(lowpass_table()))
    print(c_values(lowpass_table(), 4))
