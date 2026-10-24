"""The hardware workload must exercise the actual shared renderer on desktop."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = "dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance"


def build_reference(modules):
    cc = os.environ.get("FM1_SIM_CC", "cc")
    cxx = os.environ.get("FM1_SIM_CXX", "c++")
    if not shutil.which("make") or not shutil.which(cxx):
        pytest.skip("native toolchain unavailable")
    extra = os.environ.get("FM1_SIM_EXTRA", "") + " -DFM1_APP_EXTERNAL_ARENAS=1"
    tag = hashlib.sha256((cc + cxx + extra + modules).encode()).hexdigest()[:12]
    build = ROOT / "sim/web/build" / f"devkit-renderer-{tag}"
    target = build / "fm1-devkit-renderer-ref"
    subprocess.run([
        "make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
        str(ROOT / "sim/web/mk/sim.mk"), "-f", str(ROOT / "tools/jieli/renderer.mk"),
        f"SIM={ROOT / 'sim/web'}", f"BUILD={build}", "FM1_GPL_MODS=0",
        f"FM1_MODULES={modules}", f"CC={cc}", f"CXX={cxx}", f"EXTRA={extra}",
        "-j4", str(target),
    ], check=True, stdout=subprocess.DEVNULL)
    return target


def test_shared_renderer_schedule_and_pcm(tmp_path):
    target = build_reference(MODULES)
    pcm = tmp_path / "reference.pcm"
    result = subprocess.run([str(target), str(pcm)], capture_output=True, text=True, check=True)
    rows = [dict(re.findall(r"(\w+)=(\w+)", line)) for line in result.stdout.splitlines()]
    assert len(rows) == 8
    for i, row in enumerate(rows):
        assert int(row["completed"]) == i + 1
        assert int(row["case"]) == i % 4
        assert int(row["blocks"]) == (i + 1) * 5513
        assert row["invalid"] == row["clipped"] == "0"
        assert 0 < int(row["arena"]) <= 148 * 1024
    assert int(rows[-1]["controls"]) > 1000
    assert pcm.stat().st_size == 8 * 5513 * 64 * 4
    # The same source and schedule, fresh process: reproducible PCM receipts.
    again = tmp_path / "again.pcm"
    replay = subprocess.run([str(target), str(again)], capture_output=True, text=True, check=True)
    assert result.stdout == replay.stdout
    assert hashlib.sha256(pcm.read_bytes()).digest() == hashlib.sha256(again.read_bytes()).digest()


def test_missing_effect_refuses_whole_workload():
    target = build_reference(MODULES.replace(",comp", ""))
    result = subprocess.run([str(target)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "initialization refused: stage 1" in result.stderr
    assert "LUNAR_RENDERER completed=" not in result.stdout
