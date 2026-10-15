"""Compare compact route dispatch with the retained full-track oracle."""
import shutil
import subprocess

import pytest

from tests.seq_helpers import ENGINES


def _host_test(tmp_path, oracle):
    build = tmp_path / ("oracle" if oracle else "compact")
    args = ["make", "-C", str(ENGINES), f"BUILD={build}"]
    if oracle:
        args.append("EXTRA=-DFM1_SEQ_HOST_FULL_TRACK_SNAPSHOT_ORACLE=1")
    args.append(str(build / "fm1-seq-host-test"))
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
    return subprocess.run([str(build / "fm1-seq-host-test")], check=True,
                          capture_output=True).stdout


def test_compact_route_dispatch_matches_full_track_snapshot(tmp_path):
    if not shutil.which("make") or not (shutil.which("cc") or shutil.which("gcc")):
        pytest.skip("no make / C compiler")
    compact = _host_test(tmp_path, False)
    oracle = _host_test(tmp_path, True)
    assert compact == oracle
