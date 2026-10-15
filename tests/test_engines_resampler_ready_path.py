"""Exact differential coverage for trusted-ready engine resampler calls."""
import pathlib
import shutil
import subprocess

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("hot_dsp_ram", [False, True], ids=["default", "hot-dsp-ram"])
def test_trusted_ready_path_matches_checked_api_bit_for_bit(tmp_path, hot_dsp_ram):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("C++ compiler unavailable")
    exe = tmp_path / "resampler-ready-path-test"
    source = ROOT / "engines/test/resampler_ready_path_test.cc"
    command = [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-O2"]
    if hot_dsp_ram:
        command.append("-DFM1_HOT_DSP_RAM=1")
    command += ["-I", str(ROOT / "engines/include"), str(source), "-o", str(exe)]
    built = subprocess.run(
        command,
        check=False, capture_output=True, text=True,
    )
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(exe)], check=False, capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr
    assert "match bit-for-bit" in ran.stdout


def test_hot_pop_helper_is_not_forced_into_unreferencing_translation_units(tmp_path):
    compiler = shutil.which("c++")
    nm = shutil.which("nm")
    if not compiler or not nm:
        pytest.skip("C++ compiler or nm unavailable")
    include = ROOT / "engines/include"
    used = tmp_path / "uses.cc"
    unused = tmp_path / "unused.cc"
    used.write_text(
        '#include "fm1_resampler.h"\n'
        'float call_ready(fm1_resampler_t *r) { return fm1_resampler_pop_ready_(r); }\n',
        encoding="utf-8",
    )
    unused.write_text(
        '#include "fm1_resampler.h"\n'
        'int unrelated() { return FM1_RESAMPLER_DELAY; }\n',
        encoding="utf-8",
    )
    objects = []
    for source in (used, unused):
        obj = tmp_path / (source.stem + ".o")
        built = subprocess.run(
            [compiler, "-std=c++11", "-O0", "-DFM1_HOT_DSP_RAM=1",
             "-I", str(include), "-c", str(source), "-o", str(obj)],
            check=False, capture_output=True, text=True,
        )
        assert built.returncode == 0, built.stderr
        objects.append(obj)
    symbols = []
    for obj in objects:
        inspected = subprocess.run([nm, "-a", str(obj)], check=False,
                                   capture_output=True, text=True)
        assert inspected.returncode == 0, inspected.stderr
        symbols.append(inspected.stdout)
    assert "fm1_resampler_pop_ready_" in symbols[0]
    assert "fm1_resampler_pop_ready_" not in symbols[1]
