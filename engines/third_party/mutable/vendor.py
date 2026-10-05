#!/usr/bin/env python3
"""Copy the subset of Mutable Instruments' code the engines use into this folder.

Usage:
    python3 engines/third_party/mutable/vendor.py EURORACK_CHECKOUT STMLIB_CHECKOUT

The two checkouts must be at the commits pinned in UPSTREAM.md (eurorack pins
stmlib as a submodule; use that commit). The script starts from the source
files listed in ROOTS, follows every quoted #include through both trees, and
copies the closure here with the upstream paths kept, so `-I` pointing at this
folder resolves "plaits/...", "braids/..." and "stmlib/..." as upstream does.
It rewrites nothing; local changes, if any, belong in our wrappers.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Translation units we compile, plus headers we include directly.
ROOTS = [
    "plaits/resources.cc",
    "plaits/dsp/voice.h",                 # ChannelPostProcessor + every engine header
    "braids/macro_oscillator.cc",
    "braids/analog_oscillator.cc",
    "braids/digital_oscillator.cc",
    "braids/resources.cc",
    "stmlib/dsp/units.cc",
    "stmlib/dsp/atan.cc",
    "stmlib/utils/random.cc",
    # Audio effects (engines/src/mi_fx.cc). Rings' reverb is header-only and
    # brings rings/dsp/fx/fx_engine.h; nothing else from Rings is needed. The
    # two Plaits effects are already inside plaits/dsp; they are listed so the
    # effects keep them if TREES is ever narrowed.
    "rings/dsp/fx/reverb.h",
    "plaits/dsp/fx/ensemble.h",
    "plaits/dsp/fx/diffuser.h",
    # Modulation kinds (docs/16 MG2). Bounce, Burst and Quantize are C ports
    # in engines/mod/mod_mi.c; these originals are the oracle that
    # fm1-mod-mi-ref compares the ports with (desktop test tool only), and
    # gen_mi_tables.py takes Peaks' delay and gravity tables and Braids'
    # scales from them.
    "peaks/modulations/bouncing_ball.h",
    "peaks/pulse_processor/pulse_shaper.cc",
    "peaks/pulse_processor/pulse_randomizer.cc",
    "peaks/resources.cc",
    "braids/quantizer.cc",
    "braids/quantizer_scales.h",
]
# Whole directories copied as-is (all Plaits engines, light and heavy).
TREES = ["plaits/dsp"]
LICENSES = {"stmlib/LICENSE": "stmlib/LICENSE"}

INCLUDE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.M)


def source(rel: str, eurorack: Path, stmlib: Path) -> Path:
    if rel.startswith("stmlib/"):
        return stmlib / rel[len("stmlib/"):]
    return eurorack / rel


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    eurorack, stmlib = Path(sys.argv[1]), Path(sys.argv[2])
    todo = list(ROOTS)
    for tree in TREES:
        todo += [str(p.relative_to(eurorack)) for p in (eurorack / tree).rglob("*")
                 if p.suffix in (".h", ".cc")]
    seen = set()
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        src = source(rel, eurorack, stmlib)
        if not src.exists():
            print(f"missing: {rel}", file=sys.stderr)
            return 1
        seen.add(rel)
        for inc in INCLUDE.findall(src.read_text(errors="replace")):
            if source(inc, eurorack, stmlib).exists():
                todo.append(inc)
    for rel in sorted(seen):
        dst = HERE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source(rel, eurorack, stmlib), dst)
    for src_rel, dst_rel in LICENSES.items():
        shutil.copy2(source(src_rel, eurorack, stmlib), HERE / dst_rel)
    print(f"copied {len(seen)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
