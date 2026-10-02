#!/usr/bin/env python3
"""Print the hashes of what sim/web/www/fm1.wasm and its record are built from.

    python3 sim/web/tools/source_hash.py [REPO_ROOT]

Two SHA-256 hashes, each over the files' paths relative to the repository and
their bytes, in sorted path order:

  engines  engines/, less build output, dotfiles and Markdown: every engine,
           effect and the host the module links
  sim      sim/web's own inputs: src/, mk/ (the link flags and export list),
           build.sh, and the parity test, its scenarios and their sequencer
           scripts (test/seq/), whose results the record carries; and the
           sequencer core and host bridge the module links (engines/seq/,
           include/fm1_seq*.h), so that an engines-only change to them
           cannot ship a module that behaves differently with only a warning

build-on-aeon.sh records both in www/fm1.wasm.json; tests/test_sim_web.py
warns when the tree has moved on since, and fails in CI when the sim's own
inputs have. MIT licence.
"""
import hashlib
import json
import sys
from pathlib import Path

SIM_INPUTS = ("sim/web/src", "sim/web/mk", "sim/web/build.sh", "sim/web/test/parity.mjs",
              "sim/web/test/scenarios.json", "sim/web/test/fm1_sim_render.c",
              "sim/web/test/seq", "sim/web/www/fm1-wasm.mjs",
              "engines/seq", "engines/include/fm1_seq*.h")


def _files(root, base):
    if "*" in base.name:
        return sorted(p for p in base.parent.glob(base.name) if p.is_file())
    if base.is_file():
        return [base]
    return [p for p in base.rglob("*") if p.is_file()]


def engine_files(root):
    engines = root / "engines"
    out = []
    for p in _files(root, engines):
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts) or p.suffix == ".md":
            continue
        if p.relative_to(engines).parts[0].startswith("build"):
            continue
        out.append(p)
    return out


def sim_files(root):
    out = []
    for name in SIM_INPUTS:
        for p in _files(root, root / name):
            if not any(part.startswith(".") or part == "__pycache__"
                       for part in p.relative_to(root).parts):
                out.append(p)
    return out


def _digest(root, files):
    h = hashlib.sha256()
    for p in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        h.update(p.relative_to(root).as_posix().encode() + b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()


def source_hashes(root):
    root = Path(root)
    return {"engines": _digest(root, engine_files(root)), "sim": _digest(root, sim_files(root))}


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
    print(json.dumps(source_hashes(root.resolve()), sort_keys=True))
