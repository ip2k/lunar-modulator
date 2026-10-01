"""Macro, Macro Heavy and Six-Op FM against upstream Plaits (engines/reference-plaits.md).

Each of plaits::Voice's 24 engine slots is rendered twice and compared. The
reference is fm1-ref-plaits: the vendored, unmodified Voice, driven the way the
module drives it. The other side is fm1-render, through the fm1 engine that
wraps the same slot. Both link the same compiled vendored DSP, so what the
comparison checks is the wrapper layer: parameter mapping, gains, velocity,
the low-pass gate, trigger timing and re-blocking (reference-plaits.md,
"What the comparison covers").

- At Plaits' own rate (47,872.34 Hz): three (harmonics, timbre, morph) points,
  each with its own Decay, Colour and velocity, and two notes two octaves
  apart. fm1-render runs in Plaits' 12-frame blocks, and again in the FM-1's
  64-frame blocks, which must give the same bytes.
  - Engines whose OUT does not depend on the random generator must match
    sample for sample.
  - Six-Op, which renders in other blocks by design, must match closely.
  - Engines with internal randomness must match sample for sample on the
    generator's shared initial state. An fm1 render from another state must
    also match seeded upstream renders statistically.
- At the FM-1's rate (44,118 Hz, 64-frame blocks), where the wrappers run
  Plaits at its own rate and resample (fm1_resampler.h):
  - against upstream at its own rate passed through the same resampler
    (fm1-ref-plaits --host-rate), the same points and notes: within 1 LSB of
    fm1-render's output (Six-Op closely);
  - against upstream at its own rate, unresampled: pitch and envelope timing,
    which a wrong ratio, a missing resampler or a leftover pitch offset would
    move;
  - 1-, 7- and 64-frame host blocks give the same bytes, and a note mid-render
    lands on the block the resampler's pulls predict, mid-block or on a block
    boundary;
  - against the wrapper itself at 47,872.34 Hz, resampled (fm1-ref-plaits
    --resample), where upstream cannot stand in: Six-Op's own blocks,
    several notes, model changes into and out of the string machine, voices
    freed and their successors: within 2 LSB.
- The vendored files both programs compile are pinned by hash.

Negative controls check that the criteria reject a wrong engine, a wrong
parameter mapping, a mistuned or mis-enveloped voice, a wrong gain and a
wrong host rate.

    python tests/test_engines_reference_plaits.py --report        # the doc's tables
    python tests/test_engines_reference_plaits.py --calibrate     # the STAT factors
    python tests/test_engines_reference_plaits.py --sixop-sweep   # all 96 Six-Op patches
"""
import array
import collections
import concurrent.futures
import hashlib
import itertools
import json
import math
import os
import random
import re
import statistics
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.engine_helpers import ENGINES, renderer  # noqa: E402,F401  (fixture: builds engines/)

REF = ENGINES / "build" / "fm1-ref-plaits"
RENDER = ENGINES / "build" / "fm1-render"
MUTABLE = ENGINES / "third_party" / "mutable"
NATIVE = "47872.34"          # Plaits' kCorrectedSampleRate
NATIVE_HZ = 47872.34
FM1_RATE = "44118"           # the FM-1's
FM1_HZ = 44118.0
RATE_RATIO = NATIVE_HZ / FM1_HZ
RESAMPLER_DELAY = 30         # fm1_resampler.h's group delay, output samples
NOTES = (45, 69)             # A2 and A4
VELOCITY = 100               # LEVEL 100/127 on the reference; accent 0.94

Point = collections.namedtuple("Point", "harmonics timbre morph decay colour velocity")

# (harmonics, timbre, morph) form a Latin square: each knob takes 0.2, 0.5 and
# 0.8 once, each time with the other two elsewhere. (Decay, Colour) form a
# second one over the same points, and velocity takes 100, 60 and 120. (Not
# 127: LEVEL 1 makes upstream's six-op read one past lut_cube_root's end,
# plaits-heavy.md.)
POINTS = (Point(0.2, 0.5, 0.8, decay=0.2, colour=0.8, velocity=100),
          Point(0.5, 0.8, 0.2, decay=0.5, colour=0.2, velocity=60),
          Point(0.8, 0.2, 0.5, decay=0.8, colour=0.5, velocity=120))


def neutral(point, decay=0.5, colour=0.5, velocity=VELOCITY):
    """The same knobs with Decay, Colour and velocity at the values the
    statistical tests and the negative controls use."""
    return point._replace(decay=decay, colour=colour, velocity=velocity)


SECONDS = 0.6
# Note length for the models under the low-pass gate. The note-off lands on
# sample 14,400 = 75 x 192 in the reference and in fm1-render with 12- and
# with 64-frame blocks (192 = lcm(12, 64); fm1-render applies events at block
# boundaries), so the two block sizes render the same note.
GATE_SAMPLES = 14400
GATE = 0.30075               # (14,394 .. 14,400] / 47,872.34 Hz
SHARED_SEED = 0x21           # stmlib::Random's initial state, in both programs
SEEDS = (1001, 2002, 3003, 4004, 5005)   # independent upstream realisations
CALIBRATION_SEEDS = SEEDS + (6006, 7007, 8008)
STAT_SECONDS = 1.5           # held notes for the statistical comparison
# The statistical candidate: fm1-render plays a pre-note (a fifth up, velocity
# 1, two blocks) that draws from stmlib::Random and has died away before
# the candidate's note-on at STAT_LEAD samples. The candidate is therefore
# another realisation than the shared-seed one the exact test matches.
STAT_LEAD = 96000            # a multiple of 12 and 64
PRE_NOTE = (7, 1, 0.0003)    # key offset, velocity, seconds
WORKERS = min(8, os.cpu_count() or 2)

# Envelope timing at 44,118 Hz against upstream at its own rate: the same
# time base, so a stretch of 1. Running Plaits at the host's rate gave 1.085.
LPG_STRETCH = ("fit", 0.98, 1.02)


def f32(x):
    """x rounded to a 32-bit float, as a Python float."""
    return struct.unpack("f", struct.pack("f", x))[0]


class Slot:
    """One of plaits::Voice's engine slots and the fm1 engine that wraps it.

    env:  "lpg"    under the low-pass gate (released at GATE, release compared);
          "self"   self-enveloped (the note is held: the wrapper's added release
                   is not upstream behaviour, see test_added_release_after_note_off);
          "speech" LPG for vowels (harmonics <= 1/3), self-enveloped for words;
          "sixop"  Six-Op FM (its own DX7 envelopes, released at GATE);
          "chip"   Chiptune (upstream bypasses the LPG in clocked mode).
    random: indices into POINTS where OUT depends on stmlib::Random ("all").
    stat_points: the random points the statistical test uses (default: all).
    pitched: the spectral pitch shift is meaningful (a tone, not a texture).
    rate_pitch: pitch at 44,118 Hz against unresampled upstream is held to 0.
    rate_timing: (method, lo, hi) for the envelope time stretch at 44,118 Hz,
                 or None where one render per rate cannot show it.
    rate_point: the Point of the 44,118 Hz comparison with unresampled upstream.
    rate_window: (from, to) seconds of that comparison, or None (all).
    """

    def __init__(self, index, upstream, engine, model, env, random=(), stat_points=None,
                 pitched=True, rate_pitch=True, rate_timing=LPG_STRETCH,
                 rate_point=Point(0.5, 0.5, 0.5, decay=0.3, colour=0.5, velocity=VELOCITY),
                 rate_window=None):
        self.index, self.upstream, self.engine, self.model = index, upstream, engine, model
        self.env, self.pitched = env, pitched
        self.random = tuple(range(len(POINTS))) if random == "all" else tuple(random)
        self.stat_points = self.random if stat_points is None else tuple(stat_points)
        self.rate_pitch, self.rate_timing, self.rate_point = rate_pitch, rate_timing, rate_point
        self.rate_window = rate_window

    @property
    def id(self):
        return f"{self.index:02d}-{self.upstream}"

    @property
    def gain(self):
        """fm1 output per reference DAC word, at Volume 1: each wrapper voice
        is scaled by 0.25. Macro and Macro Heavy pass on the Voice's own DAC
        words, which Plaits writes inverted (x -32767). Six-Op mixes its
        SoftClip() output directly, so its sign is the opposite
        (reference-plaits.md, finding 1)."""
        return -0.25 if self.engine == "sixop" else 0.25


SLOTS = [
    Slot(0, "VirtualAnalogVCFEngine", "macro", 0, "lpg"),
    Slot(1, "PhaseDistortionEngine", "macro", 1, "lpg"),
    # Six-Op rate points: patches whose release falls 30 dB inside the
    # render at both notes (bank 1 slot 10, bank 2 slot 6, bank 3 slot 16).
    Slot(2, "SixOpEngine-bank1", "sixop", 0, "sixop", rate_timing=("slope", 0.98, 1.02),
         rate_point=Point(0.3217, 0.5, 0.5, 0.3, 0.5, VELOCITY)),
    Slot(3, "SixOpEngine-bank2", "sixop", 1, "sixop", rate_timing=("slope", 0.98, 1.02),
         rate_point=Point(0.1991, 0.5, 0.5, 0.3, 0.5, VELOCITY)),
    Slot(4, "SixOpEngine-bank3", "sixop", 2, "sixop", rate_timing=("slope", 0.98, 1.02)),
    Slot(5, "WaveTerrainEngine", "macro", 2, "lpg"),
    Slot(6, "StringMachineEngine", "macro-heavy", 0, "lpg"),
    # Chiptune at 44,118 Hz as at the native rate: Colour 1 and velocity 127
    # make the wrapper's LPG transparent once open, and only the held part is
    # compared (upstream has no LPG here).
    Slot(7, "ChiptuneEngine", "macro", 3, "chip", random=(1,), rate_timing=None,
         rate_point=Point(0.5, 0.5, 0.5, 0.3, 1.0, 127), rate_window=(0.01, GATE)),
    Slot(8, "VirtualAnalogEngine", "macro", 4, "lpg"),
    Slot(9, "WaveshapingEngine", "macro", 5, "lpg"),
    Slot(10, "FMEngine", "macro", 6, "lpg",
         rate_point=Point(0.5, 0.0, 0.5, 0.3, 0.5, VELOCITY)),
    Slot(11, "GrainEngine", "macro-heavy", 3, "lpg"),
    Slot(12, "AdditiveEngine", "macro-heavy", 4, "lpg"),
    Slot(13, "WavetableEngine", "macro", 7, "lpg"),
    # Chords, Swarm, Noise, Particle and String at 44,118 Hz: both sides draw
    # the same random numbers at the same rate on the shared seed, and the
    # chord's beating is in the same phase, so their timing and spectra are
    # held too (they were not while Plaits ran at the host's rate).
    Slot(14, "ChordEngine", "macro-heavy", 1, "lpg"),
    Slot(15, "SpeechEngine", "macro-heavy", 2, "speech"),
    Slot(16, "SwarmEngine", "macro-heavy", 5, "lpg", random="all", pitched=False),
    Slot(17, "NoiseEngine", "macro-heavy", 6, "lpg", random="all", pitched=False),
    # Particle at (0.8, 0.2, 0.5) makes one to three grains a second: upstream
    # renders of it differ so much that silence passes as one of them, so it
    # is compared sample for sample only.
    Slot(18, "ParticleEngine", "macro-heavy", 7, "lpg", random="all", stat_points=(0, 1),
         pitched=False),
    Slot(19, "StringEngine", "macro-heavy", 8, "self", random="all"),
    Slot(20, "ModalEngine", "macro-heavy", 9, "self"),
    Slot(21, "BassDrumEngine", "macro-heavy", 10, "self"),
    Slot(22, "SnareDrumEngine", "macro-heavy", 11, "self", random="all", pitched=False),
    Slot(23, "HiHatEngine", "macro-heavy", 12, "self", random="all", pitched=False),
]
BY_INDEX = {s.index: s for s in SLOTS}


# --- running the tools ------------------------------------------------------------

