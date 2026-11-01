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
