"""Tests for the engine API, the Mutable-derived engines and the desktop host.

Builds engines/ with the system C++ compiler (skipped when there is none),
renders through engines/build/fm1-render and checks tuning, output sanity,
polyphony, voice release, determinism and instance size. docs/11 §8 stage A.
"""
import json
import subprocess

import pytest

from tests.engine_helpers import (ENGINES, RATE, cents, pitch_hz,  # noqa: F401
                                  render, renderer, rms)


def test_registry_lists_engines(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True,
                         capture_output=True, text=True).stdout
    engines = {e["id"]: e for e in json.loads(out)}
    assert {"macro", "shapes", "test-sine", "test-gain"} <= set(engines)
    for e in engines.values():
        assert e["credits"]
        assert e["kind"] in ("sound", "audio_fx")
        if e["kind"] == "sound":
            assert e["max_voices"] >= 1
        else:
            assert e["max_voices"] == 0
        assert all(p["page"] in (0, 1) for p in e["params"])  # four knobs a page
        assert sum(p["page"] == 0 for p in e["params"]) <= 4
        for p in e["params"]:   # an enum lists one name per value, nothing else does
            if p["type"] == 1:
                assert len(p["names"]) == p["max"] - p["min"] + 1 and all(p["names"])
            else:
                assert "names" not in p


def test_reference_sine_is_in_tune(renderer, tmp_path):
    _, left, _ = render(renderer, tmp_path, "test-sine", notes=["0:69:100:1.5"])
    assert abs(cents(pitch_hz(left, 0.3, 1.0), 440.0)) < 0.5


@pytest.mark.parametrize("key", [45, 69, 93])
def test_macro_keeps_tuning_at_the_fm1_rate(renderer, tmp_path, key):
    # 2-op FM with zero modulation index and no feedback is a pure sine. Macro
    # runs Plaits at its own rate and resamples, so no pitch correction is
    # involved (until 2026-10-01 a pitch offset compensated for the host's
    # rate, which this test checked).
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


def test_fx_chain_processes_in_place(renderer, tmp_path):
    base, _, _ = render(renderer, tmp_path, input="sine", seconds=0.5,
                        fx=[("test-gain", ["Gain=1.0"])], name="unity")
    half, _, _ = render(renderer, tmp_path, input="sine", seconds=0.5,
                        fx=[("test-gain", ["Gain=0.5"])], name="half")
    assert base["fx"] == ["test-gain"] and base["input"] == "sine"
    assert abs(base["peak"] - 0.5) < 1e-3
    assert abs(half["peak"] - 0.25) < 1e-3


def test_fx_after_an_engine(renderer, tmp_path):
    dry, _, _ = render(renderer, tmp_path, "test-sine", notes=["0:69:127:0.5"],
                       seconds=0.5, name="dry")
    wet, _, _ = render(renderer, tmp_path, "test-sine", notes=["0:69:127:0.5"],
                       seconds=0.5, fx=[("test-gain", ["Gain=2.0"])], name="wet")
    assert abs(wet["raw_peak"] - 2 * dry["raw_peak"]) < 1e-3
