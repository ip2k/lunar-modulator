#!/usr/bin/env bash
# MIT. Build the RAM-only, SDK-free M4 dev-kit RAM test image in the existing
# bounded lunar-jieli-check container (reached through link-diagnostic.sh
# with profile ramtest). Builds and audits only; never runs anything.
set -euo pipefail
TC=${TC:-/opt/jieli}
SRC=${SRC:-/src}
OUT=${OUT:-/out}
BUILD_ID=${BUILD_ID:-unknown}
if [[ ! $BUILD_ID =~ ^[A-Za-z0-9\ .:-]{1,19}$ ]]; then
    echo "invalid build id" >&2
    exit 2
fi
mkdir -p "$OUT"
CC="$TC/common/bin/clang"
FLAGS=(-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin
       -fno-common -fno-unwind-tables -ffunction-sections -fdata-sections
       -mllvm -pi32v2-large-program=true -Wall -Wextra -Werror -DLUNAR_PI32V2)
F=$SRC/firmware/ramtest
OBJECTS=()
for source in startup.S main.c ramtest.c; do
    object="$OUT/$source.o"
    extra=()
    if [[ $source == main.c ]]; then extra=("-DLUNAR_BUILD_ID=\"$BUILD_ID\""); fi
    "$CC" "${FLAGS[@]}" "${extra[@]}" -c "$F/$source" -o "$object"
    OBJECTS+=("$object")
done
"$TC/pi32v2/bin/ld" -T "$F/app.ld" --gc-sections -Map="$OUT/ramtest.map" \
    -o "$OUT/ramtest.elf" "${OBJECTS[@]}"
"$TC/pi32v2/bin/objcopy" -O binary -j .image "$OUT/ramtest.elf" "$OUT/ramtest.bin"
"$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$OUT/ramtest.elf" > "$OUT/ramtest.disasm.txt"
"$TC/pi32v2/bin/objdump" -t "$OUT/ramtest.elf" > "$OUT/ramtest.symbols.txt"
python3 "$SRC/tools/jieli/audit_link.py" --runtime sdk-free \
    --elf "$OUT/ramtest.elf" --app "$OUT/ramtest.bin" --sources "$F" \
    --json "$OUT/audit_link.json"
python3 "$SRC/tools/jieli/diagnostic_report.py" "$OUT/ramtest.elf" "$OUT/ramtest.bin" \
    "$OUT/audit_link.json" ram > "$OUT/report.json"
sha256sum "$OUT"/ramtest.elf "$OUT"/ramtest.bin "$OUT"/*.o > "$OUT/sha256.txt"
"$TC/common/bin/clang" --version | head -1 > "$OUT/toolchain.txt"
