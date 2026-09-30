"""Macro, Macro Heavy and Six-Op FM against upstream Plaits (engines/reference-plaits.md).

Each of plaits::Voice's 24 engine slots is rendered twice and compared. The
reference is fm1-ref-plaits: the vendored, unmodified Voice, driven the way the
module drives it. The other side is fm1-render, through the fm1 engine that
wraps the same slot.

- At Plaits' own rate (47,872.34 Hz, fm1-render in 12-frame blocks): three
  (harmonics, timbre, morph) points and two notes two octaves apart.
  - Engines whose OUT does not depend on the random generator must match
    sample for sample.
  - Six-Op, which renders in other blocks by design, must match closely.
  - Engines with internal randomness must match sample for sample on the
    generator's shared initial state. They must also match statistically,
    without that seed, against seeded upstream renders.
- At the FM-1's rate (44,118 Hz, 64-frame blocks): pitch and envelope timing,
  held against the documented rate compensation.

Negative controls check that the criteria reject a wrong engine, a wrong
parameter mapping, a mistuned or mis-enveloped voice and a wrong gain.

    python tests/test_engines_reference_plaits.py --report   # the doc's tables
"""
import concurrent.futures
import itertools
import json
import os
import re
import statistics
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
NATIVE = "47872.34"          # Plaits' kCorrectedSampleRate
FM1_RATE = "44118"           # the FM-1's
RATE_RATIO = 47872.34 / 44118
NOTES = (45, 69)             # A2 and A4
# (harmonics, timbre, morph): a Latin square, so each knob takes 0.2, 0.5 and
# 0.8 once, each time with the other two elsewhere.
POINTS = ((0.2, 0.5, 0.8), (0.5, 0.8, 0.2), (0.8, 0.2, 0.5))
VELOCITY = 100               # LEVEL 100/127 on the reference; accent 0.94
SECONDS = 0.6
GATE = 0.3                   # note length for the models under the low-pass gate
SHARED_SEED = 0x21           # stmlib::Random's initial state, in both programs
SEEDS = (1001, 2002, 3003, 4004, 5005)   # independent upstream realisations
STAT_SECONDS = 1.5           # held notes for the statistical comparison
WORKERS = min(8, os.cpu_count() or 2)

LPG_STRETCH = ("fit", RATE_RATIO - 0.02, RATE_RATIO + 0.02)


class Slot:
    """One of plaits::Voice's engine slots and the fm1 engine that wraps it.

    env:  "lpg"    under the low-pass gate (released at GATE, release compared);
          "self"   self-enveloped (the note is held: the wrapper's added release
                   is not upstream behaviour, see test_added_release_after_note_off);
          "speech" LPG for vowels (harmonics <= 1/3), self-enveloped for words;
          "sixop"  Six-Op FM (its own DX7 envelopes, released at GATE);
          "chip"   Chiptune (upstream bypasses the LPG in clocked mode).
    random: indices into POINTS where OUT depends on stmlib::Random ("all").
    pitched: the spectral pitch shift is meaningful (a tone, not a texture).
    rate_pitch: cents allowed at 44,118 Hz, or None (not a pitch).
    rate_timing: (method, lo, hi) for the envelope time stretch at 44,118 Hz,
                 or None where one render per rate cannot show it.
    """

    def __init__(self, index, upstream, engine, model, env, random=(), pitched=True,
                 rate_pitch=5.0, rate_timing=LPG_STRETCH, rate_point=(0.5, 0.5, 0.5)):
        self.index, self.upstream, self.engine, self.model = index, upstream, engine, model
        self.env, self.pitched = env, pitched
        self.random = tuple(range(len(POINTS))) if random == "all" else tuple(random)
        self.rate_pitch, self.rate_timing, self.rate_point = rate_pitch, rate_timing, rate_point

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
         rate_point=(0.3217, 0.5, 0.5)),
    Slot(3, "SixOpEngine-bank2", "sixop", 1, "sixop", rate_timing=("slope", 0.98, 1.02),
         rate_point=(0.1991, 0.5, 0.5)),
    Slot(4, "SixOpEngine-bank3", "sixop", 2, "sixop", rate_timing=("slope", 0.98, 1.02)),
    Slot(5, "WaveTerrainEngine", "macro", 2, "lpg"),
    Slot(6, "StringMachineEngine", "macro-heavy", 0, "lpg"),
    Slot(7, "ChiptuneEngine", "macro", 3, "chip", random=(1,), rate_timing=None),
    Slot(8, "VirtualAnalogEngine", "macro", 4, "lpg"),
    Slot(9, "WaveshapingEngine", "macro", 5, "lpg"),
    Slot(10, "FMEngine", "macro", 6, "lpg", rate_point=(0.5, 0.0, 0.5)),
    Slot(11, "GrainEngine", "macro-heavy", 3, "lpg"),
    Slot(12, "AdditiveEngine", "macro-heavy", 4, "lpg"),
    Slot(13, "WavetableEngine", "macro", 7, "lpg"),
    Slot(14, "ChordEngine", "macro-heavy", 1, "lpg", rate_timing=None),
    Slot(15, "SpeechEngine", "macro-heavy", 2, "speech"),
    Slot(16, "SwarmEngine", "macro-heavy", 5, "lpg", random="all", pitched=False,
         rate_pitch=None, rate_timing=None),
    Slot(17, "NoiseEngine", "macro-heavy", 6, "lpg", random="all", pitched=False,
         rate_pitch=None, rate_timing=None),
    Slot(18, "ParticleEngine", "macro-heavy", 7, "lpg", random="all", pitched=False,
         rate_pitch=None, rate_timing=None),
    Slot(19, "StringEngine", "macro-heavy", 8, "self", random="all", rate_pitch=12.0,
         rate_timing=None),
    Slot(20, "ModalEngine", "macro-heavy", 9, "self", rate_timing=("fit", 0.98, RATE_RATIO + 0.02)),
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
    if slot.env == "self" or (slot.env == "speech" and point[0] * 6.0 > 2.0):
        return seconds
    return GATE


