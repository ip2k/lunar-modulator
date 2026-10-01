"""Tests for the heavy Plaits engines: Macro Heavy (engines/src/mi_macro_heavy.cc)
and Six-Op FM (engines/src/mi_sixop.cc). See engines/plaits-heavy.md.

Every model and patch renders one clean, audible note; tonal models hold their
tuning where a clean fundamental exists; a chord at (and past) the voice cap
stays under the bus limiter; releases end; output is deterministic and
independent of the host's block size; instance sizes stay bounded.
"""
import json
import math
import re
import subprocess
import wave

import pytest

from tests.engine_helpers import (ENGINES, RATE, cents, pitch_hz,  # noqa: F401
                                  render, renderer, rms)

HEAVY_MODELS = ["Str Machine", "Chords", "Speech", "Formant", "Additive", "Swarm",
                "Filt Noise", "Particle", "String", "Modal", "Bass Drum", "Snare",
                "Hi-Hat"]
HEAVY_VOICES = 4
SIXOP_VOICES = 8
RESOURCES = ENGINES / "third_party" / "mutable" / "plaits" / "resources.cc"


def syx_banks():
    """The three packed DX7 banks from Plaits' resources.cc, as byte lists."""
    src = RESOURCES.read_text()
    banks = []
    for b in range(3):
        m = re.search(r"const uint8_t syx_bank_%d\[\] = \{(.*?)\};" % b, src, re.S)
        banks.append([int(x) for x in re.findall(r"\d+", m.group(1))])
    return banks


