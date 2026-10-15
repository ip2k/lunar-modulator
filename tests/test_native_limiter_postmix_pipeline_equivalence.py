# SPDX-License-Identifier: MIT
"""Bitwise-check the hot-DSP peak handoff against the established pipeline."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "native" / "fm1_limiter_postmix_pipeline_equivalence.c"
INCLUDE = ROOT / "engines" / "include"
SOURCE = ROOT / "sim" / "web" / "src"


@pytest.mark.parametrize(
    ("optimization", "sanitizer"),
    [("-O0", None), ("-O2", None), ("-O1", "undefined")],
)
def test_hot_pipeline_peak_matches_baseline(optimization, sanitizer, tmp_path):
    compiler = shutil.which("cc") or shutil.which("clang")
    if not compiler:
        pytest.skip("a C compiler is required for the native pipeline harness")
    executable = tmp_path / "limiter-postmix-pipeline-equivalence"
    command = [
        compiler, "-std=c99", optimization, "-DFM1_HOT_DSP_RAM=1",
        "-DFM1_EXPERIMENT_POSTMIX_PEAK_HANDOFF=1",
        "-fno-fast-math", "-fno-builtin-fabsf", "-ffp-contract=off",
        "-Wall", "-Wextra", "-Werror", "-I", str(INCLUDE), "-I", str(SOURCE),
        str(HARNESS), "-lm", "-o", str(executable),
    ]
    if sanitizer:
        command[1:1] = [f"-fsanitize={sanitizer}", "-fno-sanitize-recover=all"]
    compiled = subprocess.run(command, capture_output=True, text=True)
    if sanitizer and compiled.returncode and "libubsan" in compiled.stderr and "cannot find" in compiled.stderr:
        pytest.skip("host compiler is present but its UBSan runtime is not installed")
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "limiter/postmix peak pipeline exact equivalence: PASS (223860 cases)"
