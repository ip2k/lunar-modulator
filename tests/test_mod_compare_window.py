"""Compare's Window emits every interpolated crossing within one tick."""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def compare_probe():
    cc = shutil.which("clang") or shutil.which("cc")
    if not cc:
        pytest.skip("C compiler unavailable")
    scratch = ROOT / "scratch/compare-window-crossing"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="probe-", dir=scratch) as directory:
        exe = Path(directory) / "compare-window"
        subprocess.run([
            cc, "-std=c99", "-O2", "-ffp-contract=off", "-Wall", "-Wextra",
            "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
            f"-I{ROOT / 'engines/include'}", f"-I{ROOT / 'engines/mod'}",
            str(ROOT / "engines/mod/kinds/mod_compare.c"),
            str(ROOT / "engines/test/mod_compare_window_test.c"), "-o", str(exe),
        ], check=True, capture_output=True, text=True)
        yield exe


def probe(exe, start, end, hyst=0, width=0.25, mode=1, next_tick=False):
    output = subprocess.check_output(
        [str(exe), *map(str, (start, end, hyst, width, mode)),
         *(["next"] if next_tick else [])], text=True)
    ports = []
    for line in output.splitlines():
        port, initial, final, *events = line.split()
        assert int(port) == len(ports)
        ports.append((int(initial), int(final),
                      [tuple(map(int, event.split(":"))) for event in events]))
    return ports


@pytest.mark.parametrize("start,end", [(-0.5, 0.5), (0.5, -0.5)])
@pytest.mark.parametrize("hyst,entry,exit", [(0, 8, 24), (0.25, 12, 28)])
def test_full_window_traversal(compare_probe, start, end, hyst, entry, exit):
    p = probe(compare_probe, start, end, hyst)
    assert p[0] == (0, 0, [(entry, 1), (exit, 0)])
    assert p[1] == (1, 1, [(entry, 0), (exit, 1)])
    assert p[2] == (0, 1, [(entry, 1)])
    assert p[3] == (0, 1, [(exit, 1)])
    # Zone ports retain their own existing hysteretic traversal semantics.
    leaving, entering = (6, 4) if start < 0 else (4, 6)
    assert p[leaving] == (1, 0, [(entry, 0)])
    assert p[entering] == (0, 1, [(exit, 1)])
    assert p[5] == (0, 0, [(entry, 1), (exit, 0)])


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("hyst,end,entry", [(0, 0.125, 12), (0.25, 0.0625, 21)])
def test_opposite_sign_entry(compare_probe, sign, hyst, end, entry):
    p = probe(compare_probe, sign * 0.5, -sign * end, hyst)
    assert p[0] == (0, 1, [(entry, 1)])
    assert p[1] == (1, 0, [(entry, 0)])
    assert p[2] == (0, 1, [(entry, 1)])
    assert p[3] == (0, 0, [])


@pytest.mark.parametrize("sign", [-1, 1])
def test_equal_boundary_holds_but_crossing_interior_enters(compare_probe, sign):
    assert probe(compare_probe, sign * 0.5, sign * 0.25)[0] == (0, 0, [])
    assert probe(compare_probe, sign * 0.5, -sign * 0.25)[0] == (0, 1, [(10, 1)])
    assert probe(compare_probe, 0, sign * 0.25)[0] == (1, 1, [])
    assert probe(compare_probe, 0, sign * 0.5)[0] == (1, 0, [(16, 0)])


@pytest.mark.parametrize("width,hyst", [(0, 0), (0.125, 0.25), (0.125, 0.5)])
def test_closed_entry_band_never_opens(compare_probe, width, hyst):
    p = probe(compare_probe, -0.5, 0.5, hyst, width)
    assert p[0] == (0, 0, []) and p[1] == (1, 1, [])
    assert p[2] == (0, 0, []) and p[3] == (0, 0, [])


@pytest.mark.parametrize("start,end", [(-0.5, 0.5), (0.5, -0.5)])
def test_crossing_triggers_fall_at_same_offset_next_tick(compare_probe, start, end):
    p = probe(compare_probe, start, end, next_tick=True)
    assert p[0] == (0, 0, []) and p[1] == (1, 1, [])
    assert p[2] == (1, 0, [(8, 0)])
    assert p[3] == (1, 0, [(24, 0)])
