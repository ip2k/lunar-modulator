"""Page 3 of Macro and Macro Heavy: Plaits' internal decay envelope (Env Pitch,
Env Timbre, Env Morph, its three attenuverters) and the low-pass gate's modes
(LPG: Gate, Ping, Off). engines/src/mi_plaits_env.h has what they do.

- Against upstream plaits::Voice (fm1-ref-plaits, engines/reference-plaits.md),
  sample for sample at Plaits' own rate:
  - the attenuverters with TRIG and LEVEL patched (LPG Gate), on all 21 slots
    the two engines wrap, speech prosody and Chip's own envelope included;
  - LPG Ping as the module with TRIG alone patched, with the attenuverters;
  - LPG Off as the module with neither patched (LPG bypassed), while held;
  - and the same through the resampler at the FM-1's 44,118 Hz.
- At their defaults the page changes nothing: explicit defaults, -0 and NaN
  render the bytes of a render that never touches the page. (The reference
  suite, unchanged, holds the default path to upstream.)
- What upstream cannot show: Ping ignores the key's length, Off releases at
  key-up over Decay, velocity scales Ping and Off, the envelope sweeps the
  pitch, Chip's own envelope decays.
- Robustness: any value (min, max, beyond, NaN) on every model, instance
  memory filled with 0x00, 0xA5 or 0xFF, the page turned while notes sound,
  silence with no notes. The engine-wide tests (test_engine_host.py) cover
  the page too, as they do every parameter.
"""
import json
import subprocess

import pytest

from tests.engine_helpers import RATE, cents, pitch_hz, render, renderer, rms  # noqa: F401
from tests.test_engines_reference_plaits import (BY_INDEX, FM1_HZ, FM1_RATE, GATE, NATIVE,
                                                 NATIVE_HZ, NOTES, POINTS, REF, RENDER, fm1_cmd,
                                                 fm1_params, gate_for,
                                                 host_failures, lsb_diff, native_point, ref_cmd,
                                                 run_all)

PAGE3 = ["Env Pitch", "Env Timbre", "Env Morph", "LPG"]
LPG_MODES = ["Gate", "Ping", "Off"]
GATE_MODE, PING, OFF = 0, 1, 2
ENV = (0.5, 0.7, -0.6)          # Env Pitch, Env Timbre, Env Morph
MODELS = {"macro": 8, "macro-heavy": 13}

# The slots each comparison can reach. Six-Op has no low-pass gate and no
# page 3. Chip keeps a gate that upstream bypasses (compared from 10 ms at
# Colour 1, velocity 127, as the reference suite does). Self-enveloped models
# and speech take velocity as their accent, which upstream fixes at 0.8 when
# LEVEL is unpatched, so they are not compared on Ping or Off; the engines
# that read TRIG (swarm, noise, particle) behave otherwise with it unpatched,
# so not on Off either.
ENV_SLOTS = [s for s in BY_INDEX.values() if s.engine != "sixop"]
PING_SLOTS = [s for s in ENV_SLOTS if s.env == "lpg"]
OFF_SLOTS = [s for s in PING_SLOTS if s.index not in (16, 17, 18)]


def page3(env=(0, 0, 0), lpg=GATE_MODE):
    return [f"Env Pitch={env[0]}", f"Env Timbre={env[1]}", f"Env Morph={env[2]}", f"LPG={lpg}"]


def ref_extra(env, mode):
    return ["--mode", mode, "--fm-amount", env[0], "--timbre-amount", env[1],
            "--morph-amount", env[2]]


def stereo_channels(slot):
    return [0, 1] if slot.engine == "macro-heavy" and slot.model == 0 else [0]


def compare(tmp, tag, slot, note, point, env, lpg, mode, window=None, gate=None, ref_env=None):
    """fm1-render with page 3 against fm1-ref-plaits in the matching mode, both
    at Plaits' rate in its 12-sample blocks. The reference is written at
    fm1's scale (its host mode at Plaits' own rate, where the resampler
    passes samples through), so the two WAVs compare sample for sample: per
    channel, the lsb_diff of the reference suite over `window` seconds.
    ref_env: other attenuverters for the reference (the negative controls)."""
    ref, fm1 = tmp / f"ref_{tag}.wav", tmp / f"fm1_{tag}.wav"
    params = fm1_params(slot, point) + page3(env, lpg)
    if slot.env == "speech":   # upstream's word speed is the MORPH attenuverter
        params.append(f"Word Speed={env[2]}")
    host = ["--host-rate", NATIVE, "--host-frames", 12, "--host-gain", slot.gain]
    ref_env = env if ref_env is None else ref_env
    run_all([ref_cmd(ref, slot, note, point, gate=gate, extra=ref_extra(ref_env, mode) + host),
             fm1_cmd(fm1, slot, note, point, gate=gate, params=params)])
    return [native_lsb(ref, fm1, ch, window) for ch in stereo_channels(slot)]


