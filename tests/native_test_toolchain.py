"""Optional target-compiler access for desktop-only native tests."""
import os
from pathlib import Path

import pytest


def configured_target_toolchain():
    """Skip only when no toolchain was configured; invalid paths must fail use."""
    if "FM1_NATIVE_TOOLCHAIN" not in os.environ:
        pytest.skip("FM1_NATIVE_TOOLCHAIN is absent; target-only compile check skipped")
    return Path(os.environ["FM1_NATIVE_TOOLCHAIN"])