def patch_transpose(index):
    data = syx_banks()[index // 32]
    return min(data[(index % 32) * 128 + 117] & 0x7F, 48)


def lowpass(samples, cutoff_hz, passes=4):
    """Cascaded one-pole low-pass, so zero crossings follow the fundamental of a
    tone whose upper partials would otherwise add crossings."""
    a = 1.0 - math.exp(-2.0 * math.pi * cutoff_hz / RATE)
    y = list(samples)
    for _ in range(passes):
        s = 0.0
        for i, v in enumerate(y):
            s += a * (v - s)
            y[i] = s
    return y


def stereo(wav_path):
    with wave.open(str(wav_path), "rb") as w:
        raw = w.readframes(w.getnframes())
    frames = [(int.from_bytes(raw[i:i + 2], "little", signed=True),
               int.from_bytes(raw[i + 2:i + 4], "little", signed=True))
              for i in range(0, len(raw), 4)]
    return [f[0] / 32767.0 for f in frames], [f[1] / 32767.0 for f in frames]


def run_raw(renderer, *args):
    res = subprocess.run([str(renderer), *args], check=True, capture_output=True, text=True)
    return json.loads(res.stdout)


# --- registry ------------------------------------------------------------------

def test_registry_lists_heavy_engines(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True,
                         capture_output=True, text=True).stdout
    engines = {e["id"]: e for e in json.loads(out)}
    heavy, sixop = engines["macro-heavy"], engines["sixop"]
    assert heavy["kind"] == sixop["kind"] == "sound"
    assert heavy["max_voices"] == HEAVY_VOICES and sixop["max_voices"] == SIXOP_VOICES
    for e in (heavy, sixop):
        assert "Plaits" in e["credits"] and "MIT" in e["credits"]
        # docs/11 §7: no Mutable Instruments module names in ids or names.
        for banned in ("plaits", "braids", "rings", "clouds", "elements", "mutable"):
            assert banned not in e["id"].lower() and banned not in e["name"].lower()
        assert all(p["page"] in (0, 1) for p in e["params"])
        assert sum(p["page"] == 0 for p in e["params"]) <= 4
        assert all(len(p["name"]) <= 12 for p in e["params"])
    model = next(p for p in heavy["params"] if p["name"] == "Model")
    assert model["max"] == len(HEAVY_MODELS) - 1
    patch = next(p for p in sixop["params"] if p["name"] == "Patch")
    assert patch["max"] == 95


def test_patch_names_match_the_banks():
    """kPatchNames in mi_sixop.cc is "<bank> <name>" of every patch in
    syx_bank_0..2 (bytes 118..127 of each packed patch)."""
    src = (ENGINES / "src" / "mi_sixop.cc").read_text()
    table = src[src.index("kPatchNames[kNumPatches] = {"):]
    table = table[:table.index("};")]
    ours = re.findall(r'"((?:[^"\\]|\\.)*)"', table)
    expected = []
    for b, data in enumerate(syx_banks()):
        for i in range(32):
            name = bytes(x & 0x7F for x in data[i * 128 + 118:i * 128 + 128])
            expected.append(f"{b + 1} {name.decode('ascii').rstrip()}")
    assert ours == expected
    assert all(len(n) <= 12 for n in ours)


# --- every model and patch renders cleanly ---------------------------------------

@pytest.mark.parametrize("model", range(len(HEAVY_MODELS)), ids=HEAVY_MODELS)
def test_every_heavy_model_sounds_cleanly(renderer, tmp_path, model):
    summary, left, _ = render(renderer, tmp_path, "macro-heavy",
                              params=[f"Model={model}"], notes=["0.05:57:100:0.8"])
    assert summary["nonfinite"] == 0 and summary["raw_clipped"] == 0
    assert summary["raw_peak"] > 0.02
    # Percussive models are loudest just after the trigger.
    assert rms(left, 0.05, 0.35) > 1e-3


@pytest.mark.parametrize("patch", range(96))
def test_every_sixop_patch_sounds_cleanly(renderer, tmp_path, patch):
    summary, left, _ = render(renderer, tmp_path, "sixop", params=[f"Patch={patch}"],
                              notes=["0.05:57:100:0.8"], seconds=1.0)
    assert summary["nonfinite"] == 0 and summary["raw_clipped"] == 0
    assert summary["raw_peak"] > 0.005


# --- tuning, only where a clean fundamental exists ---------------------------------
#
# Chords and string machine play several notes per key, the drums, noise and
# particle models have no stable fundamental, and the formant/speech models are
# pulse trains through resonances: those are only checked after a low-pass that
# leaves the fundamental. A2 is left out because the low-passed fundamental of
# the physical models is too weak there for zero crossings.

@pytest.mark.parametrize("name,params,tolerance", [
    ("additive", ["Model=4", "Timbre=0", "Harmonics=0"], 5.0),
    ("formant", ["Model=3"], 5.0),
    ("swarm", ["Model=5", "Harmonics=0"], 5.0),
    ("speech-vowel", ["Model=2", "Harmonics=0"], 5.0),
    # Structure 0.25 is where the modal resonator has no stiffness, so its
    # first mode sits on f0 (elsewhere Plaits tunes the third mode instead).
    ("modal", ["Model=9", "Harmonics=0.25", "Morph=0.8"], 5.0),
    # The string model reads 6-9 cents sharp here, at Plaits' own 47,872 Hz,
    # where it runs at any host rate (engines/plaits-heavy.md): an upstream
    # property of these settings.
    ("string", ["Model=8", "Harmonics=0.25", "Morph=0.8"], 12.0),
])
@pytest.mark.parametrize("key", [57, 69, 81])
def test_heavy_tuning(renderer, tmp_path, name, params, tolerance, key):
    ref = 440.0 * 2 ** ((key - 69) / 12)
    _, left, _ = render(renderer, tmp_path, "macro-heavy", params=params,
                        notes=[f"0:{key}:100:1.4"], seconds=1.2)
    # The modal model's partials rise with their order here (A4: -48, -42.5,
    # -39.4 dB), so four one-pole passes leave the second as strong as the
    # first, and the zero crossings counted the octave at A4 (+1200.4 cents)
    # once the model ran at Plaits' own rate; eight passes put it 22 dB under.
    passes = 8 if name == "modal" else 4
    f = pitch_hz(lowpass(left, 1.5 * ref, passes), 0.3, 0.6)
    assert abs(cents(f, ref)) < tolerance


@pytest.mark.parametrize("patch", [
    49,   # 2 MARIMBA, transpose C3 (none)
    36,   # 2 *Mark III, transpose C2: an octave down
    51,   # 2 GLOKENSPL, transpose C4: an octave up
])
@pytest.mark.parametrize("key", [57, 69])
def test_sixop_tuning_follows_patch_transpose(renderer, tmp_path, patch, key):
    ref = 440.0 * 2 ** ((key + patch_transpose(patch) - 24 - 69) / 12)
    _, left, _ = render(renderer, tmp_path, "sixop", params=[f"Patch={patch}"],
                        notes=[f"0:{key}:100:1.0"], seconds=0.8)
    f = pitch_hz(lowpass(left, 1.5 * ref), 0.2, 0.4)
    assert abs(cents(f, ref)) < 5.0


# --- polyphony under the limiter ---------------------------------------------------

@pytest.mark.parametrize("model", [0, 1, 4, 5, 7, 8, 10, 12])
@pytest.mark.parametrize("extra", [0, 2])
def test_heavy_chord_at_and_past_the_voice_cap(renderer, tmp_path, model, extra):
    notes = [f"{0.01 * k}:{48 + 3 * k}:127:1.0" for k in range(HEAVY_VOICES + extra)]
    summary, left, _ = render(renderer, tmp_path, "macro-heavy",
                              params=[f"Model={model}", "Morph=0.8", "Volume=1"], notes=notes)
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    assert summary["peak"] <= 0.98 + 1e-6
    assert rms(left, 0.05, 0.5) > 1e-3


@pytest.mark.parametrize("patch", [0, 32, 65, 90])
@pytest.mark.parametrize("extra", [0, 3])
def test_sixop_chord_at_and_past_the_voice_cap(renderer, tmp_path, patch, extra):
    notes = [f"0:{40 + 4 * k}:127:1.0" for k in range(SIXOP_VOICES + extra)]
    summary, left, _ = render(renderer, tmp_path, "sixop",
                              params=[f"Patch={patch}", "Volume=1"], notes=notes)
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    assert summary["peak"] <= 0.98 + 1e-6
    assert rms(left, 0.1, 0.9) > 1e-3


# --- releases -----------------------------------------------------------------------

@pytest.mark.parametrize("engine,params", [
    ("macro-heavy", ["Model=4", "Decay=0.2"]),                 # low-pass gate
    ("macro-heavy", ["Model=0", "Decay=0.2"]),                 # low-pass gate, stereo
    # Self-enveloped models, Morph=1: the string and modal models then ring
    # (almost) forever on Plaits; the note-off release must still end them.
    ("macro-heavy", ["Model=8", "Morph=1", "Decay=0.2"]),
    ("macro-heavy", ["Model=9", "Morph=1", "Decay=0.2"]),
    ("macro-heavy", ["Model=2", "Harmonics=0.9", "Decay=0.2"]),  # speech words
    ("sixop", ["Patch=32"]),                                   # 2 E.PIANO 1
    ("sixop", ["Patch=89"]),                                   # 3 STRINGS 2
])
def test_release_ends_notes(renderer, tmp_path, engine, params):
    _, left, _ = render(renderer, tmp_path, engine, params=params,
                        notes=["0:60:100:0.3", "0:64:100:0.3"], seconds=3.0)
    assert rms(left, 0.05, 0.3) > 1e-3
    assert rms(left, 2.6, 3.0) < 1e-4


@pytest.mark.parametrize("engine,params", [
    ("macro-heavy", ["Model=9", "Morph=1", "Decay=0.2"]),     # self-enveloped
    ("macro-heavy", ["Model=4", "Decay=0.2"]),                # low-pass gate
    ("sixop", ["Patch=67"]),
])
def test_released_voices_are_freed(renderer, tmp_path, engine, params):
    """A faded voice must be freed, not merely silent: nothing else would stop
    it costing a full voice of CPU (at Morph=1 the modal model rings forever
    inside the engine). Freeing is only visible as time, so compare the render
    cost of the same chord released after 0.3 s and held for the whole render;
    a leak would make them equal, freeing makes the released one several times
    cheaper."""
    cap = HEAVY_VOICES if engine == "macro-heavy" else SIXOP_VOICES
    base = ["--engine", engine, "--seconds", "20"]
    for p in params:
        base += ["--param", p]

    def cost(duration):
        notes = []
        for k in range(cap):
            notes += ["--note", f"0:{48 + 3 * k}:100:{duration}"]
        return min(run_raw(renderer, *base, *notes)["ns_per_block"] for _ in range(3))

    assert cost(0.3) < 0.5 * cost(30.0)


# --- behaviour specific to the wrappers ---------------------------------------------

def test_string_machine_is_stereo_and_others_mono(renderer, tmp_path):
    _, _, wav = render(renderer, tmp_path, "macro-heavy", params=["Model=0"],
                       notes=["0:57:100:1.0"], name="strm")
    left, right = stereo(wav)
    assert rms(right, 0.2, 0.8) > 1e-3
    assert max(abs(a - b) for a, b in zip(left, right)) > 0.01
    _, _, wav = render(renderer, tmp_path, "macro-heavy", params=["Model=4"],
                       notes=["0:57:100:1.0"], name="add")
    left, right = stereo(wav)
    assert left == right


@pytest.mark.parametrize("frames", [64, 7])
def test_string_machine_entered_later_renders_as_if_created_in_it(renderer, tmp_path, frames):
    """Outside the string machine the right channel's resampler stands
    still, and on a change into it takes the left one's state
    (mi_macro_heavy.cc). An instance that plays nothing as Additive and is
    switched to the string machine at 0.1 s must then render exactly what an
    instance created as the string machine renders, both channels: without
    the copy the right channel's resampler is out of step with the left."""
    outs = []
    for name, params, extra in (("switched", ["Model=4"], ["--param-at", "0.1:Model=0"]),
                                ("created", ["Model=0"], [])):
        wav = tmp_path / f"{name}.wav"
        args = ["--engine", "macro-heavy", "--seconds", "0.6", "--frames", str(frames),
                "--note", "0.2:57:100:0.3", "--out", str(wav), *extra]
        for p in params:
            args += ["--param", p]
        run_raw(renderer, *args)
        outs.append(wav.read_bytes())
    left, right = stereo(tmp_path / "created.wav")
    assert rms(right, 0.25, 0.45) > 1e-3 and left != right
    assert outs[0] == outs[1]


def test_sixop_stolen_held_voice_attacks_again(renderer, tmp_path):
    """fm::Voice only starts its envelopes on a gate edge. When every voice is
    held and a new key steals one, the wrapper must still give it a fresh
    attack. MARIMBA has decayed to near silence after 1.5 s of holding."""
    held = [f"0:{40 + 3 * k}:100:3.0" for k in range(SIXOP_VOICES)]
    _, left, _ = render(renderer, tmp_path, "sixop", params=["Patch=49"],
                        notes=held + ["1.5:84:100:1.0"], seconds=2.0)
    before = rms(left, 1.3, 1.5)
    after = rms(left, 1.5, 1.7)
    assert after > 1e-3 and after > 10 * before


@pytest.mark.parametrize("patch", [32, 49])   # 2 E.PIANO 1, 2 MARIMBA: fast attacks
def test_sixop_note_sounds_from_its_first_block(renderer, tmp_path, patch):
    """fm::Voice spends the first render after a patch is loaded on Setup()
    and renders nothing. The wrapper runs that render at note-on, so a note on
    a newly loaded patch sounds from its first 16-sample block rather than
    starting with a blank one (which would read exactly 0 here). Checked at
    Plaits' own rate, where the resampler passes the wrapper's blocks
    through: at 44,118 Hz its 30-sample delay would hide the first block."""
    wav = tmp_path / "first.wav"
    run_raw(renderer, "--engine", "sixop", "--param", f"Patch={patch}", "--note", "0:69:127:0.05",
            "--seconds", "0.05", "--rate", "47872.34", "--out", str(wav))
    left, _ = stereo(wav)
    assert max(abs(x) for x in left[:16]) > 0.01


def test_speech_voices_all_read_the_shared_word_bank(renderer, tmp_path):
    """The speech voices share one word bank, allocated in voice 0's arena
    (mi_macro_heavy.cc). A four-note chord in word mode uses all four voices;
    each must speak, so the chord carries about the energy of the four notes
    rendered one at a time (each of those on voice 0). A voice without the
    bank would be disabled and silent, leaving about half of it."""
    params = ["Model=2", "Harmonics=0.9", "Morph=0.4"]
    keys = [57, 60, 64, 67]
    singles = []
    for k in keys:
        _, left, _ = render(renderer, tmp_path, "macro-heavy", params=params,
                            notes=[f"0:{k}:100:1.0"], seconds=1.0, name=f"one{k}")
        singles.append(left)
    summary, chord, _ = render(renderer, tmp_path, "macro-heavy", params=params,
                               notes=[f"0:{k}:100:1.0" for k in keys], seconds=1.0,
                               name="chord")
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    total = [sum(s) for s in zip(*singles)]
    assert rms(chord, 0.0, 0.8) > 0.8 * rms(total, 0.0, 0.8)


def last_loud(samples, threshold=0.005):
    for i in range(len(samples) - 1, -1, -1):
        if abs(samples[i]) > threshold:
            return i / RATE
    return 0.0


def test_word_speed_changes_word_length(renderer, tmp_path):
    """Speech in word mode (HARMONICS high) replays a whole word per trigger;
    Word Speed is Plaits' speed control (the MORPH attenuverter there)."""
    base = ["Model=2", "Harmonics=0.75", "Morph=0.3", "Decay=1"]
    _, fast, _ = render(renderer, tmp_path, "macro-heavy", params=base + ["Word Speed=0.5"],
                        notes=["0:57:100:2.5"], seconds=3.0, name="fast")
    _, slow, _ = render(renderer, tmp_path, "macro-heavy", params=base + ["Word Speed=-0.5"],
                        notes=["0:57:100:2.5"], seconds=3.0, name="slow")
    assert 0.05 < last_loud(fast) < last_loud(slow)


def test_output_is_independent_of_host_block_size(renderer, tmp_path):
    """Engines must accept any 1..max_frames; the internal 12- and 16-sample
    blocks make the output identical whatever the host calls with."""
    for engine, params in (("macro-heavy", ["Model=7"]), ("sixop", ["Patch=11"])):
        outs = []
        for frames in (64, 7, 1):
            wav = tmp_path / f"{engine}-{frames}.wav"
            args = ["--engine", engine, "--seconds", "0.5", "--frames", str(frames),
                    "--note", "0:60:100:2", "--note", "0:67:90:2", "--out", str(wav)]
            for p in params:
                args += ["--param", p]
            run_raw(renderer, *args)
            outs.append(wav.read_bytes())
        assert outs[0] == outs[1] == outs[2], engine


@pytest.mark.parametrize("engine,params", [
    ("macro-heavy", ["Model=7", "Timbre=0.3"]),   # particle: random numbers
    ("macro-heavy", ["Model=8"]),                 # string: dispersion noise
    ("sixop", ["Patch=62"]),
])
def test_rendering_is_deterministic(renderer, tmp_path, engine, params):
    args = dict(params=params, notes=["0:60:90:0.5", "0.2:64:90:0.5"])
    _, _, a = render(renderer, tmp_path, engine, name="a", **args)
    _, _, b = render(renderer, tmp_path, engine, name="b", **args)
    assert a.read_bytes() == b.read_bytes()


def test_instance_sizes_are_bounded(renderer, tmp_path):
    heavy, _, _ = render(renderer, tmp_path, "macro-heavy", seconds=0.1)
    sixop, _, _ = render(renderer, tmp_path, "sixop", seconds=0.1)
    # Tight on purpose: the resamplers are 1,288 B each (fm1_resampler.h),
    # and these bounds are what catches one per voice instead of one per
    # output channel per instance (resampling is linear, so the renders
    # cannot tell). Each leaves less than one resampler of room.
    # Macro Heavy: four voices, each with a 16 KB arena (the particle engine's
    # diffuser alone takes all of it), and two resamplers (the string
    # machine's L and R). 71,088 B on a 64-bit host, 70,880 B on 32-bit
    # targets (plaits-heavy.md); a resampler per voice would add 5,152 B.
    assert heavy["instance_bytes"] < 72_000
    # Six-Op FM: eight FMVoices, one shared algorithm table and one
    # resampler. 12,528 B on a 64-bit host, 10,796 B on 32-bit targets; a
    # resampler per voice would add 10,304 B.
    assert sixop["instance_bytes"] < 13_500