def native_lsb(ref, fm1, ch, window):
    """lsb_diff at Plaits' rate: the window in samples of 47,872.34 Hz."""
    if window:
        window = tuple(t * NATIVE_HZ / FM1_HZ for t in window)   # lsb_diff counts at 44,118 Hz
    return lsb_diff(ref, fm1, ch, ch, window)


def failures_of(results, slot, label):
    out = []
    for ch, d in enumerate(results):
        out += [f"{label} ch{ch}: {x}" for x in host_failures(d)]
    return out


@pytest.fixture(scope="module")
def wavs(renderer, tmp_path_factory):  # noqa: F811
    assert REF.exists(), "make -C engines builds fm1-ref-plaits (mk/ref-plaits.mk)"
    return tmp_path_factory.mktemp("plaits-env")


def self_enveloped(engine, model):
    return engine == "macro-heavy" and model >= 8   # string, modal and the drums


def listing():
    out = subprocess.run([str(RENDER), "--list"], check=True, capture_output=True, text=True).stdout
    return {e["id"]: e for e in json.loads(out)}


# --- the page --------------------------------------------------------------------------

@pytest.mark.parametrize("engine", sorted(MODELS))
def test_page_three_is_the_envelope_and_the_gate(wavs, engine):
    """Four parameters on page 3, appended after the existing ones so their
    indices keep their meaning; attenuverters -1..1 at 0, LPG on Gate."""
    params = listing()[engine]["params"]
    assert [p["name"] for p in params[-4:]] == PAGE3
    assert all(p["page"] == 2 for p in params[-4:])
    assert all(p["page"] < 2 for p in params[:-4])
    assert [p["name"] for p in params[:4]] == ["Model", "Harmonics", "Timbre", "Morph"]
    for p in params[-4:-1]:
        assert (p["type"], p["min"], p["max"], p["def"]) == (0, -1, 1, 0)
    lpg = params[-1]
    assert (lpg["type"], lpg["min"], lpg["max"], lpg["def"]) == (1, 0, 2, 0)
    assert lpg["names"] == LPG_MODES


@pytest.mark.parametrize("engine", sorted(MODELS))
def test_page_three_at_its_defaults_changes_nothing(renderer, tmp_path, engine):  # noqa: F811
    """Explicit defaults, a negative zero, NaN (which falls back to the
    default) and an LPG value that rounds to Gate give the bytes of a render
    that never touches the page, on every model, through a chord past the
    voice cap, a bend and a knob turned mid-note."""
    chord = [f"{0.02 * i}:{40 + 5 * i}:{50 + 5 * i}:0.3" for i in range(14)]
    for model in range(MODELS[engine]):
        args = dict(notes=chord, seconds=0.8,
                    extra=["--bend", "0.1:5", "--param-at", "0.2:Timbre=0.8"])
        _, _, plain = render(renderer, tmp_path, engine, params=[f"Model={model}"],
                             name=f"plain{model}", **args)
        for i, explicit in enumerate([page3(), ["Env Pitch=-0", "Env Timbre=nan",
                                                "Env Morph=-0.0", "LPG=0.4"]]):
            _, _, same = render(renderer, tmp_path, engine, params=[f"Model={model}"] + explicit,
                                name=f"explicit{model}-{i}", **args)
            assert same.read_bytes() == plain.read_bytes(), (engine, model, explicit)


# --- against upstream, at Plaits' rate --------------------------------------------------

