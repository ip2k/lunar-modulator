#!/usr/bin/env bash
# tools/jieli/compile-check.sh -- compile-only stage B: build the engines, the
# vendored Mutable and Schwung code, the sequencer core and the simulator's
# app layer with JieLi's pi32v2 toolchain, in a container on a Linux build
# host, and bring back the report (notes/2026-10-02-jieli-compile-check.md).
#
#   FM1_JIELI_HOST=user@host tools/jieli/compile-check.sh
#
# Nothing is linked into a firmware, nothing runs on a JieLi chip, and
# nothing touches an FM-1 or a dev board. Nothing is downloaded to this
# machine: the toolchain, the SDK headers and libc++'s math.h are fetched by
# containers on the build host, checked against the pins below, and stay
# there. The toolchain is never committed.
#
# On the build host, under FM1_JIELI_DIR (default ~/mvave-fm1/jieli):
#   dl/          the toolchain archive (SHA-256 pinned)
#   toolchain/   the archive unpacked; mounted read-only at /opt/jieli
#   sdk/         AC79 SDK (Apache-2.0) at the pinned tag, blobless, with only
#                include_lib/c++ (libc++), demo_hello's wl82 Makefile and the
#                seven closed libraries it links checked out (for symbols)
#   cxxshim/     libc++ 7.0.0's math.h, which the SDK's libc++ copy lacks
#   src/         the staged tree: engines/, sim/web/, tools/jieli/
#   out/         results; copied back to engines/build-jieli/ here
#
# Environment: FM1_JIELI_HOST (required: user@host of a Linux x86-64 machine
# with Docker), FM1_JIELI_DIR, FM1_SESSION (container label, default
# jieli-compile), FM1_JIELI_TOOLCHAIN_SHA256 (to accept a different archive
# when JieLi's link moves; the report records which one ran).
# MIT licence, like the rest of this repository.
set -euo pipefail
export COPYFILE_DISABLE=1   # no AppleDouble files in the staged tree

HOST="${FM1_JIELI_HOST:?set FM1_JIELI_HOST=user@host (a Linux x86-64 machine with Docker)}"
SESSION=${FM1_SESSION:-jieli-compile}
LABELS="--label project=lunar-modulator --label session=$SESSION"

# Pins (verified 2026-10-02). JieLi's short link redirects to the newest
# archive; the pin makes a silent change of toolchain fail loudly.
TOOLCHAIN_URL=https://pkgman.jieliapp.com/s/linux-toolchain
TOOLCHAIN_ARCHIVE=jieli-linux-toolchains-20250805.1.tar.xz
TOOLCHAIN_SHA256=${FM1_JIELI_TOOLCHAIN_SHA256:-f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958}
SDK_REPO=https://github.com/amitv87/fw-AC79_AIoT_SDK.git
SDK_TAG=AC79NN_SDK_V1.1.9_2023-08-01
SDK_COMMIT=8eae66452ce4c34d64ad38a2764ba1c0610900e3
LIBCXX_MATH_URL=https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-7.0.0/libcxx/include/math.h
LIBCXX_MATH_SHA256=ccb698bba066ba4b9cef6ccddd5a79ae5c389def391adb10d2de1be77f05b69d
CURL_IMAGE=curlimages/curl:8.16.0
GIT_IMAGE=alpine/git:v2.49.1
BASE_IMAGE=debian:bookworm-slim
IMAGE=lunar-jieli-check:bookworm

ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
REMOTE=${FM1_JIELI_DIR:-$(ssh "$HOST" 'printf %s "$HOME"')/mvave-fm1/jieli}
LOCAL_OUT=$ROOT/engines/build-jieli

echo "== fetching what is missing on $HOST:$REMOTE"
# ssh joins its arguments into one remote command line: quote each for it.
ARGS=$(printf '%q ' "$REMOTE" "$LABELS" "$TOOLCHAIN_URL" "$TOOLCHAIN_ARCHIVE" "$TOOLCHAIN_SHA256" \
  "$SDK_REPO" "$SDK_TAG" "$SDK_COMMIT" "$LIBCXX_MATH_URL" "$LIBCXX_MATH_SHA256" "$CURL_IMAGE" "$GIT_IMAGE")
ssh "$HOST" "bash -s -- $ARGS" <<'REMOTE'
set -euo pipefail
R=$1 LABELS=$2 TC_URL=$3 TC_AR=$4 TC_SHA=$5 SDK_REPO=$6 SDK_TAG=$7 SDK_COMMIT=$8 MATH_URL=$9
MATH_SHA=${10} CURL=${11} GIT=${12}
U="$(id -u):$(id -g)"
mkdir -p "$R/dl" "$R/toolchain" "$R/cxxshim"
if [ ! -f "$R/dl/$TC_AR" ]; then
  docker run --rm $LABELS -u "$U" -v "$R/dl:/dl" -w /dl "$CURL" -sSfL -o "$TC_AR.part" "$TC_URL"
  mv "$R/dl/$TC_AR.part" "$R/dl/$TC_AR"
fi
echo "$TC_SHA  $R/dl/$TC_AR" | sha256sum -c --quiet || {
  echo "toolchain archive differs from the pin; set FM1_JIELI_TOOLCHAIN_SHA256 to accept it" >&2; exit 1; }
