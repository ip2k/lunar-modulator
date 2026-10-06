"""Engine API v4 (engines/include/fm1_engine.h; engines/README.md, "Engine API
v4"; notes/2026-10-06-state-files.md ST7): the FOCUS and PER_FOCUS flags and
get_param, so a host can read back every value it can set, every pad of a
kit included, and a saved sound restores exactly.

fm1-param-get-test (engines/test/param_get_test.cc) runs on every registered
engine, effect and MIDI effect:
- with get_param (the pad kits): a fresh instance reads within range, the
  table's defaults where it gives them; random values, out-of-range ones
  among them, set on every pad, read back exactly as set_param kept them,
  without the reading moving the focus; fm1_engine_copy_params into a fresh
  instance gives every value back and the same samples, every pad played;
- without get_param: random values set in a random order render the same
  as only the last value of each, as a host keeps it, replayed once in
  table order, so what a host saves is enough to restore the sound.
"""
import json
import re
import subprocess

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401

TOOL = ENGINES / "build" / "fm1-param-get-test"
HEADER = ENGINES / "include" / "fm1_engine.h"


@pytest.fixture(scope="module")
def results(renderer):
    out = subprocess.run([str(TOOL), "6"], check=True, capture_output=True, text=True).stdout
    return [json.loads(line) for line in out.splitlines()]


@pytest.fixture(scope="module")
def listed(renderer):
    return json.loads(subprocess.run([str(renderer), "--list"], check=True,
                                     capture_output=True, text=True).stdout)


def test_the_header_is_api_v4_with_its_flags():
    text = HEADER.read_text()
    assert re.search(r"#define FM1_ENGINE_API_VERSION 4u", text)
    assert re.search(r"#define FM1_PARAM_FOCUS\s+0x0100u", text)
    assert re.search(r"#define FM1_PARAM_PER_FOCUS 0x0200u", text)
    assert re.search(r"#define FM1_FOCUS_CURRENT 0xFFu", text)
    assert "float (*get_param)(const void *self, uint16_t index, uint8_t focus);" in text


def test_every_engine_is_checked(results, listed):
    """Every engine, effect and MIDI effect is run, with the check its API
    calls for: get and copy with get_param, replay without."""
    by = {}
    for r in results:
        by.setdefault(r["engine"], set()).add(r["check"])
    assert set(by) == {e["id"] for e in listed}
    for e in listed:
        assert by[e["id"]] == ({"get", "copy"} if e["get_param"] else {"replay"}), e["id"]


@pytest.mark.parametrize("check", ["get", "copy", "replay"])
def test_values_read_back_and_restore(results, check):
    failed = [r for r in results if r["check"] == check and not r["pass"]]
    assert not failed, failed


def test_the_pad_kits_read_every_pad(listed):
    """Drums and Sophie, the kits here, have their focus and per-pad values:
    a saved kit holds all sixteen pads (the state note's §5.1)."""
    eng = {e["id"]: e for e in listed}
    for eid, per_pad in (("drums", {"Tune", "Decay", "Level", "Tone", "Snap", "Sweep", "Drive",
                                    "Model", "Choke"}),
                         ("sw-sophie", {"Tune", "Decay", "Model", "Color", "Metal", "Feedback",
                                        "Sweep"})):
        e = eng[eid]
        assert e["get_param"] and e["pads"] == {"first": 36, "count": 16}, eid
        assert [p["name"] for p in e["params"] if "focus" in p["flags"]] == ["Pad"], eid
        assert {p["name"] for p in e["params"] if "per_focus" in p["flags"]} == per_pad, eid
