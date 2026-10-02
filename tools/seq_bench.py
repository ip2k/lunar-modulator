#!/usr/bin/env python3
"""Worst-case scripts for the sequencer core's cycle budget (engines/seq.md, stage B).

    python3 tools/seq_bench.py --out DIR            # writes DIR/burst.verbs, DIR/edit.verbs
    python3 tools/seq_bench.py --out DIR --run      # and times them with engines/build/fm1-seq

burst.verbs: 8 tracks, every step of a 16-step clip a 12-note chord (1,536
notes, the 8-track note pool), 8 locked lanes per track on every step, 300
BPM, clip speed `--scale` (default 255/1: Movy's core takes it, the FM-1's
D8 clamps it to 4X). Every master tick fires chords on every track.

edit.verbs: tracks 1-7 fill the note pool to 192 short of full, then track
0 gets `addp` over 256 steps (D7 refuses it whole), `asetr` over 256 steps
and Double Loop, each in one block while playing.

Both run at 44,118 Hz in 64-frame blocks, the FM-1's. Stage B times
fm1_seq_advance on the dev board with them; on the desktop, --run prints
fm1-seq's own timing (`advance_ns_per_block`, `advance_ns_max`). Our code,
MIT.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEQ = ROOT / "engines" / "build" / "fm1-seq"
RATE, BLOCK, TRACKS = 44118, 64, 8


def chord(step: int) -> str:
    base = 40 + 12 * (step % 4)
    return " ".join(f"{base + k} 100" for k in range(12))


def burst(scale: str, seconds: int = 10) -> str:
    lines = [f"#! rate={RATE} block={BLOCK} tracks={TRACKS}", "@0 bpm 30000"]
    for t in range(TRACKS):
        lines += [f"@0 tog {t} {s} {chord(s)}" for s in range(16)]
        lines.append(f"@0 cscl {t} {scale}")
        for lane in range(8):
            lines.append(f"@0 alabel {t} {lane} synth:p{lane}")
            lines += [f"@0 aset {t} {lane} {s} {(13 * lane + 7 * s) % 128} 1" for s in range(16)]
    lines += ["@0 play", f"@{seconds * RATE} stop"]
    return "\n".join(lines) + "\n"


def edit() -> str:
    lines = [f"#! rate={RATE} block={BLOCK} tracks={TRACKS}"]
    for t in range(1, TRACKS):
        lines += [f"@0 tog {t} {s} {chord(0)}" for s in range(16)]
    lines += ["@64 play", "@6400 addp 0 0 255 61 100", "@12800 asetr 0 0 0 255 64",
              "@19200 dbl 0", "@25600 stop"]
    return "\n".join(lines) + "\n"


def run(path: pathlib.Path, compat: bool) -> dict:
    state = path.with_suffix(".state.json")
    cmd = [str(SEQ), "--cmd", str(path), "--state", str(state)] + (["--compat"] if compat else [])
    subprocess.run(cmd, check=True)
    doc = json.loads(state.read_text())
    state.unlink()
    st = doc["end"]["stats"]
    return {"advance_ns_per_block": doc["advance_ns_per_block"],
            "advance_ns_max": doc["advance_ns_max"], "blocks": doc["blocks"],
            "dropped_events": st["dropped_events"], "gates_evicted": st["gates_evicted"],
            "refused": st["refused"]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--scale", default="255 1", help="clip speed for burst.verbs, 'num den'")
    ap.add_argument("--run", action="store_true", help="time them with engines/build/fm1-seq")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "burst.verbs").write_text(burst(args.scale))
    (args.out / "edit.verbs").write_text(edit())
    if args.run:
        for name in ("burst", "edit"):
            for compat in (False, True):
                r = run(args.out / f"{name}.verbs", compat)
                print(json.dumps({"script": name, "mode": "compat" if compat else "fm1", **r}))


if __name__ == "__main__":
    main()
