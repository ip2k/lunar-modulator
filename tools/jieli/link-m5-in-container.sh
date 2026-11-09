#!/usr/bin/env bash
# MIT. Build the RAM-only, SDK-free M5 test-pattern image in the existing
# bounded lunar-jieli-check container (reached through link-diagnostic.sh
# with profile m5-test-pattern). Builds and audits only; never runs anything.
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
F=$SRC/firmware
LINKED=(m5/startup.S m5/main.c board/board_io.c board/matrix.c display/spi1_transport.c
        display/panel_probe.c display/m5_pattern.c timing/timer4.c
        third_party/fm1-nes/fm1_keys.c)
# Board modules M5 does not call: compiled for the target as object evidence.
COMPILE_ONLY=(board/adc.c board/midi_parser.c board/midi_uart.c)
OBJECTS=()
for source in "${LINKED[@]}" "${COMPILE_ONLY[@]}"; do
    object="$OUT/$(echo "$source" | tr / _).o"
    extra=()
    if [[ $source == m5/main.c ]]; then extra=("-DLUNAR_BUILD_ID=\"$BUILD_ID\""); fi
    "$CC" "${FLAGS[@]}" "${extra[@]}" -c "$F/$source" -o "$object"
    for linked in "${LINKED[@]}"; do
        if [[ $linked == "$source" ]]; then OBJECTS+=("$object"); fi
    done
done
"$TC/pi32v2/bin/ld" -T "$F/m5/app.ld" --gc-sections -Map="$OUT/m5.map" \
    -o "$OUT/m5.elf" "${OBJECTS[@]}"
"$TC/pi32v2/bin/objcopy" -O binary -j .image "$OUT/m5.elf" "$OUT/m5.bin"
"$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$OUT/m5.elf" > "$OUT/m5.disasm.txt"
"$TC/pi32v2/bin/objdump" -t "$OUT/m5.elf" > "$OUT/m5.symbols.txt"
python3 "$SRC/tools/jieli/audit_link.py" --runtime sdk-free \
    --elf "$OUT/m5.elf" --app "$OUT/m5.bin" \
    --sources "$F/m5" --sources "$F/board" --sources "$F/display" \
    --sources "$F/timing" --sources "$F/third_party/fm1-nes" \
    --json "$OUT/audit_link.json"
python3 "$SRC/tools/jieli/diagnostic_report.py" "$OUT/m5.elf" "$OUT/m5.bin" \
    "$OUT/audit_link.json" ram > "$OUT/report.json"
# Undefined symbols of every object, so compile-only modules show what they need.
python3 - "$OUT" > "$OUT/objects.json" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "/src/tools/jieli")
from audit_link import Elf
out = Path(sys.argv[1])
print(json.dumps({p.name: sorted(Elf(p.read_bytes()).undefined_symbols())
                  for p in sorted(out.glob("*.o"))}, indent=2))
PY
sha256sum "$OUT"/m5.elf "$OUT"/m5.bin "$OUT"/*.o > "$OUT/sha256.txt"
"$TC/common/bin/clang" --version | head -1 > "$OUT/toolchain.txt"
