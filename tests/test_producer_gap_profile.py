from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_producer_gap_accumulator_wraps_and_resets_windows(tmp_path):
    compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if compiler is None:
        pytest.skip("a C compiler is required for the native accumulator harness")
    executable = tmp_path / "producer-gap-profile"
    subprocess.run([
        compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/native"),
        "-I", str(ROOT / "sim/web/src"),
        str(ROOT / "tests/native/producer_gap_profile.c"), "-o", str(executable),
    ], check=True, capture_output=True, text=True)
    subprocess.run([str(executable)], check=True, capture_output=True, text=True)
