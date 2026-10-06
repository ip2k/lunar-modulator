"""FM6 (engine id dx7): six-operator FM on msfa, Google's
music-synthesizer-for-android FM core (engines/src/msfa_dx7.cc,
engines/msfa.md).

What is checked:
  - the vendored msfa files are upstream's, byte for byte; the built-in bank
    header is what tools/dx7_bank.py makes; the engine's carrier table is
    msfa's algorithm table; msfa's tables, const data made ahead of time by
    tools/msfa_tables.py, are exact (libm's last bits do not move them) and
    equal msfa's own init word for word, the frequency table at every rate;
    at 44,118 Hz an instance reads them all from const data, at any other
    rate a frequency table in its own memory;
  - against an independent port of the same core, Felucca's fm6_core.c
    (fm1-dx7-oracle): all 32 algorithms with and without feedback, the
    pitch envelope, the LFO, velocity and scaling, fixed frequencies;
  - the loops of algorithms 4 and 6 against msfa's own kernels, bit for bit;
  - tuning, transpose, envelope rates in dB per second at two host rates,
    the LFO's speed, the amplitude modulation's depth, the pitch envelope,
    velocity, the six carriers of algorithm 32;
  - the four macros, two of them byte for byte against an edited voice;
  - SysEx: single voices and banks, several in a file, checksums, the
    built-in bank exported and read back byte for byte, hostile bytes;
  - every built-in voice sounds, finite and within range; voices end, steal
    and retrigger; instance size and time per block.
The engine contracts every engine shares (initial memory, any parameter
value, host block sizes, per-note offsets, SMOOTH) are in the generic tests,
which list dx7 like the others.
"""
import hashlib
import json
import math
import re
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from tests.engine_helpers import ENGINES, RATE, cents, pitch_hz, render, renderer, rms  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import dx7_bank as dx  # noqa: E402
import msfa_tables  # noqa: E402

ORACLE = ENGINES / "build" / "fm1-dx7-oracle"
MSFA = ENGINES / "third_party" / "msfa"
FELUCCA = ENGINES / "third_party" / "felucca-fm6"
USER1 = 32                           # the Patch value of User 1 (after the 32 built-in voices)
SINE = 31                            # PURE SINE

Op, Voice, silent = dx.Op, dx.Voice, dx.silent


def held_op(level=99, ratio=1.0, **kw):
    """An operator that holds while the key is down (no equal neighbouring
    levels: msfa's and Dexed's envelopes differ there, engines/msfa.md)."""
    kw.setdefault("rates", (80, 50, 40, 60))
    kw.setdefault("levels", (99, 85, 70, 0))
    return Op(level=level, ratio=ratio, **kw)


def sine_voice(**kw):
    """One carrier at output level 99, ratio 1: the INIT VOICE's shape."""
    return Voice("TEST", 32, ops=[Op(level=99, rates=(99, 99, 99, 99), levels=(99, 99, 99, 0),
                                     **kw)] + [silent() for _ in range(5)])


def syx(tmp_path, voice, name="v"):
    path = tmp_path / f"{name}.syx"
    path.write_bytes(dx.vced_syx(voice))
    return path


def play(renderer, tmp_path, voice=None, params=(), notes=("0:60:100:1",), seconds=1.2,
         name="out", extra=(), files=()):
    """Render FM6; `voice` goes to User 1 and is played unless params name
    another Patch."""
    args = list(extra)
    paths = list(files)
    if voice is not None:
        paths.insert(0, syx(tmp_path, voice, name))
    for p in paths:
        args += ["--sysex", str(p)]
    ps = list(params)
    if voice is not None and not any(p.startswith("Patch=") for p in ps):
        ps.insert(0, f"Patch={USER1}")
    return render(renderer, tmp_path, "dx7", params=ps, notes=list(notes), seconds=seconds,
                  name=name, extra=args)


def windows(x, ms=10):
    n = int(RATE * ms / 1000)
    return [math.sqrt(sum(v * v for v in x[a:a + n]) / n) for a in range(0, len(x) - n + 1, n)]


def peaks(x, ms=10):
    """The largest |sample| of each window: a sine's amplitude whatever the
    window holds of its cycle (an RMS over a part cycle moves with the
    phase)."""
    n = int(RATE * ms / 1000)
    return [max(abs(v) for v in x[a:a + n]) for a in range(0, len(x) - n + 1, n)]


def db(a, b):
    return 20 * math.log10(a / b)


def goertzel(x, f, rate=RATE):
    w = 2 * math.pi * f / rate
    c = 2 * math.cos(w)
    s1 = s2 = 0.0
    for v in x:
        s1, s2 = v + c * s1 - s2, s1
    return math.sqrt(max(0.0, s1 * s1 + s2 * s2 - c * s1 * s2)) * 2 / len(x)


