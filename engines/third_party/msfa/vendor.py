#!/usr/bin/env python3
"""Copy the msfa files the FM6 engine uses into this folder, or check them.

Usage:
    python3 engines/third_party/msfa/vendor.py MSFA_CHECKOUT          # copy
    python3 engines/third_party/msfa/vendor.py MSFA_CHECKOUT --check  # compare

MSFA_CHECKOUT is a clone of https://github.com/google/music-synthesizer-for-android
(any commit; the files are read from the commit pinned in UPSTREAM.md with
`git show`, so the working tree's own state does not matter). The files land
here flat, as they sit upstream in app/src/main/jni/, so their quoted
#includes resolve as upstream. Nothing is rewritten: our build replaces
synth.h through engines/src/msfa.h instead (see UPSTREAM.md). --check
compares every vendored file with the pinned commit, byte for byte, and
exits non-zero on any difference. MIT licence, like the rest of this
repository.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMIT = "f67d41d313b7dc85f6fb99e79e515cc9d208cfff"
UPSTREAM_DIR = "app/src/main/jni"

# The translation units engines/src/msfa_core.cc compiles, and every header
# they include. synth.h is vendored for the record but not used (UPSTREAM.md).
FILES = [
    "aligned_buf.h", "controllers.h", "synth.h",
    "dx7note.cc", "dx7note.h",
    "env.cc", "env.h",
    "exp2.cc", "exp2.h",
    "fm_core.cc", "fm_core.h",
    "fm_op_kernel.cc", "fm_op_kernel.h",
    "freqlut.cc", "freqlut.h",
    "lfo.cc", "lfo.h",
    "patch.cc", "patch.h",
    "pitchenv.cc", "pitchenv.h",
    "sin.cc", "sin.h",
]
LICENSES = {"COPYING": "LICENSE"}       # upstream path -> name here


def upstream(checkout: Path, path: str) -> bytes:
    return subprocess.run(["git", "-C", str(checkout), "show", f"{COMMIT}:{path}"],
                          check=True, capture_output=True).stdout


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--check"]
    if len(args) != 1:
        print(__doc__)
        return 2
    checkout, check = Path(args[0]), "--check" in sys.argv[1:]
    pairs = [(f"{UPSTREAM_DIR}/{f}", f) for f in FILES] + list(LICENSES.items())
    bad = 0
    for src, dst in pairs:
        data = upstream(checkout, src)
        here = HERE / dst
        if check:
            if not here.exists() or here.read_bytes() != data:
                print(f"differs from {COMMIT[:7]}: {dst}", file=sys.stderr)
                bad += 1
        else:
            here.write_bytes(data)
    if check:
        print(f"{len(pairs) - bad} of {len(pairs)} files identical to {COMMIT[:7]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
