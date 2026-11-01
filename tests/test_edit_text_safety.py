"""Exercise actual edit parser/formatter without linking the audio engine bank."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests.engine_helpers import ROOT


@pytest.fixture(scope="module")
def edit_text_probe():
    cc = shutil.which("clang")
    if not cc:
        pytest.skip("clang needed for float-cast-overflow sanitizer")
    scratch = ROOT / "scratch/edit-parser-safety"
    scratch.mkdir(parents=True, exist_ok=True)
    # All reproducible files are local to this lane and removed on fixture exit.
    with tempfile.TemporaryDirectory(prefix="probe-", dir=scratch) as directory:
        build = Path(directory)
        (build / "fm1_modules.h").write_text("#define FM1_WITH_DX7 0\n")
        exe = build / "edit-text-check"
        linker = "-Wl,-dead_strip" if sys.platform == "darwin" else "-Wl,--gc-sections"
        subprocess.run([
            cc, "-std=c99", "-O1", "-g", "-ffunction-sections", "-fdata-sections",
            "-fsanitize=undefined,float-cast-overflow", "-fno-sanitize-recover=all", linker,
            f"-I{build}", f"-I{ROOT / 'sim/web/src'}", f"-I{ROOT / 'engines/include'}",
            f"-I{ROOT / 'engines/state'}", f"-I{ROOT / 'engines/host'}",
            str(ROOT / "sim/web/src/fm1_edit.c"),
            str(ROOT / "sim/web/test/fm1_edit_text_check.c"), "-lm", "-o", str(exe),
        ], check=True, capture_output=True, text=True)
        yield exe


@pytest.mark.parametrize("value,accepted,bits", [
    ("nan", 0, 0), ("NaN", 0, 0), ("inf", 0, 0), ("-inf", 0, 0),
    ("1e30", 0, 0), ("4294967296", 0, 0), ("4294967295", 0, 0),
    ("4294967040", 1, 4294967040), ("0", 1, 0), ("-0", 1, 0),
    ("0.75", 1, 0), ("2.9", 1, 2), ("-0.75", 1, 4294967295),
    ("-1", 1, 4294967295), ("-1e30", 1, 4294967295),
])
def test_index_conversion(edit_text_probe, value, accepted, bits):
    subprocess.run([str(edit_text_probe), value, str(accepted), str(bits)],
                   check=True, capture_output=True, text=True)


def test_record_text_and_wire_roundtrips(edit_text_probe):
    subprocess.run([str(edit_text_probe)], check=True, capture_output=True, text=True)
