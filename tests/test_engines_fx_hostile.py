"""Hostile host-contract checks, the same for every effect of the master-bus
pack: DJ Filter, Tilt, EQ, Isolator and Master Sat (engines/README.md; the
design in notes/2026-10-02-delay-reverb-eq-gates-options.md §4-§6).

fm1-fx-hostile-test (engines/test/fx_hostile_test.cc) drives the five
through their engine structs only. Each effect's own tests check its design;
these check fm1_engine.h's contracts alike for all of them, and harder than
fm1-render can: parameters changed at any frame, block sizes from 1 to
4,096 frames, instance memory filled with NaNs, infinities or random bytes,
garbage parameters and input for seconds and then one setting (which must
end where a fresh instance with it is), the pass-through settings on input
with -0, subnormals and values at the guard, parameters thrown between their
ends every frame, tails, host rates, glides landing at four rates, and
indices past the table. Written for the review of the integrated pack
(2026-10-05), which found Isolator's crossover glide stalling an ulp-sized
step short of its target for ever.
"""
import json
import math
import subprocess

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401

TOOL = ENGINES / "build" / "fm1-fx-hostile-test"
EFFECTS = ["djfilter", "tilt", "eq", "isolator", "sat"]


@pytest.fixture(scope="module")
def report(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_every_effect_of_the_pack_is_covered(report):
    assert sorted(report) == sorted(EFFECTS)


@pytest.mark.parametrize("fx", EFFECTS)
def test_blocks_and_memory_fills_do_not_change_the_output(report, fx):
    # Random changes at random frames, NaN and infinities among them, in
    # blocks of 64, 1, 7, 13, random sizes and 4,096; and from seven fills.
    r = report[fx]
    assert r["block_mismatch"] == 0 and r["fill_mismatch"] == 0
    assert math.isfinite(r["random_peak"]) and r["random_peak"] < 100


@pytest.mark.parametrize("fx", EFFECTS)
def test_chaos_neither_breaks_nor_latches(report, fx):
    # 3 s of garbage parameters and input, then one setting: 2.5 s later the
    # output is a fresh instance's with that setting (it was 2e-5 off for
    # Isolator, whose crossover glide stalled short of its target).
    r = report[fx]
    assert math.isfinite(r["chaos_peak"]) and r["chaos_peak"] < 1e4
    assert r["chaos_settled_diff"] <= 1e-6


@pytest.mark.parametrize("fx", EFFECTS)
def test_pass_through_settings_are_exact_and_come_back(report, fx):
    # From every memory fill, on input with -0, subnormals, FLT_MIN and
    # +/-16; then a visit to a busy setting and back: exact again within
    # 100 ms (measured 5-60 ms).
    for n in report[fx]["neutral"]:
        assert n["exact_fills"] == 7
        assert n["exact_before_visit"] and n["changed_by_visit"]
        assert n["exact_again_ms"] < 100


@pytest.mark.parametrize("fx", EFFECTS)
def test_every_frame_extremes_stay_bounded(report, fx):
    peaks = report[fx]["extremes_peak"]
    assert all(math.isfinite(p) and p < 100 for p in peaks)


@pytest.mark.parametrize("fx", EFFECTS)
def test_tails_end_in_exact_zeros(report, fx):
    r = report[fx]
    assert 0 < r["tail_s"] < 2 and not r["subnormal_out"]


@pytest.mark.parametrize("fx", EFFECTS)
def test_host_rates(report, fx):
    r = report[fx]
    assert r["bad_rates_accepted"] == 0
    assert math.isfinite(r["rates_peak"]) and r["rates_peak"] < 100
    assert r["rates_neutral_exact"] == 8


@pytest.mark.parametrize("fx", EFFECTS)
def test_glides_land(report, fx):
    # Each parameter moved end to end and between random values, at 8, 44.1,
    # 96 and 384 kHz: 1.5 s later within 1e-5 of a fresh instance at the
    # new value. Before the review, Isolator's crossovers stayed up to 1e-4
    # off at 96 and 384 kHz. Four of the five land bit for bit; EQ keeps
    # float rounding noise near 1e-6 where a band is moved to 20 Hz (its
    # values do land: the states of a filter that narrow differ by rounding).
    for g in report[fx]["glides"]:
        assert g["routes"] >= 24
        assert g["worst"] < 1e-5, g
        if fx != "eq":
            assert g["not_identical"] == 0, g


@pytest.mark.parametrize("fx", EFFECTS)
def test_an_index_past_the_table_is_ignored(report, fx):
    assert report[fx]["bad_index_ignored"]
