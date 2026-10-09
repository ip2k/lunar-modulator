"""Target report regressions using observed pi32v2 prologue forms."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "target_analyze", Path(__file__).resolve().parents[1] / "tools/jieli/analyze.py")
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


def test_split_stack_reservation_matches_compiler_frame():
    # fm1_state_bin_read, vendor compiler -O2: 13 saved registers and
    # three decrements. The compiler reports 8264 bytes, not 4148.
    body = ["0: [--sp] = {rets, r15-r4}", "2: sp += -4096",
            "6: sp += -4096", "a: sp += -20", "c: r6 = r2"]
    assert analyze.frame_of(body) == (8264, "")


def test_single_adjustment_and_epilogue_outside_prologue():
    body = ["[--sp] = {rets, r8-r4}", "sp -= 64"] + ["r0 = r1"] * 6
    body += ["sp += -32"]  # outside the bounded prologue scan
    assert analyze.frame_of(body) == (88, "")


def test_dynamic_stack_adjustment_is_flagged():
    frame, warning = analyze.frame_of(["[--sp] = {rets}", "sp -= r2"])
    assert frame == 4
    assert warning
