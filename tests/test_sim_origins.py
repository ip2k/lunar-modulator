"""The simulator page's localhost exception (owner, 2026-10-06): served
from localhost, 127.0.0.1 or [::1], it takes an embedding parent and ?load=
files on any local origin; the public site keeps to its own origin. The
page's pure functions under Node (sim/web/test/origins.mjs); the page itself
is checked in headless Chromium by sim/web/test/files.mjs on the Docker host."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_the_localhost_exception():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    r = subprocess.run([node, str(ROOT / "sim" / "web" / "test" / "origins.mjs"), str(ROOT / "sim" / "web" / "www")],
                       capture_output=True, text=True, timeout=60)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert r.returncode == 0 and out["pass"], out
