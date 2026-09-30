"""Tests for the engine API, the Mutable-derived engines and the desktop host.

Builds engines/ with the system C++ compiler (skipped when there is none),
renders through engines/build/fm1-render and checks tuning, output sanity,
polyphony, voice release, determinism and instance size. docs/11 §8 stage A.
"""
import json
import math
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"
RENDER = ENGINES / "build" / "fm1-render"
RATE = 44118


@pytest.fixture(scope="session")
def renderer():
    if not shutil.which("make") or not (shutil.which("c++") or shutil.which("g++")):
        pytest.skip("no make / C++ compiler")
    subprocess.run(["make", "-C", str(ENGINES), "-j4"], check=True,
                   stdout=subprocess.DEVNULL)
    return RENDER


def render(renderer, tmp_path, engine, params=(), notes=(), seconds=1.5, name="out"):
    wav = tmp_path / f"{name}.wav"
    cmd = [str(renderer), "--engine", engine, "--seconds", str(seconds), "--out", str(wav)]
    for p in params:
        cmd += ["--param", p]
    for n in notes:
        cmd += ["--note", n]
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    summary = json.loads(res.stdout)
    with wave.open(str(wav), "rb") as w:
        assert w.getframerate() == RATE and w.getnchannels() == 2
        raw = w.readframes(w.getnframes())
    left = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767.0
            for i in range(0, len(raw), 4)]
    return summary, left, wav


def pitch_hz(samples, start_s, dur_s):
    """Fundamental from rising zero crossings (clean, sine-like input)."""
    a, b = int(start_s * RATE), int((start_s + dur_s) * RATE)
    seg = samples[a:b]
    mean = sum(seg) / len(seg)
    seg = [x - mean for x in seg]
    crossings = []
    for i in range(1, len(seg)):
        if seg[i - 1] < 0.0 <= seg[i]:
            frac = -seg[i - 1] / (seg[i] - seg[i - 1])
            crossings.append(i - 1 + frac)
    assert len(crossings) > 10, "no periodic signal"
    return (len(crossings) - 1) * RATE / (crossings[-1] - crossings[0])


def cents(f, ref):
    return 1200.0 * math.log2(f / ref)


def rms(samples, start_s, end_s):
    seg = samples[int(start_s * RATE):int(end_s * RATE)]
    return math.sqrt(sum(x * x for x in seg) / max(1, len(seg)))


def test_registry_lists_engines(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True,
                         capture_output=True, text=True).stdout
    engines = {e["id"]: e for e in json.loads(out)}
    assert {"macro", "shapes", "test-sine"} <= set(engines)
    for e in engines.values():
        assert e["credits"] and e["max_voices"] == 12
        assert all(p["page"] in (0, 1) for p in e["params"])  # four knobs a page
        assert sum(p["page"] == 0 for p in e["params"]) <= 4


def test_reference_sine_is_in_tune(renderer, tmp_path):
    _, left, _ = render(renderer, tmp_path, "test-sine", notes=["0:69:100:1.5"])
    assert abs(cents(pitch_hz(left, 0.3, 1.0), 440.0)) < 0.5


@pytest.mark.parametrize("key", [45, 69, 93])
def test_macro_rate_compensation_keeps_tuning(renderer, tmp_path, key):
    # 2-op FM with zero modulation index and no feedback is a pure sine.
    _, left, _ = render(renderer, tmp_path, "macro",
                        params=["Model=6", "Timbre=0", "Morph=0.5", "Harmonics=0.5"],
                        notes=[f"0:{key}:100:1.5"])
    ref = 440.0 * 2 ** ((key - 69) / 12)
    assert abs(cents(pitch_hz(left, 0.3, 1.0), ref)) < 5.0


@pytest.mark.parametrize("key", [45, 69, 93])
def test_shapes_rate_compensation_keeps_tuning(renderer, tmp_path, key):
    _, left, _ = render(renderer, tmp_path, "shapes",
                        params=["Shape=3", "Timbre=0", "Color=0"],
                        notes=[f"0:{key}:100:1.5"])
    ref = 440.0 * 2 ** ((key - 69) / 12)
    assert abs(cents(pitch_hz(left, 0.3, 1.0), ref)) < 5.0


@pytest.mark.parametrize("model", range(8))
def test_every_macro_model_sounds_cleanly(renderer, tmp_path, model):
    summary, left, _ = render(renderer, tmp_path, "macro",
                              params=[f"Model={model}"], notes=["0.05:57:100:0.8"])
    assert summary["nonfinite"] == 0 and summary["raw_clipped"] == 0
    assert rms(left, 0.1, 0.8) > 1e-3


@pytest.mark.parametrize("shape", range(47))
def test_every_shape_sounds_cleanly(renderer, tmp_path, shape):
    summary, left, _ = render(renderer, tmp_path, "shapes",
                              params=[f"Shape={shape}"], notes=["0.05:57:100:0.8"],
                              seconds=1.0)
    assert summary["nonfinite"] == 0 and summary["raw_clipped"] == 0
    assert summary["peak"] > 0.005


@pytest.mark.parametrize("engine", ["macro", "shapes"])
def test_twelve_note_chord(renderer, tmp_path, engine):
    notes = [f"0:{48 + k}:100:1.0" for k in range(12)]
    summary, left, _ = render(renderer, tmp_path, engine, notes=notes)
    # Twelve voices started in phase may sum past full scale; the host's bus
    # limiter (fm1_mix_limiter.h) must hold the output under the ceiling.
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    assert summary["peak"] <= 0.98 + 1e-6
    assert rms(left, 0.2, 0.9) > 1e-3


@pytest.mark.parametrize("engine,params", [
    ("macro", ["Decay=0.2"]),
    ("shapes", ["Release=0.1"]),
])
def test_release_frees_voices(renderer, tmp_path, engine, params):
    _, left, _ = render(renderer, tmp_path, engine, params=params,
                        notes=["0:60:100:0.3"], seconds=2.0)
    assert rms(left, 0.05, 0.3) > 1e-3
    assert rms(left, 1.6, 2.0) < 1e-4


def test_rendering_is_deterministic(renderer, tmp_path):
    args = dict(params=["Model=1", "Timbre=0.3"], notes=["0:60:90:0.5", "0.2:64:90:0.5"])
    _, _, a = render(renderer, tmp_path, "macro", name="a", **args)
    _, _, b = render(renderer, tmp_path, "macro", name="b", **args)
    assert a.read_bytes() == b.read_bytes()


def test_instance_sizes_are_reported(renderer, tmp_path):
    macro, _, _ = render(renderer, tmp_path, "macro", seconds=0.1)
    shapes, _, _ = render(renderer, tmp_path, "shapes", seconds=0.1)
    # 12 voices; host pointers are 64-bit, so pi32v2 will be smaller.
    assert macro["instance_bytes"] < 40_000
    # Braids' DigitalOscillator carries ~17 KB of physical-model state per voice
    # (docs/11 §4): too much for 12 voices on the FM-1; recorded, not hidden.
    assert shapes["instance_bytes"] < 256_000
