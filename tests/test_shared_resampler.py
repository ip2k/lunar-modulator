"""Shared coefficients preserve the resampler's existing measurement output."""
import json
import shutil
import subprocess

import pytest

from tests.engine_helpers import ROOT

CASES = [
    ["tables"], ["passthrough"], ["refuse"], ["window"],
    *[["blocks", "--in-rate", str(rate)]
      for rate in (96000, 47872.34, 48000, 88236, 176472)],
    *[["extreme", "--in-rate", str(rate)]
      for rate in (96000, 47872.34, 48000, 88236, 176472)],
    ["sweep", "--in-rate", "96000", "--from", "1000", "--to", "24000", "--step", "1000"],
    ["sweep", "--in-rate", "47872.34", "--from", "1000", "--to", "23000", "--step", "1000"],
]


@pytest.fixture(scope="session")
def resampler_profiles(tmp_path_factory):
    if not shutil.which("make") or not shutil.which("c++"):
        pytest.skip("no host C++ toolchain")
    root = tmp_path_factory.mktemp("shared-resampler")
    binaries = []
    for shared in (0, 1):
        out = root / str(shared)
        binary = out / "fm1-resampler-test"
        subprocess.run([
            "make", "-s", "-C", str(ROOT / "engines"),
            f"BUILD={out}", f"FM1_SHARED_RESAMPLER={shared}",
            "FM1_GPL_MODS=0", str(binary),
        ], check=True)
        binaries.append(binary)
    return binaries


@pytest.mark.parametrize("shard", range(16))
def test_shared_resampler(resampler_profiles, shard):
    outputs = [json.loads(subprocess.check_output([str(binary), *CASES[shard]], text=True))
               for binary in resampler_profiles]
    assert outputs[0] == outputs[1]
