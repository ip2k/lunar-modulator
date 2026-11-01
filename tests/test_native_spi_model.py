"""Small host-only protocol and actual scanner proofs; owned pytest products."""
import os
from pathlib import Path
import shlex
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("case", ["spi", "scanner", "owner-fault"])
def test_injected_protocol_and_accepted_scanner(tmp_path, case):
    native = ROOT / "firmware/native"
    hal = ROOT / "firmware/third_party/dinghy/hal"
    sources = ([ROOT / "tests/fixtures/native_spi_model/check.c",
                native / "diagnostic_spi_model.c", native / "diagnostic_display.c"]
               if case == "spi" else ([ROOT / "tests/fixtures/selected_interactive/scanner.c"]
               if case == "scanner" else [ROOT / "tests/fixtures/selected_interactive/owner_fault.c",
               native / "selected_interactive_owner.c", native / "diagnostic_transport.c",
               native / "diagnostic_display.c", native / "diagnostic_spi_model.c"]))
    exe = tmp_path / case
    subprocess.run([os.environ.get("FM1_SIM_CC", "cc"), "-std=c11", "-O1",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                    "-DLUNAR_DIAGNOSTIC_OFFLINE_PROOF=1", "-DLUNAR_SELECTED_INTERACTIVE_PROOF=1", f"-I{native}", f"-I{hal}",
                    *shlex.split(os.environ.get("FM1_SIM_EXTRA", "")),
                    *(str(p) for p in sources), "-o", str(exe)], check=True, timeout=60)
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=10)
    print(result.stdout, end="")
    if case == "owner-fault":
        for mode in ["reentry", "draw-fault"]:
            result = subprocess.run([str(exe), mode], check=True, capture_output=True, text=True, timeout=10)
            print(result.stdout, end="")
