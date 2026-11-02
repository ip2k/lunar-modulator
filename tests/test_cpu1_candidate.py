"""Actual offline candidate through the native adapter/common core. No devices."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
MODES = ["stream", "clock", "clock_fraction", "enabled_irq", "nested_irq", "frozen_clock", "fault_records",
         "wrong_core", "early_hold", "prepoison", "bad_setup", "no_entry",
         "late_entry", "cleanup_failure", "lifetime", "stalled_launch", "stalled_ready"]
MODES += ["poison_worker_failed", "poison_worker_raw_fault", "poison_worker_clock_start",
          "poison_worker_clock_end", "poison_wait_failed", "poison_wait_raw_fault",
          "poison_wait_clock", "poison_publish_clock", "poison_direct_step"]
MODES += [f"write_{kind}_{i}" for kind in ("a", "n") for i in range(1, 65)]
MODES += [f"read_{i}" for i in range(1, 45)]
MODES += [f"vector_{kind}_{i}" for kind in ("a", "n") for i in range(1, 167)]
MODES += [f"invalid_{i}" for i in range(12)]

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

@pytest.mark.parametrize("flags", [
    ["-DLUNAR_NATIVE_PIPELINE_ENABLE=1"],
    ["-DLUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE=0"],
    ["-DLUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE=2"],
    ["-DLUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE=1"],
    ["-DLUNAR_CPU1_CANDIDATE_STOCK_SPL=1"],
    ["-DLUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE=1", "-DLUNAR_CPU1_CANDIDATE_STOCK_SPL=0"],
    ["-DLUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE=1", "-DLUNAR_CPU1_CANDIDATE_STOCK_SPL=2"],
    ["-DLUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE=1", "-DLUNAR_CPU1_CANDIDATE_STOCK_SPL=1"],
    ["-DLUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE=1", "-DLUNAR_CPU1_CANDIDATE_STOCK_SPL=1", "-DLUNAR_CPU1_CANDIDATE_PI32V2=1"],
])
def test_target_opt_in_rejected_on_host(flags):
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc")
    if not cc:
        pytest.skip("C compiler unavailable")
    result = subprocess.run([cc, "-E", *flags, str(ROOT/"firmware/native/renderer_pipeline_native.c")],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and "error:" in result.stderr

def test_default_has_no_candidate_header(tmp_path):
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc")
    if not cc:
        pytest.skip("C compiler unavailable")
    source = str(ROOT/"firmware/native/renderer_pipeline_native.c")
    result = subprocess.run([cc, "-E", source], check=True, capture_output=True, text=True, timeout=10)
    assert "cpu1_candidate_target" not in result.stdout
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-c", source,
                    "-o", str(tmp_path/"disabled.o")], check=True, timeout=15)
