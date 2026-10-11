#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Offline object check only. Run in the bounded, network-disabled Hera container
# with the pinned 20250324.1 toolchain mounted read-only at /opt/jieli.
set -euo pipefail
TC=${TC:-/opt/jieli}
SRC=${SRC:-/source}
OUT=${OUT:-/out}
mkdir -p "$OUT"
FLAGS=(-target pi32v2 -mcpu=r3 -mfprev1 -Oz -std=c99 -ffreestanding
       -fno-builtin -fno-common -fno-unwind-tables -ffunction-sections
       -fdata-sections -mllvm -pi32v2-large-program=true
       -Wall -Wextra -Werror -DLUNAR_PI32V2)
"$TC/common/bin/clang" --version > "$OUT/compiler.txt"
OBJECTS=()
for component in bringup/bringup display/panel_probe display/spi1_transport timing/timer4 recovery/request; do
    name=${component##*/}
    "$TC/common/bin/clang" "${FLAGS[@]}" -c "$SRC/firmware/$component.c" -o "$OUT/$name.o"
    "$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$OUT/$name.o" > "$OUT/$name.disasm.txt"
    "$TC/pi32v2/bin/objdump" -t "$OUT/$name.o" > "$OUT/$name.symbols.txt"
    OBJECTS+=("$OUT/$name.o")
done
# A relocatable object, never a boot ELF/image or package. All component
# dependencies must resolve without a runtime library or generated memcpy.
"$TC/pi32v2/bin/ld" -r -o "$OUT/bringup-components.o" "${OBJECTS[@]}"
"$TC/pi32v2/bin/objdump" -t "$OUT/bringup-components.o" > "$OUT/bringup-components.symbols.txt"
python3 - "$OUT" <<'PY'
from pathlib import Path
import sys
out = Path(sys.argv[1])
def undefined(path):
    result = set()
    for line in path.read_text().splitlines():
        if '*UND*' in line:
            parts = line.split('*UND*', 1)[1].split()
            if len(parts) > 1:
                result.add(parts[-1])
    return result
for path in sorted(out.glob('*.symbols.txt')):
    expected = {'lunar_panel_probe', 'lunar_recovery_request'} if path.name == 'bringup.symbols.txt' else set()
    actual = undefined(path)
    if actual != expected:
        raise SystemExit(f'{path.name}: unresolved {sorted(actual)}, expected {sorted(expected)}')
print('All five target C objects compile with Werror; orchestration dependencies resolve; no external runtime dependency.')
print('Relocatable object only. No target execution or native activation.')
PY
