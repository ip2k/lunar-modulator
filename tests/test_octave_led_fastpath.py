"""The octave LEDs should avoid time conversion when their state is constant."""

import json
import math
import re
import subprocess
from pathlib import Path

import pytest

from tests.test_sim_web import tools  # noqa: F401


RATE = 44118
OCTAVE_LED_INDEX = 27


def render_octave_led(sim, direction, magnitude, frames):
    args = [str(sim), "--rate", str(RATE), "--seconds", format(frames / RATE, ".17g")]
    button = "OCT+" if direction == "up" else "OCT-"
    for step in range(magnitude):
        start = step * 0.02
        args += ["--button", f"{start:.2f}:{button}:0.005"]
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    summary = json.loads(result.stdout)
    assert summary["frames"] == frames
    assert summary["octave"] == (magnitude if direction == "up" else -magnitude)
    index = OCTAVE_LED_INDEX + (0 if direction == "down" else 1)
    return int(summary["leds"][index])


def expected_led(magnitude, frames):
    if magnitude <= 0:
        return 0
    if magnitude >= 3:
        return 1
    period = 1.0 if magnitude == 1 else 0.25
    return int(math.fmod(frames / RATE, period) < period * 0.5)


@pytest.mark.parametrize("direction", ["down", "up"])
@pytest.mark.parametrize("magnitude,frames", [
    (0, RATE),
    (1, 22058), (1, 22059), (1, 22060),
    (1, 44117), (1, 44118), (1, 44119),
    (2, 5514), (2, 5515), (2, 5516),
    (2, 11029), (2, 11030), (2, 11031),
    (3, RATE),
])
def test_octave_led_matches_period_oracle_at_boundaries(tools, direction, magnitude, frames):
    actual = render_octave_led(tools["sim"], direction, magnitude, frames)
    assert actual == expected_led(magnitude, frames)


def test_constant_octave_led_returns_precede_seconds_conversion():
    source = (Path(__file__).resolve().parents[1] / "sim" / "web" / "src" / "fm1_app.c").read_text()
    body = re.search(r"static int octave_led\([^)]*\)\s*\{(?P<body>.*?)\n\}", source, re.S)
    assert body
    text = body.group("body")
    assert text.index("if (magnitude <= 0) return 0;") < text.index("double t = seconds(a);")
    assert text.index("if (magnitude >= 3) return 1;") < text.index("double t = seconds(a);")
