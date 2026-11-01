"""Capture's actual app/panel refusal and retained-history contract."""
import hashlib
import json
import os
import shutil
import subprocess

import pytest

from tests.engine_helpers import ROOT, GPL_MODS


def test_capture_feedback_and_retained_history(tmp_path):
    engines, sim = ROOT / "engines", ROOT / "sim" / "web"
    if not shutil.which("make") or not (shutil.which("c++") or shutil.which("g++")):
        pytest.skip("no make / C++ compiler")
    # Match the app harness's isolated flag/GPL variants so sanitizer and
    # permissive builds never reuse incompatible engine objects.
    extra = os.environ.get("FM1_SIM_EXTRA", "")
    flags = {
        "EXTRA": extra,
        "OPT": os.environ.get("FM1_SIM_OPT", "-O2"),
        "CC": os.environ.get("FM1_SIM_CC", "cc"),
        "CXX": os.environ.get("FM1_SIM_CXX", "c++"),
    }
    tag = hashlib.sha256(json.dumps(flags, sort_keys=True).encode()).hexdigest()[:8]
    build = sim / "build" / ("native" if not extra and flags["OPT"] == "-O2" else f"native-{tag}")
    if not GPL_MODS:
        build = build.with_name(build.name + "-mit")
    target = build / "fm1-capture-check"
    subprocess.run([
        "make", "-C", str(engines), "-f", "Makefile", "-f", str(sim / "mk" / "sim.mk"),
        "-f", str(sim / "test" / "capture.mk"), f"SIM={sim}", f"BUILD={build}",
        f"FM1_GPL_MODS={int(GPL_MODS)}", "-j4",
        *[f"{key}={value}" for key, value in flags.items()], str(target),
    ], check=True, stdout=subprocess.DEVNULL)
    result = subprocess.run([str(target), str(tmp_path / "capture-refused.ppm")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("PASS app Capture:")
