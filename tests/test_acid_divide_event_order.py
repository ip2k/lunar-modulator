"""Focused public-API regressions for MIDI STOP/origin and Divide chronology.

Only the changed C units and their generator/RNG dependencies are compiled;
all binaries and generated headers live in pytest's per-run scratch directory.
"""
import shutil
import subprocess
from pathlib import Path

import pytest
from tests.engine_helpers import GPL_MODS, gpl_only

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def event_tools(tmp_path_factory):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    build = tmp_path_factory.mktemp("event-order")
    (build / "fm1_gpl_mods.h").write_text("#define FM1_GPL_MODS 1\n")
    inc = ["-I", str(ROOT / "engines/include"), "-I", str(ROOT / "engines/mod"),
           "-I", str(build), "-I", str(ROOT / "engines/third_party/fm1-x0x")]
    sources = {
        "acid": ["tests/fixtures/acid_gen_transport.c", "engines/midi_fx/acid_gen.c",
                 "engines/third_party/fm1-x0x/seq/tb3po.c"],
        "divide": ["tests/fixtures/divide_event_order.c", "engines/mod/kinds/mod_divide.c",
                   "engines/mod/mp_rng.c"],
    }
    tools = {}
    for name, files in sources.items():
        if name == "acid" and not GPL_MODS:
            continue
        exe = build / name
        subprocess.run([cc, "-std=c99", "-O1", "-g", "-ffp-contract=off",
                        "-fsanitize=address,undefined", *inc,
                        *(str(ROOT / f) for f in files), "-o", str(exe)], check=True)
        tools[name] = exe
    return tools


@gpl_only
@pytest.mark.parametrize("case", ["seq-latch", "live-latch", "run", "same-key", "deferred", "zero-velocity"])
def test_acid_transport_origin(event_tools, case):
    subprocess.run([str(event_tools["acid"]), case], check=True)


@pytest.mark.parametrize("case", ["clock-before-reset", "delayed-before-reset", "future-reset",
                                  "mult-clock", "same-frame-reset"])
def test_divide_chronology(event_tools, case):
    subprocess.run([str(event_tools["divide"]), case], check=True)
