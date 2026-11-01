"""Release-audit regressions using only the bounded native sequencer build."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ["seq_clip", "seq_engine", "seq_cmd", "seq_persist", "seq_capture"]


def test_playing_capture_offset_loop(tmp_path):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    exe = tmp_path / "capture-offset"
    subprocess.run([cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                    "-Iengines/include", "engines/test/seq_capture_offset_test.c",
                    *[f"engines/seq/{s}.c" for s in CORE], "-lm", "-o", str(exe)],
                   cwd=ROOT, check=True)
    result = subprocess.run([str(exe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "27 cases" in result.stdout


def test_released_lane_host_dispatch(tmp_path):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    exe = tmp_path / "seq-host"
    subprocess.run([cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                    "-Iengines/include", "engines/test/seq_host_test.c",
                    *[f"engines/seq/{s}.c" for s in CORE + ["seq_host", "fx_host", "mfx_host"]],
                    "-lm", "-o", str(exe)], cwd=ROOT, check=True)
    result = subprocess.run([str(exe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '"ok":true' in result.stdout


@pytest.mark.parametrize("checking", [False, True])
def test_playing_capture_overflow_is_transactional(tmp_path, checking):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    exe = tmp_path / "capture-overflow"
    subprocess.run([cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                    *(["-DSQ_CHECK_INDEX"] if checking else []), "-Iengines/include",
                    "engines/test/seq_capture_overflow_test.c",
                    *[f"engines/seq/{s}.c" for s in CORE], "-lm", "-o", str(exe)],
                   cwd=ROOT, check=True)
    result = subprocess.run([str(exe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "8 cases" in result.stdout
