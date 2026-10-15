import pathlib
import shutil
import subprocess


def test_original_zero_history_oracle_and_ring_recount(tmp_path):
    compiler = shutil.which("c++")
    if not compiler:
        import pytest
        pytest.skip("C++ compiler unavailable")
    root = pathlib.Path(__file__).resolve().parents[1]
    executable = tmp_path / "resampler-zero-history-reference-test"
    source = root / "engines/test/resampler_zero_history_reference_test.cc"
    include = root / "engines/include"
    built = subprocess.run(
        [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-O2",
         "-I", str(include), str(source), "-o", str(executable)],
        check=False, capture_output=True, text=True,
    )
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(executable)], check=False, capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr
    assert "zero-history fast path matches reference bit-for-bit" in ran.stdout
