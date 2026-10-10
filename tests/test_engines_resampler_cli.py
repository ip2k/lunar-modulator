"""Malformed measurement arguments must fail before allocating or looping."""
import json
import math
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cli(tmp_path_factory):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("no C++ compiler")
    target = tmp_path_factory.mktemp("resampler-cli") / "resampler"
    subprocess.run([compiler, "-std=c++11", "-O2", "-I", str(ROOT / "engines/include"),
                    str(ROOT / "engines/test/resampler_test.cc"), "-o", str(target)], check=True)
    return target


@pytest.mark.parametrize("args", [
    ["bench", "--outputs", "-1"],
    ["bench", "--outputs", "18446744073709551616"],
    ["bench", "--outputs", "4294967296"],
    ["bench", "--outputs", "4294967295"],  # derived input count exceeds API
    ["bench", "--outputs", "12junk"],
    ["bench", "--in-rate", "inf"],
    ["sweep", "--from", "-inf"],
    ["sweep", "--to", "nan"],
    ["sweep", "--step", "inf"],
    ["sweep", "--from", "1000", "--step", "1e-300"],
    ["peaks", "--in", "missing.wav", "--length", "-1"],
    ["peaks", "--in", "missing.wav", "--start", "-1"],
])
def test_invalid_args_fail_promptly(cli, args):
    result = subprocess.run([str(cli), *args], capture_output=True, timeout=5)
    assert result.returncode == 2


def test_peak_window_clamps_without_addition_overflow(cli, tmp_path):
    # SIZE_MAX is valid on 64-bit hosts; on 32-bit hosts it is rejected by the parser.
    values = [math.sin(2 * math.pi * 1000 * i / 44118) for i in range(2048)]
    raw = struct.pack("<2048f", *values)
    wav = tmp_path / "input.wav"
    wav.write_bytes(b"RIFF" + struct.pack("<I", 36 + len(raw)) + b"WAVEfmt " +
                   struct.pack("<IHHIIHH", 16, 3, 1, 44118, 44118 * 4, 4, 32) +
                   b"data" + struct.pack("<I", len(raw)) + raw)
    for mode in ("peaks", "tones"):
        cmd = [str(cli), mode, "--in", str(wav), "--start", "1", "--length",
               "18446744073709551615"]
        if mode == "tones":
            cmd += ["--freq", "1000"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if struct.calcsize("P") == 4:
            assert result.returncode == 2
        else:
            assert result.returncode == 0, result.stderr
            expected = 1024 if mode == "peaks" else 2047
            assert json.loads(result.stdout)["length"] == expected


def test_normal_benchmark_still_completes(cli):
    result = subprocess.run([str(cli), "bench", "--outputs", "1024"],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)