def ref_cmd(out, slot, note, point, seconds=SECONDS, gate=None, seed=None, level=VELOCITY / 127,
            colour=0.5, decay=0.5, extra=()):
    h, t, m = point
    cmd = [REF, "--engine", slot.index, "--note", note, "--harmonics", h, "--timbre", t,
           "--morph", m, "--seconds", seconds,
           "--gate", gate_for(slot, point, seconds) if gate is None else gate,
           "--level", f"{level:.6f}", "--colour", colour, "--decay", decay, "--out", out]
    if seed is not None:
        cmd += ["--seed", seed]
    return cmd + list(extra)


def sixop_patch(slot, harmonics):
    """The patch SixOpEngine's HARMONICS scan selects (HysteresisQuantizer2,
    32 steps, hysteresis 0.005, from a fresh state)."""
    value = harmonics * 1.02 * 32 - 0.5
    q = int(value + (-0.005 if value > 0 else 0.005) + 0.5)
    return slot.model * 32 + max(0, min(31, q))


def fm1_params(slot, point, colour=0.5, decay=0.5):
    h, t, m = point
    if slot.engine == "sixop":
        return [f"Patch={sixop_patch(slot, h)}", f"Brightness={t}", f"Envelope={m}", "Volume=1"]
    return [f"Model={slot.model}", f"Harmonics={h}", f"Timbre={t}", f"Morph={m}",
            f"Decay={decay}", f"Colour={colour}", "Volume=1"]


def fm1_cmd(out, slot, key, point, rate=NATIVE, frames=12, seconds=SECONDS, gate=None,
            velocity=VELOCITY, params=None, colour=0.5, decay=0.5):
    g = gate_for(slot, point, seconds) if gate is None else gate
    cmd = [RENDER, "--engine", slot.engine, "--rate", rate, "--frames", frames,
           "--seconds", seconds, "--note", f"0:{key}:{velocity}:{g}", "--out", out]
    for p in (params if params is not None else fm1_params(slot, point, colour, decay)):
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


# --- criteria ------------------------------------------------------------------------

