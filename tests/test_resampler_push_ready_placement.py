"""The checked resampler push helper is opt-in RAM code and is not retained unused."""
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
    return Elf(obj.read_bytes())


def _push_ready_symbols(elf):
    return [symbol for symbol in elf.symbols
            if "fm1_resampler_push_ready_" in symbol["name"] and symbol["shndx"]]


def test_used_push_ready_helper_is_in_ram_only_for_hot_elf(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Clang cross-object compiler unavailable")
    source = tmp_path / "uses-push-ready.cc"
    source.write_text(
        '#include "fm1_resampler.h"\n'
        'using push_fn = uint32_t (*)(fm1_resampler_t *, const float *, uint32_t);\n'
        'uint32_t call_push_ready(fm1_resampler_t *r, const float *in, uint32_t n) {\n'
        '  push_fn volatile fn = &fm1_resampler_push_ready_;\n'
        '  return fn(r, in, n);\n'
        '}\n',
        encoding="utf-8",
    )

    hot_elf = _compile(tmp_path, compiler, source, hot=True)
    hot_symbols = _push_ready_symbols(hot_elf)
    assert len(hot_symbols) == 1
    assert hot_elf.sections[hot_symbols[0]["shndx"]]["name"] == ".ram_dsp"

    default_elf = _compile(tmp_path, compiler, source, hot=False)
    default_symbols = _push_ready_symbols(default_elf)
    assert all(default_elf.sections[symbol["shndx"]]["name"] != ".ram_dsp"
               for symbol in default_symbols)


@pytest.mark.parametrize("hot", [False, True], ids=["default", "hot-dsp-ram"])
def test_unused_push_ready_helper_is_not_retained_with_werror(tmp_path, hot):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Clang cross-object compiler unavailable")
    source = tmp_path / "unused-push-ready.cc"
    source.write_text(
        '#include "fm1_resampler.h"\n'
        'int unrelated() { return FM1_RESAMPLER_DELAY; }\n',
        encoding="utf-8",
    )
    assert not _push_ready_symbols(_compile(tmp_path, compiler, source, hot=hot))
