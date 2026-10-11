#!/usr/bin/env bash
# SPDX-License-Identifier: MIT. Offline build only; no upload path.
set -euo pipefail
TC=${TC:-/opt/jieli}
SRC=${SRC:-/src}
OUT=${OUT:-/out}
mkdir -p "$OUT"
CC="$TC/common/bin/clang"
FLAGS=(-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin
    -fno-common -fno-unwind-tables -ffunction-sections -fdata-sections
    -mllvm -pi32v2-large-program=true -Wall -Wextra -Werror -DLUNAR_PI32V2)
"$CC" "${FLAGS[@]}" -c "$SRC/firmware/ram-recovery/startup.S" -o "$OUT/startup.o"
"$CC" "${FLAGS[@]}" -c "$SRC/firmware/ram-recovery/runtime.c" -o "$OUT/runtime.o"
"$CC" "${FLAGS[@]}" -c "$SRC/firmware/recovery/request.c" -o "$OUT/request.o"
"$TC/pi32v2/bin/ld" -T "$SRC/firmware/ram-recovery/probe.ld" --gc-sections \
    -Map="$OUT/probe.map" -o "$OUT/probe.elf" "$OUT/startup.o" "$OUT/runtime.o" "$OUT/request.o"
"$TC/pi32v2/bin/objcopy" -O binary -j .probe "$OUT/probe.elf" "$OUT/probe.bin"
"$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$OUT/probe.elf" > "$OUT/probe.disasm.txt"
"$TC/pi32v2/bin/objdump" -t "$OUT/probe.elf" > "$OUT/probe.symbols.txt"
python3 - "$OUT" <<'PY'
import hashlib, json, pathlib, sys
out = pathlib.Path(sys.argv[1])
undefined = []
for line in (out / 'probe.symbols.txt').read_text().splitlines():
    if '*UND*' in line:
        words = line.split('*UND*', 1)[1].split()
        if len(words) > 1:
            undefined.append(words[-1])
if undefined:
    raise SystemExit('Unresolved symbols: ' + ', '.join(undefined))
blob = (out / 'probe.bin').read_bytes()
if not 0 < len(blob) <= 8192:
    raise SystemExit('Unexpected initialized image size')
receipt = dict(entry='0x01c02000', reserved_ram='0x01c02000..0x01c06000',
    bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(),
    undefined=undefined, device_executed=False, installable_package=False,
    hardware_review_required=True)
(out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
PY