# Sample for sample. Both sides carry the Voice's own 16-bit DAC words; fm1's
# are scaled by 0.25 and rounded to 16 bits again, so the difference is that
# rounding: +/-0.5 LSB of fm1's WAV is +/-2 LSB of the reference's, an RMS of
# 2/sqrt(3)/32768, -89 dBFS. The limit is -80 dBFS, 9 dB above it. No lag:
# the wrappers and the aligned reference put the note on the same sample. The
# other measures only restate that error in their own terms: what is left of
# them is the same rounding where the signal is quiet (windows and bands down
# to -70 dBFS). Their limits are about 1.5 times the worst of the 144 cases
# (gain 3 times; reference-plaits.md, "Results").
EXACT = dict(err_dbfs=-80.0, gain_db=0.01, env_max_db=0.25, pitch_cents=0.05, lsd_db=0.25)

# Six-Op runs the same fm::Voice code, with two differences by design
# (reference-plaits.md, "Six-Op"). First, it renders in 16-sample blocks from
# the note-on, where upstream renders staggered 24-sample chunks that start
# 36 samples later; envelopes and LFO step at those block rates. Second, its
# one-sample note-on renders move the free-running operator phases of
# patches without key sync on by one sample. The limits are three times the
# worst of the 18 cases compared (1 - NCC, gain, envelope, pitch, LSD);
# reference-plaits.md has those and the spread over all 96 patches.
SIXOP = dict(ncc=0.977, lag=(-40, -32), gain_db=0.4, env_max_db=0.95, pitch_cents=0.25,
             lsd_db=2.3)

# Random engines, without the shared seed. The fm1 render joins five seeded
# upstream renders of the same held note as a sixth member, and must not be
# the outlier. Its median distance to the others may exceed the largest
# leave-one-out median of any upstream member by the factor, plus the floor.
# The factors are 1.5 times the largest ratio any genuine upstream render
# reached, with eight seeds in turn as the candidate over every random point
# (reference-plaits.md, "Method", Statistical).
STAT = dict(level_db=(4.5, 0.1), env_mean_db=(2.2, 0.2), lsd_db=(2.6, 0.25),
            centroid_cents=(7.5, 5.0), shift_cents=(6.5, 5.0), pitch_cents=(2.0, 0.5))
STAT_ARGS = ("--max-lag-ms", "0", "--env-window-ms", "50", "--no-timing")


def exact_failures(c, limits=EXACT, pitched=True):
    f = []
    if c["lag"] != 0:
        f.append(f"lag {c['lag']} samples")
    if not c["err_dbfs"] <= limits["err_dbfs"]:
        f.append(f"error {c['err_dbfs']:.1f} dBFS > {limits['err_dbfs']}")
    if not abs(c["gain_db"]) <= limits["gain_db"]:
        f.append(f"gain {c['gain_db']:+.4f} dB")
    if not c["env_max_db"] <= limits["env_max_db"]:
        f.append(f"envelope {c['env_max_db']:.3f} dB")
    if pitched and not abs(c["pitch_cents"]) <= limits["pitch_cents"]:
        f.append(f"pitch {c['pitch_cents']:+.3f} cents")
    if not c["lsd_db"] <= limits["lsd_db"]:
        f.append(f"LSD {c['lsd_db']:.3f} dB")
    return f


def sixop_failures(c, limits=SIXOP):
    f = []
    if not c["ncc"] >= limits["ncc"]:
        f.append(f"NCC {c['ncc']:.5f}")
    lo, hi = limits["lag"]
    if not lo <= c["lag"] <= hi:
        f.append(f"lag {c['lag']}")
    for k in ("gain_db", "pitch_cents"):
        if not abs(c[k]) <= limits[k]:
            f.append(f"{k} {c[k]:+.4f}")
    for k in ("env_max_db", "lsd_db"):
        if not c[k] <= limits[k]:
            f.append(f"{k} {c[k]:.3f}")
    return f


def stat_keys(slot):
    return [k for k in STAT if k != "pitch_cents" or slot.pitched]


def stat_failures(pairs, refs, candidate, keys):
    """pairs: {(a, b) sorted: compare JSON} over refs + [candidate]."""
    members = list(refs) + [candidate]
    f, margins = [], {}
    for k in keys:
        factor, floor = STAT[k]

        def med(m):
            return statistics.median(abs(pairs[tuple(sorted((m, o)))][k] or 0.0)
                                     for o in members if o != m)
        spread = max(med(r) for r in refs)
        limit = factor * spread + floor
        got = med(candidate)
        margins[k] = (got, limit)
        if not got <= limit:
            f.append(f"{k}: {got:.3g} > {limit:.3g} (upstream spread {spread:.3g})")
    return f, margins


