"""Writes tests/fixtures/squash-oracle.json from the oracle's renders
(run-on-aeon.sh): every 61st frame of each case, both channels, with the
upstream commit, the container image and each render's RMS. Standard library
only. MIT licence, like the rest of this repository."""
import json
import math
import struct
import sys
from pathlib import Path

DECIMATE = 61
COMMIT = "e718c9bcfcdd736deeddb08bffe6bce2aa8e0eea"


def main(src, dst):
    src = Path(src)
    cases = [line.split() for line in (src / "cases.txt").read_text().splitlines() if line]
    out = {"upstream": f"airwindows/airwindows@{COMMIT}",
           "image": (src / "image.txt").read_text().strip(),
           "rate": 44100, "decimate": DECIMATE, "cases": {}}
    for c in cases:
        name = c[0]
        raw = (src / f"{name}.oracle.f32").read_bytes()
        x = struct.unpack(f"<{len(raw) // 4}f", raw)
        frames = len(x) // 2
        rms = math.sqrt(sum(v * v for v in x) / len(x))
        dec = []
        for i in range(0, frames, DECIMATE):
            dec += [float(f"{x[2 * i]:.9g}"), float(f"{x[2 * i + 1]:.9g}")]
        out["cases"][name] = {"kind": c[1], "signal": int(c[2]),
                              "knobs": [float(v) for v in c[3:]], "rms": rms, "frames": dec}
    Path(dst).write_text(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])
