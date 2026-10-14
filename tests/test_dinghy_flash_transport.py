"""Compile and run the flash HAL against deterministic host register mocks."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/native/test_dinghy_flash_transport.c"


def test_dinghy_spi_failures_propagate_and_cleanup(tmp_path):
    compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if compiler is None:
        pytest.skip("a host C compiler is required for the register-mock harness")
    executable = tmp_path / "flash-transport-test"
    subprocess.run(
        [compiler, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
         "-Wno-unused-function", "-Wno-int-to-pointer-cast",
         str(SOURCE), "-o", str(executable)],
        cwd=ROOT, check=True,
    )
    subprocess.run([str(executable)], cwd=ROOT, check=True)