def _run(cmd):
    res = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if res.returncode:
        raise RuntimeError(f"{' '.join(map(str, cmd))}\n{res.stderr}")
    return json.loads(res.stdout)


def run_all(cmds):
    """Run tool invocations in parallel threads (each one its own process)."""
    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        return list(pool.map(_run, cmds))


def gate_for(slot, point, seconds=SECONDS):
    if slot.env == "self" or (slot.env == "speech" and point.harmonics * 6.0 > 2.0):
        return seconds
    return GATE


def ref_cmd(out, slot, note, point, seconds=SECONDS, gate=None, seed=None, extra=(), host=False):
    """LEVEL is the wrapper's own float, velocity / 127.0f, written in full
    (repr of the float32 value), so both sides compute the same accent. At six
    decimals 60/127 read as another float, and about 1 word in 3,000 came out
    1 off (reference-plaits.md, "Criteria"). host: the reference at the FM-1's
    rate and host block, resampled as the wrappers resample, at fm1's scale
    and polarity (slot.gain), so fm1 compares at gain 1."""
    cmd = [REF, "--engine", slot.index, "--note", note, "--harmonics", point.harmonics,
           "--timbre", point.timbre, "--morph", point.morph, "--seconds", seconds,
           "--gate", gate_for(slot, point, seconds) if gate is None else gate,
           "--level", repr(f32(point.velocity / 127)), "--colour", point.colour,
           "--decay", point.decay, "--out", out]
    if seed is not None:
        cmd += ["--seed", seed]
    if host:
        cmd += ["--host-rate", FM1_RATE, "--host-frames", 64, "--host-gain", slot.gain]
    return cmd + list(extra)


def sixop_patch(slot, harmonics):
    """The patch SixOpEngine's HARMONICS scan selects (HysteresisQuantizer2,
    32 steps, hysteresis 0.005, from a fresh state)."""
    value = harmonics * 1.02 * 32 - 0.5
    q = int(value + (-0.005 if value > 0 else 0.005) + 0.5)
    return slot.model * 32 + max(0, min(31, q))


def fm1_params(slot, point):
    if slot.engine == "sixop":
        return [f"Patch={sixop_patch(slot, point.harmonics)}", f"Brightness={point.timbre}",
                f"Envelope={point.morph}", "Volume=1"]
    return [f"Model={slot.model}", f"Harmonics={point.harmonics}", f"Timbre={point.timbre}",
            f"Morph={point.morph}", f"Decay={point.decay}", f"Colour={point.colour}", "Volume=1"]


def fm1_cmd(out, slot, key, point, rate=NATIVE, frames=12, seconds=SECONDS, gate=None,
            params=None, start=0.0, extra_notes=()):
    g = gate_for(slot, point, seconds) if gate is None else gate
    cmd = [RENDER, "--engine", slot.engine, "--rate", rate, "--frames", frames,
           "--seconds", seconds + start, "--note", f"{start:.9f}:{key}:{point.velocity}:{g}",
           "--out", out]
    for n in extra_notes:
        cmd += ["--note", n]
    for p in (params if params is not None else fm1_params(slot, point)):
        cmd += ["--param", p]
    return cmd


def cmp_cmd(ref, fm1, gain, *extra):
    return [REF, "--compare", ref, fm1, "--gain", gain, *extra]


def played_key(slot, note, info):
    """Six-Op applies each patch's transpose (DX7 C3 = 24), which Plaits
    ignores: play the key that lands on the reference's note."""
    if slot.engine == "sixop":
        return note - (info["sixop"]["transpose"] - 24)
    return note


def crop_wav(src, dst, frames):
    """dst: src without its first `frames` frames, same header."""
    with wave.open(str(src), "rb") as r:
        params = r.getparams()
        r.setpos(frames)
        data = r.readframes(r.getnframes() - frames)
    with wave.open(str(dst), "wb") as w:
        w.setparams(params)
        w.writeframes(data)


# --- criteria ------------------------------------------------------------------------

# Sample for sample. Both sides carry the Voice's own 16-bit DAC words; fm1's
# are scaled by 0.25 and rounded to 16 bits again. That rounding of word/4 is
# 0, 1/4, 1/2 or 1/4 of an fm1 LSB, a mean square of 3/32 LSB^2, which is
# 1.5 LSB^2 of the reference: RMS sqrt(1.5)/32768, -88.6 dBFS. The limit is
# -80 dBFS, 8.6 dB above it. No lag: the wrappers and the aligned reference
# put the note on the same sample. The other measures only restate that
# error in their own terms: what is left of them is the same rounding where
# the signal is quiet (windows and bands down to -70 dBFS). Their limits
# stand 1.5 to 4 times above the worst of the 132 exact cases
# (reference-plaits.md, "Criteria").
EXACT = dict(err_dbfs=-80.0, gain_db=0.01, env_max_db=0.25, pitch_cents=0.05, lsd_db=0.25)

# Six-Op runs the same fm::Voice code, with two differences by design
# (reference-plaits.md, "Six-Op"). First, it renders in 16-sample blocks from
# the note-on, where upstream renders staggered 24-sample chunks that start
# 36 samples later; envelopes and LFO step at those block rates. Second, its
# one-sample note-on renders move the free-running operator phases of
# patches without key sync on by one sample. The limits are three times the
# worst of the 18 cases compared (1 - NCC, gain, envelope, pitch, LSD);
# reference-plaits.md has those and the spread over all 96 patches.
SIXOP = dict(ncc=0.981, lag=(-40, -32), gain_db=0.35, env_max_db=0.7, pitch_cents=0.22,
             lsd_db=2.25)

# Random engines, from another generator state than upstream's. The fm1
# render joins five seeded upstream renders of the same held note as a sixth
# member, and must not be the outlier. Its median distance to the others may
# exceed the largest leave-one-out median of any upstream member by the
# factor, plus the floor. The factors are 1.5 times the largest ratio any
# genuine upstream render reached, with eight seeds in turn as the candidate
# over every statistical point (--calibrate; reference-plaits.md, "Criteria").
STAT = dict(level_db=(4.4, 0.1), env_mean_db=(2.2, 0.2), lsd_db=(2.6, 0.25),
            centroid_cents=(7.6, 5.0), shift_cents=(6.4, 5.0), pitch_cents=(2.0, 0.5))
STAT_ARGS = ("--max-lag-ms", "0", "--env-window-ms", "50", "--no-timing")

# At the FM-1's rate, against upstream through the same resampler (host_case):
# the wrappers' words are Voice's words, bit for bit, and both sides resample
# the same floats (word x 0.25 / 32,768) with the same header code and write
# them the same way, so the WAVs are expected to be identical, and are, except
# Chiptune: 23 of 76,962 samples 1 off (0.034 LSB RMS at worst), from the
# low-pass gate the wrapper keeps and upstream bypasses there. The limit is
# 1 LSB of fm1-render's 16-bit output at any sample, and 0.1 LSB RMS: room for
# a compiler that evaluates the resampler's float expressions differently in
# the two programs (contracting a multiply-add in one and not the other),
# which moves a sample by a float rounding and can flip its 16-bit rounding by
# one, never more [inferred]. Every wrapper error the comparison exists for
# moves many samples by more: a note one 12-sample block late, a gain
# 0.01 dB off (9 LSB at fm1's -12 dBFS peak), a host rate 0.04 % off
# (test_host_rate_criteria_reject).
HOST_LSB = dict(max=1, rms=0.1)
# The reference at fm1's scale is 12.04 dB below the native reference's, so
# the compare tool's quantisation floor (-80 dBFS there) moves with it.
HOST_NOISE_DBFS = -92.0

# Six-Op at 44,118 Hz: the native-rate limits, the lag window scaled by
# 44,118 / 47,872.34 (the native lag of -35 to -38 samples is -32.3 to -35.0
# at 44,118 Hz; the native window, -40 to -32, becomes -36.9 to -29.5).
SIXOP_HOST = dict(SIXOP, lag=(-37, -29))

# Pitch at 44,118 Hz against upstream at its own rate, unresampled. The engines
# run at that rate, so 0, to the measurement's resolution. A pitch offset left
# in a wrapper (141 cents), a missing resampler (-141 cents) or a resampler
# told another input rate (48 kHz: +4.6 cents) are far outside it; so is the
# pitch table's -0.37 cents that the old rate offset left on every engine.
RATE_PITCH_CENTS = 0.1


def exact_failures(c, limits=EXACT, pitched=True):
    f = []
    if c["lag"] != 0:
        f.append(f"lag {c['lag']} samples")
    if not (c["err_dbfs"] is not None and c["err_dbfs"] <= limits["err_dbfs"]):
        f.append(f"error {c['err_dbfs']} dBFS > {limits['err_dbfs']}")
    for k in ("gain_db",) + (("pitch_cents",) if pitched else ()):
        if not (c[k] is not None and abs(c[k]) <= limits[k]):
            f.append(f"{k} {c[k]}")
    for k in ("env_max_db", "lsd_db"):
        if not (c[k] is not None and c[k] <= limits[k]):
            f.append(f"{k} {c[k]}")
    return f


def sixop_failures(c, limits=SIXOP):
    f = []
    if not (c["ncc"] is not None and c["ncc"] >= limits["ncc"]):
        f.append(f"NCC {c['ncc']}")
    lo, hi = limits["lag"]
    if not lo <= c["lag"] <= hi:
        f.append(f"lag {c['lag']}")
    for k in ("gain_db", "pitch_cents"):
        if not (c[k] is not None and abs(c[k]) <= limits[k]):
            f.append(f"{k} {c[k]}")
    for k in ("env_max_db", "lsd_db"):
        if not (c[k] is not None and c[k] <= limits[k]):
            f.append(f"{k} {c[k]}")
    return f


def wav_channels(path):
    """The 16-bit samples of each channel of a WAV."""
    with wave.open(str(path), "rb") as w:
        n = w.getnchannels()
        a = array.array("h", w.readframes(w.getnframes()))
    if sys.byteorder != "little":
        a.byteswap()
    return [a[c::n] for c in range(n)]


def lsb_diff(ref, fm1, ref_ch=0, fm1_ch=0, window=None):
    """fm1 against a reference written at fm1's scale, sample for sample, in
    LSB of the 16-bit WAVs: largest and RMS difference, samples that differ,
    the reference's peak and both lengths. window: (from, to) seconds at
    44,118 Hz, else all."""
    x, y = wav_channels(ref)[ref_ch], wav_channels(fm1)[fm1_ch]
    a, b = 0, min(len(x), len(y))
    if window:
        a, b = int(window[0] * FM1_HZ), min(b, int(window[1] * FM1_HZ))
    d = [abs(p - q) for p, q in zip(x[a:b], y[a:b])]
    return dict(max=max(d) if d else None, rms=math.sqrt(sum(v * v for v in d) / len(d)) if d else None,
                differ=sum(1 for v in d if v), n=len(d), peak=max(abs(v) for v in x[a:b]) if d else 0,
                lengths=(len(x), len(y)))


def host_failures(d, limits=HOST_LSB):
    f = []
    if d["lengths"][0] != d["lengths"][1]:
        f.append(f"lengths {d['lengths']}")
    if not (d["max"] is not None and d["max"] <= limits["max"]):
        f.append(f"largest difference {d['max']} LSB")
    if not (d["rms"] is not None and d["rms"] <= limits["rms"]):
        f.append(f"RMS difference {d['rms']} LSB")
    if d["peak"] < 100:
        f.append(f"reference peak {d['peak']} LSB: too quiet to compare")
    return f


def stat_keys(slot):
    return [k for k in STAT if k != "pitch_cents" or slot.pitched]


def _dist(pairs, a, b, k):
    v = pairs[tuple(sorted((a, b)))][k]
    return None if v is None else abs(v)


