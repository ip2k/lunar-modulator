"""Recreate the capacity-test fixture and SAVE binary for compression research.

This extracts only the test fixture builders, avoiding a pytest dependency. It
uses the same source generator and simulator options as the capacity test.
"""
import ast
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path("/tmp/lunar-compression-dense")
SOURCE = ROOT / "tests/test_native_project_capacity.py"
DX7 = ROOT / "sim/web/test/dx7/lunar-test-voices.syx"
BUILD = ROOT / "sim/web/build/compression-research"

source = ast.parse(SOURCE.read_text(encoding="utf-8"))
names = {"_dense_set", "_dense_mod", "_start_args"}
module = ast.Module(body=[node for node in source.body
                          if isinstance(node, ast.FunctionDef) and node.name in names],
                    type_ignores=[])
OUT.mkdir(parents=True, exist_ok=True)
seq, mod = OUT / "dense.movy1", OUT / "dense.mod"
namespace = {
    "Path": Path, "SEQ_TRACKS": 8, "NOTES_PER_TRACK": 192,
    "LOCKS_PER_TRACK": 192, "TRIGS_PER_TRACK": 32, "MOD_SLOTS": 32,
    "MOD_MODULES": 8, "DX7": str(DX7),
}
exec(compile(module, str(SOURCE), "exec"), namespace)
namespace["_dense_set"](seq)
namespace["_dense_mod"](mod)
payload_path = OUT / "dense.native-save.lunarb"
args = namespace["_start_args"](seq, mod) + ["--save", f"project:{payload_path}"]
subprocess.run([
    "make", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
    str(ROOT / "sim/web/mk/sim.mk"), f"SIM={ROOT / 'sim/web'}",
    f"BUILD={BUILD}", "FM1_GPL_MODS=1",
    "EXTRA=-DFM1_STATE_BIN_COMPACT_WRITER -DFM1_TFT_INDEXED=1",
    "OPT=-O2", str(BUILD / "fm1-sim-render"),
], check=True)
subprocess.run([str(BUILD / "fm1-sim-render"), "--seconds", "0", *args], check=True,
               stdout=subprocess.DEVNULL)
payload = OUT / "dense.native-save.lunarb"
print(json.dumps({"payload": str(payload), "bytes": payload.stat().st_size,
                  "sha256": __import__("hashlib").sha256(payload.read_bytes()).hexdigest()}))
