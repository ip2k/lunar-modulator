"""Host-only regression tests for the isolated GPL Felucca loader probe.

These compile the fake-NOR fixture, never a target loader or flash transport.
"""
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "firmware" / "third_party" / "expanded-loader-offline"
CORE = PROBE / "ldr_core.c"
HARNESS = PROBE / "test_ldr_core.c"
CC = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")


@pytest.mark.skipif(CC is None, reason="no host C compiler")
def test_expanded_loader_fake_nor_regression(tmp_path):
    exe = tmp_path / "expanded-loader-fake-nor"
    subprocess.run(
        [CC, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
         str(HARNESS), "-o", str(exe)],
        check=True, capture_output=True, text=True,
    )
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    assert "offline core test passed" in result.stdout
    assert "corrupt package is rejected before any erase ok" in result.stdout
    assert "changed host chunk is refused before erase   ok" in result.stdout
    # Recompile the same portable core with the proposed D7000 app boundary.
    bounded = tmp_path / "expanded-loader-d7000-fake-nor"
    subprocess.run(
        [CC, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
         "-DAPP_HI=0xD7000u", str(HARNESS), "-o", str(bounded)],
        check=True, capture_output=True, text=True,
    )
    bounded_result = subprocess.run([str(bounded)], check=True, capture_output=True, text=True)
    assert "D7000 stage boundary is outside app writes" in bounded_result.stdout
    assert "D7000 profile transaction preserves stage and later banks" in bounded_result.stdout


@pytest.mark.skipif(CC is None, reason="no host C compiler")
def test_expanded_loader_core_rejects_non_fixture_build(tmp_path):
    obj = tmp_path / "target-core.o"
    result = subprocess.run(
        [CC, "-std=c99", "-Wall", "-Wextra", "-Werror", "-c", str(CORE), "-o", str(obj)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "host-test-only" in result.stderr
