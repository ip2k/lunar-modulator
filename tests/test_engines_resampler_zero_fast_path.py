import pathlib
import shutil
import subprocess

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_zero_history_fast_path_matches_reference_bit_for_bit(tmp_path):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("C++ compiler unavailable")
    exe = tmp_path / "resampler-zero-fast-test"
    source = ROOT / "engines/test/resampler_zero_fast_test.cc"
    include = ROOT / "engines/include"
    built = subprocess.run(
        [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-O2",
         "-I", str(include), str(source), "-o", str(exe)],
        check=False, capture_output=True, text=True,
    )
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(exe)], check=False, capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr
    assert "bit-for-bit" in ran.stdout
