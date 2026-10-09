#!/usr/bin/env bash
# MIT. Run in the existing bounded lunar-jieli-check container. No SDK needed.
set -euo pipefail
TC=${TC:-/opt/jieli}
SRC=${SRC:-/src}
OUT=${OUT:-/out}
mkdir -p "$OUT"
CC="$TC/common/bin/clang"
FLAGS=(-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin
       -fno-common -fno-unwind-tables -ffunction-sections -fdata-sections
       -mllvm -pi32v2-large-program=true -Wall -Wextra -Werror)
for source in startup.S memory.c runtime.c; do
    "$CC" "${FLAGS[@]}" -I"$SRC/firmware/diagnostic" -c \
        "$SRC/firmware/diagnostic/$source" -o "$OUT/$source.o"
done
"$TC/pi32v2/bin/ld" -T "$SRC/firmware/diagnostic/app.ld" --gc-sections \
    -Map="$OUT/diagnostic.map" -o "$OUT/diagnostic.elf" \
    "$OUT/startup.S.o" "$OUT/memory.c.o" "$OUT/runtime.c.o"
# JieLi's objcopy accepts exactly one -j. Export each load section and place
# it at its ELF load address rather than relying on GNU objcopy semantics.
for section in entry text data; do
    "$TC/pi32v2/bin/objcopy" -O binary -j ".$section" \
        "$OUT/diagnostic.elf" "$OUT/$section.bin"
done
python3 "$SRC/tools/jieli/diagnostic_flat.py" "$OUT"
"$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$OUT/diagnostic.elf" \
    > "$OUT/diagnostic.disasm.txt"
python3 "$SRC/tools/jieli/audit_link.py" --runtime sdk-free \
    --elf "$OUT/diagnostic.elf" --app "$OUT/diagnostic.bin" \
    --sources "$SRC/firmware/diagnostic" --json "$OUT/audit_link.json"
python3 "$SRC/tools/jieli/diagnostic_report.py" "$OUT/diagnostic.elf" \
    "$OUT/diagnostic.bin" "$OUT/audit_link.json" > "$OUT/report.json"
