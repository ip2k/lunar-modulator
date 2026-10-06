#!/usr/bin/env python3
"""Copy Felucca's WHEEL, TRIO and PHASE engines (GPL-3.0-only) into this
folder, or check them.

Usage:
    python3 engines/third_party/felucca/vendor.py FELUCCA_CHECKOUT          # copy
    python3 engines/third_party/felucca/vendor.py FELUCCA_CHECKOUT --check  # compare

FELUCCA_CHECKOUT is a clone of https://github.com/hugelton/Felucca (any
commit; the files are read from the commit pinned below with `git show`).
Nothing is rewritten: every file is upstream's, byte for byte. The one file
made here, gen/felucca_tables.h, is the output of upstream's own
tools/gen_tables.py at that commit (copied to tools/), run with this
machine's python3; `--check` runs it again and compares. Felucca's build
makes the same file the same way (its build.py and tests/run_tests.sh).
UPSTREAM.md has the hashes. MIT licence (this script), like the rest of
this repository; the files it copies are GPL-3.0-only.
"""
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMIT = "b0dcd53a251d5f5392fea9478b48244d322eeb2a"
FILES = {
    "LICENSE": "LICENSE",                              # the GPL version 3, as the FSF publishes it
    "LICENSING.md": "LICENSING.md",                    # Felucca's own account of its licences
    "firmware/src/core.h": "src/core.h",               # types: tracks, voices, engines, parameters
    "firmware/src/dsp.c": "src/dsp.c",                 # the shared fixed-point DSP blocks
    "firmware/src/eng_wheel.c": "src/eng_wheel.c",     # WHEEL: our Drawbar
    "firmware/src/eng_trio.c": "src/eng_trio.c",       # TRIO: our Trio
    "firmware/src/eng_phase.c": "src/eng_phase.c",     # PHASE: our Phase Bend
    "firmware/src/voice.c": "src/voice.c",             # the test oracle's voices only (engines/test)
    "tools/gen_tables.py": "tools/gen_tables.py",      # makes gen/felucca_tables.h
}
GENERATED = "gen/felucca_tables.h"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tables(gen_tables: Path) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "felucca_tables.h"
        subprocess.run([sys.executable, str(gen_tables), str(out)], check=True,
                       stdout=subprocess.DEVNULL)
        return out.read_bytes()


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--check"]
    if len(args) != 1:
        print(__doc__)
        return 2
    checkout, check = Path(args[0]), "--check" in sys.argv[1:]
    bad = 0
    for src, dst in FILES.items():
        data = subprocess.run(["git", "-C", str(checkout), "show", f"{COMMIT}:{src}"],
                              check=True, capture_output=True).stdout
        here = HERE / dst
        if check:
            if not here.exists() or here.read_bytes() != data:
                print(f"differs from {COMMIT[:7]}: {dst}", file=sys.stderr)
                bad += 1
            continue
        if src.endswith((".c", ".h", ".py")) and b"SPDX-License-Identifier: GPL-3.0-only" not in data[:300]:
            print(f"{src} is not GPL-3.0-only at {COMMIT[:7]}: not copied", file=sys.stderr)
            return 1
        here.parent.mkdir(parents=True, exist_ok=True)
        here.write_bytes(data)
    made = tables(HERE / FILES["tools/gen_tables.py"])
    gen = HERE / GENERATED
    if check:
        if not gen.exists() or gen.read_bytes() != made:
            print(f"differs from tools/gen_tables.py's output: {GENERATED}", file=sys.stderr)
            bad += 1
        n = len(FILES) + 1
        print(f"{n - bad} of {n} files identical to {COMMIT[:7]} and its gen_tables.py")
    else:
        gen.parent.mkdir(parents=True, exist_ok=True)
        gen.write_bytes(made)
        for f in list(FILES.values()) + [GENERATED]:
            print(f"{sha256((HERE / f).read_bytes())}  {f}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
