"""Inline stage 1 into the opt-in RAM pop without retaining unused copies."""
import pathlib
import shutil
import subprocess
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/jieli"))
from audit_link import Elf  # noqa: E402


def _compile(tmp_path, compiler, source, *, hot):
    obj = tmp_path / f"{source.stem}-{int(hot)}.o"
    command = [
        compiler, "--target=i386-unknown-linux-gnu", "-ffreestanding",
        "-std=c++11", "-Wall", "-Wextra", "-Werror", "-O2",
        f"-DFM1_HOT_DSP_RAM={int(hot)}", "-I", str(ROOT / "engines/include"),
        "-c", str(source), "-o", str(obj),
    ]
    built = subprocess.run(command, check=False, capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    return obj


def test_stage1_is_inlined_into_ram_pop_only_for_hot_elf(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Clang cross-object compiler unavailable")
    source = tmp_path / "uses-stage1.cc"
    source.write_text(
        '#include "fm1_resampler.h"\n'
        'float call_pop(fm1_resampler_t *r) {\n'
        '  return fm1_resampler_pop_ready_(r);\n'
        '}\n',
        encoding="utf-8",
    )

    hot_elf = Elf(_compile(tmp_path, compiler, source, hot=True).read_bytes())
    stage1 = [s for s in hot_elf.symbols
              if "fm1_resampler_intermediate_" in s["name"] and s["shndx"]]
    assert not stage1
    pop = [s for s in hot_elf.symbols
           if "fm1_resampler_pop_ready_" in s["name"] and s["shndx"]]
    assert len(pop) == 1
    assert hot_elf.sections[pop[0]["shndx"]]["name"] == ".ram_dsp"

    default_elf = Elf(_compile(tmp_path, compiler, source, hot=False).read_bytes())
    default_stage1 = [s for s in default_elf.symbols
                      if "fm1_resampler_intermediate_" in s["name"] and s["shndx"]]
    assert all(default_elf.sections[s["shndx"]]["name"] != ".ram_dsp"
               for s in default_stage1)


@pytest.mark.parametrize("hot", [False, True], ids=["default", "hot-dsp-ram"])
def test_unused_stage1_helper_is_not_retained_with_werror(tmp_path, hot):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Clang cross-object compiler unavailable")
    source = tmp_path / "unused-stage1.cc"
    source.write_text(
        '#include "fm1_resampler.h"\n'
        'int unrelated() { return FM1_RESAMPLER_DELAY; }\n',
        encoding="utf-8",
    )
    elf = Elf(_compile(tmp_path, compiler, source, hot=hot).read_bytes())
    assert not [s for s in elf.symbols
                if "fm1_resampler_intermediate_" in s["name"] and s["shndx"]]
