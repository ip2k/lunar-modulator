#!/usr/bin/env bash
# MIT. Build the RAM-only, SDK-free K1-K3 dev-kit watchdog probe images in the
# existing bounded lunar-jieli-check container (reached through
# link-diagnostic.sh with profile wdtprobe): one image per mode, each with
# build id "<BUILD_ID>-<mode>". Builds and audits only; never runs anything.
set -euo pipefail
TC=${TC:-/opt/jieli}
SRC=${SRC:-/src}
OUT=${OUT:-/out}
BUILD_ID=${BUILD_ID:-unknown}
# The longest suffix is "-mailbox" (8), so the base is held to 11 characters.
if [[ ! $BUILD_ID =~ ^[A-Za-z0-9.:-]{1,11}$ ]]; then
    echo "invalid build id (wdtprobe base: 1-11 of [A-Za-z0-9.:-])" >&2
    exit 2
fi
mkdir -p "$OUT"
CC="$TC/common/bin/clang"
FLAGS=(-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin
       -fno-common -fno-unwind-tables -ffunction-sections -fdata-sections
       -mllvm -pi32v2-large-program=true -Wall -Wextra -Werror -DLUNAR_PI32V2)
F=$SRC/firmware
SOURCES=(wdtprobe/startup.S wdtprobe/main.c wdtprobe/wdtprobe.c ramtest/ramtest.c
         display/m5_pattern.c display/panel_probe.c)

build() { # mode-number mode-name
    local number=$1 name=$2 objects=() source object extra
    local stem="wdtprobe-$name"
    for source in "${SOURCES[@]}"; do
        object="$OUT/$stem.$(echo "$source" | tr / _).o"
        extra=()
        if [[ $source == wdtprobe/main.c ]]; then
            extra=("-DLUNAR_BUILD_ID=\"$BUILD_ID-$name\"" "-DLUNAR_WDTPROBE_MODE=$number")
        fi
        "$CC" "${FLAGS[@]}" "${extra[@]}" -c "$F/$source" -o "$object"
        objects+=("$object")
    done
    "$TC/pi32v2/bin/ld" -T "$F/wdtprobe/app.ld" --gc-sections -Map="$OUT/$stem.map" \
        -o "$OUT/$stem.elf" "${objects[@]}"
    "$TC/pi32v2/bin/objcopy" -O binary -j .image "$OUT/$stem.elf" "$OUT/$stem.bin"
    "$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$OUT/$stem.elf" > "$OUT/$stem.disasm.txt"
    "$TC/pi32v2/bin/objdump" -t "$OUT/$stem.elf" > "$OUT/$stem.symbols.txt"
    python3 "$SRC/tools/jieli/audit_link.py" --runtime sdk-free \
        --elf "$OUT/$stem.elf" --app "$OUT/$stem.bin" \
        --sources "$F/wdtprobe" --sources "$F/ramtest" --sources "$F/display" \
        --json "$OUT/$stem.audit_link.json"
    python3 "$SRC/tools/jieli/diagnostic_report.py" "$OUT/$stem.elf" "$OUT/$stem.bin" \
        "$OUT/$stem.audit_link.json" ram > "$OUT/$stem.report.json"
}
build 1 read
build 2 kick
build 3 disarm
build 4 mailbox
sha256sum "$OUT"/wdtprobe-*.elf "$OUT"/wdtprobe-*.bin > "$OUT/sha256.txt"
"$TC/common/bin/clang" --version | head -1 > "$OUT/toolchain.txt"
