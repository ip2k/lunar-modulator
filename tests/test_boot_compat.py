"""Desktop test for the FM-1 boot_info bridge
(firmware/third_party/fm1-nes/boot_compat.c, derived from fm1-nes, Apache-2.0).

Compiles the bridge with -DFM1_BOOT_COMPAT_TEST together with its driver
(firmware/boot/boot_compat_test.c) and runs it, so the 6-word copy /
zero-6..22 contract is exercised on the host. The JieLi compile check
(tools/jieli/in-container.sh) separately checks that the pi32v2 object calls
nothing but __real_boot_info_init; the linked machine code is not pinned yet
(DEVELOPERS.md I1). This just proves the C is correct.
"""
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOT = ROOT / "firmware" / "boot"
BRIDGE = ROOT / "firmware" / "third_party" / "fm1-nes" / "boot_compat.c"


@pytest.mark.skipif(not (shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")),
                    reason="no host C compiler")
def test_boot_compat_contract(tmp_path):
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    exe = tmp_path / "boot_compat_test"
    subprocess.run(
        [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-DFM1_BOOT_COMPAT_TEST",
         str(BRIDGE), str(BOOT / "boot_compat_test.c"), "-o", str(exe)],
        check=True)
    out = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    assert "source preserved" in out.stdout
