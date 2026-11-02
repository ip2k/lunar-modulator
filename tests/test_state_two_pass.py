"""Bounded plain writer: actual host encoder, frozen baseline and staged faults.

Optional FM1_CODEC_BASELINE_SOURCE is state_bin.c from the pinned parent. The
ordinary CI path uses the current host writer plus frozen old report digest;
review receipts also compile the exact old source with renamed public exports.
Products are lane-local under pytest tmp_path and removed by TemporaryDirectory.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("sanitize", [False, True], ids=["normal", "asan-ubsan"])
def test_two_pass_binary_codec(tmp_path, sanitize):
    compiler = shutil.which(os.environ.get("FM1_CODEC_CC", "clang"))
    if not compiler:
        pytest.skip("C compiler unavailable")
    flags = ["-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
             f"-I{ROOT / 'engines/include'}", f"-I{ROOT / 'engines/state'}"]
    if sanitize:
        flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    sources = [ROOT / "tests/fixtures/native_state/codec.c"]
    sources += [ROOT / "engines/state" / name for name in (
        "state_bin.c", "state_movy1.c", "state_names.c", "fm1_num.c", "fm1_deflate.c",
        "state_json_read.c", "fm1_json.c", "state_print.c")]
    with tempfile.TemporaryDirectory(prefix="codec-", dir=tmp_path) as temporary:
        stage = Path(temporary)
        baseline = os.environ.get("FM1_CODEC_BASELINE_SOURCE")
        if baseline:
            obj = stage / "baseline.o"
            renames = ["-Dfm1_state_bin_writer_size=baseline_writer_size",
                       "-Dfm1_state_bin_writer=baseline_writer",
                       "-Dfm1_state_bin_write=baseline_write",
                       "-Dfm1_state_bin_read=baseline_read"]
            subprocess.run([compiler, *flags, *renames, "-c", baseline, "-o", str(obj)], check=True)
            sources.append(obj)
            flags += ["-DFM1_CODEC_BASELINE"]
        exe = stage / "codec"
        subprocess.run([compiler, *flags, *map(str, sources), "-o", str(exe)], check=True)
        gold = sorted((ROOT / "tests/fixtures/state/1.0").glob("*.lunarb"))
        result = subprocess.run([str(exe), *map(str, gold)], check=True, capture_output=True,
                                text=True, timeout=90)
        assert "cases=387 reports=2a4db010" in result.stdout
        print(result.stdout.strip())
