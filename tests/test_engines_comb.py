"""Tests for Comb, the comb filter effect (engines/src/fx_comb.cc, parameters
in engines/README.md, "Comb"), the Filter's seventh type until 2026-10-05.

The split (notes/2026-10-02-filters-dynamics-options.md, FD0): renders
pinned at main d538f1e (tests/fixtures/comb-split.json) show that the
Filter's other types are byte for byte what they were, Formant now at Type
5, and that Comb renders what a Filter set to Comb rendered. Through
fm1-render: registration, its uids beside the Filter's, the instance size,
and the host contracts (any block size, any prior memory contents, any
parameter value, bad input guarded and not latched, silence in gives silence
out). fm1-filter-test drives it with the Filter (tests/test_engines_filter.py:
responses, extremes, the parameter sweep, host rates).
"""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tests.engine_helpers import RATE, render, renderer  # noqa: F401
from tests.test_engines_mi_fx import BANNED, run

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "comb-split.json"
LSB = 1 / 32767.0
BUSY = ["Cutoff=900", "Resonance=0.6", "Drive=0.4", "Mode=0.7", "Morph=0.3"]


def fx(*params):
    return [("comb", list(params))]


def listed(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return {x["id"]: x for x in json.loads(out)}


def test_comb_is_registered(renderer):  # noqa: F811
    e = listed(renderer)["comb"]
    assert (e["name"], e["kind"], e["max_voices"], e["per_note"]) == ("Comb", "audio_fx", 0, False)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Zoelzer" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Cutoff", "Resonance", "Drive"], ["Mode", "Morph", "Mix", "Level"]]
    cutoff = e["params"][0]
    assert (cutoff["min"], cutoff["max"], cutoff["unit"]) == (20, 18000, "hz")
    assert "log" in cutoff["flags"]


def test_comb_keeps_the_filters_uids(renderer):  # noqa: F811
    """A Filter that was set to Comb maps onto Comb uid for uid: every Comb
    parameter has the Filter's uid, range and default for the same name, and
    uid 1, the Filter's Type, is not Comb's (it is retired there)."""
    e = listed(renderer)
    comb = {p["name"]: p for p in e["comb"]["params"]}
    filt = {p["name"]: p for p in e["filter"]["params"]}
    assert set(comb) == set(filt) - {"Type"}
    for name, p in comb.items():
        q = filt[name]
        assert (p["uid"], p["min"], p["max"], p["def"], p["flags"], p["unit"]) == \
               (q["uid"], q["min"], q["max"], q["def"], q["flags"], q["unit"]), name
    assert 1 not in {p["uid"] for p in comb.values()}
    pinned = json.loads((FIXTURE.parent / "param-uids.json").read_text())
    assert pinned["retired"]["comb"] == [1]


def test_filter_types_after_the_split(renderer):  # noqa: F811
    t = listed(renderer)["filter"]["params"][0]
    assert t["names"] == ["SVF", "Ladder", "Diode", "Sallen-Key", "SK Mixed", "Formant"]


@pytest.mark.parametrize("case", sorted(json.loads(FIXTURE.read_text())["cases"]))
def test_split_is_byte_identical(renderer, tmp_path, case):  # noqa: F811
    """Each case renders the bytes main d538f1e rendered with the arguments
    the fixture's `was` lists: the Filter's types unchanged (Formant moved
    from 6 to 5), and Comb the old Comb type."""
    fixture = json.loads(FIXTURE.read_text())
    c = fixture["cases"][case]
    wav = tmp_path / "out.wav"
    subprocess.run([str(renderer), "--seconds", str(fixture["seconds"]), "--out", str(wav),
                    *c["args"]], check=True, capture_output=True)
    assert hashlib.sha256(wav.read_bytes()).hexdigest() == c["sha256"]


def test_instance_size(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    # 160 bytes of state and two delay lines of fs / 20 Hz + 4 floats.
    assert s["fx_bytes"] == [160 + ((2 * (int(RATE / 20) + 4) * 4 + 15) // 16) * 16] == [17840]


def test_block_size_does_not_change_the_output(renderer, tmp_path):  # noqa: F811
    # (A change mid-stream at any block size: fm1-filter-test's glide.)
    wavs = []
    for frames in ("64", "7", "1"):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.4, fx=fx(*BUSY),
                           name=f"f{frames}", extra=["--frames", frames])
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


def test_output_ignores_initial_memory(renderer, tmp_path):  # noqa: F811
    wavs = []
    for fill in ("0", "0xA5", "0xFF"):
        s, _, wav = render(renderer, tmp_path, input="noise", seconds=0.4, fx=fx(*BUSY),
                           name=f"fill{fill}", extra=["--fill", fill])
        assert s["nonfinite"] == 0
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


@pytest.mark.parametrize("value,same_as", [("nan", None), ("1e9", "max"), ("-inf", "min")])
def test_out_of_range_parameters_clamp(renderer, tmp_path, value, same_as):  # noqa: F811
    params = listed(renderer)["comb"]["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


def test_silence_in_is_silence_out(renderer, tmp_path):  # noqa: F811
    hot = ["Resonance=1", "Drive=1", "Mode=1.5", "Morph=0.6", "Level=2"]
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*hot))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


@pytest.mark.parametrize("bad", ["nan", "inf", "1e30"])
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad):  # noqa: F811
    # As the Filter: NaN reads as 0, the rest clamps to +/-16, so 0.7 s after
    # the fault the output is the fault-free one again, within one LSB.
    base = ["--input", "noise", "--seconds", "1.5", "--fx", "comb"]
    for p in BUSY:
        base += ["--fx-param", p]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    s, left, right, _ = run(renderer, tmp_path, [*base, "--fault", f"0.2..0.5:{bad}"], "fault")
    assert s["nonfinite"] == 0
    tail = slice(int(1.2 * RATE), None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= LSB
