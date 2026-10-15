"""Check placement and exact coefficient bytes without the vendor toolchain."""
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/jieli"))
from audit_link import Elf  # noqa: E402


def test_hot_shared_tables_move_without_changing_coefficients(tmp_path):
    clang = shutil.which("clang++")
    if not clang:
        pytest.skip("Clang cross-object compiler unavailable")
    variants = {}
    for hot in (0, 1):
        obj = tmp_path / f"tables-{hot}.o"
        subprocess.run([
            clang, "--target=i386-unknown-linux-gnu", "-ffreestanding",
            "-std=c++11", "-Wall", "-Wextra", "-Werror", "-O2",
            "-DFM1_RESAMPLER_SHARED_TABLES=1", f"-DFM1_HOT_DSP_RAM={hot}",
            "-I", str(ROOT / "engines/include"), "-c",
            str(ROOT / "engines/src/resampler_tables.cc"), "-o", str(obj),
        ], check=True, capture_output=True, text=True)
        elf = Elf(obj.read_bytes())
        tables = {}
        for name, size in (("fm1_resampler_kernel", 769 * 4),
                           ("fm1_resampler_lowpass", 62 * 4)):
            symbols = [s for s in elf.symbols if s["name"] == name and s["shndx"]]
            assert len(symbols) == 1
            symbol = symbols[0]
            assert symbol["size"] == size
            section = elf.sections[symbol["shndx"]]
            assert section["name"] == (".ram_dsp.tables" if hot else ".rodata")
            assert section["flags"] & 2  # allocated
            assert not section["flags"] & 1  # coefficients stay const
            start = section["offset"] + symbol["value"]
            tables[name] = elf.data[start:start + size]
        variants[hot] = tables
    assert variants[0] == variants[1]
