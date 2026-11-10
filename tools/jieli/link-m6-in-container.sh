#!/usr/bin/env bash
# MIT. Build the RAM-only, SDK-free M6 images in the existing bounded
# lunar-jieli-check container (reached through link-diagnostic.sh with
# profile m6): m6.bin for the FM-1 (panel and ALNK0) and m6-devkit.bin for
# the AC79 dev kit (UART report, ALNK0 pin writes masked). Builds and audits
# only; never runs anything.
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
COMMON=(m6/m6_core.c board/alnk0_audio.c board/alnk0_audio_mmio.c timing/timer4.c)
FM1=(m6/startup.S m6/main_fm1.c m6/m6_screen.c ramtest/ramtest.c board/board_io.c board/matrix.c
     display/spi1_transport.c display/panel_probe.c "${COMMON[@]}")
KIT=(m6/startup.S m6/main_devkit.c ramtest/ramtest.c "${COMMON[@]}")

build() { # name entry sources...
    local name=$1 entry=$2
    shift 2
    local objects=() source object extra
    for source in "$@"; do
        # flat in $OUT: the container's root-owned subdirectories could not
        # be removed by the host user afterwards
        object="$OUT/$name.$(echo "$source" | tr / _).o"
        extra=()
        case $source in
            m6/main_*.c) extra=("-DLUNAR_BUILD_ID=\"$BUILD_ID\"") ;;
            m6/startup.S) extra=("-DM6_ENTRY=$entry") ;;
        esac
        "$CC" "${FLAGS[@]}" "${extra[@]}" -c "$F/$source" -o "$object"
        objects+=("$object")
    done
    "$TC/pi32v2/bin/ld" -T "$F/m6/app.ld" --gc-sections -Map="$OUT/$name.map" \
        -o "$OUT/$name.elf" "${objects[@]}"
    "$TC/pi32v2/bin/objcopy" -O binary -j .image "$OUT/$name.elf" "$OUT/$name.bin"
    "$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$OUT/$name.elf" > "$OUT/$name.disasm.txt"
    "$TC/pi32v2/bin/objdump" -t "$OUT/$name.elf" > "$OUT/$name.symbols.txt"
    python3 "$SRC/tools/jieli/audit_link.py" --runtime sdk-free \
        --elf "$OUT/$name.elf" --app "$OUT/$name.bin" \
        --sources "$F/m6" --sources "$F/board" --sources "$F/display" \
        --sources "$F/timing" --sources "$F/ramtest" \
        --json "$OUT/$name.audit_link.json"
    python3 "$SRC/tools/jieli/diagnostic_report.py" "$OUT/$name.elf" "$OUT/$name.bin" \
        "$OUT/$name.audit_link.json" ram-window > "$OUT/$name.report.json"
}
build m6 lunar_m6_main "${FM1[@]}"
build m6-devkit lunar_m6_kit_main "${KIT[@]}"
sha256sum "$OUT"/m6.elf "$OUT"/m6.bin "$OUT"/m6-devkit.elf "$OUT"/m6-devkit.bin > "$OUT/sha256.txt"
"$TC/common/bin/clang" --version | head -1 > "$OUT/toolchain.txt"