# --- the comparisons, cached per session ----------------------------------------------

_cache = {}


def _tag(*parts):
    return "_".join(str(p) for p in parts).replace(" ", "")


def native_case(tmp, slot, note, point):
    """Reference (unseeded: the shared initial state) and fm1 at the native
    rate, compared.

    Chiptune: upstream bypasses the LPG in clocked mode, the wrapper keeps it.
    At Colour 1 the LPG has no filter (hf_bleed = 1) and at velocity 127 its
    gain settles to 1 within a few blocks, so from 10 ms on only the engine
    is compared (reference-plaits.md, intentional difference 7)."""
    key = ("native", slot.index, note, point)
    if key in _cache:
        return _cache[key]
    tag = _tag(slot.index, note, *point)
    ref, fm1 = tmp / f"ref_{tag}.wav", tmp / f"fm1_{tag}.wav"
    extra = ["--max-lag-ms", "2" if slot.engine == "sixop" else "1"]
    if slot.env == "chip":
        info = run_all([ref_cmd(ref, slot, note, point, level=1.0, colour=1.0),
                        fm1_cmd(fm1, slot, note, point, velocity=127, colour=1.0)])[0]
        extra += ["--from", "0.01", "--to", GATE]
    elif slot.engine == "sixop":             # the key depends on the patch's transpose
        info = _run(ref_cmd(ref, slot, note, point))
        _run(fm1_cmd(fm1, slot, played_key(slot, note, info), point))
    else:
        info = run_all([ref_cmd(ref, slot, note, point), fm1_cmd(fm1, slot, note, point)])[0]
    cmps = [cmp_cmd(ref, fm1, slot.gain, *extra)]
    if slot.engine == "macro-heavy" and slot.model == 0:     # string machine: AUX is R
        cmps.append(cmp_cmd(ref, fm1, slot.gain, *extra, "--ref-channel", 1, "--fm1-channel", 1))
    _cache[key] = (info, run_all(cmps))
    return _cache[key]


def stat_members(tmp, slot, note, point):
    """Seeded upstream renders of a held note (cached)."""
    refs = []
    cmds = []
    for s in SEEDS:
        r = tmp / f"seed{s}_{_tag(slot.index, note, *point)}.wav"
        refs.append(r)
        if not r.exists():
            cmds.append(ref_cmd(r, slot, note, point, seconds=STAT_SECONDS, gate=STAT_SECONDS,
                                seed=s))
    run_all(cmds)
    return refs


def stat_case(tmp, slot, note, point, name="fm1", key_offset=0, params=None):
    key = ("stat", name, slot.index, note, point)
    if key in _cache:
        return _cache[key]
    refs = stat_members(tmp, slot, note, point)
    cand = tmp / f"stat_{name}_{_tag(slot.index, note, *point)}.wav"
    _run(fm1_cmd(cand, slot, note + key_offset, point, seconds=STAT_SECONDS, gate=STAT_SECONDS,
                 params=params))
    pairs, cmds = [], []
    for a, b in itertools.combinations(refs + [cand], 2):
        pairs.append(tuple(sorted((a, b))))
        if cand in (a, b):
            r = b if a == cand else a
            cmds.append(cmp_cmd(r, cand, slot.gain, *STAT_ARGS))
        else:
            cmds.append(cmp_cmd(a, b, 1, *STAT_ARGS))
    res = dict(zip(pairs, run_all(cmds)))
    _cache[key] = (res, refs, cand)
    return _cache[key]


def rate_case(tmp, slot, note):
    """fm1 at 44,118 Hz in 64-frame blocks against the native reference, one
    second, Decay 0.3 so an LPG release ends inside it. Timing is measured
    from the note-off for released models, from the note-on for held ones."""
    key = ("rate", slot.index, note)
    if key in _cache:
        return _cache[key]
    point, seconds = slot.rate_point, 1.0
    gate = gate_for(slot, point, seconds)
    tag = _tag("rate", slot.index, note)
    ref, fm1 = tmp / f"ref_{tag}.wav", tmp / f"fm1_{tag}.wav"
    info = _run(ref_cmd(ref, slot, note, point, seconds=seconds, gate=gate, decay=0.3))
    _run(fm1_cmd(fm1, slot, played_key(slot, note, info), point, rate=FM1_RATE, frames=64,
                 seconds=seconds, gate=gate, decay=0.3))
    t0 = 0.0 if gate >= seconds else gate
    _cache[key] = _run(cmp_cmd(ref, fm1, slot.gain, "--t0", t0))
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


