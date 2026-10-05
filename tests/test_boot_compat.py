"""Desktop test for the FM-1 boot_info bridge (firmware/boot/boot_compat.c).

Compiles the bridge with -DFM1_BOOT_COMPAT_TEST together with its driver and
runs it, so the 6-word copy / zero-6..22 contract is exercised on the host.
The on-chip machine code is pinned separately by tools/jieli/audit_link.py and
fm1-nes's audit_boot.py; this just proves the C is correct.
"""
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOT = ROOT / "firmware" / "boot"


@pytest.mark.skipif(not (shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")),
                    reason="no host C compiler")
def test_boot_compat_contract(tmp_path):
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    exe = tmp_path / "boot_compat_test"
    subprocess.run(
        [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-DFM1_BOOT_COMPAT_TEST",
         str(BOOT / "boot_compat.c"), str(BOOT / "boot_compat_test.c"), "-o", str(exe)],
        check=True)
    out = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    assert "source preserved" in out.stdout
