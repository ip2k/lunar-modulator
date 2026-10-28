"""Opt-in render-owned DX7 capacity: PCM, voice ownership and block boundary."""
import subprocess
import pytest
from tests.engine_helpers import ENGINES, renderer  # noqa: F401


@pytest.mark.parametrize("rate", [16385, 44118, 96000, 384000])
def test_render_owned_voice_budget(renderer, rate):  # noqa: F811
    result = subprocess.run([str(ENGINES / "build/fm1-dx7-budget-test"), str(rate)],
                            check=True, capture_output=True, text=True, timeout=30)
    assert result.stdout.startswith("PASS default12 exact PCM"), result.stdout