# --- native rate ---------------------------------------------------------------------------

@pytest.mark.parametrize("slot", SLOTS, ids=lambda s: s.id)
def test_matches_upstream_at_the_native_rate(wavs, slot):
    """Sample for sample (Six-Op closely), random points included, on the
    shared seed. Chiptune from 10 ms, past the LPG's attack."""
    failures = []
    for note in NOTES:
        for point in POINTS:
            _, res = native_case(wavs, slot, note, point)
            for ch, c in enumerate(res):
                f = (sixop_failures(c) if slot.engine == "sixop"
                     else exact_failures(c, pitched=slot.pitched))
                failures += [f"note {note} {point} ch{ch}: {x}" for x in f]
    assert not failures, "\n".join(failures)


# Chiptune's randomness is which note of the arpeggio plays first (random
# mode, TIMBRE 0.8): a discrete choice, not a distribution to compare, so it
# is checked on the shared seed only.
STAT_SLOTS = [s for s in SLOTS if s.random and s.env != "chip"]


@pytest.mark.parametrize("slot", STAT_SLOTS, ids=lambda s: s.id)
def test_random_engines_match_seeded_upstream_statistically(wavs, slot):
    """Without the shared seed, the fm1 render is no outlier among upstream
    renders with five other seeds. Measures: level, envelope in 50 ms
    windows, band spectrum, spectral centroid, spectral-envelope shift, and
    pitch for the string."""
    failures = []
    for note in NOTES:
        for i in slot.random:
            pairs, refs, cand = stat_case(wavs, slot, note, POINTS[i])
            f, _ = stat_failures(pairs, refs, cand, stat_keys(slot))
            failures += [f"note {note} {POINTS[i]}: {x}" for x in f]
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


# --- the FM-1's rate --------------------------------------------------------------------------

@pytest.mark.parametrize("slot", [s for s in SLOTS if s.rate_pitch], ids=lambda s: s.id)
def test_rate_compensation_holds_pitch(wavs, slot):
    """At 44,118 Hz the wrappers raise the note by 12*log2(47,872.34/44,118)
    semitones: pitch within +/-5 cents of upstream, +/-12 for the string
    model (engines/plaits-heavy.md). Six-Op runs at the host rate itself."""
    failures = []
    for note in NOTES:
        c = rate_case(wavs, slot, note)
        if not abs(c["pitch_cents"]) <= slot.rate_pitch:
            failures.append(f"note {note}: pitch {c['pitch_cents']:+.2f} cents")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("slot", [s for s in SLOTS if s.rate_timing], ids=lambda s: s.id)
def test_rate_compensation_envelope_timing(wavs, slot):
    """The wrappers leave time constants alone at 44,118 Hz, so envelopes set
    per sample or per 12-sample block run 47,872.34/44,118 = 1.085 times
    long: the LPG, the drums, speech words. Modal's resonators decay by Q,
    so between 1.0 and 1.085. Six-Op runs at the host rate: 1.0. Measured as
    the time stretch of the envelope after the note-off (or note-on)."""
    method, lo, hi = slot.rate_timing
    failures = []
    for note in NOTES:
        c = rate_case(wavs, slot, note)
        s = rate_stretch(slot, c)
        if not (s is not None and lo <= s <= hi):
            failures.append(f"note {note}: {method} stretch {s} not in [{lo:.3f}, {hi:.3f}]")
    assert not failures, "\n".join(failures)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="reference-plaits.md finding 3: NoiseEngine's TIMBRE "
                   "clock is NoteToFrequency(timbre), not of the note, so the rate "
                   "compensation misses it and it runs 1.41 semitones low at 44,118 Hz")
