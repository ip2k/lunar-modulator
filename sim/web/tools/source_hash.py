#!/usr/bin/env python3
"""Print the hash of the sources sim/web/www/fm1.wasm is built from.

    python3 sim/web/tools/source_hash.py [REPO_ROOT]

SHA-256 over engines/ (less build output and dotfiles) and sim/web/src, each
file's path relative to the repository and its bytes, in sorted path order.
build-on-aeon.sh records it in www/fm1.wasm.json; tests/test_sim_web.py warns
when the tree has moved on since. MIT licence.
"""
import hashlib
import sys
from pathlib import Path


def source_files(root):
    engines = root / "engines"
    out = []
    for base in (engines, root / "sim" / "web" / "src"):
        for p in base.rglob("*"):
            rel = p.relative_to(root)
            if not p.is_file() or any(part.startswith(".") for part in rel.parts):
                continue
            if base == engines and p.relative_to(engines).parts[0].startswith("build"):
                continue
            out.append(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def source_hash(root):
    h = hashlib.sha256()
    for p in source_files(root):
        h.update(p.relative_to(root).as_posix().encode() + b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
    print(source_hash(root.resolve()))