@pytest.mark.parametrize("slot", ENV_SLOTS, ids=lambda s: s.id)
def test_envelope_matches_upstream(wavs, slot):
    """The attenuverters with TRIG and LEVEL patched (LPG Gate), sample for
    sample at every reference point and both notes. Speech at its three
    points covers the envelope's fade into the word banks and the prosody the
    FM attenuverter sets there; Chip covers its own envelope (Env Timbre)."""
    failures = []
    for note in NOTES:
        for i, point in enumerate(POINTS):
            point = native_point(slot, point)
            env = ENV if slot.env != "chip" else (ENV[0], 0.3, ENV[2])
            window = (0.01, GATE) if slot.env == "chip" else None
            res = compare(wavs, f"env_{slot.index}_{note}_{i}", slot, note, point, env,
                          GATE_MODE, "trigger", window)
            failures += failures_of(res, slot, f"note {note} {tuple(point)}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("slot", PING_SLOTS, ids=lambda s: s.id)
def test_ping_matches_upstream_with_trig_alone(wavs, slot):
    """LPG Ping is the module with TRIG patched and LEVEL not: the gate is
    pinged at the note-on, and the key-up (at the same time as TRIG falls
    upstream) does not close it. Velocity 127, whose accent is 1."""
    failures = []
    for note in NOTES:
        for i, point in enumerate(POINTS):
            point = point._replace(velocity=127)
            res = compare(wavs, f"ping_{slot.index}_{note}_{i}", slot, note, point, ENV,
                          PING, "ping")
            failures += failures_of(res, slot, f"note {note} {tuple(point)}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("slot", OFF_SLOTS, ids=lambda s: s.id)
def test_off_matches_upstream_with_the_gate_bypassed(wavs, slot):
    """LPG Off while the key is held is the module with neither TRIG nor LEVEL
    patched, where Voice bypasses the gate: the engine's output at gain 1
    (velocity 127). Upstream's envelope does not run there, so the
    attenuverters stay at 0. After the key-up only fm1 releases."""
    failures = []
    for note in NOTES:
        for i, point in enumerate(POINTS):
            point = point._replace(velocity=127)
            res = compare(wavs, f"off_{slot.index}_{note}_{i}", slot, note, point, (0, 0, 0),
                          OFF, "free", window=(0, GATE))
            failures += failures_of(res, slot, f"note {note} {tuple(point)}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("name,lpg,mode,env_fm1,env_ref", [
    ("envelope-missing", GATE_MODE, "trigger", ENV, (0, 0, 0)),
    ("envelope-sign", GATE_MODE, "trigger", (0.5, 0.7, -0.6), (-0.5, -0.7, 0.6)),
    ("ping-as-gate", GATE_MODE, "ping", (0, 0, 0), (0, 0, 0)),
    ("off-as-gate", GATE_MODE, "free", (0, 0, 0), (0, 0, 0)),
])
def test_criteria_reject_a_wrong_mapping(wavs, name, lpg, mode, env_fm1, env_ref):
    """The comparisons above would catch an envelope not applied, applied
    with the wrong sign, or a mode driving the gate the wrong way."""
    slot, point = BY_INDEX[8], POINTS[0]._replace(velocity=127)
    res = compare(wavs, f"neg_{name}", slot, NOTES[0], point, env_fm1, lpg, mode,
                  window=(0, GATE), ref_env=env_ref)
    assert failures_of(res, slot, name), f"{name} passed the sample-for-sample criteria"


# --- against upstream, at the FM-1's rate ------------------------------------------------

@pytest.mark.parametrize("index,lpg,mode,env", [
    (8, GATE_MODE, "trigger", ENV), (6, GATE_MODE, "trigger", ENV), (20, GATE_MODE, "trigger", ENV),
    (8, PING, "ping", ENV), (6, PING, "ping", ENV),
    (8, OFF, "free", (0, 0, 0)), (6, OFF, "free", (0, 0, 0)),
])
def test_modes_match_upstream_resampled_at_the_fm1_rate(wavs, index, lpg, mode, env):
    """44,118 Hz in 64-frame blocks against upstream resampled the same way:
    within 1 LSB at every sample (the reference suite's host criterion), up
    to the key-up on Off."""
    slot = BY_INDEX[index]
    point = POINTS[1]._replace(velocity=127 if lpg != GATE_MODE else POINTS[1].velocity)
    tag = f"host_{index}_{lpg}"
    ref, fm1 = wavs / f"ref_{tag}.wav", wavs / f"fm1_{tag}.wav"
    run_all([ref_cmd(ref, slot, 57, point, host=True, extra=ref_extra(env, mode)),
             fm1_cmd(fm1, slot, 57, point, rate=FM1_RATE, frames=64,
                     params=fm1_params(slot, point) + page3(env, lpg))])
    window = (0, gate_for(slot, point)) if lpg == OFF else None
    failures = []
    for ch in stereo_channels(slot):
        failures += [f"ch{ch}: {x}" for x in host_failures(lsb_diff(ref, fm1, ch, ch, window))]
    assert not failures, "\n".join(failures)


# --- what upstream cannot show ------------------------------------------------------------

@pytest.mark.parametrize("engine,tone", [
    ("macro", ["Model=6", "Timbre=0", "Morph=0.5", "Harmonics=0.5"]),       # 2-op FM, a sine
    ("macro-heavy", ["Model=4", "Harmonics=0", "Timbre=0"]),                 # additive, a sine
])
@pytest.mark.parametrize("amount", [0.5, -0.5])
def test_env_pitch_sweeps_the_note_back_to_pitch(renderer, tmp_path, engine, tone, amount):  # noqa: F811
    """The envelope's square reaches the note: 0.5 is 0.236 x 48 = 11.3
    semitones at the trigger. With Decay 0.9 it has fallen to a fraction of a
    cent after 1.5 s, where the note is in tune again."""
    _, left, _ = render(renderer, tmp_path, engine, params=tone + ["Decay=0.9",
                        f"Env Pitch={amount}"], notes=["0:69:100:2.0"], seconds=2.0)
    early, late = pitch_hz(left, 0.01, 0.07), pitch_hz(left, 1.5, 0.4)
    assert abs(cents(late, 440.0)) < 5.0
    assert cents(early, late) * (1 if amount > 0 else -1) > 500.0


def test_env_timbre_on_chip_is_its_own_envelope(renderer, tmp_path):  # noqa: F811
    """On Chip, Env Timbre sets the chiptune engine's own decay, as on the
    module; at 0 a held note holds its level."""
    def ratio(amount):
        _, left, _ = render(renderer, tmp_path, "macro", name=f"chip{amount}",
                            params=["Model=3", "Colour=1", f"Env Timbre={amount}"],
                            notes=["0:57:127:1.0"], seconds=1.0)
        return rms(left, 0.7, 0.9) / rms(left, 0.02, 0.1)
    assert ratio(0) > 0.7
    assert ratio(0.5) < 0.1 and ratio(-0.5) < 0.1


@pytest.mark.parametrize("engine,model", [("macro", 4), ("macro", 0), ("macro-heavy", 1),
                                          ("macro-heavy", 9), ("macro-heavy", 10)])
def test_ping_ignores_the_key_length(renderer, tmp_path, engine, model):  # noqa: F811
    """A short tap and a long hold render the same note on Ping. Under the
    gate that is the same bytes, and the hold closes over Decay with the key
    still down, where Gate sustains it. The self-enveloped Modal and Bass Drum
    skip the release they get at key-up on Gate and ring out as on the
    module; a voice they free on silence may end on another block, so within
    1 LSB."""
    base = [f"Model={model}", "Decay=0.3", "Volume=1"]

    def play(name, lpg, length):
        return render(renderer, tmp_path, engine, params=base + [f"LPG={lpg}"], name=name,
                      notes=[f"0:57:110:{length}"], seconds=1.2)
    _, short, a = play("short", PING, 0.02)
    _, held, b = play("held", PING, 1.0)
    _, gate_short, _ = play("gate-short", GATE_MODE, 0.02)
    _, gate_held, _ = play("gate-held", GATE_MODE, 1.0)
    if self_enveloped(engine, model):
        assert max(abs(x - y) for x, y in zip(short, held)) <= 1.5 / 32767
        assert rms(short, 0.06, 0.2) > 2 * rms(gate_short, 0.06, 0.2)   # Gate released at key-up
    else:
        assert a.read_bytes() == b.read_bytes()
        assert rms(held, 0.6, 0.9) < 0.05 * rms(gate_held, 0.6, 0.9)   # closed with the key down


@pytest.mark.parametrize("engine,model", [("macro", 4), ("macro-heavy", 3)])
def test_off_releases_at_key_up_over_decay(renderer, tmp_path, engine, model):  # noqa: F811
    """Off holds the bypassed engine at full level while the key is down,
    and fades it at key-up with the gate's release curve, longer with Decay;
    then the voice ends and the output is silent."""
    def levels(decay):
        _, left, _ = render(renderer, tmp_path, engine, name=f"off{decay}",
                            params=[f"Model={model}", "LPG=2", f"Decay={decay}"],
                            notes=["0:57:127:0.5"], seconds=2.5)
        return left
    short, long_ = levels(0.2), levels(0.6)
    assert rms(short, 0.4, 0.5) == pytest.approx(rms(short, 0.1, 0.2), rel=0.05)
    assert rms(short, 0.55, 0.6) < 0.5 * rms(long_, 0.55, 0.6)
    assert rms(short, 2.2, 2.5) == 0.0
    assert rms(long_, 2.2, 2.5) < 0.05 * rms(long_, 0.55, 0.6)


@pytest.mark.parametrize("lpg", [PING, OFF])
def test_velocity_scales_ping_and_off(renderer, tmp_path, lpg):  # noqa: F811
    """With LEVEL unpatched upstream has no velocity; here it scales the
    voice by its accent, 1.3 v / (0.3 + v): 0.815 at velocity 64."""
    def level(velocity):
        _, left, _ = render(renderer, tmp_path, "macro", name=f"v{velocity}",
                            params=["Model=4", f"LPG={lpg}", "Decay=0.8"],
                            notes=[f"0:57:{velocity}:0.5"], seconds=0.5)
        return rms(left, 0.05, 0.2)
    v = 64 / 127
    assert level(64) / level(127) == pytest.approx(1.3 * v / (0.3 + v), rel=0.01)


# --- robustness ----------------------------------------------------------------------------

CHORD = [f"{0.02 * i}:{40 + 5 * i}:{60 + 5 * i}:0.2" for i in range(14)]   # past both caps


@pytest.mark.parametrize("engine", sorted(MODELS))
@pytest.mark.parametrize("setting", ["min", "max", "beyond", "nan"])
def test_page_three_takes_any_value_on_every_model(renderer, tmp_path, engine, setting):  # noqa: F811
    """Every model with the attenuverters at their extremes, beyond them and
    NaN, in each LPG mode and with the LPG itself beyond its range or NaN,
    through a chord past the voice cap and bends to both ends: finite output,
    and silence once the notes have ended (except the self-enveloped models
    on Ping, which ring as long as their own envelope says, by design)."""
    values = {"min": (-1, -1, -1), "max": (1, 1, 1), "beyond": (-7, 9, 1e30),
              "nan": ("nan", "nan", "nan")}[setting]
    for model in range(MODELS[engine]):
        for lpg in (GATE_MODE, PING, OFF, "nan" if setting == "nan" else 99):
            params = [f"Model={model}", "Decay=0.2"] + page3(values, lpg)
            s, left, _ = render(renderer, tmp_path, engine, params=params, notes=CHORD,
                                seconds=2.0, name="any",
                                extra=["--frames", "7", "--bend", "0.1:48", "--bend", "0.2:-48"])
            assert s["nonfinite"] == 0, (engine, model, lpg, setting)
            if not (lpg == PING and self_enveloped(engine, model)):
                assert rms(left, 1.8, 2.0) < 1e-4, (engine, model, lpg, setting)


@pytest.mark.parametrize("engine", sorted(MODELS))
def test_instance_memory_fill_does_not_matter(renderer, tmp_path, engine):  # noqa: F811
    """Instance memory is not zeroed by the host: 0x00, 0xA5 and 0xFF before
    create give the same bytes, on every model with the page in use and each
    LPG mode in turn."""
    for model in range(MODELS[engine]):
        params = [f"Model={model}"] + page3(ENV, model % 3)
        outs = []
        for fill in ("0x00", "0xA5", "0xFF"):
            _, _, wav = render(renderer, tmp_path, engine, params=params, notes=CHORD,
                               seconds=0.8, name=f"fill{fill}", extra=["--fill", fill])
            outs.append(wav.read_bytes())
        assert outs[0] == outs[1] == outs[2], (engine, model)


@pytest.mark.parametrize("engine", sorted(MODELS))
def test_page_three_turns_while_notes_sound(renderer, tmp_path, engine):  # noqa: F811
    """Each mode and attenuverter changes mid-chord, on every model: finite
    throughout, deterministic, and every voice ends after its release."""
    for model in range(MODELS[engine]):
        extra = ["--frames", "7"]
        t = 0.03
        for lpg in (PING, OFF, GATE_MODE, OFF, PING, GATE_MODE):
            extra += ["--param-at", f"{t:.3f}:LPG={lpg}"]
            for name, value in zip(PAGE3[:3], (1, -1, 0.3)):
                extra += ["--param-at", f"{t + 0.005:.3f}:{name}={value}"]
            t += 0.04
        args = dict(params=[f"Model={model}", "Decay=0.2"], notes=CHORD, seconds=2.0, extra=extra)
        s, left, a = render(renderer, tmp_path, engine, name="turn-a", **args)
        _, _, b = render(renderer, tmp_path, engine, name="turn-b", **args)
        assert s["nonfinite"] == 0, (engine, model)
        assert a.read_bytes() == b.read_bytes(), (engine, model)
        assert rms(left, 1.8, 2.0) < 1e-4, (engine, model)


@pytest.mark.parametrize("engine", sorted(MODELS))
@pytest.mark.parametrize("lpg", [GATE_MODE, PING, OFF])
def test_no_notes_is_silence(renderer, tmp_path, engine, lpg):  # noqa: F811
    s, left, _ = render(renderer, tmp_path, engine, params=page3(ENV, lpg), seconds=0.3)
    assert s["nonfinite"] == 0 and max(abs(x) for x in left) == 0.0
