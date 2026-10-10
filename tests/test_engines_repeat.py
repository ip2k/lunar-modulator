"""Repeat beat-synchronised stutter/hold, checked at the engine boundary.

The native selftest covers transport/event timing and the effective musical
division. The renderer checks public registration and the admitted instance
size; the desktop evidence is not a device memory or CPU measurement.
"""
import json
import subprocess

from tests.engine_helpers import ENGINES, renderer  # noqa: F401

SELFTEST = ENGINES / "build" / "fm1-repeat-selftest"


def test_repeat_is_registered_with_stable_control_contract(renderer):
    listing = json.loads(subprocess.run([str(renderer), "--list"], check=True,
                                        capture_output=True, text=True).stdout)
    effect = next(e for e in listing if e["id"] == "repeat")
    assert effect["kind"] == "audio_fx" and effect["name"] == "Repeat"
    assert "Original MIT" in effect["credits"]
    assert [(p["name"], p["min"], p["max"], p["def"]) for p in effect["params"]] == [
        ("Hold", 0, 1, 0), ("Max slice", 0, 2, 1), ("Mix", 0, 1, 0.5),
    ]
    assert effect["params"][0]["names"] == ["Off", "On"]
    assert effect["params"][1]["names"] == ["1/8 max", "1/16 max", "1/32 max"]


def test_repeat_native_transport_and_memory_regressions(renderer):
    result = subprocess.run([str(SELFTEST)], check=True, capture_output=True, text=True)
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    summary = rows[-1]
    assert summary == {"summary": "repeat", "passed": 8, "failed": 0}
    caps = [row for row in rows if row.get("diagnostic") == "effective_slice"]
    assert [(row["rate"], row["bpm"], row["requested_denominator"],
             row["effective_denominator"], row["frames"]) for row in caps] == [
        (192000, 20, 8, 256, 9000), (96000, 20, 8, 128, 9000),
        (44118, 120, 16, 16, 5515), (8000, 300, 32, 32, 200),
    ]
