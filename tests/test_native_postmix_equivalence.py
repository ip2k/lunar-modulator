# SPDX-License-Identifier: MIT
"""Bitwise equivalence for the fused native scope/peak/master-gain pass."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "native" / "fm1_postmix_equivalence.c"
SOURCE = ROOT / "sim" / "web" / "src"


@pytest.mark.parametrize(
    ("optimization", "sanitizer"),
    [("-O0", None), ("-O2", None), ("-O1", "undefined")],
)
def test_fused_postmix_matches_original_two_pass(optimization, sanitizer, tmp_path):
    compiler = shutil.which("cc") or shutil.which("clang")
    if not compiler:
        pytest.skip("a C compiler is required for the native equivalence harness")
    executable = tmp_path / "postmix-equivalence"
    command = [
        compiler, "-std=c99", optimization, "-fno-fast-math",
        "-ffp-contract=off", "-Wall", "-Wextra", "-Werror",
        "-I", str(SOURCE), str(HARNESS), "-lm", "-o", str(executable),
    ]
    if sanitizer:
        command[1:1] = [f"-fsanitize={sanitizer}", "-fno-sanitize-recover=all"]
    subprocess.run(
        command,
        check=True, capture_output=True, text=True,
    )
    result = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "postmix optimized/reference exact equivalence: PASS (58608 cases)"
