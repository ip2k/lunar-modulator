#!/usr/bin/env bash
# Reproducible, bounded WASM32 execution of the production allocation path.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
IMAGE=emscripten/emsdk:6.0.10
EXPECTED_ID=sha256:e077d54e2b8970575ebc4f185ac1de0b95c05f2b266134d4ba27449af7aebf65
ACTUAL_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE")
[ "$ACTUAL_ID" = "$EXPECTED_ID" ] || {
  echo "unexpected $IMAGE image id: $ACTUAL_ID (expected $EXPECTED_ID)" >&2
  exit 2
}
mkdir -p "$ROOT/build/allocator-vectors-wasm"
OUT="$ROOT/build/allocator-vectors-wasm/allocator-vectors.js"
docker run --rm --network none --cpus=1 --memory=1g --memory-swap=2g \
  --cgroup-parent=docker-batch.slice \
  --label project=lunar-modulator --label task=allocator-vectors-wasm \
  -u "$(id -u):$(id -g)" \
  -v "$ROOT:/src:ro" -v "$ROOT/build/allocator-vectors-wasm:/out" \
  -w /src "$IMAGE" \
  emcc -O0 -sASSERTIONS=1 -sEXIT_RUNTIME=1 \
    -Ifirmware/native -Ifirmware/third_party/tlsf \
    tests/native_allocator_vectors_wasm.c \
    firmware/native/instance_pool.c firmware/third_party/tlsf/tlsf.c \
    -o /out/allocator-vectors.js
docker run --rm --network none --cpus=1 --memory=1g --memory-swap=2g \
  --cgroup-parent=docker-batch.slice \
  --label project=lunar-modulator --label task=allocator-vectors-wasm \
  -v "$ROOT/build/allocator-vectors-wasm:/out:ro" -w /out "$IMAGE" \
  node /out/allocator-vectors.js
