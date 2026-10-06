#!/usr/bin/env python3
"""Copy Felucca's fm6_core.c (Apache-2.0) into this folder, or check it.

Usage:
    python3 engines/third_party/felucca-fm6/vendor.py FELUCCA_CHECKOUT          # copy
    python3 engines/third_party/felucca-fm6/vendor.py FELUCCA_CHECKOUT --check  # compare

FELUCCA_CHECKOUT is a clone of https://github.com/hugelton/Felucca (any
commit; the files are read from the commit pinned in UPSTREAM.md with
`git show`). Only the two files below are taken: the rest of Felucca is
GPL-3.0-only and is not vendored. Nothing is rewritten. MIT licence, like
the rest of this repository.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMIT = "727f272015da26eb2d0291bd652eba28ff57cb37"
FILES = {
    "firmware/src/fm6_core.c": "fm6_core.c",          # SPDX-License-Identifier: Apache-2.0
    "LICENSES/Apache-2.0-msfa.txt": "LICENSE",        # its notice and the licence text
}


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
        elif src.endswith(".c") and b"SPDX-License-Identifier: Apache-2.0" not in data[:200]:
            print(f"{src} is not Apache-2.0 at {COMMIT[:7]}: not copied", file=sys.stderr)
            return 1
        else:
            here.write_bytes(data)
    if check:
        print(f"{len(FILES) - bad} of {len(FILES)} files identical to {COMMIT[:7]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
