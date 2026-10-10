"""Scope pixels stay edge-connected before CSS scaling, including steep
steps and wrapped sample buffers. Compile the actual private app renderer,
discarding unrelated engine paths, rather than a duplicate line algorithm.
"""
import shutil
import subprocess
import sys

import pytest

from tests.engine_helpers import ROOT

SIM = ROOT / "sim/web"


@pytest.fixture(scope="module")
def scope_probe(tmp_path_factory):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    build = tmp_path_factory.mktemp("scope-probe")
    # draw_scope has no dependency on FM6; avoid linking an engine bank.
    (build / "fm1_modules.h").write_text("#define FM1_WITH_DX7 0\n")
    target = build / "scope-check"
    linker = "-Wl,-dead_strip" if sys.platform == "darwin" else "-Wl,--gc-sections"
    subprocess.run([
        cc, "-std=c99", "-O2", "-ffunction-sections", "-fdata-sections", linker,
        f"-I{build}", f"-I{SIM / 'src'}", f"-I{ROOT / 'engines/include'}",
        f"-I{ROOT / 'engines/state'}", f"-I{ROOT / 'engines/host'}",
        str(SIM / "test/fm1_scope_check.c"), str(SIM / "src/fm1_tft.c"),
        "-lm", "-o", str(target),
    ], check=True, capture_output=True)
    return target


def render(probe, kind, top, pos):
    out = subprocess.check_output([str(probe), str(kind), str(top), str(pos)])
    header, data = out.split(b"\n255\n", 1)
    assert header == b"P6\n240 240"
    assert len(data) == 240 * 240 * 3
    return [data[i:i + 3] for i in range(0, len(data), 3)]


def component_count(points):
    todo = set(points)
    count = 0
    while todo:
        count += 1
        pending = [todo.pop()]
        while pending:
            x, y = pending.pop()
            for p in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if p in todo:
                    todo.remove(p)
                    pending.append(p)
    return count


@pytest.mark.parametrize("kind", range(5), ids=["silent", "sine", "steps", "alternating", "quiet"])
@pytest.mark.parametrize("top", [122, 164, 190])
@pytest.mark.parametrize("pos", [0, 511])
def test_native_trace_is_connected_and_confined(scope_probe, kind, top, pos):
    px = render(scope_probe, kind, top, pos)
    # Get the live token from a scope column: each is a background/live pair.
    colors = {px[y * 240 + 6] for y in range(top, 212)}
    background = px[top * 240 + 6]
    # The trace never touches the top row (one-pixel amplitude margin).
    assert len(colors) == 2
    live = (colors - {background}).pop()
    points = {(x, y) for y in range(240) for x in range(240) if px[y * 240 + x] == live}
    assert component_count(points) == 1
    assert {x for x, y in points} == set(range(6, 234))
    assert all(top <= y < 212 for x, y in points)
    sentinel = px[0]
    assert all(px[y * 240 + x] == sentinel
               for y in range(240) for x in range(240)
               if x < 6 or x >= 234 or y < top or y >= 212)
    assert render(scope_probe, kind, top, 0) == render(scope_probe, kind, top, 511)


def test_shrinking_discards_native_connectors(scope_probe):
    px = render(scope_probe, 1, 164, 0)
    # Native nearest-neighbour artwork at the screenshot's approximate 190px
    # preview width loses source rows/columns, even without interpolation.
    background = px[164 * 240 + 6]
    colors = {px[y * 240 + 6] for y in range(164, 212)}
    live = (colors - {background}).pop()
    points = {(x, y) for y in range(190) for x in range(190)
              if px[int((y + 0.5) * 240 / 190) * 240 + int((x + 0.5) * 240 / 190)] == live}
    assert component_count(points) > 1
