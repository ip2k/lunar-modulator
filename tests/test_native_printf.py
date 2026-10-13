"""Pinned native formatter: UI formats, truncation and untouched guards."""
import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from tests.engine_helpers import ROOT


@pytest.fixture(scope="session")
def native_formatter(tmp_path_factory):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("no host C compiler")
    source = ROOT / "firmware/third_party/printf"
    inventory = json.loads((source / "inventory.json").read_text())
    for name, digest in inventory["files"].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    binary = tmp_path_factory.mktemp("native-printf") / "check"
    subprocess.run([
        cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
        "-ffunction-sections", "-fdata-sections",
        "-Wl,-dead_strip" if sys.platform == "darwin" else "-Wl,--gc-sections",
        f"-I{source}", str(ROOT / "tests/native_printf_check.c"),
        str(source / "printf/printf.c"), "-o", str(binary),
    ], check=True)
    return binary


@pytest.mark.parametrize("shard", range(16))
def test_native_formatter(native_formatter, shard):
    subprocess.run([str(native_formatter), str(shard)], check=True)
