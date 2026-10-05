"""A reviewer's hostile checks across the third effects pack: Room, Hall,
Gate and Plate with Freeze (engines/README.md, engines/mi-fx.md), driven the
same way by build/fm1-fx3-hostile (engines/test/fx3_hostile.cc). Each
effect's own tests go deeper; these hold the four to one standard.
"""
import json
import subprocess

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401

TOOL = ENGINES / "build" / "fm1-fx3-hostile"


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_any_schedule_any_blocks_any_fill_same_bits(tool):
    # Three seconds of noise bursts with a random parameter change every
    # 1,500-4,500 frames (seed 1 in range; seed 2 any value, NaN and
    # infinities included; seed 3 in range with NaN, infinities, 1e30 and
    # subnormals in the input), at 32, 44.118 and 48 kHz. Blocks of 1, 7, 13
    # and random 1-64 frames, and memory filled with 0x00, 0xFF, 0xA5, 0x7F
    # and 0x80 before create, give the 64-frame render's bits exactly.
    rows = tool["schedule"]
    assert {r["fx"] for r in rows} == {"room", "hall", "gate", "plate"} and len(rows) == 36
    for r in rows:
        assert r["finite"] and r["changes"] >= 30, r
        assert r["same"] == r["tried"] == 9, r
        # Clean input peaks at 0.6: nothing runs away. Bad input is clamped
        # to 16, plus at most a reverb's wet (Hall: four words of 2.0 a side).
        assert r["peak"] <= (2.0 if r["seed"] != 3 else 24.0), r


def test_the_gate_never_amplifies(tool):
    # Listen off, every other parameter on a random schedule (Mode, Range,
    # Lookahead and the rest turned while bursts gate): no output sample is
    # larger than the largest input sample within the look-ahead's 5 ms.
    for r in tool["gate_gain"]:
        assert r["changes"] > 50 and r["excess"] <= 0.0, r


def test_a_key_copied_from_the_input_is_the_input(tool):
    # fm1_gate_render_key with a copy of the input as the key, under the
    # wild schedule and bad input, at random block sizes: render's bits.
    assert tool["gate_key"] == [True, True, True]


def test_longest_tails_end_in_exact_zeros(tool):
    # Half a second of noise (0.5 peak), then 119.5 s of silence, at the
    # longest settings. Hall at Decay 1, Damping 0, Size 1 and Mod 0 runs
    # whole-sample delays with stores that round above four words, the
    # setting most open to a limit cycle; Freeze held 10 s, then released.
    # Measured 2026-10-05: Hall 18.2, 10.0 and 22.8 s; Room 16.0 and 8.6 s;
    # Plate after Freeze 40.7 s.
    tails = {t["name"]: t for t in tool["tails"]}
    for name, t in tails.items():
        assert t["nonfinite"] == 0, t
        assert 1.0 < t["last_nonzero_s"] < 60.0, t
        if not name.startswith("plate"):
            assert t["subnormal"] == 0, t
    # Plate's tail passes through subnormal output samples on its way to
    # zero (about a thousand): rings::Reverb's private damping states, and a
    # wrapper that predates this pack and does not flush its wet
    # (engines/mi-fx.md, "Limits"). Recorded, not asserted.
    assert tails["plate-freeze-released"]["subnormal"] >= 0
