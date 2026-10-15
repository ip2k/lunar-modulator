# SPDX-License-Identifier: MIT
"""First-party helpers shared with the permissive reusable core."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_diagnostic_and_postmix_headers_remain_mit():
    for relative in (
        "engines/include/engine_render_profile.h",
        "sim/web/src/fm1_postmix.h",
    ):
        header = (ROOT / relative).read_text(encoding="utf-8")
        assert header.startswith("/* SPDX-License-Identifier: MIT */"), relative
        assert "SPDX-License-Identifier: GPL" not in header, relative
