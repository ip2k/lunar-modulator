from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("enabled", [False, True], ids=["disabled", "enabled"])
def test_native_irq_profile_accounting(tmp_path, enabled):
    compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if compiler is None:
        pytest.skip("a C compiler is required for the IRQ accounting harness")
    executable = tmp_path / ("irq-profile-enabled" if enabled else "irq-profile-disabled")
    command = [
        compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/native"),
    ]
    if enabled:
        command.append("-DLUNAR_DIAGNOSTIC_IRQ_PROFILE=1")
    command += [str(ROOT / "tests/native/irq_profile.c"), "-o", str(executable)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    subprocess.run([str(executable)], check=True, capture_output=True, text=True)
