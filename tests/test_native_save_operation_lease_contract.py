"""Exercise the production SAVE service with explicit fake host callbacks."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/native/save_operation_lease_contract.c"


def test_save_service_generation_and_unresolved_transport_contract(tmp_path):
    compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if compiler is None:
        pytest.skip("a host C compiler is required for the SAVE service harness")
    executable = tmp_path / "save-operation-lease-contract"
    includes = [
        ROOT / "firmware/native", ROOT / "engines/include", ROOT / "engines/state",
        ROOT / "engines/mod", ROOT / "sim/web/src",
    ]
    subprocess.run(
        [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
         "-DFM1_TFT_INDEXED=1", "-DFM1_STATE_BIN_COMPACT_WRITER",
         *["-I" + str(path) for path in includes], str(SOURCE), "-o", str(executable)],
        cwd=ROOT, check=True,
    )
    result = subprocess.run([str(executable)], cwd=ROOT, check=True, text=True,
                            capture_output=True)
    assert "actual SAVE service callback composition: PASS" in result.stdout
