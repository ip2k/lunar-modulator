"""App import atomicity with the real clip helper's allocation refusal."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("sanitize", [False, True])
def test_app_import_refusal_and_clip_merge(tmp_path, sanitize):
    if not sys.platform.startswith("linux"):
        pytest.skip("GNU-compatible linker wrapping is required")
    cc, cxx = shutil.which("clang"), shutil.which("clang++")
    if not cc or not cxx or not shutil.which("make"):
        pytest.skip("native clang toolchain unavailable")
    build = tmp_path / "build"
    exe = build / "fm1-sim-render"
    flags = ("-DFM1_EDIT_CHECK_CLIP_FAULT=1 -Wl,--wrap=fm1_state_clip_into "
             "-Wl,--wrap=realloc -Wno-unused-command-line-argument")
    if sanitize:
        flags += " -fsanitize=address,undefined -fno-sanitize=shift -fno-omit-frame-pointer"
    subprocess.run([
        "make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
        str(ROOT / "sim/web/mk/sim.mk"), f"SIM={ROOT / 'sim/web'}", f"BUILD={build}",
        "FM1_GPL_MODS=0", f"CC={cc}", f"CXX={cxx}", f"EXTRA={flags}", "-j4", str(exe),
    ], check=True, stdout=subprocess.DEVNULL)
    env = dict(os.environ, ASAN_OPTIONS="halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1")
    result = subprocess.run([str(exe), "--edit-check"], capture_output=True, text=True,
                            timeout=300, env=env)
    assert result.returncode == 0, (result.stdout, result.stderr)
