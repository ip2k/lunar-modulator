"""Shared helpers for the engine tests (tests/test_engines*.py): build the
desktop renderer, render through it, read the WAV back, measure pitch and level.
"""
import json
import math
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"
RENDER = ENGINES / "build" / "fm1-render"
RATE = 44118


@pytest.fixture(scope="session")
def renderer():
    if not shutil.which("make") or not (shutil.which("c++") or shutil.which("g++")):
        pytest.skip("no make / C++ compiler")
    subprocess.run(["make", "-C", str(ENGINES), "-j4"], check=True,
                   stdout=subprocess.DEVNULL)
    return RENDER


def render(renderer, tmp_path, engine=None, params=(), notes=(), seconds=1.5, name="out",
           fx=(), input=None):
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


