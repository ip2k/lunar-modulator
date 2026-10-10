#!/usr/bin/env bash
# MIT. Run in the existing bounded lunar-jieli-check container. No SDK needed.
set -euo pipefail
TC=${TC:-/opt/jieli}
SRC=${SRC:-/src}
OUT=${OUT:-/out}
PROFILE=${PROFILE:-inert}
REPORT_PROFILE=$PROFILE
case "$PROFILE" in
    inert) FOLDER=diagnostic; SOURCES=(startup.S memory.c runtime.c) ;;
    handover) FOLDER=handover; SOURCES=(startup.S capture.c runtime.c) ;;
    panel-protocol) FOLDER=handover; REPORT_PROFILE=handover; SOURCES=(startup.S capture.c runtime.c) ;;
    *) echo "unknown diagnostic profile" >&2; exit 2 ;;
esac
mkdir -p "$OUT"
CC="$TC/common/bin/clang"
FLAGS=(-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin
       -fno-common -fno-unwind-tables -ffunction-sections -fdata-sections
       -mllvm -pi32v2-large-program=true -Wall -Wextra -Werror)
if [[ $PROFILE == panel-protocol ]]; then FLAGS+=(-DLUNAR_PANEL_PROTOCOL_LINK); fi
for source in "${SOURCES[@]}"; do
    "$CC" "${FLAGS[@]}" -I"$SRC/firmware/diagnostic" -c \
        "$SRC/firmware/$FOLDER/$source" -o "$OUT/$source.o"
done
OBJECTS=("$OUT/startup.S.o" "$OUT/memory.c.o" "$OUT/runtime.c.o")
if [[ $FOLDER == handover ]]; then
    "$CC" "${FLAGS[@]}" -I"$SRC/firmware/diagnostic" -c \
        "$SRC/firmware/diagnostic/memory.c" -o "$OUT/memory.c.o"
    OBJECTS=("$OUT/startup.S.o" "$OUT/runtime.c.o" "$OUT/capture.c.o" "$OUT/memory.c.o")
fi
AUDIT_SOURCES=(--sources "$SRC/firmware/diagnostic" --sources "$SRC/firmware/$FOLDER")
if [[ $PROFILE == panel-protocol ]]; then
    for source in panel_probe.c protocol_capture.c; do
        "$CC" "${FLAGS[@]}" -c "$SRC/firmware/display/$source" -o "$OUT/$source.o"
        OBJECTS+=("$OUT/$source.o")
    done
    AUDIT_SOURCES+=(--sources "$SRC/firmware/display")
fi
"$TC/pi32v2/bin/ld" -T "$SRC/firmware/$FOLDER/app.ld" --gc-sections \
    -Map="$OUT/diagnostic.map" -o "$OUT/diagnostic.elf" \
    "${OBJECTS[@]}"
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
    "${AUDIT_SOURCES[@]}" --json "$OUT/audit_link.json"
python3 "$SRC/tools/jieli/diagnostic_report.py" "$OUT/diagnostic.elf" \
    "$OUT/diagnostic.bin" "$OUT/audit_link.json" "$REPORT_PROFILE" > "$OUT/report.json"
