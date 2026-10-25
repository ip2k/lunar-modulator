"""FM6 copied-kernel adapter: exact output and late-job ownership."""
import subprocess

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401


@pytest.mark.parametrize("rate", [16385, 44118, 96000, 384000])
@pytest.mark.parametrize("mode", [0, 1, 2], ids=["parallel", "rejected", "late-after-destroy"])
def test_copied_kernels_match_sequential_engine(renderer, rate, mode):  # noqa: F811
    result = subprocess.run([str(ENGINES / "build/fm1-dx7-kernel-test"), str(rate), str(mode)],
                            check=True, capture_output=True, text=True, timeout=60)
    assert result.stdout.startswith("PASS exact PCM"), result.stdout
