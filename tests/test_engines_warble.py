"""Warble (original MIT wow/flutter): registration and measurable behavior."""
import json
import subprocess

from tests.engine_helpers import ENGINES, render, renderer  # noqa: F401

SELFTEST = ENGINES / "build" / "fm1-warble-selftest"


def effect(*params):
    return [("warble", list(params))]


def test_warble_is_registered_with_stable_editor_metadata(renderer, tmp_path):
    listed = json.loads(subprocess.run([str(renderer), "--list"], check=True,
                                       capture_output=True, text=True).stdout)
    e = next(x for x in listed if x["id"] == "warble")
    assert e["kind"] == "audio_fx" and e["name"] == "Warble" and e["max_voices"] == 0
    assert "MIT" in e["credits"] and "CHOMPI Warble" in e["credits"]
    assert [(p["name"], p["min"], p["max"], p["def"], p["page"]) for p in e["params"]] == [
        ("Wow", 0, 1, 0.35, 0), ("Flutter", 0, 1, 0.25, 0), ("Mix", 0, 1, 0.5, 0),
    ]
    summary, _, _ = render(renderer, tmp_path, input="silence", seconds=0.01,
                           fx=effect())
    assert summary["fx"] == ["warble"]
    assert 16384 <= summary["fx_bytes"][0] <= 16896


def test_mix_zero_is_bit_exact_and_modulation_is_audible(renderer, tmp_path):
    _, dry, dry_wav = render(renderer, tmp_path, input="sine", seconds=1.0,
                             fx=effect("Mix=0"), name="dry")
    _, reference, reference_wav = render(renderer, tmp_path, input="sine", seconds=1.0,
                                         fx=[("test-gain", ["Gain=1"])], name="reference")
    assert dry == reference
    assert dry_wav.read_bytes() == reference_wav.read_bytes()

    _, wet, _ = render(renderer, tmp_path, input="sine", seconds=1.0,
                       fx=effect("Wow=1", "Flutter=1", "Mix=1"), name="wet")
    assert max(abs(a - b) for a, b in zip(wet[1000:], dry[1000:])) > 0.02


def test_host_contracts_and_live_smoothing(renderer):
    res = subprocess.run([str(SELFTEST)], check=False, capture_output=True, text=True)
    checks = [json.loads(line) for line in res.stdout.splitlines()]
    assert res.returncode == 0, res.stdout + res.stderr
    assert {x["check"] for x in checks} == {
        "refuses_bad_rates", "fixed_bounded_instance", "delay_scales_in_seconds",
        "deterministic_and_reblockable", "exact_dry_and_smooth_mix",
        "live_wow_flutter_are_smoothed",
        "hostile_values_finite_and_bounded",
    }
    assert all(x["ok"] for x in checks), res.stdout