def oracle(tmp_path, voice, key=60, vel=100, gate=0.5, seconds=1.0, name="o"):
    path = syx(tmp_path, voice, name)
    out = subprocess.run([str(ORACLE), "--vced", str(path), "--key", str(key), "--vel", str(vel),
                          "--gate", str(gate), "--seconds", str(seconds)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


# --------------------------------------------------------------- sources --

def test_vendored_msfa_files_are_upstreams(renderer):
    """Every vendored msfa file has the sha256 UPSTREAM.md records for
    upstream's file at the pinned commit; with a clone in reference/, the
    vendor script compares them with git itself."""
    table = (MSFA / "UPSTREAM.md").read_text()
    pinned = dict(re.findall(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|", table, re.M))
    files = sorted(p.name for p in MSFA.iterdir() if p.suffix in (".h", ".cc") or p.name == "LICENSE")
    assert sorted(pinned) == files
    for name, digest in pinned.items():
        assert hashlib.sha256((MSFA / name).read_bytes()).hexdigest() == digest, name
    for ours, ref in ((MSFA, "msfa"), (FELUCCA, "Felucca")):
        # reference/ is git-ignored: in the repository, or two levels up
        # from a worktree under scratch/.
        homes = [ROOT] + ([ROOT.parents[1]] if len(ROOT.parents) > 1 else [])
        for clone in (home / "reference" / ref for home in homes):
            if (clone / ".git").exists():
                subprocess.run([sys.executable, str(ours / "vendor.py"), str(clone), "--check"],
                               check=True, capture_output=True)
                break


def test_felucca_oracle_file_is_apache_and_upstreams():
    src = (FELUCCA / "fm6_core.c").read_bytes()
    assert src.startswith(b"/* SPDX-License-Identifier: Apache-2.0")
    table = (FELUCCA / "UPSTREAM.md").read_text()
    digest = re.search(r"`fm6_core.c` \| `([0-9a-f]{64})`", table).group(1)
    assert hashlib.sha256(src).hexdigest() == digest


def test_the_bank_header_is_what_the_tool_makes():
    subprocess.run([sys.executable, str(ROOT / "tools" / "dx7_bank.py"), "--check"], check=True)


def test_carrier_table_is_msfas_algorithm_table():
    """kCarriers in msfa_dx7.cc: bit k set where msfa's FmCore routes
    operator k (the sixth first) to the output, for all 32 algorithms."""
    rows = re.findall(r"\{ \{ ((?:0x[0-9a-f]{2}, ){5}0x[0-9a-f]{2}) \} \}, // (\d+)",
                      (MSFA / "fm_core.cc").read_text())
    assert [int(n) for _, n in rows] == list(range(1, 33))
    want = [sum(1 << k for k, f in enumerate(r.split(", ")) if int(f, 16) & 3 == 0) for r, _ in rows]
    src = (ENGINES / "src" / "msfa_dx7.cc").read_text()
    body = re.search(r"kCarriers\[32\] = \{([^}]*)\}", src).group(1)
    assert [int(x, 16) for x in re.findall(r"0x[0-9A-F]{2}", body)] == want


def test_msfas_tables_are_exact(renderer):
    """msfa fills its sine, exp2 and frequency tables at start-up from one
    libm value each (cos and sin of 2 pi / 1024, 2^(1/1024)), then integer
    steps or repeated multiplication, and osc_freq takes a log per fine step.
    tools/msfa_tables.py runs those steps from correctly rounded values
    (Decimal) and the engine reads its output, const data: so a libm whose
    last bit differs cannot make this desktop, glibc, musl and the browser
    disagree. At 44,118 Hz the frequency table is const data too; at any
    other rate the instance fills its own, which must match as well."""
    from decimal import Decimal
    sin, exp2 = msfa_tables.sin_table(), msfa_tables.exp2_table()
    for rate in (RATE, 22050):
        got = json.loads(subprocess.run([str(ORACLE), "--tables", "--rate", str(rate)], check=True,
                                        capture_output=True, text=True).stdout)
        assert got["sin_sum"] == sum(sin) and got["sin"] == [sin[1], sin[257], sin[2047]]
        assert got["exp2_sum"] == sum(exp2) and got["exp2"] == [exp2[1], exp2[1023], exp2[2047]]
        lut = msfa_tables.freq_table(rate)
        assert got["freqlut_sum"] == sum(lut) and got["freqlut"] == [lut[0], lut[512], lut[1024]]
        assert got["freqlut_const"] == (rate == RATE)
    # osc_freq's fine term: floor(24204406.323123 * log(1 + 0.01 fine) + 0.5)
    k = 24204406.323123
    want = [math.floor(k * float((1 + Decimal(f) / 100).ln()) + 0.5) for f in range(100)]
    # osc_freq computes 1 + 0.01 * fine in double first; that sum is exact
    # enough here that its correctly rounded log is the same double.
    assert got["osc_fine"] == want


def test_the_const_tables_are_what_the_tool_makes():
    """src/msfa_rom.cc is tools/msfa_tables.py's output, unedited."""
    subprocess.run([sys.executable, str(ROOT / "tools" / "msfa_tables.py"), "--check"], check=True)


@pytest.mark.parametrize("rate", [RATE, 44100, 16385, 384000])
def test_the_tables_equal_msfas_own_init(renderer, rate):
    """fm1-dx7-oracle links upstream's sin.cc, exp2.cc and freqlut.cc as they
    are and runs their init: the const sine and exp2 tables and the 44,118 Hz
    frequency table equal what they fill, word for word; so does the
    engine's own fill (FillFreqLut, no libm) at 381 rates from 16,385 to
    384,000 Hz; and so does the table an instance reads at `rate`, const data
    at 44,118 Hz only."""
    r = subprocess.run([str(ORACLE), "--tables-vs-msfa", "--rate", str(rate)],
                       capture_output=True, text=True)
    got = json.loads(r.stdout)
    assert r.returncode == 0, got
    assert got["sin"] == [2048, 0] and got["exp2"] == [2048, 0] and got["freqlut_44118"] == [1025, 0]
    assert got["fill"]["rates"] >= 381 and got["fill"]["bad"] == 0
    assert got["engine"] == {"rate": rate, "const": rate == RATE, "words": 1025, "bad": 0}


def test_the_table_macros_touch_only_the_tables():
    """src/msfa_prelude.h turns msfa's table names into pointer reads
    (`sintab` is `(*fm1_sintab)`...): in the vendored files those names must
    stand for the tables and nothing else, and only where expected."""
    where = {"sintab": {"sin.h", "sin.cc"}, "exp2tab": {"exp2.h", "exp2.cc"}, "lut": {"freqlut.cc"}}
    for name, files in where.items():
        found = {p.name for p in MSFA.iterdir() if p.suffix in (".h", ".cc")
                 and re.search(rf"\b{name}\b", p.read_text())}
        assert found == files, name


# ---------------------------------------------------------------- oracle --

def algorithm_voice(alg, fb):
    """Every operator sounding, at mixed ratios and levels, holding."""
    return Voice("ALG", alg, feedback=fb, ops=[
        held_op(95, 1.0), held_op(78, 2.0), held_op(90, 1.0, detune=9),
        held_op(74, 3.0), held_op(84, 0.5), held_op(70, 1.0)])


@pytest.mark.parametrize("alg", range(1, 33))
def test_every_algorithm_matches_the_oracle(renderer, tmp_path, alg):
    """Each algorithm, feedback 0 and 5, against Felucca's port of the same
    core: the same waveform to within 25 dB SNR (the two differ in their
    sine tables, 64- against 32-sample blocks and Dexed's level-scaling
    rounding) and the same 10 ms envelope to within 0.6 dB. Algorithms 4
    and 6 with feedback are the exception by design: Felucca feeds the sixth
    operator back to itself there, FM6 runs the DX7's loop through the
    fourth or fifth (dx7_loop.h); their envelopes still agree to 3 dB and
    the loop makes a difference."""
    for fb in (0, 5):
        r = oracle(tmp_path, algorithm_voice(alg, fb), name=f"a{alg}-{fb}")
        assert r["peak_ours"] > 1e6, (alg, fb)
        if fb and alg in (4, 6):
            assert r["env_db"] < 3.0, (alg, fb, r)
            plain = oracle(tmp_path, algorithm_voice(alg, 0), name=f"a{alg}-0b")
            assert abs(r["rms_ours"] - plain["rms_ours"]) > 1e-4 * plain["rms_ours"]
        else:
            assert r["snr_db"] > 25 and r["env_db"] < 0.6, (alg, fb, r)


ORACLE_VOICES = {
    # the pitch envelope: up a fifth from below, drifting
    "pitch-env": Voice("PEG", 1, pitch_rates=(70, 60, 50, 50), pitch_levels=(70, 40, 50, 60),
                       ops=[held_op(99), held_op(70), *[silent()] * 4]),
    # LFO pitch modulation, sine, no delay
    "lfo-pitch": Voice("LFO", 1, lfo_speed=40, lfo_pmd=50, pms=5, lfo_wave=4,
                       ops=[held_op(99), held_op(60), *[silent()] * 4]),
    # LFO with a delay, triangle
    "lfo-delay": Voice("LFD", 1, lfo_speed=55, lfo_delay=60, lfo_pmd=70, pms=6, lfo_wave=0,
                       ops=[held_op(99), held_op(60), *[silent()] * 4]),
    # velocity sensitivity, rate and level scaling on both sides of the break point
    "scaling": Voice("SCL", 1, ops=[held_op(99, vel=7, rate_scaling=5),
                                    held_op(80, 1.0, vel=7, ld=40, rd=60, lc=1, rc=2, bp=50),
                                    *[silent()] * 4]),
    # a fixed-frequency modulator, detune at both ends
    "fixed-detune": Voice("FIX", 1, ops=[held_op(99, detune=0), Op(level=80, fixed=440.0, ratio=None,
                                         rates=(80, 50, 40, 60), levels=(99, 85, 70, 0), detune=14),
                                         held_op(90, 1.0, detune=14), held_op(60, 1.41),
                                         silent(), silent()]),
    # feedback 7 on a modulator chain, transposed up an octave
    "fb7-transpose": Voice("FB7", 1, feedback=7, transpose=36,
                           ops=[held_op(99), held_op(70), held_op(90), held_op(75), held_op(72),
                                held_op(80)]),
}


@pytest.mark.parametrize("name", sorted(ORACLE_VOICES))
@pytest.mark.parametrize("key,vel", [(36, 40), (60, 100), (84, 127)])
def test_voices_match_the_oracle(renderer, tmp_path, name, key, vel):
    """The pitch envelope and the LFO step every 64 samples in FM6 and every
    32 in Felucca, so the phases of those voices drift apart: they are held
    to the 10 ms envelope, within 1 dB (at C2 a window holds less than a
    cycle, so its RMS moves with the phase). The others are held to 0.6 dB
    and to the waveform as well, SNR 12 dB or more (at the top of the
    keyboard Dexed's rounding of level scaling's key groups is the
    difference)."""
    r = oracle(tmp_path, ORACLE_VOICES[name], key=key, vel=vel, name=f"{name}-{key}")
    if name in ("pitch-env", "lfo-pitch", "lfo-delay"):
        assert r["env_db"] < 1.0, r
    else:
        assert r["env_db"] < 0.6 and r["snr_db"] > 12, r


def test_the_loops_of_algorithms_4_and_6_are_msfas_kernels(renderer):
    """dx7_loop.cc on 3,000 random blocks: one operator with feedback is
    msfa's compute_fb to the bit, the loops' chains without feedback are
    FmCore's algorithms 4 and 6 to the bit."""
    out = subprocess.run([str(ORACLE), "--loop-check"], check=True, capture_output=True,
                         text=True).stdout
    r = json.loads(out)
    assert r == {"self_feedback": [1000, 0], "alg4_chain": [1000, 0], "alg6_chain": [1000, 0]}


# ----------------------------------------------------------------- sound --

@pytest.mark.parametrize("key", [33, 57, 69, 93])
def test_tuning(renderer, tmp_path, key):
    _, left, _ = render(renderer, tmp_path, "dx7", params=[f"Patch={SINE}"],
                        notes=[f"0:{key}:100:1.5"])
    ref = 440.0 * 2 ** ((key - 69) / 12)
    assert abs(cents(pitch_hz(left, 0.3, 1.0), ref)) < 0.5


def test_transpose_and_fixed_frequency(renderer, tmp_path):
    """Transpose 36 plays an octave up (msfa's synth ignores it; FM6 applies
    it). A fixed-frequency carrier sounds its frequency on any key."""
    v = sine_voice()
    v.transpose = 36
    _, left, _ = play(renderer, tmp_path, v, notes=["0:57:100:1.5"])
    assert abs(cents(pitch_hz(left, 0.3, 1.0), 440.0)) < 0.5
    for key in (40, 80):
        fixed = Voice("FIX", 32, ops=[Op(level=99, fixed=1000.0, ratio=None, rates=(99, 99, 99, 99),
                                         levels=(99, 99, 99, 0))] + [silent()] * 5)
        _, left, _ = play(renderer, tmp_path, fixed, notes=[f"0:{key}:100:1.5"], name=f"f{key}")
        assert abs(cents(pitch_hz(left, 0.3, 1.0), 1000.0)) < 1.0


def test_algorithm_32_sounds_six_carriers(renderer, tmp_path):
    """Six carriers at ratios 1..6, output levels 99, 91, ... 59: the six
    harmonics, each 8 output-level steps (6 dB, msfa's 32 microsteps a
    step) below the one before."""
    ops = [Op(level=99 - 8 * k, ratio=k + 1, rates=(99, 99, 99, 99), levels=(99, 99, 99, 0))
           for k in range(6)]
    _, left, _ = play(renderer, tmp_path, Voice("SIX", 32, ops=ops), notes=["0:45:127:1.2"])
    seg = left[int(0.3 * RATE):int(0.8 * RATE)]
    mags = [goertzel(seg, 110.0 * (k + 1)) for k in range(6)]
    steps = [db(mags[k], mags[k + 1]) for k in range(5)]
    assert all(abs(s - 6.0) < 0.15 for s in steps), steps


def decay_db_per_s(left, a, b):
    w = windows(left, 10)
    i, j = int(a * 100), int(b * 100)
    return (20 * math.log10(w[i]) - 20 * math.log10(w[j])) / (b - a)


@pytest.mark.parametrize("rate_value", [40, 55])
def test_envelope_rate_in_db_per_second(renderer, tmp_path, rate_value):
    """A carrier's decay (R2, toward L2 = 0) falls at msfa's rate: qrate =
    R * 41 >> 6, (4 + (qrate & 3)) << (2 + 6 + (qrate >> 2)) of 2^24 (one
    doubling) per 64-sample block, at 44,118 Hz; at 22,050 Hz the envelope
    clock (44,118 / rate) keeps the same dB per second."""
    q = rate_value * 41 >> 6
    inc = (4 + (q & 3)) << (8 + (q >> 2))
    want = inc / 2 ** 24 * 6.0206 * RATE / 64
    v = Voice("DEC", 32, ops=[Op(level=99, rates=(99, rate_value, 99, 99), levels=(99, 0, 0, 0))]
              + [silent()] * 5)
    _, left, _ = play(renderer, tmp_path, v, notes=["0:69:127:2"], seconds=1.6)
    assert decay_db_per_s(left, 0.1, 0.5) == pytest.approx(want, rel=0.02)
    # 22,050 Hz: the renderer writes that rate; read it back directly.
    wav = tmp_path / "half.wav"
    path = syx(tmp_path, v, "half")
    subprocess.run([str(renderer), "--engine", "dx7", "--sysex", str(path), "--param", f"Patch={USER1}",
                    "--note", "0:69:127:2", "--rate", "22050", "--seconds", "1.6", "--out", str(wav)],
                   check=True, capture_output=True)
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    half = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767 for i in range(0, len(raw), 4)]
    n = 220                                       # 10 ms at 22,050 Hz
    hw = [math.sqrt(sum(x * x for x in half[k:k + n]) / n) for k in range(0, len(half) - n, n)]
    slope = (20 * math.log10(hw[10]) - 20 * math.log10(hw[50])) / 0.4
    assert slope == pytest.approx(want, rel=0.03)


@pytest.mark.parametrize("value,factor", [(0.0, 8.0), (1.0, 1 / 8.0), (0.25, 2 ** 1.5)])
def test_env_time_scales_the_envelopes(renderer, tmp_path, value, factor):
    """Env Time runs the envelopes 2^(6 (0.5 - t)) times as fast: 8 times at
    0, an eighth at 1."""
    v = Voice("DEC", 32, ops=[Op(level=99, rates=(99, 40, 99, 99), levels=(99, 0, 0, 0))]
              + [silent()] * 5)
    _, base, _ = play(renderer, tmp_path, v, notes=["0:69:127:3"], seconds=2.5, name="base")
    _, fast, _ = play(renderer, tmp_path, v, params=[f"Patch={USER1}", f"Env Time={value}"],
                      notes=["0:69:127:3"], seconds=2.5, name="t")
    b = decay_db_per_s(base, 0.1, 0.5)
    a, z = (0.02, 0.07) if factor > 4 else ((0.1, 2.0) if factor < 0.2 else (0.05, 0.25))
    assert decay_db_per_s(fast, a, z) / b == pytest.approx(factor, rel=0.04)


def test_env_time_never_delays_the_note(renderer, tmp_path):
    """At any Env Time a note's first block takes an envelope step: the
    note starts on the block it was played in, and the pitch envelope
    stands at its start level from then on. (Review, 2026-10-05: at Env
    Time 1 the clock owed its first step 8 blocks in, so a note started
    up to 10 ms late and at its unbent pitch.) The voice starts PL4 82,
    most of an octave up, and glides down; at Env Time 1 eight times
    slower, so its first 12 ms are still near the top."""
    v = sine_voice()
    v.pitch_rates, v.pitch_levels = (99, 99, 99, 99), (50, 50, 50, 82)
    _, a, _ = play(renderer, tmp_path, v, notes=["0:81:100:0.5"], seconds=0.3, name="a")
    _, b, _ = play(renderer, tmp_path, v, params=[f"Patch={USER1}", "Env Time=1"],
                   notes=["0:81:100:0.5"], seconds=0.3, name="b")
    first = [next(i for i, x in enumerate(y) if x) for y in (a, b)]
    assert first[0] == first[1] < 64
    pitches = msfa_table("pitchtab")
    start = (pitches[82] - pitches[50]) * 1200 / 32          # cents above the key
    assert cents(pitch_hz(b, 0.002, 0.012), 880.0) == pytest.approx(start, abs=40)


def two_op(level2=70, fb=3):
    """Algorithm 1 with every modulator at an instant attack (R1 99)."""
    def mod(level, ratio=1.0):
        return held_op(level, ratio, rates=(99, 50, 40, 60))
    return Voice("TWO", 1, feedback=fb, ops=[held_op(99), mod(level2, 2.0), held_op(90),
                                             mod(70), mod(70), mod(60)])


def test_brightness_is_the_modulators_output_level(renderer, tmp_path):
    """Brightness 0.75 adds 12 dB (two doublings) to the level of every
    operator that is not a carrier: while the key is held, exactly the voice
    with 16 more output-level steps (32 microsteps each) on its modulators.
    (msfa's attack curve depends on the level it starts from, so the
    modulators attack at once here; after the key-off the two differ where
    the release floor is reached, which Brightness lifts.)"""
    held = ["0:60:100:2"]
    _, _, a = play(renderer, tmp_path, two_op(70), params=[f"Patch={USER1}", "Brightness=0.75"],
                   notes=held, seconds=1.0, name="a")
    up = two_op(86)
    for k in (3, 4, 5):
        up.ops[k].level += 16
    _, _, b = play(renderer, tmp_path, up, notes=held, seconds=1.0, name="b")
    _, _, c = play(renderer, tmp_path, two_op(70), notes=held, seconds=1.0, name="c")
    assert a.read_bytes() == b.read_bytes() != c.read_bytes()


def test_feedback_adds_to_the_voices(renderer, tmp_path):
    _, _, a = play(renderer, tmp_path, two_op(fb=3), params=[f"Patch={USER1}", "Feedback=2"], name="a")
    _, _, b = play(renderer, tmp_path, two_op(fb=5), name="b")
    _, _, c = play(renderer, tmp_path, two_op(fb=3), params=[f"Patch={USER1}", "Feedback=-7"], name="c")
    _, _, d = play(renderer, tmp_path, two_op(fb=0), name="d")
    assert a.read_bytes() == b.read_bytes() and c.read_bytes() == d.read_bytes()


def test_volume_scales_the_output(renderer, tmp_path):
    _, a, _ = render(renderer, tmp_path, "dx7", params=[f"Patch={SINE}", "Volume=0.7"],
                     notes=["0:60:100:1"], name="a")
    _, b, _ = render(renderer, tmp_path, "dx7", params=[f"Patch={SINE}", "Volume=0.35"],
                     notes=["0:60:100:1"], name="b")
    assert rms(b, 0.2, 0.8) / rms(a, 0.2, 0.8) == pytest.approx(0.5, rel=2e-3)


def test_velocity_sensitivity(renderer, tmp_path):
    """KVS 7, velocity 127 against 40: msfa's velocity table puts them 1,072
    microsteps (25.1 dB) apart."""
    v = sine_voice(vel=7)
    _, hi, _ = play(renderer, tmp_path, v, notes=["0:69:127:1"], name="hi")
    _, lo, _ = play(renderer, tmp_path, v, notes=["0:69:40:1"], name="lo")
    assert db(rms(hi, 0.2, 0.8), rms(lo, 0.2, 0.8)) == pytest.approx(1072 / 256 * 6.0206, abs=0.15)


@pytest.mark.parametrize("ams,depth_db", [(1, 0.2588 * 96.33 * 255 / 256),
                                          (2, 0.4274 * 96.33 * 255 / 256)])
def test_amplitude_modulation_depth(renderer, tmp_path, ams, depth_db):
    """AMD 99 under a square LFO: the carrier with AMS 1 or 2 drops by that
    sensitivity's share of 96 dB (16 doublings) times AMD's 255/256 for half
    of each LFO cycle, and is untouched for the other half."""
    v = sine_voice(ams=ams)
    v.lfo_speed, v.lfo_amd, v.lfo_wave, v.lfo_sync = 20, 99, 3, 1
    _, left, _ = play(renderer, tmp_path, v, notes=["0:69:127:2"], seconds=2)
    w = peaks(left, 5)[20:]
    top, bottom = max(w), min(w)
    assert db(top, bottom) == pytest.approx(depth_db, abs=0.1)
    _, plain, _ = render(renderer, tmp_path, "dx7", params=[f"Patch={SINE}", "Volume=0.7"],
                         notes=["0:69:127:2"], seconds=2, name="plain")
    assert top == pytest.approx(max(peaks(plain, 5)[20:]), rel=1e-3)


def test_lfo_speed_follows_msfa(renderer, tmp_path):
    """LFO speed 30 under AMS 3: the tremolo's period is msfa's, 2^32 /
    (unit * sr) blocks, unit = 64 * 25,190,424 / rate rounded, sr = 11 *
    (165 * 30 >> 6)."""
    v = sine_voice(ams=3)
    v.lfo_speed, v.lfo_amd, v.lfo_wave = 30, 40, 4
    _, left, _ = play(renderer, tmp_path, v, notes=["0:69:127:4"], seconds=4)
    unit = int(64 * 25190424 / RATE + 0.5)
    sr = ((165 * 30) >> 6) * 11
    want_hz = unit * sr / 2 ** 32 * RATE / 64
    w = peaks(left, 5)[40:]
    mean = sum(w) / len(w)
    ups = [i for i in range(1, len(w)) if w[i - 1] < mean <= w[i]]
    got_hz = (len(ups) - 1) / ((ups[-1] - ups[0]) * 0.005)
    assert got_hz == pytest.approx(want_hz, rel=0.02)


def msfa_table(name):
    """A uint8_t or int8_t table from the vendored pitchenv.cc."""
    src = (MSFA / "pitchenv.cc").read_text()
    body = re.search(name + r"\[\] = \{([^}]*)\}", src).group(1)
    return [int(x) for x in re.findall(r"-?\d+", body)]


def test_pitch_envelope_glides_at_its_rate(renderer, tmp_path):
    """PL4 82 to PL1 50 (none) at R1 50: the note starts pitchtab[82] / 32
    octave up (one octave) and comes down linearly in log pitch at msfa's
    rate, ratetab[50] units of 64 * 2^24 / (21.3 * rate) per 64-sample block."""
    v = sine_voice()
    v.pitch_rates, v.pitch_levels = (50, 99, 99, 99), (50, 50, 50, 82)
    _, left, _ = play(renderer, tmp_path, v, notes=["0:57:100:1.6"], seconds=1.6)
    rates, pitches = msfa_table("ratetab"), msfa_table("pitchtab")
    unit = int(64 * 2 ** 24 / (21.3 * RATE) + 0.5)
    start = pitches[82] - pitches[50]                  # in 1/32 octave
    t_end = (start << 19) / (rates[50] * unit) * 64 / RATE
    early = cents(pitch_hz(left, 0.05, 0.05), 220.0) / 100
    want = start * 12 / 32 * (1 - 0.075 / t_end)
    assert early == pytest.approx(want, abs=0.3)
    assert abs(cents(pitch_hz(left, t_end + 0.1, 0.5), 220.0)) < 1.0


def test_lfo_delay_holds_the_vibrato_back(renderer, tmp_path):
    """LFD 70: no vibrato for the first 0.3 s (msfa's delay counts 0.73 s
    before it starts to fade in); a full one (PMD 99, PMS 4: about +-2.6
    semitones) two seconds in."""
    v = sine_voice()
    v.lfo_speed, v.lfo_delay, v.lfo_pmd, v.pms, v.lfo_wave = 50, 70, 99, 4, 4
    _, left, _ = play(renderer, tmp_path, v, notes=["0:69:100:3"], seconds=3)

    def spread(a, b):
        ps = [pitch_hz(left, a + k * 0.04, 0.04) for k in range(int((b - a) / 0.04))]
        return max(cents(p, 440.0) for p in ps) - min(cents(p, 440.0) for p in ps)
    assert spread(0.05, 0.3) < 5 and spread(2.0, 2.8) > 100


# ----------------------------------------------------------------- sysex --

def test_vced_and_a_bank_slot_play_the_same(renderer, tmp_path):
    """The same voice as a single-voice dump and packed in a bank (slot 5)
    renders the same bytes."""
    v = ORACLE_VOICES["scaling"]
    bank = [dx.bank()[i] for i in range(32)]
    bank[4] = v
    (tmp_path / "bank.syx").write_bytes(dx.vmem_syx(bank))
    _, _, a = play(renderer, tmp_path, v, name="a")
    _, _, b = play(renderer, tmp_path, None, params=[f"Patch={USER1 + 4}"], name="b",
                   files=[tmp_path / "bank.syx"])
    assert a.read_bytes() == b.read_bytes()


def test_the_builtin_bank_round_trips_through_sysex(renderer, tmp_path):
    """tools/dx7_bank.py --syx exports the built-in voices as a bank; read
    back, each user slot renders as its built-in voice, byte for byte."""
    path = tmp_path / "builtin.syx"
    subprocess.run([sys.executable, str(ROOT / "tools" / "dx7_bank.py"), "--syx", str(path)],
                   check=True)
    for k in (0, 7, 14, 21, 28, 31):
        _, _, a = render(renderer, tmp_path, "dx7", params=[f"Patch={k}"],
                         notes=["0:60:100:0.4", "0:67:90:0.4"], seconds=0.8, name="a")
        _, _, b = render(renderer, tmp_path, "dx7", params=[f"Patch={USER1 + k}"],
                         notes=["0:60:100:0.4", "0:67:90:0.4"], seconds=0.8, name="b",
                         extra=["--sysex", str(path)])
        assert a.read_bytes() == b.read_bytes(), k


def run_sysex(renderer, tmp_path, data, name="x"):
    path = tmp_path / f"{name}.syx"
    path.write_bytes(data)
    wav = tmp_path / f"{name}.wav"
    return subprocess.run([str(renderer), "--engine", "dx7", "--sysex", str(path),
                           "--param", f"Patch={USER1}", "--note", "0:60:127:0.3",
                           "--seconds", "0.4", "--out", str(wav)], capture_output=True, text=True)


def test_several_dumps_checksums_and_other_sysex(renderer, tmp_path):
    a = dx.vced_syx(ORACLE_VOICES["scaling"])
    b = bytearray(dx.vced_syx(ORACLE_VOICES["pitch-env"]))
    b[-2] ^= 0x01                                   # a wrong checksum: stored all the same
    other = bytes([0xF0, 0x41, 0x10, 0x42, 0x12, 0x00, 0xF7])    # not a DX7 dump
    r = run_sysex(renderer, tmp_path, a + other + bytes(b))
    assert r.returncode == 0
    assert '2 voices from User 1, 1 bad checksums, 1 skipped: "SCL" "PEG"' in r.stderr


def test_raw_bank_data_without_framing(renderer, tmp_path):
    data = dx.vmem_syx(dx.bank())[6:-2]
    r = run_sysex(renderer, tmp_path, data)
    assert r.returncode == 0 and '32 voices from User 1' in r.stderr and '"TINE EP"' in r.stderr


@pytest.mark.parametrize("case", ["empty", "truncated", "noise", "status-inside", "wrong-count"])
def test_broken_dumps_are_refused(renderer, tmp_path, case):
    good = dx.vced_syx(ORACLE_VOICES["scaling"])
    data = {
        "empty": b"",
        "truncated": good[:100],
        "noise": bytes((i * 37 + 11) & 0xFF for i in range(5000)),
        "status-inside": good[:50] + b"\x90" + good[51:],
        "wrong-count": good[:5] + b"\x1C" + good[6:],
    }[case]
    r = run_sysex(renderer, tmp_path, data)
    assert r.returncode != 0 and "no DX7 voice dump" in r.stderr


def test_out_of_range_values_are_clamped(renderer, tmp_path):
    """A bank whose every data byte is 0x7F (rates, levels, curves,
    algorithm, LFO wave... all past their ranges) loads, clamped, and
    plays finite sound; the names read as spaces trimmed to nothing."""
    d = [0x7F] * 4096
    data = bytes([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00] + d + [dx.checksum(d), 0xF7])
    for slot in (USER1, USER1 + 31):
        path = tmp_path / "hot.syx"
        path.write_bytes(data)
        s, _, _ = render(renderer, tmp_path, "dx7", params=[f"Patch={slot}"],
                         notes=["0:0:127:0.3", "0:127:127:0.3", "0.1:60:1:0.2"], seconds=0.5,
                         extra=["--sysex", str(path), "--bend", "0.2:48"])
        assert s["nonfinite"] == 0


def test_sysex_needs_the_fm6_engine(renderer, tmp_path):
    path = tmp_path / "v.syx"
    path.write_bytes(dx.vced_syx(sine_voice()))
    r = subprocess.run([str(renderer), "--engine", "macro", "--sysex", str(path), "--seconds", "0.1",
                        "--out", str(tmp_path / "x.wav")], capture_output=True, text=True)
    assert r.returncode != 0 and "--sysex needs --engine dx7" in r.stderr


# ----------------------------------------------------------------- voices --

@pytest.mark.parametrize("patch", range(32))
def test_every_builtin_voice_sounds(renderer, tmp_path, patch):
    """A two-note chord of each built-in voice at three velocities: finite,
    audible, under full scale before the limiter, and silent, every voice
    ended, 7 s after the release."""
    for vel in (30, 90, 127):
        s, left, _ = render(renderer, tmp_path, "dx7", params=[f"Patch={patch}"],
                            notes=[f"0:48:{vel}:0.6", f"0:55:{vel}:0.6"], seconds=8.0,
                            name=f"p{patch}-{vel}")
        assert s["nonfinite"] == 0 and s["raw_clipped"] == 0, (patch, vel)
        assert s["raw_peak"] > 0.01, (patch, vel)
        assert not any(left[int(7.6 * RATE):]), (patch, vel)


def test_builtin_names_are_unique_and_fit():
    names = [v.name for v in dx.bank()]
    assert len(names) == 32 == len(set(names)) and all(0 < len(n) <= 10 for n in names)


def test_twelve_voices_and_a_steal(renderer, tmp_path):
    """Twelve notes sound together; a thirteenth steals the oldest; a key
    played again retriggers its own voice."""
    notes = [f"0:{48 + k}:100:1.0" for k in range(12)]
    s, left, _ = render(renderer, tmp_path, "dx7", params=[f"Patch={SINE}", "Volume=0.2"],
                        notes=notes + ["0.5:80:100:0.5", "0.6:48:100:0.3"], seconds=1.4)
    assert s["nonfinite"] == 0 and s["clipped"] == 0
    assert rms(left, 0.1, 0.4) > 0.05 and rms(left, 0.7, 0.9) > 0.05


def test_retrigger_and_release(renderer, tmp_path):
    s, left, _ = render(renderer, tmp_path, "dx7", params=["Patch=0"],
                        notes=["0:60:100:0.3", "0.15:60:110:0.3"], seconds=3.0)
    assert s["nonfinite"] == 0 and rms(left, 0.2, 0.4) > 1e-3 and rms(left, 2.6, 3.0) < 1e-5


def tone(x, f, a, b):
    """The level of frequency f in x[a s .. b s], through a Hann window (so
    that a neighbour a few hertz off does not leak in)."""
    seg = x[int(a * RATE):int(b * RATE)]
    n = len(seg)
    return goertzel([v * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i, v in enumerate(seg)], f)


def hz(key):
    return 440.0 * 2 ** ((key - 69) / 12)


def slow_release_voice():
    """A sine whose release takes many seconds: a released voice that is
    still sounding."""
    return Voice("SLOWREL", 32, ops=[Op(level=99, rates=(99, 99, 99, 25), levels=(99, 99, 99, 0))]
                 + [silent()] * 5)


def test_a_steal_takes_a_released_voice_before_a_held_one(renderer, tmp_path):
    """Twelve voices, one of them (key 52) released but still sounding: a
    thirteenth note takes that one, and every held note keeps sounding."""
    keys = [48 + 2 * k for k in range(12)]
    notes = [f"0:{k}:100:{0.3 if k == 52 else 1.2}" for k in keys] + ["0.4:84:100:0.8"]
    _, left, _ = play(renderer, tmp_path, slow_release_voice(), params=[f"Patch={USER1}", "Volume=0.3"],
                      notes=notes, seconds=1.0)
    ref = tone(left, hz(48), 0.1, 0.3)
    assert tone(left, hz(52), 0.1, 0.3) == pytest.approx(ref, rel=0.05)    # all twelve sound
    for k in keys:
        level = tone(left, hz(k), 0.5, 0.9) / ref
        assert (level < 0.01) if k == 52 else (level > 0.5), (k, level)
    assert tone(left, hz(84), 0.5, 0.9) / ref > 0.5


def test_a_steal_takes_the_oldest_held_voice_and_a_key_again_its_own(renderer, tmp_path):
    """Twelve held notes, started one after another: a thirteenth takes the
    first one's voice; then a key that sounds, played again, restarts in its
    own voice and takes nobody's."""
    keys = [48 + 2 * k for k in range(12)]
    notes = [f"{0.01 * i}:{k}:100:1.5" for i, k in enumerate(keys)]
    notes += ["0.4:84:100:1.0", "0.7:60:110:0.8"]
    _, left, _ = play(renderer, tmp_path, slow_release_voice(), params=[f"Patch={USER1}", "Volume=0.3"],
                      notes=notes, seconds=1.2)
    ref = tone(left, hz(50), 0.2, 0.38)
    for k in keys:
        level = tone(left, hz(k), 0.45, 0.68) / ref
        assert (level < 0.01) if k == 48 else (level > 0.5), (k, level)
    for k in keys[1:] + [84]:                       # after the retrigger of 60
        assert tone(left, hz(k), 0.75, 1.15) / ref > 0.5, k


def test_a_tremolo_trough_does_not_end_a_release(renderer, tmp_path):
    """AMS 3 under a slow square LFO at AMD 99: the carrier is silent for the
    LFO's low half (1.1 s here), which outlasts the 50 ms after which a
    released, silent voice ends. The voice is released inside the trough;
    when the LFO comes back up, its release is still there, as the same
    voice without tremolo plays it. (Review, 2026-10-05: the voice was ended
    in the trough and the rest of its release lost.)"""
    def voice(ams):
        return Voice("AMTAIL", 32, ops=[Op(level=99, rates=(99, 99, 99, 30), levels=(99, 99, 99, 0),
                                           ams=ams)] + [silent()] * 5,
                     lfo_speed=3, lfo_amd=99, lfo_wave=3, lfo_sync=1)
    notes = ["0:69:100:0.5"]
    _, deep, _ = play(renderer, tmp_path, voice(3), notes=notes, seconds=2.4, name="deep")
    _, plain, _ = play(renderer, tmp_path, voice(0), notes=notes, seconds=2.4, name="plain")
    assert rms(deep, 0.3, 1.0) == 0.0                      # the trough: silent
    assert rms(plain, 1.2, 2.1) > 0.01
    assert rms(deep, 1.2, 2.1) == pytest.approx(rms(plain, 1.2, 2.1), rel=1e-3)


def test_a_release_that_ends_above_silence_holds(renderer, tmp_path):
    """A carrier whose L4 is above 0 holds there after its release, as on
    the keyboards: the voice keeps sounding."""
    v = Voice("HOLDREL", 32, ops=[Op(level=99, rates=(99, 99, 99, 60), levels=(99, 99, 99, 70))]
              + [silent()] * 5)
    _, left, _ = play(renderer, tmp_path, v, notes=["0:69:100:0.3"], seconds=3.0)
    held = rms(left, 1.0, 1.5)
    assert held > 0.005 and rms(left, 2.5, 3.0) == pytest.approx(held, rel=1e-3)


def test_a_patch_change_leaves_sounding_notes_alone(renderer, tmp_path):
    """Patch is read at note-on (LATCH): moving it under a held chord
    changes nothing until the next note, which plays the new voice."""
    notes = ["0:60:100:1.2", "0:64:90:1.2"]
    _, _, a = render(renderer, tmp_path, "dx7", params=["Patch=14"], notes=notes, seconds=1.0, name="a")
    _, _, b = render(renderer, tmp_path, "dx7", params=["Patch=14"], notes=notes, seconds=1.0, name="b",
                     extra=["--param-at", "0.3:Patch=31", "--param-at", "0.5:Patch=6"])
    assert a.read_bytes() == b.read_bytes()
    _, s1, _ = render(renderer, tmp_path, "dx7", params=["Patch=14"], notes=["0.5:72:100:0.4"],
                      seconds=1.0, name="c", extra=["--param-at", "0.3:Patch=31"])
    _, s2, _ = render(renderer, tmp_path, "dx7", params=["Patch=31"], notes=["0.5:72:100:0.4"],
                      seconds=1.0, name="d")
    assert s1 == s2


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    return rate, [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767 for i in range(0, len(raw), 4)]


@pytest.mark.parametrize("rate", [8000, 16000, 16384])
def test_rates_msfa_cannot_tune_are_refused(renderer, tmp_path, rate):
    """msfa's frequency table holds int32_t values up to 2^45 / rate (the
    top of an octave), which overflow at 16,384 Hz and below: the pitches
    near the top of each octave come out wrong there, so the engine refuses
    those rates rather than play out of tune. (Review, 2026-10-05: the
    floor was 8,000 Hz.)"""
    r = subprocess.run([str(renderer), "--engine", "dx7", "--rate", str(rate), "--seconds", "0.1",
                        "--out", str(tmp_path / "x.wav")], capture_output=True, text=True)
    assert r.returncode != 0 and "dx7 refused this host" in r.stderr


def test_the_lowest_rate_is_in_tune_at_an_octaves_top(renderer, tmp_path):
    """At 16,385 Hz, a fixed 1,023 Hz carrier (log2 frequency 0.998 into its
    octave, the end of msfa's table) sounds at its frequency."""
    v = Voice("TOP", 32, ops=[Op(level=99, fixed=1023.3, ratio=None, rates=(99, 99, 99, 99),
                                 levels=(99, 99, 99, 0))] + [silent()] * 5)
    wav = tmp_path / "top.wav"
    subprocess.run([str(renderer), "--engine", "dx7", "--sysex", str(syx(tmp_path, v, "top")),
                    "--param", f"Patch={USER1}", "--note", "0:60:100:1", "--rate", "16385",
                    "--seconds", "1", "--out", str(wav)], check=True, capture_output=True)
    rate, x = read_wav(wav)
    assert rate == 16385
    seg = x[int(0.2 * rate):int(0.8 * rate)]
    ups = [i - 1 + seg[i - 1] / (seg[i - 1] - seg[i]) for i in range(1, len(seg))
           if seg[i - 1] < 0 <= seg[i]]
    got = (len(ups) - 1) * rate / (ups[-1] - ups[0])
    assert abs(cents(got, 10 ** 3.01)) < 1.0


def test_instance_size_and_cost(renderer, tmp_path):
    """12 voices of msfa state, the user bank (32 x 156 bytes) and msfa's
    two 64-sample buses: under 16 KB here (64-bit). The time per block with
    twelve voices of the busiest built-in voices is recorded in
    engines/msfa.md; here it only has to stay below Macro's, the engine the
    FM-1 already runs twelve of."""
    chord = [f"0:{48 + k}:100:2" for k in range(12)]
    s, _, _ = render(renderer, tmp_path, "dx7", params=["Patch=14"], notes=chord, seconds=2.0)
    m, _, _ = render(renderer, tmp_path, "macro", notes=chord, seconds=2.0, name="m")
    assert s["instance_bytes"] < 16384
    assert s["ns_per_block"] < m["ns_per_block"]


def test_the_frequency_table_is_in_the_instance_off_the_fm1s_rate(renderer, tmp_path):
    """At 44,118 Hz the instance reads msfa's frequency table from const
    data (flash on the FM-1); at any other rate it holds its own, 1,025
    words, and says so in its size, which is what the simulator's RAM meter
    counts."""
    sizes = {}
    for rate in (RATE, 44100, 48000):
        out = subprocess.run([str(renderer), "--engine", "dx7", "--rate", str(rate), "--seconds", "0.05",
                              "--note", "0:60:100:0.04", "--out", str(tmp_path / f"{rate}.wav")],
                             check=True, capture_output=True, text=True).stdout
        sizes[rate] = json.loads(out.strip().splitlines()[-1])["instance_bytes"]
    assert sizes[44100] == sizes[48000] == sizes[RATE] + 4 * 1025
