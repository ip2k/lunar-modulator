# SPDX-License-Identifier: MIT
"""Fault-model check for a packed slot that reserves each physical tail page."""
from pathlib import Path
import subprocess

from tests.native_test_flags import native_host_flags

ROOT = Path(__file__).resolve().parents[1]


def test_packed_slots_reserve_tail_pages(tmp_path):
    binary = tmp_path / "storage-tail-pages"
    subprocess.run([
        "cc", "-std=c99", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
        *native_host_flags(), "-I" + str(ROOT / "firmware/native"),
        str(ROOT / "tests/native/storage_tail_pages.c"), "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True, timeout=20)
