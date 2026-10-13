"""Single-core audio queue: FIFO, saturation, wraparound and silent underruns."""
import shutil
import subprocess

import pytest

from tests.engine_helpers import ROOT


@pytest.fixture(scope="session")
def native_audio_queue(tmp_path_factory):
    compiler = shutil.which("cc")
    if not compiler:
        pytest.skip("no host C compiler")
    binary = tmp_path_factory.mktemp("native-audio-queue") / "check"
    subprocess.run([
        compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
        "-I" + str(ROOT / "firmware/native"),
        str(ROOT / "tests/native_audio_queue_check.c"), "-o", str(binary),
    ], check=True)
    return binary


@pytest.mark.parametrize("shard", range(16))
def test_native_audio_queue(native_audio_queue, shard):
    subprocess.run([str(native_audio_queue), str(shard)], check=True)
