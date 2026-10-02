#!/usr/bin/env bash
# sim/web/build-on-aeon.sh -- rebuild the virtual FM-1 on aeon in one command:
#
#   sim/web/build-on-aeon.sh [--engines-ref GIT_REF] [--no-screenshot]
#
# Copies engines/ and sim/web/ (no build output) to aeon, builds a static
# musl fm1-render in Alpine (musl is Emscripten's C library, so it separates
# the compiler from libm in the parity test), runs sim/web/build.sh in the
# emscripten/emsdk container (native reference, WebAssembly, parity test),
# then optionally the page in headless Chromium (test/screenshot.mjs in
# the Playwright container), and brings back www/fm1.wasm, www/fm1.wasm.json
# and the screenshots (sim/web/build/screenshots/). Nothing runs on this
# machine but ssh, tar and scp; nothing is installed on aeon's host.
#
# --engines-ref builds against engines/ as committed at GIT_REF instead of the
# working tree, e.g. to try a branch that changes the engines; that module,
# its record, parity.json and the screenshots land in sim/web/build/ref-GIT_REF/,
# and www/ and the working tree's own results in sim/web/build/ stay as they
# were. The record names each container image by digest, since tags move.
#
# Environment: FM1_AEON (ssh target, default claude@192.168.1.25),
# FM1_REMOTE_DIR (default /home/claude/mvave-fm1/virtual), FM1_SESSION (the
# session label on the containers). MIT licence, like the rest of this repository.
set -euo pipefail
# macOS tar would add AppleDouble ._* files (provenance attributes) to the
# staged tree, and a scan of www/ then trips over them.
export COPYFILE_DISABLE=1

HOST=${FM1_AEON:-claude@192.168.1.25}
REMOTE=${FM1_REMOTE_DIR:-/home/claude/mvave-fm1/virtual}
SESSION=${FM1_SESSION:-virtual-fm1}
EMSDK_IMAGE=emscripten/emsdk:6.0.10
ALPINE_IMAGE=alpine:3.22
PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright:v1.63.0-noble
PLAYWRIGHT_NPM=playwright@1.63.0

ENGINES_REF=""
SCREENSHOT=1
while [ $# -gt 0 ]; do
  case "$1" in
    --engines-ref) ENGINES_REF=$2; shift 2 ;;
    --no-screenshot) SCREENSHOT=0; shift ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done

ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
SIM=$ROOT/sim/web
STAGE=$REMOTE/src
LABELS=(--label project=mvave-fm1-firmware --label "session=$SESSION")

echo "== staging sources on $HOST:$STAGE"
ssh "$HOST" "rm -rf '$STAGE' && mkdir -p '$STAGE'"
if [ -n "$ENGINES_REF" ]; then
  git -C "$ROOT" archive "$ENGINES_REF" engines | ssh "$HOST" "tar -x -C '$STAGE'"
else
  tar -C "$ROOT" --no-xattrs --exclude='engines/build*' --exclude='.DS_Store' -cf - engines \
    | ssh "$HOST" "tar -x -C '$STAGE'"
fi
tar -C "$ROOT" --no-xattrs --exclude='sim/web/build' --exclude='.DS_Store' --exclude='__pycache__' -cf - sim/web \
  | ssh "$HOST" "tar -x -C '$STAGE'"

echo "== images (by digest)"
IMAGES=("$ALPINE_IMAGE" "$EMSDK_IMAGE")
if [ "$SCREENSHOT" = 1 ]; then IMAGES+=("$PLAYWRIGHT_IMAGE"); fi
DIGESTS=$(ssh "$HOST" bash -s -- "${IMAGES[@]}" <<'REMOTE'
for i in "$@"; do
  docker image inspect "$i" >/dev/null 2>&1 || docker pull -q "$i" >/dev/null
  d=$(docker image inspect --format '{{index .RepoDigests 0}}' "$i")
  echo "$i@${d#*@}"
done
REMOTE
)
DIGESTS=$(printf '%s' "$DIGESTS" | paste -sd';' -)
echo "$DIGESTS" | tr ';' '\n'

echo "== static musl reference in $ALPINE_IMAGE"
ssh "$HOST" "docker run --rm ${LABELS[*]} -v '$STAGE:/src' -w /src $ALPINE_IMAGE \
  sh -c 'apk add -q build-base >/dev/null && \
         make -C engines BUILD=/src/sim/web/build/musl CC=gcc CXX=g++ EXTRA=-static -j\$(nproc) \
           /src/sim/web/build/musl/fm1-render >/dev/null; s=\$?; chown -R \$(stat -c %u:%g /src) /src; exit \$s'"

echo "== build and parity in $EMSDK_IMAGE"
ssh "$HOST" "docker run --rm ${LABELS[*]} -e ENGINES_REF='${ENGINES_REF:-working tree}' -e FM1_IMAGES='$DIGESTS' \
  -v '$STAGE:/src' -w /src $EMSDK_IMAGE \
  sh -c 'bash sim/web/build.sh; s=\$?; chown -R \$(stat -c %u:%g /src) /src; exit \$s'"

if [ "$SCREENSHOT" = 1 ]; then
  echo "== page in headless Chromium ($PLAYWRIGHT_IMAGE)"
  ssh "$HOST" "mkdir -p '$REMOTE/playwright' && docker run --rm ${LABELS[*]} --ipc=host \
    -v '$REMOTE/playwright:/pw' -v '$STAGE:/src' -w /pw $PLAYWRIGHT_IMAGE \
    sh -c '[ -d node_modules/playwright ] || npm install --no-save --no-audit --no-fund $PLAYWRIGHT_NPM >/dev/null; \
           PLAYWRIGHT_DIR=/pw node /src/sim/web/test/screenshot.mjs /src/sim/web/www /src/sim/web/build/screenshots; \
           s=\$?; chown -R \$(stat -c %u:%g /src) /src /pw; exit \$s'"
fi

echo "== fetching results"
# A build of another ref's engines is a trial: its module and every result go
# to build/ref-<ref>/, so www/fm1.wasm always matches this working tree and
# build/ keeps this tree's parity and screenshots.
if [ -n "$ENGINES_REF" ]; then
  DEST=$SIM/build/ref-$(printf '%s' "$ENGINES_REF" | tr -c 'A-Za-z0-9._-' '_')
  RESULTS=$DEST
else
  DEST=$SIM/www
  RESULTS=$SIM/build
fi
mkdir -p "$DEST" "$RESULTS"
scp -q "$HOST:$STAGE/sim/web/www/fm1.wasm" "$HOST:$STAGE/sim/web/www/fm1.wasm.json" "$DEST/"
rm -f "$RESULTS/parity.json"
scp -q "$HOST:$STAGE/sim/web/build/parity.json" "$RESULTS/"
if [ "$SCREENSHOT" = 1 ]; then              # replaced only by a new set
  rm -rf "$RESULTS/screenshots"
  scp -q -r "$HOST:$STAGE/sim/web/build/screenshots" "$RESULTS/"
fi
python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print(sys.argv[1], r['wasm_bytes'], 'bytes; parity', r['parity'])" \
  "$DEST/fm1.wasm.json"
