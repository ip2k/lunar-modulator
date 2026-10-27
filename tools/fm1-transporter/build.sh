#!/usr/bin/env bash
# Builds FM-1-transporter for a Raspberry Pi Pico 2 W (and Pico 2) with this
# directory's RP2350 patch applied, in an ubuntu:24.04 container. Needs
# Docker and git; any Linux host or a Mac with Docker works.
#
#   tools/fm1-transporter/build.sh [OUT_DIR]
#
# Writes OUT_DIR/fm1_transporter-pico2_w.uf2 and -pico2.uf2 (default:
# scratch/fm1-transporter) and prints their SHA-256.
set -euo pipefail

UPSTREAM=https://github.com/kurogedelic/FM-1-transporter
COMMIT=a7fb5e8ac692c528f8ed29e325911a3f4b8111d6
SDK_TAG=2.2.0

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
OUT=$(mkdir -p "${1:-$ROOT/scratch/fm1-transporter}" && cd "${1:-$ROOT/scratch/fm1-transporter}" && pwd)
WORK="$OUT/work"

if [ ! -d "$WORK/src/.git" ]; then
  git clone -q "$UPSTREAM" "$WORK/src"
fi
git -C "$WORK/src" fetch -q origin
git -C "$WORK/src" checkout -q --detach "$COMMIT"
git -C "$WORK/src" reset -q --hard "$COMMIT"
git -C "$WORK/src" submodule update -q --init lib/Pico-PIO-USB
git -C "$WORK/src" apply "$HERE/0001-pico2-reject-false-d-pullups.patch"

docker run --rm -v "$WORK:/w" -w /w ubuntu:24.04 bash -c "
set -e
trap 'chown -R $(id -u):$(id -g) /w' EXIT
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null
apt-get install -y -qq git cmake gcc-arm-none-eabi libnewlib-arm-none-eabi \
  libstdc++-arm-none-eabi-newlib build-essential python3 >/dev/null
test -d pico-sdk || (git clone -q -b $SDK_TAG --depth 1 https://github.com/raspberrypi/pico-sdk \
  && git -C pico-sdk submodule update --init -q --depth 1 lib/tinyusb)
for B in pico2_w pico2; do
  cmake -S src -B build-\$B -DPICO_SDK_PATH=/w/pico-sdk -DPICO_BOARD=\$B >/w/cfg-\$B.log 2>&1 \
    || { tail -40 /w/cfg-\$B.log; exit 1; }
  make -C build-\$B -j\$(nproc) fm1_transporter >/w/make-\$B.log 2>&1 \
    || { tail -40 /w/make-\$B.log; exit 1; }
done
"

for B in pico2_w pico2; do
  cp "$WORK/build-$B/fm1_transporter.uf2" "$OUT/fm1_transporter-$B.uf2"
done
(cd "$OUT" && shasum -a 256 fm1_transporter-pico2_w.uf2 fm1_transporter-pico2.uf2 2>/dev/null \
  || sha256sum fm1_transporter-pico2_w.uf2 fm1_transporter-pico2.uf2)
