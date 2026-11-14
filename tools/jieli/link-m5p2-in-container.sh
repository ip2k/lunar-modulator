#!/usr/bin/env bash
# MIT. Build the RAM-only, SDK-free m5-plan-2 images in the existing bounded
# lunar-jieli-check container (reached through link-diagnostic.sh with
# profile m5-plan-2). The portable objects are compiled once and linked into
# all four images; only firmware/m5p2/main.c differs, by its build switches:
#   m5p2.bin             FM-1 default ("<id>"):    no switch
#   m5p2-mailbox.bin     FM-1, mailbox ("<id>m"):  LUNAR_M5P2_MAILBOX=1
#   m5p2-kit.bin         dev kit ("<id>k"):        LUNAR_M5P2_KIT=1
#   m5p2-kit-mailbox.bin dev kit, mailbox ("<id>km")
# Builds and audits only; never runs anything.
set -euo pipefail
TC=${TC:-/opt/jieli}
SRC=${SRC:-/src}
OUT=${OUT:-/out}
BUILD_ID=${BUILD_ID:-unknown}
# The panel label adds 9 characters to the id (" 1C 0F424") within 19, and
# the longest suffix is "km": the base is held to 1-10 characters.
if [[ ! $BUILD_ID =~ ^[A-Za-z0-9.:-]{1,10}$ ]]; then
    echo "invalid build id (m5-plan-2 base: 1-10 of [A-Za-z0-9.:-])" >&2
    exit 2
fi
mkdir -p "$OUT"
CC="$TC/common/bin/clang"
FLAGS=(-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin
       -fno-common -fno-unwind-tables -ffunction-sections -fdata-sections
       -mllvm -pi32v2-large-program=true -Wall -Wextra -Werror -DLUNAR_PI32V2)
F=$SRC/firmware
SHARED=(m5p2/startup.S m5p2/m5p2.c ramtest/ramtest.c board/board_io.c board/matrix.c
        display/spi1_transport.c display/panel_probe.c display/m5_pattern.c
        third_party/fm1-nes/fm1_keys.c)
OBJECTS=()
for source in "${SHARED[@]}"; do
    object="$OUT/shared.$(echo "$source" | tr / _).o"
    "$CC" "${FLAGS[@]}" -c "$F/$source" -o "$object"
    OBJECTS+=("$object")
done

build() { # stem id kit mailbox
    local stem=$1 id=$2 kit=$3 mailbox=$4
    "$CC" "${FLAGS[@]}" "-DLUNAR_BUILD_ID=\"$id\"" "-DLUNAR_M5P2_KIT=$kit" \
        "-DLUNAR_M5P2_MAILBOX=$mailbox" -c "$F/m5p2/main.c" -o "$OUT/$stem.main.o"
    "$TC/pi32v2/bin/ld" -T "$F/m5p2/app.ld" --gc-sections -Map="$OUT/$stem.map" \
        -o "$OUT/$stem.elf" "${OBJECTS[@]}" "$OUT/$stem.main.o"
    "$TC/pi32v2/bin/objcopy" -O binary -j .image "$OUT/$stem.elf" "$OUT/$stem.bin"
    "$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$OUT/$stem.elf" > "$OUT/$stem.disasm.txt"
    "$TC/pi32v2/bin/objdump" -t "$OUT/$stem.elf" > "$OUT/$stem.symbols.txt"
    python3 "$SRC/tools/jieli/audit_link.py" --runtime sdk-free \
        --elf "$OUT/$stem.elf" --app "$OUT/$stem.bin" \
        --sources "$F/m5p2" --sources "$F/ramtest" --sources "$F/board" \
        --sources "$F/display" --sources "$F/third_party/fm1-nes" \
        --json "$OUT/$stem.audit_link.json"
    python3 "$SRC/tools/jieli/diagnostic_report.py" "$OUT/$stem.elf" "$OUT/$stem.bin" \
        "$OUT/$stem.audit_link.json" ram > "$OUT/$stem.report.json"
}
build m5p2 "$BUILD_ID" 0 0
build m5p2-mailbox "${BUILD_ID}m" 0 1
build m5p2-kit "${BUILD_ID}k" 1 0
build m5p2-kit-mailbox "${BUILD_ID}km" 1 1
sha256sum "$OUT"/m5p2*.elf "$OUT"/m5p2*.bin "$OUT"/shared.*.o > "$OUT/sha256.txt"
"$TC/common/bin/clang" --version | head -1 > "$OUT/toolchain.txt"