def stat_measure(pairs, refs, candidate, k):
    """(the candidate's median distance to the upstream renders, the largest
    leave-one-out median of any upstream render) for measure k.

    A distance the compare tool cannot measure (null: a silent segment) puts
    the candidate infinitely far; between upstream renders it is left out,
    and an upstream render with fewer than three measurable distances gives
    no spread. The spread is None when no upstream render gives one."""
    members = list(refs) + [candidate]
    cand = [_dist(pairs, candidate, o, k) for o in refs]
    got = math.inf if any(v is None for v in cand) else statistics.median(cand)
    spreads = []
    for r in refs:
        vals = [v for v in (_dist(pairs, r, o, k) for o in members if o != r) if v is not None]
        if len(vals) >= 3:
            spreads.append(statistics.median(vals))
    return got, (max(spreads) if spreads else None)


def stat_failures(pairs, refs, candidate, keys):
    """pairs: {(a, b) sorted: compare JSON} over refs + [candidate]."""
    f, margins = [], {}
    for k in keys:
        factor, floor = STAT[k]
        got, spread = stat_measure(pairs, refs, candidate, k)
        if spread is None:
            f.append(f"{k}: upstream renders not measurable against each other")
            margins[k] = (got, math.nan)
            continue
        limit = factor * spread + floor
        margins[k] = (got, limit)
        if not got <= limit:
            f.append(f"{k}: {got:.3g} > {limit:.3g} (upstream spread {spread:.3g})")
    return f, margins


# --- the comparisons, cached per session ----------------------------------------------

_cache = {}


def _tag(*parts):
    return "_".join(str(p) for p in parts).replace(" ", "")


def native_point(slot, point):
    """Chiptune: upstream bypasses the LPG in clocked mode, the wrapper keeps
    it. At Colour 1 the LPG has no filter (hf_bleed = 1) and at velocity 127
    its gain settles to 1 within a few blocks, so from 10 ms on only the
    engine is compared (reference-plaits.md, intentional difference 7)."""
    return point._replace(colour=1.0, velocity=127) if slot.env == "chip" else point


def native_case(tmp, slot, note, point):
    """Reference (unseeded: the shared initial state) and fm1 at the native
    rate, compared; and whether fm1 in 64-frame host blocks wrote the same
    bytes as in 12-frame ones."""
    key = ("native", slot.index, note, point)
    if key in _cache:
        return _cache[key]
    point = native_point(slot, point)
    tag = _tag(slot.index, note, *point)
    ref, fm1, fm1_64 = tmp / f"ref_{tag}.wav", tmp / f"fm1_{tag}.wav", tmp / f"fm1-64_{tag}.wav"
    extra = ["--max-lag-ms", "2" if slot.engine == "sixop" else "1"]
    if slot.env == "chip":
        extra += ["--from", "0.01", "--to", GATE]
    if slot.engine == "sixop":                   # the key depends on the patch's transpose
        info = _run(ref_cmd(ref, slot, note, point))
        k = played_key(slot, note, info)
        run_all([fm1_cmd(fm1, slot, k, point), fm1_cmd(fm1_64, slot, k, point, frames=64)])
    else:
        info = run_all([ref_cmd(ref, slot, note, point), fm1_cmd(fm1, slot, note, point),
                        fm1_cmd(fm1_64, slot, note, point, frames=64)])[0]
    cmps = [cmp_cmd(ref, fm1, slot.gain, *extra)]
    if slot.engine == "macro-heavy" and slot.model == 0:     # string machine: AUX is R
        cmps.append(cmp_cmd(ref, fm1, slot.gain, *extra, "--ref-channel", 1, "--fm1-channel", 1))
    same_64 = fm1.read_bytes() == fm1_64.read_bytes()
    _cache[key] = (info, run_all(cmps), same_64)
    return _cache[key]


def host_case(tmp, slot, note, point):
    """fm1 at 44,118 Hz in 64-frame blocks against the reference resampled to
    44,118 Hz the same way (unseeded: the shared initial state): per channel
    compared, {"lsb": lsb_diff} for the exact slots, {"cmp": compare JSON}
    for Six-Op."""
    key = ("host", slot.index, note, point)
    if key in _cache:
        return _cache[key]
    point = native_point(slot, point)
    tag = _tag("host", slot.index, note, *point)
    ref, fm1 = tmp / f"ref_{tag}.wav", tmp / f"fm1_{tag}.wav"
    if slot.engine == "sixop":
        info = _run(ref_cmd(ref, slot, note, point, host=True))
        _run(fm1_cmd(fm1, slot, played_key(slot, note, info), point, rate=FM1_RATE, frames=64))
        # A lag search of +/-1 ms: the expected lag (-29 to -37) is well inside
        # it, and +/-2 ms reaches the next period of A4 (100 samples), which
        # can correlate better by a hair (an A4 case read +67).
        res = [{"cmp": _run(cmp_cmd(ref, fm1, 1, "--max-lag-ms", "1",
                                    "--noise-dbfs", HOST_NOISE_DBFS))}]
    else:
        info = run_all([ref_cmd(ref, slot, note, point, host=True),
                        fm1_cmd(fm1, slot, note, point, rate=FM1_RATE, frames=64)])[0]
        window = (0.01, GATE) if slot.env == "chip" else None
        channels = [(0, 0)] + ([(1, 1)] if slot.engine == "macro-heavy" and slot.model == 0 else [])
        res = [{"lsb": lsb_diff(ref, fm1, r, f, window)} for r, f in channels]
    _cache[key] = (info, res)
    return _cache[key]


def stat_members(tmp, slot, note, point, seeds=SEEDS):
    """Seeded upstream renders of a held note (cached)."""
    refs, cmds = [], []
    for s in seeds:
        r = tmp / f"seed{s}_{_tag(slot.index, note, *point)}.wav"
        refs.append(r)
        if not r.exists():
            cmds.append(ref_cmd(r, slot, note, point, seconds=STAT_SECONDS, gate=STAT_SECONDS,
                                seed=s))
    run_all(cmds)
    return refs


def stat_candidate_cmd(out, slot, key, point, params=None):
    """fm1 render of the held note, preceded by the pre-note (STAT_LEAD)."""
    offset, velocity, length = PRE_NOTE
    start = (STAT_LEAD - 0.5) / NATIVE_HZ
    return fm1_cmd(out, slot, key, point, seconds=STAT_SECONDS, gate=STAT_SECONDS, params=params,
                   start=start, extra_notes=[f"0:{key + offset}:{velocity}:{length}"])


def stat_candidate(tmp, slot, note, point, name, key_offset=0, params=None):
    tag = _tag(name, slot.index, note, *point)
    full, cand = tmp / f"statfull_{tag}.wav", tmp / f"stat_{tag}.wav"
    if not cand.exists():
        _run(stat_candidate_cmd(full, slot, note + key_offset, point, params))
        crop_wav(full, cand, STAT_LEAD)
    return cand


def stat_case(tmp, slot, note, point, name="fm1", key_offset=0, params=None):
    """The candidate's comparisons with five seeded upstream renders, and
    theirs with each other; and the candidate against the unseeded (shared
    seed) reference, to show it is another realisation."""
    key = ("stat", name, slot.index, note, point)
    if key in _cache:
        return _cache[key]
    point = neutral(point)
    refs = stat_members(tmp, slot, note, point)
    cand = stat_candidate(tmp, slot, note, point, name, key_offset, params)
    shared = tmp / f"shared_{_tag(slot.index, note, *point)}.wav"
    if not shared.exists():
        _run(ref_cmd(shared, slot, note, point, seconds=STAT_SECONDS, gate=STAT_SECONDS))
    pairs, cmds = [], []
    for a, b in itertools.combinations(refs + [cand], 2):
        pairs.append(tuple(sorted((a, b))))
        if cand in (a, b):
            r = b if a == cand else a
            cmds.append(cmp_cmd(r, cand, slot.gain, *STAT_ARGS))
        else:
            cmds.append(cmp_cmd(a, b, 1, *STAT_ARGS))
    cmds.append(cmp_cmd(shared, cand, slot.gain, "--max-lag-ms", "0", "--no-timing"))
    res = run_all(cmds)
    _cache[key] = (dict(zip(pairs, res[:-1])), refs, cand, res[-1])
    return _cache[key]


# --- when the wrappers render, at the FM-1's rate ---------------------------------------

SPAN = 12                    # fm1_resampler.h's kernel width, intermediate samples


def resampler_constants(in_rate=NATIVE_HZ, out_rate=FM1_HZ):
    """fm1_resampler_init's step and lead (32.32 fixed point), from the rates
    as 32-bit floats, in the same double arithmetic."""
    ratio = f32(in_rate) / f32(out_rate)
    rho = 2.0 / ratio
    step = int(ratio / 2.0 * 4294967296.0 + 0.5)
    return step, step + int(SPAN / (2.0 * rho) * 4294967296.0 + 0.5) + (1 << 32)


def inputs_pulled(outputs):
    """The 47,872.34 Hz samples a wrapper's resampler has pulled once it has
    made `outputs` samples at 44,118 Hz: output j needs ceil((2 j step +
    lead) / 2^32) of them."""
    if outputs == 0:
        return 0
    step, lead = resampler_constants()
    return -(-(2 * (outputs - 1) * step + lead) >> 32)


def host_event_sample(t, frames=64):
    """The host sample at which fm1-render applies an event at time t: the
    first block start at or after it."""
    pos = 0
    while not t <= pos / FM1_HZ:
        pos += frames
    return pos


