"""Bitwise host-render equivalence for Six-Op's cached velocity accent."""

import subprocess

from tests.engine_helpers import ENGINES, renderer  # noqa: F401


def test_cached_accent_matches_per_block_reference(renderer):  # noqa: F811
    tool = ENGINES / "build" / "fm1-sixop-accent-cache-test"
    result = subprocess.run([str(tool)], check=True, capture_output=True, text=True)
    assert "24000 stereo frames bitwise equal" in result.stdout
