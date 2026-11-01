"""Actual offline candidate through the native adapter/common core. No devices."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
MODES = ["stream", "clock", "nested_irq", "frozen_clock", "fault_records",
         "wrong_core", "early_hold", "prepoison", "bad_setup", "no_entry",
         "late_entry", "cleanup_failure", "lifetime"] + [f"partial_{i}" for i in range(1, 50)]

@pytest.mark.parametrize("sanitize", [False, True])
def test_actual_candidate(tmp_path, sanitize):
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc")
    if not cc:
        pytest.skip("C compiler unavailable")
    fixture = ROOT / "tests/fixtures/renderer_pipeline"
    exe = tmp_path / "cpu1-candidate"
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitize else []
    subprocess.run([cc, "-std=c11", "-O1", "-g", "-pthread", "-Wall", "-Wextra", "-DLUNAR_CPU1_CANDIDATE_HOST=1",
                    "-Werror", "-Wno-unused-function", *flags,
                    "-I"+str(fixture), "-I"+str(ROOT/"firmware/native"),
                    str(fixture/"cpu1_candidate_check.c"), str(ROOT/"firmware/native/cpu1_candidate.c"), "-o", str(exe)], check=True, timeout=30)
    # Apple ASan does not implement LeakSanitizer; these fixtures own no heap.
    env = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks="+str(int(sys.platform != "darwin")), UBSAN_OPTIONS="halt_on_error=1")
    for mode in MODES:
        result = subprocess.run([str(exe), mode], check=False, env=env, timeout=5,
                                capture_output=True, text=True)
        assert result.returncode == 0, (mode, result.stdout, result.stderr)
        assert f"CPU1_CANDIDATE PASS {mode} " in result.stdout
