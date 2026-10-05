"""Tests for the Gate, the triggerable noise gate with a Duck mode
(engines/src/fx_gate.cc, parameters in engines/README.md, "Gate").

Through fm1-render: registration and pages, the host contracts (deterministic
renders, any block size, any prior memory contents, any parameter value,
NaN included, bad input guarded and not latched, silence in gives silence
out), bit-exact passage where the design allows it (Range 0; an open gate),
gating a quiet gap, Duck, Listen and the key filters, Lookahead's latency
on the renderer's own clock, a chain, and every switch (Mode, Listen, Link)
and Lookahead turned every third block (the harness of
tests/test_engines_fx_switches.py). Through fm1-gate-test
(engines/test/gate_test.cc), which reads the gate's state frame by frame
(include/fm1_gate.h): open and close timing (Attack, the detector's fall,
Hold, Decay), Range, Return's hysteresis, Duck, Lockout, the look-ahead's
latency at four host rates, a burst's onset kept whole by look-ahead, the
key filters' magnitude responses against the bilinear Butterworth formula,
Listen's output against a float64 reference of the filter pair, Link on
Listen and on the detector, the key LP's delay of the trigger, chattering
on a noisy decaying key, bad keys not latching, a key other than the input
(fm1_gate_render_key), parameters changed mid-stream at any block size and
render_key(NULL) equal to render, host rates and instance sizes, its tan
against libm, and the output's bits pinned.

The figures in the comments were measured on the desktop build (Apple
clang, arm64, 2026-10-05).
"""
import json
import math
import struct
import subprocess

import pytest

from tests import test_engines_fx_switches as switches
from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, brightness, run

TOOL = ENGINES / "build" / "fm1-gate-test"
LSB = 1 / 32767.0
K = math.sqrt(2.0)                    # the key filters' damping: Q = 1/sqrt(2)
FALL = 0.004                          # the detector's fall, s

# Every parameter away from its default, the gate opening and closing on the
# renderer's noise (+-0.5) only where --fault quietens it.
BUSY = ["Threshold=-30", "Attack=2", "Hold=20", "Decay=60", "Range=-50", "Return=6",
        "Mode=0", "Key HP=120", "Key LP=6000", "Listen=0", "Lockout=40", "Lookahead=1.5",
        "Link=1"]
GAPS = ["--fault", "0.1..0.2:0.001", "--fault", "0.3..0.35:0.0005"]


def fx(*params):
    return [("gate", list(params))]


def cli(*params):
    args = ["--fx", "gate"]
    for p in params:
        args += ["--fx-param", p]
    return args


def db_gain(db):
    return 10 ** (db / 20)


def f32(x):
    return struct.unpack("f", struct.pack("f", x))[0]


def lcg_noise(seed, n):
    """The test driver's Lcg: 0.5 x Bipolar(), as float32, n values."""
    out, s = [], seed
    for _ in range(n):
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        i = s - (1 << 32) if s & 0x80000000 else s
        out.append(0.5 * f32(float(i)) / 2147483648.0)
    return out


def svf(xs, hz, high):
    """Zavalishin's trapezoidal SVF, Q = 1/sqrt(2), prewarped, in float64:
    an independent reference for the key filters."""
    g = math.tan(math.pi * hz / RATE)
    a1 = 1 / (1 + g * (g + K))
    a2, a3 = g * a1, g * g * a1
    ic1 = ic2 = 0.0
    out = []
    for x in xs:
        v3 = x - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1, ic2 = 2 * v1 - ic1, 2 * v2 - ic2
        out.append(x - K * v1 - v2 if high else v2)
    return out


def butterworth_db(f, hp, lp):
    """The pair's magnitude: the analogue second-order Butterworth through the
    bilinear transform with its cutoff prewarped (what the SVF realises); a
    filter at its end (HP 20 Hz, LP 20 kHz) is out."""
    total = 0.0
    for fc, high in ((hp, True), (lp, False)):
        if (high and fc <= 20) or (not high and fc >= 20000):
            continue
        fc = min(fc, 0.45 * RATE)
        w = math.tan(math.pi * f / RATE) / math.tan(math.pi * fc / RATE)
        den = math.sqrt((1 - w * w) ** 2 + (K * w) ** 2)
        total += 20 * math.log10((w * w if high else 1.0) / den)
    return total


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


