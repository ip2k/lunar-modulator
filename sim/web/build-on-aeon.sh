#!/usr/bin/env bash
# sim/web/build-on-aeon.sh -- rebuild the virtual FM-1 on aeon in one command:
#
#   FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh [--engines-ref GIT_REF]
#       [--no-screenshot] [--readme-screenshots]
#
# Copies engines/ and sim/web/ (no build output) to aeon, builds a static
# musl fm1-render in Alpine (musl is Emscripten's C library, so it separates
# the compiler from libm in the parity test), runs sim/web/build.sh in the
# emscripten/emsdk container (native reference, WebAssembly, parity test),
# then optionally the page in headless Chromium (test/screenshot.mjs, then
# test/files.mjs for Open, Save, storage, links and the embed API, in
# the Playwright container), and brings back www/fm1.wasm, www/meta.json, www/fm1.wasm.json
# and the screenshots (sim/web/build/screenshots/). Nothing runs on this
# machine but ssh, tar and scp; nothing is installed on aeon's host.
#
# --engines-ref builds against engines/ as committed at GIT_REF instead of the
# working tree, e.g. to try a branch that changes the engines; that module,
# its record, parity.json and the screenshots land in sim/web/build/ref-GIT_REF/,
# and www/ and the working tree's own results in sim/web/build/ stay as they
# were. The record names each container image by digest, since tags move.
#
# --readme-screenshots also runs test/readme-screenshots.mjs in the same
# container: the README's pictures (the panel, every engine's screen, an
# effect page, a parameter page, the phone layout and the parity figure) go
# to sim/web/build/readme-screenshots/, to be looked at and copied to
# assets/screenshots/ (assets/screenshots/README.md).
#
# Environment: FM1_SIM_HOST (required: user@host of a Linux machine with
# Docker), FM1_REMOTE_DIR (default ~/mvave-fm1/virtual on that host),
# FM1_SESSION (the session label on the containers), FM1_GPL_MODS (the GPL
# switch, engines/Makefile: 1, the default, builds the GPL modules in; 0 the
# MIT/BSD build). MIT licence, like the rest of this repository.
set -euo pipefail
# macOS tar would add AppleDouble ._* files (provenance attributes) to the
# staged tree, and a scan of www/ then trips over them.
export COPYFILE_DISABLE=1

SESSION=${FM1_SESSION:-virtual-fm1}
GPL_MODS=${FM1_GPL_MODS:-1}
case "$GPL_MODS" in 0|1) ;; *) echo "FM1_GPL_MODS is 0 or 1, not $GPL_MODS" >&2; exit 2 ;; esac
EMSDK_IMAGE=emscripten/emsdk:6.0.10
ALPINE_IMAGE=alpine:3.22
PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright:v1.63.0-noble
PLAYWRIGHT_NPM=playwright@1.63.0

ENGINES_REF=""
SCREENSHOT=1
README_SHOTS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --engines-ref) ENGINES_REF=$2; shift 2 ;;
    --no-screenshot) SCREENSHOT=0; shift ;;
    --readme-screenshots) README_SHOTS=1; shift ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
if [ "$README_SHOTS" = 1 ] && [ "$SCREENSHOT" = 0 ]; then
  echo "--readme-screenshots needs the page step; drop --no-screenshot" >&2
  exit 2
fi
HOST="${FM1_SIM_HOST:?set FM1_SIM_HOST=user@host (a Linux machine with Docker)}"
# The remote directory defaults to one under the remote user's home.
REMOTE=${FM1_REMOTE_DIR:-$(ssh "$HOST" 'printf %s "$HOME"')/mvave-fm1/virtual}

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
         make -C engines BUILD=/src/sim/web/build/musl CC=gcc CXX=g++ EXTRA=-static FM1_GPL_MODS=$GPL_MODS -j\$(nproc) \
           /src/sim/web/build/musl/fm1-render >/dev/null; s=\$?; chown -R \$(stat -c %u:%g /src) /src; exit \$s'"

echo "== build and parity in $EMSDK_IMAGE"
ssh "$HOST" "docker run --rm ${LABELS[*]} -e ENGINES_REF='${ENGINES_REF:-working tree}' -e FM1_IMAGES='$DIGESTS' -e FM1_GPL_MODS=$GPL_MODS \
  -v '$STAGE:/src' -w /src $EMSDK_IMAGE \
  sh -c 'bash sim/web/build.sh; s=\$?; chown -R \$(stat -c %u:%g /src) /src; exit \$s'"

if [ "$SCREENSHOT" = 1 ]; then
  echo "== page in headless Chromium ($PLAYWRIGHT_IMAGE)"
  ssh "$HOST" "mkdir -p '$REMOTE/playwright' && docker run --rm ${LABELS[*]} --ipc=host \
    -v '$REMOTE/playwright:/pw' -v '$STAGE:/src' -w /pw $PLAYWRIGHT_IMAGE \
    sh -c '[ -d node_modules/playwright ] || npm install --no-save --no-audit --no-fund $PLAYWRIGHT_NPM >/dev/null; \
           PLAYWRIGHT_DIR=/pw node /src/sim/web/test/screenshot.mjs /src/sim/web/www /src/sim/web/build/screenshots; \
           s=\$?; PLAYWRIGHT_DIR=/pw node /src/sim/web/test/files.mjs /src/sim/web/www /src/sim/web/build/screenshots \
             || s=1; if [ $README_SHOTS = 1 ] && [ \$s = 0 ]; then \
             PLAYWRIGHT_DIR=/pw node /src/sim/web/test/readme-screenshots.mjs /src/sim/web/www \
               /src/sim/web/build/readme-screenshots /src/sim/web/build/parity; s=\$?; fi; \
           chown -R \$(stat -c %u:%g /src) /src /pw; exit \$s'"
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
scp -q "$HOST:$STAGE/sim/web/www/fm1.wasm" "$HOST:$STAGE/sim/web/www/fm1.wasm.json" \
  "$HOST:$STAGE/sim/web/www/meta.json" "$DEST/"
rm -f "$RESULTS/parity.json"
scp -q "$HOST:$STAGE/sim/web/build/parity.json" "$RESULTS/"
if [ "$SCREENSHOT" = 1 ]; then              # replaced only by a new set
  rm -rf "$RESULTS/screenshots"
  scp -q -r "$HOST:$STAGE/sim/web/build/screenshots" "$RESULTS/"
fi
if [ "$README_SHOTS" = 1 ]; then
  rm -rf "$RESULTS/readme-screenshots"
  scp -q -r "$HOST:$STAGE/sim/web/build/readme-screenshots" "$RESULTS/"
fi
python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print(sys.argv[1], r['wasm_bytes'], 'bytes; parity', r['parity'], '; GPL switch', r['gpl_mods'], [m['id'] for m in r['licences'] if 'GPL' in m['licence']])" \
  "$DEST/fm1.wasm.json"