def test_noise_clock_follows_the_rate(wavs):
    """The filtered-noise model's spectrum at 44,118 Hz, against upstream's
    at its own rate: TIMBRE 0.5 puts its clock (sample-and-hold noise) in
    the audio band. The shift of the spectral envelope, median against five
    seeded upstream renders of a held note, would be near 0 if the clock
    were compensated."""
    slot = BY_INDEX[17]
    shifts = _noise_clock_shifts(wavs, slot, (0.5, 0.5, 0.2))
    assert all(abs(s) < 20.0 for s in shifts), shifts


def test_noise_filter_follows_the_rate(wavs):
    """The same model with the clock at the top of its range (TIMBRE 1):
    then the note-tracking filter shapes the spectrum, and it is on pitch at
    44,118 Hz. So the shift above is the clock alone."""
    slot = BY_INDEX[17]
    shifts = _noise_clock_shifts(wavs, slot, (0.5, 1.0, 0.8))
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
    a, b = wavs / "aligned.wav", wavs / "literal.wav"
    run_all([ref_cmd(a, slot, 57, POINTS[0]), ref_cmd(b, slot, 57, POINTS[0], extra=["--literal"])])
    assert _onset(a) == 0
    assert _onset(b) == 48


def test_sixop_applies_the_patch_transpose_plaits_ignores(wavs):
    """Six-Op plays each patch at its own transpose (DX7 C3 = 24); Plaits
    ignores it. At the same key the fm1 note sits (transpose - 24) semitones
    from upstream's, and that is the only pitch difference."""
    slot = BY_INDEX[2]
    point = (0.2, 0.5, 0.5)                   # bank 1, slot 6, "BASS    1"
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
    ref, fm1 = wavs / "chip_lpg_ref.wav", wavs / "chip_lpg_fm1.wav"
    run_all([ref_cmd(ref, slot, 57, POINTS[0]), fm1_cmd(fm1, slot, 57, POINTS[0])])
    held = _run(cmp_cmd(ref, fm1, slot.gain, "--from", "0.05", "--to", "0.25"))
    tail = _run(cmp_cmd(ref, fm1, slot.gain, "--from", "0.5", "--to", "0.6"))
    assert held["ncc"] > 0.95 and held["err_dbfs"] > -60   # the same notes, through the LPG
    assert tail["level_db"] < -20                          # released here, held upstream


@pytest.mark.parametrize("index,point", [(15, (0.5, 0.8, 0.2)), (19, (0.2, 0.5, 0.8)),
                                         (21, (0.2, 0.5, 0.8))],
                         ids=["speech-word", "string", "bass-drum"])
def test_added_release_after_note_off(wavs, index, point):
    """The self-enveloped models fade at note-off with the LPG's release
    curve (plaits-heavy.md). Upstream, LEVEL falling to 0 ends a speech word
    at once (the accent is the word's gain on every block), and leaves drums
    and strings ringing (they read the accent at the trigger)."""
    slot = BY_INDEX[index]
    ref, fm1 = wavs / f"rel_ref_{index}.wav", wavs / f"rel_fm1_{index}.wav"
    run_all([ref_cmd(ref, slot, 57, point, gate=GATE, decay=0.3),
             fm1_cmd(fm1, slot, 57, point, gate=GATE, decay=0.3)])
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
    # at POINTS[1] unless NEGATIVE_POINT says otherwise
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


@pytest.mark.parametrize("name", NEGATIVE)
def test_criteria_reject(wavs, name):
    """Each deliberate error fails the sample-exact or Six-Op criteria. (The
    Six-Op limit: how small a Brightness error it sees depends on the patch;
    see reference-plaits.md.)"""
    index, params, ref_offset = NEGATIVE[name]
    slot = BY_INDEX[index]
    point, note = NEGATIVE_POINT.get(name, POINTS[1]), 57
    ref, fm1 = wavs / f"neg_ref_{name}.wav", wavs / f"neg_fm1_{name}.wav"
    info = _run(ref_cmd(ref, slot, note + ref_offset, point))
    _run(fm1_cmd(fm1, slot, played_key(slot, note, info), point, params=params))
    c = _run(cmp_cmd(ref, fm1, slot.gain, "--max-lag-ms", "2" if slot.engine == "sixop" else "1"))
    f = sixop_failures(c) if slot.engine == "sixop" else exact_failures(c)
    assert f, f"{name} passed: {c}"