def native_event_sample(t, block=12, frames=64):
    """The 47,872.34 Hz sample at which a wrapper with `block`-sample blocks
    acts on an event fm1-render sends at time t: the start of the first block
    not yet rendered by then."""
    return block * -(-inputs_pulled(host_event_sample(t, frames)) // block)


def rate_case(tmp, slot, note):
    """fm1 at 44,118 Hz in 64-frame blocks against the native reference,
    unresampled, one second, Decay 0.3 so an LPG release ends inside it.
    Aligned in time, so that what is left is rate and pitch: fm1 less the
    resampler's 30-sample group delay (its first 30 frames cropped), and the
    reference's note-off on the 12-sample block where the wrapper's lands
    (for Six-Op, the first one at or after its 16-sample block's start).
    Timing is measured from the note-off for released models, from the
    note-on for held ones."""
    key = ("rate", slot.index, note)
    if key in _cache:
        return _cache[key]
    point, seconds = slot.rate_point, 1.0
    gate = gate_for(slot, point, seconds)
    ref_gate = gate
    if gate < seconds:
        off = native_event_sample(gate, block=16 if slot.engine == "sixop" else 12)
        ref_gate = 12 * -(-off // 12) / NATIVE_HZ
    tag = _tag("rate", slot.index, note)
    ref, full, fm1 = tmp / f"ref_{tag}.wav", tmp / f"fm1full_{tag}.wav", tmp / f"fm1_{tag}.wav"
    info = _run(ref_cmd(ref, slot, note, point, seconds=seconds, gate=ref_gate))
    _run(fm1_cmd(full, slot, played_key(slot, note, info), point, rate=FM1_RATE, frames=64,
                 seconds=seconds, gate=gate))
    crop_wav(full, fm1, RESAMPLER_DELAY)
    t0 = 0.0 if gate >= seconds else ref_gate
    extra = ["--t0", t0]
    if slot.rate_window:
        extra += ["--from", slot.rate_window[0], "--to", slot.rate_window[1]]
    _cache[key] = _run(cmp_cmd(ref, fm1, slot.gain, *extra))
    return _cache[key]


def rate_stretch(slot, c):
    method = slot.rate_timing[0]
    return c["stretch"] if method == "fit" else c["slope_stretch"]


@pytest.fixture(scope="module")
def wavs(renderer, tmp_path_factory):  # noqa: F811
    assert REF.exists(), "make -C engines builds fm1-ref-plaits (mk/ref-plaits.mk)"
    return tmp_path_factory.mktemp("reference-plaits")


# --- mapping ---------------------------------------------------------------------------

def test_every_upstream_slot_is_mapped_once(wavs):
    assert [s.index for s in SLOTS] == list(range(24))
    pairs = [(s.engine, s.model) for s in SLOTS]
    assert len(set(pairs)) == 24
    assert sorted(m for e, m in pairs if e == "macro") == list(range(8))
    assert sorted(m for e, m in pairs if e == "macro-heavy") == list(range(13))
    assert sorted(m for e, m in pairs if e == "sixop") == [0, 1, 2]
    listing = {e["id"]: e for e in json.loads(subprocess.run(
        [str(RENDER), "--list"], check=True, capture_output=True, text=True).stdout)}
    for engine, count in (("macro", 8), ("macro-heavy", 13)):
        model = next(p for p in listing[engine]["params"] if p["name"] == "Model")
        assert model["max"] == count - 1
    infos = run_all([[REF, "--engine", s.index, "--seconds", "0.01"] for s in SLOTS])
    for s, info in zip(SLOTS, infos):
        assert info["engine_name"].replace(" bank ", "-bank") == s.upstream
        assert info["active_engine"] == s.index


def test_sixop_patch_scan_maps_to_patch_names(wavs):
    """The patch HARMONICS selects upstream, as the reference reports it, is
    the Patch entry of the same name in mi_sixop.cc, for all 96 patches."""
    src = (ENGINES / "src" / "mi_sixop.cc").read_text()
    table = src[src.index("kPatchNames[kNumPatches] = {"):]
    names = re.findall(r'"((?:[^"\\]|\\.)*)"', table[:table.index("};")])
    cmds = []
    for s in SLOTS[2:5]:
        for slot in range(32):
            cmds.append([REF, "--engine", s.index, "--harmonics", f"{(slot + 0.5) / 32.64:.6f}",
                         "--seconds", "0.01"])
    for info in run_all(cmds):
        p = info["sixop"]
        assert names[p["patch"]] == f"{p['bank'] + 1} {p['name']}"
        assert p["patch"] == sixop_patch(BY_INDEX[2 + p["bank"]], info["harmonics"])


# --- the vendored code both sides compile ---------------------------------------------------

def vendored_closure():
    """third_party/mutable files fm1-ref-plaits compiles (mk/ref-plaits.mk's
    list) and every file they, the reference and the three wrappers include,
    followed recursively. Includes that do not resolve (ARM-only headers)
    are skipped."""
    mk = (ENGINES / "mk" / "ref-plaits.mk").read_text()
    todo = re.findall(r"(\S+\.cc)", mk[mk.index("REF_PLAITS_TP :="):mk.index("REF_PLAITS_OBJ")])
    for ours in ("test/ref_plaits.cc", "src/mi_macro.cc", "src/mi_macro_heavy.cc", "src/mi_sixop.cc"):
        todo += re.findall(r'#include\s+"([^"]+)"', (ENGINES / ours).read_text())
    seen = set()
    while todo:
        rel = todo.pop()
        if rel in seen or not (MUTABLE / rel).is_file():
            continue
        seen.add(rel)
        todo += re.findall(r'#include\s+"([^"]+)"', (MUTABLE / rel).read_text(errors="replace"))
    return sorted(seen)


def vendored_digest(files):
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode() + b"\0" + hashlib.sha256((MUTABLE / rel).read_bytes()).digest())
    return h.hexdigest()


# SHA-256 over (path, SHA-256 of contents) of vendored_closure(): the files as
# vendored from eurorack 08460a69 and stmlib e3bd7c9c, byte-identical to local
# checkouts of those commits (reference-plaits.md, "What the comparison covers").
VENDORED_FILES = 129
VENDORED_DIGEST = "28654e0480717756681e0cb219f4850dfa7b3856198b7686f8e7eb20dbdf8165"


def test_vendored_plaits_code_is_pinned(wavs):
    """fm1-ref-plaits and fm1-render link the same compiled vendored DSP, so a
    local change to it moves both sides together and no render comparison
    can see it. The files are pinned here instead: a re-vendor at a new
    upstream commit updates the digest; nothing else should."""
    files = vendored_closure()
    assert (len(files), vendored_digest(files)) == (VENDORED_FILES, VENDORED_DIGEST), (
        "third_party/mutable differs from the pinned upstream files that the Plaits "
        "reference comparison relies on; UPSTREAM.md says they carry no local changes")


# --- native rate ---------------------------------------------------------------------------

@pytest.mark.parametrize("slot", SLOTS, ids=lambda s: s.id)
def test_matches_upstream_at_the_native_rate(wavs, slot):
    """Sample for sample (Six-Op closely), random points included, on the
    shared seed. Chiptune from 10 ms, past the LPG's attack."""
    failures = []
    for note in NOTES:
        for point in POINTS:
            _, res, _ = native_case(wavs, slot, note, point)
            for ch, c in enumerate(res):
                f = (sixop_failures(c) if slot.engine == "sixop"
                     else exact_failures(c, pitched=slot.pitched))
                failures += [f"note {note} {tuple(point)} ch{ch}: {x}" for x in f]
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("slot", SLOTS, ids=lambda s: s.id)
def test_64_frame_host_blocks_render_the_same_bytes(wavs, slot):
    """The wrappers render in 12-sample blocks (Six-Op 16) and buffer them
    out to whatever the host asks for. In the FM-1's 64-frame blocks every
    host block ends mid-block, and the render must still be byte-identical
    to the 12-frame one the exact comparison uses (note-off on sample
    14,400, a block boundary for both)."""
    bad = [f"note {note} {tuple(point)}" for note in NOTES for point in POINTS
           if not native_case(wavs, slot, note, point)[2]]
    assert not bad, "64-frame render differs: " + ", ".join(bad)


# Chiptune's randomness is which note of the arpeggio plays first (random
# mode, TIMBRE 0.8): a discrete choice, not a distribution to compare, so it
# is checked on the shared seed only.
STAT_SLOTS = [s for s in SLOTS if s.random and s.env != "chip"]


@pytest.mark.parametrize("slot", STAT_SLOTS, ids=lambda s: s.id)
def test_random_engines_match_seeded_upstream_statistically(wavs, slot):
    """An fm1 render from another generator state than the shared seed's is
    no outlier among upstream renders with five other seeds. Measures:
    level, envelope in 50 ms windows, band spectrum, spectral centroid,
    spectral-envelope shift, and pitch for the string."""
    failures = []
    for note in NOTES:
        for i in slot.stat_points:
            pairs, refs, cand, shared = stat_case(wavs, slot, note, POINTS[i])
            # the premise: not the shared-seed realisation the exact test matches
            if not (shared["err_dbfs"] is not None and shared["err_dbfs"] > -60.0):
                failures.append(f"note {note} {POINTS[i][:3]}: the candidate is the shared-seed "
                                f"realisation (error {shared['err_dbfs']} dBFS)")
            f, _ = stat_failures(pairs, refs, cand, stat_keys(slot))
            failures += [f"note {note} {POINTS[i][:3]}: {x}" for x in f]
    assert not failures, "\n".join(failures)


def test_shared_seed_is_stmlibs_initial_state(wavs):
    """The reference seeded with 0x21 renders what it renders unseeded, and
    another seed renders something else. Both programs start the one global
    generator at 0x21 and draw from it in the same order, which is why the
    random engines also match sample for sample."""
    slot = BY_INDEX[17]
    a, b, c = wavs / "seed_default.wav", wavs / "seed_21.wav", wavs / "seed_other.wav"
    run_all([ref_cmd(a, slot, 57, POINTS[0]), ref_cmd(b, slot, 57, POINTS[0], seed=SHARED_SEED),
             ref_cmd(c, slot, 57, POINTS[0], seed=SEEDS[0])])
    assert a.read_bytes() == b.read_bytes()
    assert a.read_bytes() != c.read_bytes()


def test_statistical_criteria_reject_silence_and_noise(wavs, tmp_path):
    """The statistical criteria reject a silent candidate (every measure is
    then unmeasurable: infinitely far) and white noise at the candidate's
    level, at every statistical point."""
    passed = []
    for slot in STAT_SLOTS:
        for note in NOTES:
            for i in slot.stat_points:
                _, refs, cand, _ = stat_case(wavs, slot, note, POINTS[i])
                with wave.open(str(cand), "rb") as w:
                    params, raw = w.getparams(), w.readframes(w.getnframes())
                xs = [int.from_bytes(raw[j:j + 2], "little", signed=True) for j in range(0, len(raw), 4)]
                level = math.sqrt(sum(x * x for x in xs) / len(xs))
                rnd = random.Random(slot.index * 1000 + note + i)
                for name, frames in (("silence", [0] * len(xs)),
                                     ("noise", [max(-32768, min(32767, int(rnd.gauss(0, level))))
                                                for _ in xs])):
                    path = tmp_path / f"{name}_{slot.index}_{note}_{i}.wav"
                    with wave.open(str(path), "wb") as w:
                        w.setparams(params)
                        w.writeframes(b"".join(x.to_bytes(2, "little", signed=True) * 2
                                               for x in frames))
                    pairs = {}
                    others = list(refs)
                    res = run_all([cmp_cmd(r, path, slot.gain, *STAT_ARGS) for r in others])
                    for r, c in zip(others, res):
                        pairs[tuple(sorted((r, path)))] = c
                    base = stat_case(wavs, slot, note, POINTS[i])[0]
                    for (a, b), c in base.items():
                        if cand not in (a, b):
                            pairs[(a, b)] = c
                    if not stat_failures(pairs, refs, path, stat_keys(slot))[0]:
                        passed.append(f"{slot.id} note {note} {POINTS[i][:3]} {name}")
    assert not passed, "passed as upstream: " + ", ".join(passed)


# --- the FM-1's rate --------------------------------------------------------------------------

@pytest.mark.parametrize("slot", SLOTS, ids=lambda s: s.id)
def test_matches_upstream_resampled_at_the_fm1_rate(wavs, slot):
    """At 44,118 Hz in 64-frame host blocks, every slot at every native-rate
    point and note, against upstream at its own rate passed through the same
    resampler: within 1 LSB (HOST_LSB; Six-Op closely, SIXOP_HOST), random
    points included, on the shared seed. Chiptune from 10 ms to the note-off,
    as at the native rate. A wrong ratio, a missing resampler, a leftover
    pitch offset or every event a block early or late all fail it. An event
    placed by the wrong rule only where the pulls end on a block boundary is
    left to test_note_lands_on_the_next_native_block and the comparisons with
    the wrapper's own native-rate output, whose events fall there too. A
    resampler per voice passes (it is linear: test_instance_sizes_are_bounded
    and test_instance_sizes_are_reported catch that)."""
    failures = []
    for note in NOTES:
        for point in POINTS:
            _, res = host_case(wavs, slot, note, point)
            for ch, r in enumerate(res):
                f = (sixop_failures(r["cmp"], SIXOP_HOST) if "cmp" in r else host_failures(r["lsb"]))
                failures += [f"note {note} {tuple(point)} ch{ch}: {x}" for x in f]
    assert not failures, "\n".join(failures)


def test_gate_lands_on_a_common_block_boundary():
    """GATE puts the note-off on sample GATE_SAMPLES in the reference (TRIG
    and LEVEL fall on block round(GATE * rate / 12)) and in fm1-render with
    12- and 64-frame blocks (the first block starting at or after GATE, at
    its float rate), so native_case's two block sizes render the same note."""
    rate_f = f32(NATIVE_HZ)
    assert GATE_SAMPLES % 192 == 0
    assert int(GATE * NATIVE_HZ / 12 + 0.5) * 12 == GATE_SAMPLES
    for frames in (12, 64):
        pos = 0
        while pos / rate_f < GATE:
            pos += frames
        assert pos == GATE_SAMPLES, frames


@pytest.mark.parametrize("slot", [s for s in SLOTS if s.rate_pitch], ids=lambda s: s.id)
def test_fm1_rate_pitch_matches_upstream(wavs, slot):
    """Pitch at 44,118 Hz against upstream at its own rate, unresampled, is 0
    within RATE_PITCH_CENTS: the engines run at Plaits' rate. (Until
    2026-10-01 they ran at the host's with a pitch offset, which left every
    Plaits engine 0.37 cents flat and the string model 9.5 cents flat at A2.)"""
    failures = []
    for note in NOTES:
        c = rate_case(wavs, slot, note)
        if not (c["pitch_cents"] is not None and abs(c["pitch_cents"]) <= RATE_PITCH_CENTS):
            failures.append(f"note {note}: pitch {c['pitch_cents']} cents")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("slot", [s for s in SLOTS if s.rate_timing], ids=lambda s: s.id)
def test_fm1_rate_envelope_timing_matches_upstream(wavs, slot):
    """Envelopes at 44,118 Hz run as long as upstream's at its own rate: a
    time stretch of 1 within 0.02 after the note-off (or note-on), by
    envelope fit, or for Six-Op's fast DX7 releases by decay-rate ratio.
    Running Plaits at the host's rate gave 1.085 for everything set per
    sample or per block."""
    method, lo, hi = slot.rate_timing
    failures = []
    for note in NOTES:
        c = rate_case(wavs, slot, note)
        s = rate_stretch(slot, c)
        if not (s is not None and lo <= s <= hi):
            failures.append(f"note {note}: {method} stretch {s} not in [{lo:.3f}, {hi:.3f}]")
    assert not failures, "\n".join(failures)


def test_noise_clock_follows_the_rate(wavs):
    """The filtered-noise model's spectrum at 44,118 Hz, against upstream's
    at its own rate: TIMBRE 0.5 puts its clock (sample-and-hold noise) in
    the audio band. The shift of the spectral envelope, median against five
    seeded upstream renders of a held note, is near 0. (It was -139 and -140
    cents at A2 and A4 while Plaits ran at the host's rate, a strict xfail:
    the clock is NoteToFrequency(TIMBRE), which the pitch offset missed;
    reference-plaits.md, finding 2.)"""
    slot = BY_INDEX[17]
    shifts = _noise_clock_shifts(wavs, slot, Point(0.5, 0.5, 0.2, 0.5, 0.5, VELOCITY))
    assert all(abs(s) < 20.0 for s in shifts), shifts


def test_noise_filter_follows_the_rate(wavs):
    """The same model with the clock at the top of its range (TIMBRE 1):
    then the note-tracking filter shapes the spectrum, and it is on pitch at
    44,118 Hz."""
    slot = BY_INDEX[17]
    shifts = _noise_clock_shifts(wavs, slot, Point(0.5, 1.0, 0.8, 0.5, 0.5, VELOCITY))
    assert all(abs(s) < 20.0 for s in shifts), shifts


def _noise_clock_shifts(tmp, slot, point):
    out = []
    for note in NOTES:
        refs = stat_members(tmp, slot, note, point)
        f44 = tmp / f"noise44_{_tag(note, *point)}.wav"
        _run(fm1_cmd(f44, slot, note, point, rate=FM1_RATE, frames=64, seconds=STAT_SECONDS,
                     gate=STAT_SECONDS))
        res = run_all([cmp_cmd(r, f44, slot.gain, "--no-timing", "--pitch-hi", "4000")
                       for r in refs])
        out.append(statistics.median(c["shift_cents"] for c in res))
    return out


# One slot per engine and wrapper path: an LPG model, the stereo string
# machine, a random LPG model, the random self-enveloped string, Six-Op.
BLOCK_SLOTS = [BY_INDEX[i] for i in (0, 6, 17, 19, 3)]


@pytest.mark.parametrize("slot", BLOCK_SLOTS, ids=lambda s: s.id)
def test_fm1_rate_output_does_not_depend_on_the_host_block(wavs, slot):
    """At 44,118 Hz, 1, 7 and 64 frames per render call write the same bytes:
    the resampler pulls the 47,872.34 Hz blocks as each output sample needs
    them. A note at 0, a second at host sample 4,480 and the first's note-off
    at 8,960, which all three block sizes reach exactly; 0.3 s (13,235
    frames, an odd total)."""
    t1, t2 = (4480 - 0.5) / FM1_HZ, (8960 - 0.5) / FM1_HZ
    point = POINTS[0]
    renders = []
    for frames in (1, 7, 64):
        out = wavs / f"blocks_{slot.index}_{frames}.wav"
        cmd = fm1_cmd(out, slot, 57, point, rate=FM1_RATE, frames=frames, seconds=0.3, gate=t2,
                      extra_notes=[f"{t1:.9f}:64:90:100"])
        renders.append(cmd)
    run_all(renders)
    data = [(wavs / f"blocks_{slot.index}_{f}.wav").read_bytes() for f in (1, 7, 64)]
    assert len(wav_channels(wavs / f"blocks_{slot.index}_64.wav")[0]) == 13235
    assert data[1] == data[0] and data[2] == data[0]


# (time of the note, host sample it arrives before, 47,872.34 Hz samples
# pulled by then, the block it starts on, arrival to onset in output samples)
LATE_NOTES = {
    # Mid-block: 2,435 pulled, so the next block starts at 2,436.
    "mid-block": (0.0503, 2240, 2435, 2436, 34.96),
    # 768 pulled, a multiple of 12 (and of 16): the last block is just used
    # up, and the next one, not yet rendered, starts on that very sample. A
    # wrapper that rendered its next block as soon as the last ran out would
    # start the note a block later here, and nowhere else.
    "block-boundary": (703.5 / FM1_HZ, 704, 768, 768, 33.77),
}


@pytest.mark.parametrize("case", LATE_NOTES)
@pytest.mark.parametrize("index", [8, 21])
def test_note_lands_on_the_next_native_block(wavs, index, case):
    """A note reaches the wrapper before a host sample (2,240 = 35 x 64 for
    the note at 0.0503 s). By then the resampler has pulled some samples at
    47,872.34 Hz (2,435: inputs_pulled, from fm1_resampler_init's
    arithmetic), so the voice starts on the first 12-sample block not yet
    rendered (2,436). The reference finds the same block by a dry run of the
    resampler itself, and the two renders agree within HOST_LSB. Nothing
    before the arrival + the outputs that cannot yet read the block is
    anything but silence. The onset is centred 2,436 x 44,118 / 47,872.34
    + 30 = 2,274.96 output samples in, 34.96 (0.79 ms) after the note's
    arrival. Where the pulls end on a block boundary (704: 768 pulled) the
    note starts on that boundary, which a block rendered ahead of need
    would miss."""
    slot = BY_INDEX[index]
    point = neutral(POINTS[0])
    t, *expected, latency = LATE_NOTES[case]
    arrival = host_event_sample(t)
    start = native_event_sample(t)
    assert [arrival, inputs_pulled(arrival), start] == expected
    ref, fm1 = wavs / f"late_ref_{index}_{case}.wav", wavs / f"late_fm1_{index}_{case}.wav"
    info, _ = run_all([ref_cmd(ref, slot, 57, point, seconds=0.1 + t, gate=100, host=True,
                               extra=["--at", t]),
                       fm1_cmd(fm1, slot, 57, point, rate=FM1_RATE, frames=64, seconds=0.1,
                               gate=100, start=t)])
    assert info["host"]["on_block"] * 12 == start
    assert not host_failures(lsb_diff(ref, fm1)), lsb_diff(ref, fm1)
    # The first output whose inputs reach sample `start` (2,436): before it,
    # no output reads the note's block at all.
    first = next(k for k in range(arrival, arrival + 64) if inputs_pulled(k + 1) > start)
    got = wav_channels(fm1)[0]
    assert not any(got[:first]) and any(got[first:first + 64])
    onset = start * FM1_HZ / NATIVE_HZ + RESAMPLER_DELAY
    assert onset - arrival == pytest.approx(latency, abs=0.01)


@pytest.mark.parametrize("engine", ["macro", "macro-heavy", "sixop"])
@pytest.mark.parametrize("rate,accepted", [("47872.34", True), ("47873", False), ("48000", False),
                                           ("44100", True), ("11968.09", True),
                                           ("11968.08", False)])
def test_refuses_host_rates_the_resampler_cannot_serve(wavs, engine, rate, accepted):
    """The resampler converts down, by 1 to 4: hosts above 47,872.34 Hz, or
    below a quarter of it (11,968.085 Hz as a float), are refused, as Shapes
    refuses those outside 24-96 kHz (create returns NULL)."""
    res = subprocess.run([str(RENDER), "--engine", engine, "--note", "0:57:100:0.05",
                          "--rate", rate, "--seconds", "0.05", "--out", str(wavs / "refuse.wav")],
                         capture_output=True, text=True)
    assert (res.returncode == 0) == accepted, res.stderr
    if not accepted:
        assert "refused this host" in res.stderr


HOST_NEGATIVE = {
    # name: (slot, fm1 rate, fm1 parameters (None: the right ones), reference
    # extra args, fm1 seconds)
    # At 44,100 Hz, 26,470.5 / 44,100 s gives the reference's 26,470 frames
    # (0.6 s at 44,118 Hz), so the two are compared sample for sample over
    # the same length and the content has to fail, not the length.
    "fm1-at-44100-hz": (8, "44100", None, (), 26470.5 / 44100),
    "volume-0.99": (13, FM1_RATE, ["Model=7", "Harmonics=0.5", "Timbre=0.8", "Morph=0.2",
                                   "Volume=0.99"], (), SECONDS),
    "note-off-in-7-frame-blocks": (8, FM1_RATE, None, ("--host-frames", "7"), SECONDS),
    "noise-one-semitone-sharp": (17, FM1_RATE, None, (), SECONDS),
}


def host_negative_failures(tmp, name):
    index, rate, params, extra, seconds = HOST_NEGATIVE[name]
    slot = BY_INDEX[index]
    point, note = neutral(POINTS[1]), 57
    ref, fm1 = tmp / f"hneg_ref_{name}.wav", tmp / f"hneg_fm1_{name}.wav"
    key = note + 1 if name == "noise-one-semitone-sharp" else note
    _run(ref_cmd(ref, slot, note, point, host=True, extra=extra))
    _run(fm1_cmd(fm1, slot, key, point, rate=rate, frames=64, seconds=seconds, params=params))
    d = lsb_diff(ref, fm1)
    return host_failures(d), d


@pytest.mark.parametrize("name", HOST_NEGATIVE)
def test_host_rate_criteria_reject(wavs, name):
    """Each deliberate error fails the 44,118 Hz criteria on the samples
    themselves (the largest or RMS difference), not on the length alone:
    the wrapper at 44,100 Hz (a ratio 0.04 % off, rendered to the
    reference's length and compared sample for sample whatever the header
    says), Volume 0.99, the note-off a few blocks early, the random noise
    model a semitone sharp."""
    f, d = host_negative_failures(wavs, name)
    assert d["lengths"][0] == d["lengths"][1], d
    assert [x for x in f if not x.startswith("lengths")], f"{name} passed: {d}"


# --- the wrappers at 44,118 Hz against themselves at 47,872.34 Hz --------------------------
#
# Upstream cannot stand in for a wrapper everywhere: Six-Op renders its own
# 16-sample blocks, not SixOpEngine's staggered chunks, and Plaits' Voice
# plays one note and never changes model. There the wrapper at 44,118 Hz is
# held against itself at 47,872.34 Hz, where its resampler passes the mix
# through bit for bit (1-frame host blocks, every event placed on the block
# the 44,118 Hz render acts on it in), resampled by fm1-ref-plaits
# --resample with fm1_resampler.h, one resampler per channel. That holds the
# whole host-rate path to what the wrapper does at its own rate: which block
# an event lands on, polyphony and retriggers, model changes, and when
# voices are freed.

# The native render is written as 16-bit words, so the resampled side
# carries their rounding: at most half an LSB per input sample, 0.29 LSB RMS.
# Through the resampler at 47,872.34 -> 44,118 Hz (L1 gain at most 2.13 over
# its output phases, L2 gain 0.90 [verified: impulse responses of
# fm1_resampler.h, a scratch program]) that moves a resampled sample by at
# most 1.07 LSB, 0.26 LSB RMS, before both sides round to 16 bits. Two values
# 1.07 apart round at most 2 apart; 0.26 LSB RMS apart they round one apart
# with a probability of about 0.21, 0.46 LSB RMS where the signal never rests
# [inferred]. Measured: 1 LSB at most, 0.31-0.45 LSB RMS. What these cases
# exist for moves far more: an event one block late, the string machine's
# AUX cut at a model change, or a voice freed 12 blocks early, 1,000 to
# 9,000 LSB (reference-plaits.md, "Review").
SELF_LSB = dict(max=2, rms=0.5)

# name: (engine, parameters, notes as (key, host sample the note-on arrives
# before, the note-off's), parameter changes as (host sample, NAME=VALUE),
# seconds). Every arrival is a 64-frame block start. 704, 6,720, 9,728,
# 12,736 and 15,744 have pulled a multiple of 48 samples at 47,872.34 Hz
# (768, 7,296, 10,560, 13,824, 17,088), so the last 12- or 16-sample block
# has just been used up and the event starts the next one on that sample; a
# wrapper that rendered its next block as soon as the last ran out would
# put those a block late at 44,118 Hz, and every event at 47,872.34 Hz. The
# others fall mid-block.
_TWO_NOTES = [(57, 704, 6720), (64, 2240, 12800), (57, 9728, 15744)]
SELF_CASES = {
    # Two overlapping notes, and the first key played again 3,000 host samples
    # after its note-off
    "sixop-notes": ("sixop", ["Volume=1"], _TWO_NOTES, [], 0.5),
    "macro-notes": ("macro", ["Model=0", "Volume=1"], _TWO_NOTES, [], 0.5),
    # E.PIANO 1 (no key sync: its operators run free) released to silence at
    # 0.14 s, freed 50 ms later, replayed at 0.36 s. The replay starts from
    # the phases the voice stopped at, so a silent-voice timer counted at the
    # host's rate (12 blocks early) moves every sample of it.
    "sixop-voice-freed-and-replayed": ("sixop", ["Patch=32", "Envelope=0.3", "Volume=1"],
                                       [(60, 704, 3712), (60, 16000, 19968)], [], 0.5),
    # A snare (random, self-enveloped) silent from 0.26 s, freed by the
    # 50 ms timer (Decay 1 keeps the wrapper's release fade above 0.7, so
    # silence in the WAV is silence to the timer), then another snare at
    # 0.45 s. Every block a voice renders draws from stmlib::Random, so a
    # voice freed early changes every later noise sample.
    "heavy-snare-freed-and-another-played": (
        "macro-heavy", ["Model=11", "Morph=0.2", "Decay=1", "Volume=1"],
        [(60, 704, 3712), (62, 19968, 21760)], [], 0.5),
    # The string machine left for Swarm and entered again, by two Model
    # changes: its AUX (the right channel) rings out through the right
    # resampler after leaving, and the right resampler is in step on return.
    "heavy-string-machine-left-and-entered-again": (
        "macro-heavy", ["Model=0", "Volume=1"], [(57, 704, 12736), (64, 7680, 12736),
                                                 (60, 14080, 19968)],
        [(6016, "Model=5"), (14016, "Model=0")], 0.5),
    # The same, back within 64 samples, while the right resampler still runs.
    "heavy-string-machine-left-briefly": (
        "macro-heavy", ["Model=0", "Volume=1"], [(57, 704, 12736), (60, 7680, 12736)],
        [(6016, "Model=5"), (6080, "Model=0")], 0.5),
}
# Cases whose premise is a voice freed before a later note: (silent blocks
# the wrapper waits before freeing, its block, the later note's arrival).
SELF_FREED = {
    "sixop-voice-freed-and-replayed": (149, 16, 16000),
    "heavy-snare-freed-and-another-played": (199, 12, 19968),
}


def self_block(engine):
    return 16 if engine == "sixop" else 12


def self_native_sample(engine, arrival):
    """The 47,872.34 Hz sample on which a wrapper acts on an event arriving
    before host sample `arrival` at 44,118 Hz: the first block not yet
    rendered."""
    b = self_block(engine)
    return b * -(-inputs_pulled(arrival) // b)


def self_case(tmp, name):
    """(fm1 at 44,118 Hz in 64-frame blocks, fm1 at 47,872.34 Hz resampled to
    44,118 Hz, fm1 at 47,872.34 Hz) for one SELF_CASES entry."""
    if ("self", name) in _cache:
        return _cache[("self", name)]
    engine, params, notes, changes, seconds = SELF_CASES[name]
    host, native, resampled = (tmp / f"self_{k}_{name}.wav" for k in ("host", "native", "res"))
    # The native render runs past what the resampler pulls for `seconds`.
    host_cmd = [RENDER, "--engine", engine, "--rate", FM1_RATE, "--frames", 64,
                "--seconds", seconds, "--out", host]
    native_cmd = [RENDER, "--engine", engine, "--rate", NATIVE, "--frames", 1,
                  "--seconds", seconds * RATE_RATIO + 0.01, "--out", native]
    for p in params:
        host_cmd += ["--param", p]
        native_cmd += ["--param", p]
    # Half a sample early: each lands on the block start (or sample) after it.
    at_host = lambda a: (a - 0.5) / FM1_HZ                                  # noqa: E731
    at_native = lambda a: (self_native_sample(engine, a) - 0.5) / NATIVE_HZ  # noqa: E731
    for key, on, off in notes:
        host_cmd += ["--note", f"{at_host(on):.9f}:{key}:100:{at_host(off) - at_host(on):.9f}"]
        native_cmd += ["--note",
                       f"{at_native(on):.9f}:{key}:100:{at_native(off) - at_native(on):.9f}"]
    for arrival, p in changes:
        host_cmd += ["--param-at", f"{at_host(arrival):.9f}:{p}"]
        native_cmd += ["--param-at", f"{at_native(arrival):.9f}:{p}"]
    run_all([host_cmd, native_cmd])
    _run([REF, "--resample", native, "--host-rate", FM1_RATE, "--seconds", seconds,
          "--out", resampled])
    _cache[("self", name)] = (host, resampled, native)
    return _cache[("self", name)]


@pytest.mark.parametrize("name", SELF_CASES)
def test_fm1_rate_output_is_the_native_output_resampled(wavs, name):
    """At 44,118 Hz each wrapper renders what it renders at 47,872.34 Hz,
    resampled: both channels within SELF_LSB, with the events on the blocks
    the resampler's pulls predict."""
    host, resampled, _ = self_case(wavs, name)
    failures = []
    for ch in (0, 1):
        d = lsb_diff(resampled, host, ch, ch)
        failures += [f"ch{ch}: {x}" for x in host_failures(d, SELF_LSB)]
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("name", SELF_CASES)
def test_native_rate_note_starts_on_its_block(wavs, name):
    """At 47,872.34 Hz in 1-frame host blocks a note that arrives before
    sample S, a block start, sounds from S: silence before it, sound within
    its first block. (A block rendered as soon as the last ran out would
    leave that block silent.)"""
    engine, _, notes, _, _ = SELF_CASES[name]
    s = self_native_sample(engine, notes[0][1])
    x = wav_channels(self_case(wavs, name)[2])[0]
    assert s == 768
    assert not any(x[:s]) and any(x[s:s + self_block(engine)])


@pytest.mark.parametrize("name", SELF_FREED)
def test_freed_voice_cases_free_the_voice(wavs, name):
    """The premise of the freed-voice cases: before the later note the first
    has been digitally silent in the native render for longer than the
    wrapper waits before freeing a silent released voice (50 ms, plus a
    block either side), so the later note finds it freed. Six-Op's E.PIANO 1
    has no key sync, as the replay's sensitivity to the freeing time needs."""
    hold, block, arrival = SELF_FREED[name]
    engine = SELF_CASES[name][0]
    x = wav_channels(self_case(wavs, name)[2])[0]
    s = self_native_sample(engine, arrival)
    quiet = s - max(i for i in range(s) if x[i]) - 1
    assert quiet > (hold + 2) * block, quiet
    if engine == "sixop":
        info = _run([REF, "--engine", 3, "--harmonics", f"{0.5 / 32.64:.6f}", "--seconds", "0.01"])
        assert (info["sixop"]["patch"], info["sixop"]["key_sync"]) == (32, 0)


# --- intentional differences, and what the reference itself does -------------------------

def _onset(path, threshold=0.001):
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
        ch = w.getnchannels()
    for i in range(0, len(raw) // (2 * ch)):
        v = int.from_bytes(raw[2 * ch * i:2 * ch * i + 2], "little", signed=True) / 32768
        if abs(v) > threshold:
            return i
    return None


def test_trigger_reaches_the_engine_48_samples_late(wavs):
    """Voice delays TRIG by kTriggerDelay - 1 = 4 blocks. With the literal
    timing (--literal: engine selected from the first block, TRIG and LEVEL
    together) a bass drum starts 48 samples after the aligned reference,
    which starts on sample 0 like the wrapper."""
    slot = BY_INDEX[21]
    point = neutral(POINTS[0])
    a, b = wavs / "aligned.wav", wavs / "literal.wav"
    run_all([ref_cmd(a, slot, 57, point), ref_cmd(b, slot, 57, point, extra=["--literal"])])
    assert _onset(a) == 0
    assert _onset(b) == 48


def test_sixop_applies_the_patch_transpose_plaits_ignores(wavs):
    """Six-Op plays each patch at its own transpose (DX7 C3 = 24); Plaits
    ignores it. At the same key the fm1 note sits (transpose - 24) semitones
    from upstream's, and that is the only pitch difference."""
    slot = BY_INDEX[2]
    point = Point(0.2, 0.5, 0.5, 0.5, 0.5, VELOCITY)    # bank 1, slot 6, "BASS    1"
    ref, fm1 = wavs / "tr_ref.wav", wavs / "tr_fm1.wav"
    info = _run(ref_cmd(ref, slot, 57, point))
    shift = info["sixop"]["transpose"] - 24
    assert shift != 0
    _run(fm1_cmd(fm1, slot, 57, point))
    c = _run(cmp_cmd(ref, fm1, slot.gain, "--pitch-range", "1300", "--pitch-lo", "30"))
    assert abs(c["pitch_cents"] - 100 * shift) < 0.5


def test_chiptune_keeps_the_low_pass_gate(wavs):
    """Upstream, the clocked chiptune reports itself enveloped and Voice
    bypasses the LPG: with the TIMBRE attenuverter at 0 the note holds at full
    level after the trigger falls. The wrapper keeps the LPG, so velocity,
    Decay and Colour shape the note and key-up releases it."""
    slot = BY_INDEX[7]
    point = neutral(POINTS[0])
    ref, fm1 = wavs / "chip_lpg_ref.wav", wavs / "chip_lpg_fm1.wav"
    run_all([ref_cmd(ref, slot, 57, point), fm1_cmd(fm1, slot, 57, point)])
    held = _run(cmp_cmd(ref, fm1, slot.gain, "--from", "0.05", "--to", "0.25"))
    tail = _run(cmp_cmd(ref, fm1, slot.gain, "--from", "0.5", "--to", "0.6"))
    assert held["ncc"] > 0.95 and held["err_dbfs"] > -60   # the same notes, through the LPG
    assert tail["level_db"] < -20                          # released here, held upstream


@pytest.mark.parametrize("index,point", [(15, Point(0.5, 0.8, 0.2, 0.3, 0.5, VELOCITY)),
                                         (19, Point(0.2, 0.5, 0.8, 0.3, 0.5, VELOCITY)),
                                         (21, Point(0.2, 0.5, 0.8, 0.3, 0.5, VELOCITY))],
                         ids=["speech-word", "string", "bass-drum"])
def test_added_release_after_note_off(wavs, index, point):
    """The self-enveloped models fade at note-off with the LPG's release
    curve (plaits-heavy.md). Upstream, LEVEL falling to 0 ends a speech word
    at once (the accent is the word's gain on every block), and leaves drums
    and strings ringing (they read the accent at the trigger)."""
    slot = BY_INDEX[index]
    ref, fm1 = wavs / f"rel_ref_{index}.wav", wavs / f"rel_fm1_{index}.wav"
    run_all([ref_cmd(ref, slot, 57, point, gate=GATE), fm1_cmd(fm1, slot, 57, point, gate=GATE)])
    before = _run(cmp_cmd(ref, fm1, slot.gain, "--to", GATE))
    after = _run(cmp_cmd(ref, fm1, slot.gain, "--from", GATE + 0.1, "--to", SECONDS))
    assert before["err_dbfs"] < -80                  # identical while held
    if index == 15:
        assert after["level_db"] > 10                # the wrapper's word fades out
    else:
        assert after["level_db"] < -6                # upstream rings on


# --- negative controls ---------------------------------------------------------------------

NEGATIVE = {
    # name: (slot, fm1 parameters (None: the right ones), reference note offset);
    # at neutral(POINTS[1]) unless NEGATIVE_POINT says otherwise
    "wrong-engine": (8, ["Model=5", "Harmonics=0.5", "Timbre=0.8", "Morph=0.2", "Volume=1"], 0),
    "next-heavy-model": (12, ["Model=5", "Harmonics=0.5", "Timbre=0.8", "Morph=0.2",
                              "Volume=1"], 0),
    "timbre-morph-swapped": (0, ["Model=0", "Harmonics=0.5", "Timbre=0.2", "Morph=0.8",
                                 "Volume=1"], 0),
    "mistuned-1-cent": (8, None, 0.01),
    "decay-0.55": (9, ["Model=5", "Harmonics=0.5", "Timbre=0.8", "Morph=0.2", "Decay=0.55",
                       "Volume=1"], 0),
    "colour-0.55": (9, ["Model=5", "Harmonics=0.5", "Timbre=0.8", "Morph=0.2", "Colour=0.55",
                        "Volume=1"], 0),
    "volume-0.99": (13, ["Model=7", "Harmonics=0.5", "Timbre=0.8", "Morph=0.2", "Volume=0.99"], 0),
    "sixop-next-patch": (3, ["Patch=49", "Brightness=0.8", "Envelope=0.2", "Volume=1"], 0),
    "sixop-envelope-0.25": (3, ["Patch=48", "Brightness=0.8", "Envelope=0.25", "Volume=1"], 0),
    "sixop-brightness-0.45": (2, ["Patch=6", "Brightness=0.45", "Envelope=0.8", "Volume=1"], 0),
    "sixop-brightness-envelope-swapped": (3, ["Patch=48", "Brightness=0.2", "Envelope=0.8",
                                              "Volume=1"], 0),
    "sixop-mistuned-2-cents": (3, None, 0.02),
}


NEGATIVE_POINT = {"sixop-brightness-0.45": POINTS[0]}   # bank 1 slot 6, "BASS    1"


def negative_failures(tmp, name):
    """The criteria's verdict on one deliberate error: (failures, compare JSON)."""
    index, params, ref_offset = NEGATIVE[name]
    slot = BY_INDEX[index]
    point, note = neutral(NEGATIVE_POINT.get(name, POINTS[1])), 57
    ref, fm1 = tmp / f"neg_ref_{name}.wav", tmp / f"neg_fm1_{name}.wav"
    info = _run(ref_cmd(ref, slot, note + ref_offset, point))
    _run(fm1_cmd(fm1, slot, played_key(slot, note, info), point, params=params))
    c = _run(cmp_cmd(ref, fm1, slot.gain, "--max-lag-ms", "2" if slot.engine == "sixop" else "1"))
    return (sixop_failures(c) if slot.engine == "sixop" else exact_failures(c)), c


@pytest.mark.parametrize("name", NEGATIVE)
def test_criteria_reject(wavs, name):
    """Each deliberate error fails the sample-exact or Six-Op criteria. (The
    Six-Op limit: how small a Brightness error it sees depends on the patch;
    see reference-plaits.md.)"""
    f, c = negative_failures(wavs, name)
    assert f, f"{name} passed: {c}"


NEGATIVE_STAT = {
    # name: (slot, key offset, fm1 Model or None)
    "noise-a-semitone-sharp": (17, 1, None),
    "string-a-semitone-sharp": (19, 1, None),
    "particle-an-octave-sharp": (18, 12, None),
    "swarm-as-noise": (16, 0, "Model=6"),
    "hihat-as-snare": (23, 0, "Model=11"),
}


# Reported, not tested: where the statistical criteria stop.
REPORT_STAT = {"particle-a-semitone-sharp": (18, 1, None)}


def negative_stat_failures(tmp, name):
    index, offset, model = {**NEGATIVE_STAT, **REPORT_STAT}[name]
    slot = BY_INDEX[index]
    failures, cases = [], 0
    for note in NOTES:
        for i in slot.stat_points:
            params = fm1_params(slot, neutral(POINTS[i]))
            if model:
                params[0] = model
            pairs, refs, cand, _ = stat_case(tmp, slot, note, POINTS[i], name=name,
                                             key_offset=offset, params=params)
            f = stat_failures(pairs, refs, cand, stat_keys(slot))[0]
            failures += f
            cases += len(stat_keys(slot))
    return failures, cases


@pytest.mark.parametrize("name", NEGATIVE_STAT)
def test_statistical_criteria_reject(wavs, name):
    """Each deliberate error fails the statistical criteria at one point or
    more. (Their limit: a particle cloud a semitone sharp passes; see
    reference-plaits.md.)"""
    failures, _ = negative_stat_failures(wavs, name)
    assert failures, f"{name} passed"


# --- report, calibration and the Six-Op sweep -------------------------------------------

def _fmt(v, p=3):
    return "n/a" if v is None else f"{v:.{p}f}"


def report(tmp):
    """Print the per-slot tables of engines/reference-plaits.md."""
    print(f"Vendored closure: {len(vendored_closure())} files, digest {vendored_digest(vendored_closure())}")
    print()
    print("Native rate (worst of 6 cases; limits in the test)")
    print("| # | Upstream | fm1 | Criteria | Error dBFS / NCC, lag | Gain dB | Env max dB | "
          "Pitch cents | LSD dB | 64-frame host |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    worst_all = collections.defaultdict(float)
    for slot in SLOTS:
        cases = [native_case(tmp, slot, n, p) for n in NOTES for p in POINTS]
        rows = [c for case in cases for c in case[1]]
        same = all(case[2] for case in cases)

        def worst(k):
            vals = [abs(r[k]) for r in rows if r[k] is not None]
            return max(vals) if vals else None
        crit = ("close" if slot.engine == "sixop"
                else "exact, shared seed" if slot.random else "exact")
        model = f"{slot.engine} {'bank' if slot.engine == 'sixop' else 'Model'} {slot.model}"
        if slot.engine == "sixop":
            first = (f"{min(r['ncc'] for r in rows):.4f}, "
                     f"{min(r['lag'] for r in rows)}..{max(r['lag'] for r in rows)}")
        else:
            first = f"{max(r['err_dbfs'] for r in rows):.1f}"
            for k in ("gain_db", "env_max_db", "lsd_db") + (("pitch_cents",) if slot.pitched else ()):
                worst_all[k] = max(worst_all[k], worst(k) or 0.0)
            worst_all["err_dbfs"] = max(worst_all.get("err_dbfs", -200.0),
                                        max(r["err_dbfs"] for r in rows))
            worst_all["cases"] += len(rows)
        print(f"| {slot.index} | {slot.upstream} | {model} | {crit} | {first} | "
              f"{_fmt(worst('gain_db'), 4)} | {_fmt(worst('env_max_db'))} | "
              f"{_fmt(worst('pitch_cents') if slot.pitched else None)} | {_fmt(worst('lsd_db'))} | "
              f"{'identical' if same else 'DIFFERS'} |")
    print("Exact criteria, worst over all exact cases:", dict(worst_all))
    six = [c for s in SLOTS if s.engine == "sixop" for n in NOTES for p in POINTS
           for c in native_case(tmp, s, n, p)[1]]
    print("Six-Op worst: 1-NCC", max(1 - c["ncc"] for c in six),
          {k: max(abs(c[k]) for c in six) for k in ("gain_db", "env_max_db", "pitch_cents", "lsd_db")},
          "lags", min(c["lag"] for c in six), max(c["lag"] for c in six))
    print()
    print("Statistical (fm1 median distance / limit, the point nearest its limit)")
    print("| # | Upstream | " + " | ".join(STAT) + " | vs shared seed, dBFS |")
    print("| --- | --- | " + " | ".join("---" for _ in STAT) + " | --- |")
    for slot in STAT_SLOTS:
        worst, shared_err = {}, []
        for note in NOTES:
            for i in slot.stat_points:
                pairs, refs, cand, shared = stat_case(tmp, slot, note, POINTS[i])
                shared_err.append(shared["err_dbfs"])
                for k, (got, lim) in stat_failures(pairs, refs, cand, stat_keys(slot))[1].items():
                    if k not in worst or got / lim > worst[k][0] / worst[k][1]:
                        worst[k] = (got, lim)
        print(f"| {slot.index} | {slot.upstream} | " + " | ".join(
            f"{worst[k][0]:.3g} / {worst[k][1]:.3g}" if k in worst else "–" for k in STAT)
            + f" | {min(shared_err):.1f} |")
    print()
    print("Negative controls, exact and Six-Op criteria (what fails)")
    for name in NEGATIVE:
        f, c = negative_failures(tmp, name)
        print(f"  {name}: " + "; ".join(f))
    print("Negative controls, statistical (failing point-measures / all)")
    for name in list(NEGATIVE_STAT) + list(REPORT_STAT):
        f, n = negative_stat_failures(tmp, name)
        print(f"  {name}: {len(f)} of {n}: " + "; ".join(sorted({x.split(':')[0] for x in f})))
    print("Six-Op Brightness errors at the test points, A3 (NCC; FAIL or pass)")
    for bank in range(3):
        slot = BY_INDEX[2 + bank]
        for i, point in enumerate(POINTS):
            ref = tmp / f"bright_ref_{bank}_{i}.wav"
            info = _run(ref_cmd(ref, slot, 57, point))
            key, out = played_key(slot, 57, info), []
            for err in (0.0, 0.05, 0.1, 0.2):
                fm1 = tmp / f"bright_{bank}_{i}_{err}.wav"
                params = fm1_params(slot, point)
                params[1] = f"Brightness={max(0.0, point.timbre - err)}"
                _run(fm1_cmd(fm1, slot, key, point, params=params))
                c = _run(cmp_cmd(ref, fm1, slot.gain, "--max-lag-ms", "2"))
                out.append(f"-{err}: {c['ncc']:.4f} {'FAIL' if sixop_failures(c) else 'pass'}")
            print(f"  bank {bank + 1} {info['sixop']['name']!r} {tuple(point)[:3]}: " + " | ".join(out))
    print()
    print("44,118 Hz against upstream resampled the same way (worst of 6 cases; Six-Op: "
          "least NCC, lags, worst gain, envelope, pitch, LSD)")
    print("| # | Upstream | Largest difference, LSB | RMS, LSB | Samples differing (of all compared) |")
    print("| --- | --- | --- | --- | --- |")
    for slot in SLOTS:
        rows = [r for n in NOTES for p in POINTS for r in host_case(tmp, slot, n, p)[1]]
        if slot.engine == "sixop":
            cs = [r["cmp"] for r in rows]
            print(f"| {slot.index} | {slot.upstream} | NCC {min(c['ncc'] for c in cs):.4f}, lag "
                  f"{min(c['lag'] for c in cs)}..{max(c['lag'] for c in cs)} | gain "
                  f"{max(abs(c['gain_db']) for c in cs):.3f} dB, env {max(c['env_max_db'] for c in cs):.3f} dB "
                  f"| pitch {max(abs(c['pitch_cents']) for c in cs):.3f} c, LSD "
                  f"{max(c['lsd_db'] for c in cs):.3f} dB |")
        else:
            ds = [r["lsb"] for r in rows]
            print(f"| {slot.index} | {slot.upstream} | {max(d['max'] for d in ds)} | "
                  f"{max(d['rms'] for d in ds):.3f} | {sum(d['differ'] for d in ds)} of "
                  f"{sum(d['n'] for d in ds):,} |")
    print()
    print("44,118 Hz against upstream at its own rate, unresampled (A2 / A4)")
    print("| # | Upstream | Pitch cents | Stretch (method, range) | Level dB | LSD dB |")
    print("| --- | --- | --- | --- | --- | --- |")
    for slot in SLOTS:
        cs = [rate_case(tmp, slot, n) for n in NOTES]
        pitch = " / ".join(f"{c['pitch_cents']:+.3f}" for c in cs)
        if not slot.rate_pitch:
            pitch += " (not held)"
        if slot.rate_timing:
            m, lo, hi = slot.rate_timing
            st = " / ".join(_fmt(rate_stretch(slot, c)) for c in cs) + f" ({m}, {lo:.3f}..{hi:.3f})"
        else:
            st = " / ".join(_fmt(c["stretch"]) for c in cs) + " (not held)"
        print(f"| {slot.index} | {slot.upstream} | {pitch} | {st} | "
              + " / ".join(f"{c['level_db']:+.3f}" for c in cs) + " | "
              + " / ".join(f"{c['lsd_db']:.2f}" for c in cs) + " |")
    print()
    print("Negative controls at 44,118 Hz (largest difference, LSB)")
    for name in HOST_NEGATIVE:
        f, d = host_negative_failures(tmp, name)
        print(f"  {name}: {d['max']} LSB, {d['differ']} of {d['n']} samples; " + "; ".join(f))
    print()
    print("44,118 Hz against the wrapper's own 47,872.34 Hz render, resampled (L / R)")
    print("| Case | Largest difference, LSB | RMS, LSB | Samples differing (of all) | Peak, LSB |")
    print("| --- | --- | --- | --- | --- |")
    for name in SELF_CASES:
        host, resampled, _ = self_case(tmp, name)
        ds = [lsb_diff(resampled, host, ch, ch) for ch in (0, 1)]
        print(f"| {name} | " + " / ".join(str(d["max"]) for d in ds) + " | "
              + " / ".join(f"{d['rms']:.3f}" for d in ds) + " | "
              + " / ".join(f"{d['differ']:,}" for d in ds) + f" (of {ds[0]['n']:,}) | "
              + " / ".join(f"{d['peak']:,}" for d in ds) + " |")
    lat = []
    for arrival in range(1, 20001):
        start = 12 * -(-inputs_pulled(arrival) // 12)
        lat.append(start * FM1_HZ / NATIVE_HZ + RESAMPLER_DELAY - arrival)
    lat16 = []
    for arrival in range(1, 20001):
        start = 16 * -(-inputs_pulled(arrival) // 16)
        lat16.append(start * FM1_HZ / NATIVE_HZ + RESAMPLER_DELAY - arrival)
    for name, v in (("12-sample blocks", lat), ("16-sample blocks (Six-Op)", lat16)):
        print(f"Note arrival to onset centre, {name}, arrivals 1-20,000: "
              f"{min(v):.2f}-{max(v):.2f} output samples ({1000 * min(v) / FM1_HZ:.3f}-"
              f"{1000 * max(v) / FM1_HZ:.3f} ms), mean {statistics.mean(v):.2f} "
              f"({1000 * statistics.mean(v) / FM1_HZ:.3f} ms)")


def calibrate(tmp):
    """The STAT factors. Each of eight seeded upstream renders in turn is the
    candidate against five of the other seven, at every statistical point;
    the factor it needs for a measure is (its median - floor) / spread. The
    largest need over all of them, times 1.5, is the factor. The fm1
    candidate's and the negative controls' needs are printed beside it."""
    need_up = collections.defaultdict(list)
    need_fm1 = collections.defaultdict(list)
    for slot in STAT_SLOTS:
        for note in NOTES:
            for i in slot.stat_points:
                point = neutral(POINTS[i])
                refs = stat_members(tmp, slot, note, point, seeds=CALIBRATION_SEEDS)
                pairs = {}
                cmds, keys = [], []
                for a, b in itertools.combinations(refs, 2):
                    keys.append(tuple(sorted((a, b))))
                    cmds.append(cmp_cmd(a, b, 1, *STAT_ARGS))
                pairs.update(zip(keys, run_all(cmds)))
                for k in stat_keys(slot):
                    floor = STAT[k][1]
                    for c in range(len(refs)):
                        others = [r for j, r in enumerate(refs) if j != c][:len(SEEDS)]
                        got, spread = stat_measure(pairs, others, refs[c], k)
                        if spread:
                            need_up[k].append(((got - floor) / spread, slot.index, note, i))
                fpairs, _, cand, _ = stat_case(tmp, slot, note, POINTS[i])
                for k in stat_keys(slot):
                    got, spread = stat_measure(fpairs, stat_members(tmp, slot, note, point), cand, k)
                    if spread:
                        need_fm1[k].append(((got - STAT[k][1]) / spread, slot.index, note, i))
    print("measure: upstream's largest need (slot, note, point) | fm1's largest need | "
          "factor in use (1.5 x upstream's)")
    for k in STAT:
        if not need_up[k]:
            continue
        u, f = max(need_up[k]), max(need_fm1[k])
        scale = f"{1.5 * u[0]:.2f}" if u[0] > 0 else "every render within the floor"
        print(f"  {k}: {u[0]:.2f} {u[1:]} | {f[0]:.2f} {f[1:]} | {STAT[k][0]} ({scale})")


def sixop_sweep(tmp):
    """All 96 Six-Op patches x NOTES x three (Brightness, Envelope) pairs at
    velocity 100: fm1 against upstream, beside upstream against itself with
    one timing detail moved (the yardsticks): the note one 12-sample block
    later (--delay-blocks 1, the other half of SixOpEngine's staggered
    24-sample chunks), the note one whole chunk later (--delay-blocks 2), and
    the note-off one block later. Then the 44,118 Hz release timing of the
    patches whose release falls 30-400 dB/s at both notes."""
    tms = ((0.5, 0.5), (0.8, 0.2), (0.2, 0.8))
    yardsticks = (("note one block later", dict(extra=["--delay-blocks", "1"])),
                  ("note one chunk later", dict(extra=["--delay-blocks", "2"])),
                  ("note-off one block later", dict(gate=GATE + 12 / NATIVE_HZ)))
    renders, cmps, meta = [], [], []
    for bank in range(3):
        slot = BY_INDEX[2 + bank]
        for p in range(32):
            h = (p + 0.5) / 32.64
            for note in NOTES:
                for t, m in tms:
                    point = Point(h, t, m, 0.5, 0.5, VELOCITY)
                    tag = _tag("sweep", bank, p, note, t, m)
                    ref, fm1 = tmp / f"r_{tag}.wav", tmp / f"f_{tag}.wav"
                    info = _run(ref_cmd(ref, slot, note, point))
                    renders.append(fm1_cmd(fm1, slot, played_key(slot, note, info), point))
                    cmps.append(cmp_cmd(ref, fm1, slot.gain, "--max-lag-ms", "2", "--no-timing"))
                    for j, (_, kw) in enumerate(yardsticks):
                        other = tmp / f"y{j}_{tag}.wav"
                        renders.append(ref_cmd(other, slot, note, point, **kw))
                        cmps.append(cmp_cmd(ref, other, 1, "--max-lag-ms", "2", "--no-timing"))
                    meta.append((bank, p, note, (t, m), info["sixop"]["name"], info["sixop"]["key_sync"]))
    run_all(renders)
    res = run_all(cmps)
    n = len(yardsticks) + 1
    cols = [("fm1 against upstream", res[0::n])] + [
        (f"upstream, {name}", res[j + 1::n]) for j, (name, _) in enumerate(yardsticks)]
    print(f"{len(meta)} cases; " + "; ".join(
        f"{name}: lag {min(c['lag'] for c in rows)}..{max(c['lag'] for c in rows)}" for name, rows in cols))
    print("| | " + " | ".join(name for name, _ in cols) + " |")
    print("| --- |" + " --- |" * len(cols))
    for k, name in (("residual_db", "Residual (1 - NCC^2), median / worst, dB"),
                    ("env_max_db", "Envelope, median / worst, dB"),
                    ("pitch_cents", "Pitch, median / worst, cents"),
                    ("gain_db", "Gain, median / worst, dB")):
        def col(rows):
            v = [c[k] if k == "residual_db" else abs(c[k]) for c in rows if c[k] is not None]
            return f"{statistics.median(v):.3g} / {max(v):.3g}"
        print(f"| {name} | " + " | ".join(col(rows) for _, rows in cols) + " |")
    print("| Identical (error under -100 dBFS) | " + " | ".join(
        f"{sum(1 for c in rows if c['err_dbfs'] < -100)} of {len(rows)}" for _, rows in cols) + " |")
    fm = cols[0][1]
    worst = sorted(zip(fm, meta), key=lambda x: -x[0]["residual_db"])[:6]
    print("worst fm1 residuals:", [(round(c["residual_db"], 1), m) for c, m in worst])
    worst = sorted(zip(fm, meta), key=lambda x: -abs(x[0]["gain_db"]))[:6]
    print("worst fm1 gains:", [(round(c["gain_db"], 2), m) for c, m in worst])
    for name, rows in cols[1:]:
        worst = sorted(zip(rows, meta), key=lambda x: -x[0]["residual_db"])[:4]
        print(f"worst residuals, {name}:", [(round(c["residual_db"], 1), m) for c, m in worst])
    for sync in (1, 0):
        sel = [i for i, m in enumerate(meta) if m[5] == sync]
        print(f"{'with' if sync else 'without'} key sync: {len(sel)} cases, median residual " + "; ".join(
            f"{name} {statistics.median(rows[i]['residual_db'] for i in sel):.1f} dB" for name, rows in cols))
    # 44,118 Hz release timing
    renders, cmps, meta = [], [], []
    for bank in range(3):
        slot = BY_INDEX[2 + bank]
        for p in range(32):
            point = Point((p + 0.5) / 32.64, 0.5, 0.5, 0.3, 0.5, VELOCITY)
            for note in NOTES:
                tag = _tag("sweep44", bank, p, note)
                ref, fm1 = tmp / f"r_{tag}.wav", tmp / f"f_{tag}.wav"
                info = _run(ref_cmd(ref, slot, note, point, seconds=1.0))
                renders.append(fm1_cmd(fm1, slot, played_key(slot, note, info), point, rate=FM1_RATE,
                                       frames=64, seconds=1.0))
                cmps.append(cmp_cmd(ref, fm1, slot.gain, "--t0", GATE))
                meta.append((bank, p, note))
    run_all(renders)
    res = run_all(cmps)
    by_patch = collections.defaultdict(dict)
    for c, (bank, p, note) in zip(res, meta):
        by_patch[(bank, p)][note] = c
    sel = [cs for cs in by_patch.values()
           if all(cs[n]["decay_rate_ref"] is not None and 30 <= cs[n]["decay_rate_ref"] <= 400
                  and cs[n]["slope_stretch"] is not None for n in NOTES)]
    st = [cs[n]["slope_stretch"] for cs in sel for n in NOTES]
    print(f"44,118 Hz: {len(sel)} patches release at 30-400 dB/s at both notes; decay-rate ratio "
          f"{min(st):.3f}..{max(st):.3f}, median {statistics.median(st):.3f}")


if __name__ == "__main__":
    import tempfile
    modes = {"--report": report, "--calibrate": calibrate, "--sixop-sweep": sixop_sweep}
    args = sys.argv[1:]
    chosen = [modes[a] for a in args if a in modes]
    if not chosen or len(chosen) + 2 * ("--render" in args) != len(args):
        sys.exit("usage: python tests/test_engines_reference_plaits.py "
                 "[--report] [--calibrate] [--sixop-sweep] [--render PATH]\n"
                 "--render: another fm1-render build for the fm1 side (for example a\n"
                 "scratch build of a changed wrapper), instead of engines/build's")
    subprocess.run(["make", "-C", str(ENGINES), "-j4"], check=True, stdout=subprocess.DEVNULL)
    if "--render" in args:
        RENDER = Path(args[args.index("--render") + 1]).resolve()
    with tempfile.TemporaryDirectory() as d:
        for mode in chosen:
            mode(Path(d))
