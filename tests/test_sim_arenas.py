"""Compact storage must run the same mixer/effect/control path as the simulator."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_external_arenas_match_builtin_renderer():
    if not shutil.which("make") or not shutil.which("c++"):
        pytest.skip("native compiler unavailable")
    results = []
    for compact in (0, 1):
        build = ROOT / "sim/web/build" / f"arenas-{compact}"
        target = build / "fm1-arena-check"
        subprocess.run([
            "make", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
            str(ROOT / "sim/web/mk/sim.mk"), f"SIM={ROOT / 'sim/web'}",
            f"BUILD={build}", "FM1_GPL_MODS=0", "FM1_MODULES=all", "-j4",
            f"EXTRA={os.environ.get('FM1_SIM_EXTRA', '')} -DFM1_APP_EXTERNAL_ARENAS={compact}",
            str(target),
        ], check=True, stdout=subprocess.DEVNULL)
        results.append(json.loads(subprocess.check_output([str(target)], text=True)))
    assert results[0]["pcm_hash"] == results[1]["pcm_hash"]
    assert results[0]["app_bytes"] - results[1]["app_bytes"] == 4 * 512 * 1024 + 10 * 256 * 1024
    assert results[1]["app_bytes"] < 256 * 1024