if [ ! -x "$R/toolchain/current/common/bin/clang" ]; then
  rm -rf "$R/toolchain" && mkdir -p "$R/toolchain"
  tar -xJf "$R/dl/$TC_AR" -C "$R/toolchain"
  top=$(tar -tJf "$R/dl/$TC_AR" | awk -F/ 'NR == 1 {print $1}')
  ln -sfn "$top" "$R/toolchain/current"
fi
if [ ! -d "$R/sdk/.git" ]; then
  docker run --rm $LABELS -u "$U" -v "$R:/w" -w /w "$GIT" clone -q --depth 1 --branch "$SDK_TAG" \
    --filter=blob:none --no-checkout "$SDK_REPO" sdk
fi
# libc++ (headers and libraries), and the closed libraries demo_hello links,
# read only for their symbol tables.
docker run --rm $LABELS -u "$U" -v "$R/sdk:/sdk" -w /sdk "$GIT" checkout -q HEAD -- include_lib/c++ \
  apps/demo/demo_hello/board/wl82/Makefile \
  cpu/wl82/liba/cpu.a cpu/wl82/liba/event.a cpu/wl82/liba/system.a cpu/wl82/liba/cfg_tool.a \
  cpu/wl82/liba/fs.a cpu/wl82/liba/common_lib.a cpu/wl82/liba/update.a
got=$(docker run --rm $LABELS -u "$U" -v "$R/sdk:/sdk" -w /sdk "$GIT" rev-parse HEAD)
[ "$got" = "$SDK_COMMIT" ] || { echo "SDK at $got, expected $SDK_COMMIT" >&2; exit 1; }
if [ ! -f "$R/cxxshim/math.h" ]; then
  docker run --rm $LABELS -u "$U" -v "$R/cxxshim:/d" -w /d "$CURL" -sSfL -o math.h "$MATH_URL"
fi
echo "$MATH_SHA  $R/cxxshim/math.h" | sha256sum -c --quiet || { echo "libc++ math.h differs from the pin" >&2; exit 1; }
echo "toolchain $(readlink "$R/toolchain/current"), SDK $SDK_TAG ($SDK_COMMIT)"
REMOTE

echo "== image $IMAGE"
ssh "$HOST" "docker build -q $LABELS -t $IMAGE - >/dev/null" <<EOF
FROM $BASE_IMAGE
RUN apt-get update \\
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\
      make python3 gcc g++ gcc-multilib g++-multilib binutils \\
 && rm -rf /var/lib/apt/lists/*
EOF
DIGEST=$(ssh "$HOST" "docker image inspect --format '{{.Id}}' $IMAGE")

echo "== staging sources"
ssh "$HOST" "rm -rf '$REMOTE/src' && mkdir -p '$REMOTE/src'"
tar -C "$ROOT" --no-xattrs --exclude='engines/build*' --exclude='sim/web/build' --exclude='sim/web/www' \
    --exclude='.DS_Store' --exclude='__pycache__' -cf - engines sim/web tools/jieli \
  | ssh "$HOST" "tar -x -C '$REMOTE/src'"

echo "== compiling in $IMAGE"
ssh "$HOST" "rm -rf '$REMOTE/out' && mkdir -p '$REMOTE/out' && docker run --rm $LABELS \
  -u \$(id -u):\$(id -g) \
  -v '$REMOTE/toolchain/current:/opt/jieli:ro' -v '$REMOTE/sdk:/sdk:ro' -v '$REMOTE/cxxshim:/cxxshim:ro' \
  -v '$REMOTE/src:/src' -v '$REMOTE/out:/out' $IMAGE bash /src/tools/jieli/in-container.sh"

echo "== record"
COMMIT=$(git -C "$ROOT" rev-parse HEAD)
DIRTY=$(git -C "$ROOT" status --porcelain -- engines sim/web/src tools/jieli | wc -l | tr -d ' ')
ssh "$HOST" "cat > '$REMOTE/out/record.json'" <<EOF
{"tree": "$COMMIT", "uncommitted_files": $DIRTY,
 "toolchain_archive": "$TOOLCHAIN_ARCHIVE", "toolchain_sha256": "$TOOLCHAIN_SHA256",
 "sdk": "$SDK_TAG", "sdk_commit": "$SDK_COMMIT",
 "libcxx_math_h": "$LIBCXX_MATH_URL", "libcxx_math_h_sha256": "$LIBCXX_MATH_SHA256",
 "image": "$IMAGE", "image_id": "$DIGEST",
 "ran": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF

echo "== fetching results to $LOCAL_OUT"
rm -rf "$LOCAL_OUT" && mkdir -p "$LOCAL_OUT"
# Reports, logs and size tables only; the objects stay on the build host.
ssh "$HOST" "cd '$REMOTE/out' && tar -cf - report.json report.md record.json sizes/*.json \
  \$(find . -name '*.log' -o -name '*.rc' -o -name 'objects.txt' -o -name 'opt.txt' -o -name 'extra.txt' | sed 's|^\./||')" \
  | tar -x -C "$LOCAL_OUT"
echo "report: $LOCAL_OUT/report.md"
