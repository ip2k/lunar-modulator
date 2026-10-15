# SPDX-License-Identifier: MIT
"""Bitwise check the mix-bus fabsf fast path against libc reference code."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "native" / "fm1_mix_limiter_equivalence.c"
INCLUDE = ROOT / "engines" / "include"


@pytest.mark.parametrize(
    ("optimization", "sanitizer"),
    [("-O0", None), ("-O2", None), ("-O1", "undefined")],
)
def test_mix_limiter_matches_fabsf_reference(optimization, sanitizer, tmp_path):
    compiler = shutil.which("cc") or shutil.which("clang")
    if not compiler:
        pytest.skip("a C compiler is required for the native equivalence harness")
    executable = tmp_path / "mix-limiter-equivalence"
    command = [
        compiler, "-std=c99", optimization, "-fno-fast-math",
        "-fno-builtin-fabsf", "-Wall", "-Wextra", "-Werror",
        "-I", str(INCLUDE), str(HARNESS), "-lm", "-o", str(executable),
    ]
    if sanitizer:
        command[1:1] = [f"-fsanitize={sanitizer}", "-fno-sanitize-recover=all"]
    compiled = subprocess.run(command, capture_output=True, text=True)
    if sanitizer and compiled.returncode and "libubsan" in compiled.stderr and "cannot find" in compiled.stderr:
        pytest.skip("host compiler is present but its UBSan runtime is not installed")
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "mix limiter optimized/reference exact equivalence: PASS (4608 cases)"