@pytest.fixture(scope="module")
def entry(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return {x["id"]: x for x in json.loads(out)}["gate"]


def test_gate_is_registered(entry):
    e = entry
    assert (e["name"], e["kind"], e["max_voices"]) == ("Gate", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    # Drawmer is credited as the inspiration, never a label.
    assert "MIT" in e["credits"] and "DS201" in e["credits"]
    assert all("drawmer" not in p["name"].lower() for p in e["params"])
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in range(4)]
    assert pages == [["Threshold", "Attack", "Hold", "Decay"], ["Range", "Return", "Mode"],
                     ["Key HP", "Key LP", "Listen"], ["Lockout", "Lookahead", "Link"]]
    by = {p["name"]: p for p in e["params"]}
    assert all(len(p["name"]) <= 10 for p in e["params"])   # the screen's label width
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])
    assert by["Mode"]["names"] == ["Gate", "Duck"]
    assert by["Listen"]["names"] == ["Off", "Key"]
    assert by["Link"]["names"] == ["Max", "Sum", "Left"]
    assert {n for n, p in by.items() if p["unit"] == "ms"} == \
        {"Attack", "Hold", "Decay", "Lockout", "Lookahead"}
    assert {n for n, p in by.items() if p["unit"] == "hz"} == {"Key HP", "Key LP"}
    assert (by["Range"]["min"], by["Threshold"]["min"], by["Return"]["max"]) == (-90, -80, 12)
    assert (by["Key HP"]["def"], by["Key LP"]["def"]) == (20, 20000)   # both out


def test_instance_size_follows_the_rate(renderer, tmp_path, tool):  # noqa: F811
    # 5 ms of look-ahead line, at most 510 frames, after a 368-byte struct
    # with no pointers (so a 32-bit build's is the same): 2,144 bytes at the
    # FM-1's rate, 4,464 at the cap (102 kHz and above).
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"] == [2144]
    sizes = {rate: size for rate, _, size in tool["rates"]}
    assert sizes["44118"] == 2144 and sizes["48000"] == 2304 and sizes["8000"] == 704
    assert sizes["102000"] == sizes["192000"] == sizes["384000"] == 4464
    assert all(size % 16 == 0 for size in sizes.values())


# --- host contracts ---------------------------------------------------------

def test_rendering_is_deterministic(renderer, tmp_path):  # noqa: F811
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="a",
                     extra=GAPS)
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="b",
                     extra=GAPS)
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("extra", [[], ["Mode=1", "Lookahead=5"], ["Listen=1", "Link=2"],
                                   ["Lookahead=0", "Key HP=20", "Key LP=20000"]])
def test_block_size_does_not_change_the_output(renderer, tmp_path, extra):  # noqa: F811
    wavs = []
    for frames in ("64", "7", "1"):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY, *extra),
                           name=f"f{frames}", extra=["--frames", frames, *GAPS])
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


def test_output_ignores_initial_memory(renderer, tmp_path):  # noqa: F811
    wavs = []
    for fill in ("0", "0xA5", "0xFF"):
        s, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY),
                           name=f"fill{fill}", extra=["--fill", fill, *GAPS])
        assert s["nonfinite"] == 0
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