NEGATIVE_STAT = {
    # name: (slot, key offset, fm1 parameters or None)
    "noise-a-semitone-sharp": (17, 1, None),
    "string-a-semitone-sharp": (19, 1, None),
    "particle-an-octave-sharp": (18, 12, None),
    "swarm-as-noise": (16, 0, "Model=6"),
    "hihat-as-snare": (23, 0, "Model=11"),
}


@pytest.mark.parametrize("name", NEGATIVE_STAT)
def test_statistical_criteria_reject(wavs, name):
    """Each deliberate error fails the statistical criteria at one point or
    more. (Their limit: a particle cloud a semitone sharp passes; see
    reference-plaits.md.)"""
    index, offset, model = NEGATIVE_STAT[name]
    slot = BY_INDEX[index]
    failures = []
    for note in NOTES:
        for i in slot.random:
            params = fm1_params(slot, POINTS[i])
            if model:
                params[0] = model
            pairs, refs, cand = stat_case(wavs, slot, note, POINTS[i], name=name,
                                          key_offset=offset, params=params)
            failures += stat_failures(pairs, refs, cand, stat_keys(slot))[0]
    assert failures, f"{name} passed"


# --- report -------------------------------------------------------------------------------

def _fmt(v, p=3):
    return "n/a" if v is None else f"{v:.{p}f}"


def report(tmp):
    """Print the per-slot tables of engines/reference-plaits.md."""
    print("Native rate (worst of 6 cases; limits in the test)")
    print("| # | Upstream | fm1 | Criteria | Error dBFS / NCC, lag | Gain dB | Env max dB | "
          "Pitch cents | LSD dB |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for slot in SLOTS:
        rows = [c for n in NOTES for p in POINTS for c in native_case(tmp, slot, n, p)[1]]

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
        print(f"| {slot.index} | {slot.upstream} | {model} | {crit} | {first} | "
              f"{_fmt(worst('gain_db'), 4)} | {_fmt(worst('env_max_db'))} | "
              f"{_fmt(worst('pitch_cents') if slot.pitched else None)} | {_fmt(worst('lsd_db'))} |")
    print()
    print("Statistical (fm1 median distance / limit, the point nearest its limit)")
    print("| # | Upstream | " + " | ".join(STAT) + " |")
    print("| --- | --- | " + " | ".join("---" for _ in STAT) + " |")
    for slot in STAT_SLOTS:
        worst = {}
        for note in NOTES:
            for i in slot.random:
                pairs, refs, cand = stat_case(tmp, slot, note, POINTS[i])
                for k, (got, lim) in stat_failures(pairs, refs, cand, stat_keys(slot))[1].items():
                    if k not in worst or got / lim > worst[k][0] / worst[k][1]:
                        worst[k] = (got, lim)
        print(f"| {slot.index} | {slot.upstream} | " + " | ".join(
            f"{worst[k][0]:.3g} / {worst[k][1]:.3g}" if k in worst else "–" for k in STAT) + " |")
    print()
    print("44,118 Hz (A2 / A4)")
    print("| # | Upstream | Pitch cents (limit) | Stretch (method, range) | Level dB | LSD dB |")
    print("| --- | --- | --- | --- | --- | --- |")
    for slot in SLOTS:
        cs = [rate_case(tmp, slot, n) for n in NOTES]
        pitch = " / ".join(f"{c['pitch_cents']:+.2f}" for c in cs)
        lim = f"±{slot.rate_pitch:g}" if slot.rate_pitch else "not held"
        if slot.rate_timing:
            m, lo, hi = slot.rate_timing
            st = " / ".join(_fmt(rate_stretch(slot, c)) for c in cs) + f" ({m}, {lo:.3f}..{hi:.3f})"
        else:
            st = " / ".join(_fmt(c["stretch"]) for c in cs) + " (not held)"
        print(f"| {slot.index} | {slot.upstream} | {pitch} ({lim}) | {st} | "
              + " / ".join(f"{c['level_db']:+.2f}" for c in cs) + " | "
              + " / ".join(f"{c['lsd_db']:.2f}" for c in cs) + " |")


if __name__ == "__main__":
    import tempfile
    if "--report" not in sys.argv:
        sys.exit("usage: python tests/test_engines_reference_plaits.py --report")
    subprocess.run(["make", "-C", str(ENGINES), "-j4"], check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory() as d:
        report(Path(d))
