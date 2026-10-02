#!/usr/bin/env bash
# sim/web/build.sh -- the virtual FM-1's build, run inside the
# emscripten/emsdk image (build-on-aeon.sh starts it there):
#
#   1. native fm1-render and fm1-sim-render with GCC, and the screen sweep
#      (every page, value extreme and popup through the layout check);
#   2. fm1.wasm (the browser's module) and fm1-render.js (render.cc for
#      Node) with Emscripten;
#   3. test/parity.mjs: the WebAssembly output against fm1-render (GCC with
#      glibc, and with musl when build-on-aeon.sh has built that in
#      build/musl/), scenario by scenario, sequencer scripts (test/seq/)
#      included, and the screens against the native harness;
#   4. www/fm1.wasm and its build record www/fm1.wasm.json, only if all of
#      that passed.
#
# Needs: gcc, make, python3, node and emcc (all in emscripten/emsdk:6.0.10).
# MIT licence, like the rest of this repository.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SIM=$ROOT/sim/web
OUT=$SIM/build
J=$(nproc 2>/dev/null || echo 4)

mk() { make -C "$ROOT/engines" -f Makefile -f "$SIM/mk/sim.mk" SIM="$SIM" "$@"; }

echo "== native reference (GCC)"
mk -j"$J" BUILD="$OUT/native" CC=gcc CXX=g++ "$OUT/native/fm1-render" "$OUT/native/fm1-sim-render" >/dev/null
rm -rf "$OUT/screens" && mkdir -p "$OUT/screens"
"$OUT/native/fm1-sim-render" --screens "$OUT/screens"

echo "== WebAssembly ($(emcc --version | head -1))"
mk -j"$J" BUILD="$OUT/wasm" CC=emcc CXX=em++ "$OUT/wasm/fm1.wasm" "$OUT/wasm/fm1-render.js" >/dev/null
ls -l "$OUT/wasm/fm1.wasm"

echo "== parity"
MUSL=()
if [ -x "$OUT/musl/fm1-render" ]; then MUSL=(--musl "$OUT/musl/fm1-render"); fi
node "$SIM/test/parity.mjs" --native "$OUT/native/fm1-render" --sim "$OUT/native/fm1-sim-render" \
  --wasm "$OUT/wasm/fm1.wasm" --render-js "$OUT/wasm/fm1-render.js" "${MUSL[@]}" \
  --scenarios "$SIM/test/scenarios.json" --work "$OUT/parity" --summary "$OUT/parity.json"

echo "== record"
cp "$OUT/wasm/fm1.wasm" "$SIM/www/fm1.wasm"
EMCC_VERSION=$(emcc --version | head -1) GCC_VERSION=$(gcc --version | head -1) \
ENGINES_REF=${ENGINES_REF:-working tree} FM1_IMAGES=${FM1_IMAGES:-} \
python3 - "$ROOT" "$OUT/parity.json" "$SIM/www" <<'EOF'
import hashlib, json, os, sys, datetime
from pathlib import Path
root, parity_path, www = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(root / "sim" / "web" / "tools"))
from source_hash import source_hashes
parity = json.loads(parity_path.read_text())
wasm = (www / "fm1.wasm").read_bytes()
record = {
    "about": "Written by sim/web/build.sh; tests/test_sim_web.py checks it.",
    "wasm_sha256": hashlib.sha256(wasm).hexdigest(),
    "wasm_bytes": len(wasm),
    "sources_sha256": source_hashes(root),
    "engines": os.environ["ENGINES_REF"],
    "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "emcc": os.environ["EMCC_VERSION"],
    "native_reference": os.environ["GCC_VERSION"],
    # The containers by digest (build-on-aeon.sh passes them; tags move).
    "images": [i for i in os.environ["FM1_IMAGES"].split(";") if i],
    "imports": parity["imports"],
    "parity": {k: v for k, v in parity.items() if k not in ("scenarios", "imports")},
    "scenarios": [
        {"name": s["name"], "samples": s["samples"], "libm_sensitive": s["libm_sensitive"],
         **{k: (None if s[k] is None else {"differing": s[k]["differing"], "max_lsb": s[k]["max"]})
            for k in ("app_vs_js", "app_vs_musl", "app_vs_glibc")},
         "screen_px_differing": s["screen"]["differing"], "ram_bytes": s["ram"],
         **({"cmd": s["cmd"], "seq": s["seq"]} if s.get("cmd") else {})}
        for s in parity["scenarios"]
    ],
}
# A rebuild of the same module from the same sources keeps the old time, so
# the committed record changes only when something it records did.
path = www / "fm1.wasm.json"
try:
    old = json.loads(path.read_text())
except (OSError, ValueError):
    old = {}
if (old.get("wasm_sha256"), old.get("sources_sha256")) == (record["wasm_sha256"],
                                                            record["sources_sha256"]):
    record["built"] = old.get("built", record["built"])
path.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record["parity"]))
EOF
