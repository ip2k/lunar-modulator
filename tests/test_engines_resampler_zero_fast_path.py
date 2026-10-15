import pathlib
import shutil
import subprocess

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("hot_dsp_ram", [False, True], ids=["default", "hot-dsp-ram"])
def test_zero_pop_fast_path_matches_prior_bit_for_bit(tmp_path, hot_dsp_ram):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("C++ compiler unavailable")
    exe = tmp_path / "resampler-zero-fast-test"
    source = ROOT / "engines/test/resampler_zero_fast_test.cc"
    include = ROOT / "engines/include"
    command = [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-O2"]
    if hot_dsp_ram:
        command.append("-DFM1_HOT_DSP_RAM=1")
    command.extend(["-I", str(include), str(source), "-o", str(exe)])
    built = subprocess.run(command, check=False, capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(exe)], check=False, capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr
    assert "full ring state" in ran.stdout