@pytest.mark.parametrize("value,same_as", [
    ("nan", None),            # NaN is the default (fm1_param_clamp)
    ("1e9", "max"),
    ("-1e9", "min"),
    ("inf", "max"),
])
def test_out_of_range_parameters_clamp(renderer, tmp_path, entry, value, same_as):  # noqa: F811
    params = entry["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad",
                     extra=GAPS)
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good",
                     extra=GAPS)
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [
    [],
    BUSY,
    ["Mode=1", "Range=-20"],                 # Duck: the gain sits at 1, silence stays silent
    ["Listen=1", "Key HP=300", "Key LP=900"],
    ["Range=0", "Lookahead=5", "Link=1"],
])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
@pytest.mark.parametrize("filters", [False, True])
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad, filters):  # noqa: F811
    # The guard reads NaN as 0 and clamps everything else to +/-16, the key
    # and the audio alike, so no state is poisoned: half a second after the
    # fault the output is the fault-free output. With the key filters out it
    # is the same bits (the detector's peak meets the clean one again); with
    # them in, within one 16-bit step (their states converge, not meet).
    params = ["Threshold=-30", "Hold=20", "Decay=60", "Lookahead=2", "Lockout=40"]
    if filters:
        params += ["Key HP=200", "Key LP=4000"]
    base = ["--input", "noise", "--seconds", "1.5", *cli(*params), *GAPS]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.4..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    assert s["raw_peak"] <= 16.0
    tail = slice(RATE, None)
    tol = LSB if filters else 0.0
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= tol
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= tol


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY),
                     extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


# --- what passes untouched -----------------------------------------------------

def reference(renderer, tmp_path, input, seconds, extra=()):  # noqa: F811
    return render(renderer, tmp_path, input=input, seconds=seconds,
                  fx=[("test-gain", ["Gain=1"])], name="ref", extra=list(extra))


@pytest.mark.parametrize("params", [
    ["Range=0"],
    ["Range=0", "Mode=1", "Key HP=500", "Link=2"],
])
def test_range_zero_passes_the_input_bit_for_bit(renderer, tmp_path, params):  # noqa: F811
    # Range 0 dB: nothing to attenuate in either Mode, whatever the key does.
    ref, _, ref_wav = reference(renderer, tmp_path, "noise", 1.0, GAPS)
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0, fx=fx(*params),
                             name="gate", extra=GAPS)
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


def test_an_open_gate_is_bit_transparent(renderer, tmp_path):  # noqa: F811
    # At the defaults the renderer's noise (+-0.5, -6 dBFS) is far over the
    # -40 dB threshold: once the 0.5 ms attack is done (23 frames) the gain is
    # exactly 1 and every sample passes untouched.
    _, ref, _ = reference(renderer, tmp_path, "noise", 1.0)
    _, out, _ = render(renderer, tmp_path, input="noise", seconds=1.0, fx=fx(), name="gate")
    assert out[23:] == ref[23:]
    assert any(abs(a) < abs(b) for a, b in zip(out[:22], ref[:22]))   # the attack


# --- every knob does what it says --------------------------------------------

def test_a_quiet_gap_is_gated(renderer, tmp_path):  # noqa: F811
    # The renderer's sine with a gap of DC at -50 dB (0.003, 98 16-bit steps)
    # from 0.3 to 0.6 s. The gate holds 50 ms, decays 150 ms (80 dB), then
    # sits at Range: -80 dB (nothing in 16 bits), or -20 dB (9.8 steps).
    gap = ["--fault", "0.3..0.6:0.003"]
    _, closed, _ = render(renderer, tmp_path, input="sine", seconds=0.8, fx=fx(), name="c",
                          extra=gap)
    _, shallow, _ = render(renderer, tmp_path, input="sine", seconds=0.8, name="s",
                           fx=fx("Range=-20"), extra=gap)
    _, ref, _ = reference(renderer, tmp_path, "sine", 0.8, gap)
    early = slice(int(0.305 * RATE), int(0.34 * RATE))      # the detector's fall, then Hold
    late = slice(int(0.52 * RATE), int(0.6 * RATE))         # closed
    assert closed[early] == ref[early]
    assert max(abs(x) for x in closed[late]) == 0.0
    assert max(abs(x) for x in shallow[late]) == pytest.approx(0.0003, abs=LSB)
    after = slice(int(0.61 * RATE), int(0.8 * RATE))         # the sine back: open again
    assert closed[after] == ref[after]


