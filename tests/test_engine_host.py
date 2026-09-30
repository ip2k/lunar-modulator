"""Host contracts every engine relies on (engines/include/fm1_engine.h):
the bus limiter survives non-finite samples, and no engine depends on the
contents of its instance memory before create.
"""
import json
import subprocess

import pytest

from tests.engine_helpers import render, rms, renderer  # noqa: F401

# Two Test Gain stages at their maximum of 2 take the host's 0.5 noise to a
# raw peak of about 2.0, so the limiter has real work to do after the fault.
LOUD = [("test-gain", ["Gain=2"]), ("test-gain", ["Gain=2"])]


@pytest.mark.parametrize("value,nonfinite", [("nan", 2), ("inf", 2), ("-inf", 2), ("1e30", 0)])
def test_limiter_survives_a_bad_sample(renderer, tmp_path, value, nonfinite):
    clean, clean_l, _ = render(renderer, tmp_path, input="noise", fx=LOUD, seconds=1.0,
                               name="clean")
    s, left, _ = render(renderer, tmp_path, input="noise", fx=LOUD, seconds=1.0,
                        name="fault", extra=["--fault", f"0.1:{value}"])
    assert clean["raw_peak"] > 1.5, "the source is not loud enough to test the limiter"
    assert s["nonfinite"] == nonfinite          # counted before the limiter, not hidden by it
    assert s["peak"] <= 0.98 + 1e-6              # before the guard, one NaN stopped limiting
    # ...and the bus comes back: the last half second matches the fault-free run.
    assert rms(left, 0.5, 1.0) == pytest.approx(rms(clean_l, 0.5, 1.0), rel=0.02)


def _engines(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def test_every_engine_ignores_initial_memory(renderer, tmp_path):
    """The API promises no zeroed instance memory, so output must not change
    with what the memory held before create."""
    checked = []
    for e in _engines(renderer):
        if e["kind"] == "sound":
            kw = dict(engine=e["id"], notes=["0:57:100:0.3", "0.1:64:90:0.3"])
        elif e["kind"] == "audio_fx":
            kw = dict(input="noise", fx=[(e["id"], [])])
        else:
            continue
        wavs = []
        for fill in ("0", "0xA5", "0xFF"):
            s, _, wav = render(renderer, tmp_path, seconds=0.6, name=f"{e['id']}-{fill}",
                               extra=["--fill", fill], **kw)
            assert s["nonfinite"] == 0, (e["id"], fill)
            wavs.append(wav.read_bytes())
        assert wavs[1] == wavs[0] and wavs[2] == wavs[0], f"{e['id']} reads memory it never set"
        checked.append(e["id"])
    assert len(checked) >= 4


CHORD = [f"{0.02 * i}:{40 + 5 * i}:{60 + 5 * i}:0.2" for i in range(14)]   # past every voice cap


@pytest.mark.parametrize("setting", ["min", "max", "beyond", "nan"])
def test_every_engine_survives_any_parameter_value(renderer, tmp_path, setting):
    """set_param takes any float: out-of-range values clamp and NaN falls back
    to the default (fm1_param_clamp), so no engine renders non-finite output.
    Under the sanitizer build this also checks the paths for UB."""
    for e in _engines(renderer):
        if e["kind"] == "midi_fx":
            continue
        values = {"min": lambda p: p["min"], "max": lambda p: p["max"],
                  "beyond": lambda p: 4 * p["max"] - 3 * p["min"] + 1, "nan": lambda p: "nan"}
        params = [f"{p['name']}={values[setting](p)}" for p in e["params"]]
        if e["kind"] == "sound":
            kw = dict(engine=e["id"], params=params, notes=CHORD)
        else:
            kw = dict(input="noise", fx=[(e["id"], params)])
        s, _, _ = render(renderer, tmp_path, seconds=0.5, name=f"{e['id']}-{setting}",
                         extra=["--frames", "7"], **kw)
        assert s["nonfinite"] == 0, (e["id"], setting)
