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
