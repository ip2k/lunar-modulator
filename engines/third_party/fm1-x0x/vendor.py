#!/usr/bin/env python3
"""Copy fm1-x0x's 303 bass, TB-3PO generator and 808 kit into this folder, or check them.

Usage:
    python3 engines/third_party/fm1-x0x/vendor.py X0X_CHECKOUT SCHWUNG303_CHECKOUT          # copy
    python3 engines/third_party/fm1-x0x/vendor.py X0X_CHECKOUT SCHWUNG303_CHECKOUT --check  # compare

X0X_CHECKOUT is a clone of https://github.com/charlesvestal/fm1-x0x and
SCHWUNG303_CHECKOUT one of https://github.com/charlesvestal/schwung-303 (any
commit: the files are read from the commits pinned below with `git show`).
From fm1-x0x come the 303 bass (dsp/bass303.*, with the maths and parameter
headers it includes), TB-3PO (seq/tb3po.*, with the pattern header it
includes), the 808 kit (dsp/drum808.*), the GPL-3.0 text and X0X's
LICENSING.md; from schwung-303 comes
Open303's MIT licence, which X0X's bass carries code of. Nothing else of
either repository is taken.

Four files carry local changes, kept as local.patch (UPSTREAM.md says what and
why): the copy applies it, and --check applies it to the pinned files and
compares the result with what is here, byte for byte, so the patch is always
the whole difference. Needs git and patch. MIT licence, like the rest of this
repository.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
X0X_COMMIT = "80b7d40cc9463653554eaf1eb9c24d47162785b7"
S303_COMMIT = "ccc2f1fed90c9c222644b58789b404126b5c7e15"
X0X_FILES = {
    "LICENSE": "LICENSE",                                  # GPL-3.0, X0X's
    "LICENSING.md": "LICENSING.md",                        # X0X's account of every file's origin
    "firmware/src/dsp/bass303.c": "dsp/bass303.c",         # SPDX: GPL-3.0-only (local.patch)
    "firmware/src/dsp/bass303.h": "dsp/bass303.h",         # SPDX: GPL-3.0-only (local.patch)
    "firmware/src/dsp/fastmath.h": "dsp/fastmath.h",       # SPDX: GPL-3.0-only
    "firmware/src/dsp/x0x_param.h": "dsp/x0x_param.h",     # SPDX: GPL-3.0-only
    "firmware/src/dsp/drum808.c": "dsp/drum808.c",         # SPDX: GPL-3.0-only (local.patch)
    "firmware/src/dsp/drum808.h": "dsp/drum808.h",         # SPDX: GPL-3.0-only (local.patch)
    "firmware/src/seq/tb3po.c": "seq/tb3po.c",             # SPDX: GPL-3.0-only
    "firmware/src/seq/tb3po.h": "seq/tb3po.h",             # SPDX: GPL-3.0-only
    "firmware/src/seq/pattern.h": "seq/pattern.h",         # SPDX: GPL-3.0-only
}
S303_FILES = {
    "src/dsp/open303/LICENSE": "LICENSE-Open303",          # MIT, Robin Schmidt
}
PATCH = HERE / "local.patch"


def show(checkout, commit, path):
    return subprocess.run(["git", "-C", str(checkout), "show", f"{commit}:{path}"],
                          check=True, capture_output=True).stdout


def assemble(x0x, s303, out):
    """The pinned files under out/, as this folder lays them out, patched."""
    for files, checkout, commit in ((X0X_FILES, x0x, X0X_COMMIT), (S303_FILES, s303, S303_COMMIT)):
        for src, dst in files.items():
            path = out / dst
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(show(checkout, commit, src))
    subprocess.run(["patch", "-s", "-p1", "-d", str(out), "-i", str(PATCH)], check=True)


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--check"]
    if len(args) != 2:
        print(__doc__)
        return 2
    x0x, s303 = Path(args[0]), Path(args[1])
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        assemble(x0x, s303, out)
        names = sorted(list(X0X_FILES.values()) + list(S303_FILES.values()))
        if "--check" not in sys.argv[1:]:
            for name in names:
                (HERE / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(out / name, HERE / name)
            print(f"copied {len(names)} files from {X0X_COMMIT[:7]} and {S303_COMMIT[:7]}, "
                  "local.patch applied")
            return 0
        bad = [n for n in names if not (HERE / n).is_file()
               or (HERE / n).read_bytes() != (out / n).read_bytes()]
        for n in bad:
            print(f"differs from the pinned commits plus local.patch: {n}", file=sys.stderr)
        print(f"{len(names) - len(bad)} of {len(names)} files are the pinned commits' plus local.patch")
        return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