def test_duck_lowers_the_signal_while_the_key_is_loud(renderer, tmp_path):  # noqa: F811
    # The renderer's sine keys itself: Duck holds it at Range, -20 dB.
    _, duck, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="d",
                        fx=fx("Mode=1", "Range=-20"))
    _, ref, _ = reference(renderer, tmp_path, "sine", 1.0)
    assert rms(duck, 0.2, 1.0) / rms(ref, 0.2, 1.0) == pytest.approx(0.1, rel=1e-3)


def test_listen_hears_the_filtered_key(renderer, tmp_path):  # noqa: F811
    _, dark, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name="lp",
                        fx=fx("Listen=1", "Key LP=500"))
    _, bright, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name="hp",
                          fx=fx("Listen=1", "Key HP=5000"))
    _, flat, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name="flat",
                        fx=fx("Listen=1"))
    _, ref, _ = reference(renderer, tmp_path, "noise", 0.5)
    assert flat == ref                    # filters out: the key is the input
    b_dark, b_flat, b_bright = (brightness(x, 0.1, 0.5) for x in (dark, flat, bright))
    assert b_dark < 0.15 < 1.3 < b_flat < b_bright       # measured 0.10, 1.41, 1.86


def test_key_filters_reject_what_should_not_open_the_gate(renderer, tmp_path):  # noqa: F811
    # The renderer's 440 Hz sine at -6 dBFS keys the gate open. Key HP at
    # 5 kHz takes 42.9 dB off it, which leaves the key at -48.9 dB, under the
    # -40 dB threshold: the gate never opens and the output stays at Range
    # (-80 dB). Key LP at 2 kHz takes 0.02 dB off: the gate opens as before.
    # The sine's onset (from rest, at full slope) is broadband, so it opens
    # the gate through the HP for Hold and Decay; from 0.25 s on it is shut.
    _, hp, _ = render(renderer, tmp_path, input="sine", seconds=0.5, fx=fx("Key HP=5000"))
    assert max(abs(x) for x in hp[int(0.25 * RATE):]) <= 2 * LSB      # 0.5 x 1e-4: 1.6 steps
    _, ref, _ = reference(renderer, tmp_path, "sine", 0.5)
    _, lp, _ = render(renderer, tmp_path, input="sine", seconds=0.5, fx=fx("Key LP=2000"),
                      name="lp")
    assert lp[30:] == ref[30:]            # the LP delays the trigger by about 2 frames


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, _, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.2",
         "--note", "0.6:52:100:0.2", "--seconds", "1.5",
         *cli("Threshold=-30", "Hold=30", "Decay=80", "Lookahead=1"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["gate", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.05, 0.2) > 1e-2 and rms(left, 0.65, 0.8) > 1e-2


SWITCH_BASE = ["Threshold=-30", "Attack=1", "Hold=10", "Decay=30", "Range=-30"]
SWITCH_CASES = [
    ("gate", "Mode", [0, 1], SWITCH_BASE, "sine", None),
    ("gate", "Mode", [0, 1], SWITCH_BASE, "notes", None),
    ("gate", "Listen", [0, 1], [*SWITCH_BASE, "Key HP=400", "Key LP=3000"], "sine", None),
    ("gate", "Listen", [0, 1], [*SWITCH_BASE, "Key LP=1500"], "notes", None),
    ("gate", "Link", [0, 1, 2], [*SWITCH_BASE, "Listen=1", "Key HP=300"], "notes", None),
    ("gate", "Lookahead", "lookahead0", SWITCH_BASE, "notes", None),
    ("gate", "Lookahead", "lookahead", [*SWITCH_BASE, "Mode=1"], "sine", None),
]


@pytest.mark.parametrize("fx_id,param,values,base,source,ceiling", SWITCH_CASES,
                         ids=[f"{k}-{c[1]}-{c[4]}" for k, c in enumerate(SWITCH_CASES)])
def test_switches_modulated_fast_are_clean(renderer, tmp_path, fx_id, param, values, base,
                                           source, ceiling):  # noqa: F811
    # The owner's switch rule (engines/README.md, "Parameters"): Mode,
    # Listen and Link crossfade over 5 ms and Lookahead crossfades its delay,
    # so each turned every third block steps the output no more than holding
    # it does, plus a 5 ms crossfade's bound.
    switches.test_fast_modulation_is_clean(renderer, tmp_path, fx_id, param, values, base,
                                           source, ceiling)


# --- fm1-gate-test: what fm1-render cannot drive ---------------------------------

def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise bursts; between blocks of 1-64 frames, up to two
    # parameters jump to their minimum, maximum, default, a random value,
    # beyond the range, NaN or an infinity; a quarter of the blocks keyed
    # from a separate noise. The output is the gated input or the filtered
    # key: measured 0.76 at worst (the filters' overshoot on +-0.5 noise).
    s = tool["sweep"]
    assert s["samples"] > 20 * RATE
    assert s["nonfinite"] == 0 and s["peak"] < 1.0


def test_block_size_and_the_key_hook_do_not_change_the_output(tool):
    # 22 changes of every parameter mid-stream, rendered at 64, 7 and 1
    # frames (split at the changes): identical. render_key(NULL) and
    # render_key(a copy of the input) are render, bit for bit (the note's
    # §7.10 test 1).
    b = tool["blocks"]
    assert b["block_independent"] and b["render_key_null"] and b["render_key_copy"]


def test_attack_opens_in_its_time_along_a_db_ramp(tool):
    # [Attack ms, trigger frame, frames to gain 1, gain at 1/4, at 1/2, ...]
    # From Range -80 dB the attenuation falls 80 dB per Attack, so the gate
    # is fully open after Attack (at least one frame), and the gain is
    # dB-linear on the way: -60 dB a quarter of the way, -40 dB half way.
    for attack, trigger, frames, quarter, half, kq, kh in tool["attack"]:
        assert trigger == 100                         # the key's first frame
        want = max(1, math.ceil(attack * 1e-3 * RATE))
        assert want <= frames <= want + 1, attack
        if attack >= 2:
            t = attack * 1e-3 * RATE
            assert 20 * math.log10(quarter) == pytest.approx(-80 + 80 * kq / t, abs=0.01)
            assert 20 * math.log10(half) == pytest.approx(-80 + 80 * kh / t, abs=0.01)


def test_close_timing_detector_hold_and_decay(tool):
    # [Hold, Decay, Range, frames to the trigger's fall, Hold's frames,
    #  Decay's frames, closed gain, gain half way through the decay]
    fall = math.exp(-1 / (FALL * RATE))
    close = db_gain(-40 - 4)                          # Threshold - Return
    want_fall = math.ceil(math.log(close / 0.5) / math.log(fall))
    for hold, decay, rng, fall_frames, hold_frames, decay_frames, closed, mid in tool["close"]:
        # The level falls from the key's 0.5 with the 4 ms time constant.
        assert abs(fall_frames - want_fall) <= 1
        # Hold: exactly its frames from the fall to the decay's first frame.
        assert hold_frames == round(hold * 1e-3 * RATE)
        # Decay: 80 dB per Decay, so -Range / 80 of it.
        want = math.ceil(-rng / 80 * decay * 1e-3 * RATE)
        assert abs(decay_frames - want) <= 1, (hold, decay, rng)
        assert closed == pytest.approx(db_gain(rng), rel=1e-6)
        assert 20 * math.log10(mid) == pytest.approx(rng / 2, abs=max(0.1, 80 / (decay * 44.1)))


def test_range_sets_the_closed_level(tool):
    for rng, gain, out in tool["range"]:
        want = 0.0 if rng <= -90 else db_gain(rng)
        assert gain == pytest.approx(want, rel=1e-6, abs=0.0) and out == gain
    assert dict((r, g) for r, g, _ in tool["range"])[-90] == 0.0      # off: silence


def test_return_is_hysteresis(tool):
    # Threshold -20 dB: levels -20.9 (closed), -19.2 (opens), -24.4, -28 dB.
    # Return 6 dB keeps it open at -24.4 and closes it at -28; Return 0
    # closes it at -24.4.
    rows = dict((r, opens) for r, opens in tool["hysteresis"])
    assert rows[6] == [0, 1, 1, 0]
    assert rows[0] == [0, 1, 0, 0]


def test_duck_inverts_the_gain(tool):
    d = tool["duck"]
    assert d["gains"][0] == 1.0                                # quiet key: untouched
    assert d["gains"][1] == pytest.approx(0.1, rel=1e-6)      # loud key: down to Range
    assert d["gains"][2] == 1.0 and d["gains"][3] == 1.0      # back after Hold and Decay
    assert d["open"] == [0, 1, 0, 0]


def test_lockout_stops_retriggers(tool):
    # Five 10 ms bursts 100 ms apart, the gate closed between them. A burst
    # within Lockout of the last opening is ignored.
    rows = {lock: (n, between) for lock, n, between in tool["lockout"]}
    assert rows == {0: (5, 1), 50: (5, 1), 150: (3, 1), 250: (2, 1), 450: (1, 1)}


def test_lookahead_is_the_latency(tool):
    # [rate, ms, measured frames, the state's latency, nothing else came out]
    for rate, ms, got, latency, clean in tool["latency"]:
        want = min(510, round(ms * 1e-3 * rate))
        assert got == want == latency and clean, (rate, ms)
    by = {(rate, ms): got for rate, ms, got, _, _ in tool["latency"]}
    assert by[(44118, 2)] == 88 and by[(44118, 5)] == 221 and by[(44118, 0)] == 0
    assert by[(192000, 5)] == 510                  # the cap: 2.66 ms at 192 kHz


def test_lookahead_keeps_the_onset_whole(tool):
    # [Lookahead, d, worst |out - in| over the burst's first 5 ms, first out,
    #  first in]. Range -90 (off), Attack 0.5 ms: without look-ahead the
    # attack eats the onset; with 2 ms the gate is open before it arrives.
    rows = {look: (d, worst, first, first_in) for look, d, worst, first, first_in in tool["onset"]}
    d, worst, first, first_in = rows[2]
    assert d == 88 and worst == 0.0 and first == first_in
    d, worst, first, first_in = rows[0]
    assert d == 0 and worst > 0.1 and abs(first) < 1e-4 * abs(first_in) * 2


def test_key_filters_are_butterworth_pairs(tool):
    # Heard through Listen: steady sines at integer frequencies, each
    # measured at its exact bin, against the bilinear Butterworth formula:
    # within 1e-4 dB down to -70 dB (measured 3.5e-5); -3.01 dB at each
    # cutoff; 12 dB per octave.
    seen = 0
    for hp, lp, rows in tool["filters"]:
        for f, got in rows:
            want = butterworth_db(f, hp, lp)
            if want > -70:
                assert got == pytest.approx(want, abs=1e-4), (hp, lp, f)
                seen += 1
    assert seen > 70
    resp = {(hp, lp): dict(rows) for hp, lp, rows in tool["filters"]}
    assert resp[(100, 20000)][100] == pytest.approx(-3.0103, abs=1e-3)
    assert resp[(20, 500)][500] == pytest.approx(-3.0103, abs=1e-3)
    # An octave apart, deep in the stopband: about 12 dB.
    assert resp[(1000, 20000)][100] - resp[(1000, 20000)][50] == pytest.approx(12.0, abs=0.1)
    assert resp[(20, 500)][8000] - resp[(20, 500)][16000] > 12.0


def test_listen_equals_a_reference_of_the_filter_pair(tool):
    # The note's §7.10 test 4: the driver's stereo noise through Key HP
    # 300 Hz then Key LP 3 kHz, against the same SVFs in float64 with libm's
    # tan. Their difference is float rounding: measured under 2e-7.
    noise = lcg_noise(11, 4000)
    out = tool["listen_ref"]
    for ch in (0, 1):
        x = noise[ch::2]
        want = svf(svf(x, 300, True), 3000, False)
        got = out[ch::2]
        assert max(abs(a - b) for a, b in zip(got, want)) < 2e-6


def test_link_on_listen_and_on_the_detector(tool):
    # Listen, filters out: Max is the key in stereo, Sum 0.5 (L + R) on both
    # channels, Left the left on both, exactly.
    assert tool["link_listen"] == [[0, True], [1, True], [2, True]]
    # [link, left-only key opens, right-only opens, anti-phase opens]
    assert tool["link_detect"] == [[0, 1, 1, 1], [1, 1, 1, 0], [2, 1, 0, 1]]


def test_key_lp_delays_the_trigger(tool):
    # A key step to 1 against a 0.5 threshold: with Key LP in, the trigger
    # waits for the filtered step to cross 0.5, which the float64 reference
    # puts within a frame; close to the filter's group delay at DC,
    # sqrt(2) / (2 pi fc): 2.5, 9.9 and 39.7 frames at 4 kHz, 1 kHz, 250 Hz.
    for lp, frames in tool["lp_trigger"]:
        if lp >= 20000:
            assert frames == 0
            continue
        step = svf([1.0] * 200, lp, False)
        want = next(n for n, y in enumerate(step) if y > db_gain(-6.0206))
        assert abs(frames - want) <= 1, lp
        assert frames == pytest.approx(math.sqrt(2) * RATE / (2 * math.pi * lp), abs=1.0)


def test_chattering_is_suppressed(tool):
    # A 200 Hz tone decaying at 50 dB/s through the -40 dB threshold over
    # noise peaking near it. With no hysteresis and the shortest hold the
    # gate chatters (measured 9 openings); Return, Hold or Lockout each stop
    # it (1, 1 and 2).
    rows = {(r, h, l): n for r, h, l, n in tool["chatter"]}
    assert rows[(0, 2, 0)] >= 5
    assert rows[(4, 2, 0)] == 1 and rows[(0, 50, 0)] == 1 and rows[(4, 50, 0)] == 1
    assert rows[(8, 50, 0)] == 1
    assert rows[(0, 2, 300)] <= 2


def test_bad_keys_do_not_latch(tool):
    # [value, opened, frame it closed, all finite, open at the end, gain at
    # the end]. 100 frames of NaN, infinities or 1e30 on a silent key: NaN
    # reads as silence and never opens the gate; the rest are clamped to 16
    # and close it on the very frame a clean full-scale (16) key does.
    rows = {v: r for v, *r in tool["bad_key"]}
    assert rows["nan"][0] == 0 and rows["nan"][2]
    clean = rows["16"][1]
    assert clean > 0
    for v in ("inf", "-inf", "1e+30"):
        opened, closed, finite, open_end, gain = rows[v]
        assert opened == 1 and closed == clean and finite and open_end == 0
        assert gain == pytest.approx(db_gain(-80), rel=1e-6)


def test_a_key_other_than_the_input_gates_it(tool):
    # fm1_gate_render_key: noise in, a click every 250 ms as the key. After
    # each click the noise passes (-10.8 dB, the noise's own RMS); before the
    # next it sits at Range, -60 dB under it.
    k = tool["external_key"]
    assert k["open_db"] == pytest.approx(10 * math.log10(0.25 / 3), abs=0.2)
    assert k["open_db"] - k["closed_db"] == pytest.approx(60.0, abs=0.5)


def test_host_rates(tool):
    accepted = {rate: ok for rate, ok, _ in tool["rates"]}
    assert accepted == {"0": False, "7999": False, "8000": True, "44118": True,
                        "48000": True, "96000": True, "102000": True, "192000": True,
                        "384000": True, "400000": False, "nan": False, "inf": False,
                        "-44118": False}


def test_tan_is_accurate(tool):
    # The key filters' tan, without libm: within 1e-6 relative on
    # [0, 0.45 pi] (measured 6.1e-7, at the top, where cos is small).
    a = tool["approx"]
    assert a["tan_rel"] < 1e-6 and a["tan_0"] == 0.0


def test_output_is_the_same_bits_on_every_build(tool):
    # No libm and no fused multiply-adds (fx_gate.cc), so every float of
    # these three renders should be the same on every IEEE single-precision
    # build without FMA, the browser's WebAssembly included. A deliberate
    # change to the DSP moves these: check it in the browser's module, then
    # pin the new ones.
    assert tool["hash"] == ["b0a682c0", "c503f3be", "1aed7712"]
