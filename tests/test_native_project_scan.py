# SPDX-License-Identifier: MIT
"""CRC-valid malformed files and uncertain validation during recovery."""
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def adapter(tmp_path_factory):
    executable = tmp_path_factory.mktemp("project-scan") / "adapter"
    subprocess.run(["cc", "-std=c99", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-I", str(ROOT / "firmware/native"),
                    str(ROOT / "tests/native/project_scan.c"),
                    "-o", str(executable)], check=True)
    return executable


@pytest.mark.parametrize("case", range(6))
def test_project_scan_validation(adapter, case):
    subprocess.run([str(adapter), str(case)], check=True)
