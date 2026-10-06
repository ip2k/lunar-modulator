"""Shared helpers for the engine tests (tests/test_engines*.py): build the
desktop renderer, render through it, read the WAV back, measure pitch and level,
read Six-Op FM's patch-name table.
"""
import json
import math
import os
import re
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"
RENDER = ENGINES / "build" / "fm1-render"
RATE = 44118

# The GPL switch (engines/Makefile, FM1_GPL_MODS; CLAUDE.md, "The GPL
# switch"): on unless the environment says 0. make reads the same variable,
# so every build the tests make follows it; CI runs the suite both ways.
GPL_MODS = os.environ.get("FM1_GPL_MODS", "1") != "0"
# A test of a GPL module: it is not in the build with the switch off.
gpl_only = pytest.mark.skipif(not GPL_MODS, reason="a GPL module: built only with FM1_GPL_MODS=1")


@pytest.fixture(scope="session")
def renderer():
    if not shutil.which("make") or not (shutil.which("c++") or shutil.which("g++")):
        pytest.skip("no make / C++ compiler")
    subprocess.run(["make", "-C", str(ENGINES), "-j4"], check=True,
                   stdout=subprocess.DEVNULL)
    info = json.loads(subprocess.run([str(RENDER), "--build-info"], check=True,
                                     capture_output=True, text=True).stdout)
    assert info["gpl_mods"] == int(GPL_MODS), "fm1-render was built with the other GPL switch"
    return RENDER


def render(renderer, tmp_path, engine=None, params=(), notes=(), seconds=1.5, name="out",
           fx=(), input=None, extra=()):
    wav = tmp_path / f"{name}.wav"
    cmd = [str(renderer), "--seconds", str(seconds), "--out", str(wav)]
    if engine:
        cmd += ["--engine", engine]
    for p in params:
        cmd += ["--param", p]
    for n in notes:
        cmd += ["--note", n]
    if input:
        cmd += ["--input", input]
    for fx_id, fx_params in fx:           # fx: [("id", ["Name=value", ...]), ...]
        cmd += ["--fx", fx_id]
        for p in fx_params:
            cmd += ["--fx-param", p]
    cmd += list(extra)                    # any other flags, e.g. ["--fill", "0xA5"]
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    summary = json.loads(res.stdout)
    with wave.open(str(wav), "rb") as w:
        assert w.getframerate() == RATE and w.getnchannels() == 2
        raw = w.readframes(w.getnframes())
    left = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767.0
            for i in range(0, len(raw), 4)]
    return summary, left, wav


def pitch_hz(samples, start_s, dur_s):
    """Fundamental from rising zero crossings (clean, sine-like input)."""
    a, b = int(start_s * RATE), int((start_s + dur_s) * RATE)
    seg = samples[a:b]
    mean = sum(seg) / len(seg)
    seg = [x - mean for x in seg]
    crossings = []
    for i in range(1, len(seg)):
        if seg[i - 1] < 0.0 <= seg[i]:
            frac = -seg[i - 1] / (seg[i] - seg[i - 1])
            crossings.append(i - 1 + frac)
    assert len(crossings) > 10, "no periodic signal"
    return (len(crossings) - 1) * RATE / (crossings[-1] - crossings[0])


def cents(f, ref):
    return 1200.0 * math.log2(f / ref)


def rms(samples, start_s, end_s):
    seg = samples[int(start_s * RATE):int(end_s * RATE)]
    return math.sqrt(sum(x * x for x in seg) / max(1, len(seg)))




def sixop_patch_names():
    """The Patch table of engines/src/mi_sixop.cc as (stored, shown) pairs:
    the name stored in the patch data and the one the default build lists.
    They differ where the table has RENAMED("<stored>", "<shown>")."""
    src = (ENGINES / "src" / "mi_sixop.cc").read_text()
    table = src[src.index("kPatchNames[kNumPatches] = {"):]
    table = table[:table.index("};")]
    string = r'"((?:[^"\\]|\\.)*)"'
    pairs = []
    for m in re.finditer(r"RENAMED\(\s*%s\s*,\s*%s\s*\)|%s" % (string, string, string), table):
        stored, shown, plain = m.groups()
        pairs.append((stored, shown) if plain is None else (plain, plain))
    return pairs
