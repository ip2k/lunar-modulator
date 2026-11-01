#!/usr/bin/env bash
# Offline recipe for the separately named fixed return-r01 Pico 2 W variant.
# No network, pull, default recovery artifact, Pico flash, or device access.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
UPSTREAM_COMMIT=a7fb5e8ac692c528f8ed29e325911a3f4b8111d6

if [[ $# != 1 || ! -d ${FM1T_RETURN_UPSTREAM:-} || ! -d ${FM1T_RETURN_SDK:-} ||
      ! -d ${FM1T_RETURN_TINYUSB:-} ||
      ! ${FM1T_RETURN_IMAGE:-} =~ ^[^[:space:]]+@sha256:[0-9a-f]{64}$ ||
      ! ${FM1T_RETURN_SDK_SHA:-} =~ ^[0-9a-f]{40}$ ||
      ! ${FM1T_RETURN_TINYUSB_SHA:-} =~ ^[0-9a-f]{40}$ ||
      ! ${FM1T_RETURN_CPUSET:-} =~ ^[0-9]+(-[0-9]+)?$ ||
      ${FM1T_RETURN_UPSTREAM:-} != /* || ${FM1T_RETURN_SDK:-} != /* ||
      ${FM1T_RETURN_TINYUSB:-} != /* || ${1:-} != /* ]]; then
  echo 'required: new OUT_DIR and pinned local upstream/SDK/TinyUSB/image/CPU-set inputs' >&2
  exit 64
fi
OUT=$1
if [[ -e $OUT || -L $OUT ]]; then echo 'output path already exists' >&2; exit 64; fi
if [[ $OUT == /Volumes/* ]]; then
  volume=${OUT#\/Volumes/}; volume=${volume%%/*}
  if ! mount | grep -Fq "on /Volumes/$volume ("; then
    echo 'requested output volume is not mounted' >&2; exit 64
  fi
fi
[[ $(git -C "$FM1T_RETURN_UPSTREAM" rev-parse "$UPSTREAM_COMMIT^{commit}") == "$UPSTREAM_COMMIT" ]]
[[ $(git -C "$FM1T_RETURN_SDK" rev-parse HEAD) == "$FM1T_RETURN_SDK_SHA" ]]
[[ $(git -C "$FM1T_RETURN_TINYUSB" rev-parse HEAD) == "$FM1T_RETURN_TINYUSB_SHA" ]]
[[ $(git -C "$FM1T_RETURN_UPSTREAM" ls-tree "$UPSTREAM_COMMIT" lib/Pico-PIO-USB | awk '{print $3}') == \
   $(git -C "$FM1T_RETURN_UPSTREAM/lib/Pico-PIO-USB" rev-parse HEAD) ]]
[[ $(git -C "$FM1T_RETURN_SDK" ls-tree HEAD lib/tinyusb | awk '{print $3}') == "$FM1T_RETURN_TINYUSB_SHA" ]]
# The upstream archive ignores its worktree; the three mounted/copied source
# trees do not. Refuse local edits and untracked overlays in those inputs.
[[ -z $(git -C "$FM1T_RETURN_UPSTREAM/lib/Pico-PIO-USB" status --porcelain --untracked-files=all) ]]
[[ -z $(git -C "$FM1T_RETURN_SDK" status --porcelain --untracked-files=all) ]]
[[ -z $(git -C "$FM1T_RETURN_TINYUSB" status --porcelain --untracked-files=all) ]]

mkdir "$OUT"                         # exclusive new destination
OUT=$(cd "$OUT" && pwd)
STAGE="$OUT/stage"
mkdir "$STAGE" "$STAGE/src" "$STAGE/build"
cleanup() { rm -rf -- "$STAGE"; }
trap cleanup EXIT

git -C "$FM1T_RETURN_UPSTREAM" archive "$UPSTREAM_COMMIT" | tar -xf - -C "$STAGE/src"
mkdir -p "$STAGE/src/lib/Pico-PIO-USB"
cp -R "$FM1T_RETURN_UPSTREAM/lib/Pico-PIO-USB/src" "$STAGE/src/lib/Pico-PIO-USB/"
git -C "$STAGE/src" init -q
for patch in "$HERE"/0001-pico2-reject-false-d-pullups.patch \
             "$HERE"/0002-exact-bot-completion.patch \
             "$HERE"/0003-fixed-return-r01-rom-mode.patch; do
  git -C "$STAGE/src" apply --check "$patch"
  git -C "$STAGE/src" apply "$patch"
done

EPOCH=$(git -C "$FM1T_RETURN_UPSTREAM" show -s --format=%ct "$UPSTREAM_COMMIT")
docker image inspect "$FM1T_RETURN_IMAGE" --format '{{.Id}}' > "$OUT/image-id.txt"
sha256sum "$HERE"/000{1,2,3}-*.patch > "$OUT/patch-sha256.txt" 2>/dev/null || \
  shasum -a 256 "$HERE"/000{1,2,3}-*.patch > "$OUT/patch-sha256.txt"
cp "$HERE/return-r01-build-manifest.json" "$OUT/manifest.json"
printf '%s\n' "$UPSTREAM_COMMIT" "$FM1T_RETURN_SDK_SHA" "$FM1T_RETURN_TINYUSB_SHA" \
  "$FM1T_RETURN_IMAGE" "$FM1T_RETURN_CPUSET" > "$OUT/input-pins.txt"

docker run --rm --pull=never --network=none --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges --cgroup-parent=docker-batch.slice \
  --cpus=4 --cpuset-cpus="$FM1T_RETURN_CPUSET" --memory=6g --memory-swap=6g \
  --label project=lunar --label session="return-r01-$(basename "$OUT")" \
  --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  -e SOURCE_DATE_EPOCH="$EPOCH" \
  -v "$STAGE/src:/src:ro" -v "$FM1T_RETURN_SDK:/sdk:ro" \
  -v "$FM1T_RETURN_TINYUSB:/sdk/lib/tinyusb:ro" -v "$STAGE/build:/build:rw" \
  "$FM1T_RETURN_IMAGE" sh -ec '
    cmake -S /src -B /build -DPICO_SDK_PATH=/sdk -DPICO_BOARD=pico2_w \
      -DFM1T_BUILD_RETURN_R01=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCMAKE_EXE_LINKER_FLAGS=-Wl,-Map=/build/return-r01.map
    cmake --build /build -j4 --target fm1_transporter_return_r01
    arm-none-eabi-nm --numeric-sort /build/fm1_transporter_return_r01.elf > /build/return-r01.nm
    arm-none-eabi-objdump -dr /build/fm1_transporter_return_r01.elf > /build/return-r01.disasm
    arm-none-eabi-readelf -W -h -S /build/fm1_transporter_return_r01.elf > /build/return-r01.sections
    arm-none-eabi-size -A /build/fm1_transporter_return_r01.elf > /build/return-r01.size
    cmake --version | head -n1
    arm-none-eabi-gcc --version | head -n1
  ' > "$OUT/build.log" 2>&1

cp "$STAGE/build/fm1_transporter_return_r01.uf2" "$OUT/return-r01-pico2_w.uf2"
cp "$STAGE/build/fm1_transporter_return_r01.elf" "$OUT/return-r01.elf"
for name in return-r01.map return-r01.nm return-r01.disasm return-r01.sections \
            return-r01.size compile_commands.json CMakeCache.txt; do
  cp "$STAGE/build/$name" "$OUT/$name"
done
(cd "$OUT" && sha256sum return-r01-pico2_w.uf2 return-r01.elf return-r01.map \
  return-r01.nm return-r01.disasm return-r01.sections return-r01.size \
  compile_commands.json CMakeCache.txt > artifact-sha256.txt 2>/dev/null) || \
  (cd "$OUT" && shasum -a 256 return-r01-pico2_w.uf2 return-r01.elf return-r01.map \
    return-r01.nm return-r01.disasm return-r01.sections return-r01.size \
    compile_commands.json CMakeCache.txt > artifact-sha256.txt)
echo "offline fixed return-r01 UF2: $OUT/return-r01-pico2_w.uf2"
