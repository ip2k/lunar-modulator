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
# test/files.mjs for Open, Save, storage, links and the embed API, then
# test/editor.mjs, a 30-second storm on the editor's port of the real
# AudioWorklet, then test/editor-ui.mjs, the editor's shell, flow and sound
# (follow, undo, PLAY and EDIT, every inspector, the layouts), then
# test/editor-reach.mjs (keyboard, screen-reader and phone passes, gain
# read-outs, then test/editor-map.mjs, the Map, then test/editor-v1.mjs, the
# v1 completion: rows, late cables, search operators, A/B picks, sheets, axe-core),
# then test/info-dialogs.mjs (desktop and phone dialog behavior),
# all in the Playwright
# container; BROWSER=firefox or webkit runs the editor's five tests in those
# browsers too, by hand, sim/web/README.md "Stage ED5b"), and brings back www/fm1.wasm, www/meta.json, www/fm1.wasm.json
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
# MIT/BSD build), FM1_DX7_SINE (the DX7 sine, engines/Makefile: trunc12, the
# default since the owner's A/B of 2026-10-29, or msfa; engines/msfa.md). A
# build with the other sine is a trial: its module, record and results land
# in sim/web/build/dx7-<sine>/ (dx7-msfa), and www/ stays as it was. MIT
# licence, like the rest of this repository.
set -euo pipefail
# macOS tar would add AppleDouble ._* files (provenance attributes) to the
# staged tree, and a scan of www/ then trips over them.
export COPYFILE_DISABLE=1

SESSION=${FM1_SESSION:-virtual-fm1}
GPL_MODS=${FM1_GPL_MODS:-1}
case "$GPL_MODS" in 0|1) ;; *) echo "FM1_GPL_MODS is 0 or 1, not $GPL_MODS" >&2; exit 2 ;; esac
# The default sine is engines/Makefile's, read here so the two cannot drift.
DEFAULT_DX7_SINE=$(sed -n 's/^FM1_DX7_SINE ?= //p' "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)/engines/Makefile")
DX7_SINE=${FM1_DX7_SINE:-$DEFAULT_DX7_SINE}
case "$DX7_SINE" in msfa|trunc12) ;; *) echo "FM1_DX7_SINE is msfa or trunc12, not $DX7_SINE" >&2; exit 2 ;; esac
EMSDK_IMAGE=emscripten/emsdk:6.0.10
ALPINE_IMAGE=alpine:3.22
PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright:v1.63.0-noble
PLAYWRIGHT_NPM=playwright@1.63.0
AXE_NPM=axe-core@4         # the editor's v1 page test runs its rules (test/editor-v1.mjs)

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
REMOTE=${REMOTE%/}
case "$REMOTE" in
  /*) [ "$REMOTE" != / ] || { echo "FM1_REMOTE_DIR cannot be /" >&2; exit 2; } ;;
  *) echo "FM1_REMOTE_DIR must be an absolute path: $REMOTE" >&2; exit 2 ;;
esac
case "$REMOTE" in
  *"'"*|*$'\n'*|*$'\r'*) echo "FM1_REMOTE_DIR contains an unsupported quote or newline" >&2; exit 2 ;;
esac
if [ "$(uname -s)" = Darwin ]; then
  MAC_FREE_GB=$(df -g /System/Volumes/Data | awk 'END {print $4}')
  if ! [[ "$MAC_FREE_GB" =~ ^[0-9]+$ ]] || [ "$MAC_FREE_GB" -lt 500 ]; then
    echo "Mac data volume has ${MAC_FREE_GB:-unknown} GiB free; this build requires the 500 GiB floor" >&2
    exit 1
  fi
fi
RUN_ID=build-$(date -u +%Y%m%dT%H%M%SZ)-$$-$RANDOM
LOG=$SIM/build/remote-runs/$RUN_ID.log
FETCH=$SIM/build/remote-runs/$RUN_ID.fetch
mkdir -p "${LOG%/*}"
record() { printf '%s\n' "$*" | tee -a "$LOG"; }
record "host=$HOST remote=$REMOTE run=$RUN_ID base=$(git -C "$ROOT" rev-parse HEAD)"

# Resolve the *output* before the expensive build. Different refs can sanitize
# to the same directory, and GPL variants of the default build share www/.
# Claim each canonical output directory separately: an alias can make DEST
# equal another run's DEST even when their RESULTS differ. Sort claims to
# avoid deadlock, then hold them through parity and screenshot publication.
if [ -n "$ENGINES_REF" ]; then
  DEST=$SIM/build/ref-$(printf '%s' "$ENGINES_REF" | tr -c 'A-Za-z0-9._-' '_')
  if [ "$DX7_SINE" != "$DEFAULT_DX7_SINE" ]; then DEST=$DEST-dx7-$DX7_SINE; fi
  RESULTS=$DEST
elif [ "$DX7_SINE" != "$DEFAULT_DX7_SINE" ]; then
  DEST=$SIM/build/dx7-$DX7_SINE
  RESULTS=$DEST
else
  DEST=$SIM/www
  RESULTS=$SIM/build
fi
# A lock beside each canonical resource also coordinates another checkout that
# reaches this output through a symlink. No checkout-local lock registry is
# sufficient for that case.
PUBLISH_LOCK_LINES=$(python3 -c 'import pathlib,sys; paths=sorted({str(pathlib.Path(p).resolve()) for p in sys.argv[1:]}); print("\n".join(p + ".lunar-publish.lock" for p in paths))' "$DEST" "$RESULTS")
PUBLISH_TARGET_LOCKS=()
while IFS= read -r lock; do PUBLISH_TARGET_LOCKS+=("$lock"); done <<< "$PUBLISH_LOCK_LINES"
STAGE=""
STAGE_VALID=0
MOUNT_GUARD=""
MUSL_CONTAINER=lunar-$RUN_ID-musl
EMSDK_CONTAINER=lunar-$RUN_ID-emsdk
PLAYWRIGHT_CONTAINER=lunar-$RUN_ID-playwright
PUBLISH_LOCKS=()
cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [ "$STAGE_VALID" = 1 ]; then
    if ssh "$HOST" "docker info >/dev/null 2>&1 || exit 1; \
      for name in '$MUSL_CONTAINER' '$EMSDK_CONTAINER' '$PLAYWRIGHT_CONTAINER'; do \
        if docker container inspect \"\$name\" >/dev/null 2>&1; then docker rm -f \"\$name\" >/dev/null || exit 1; fi; \
      done; ${MOUNT_GUARD}rm -rf -- $STAGE_Q"; then
      record "cleanup=ok stage=$STAGE"
    else
      record "cleanup=failed stage=$STAGE"
      status=1
    fi
  fi
  if [ -d "$FETCH" ]; then rm -rf -- "$FETCH"; fi
  if [ "${#PUBLISH_LOCKS[@]}" -gt 0 ]; then
    for lock in "${PUBLISH_LOCKS[@]}"; do
      if [ "$(cat "$lock/owner" 2>/dev/null)" = "$RUN_ID" ]; then
        if rm -- "$lock/owner" && rmdir "$lock"; then
          record "publication_lock=released path=$lock"
        else
          record "publication_lock=release_failed path=$lock"
          status=1
        fi
      else
        record "publication_lock=owner_mismatch path=$lock"
        status=1
      fi
    done
  fi
  record "exit=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for lock in "${PUBLISH_TARGET_LOCKS[@]}"; do
  if ! mkdir "$lock" 2>/dev/null; then
    record "publication_busy destination=$DEST results=$RESULTS lock=$lock"
    exit 75
  fi
  printf '%s\n' "$RUN_ID" > "$lock/owner"
  PUBLISH_LOCKS+=("$lock")
  record "publication_lock=$lock destination=$DEST results=$RESULTS"
done

# Allocate under the project root without touching any other invocation's src
# tree. The remote checks an external-volume mount before mkdir can create a
# plain directory on the Mac's internal disk in its place.
REMOTE_Q=$(printf '%q' "$REMOTE")
STAGE=$(ssh "$HOST" "bash -s -- $REMOTE_Q $RUN_ID" <<'REMOTE_STAGE'
remote=$1
run_id=$2
if [[ "$remote" == /Volumes/* ]]; then
  volume=${remote#/Volumes/}; volume=${volume%%/*}
  if [ -z "$volume" ] || ! mountpoint -q "/Volumes/$volume"; then
    echo "remote volume is not mounted: /Volumes/$volume" >&2
    exit 1
  fi
fi
mkdir -p -- "$remote/runs"
free_kb=$(df -Pk "$remote/runs" | awk 'END {print $4}')
if ! [[ "$free_kb" =~ ^[0-9]+$ ]] || [ "$free_kb" -lt 10485760 ]; then
  echo "remote stage needs at least 10 GiB free (found ${free_kb:-unknown} KiB)" >&2
  exit 1
fi
mktemp -d "$remote/runs/$run_id.XXXXXXXX"
REMOTE_STAGE
)
if [[ "$STAGE" != "$REMOTE/runs/$RUN_ID".* ]]; then
  echo "unexpected remote stage path: $STAGE" >&2
  exit 1
fi
STAGE_Q=$(printf '%q' "$STAGE")
if [[ "$REMOTE" == /Volumes/* ]]; then
  volume=${REMOTE#/Volumes/}; volume=${volume%%/*}
  MOUNT_GUARD="mountpoint -q '/Volumes/$volume' && "
fi
STAGE_VALID=1
LABELS=(--label project=mvave-fm1-firmware --label "session=$SESSION" --label "invocation=$RUN_ID")

record "stage=$STAGE"
echo "== staging sources on $HOST:$STAGE"
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
record "images=$DIGESTS"

echo "== static musl reference in $ALPINE_IMAGE"
ssh "$HOST" "docker run --rm --name '$MUSL_CONTAINER' --cgroup-parent=docker-batch.slice --memory=8g --memory-swap=8g ${LABELS[*]} -v '$STAGE:/src' -w /src $ALPINE_IMAGE \
  sh -c 'apk add -q build-base >/dev/null && \
         make -C engines -f Makefile -f /src/sim/web/mk/sim.mk SIM=/src/sim/web \
           BUILD=/src/sim/web/build/musl CC=gcc CXX=g++ EXTRA=-static FM1_GPL_MODS=$GPL_MODS FM1_DX7_SINE=$DX7_SINE -j\$(nproc) \
           /src/sim/web/build/musl/fm1-render /src/sim/web/build/musl/fm1-sim-render >/dev/null; \
         s=\$?; chown -R \$(stat -c %u:%g /src) /src; exit \$s'"

echo "== build and parity in $EMSDK_IMAGE"
ssh "$HOST" "docker run --rm --name '$EMSDK_CONTAINER' --cgroup-parent=docker-batch.slice --memory=8g --memory-swap=8g ${LABELS[*]} -e ENGINES_REF='${ENGINES_REF:-working tree}' -e FM1_IMAGES='$DIGESTS' -e FM1_GPL_MODS=$GPL_MODS -e FM1_DX7_SINE=$DX7_SINE \
  -v '$STAGE:/src' -w /src $EMSDK_IMAGE \
  sh -c 'bash sim/web/build.sh; s=\$?; chown -R \$(stat -c %u:%g /src) /src; exit \$s'"

if [ "$SCREENSHOT" = 1 ]; then
  echo "== page in headless Chromium ($PLAYWRIGHT_IMAGE)"
  # Seed from the prior shared install when present; this run writes only to
  # its own copy, so offline cached builds and concurrent npm runs both work.
  ssh "$HOST" "if [ -d '$REMOTE/playwright/node_modules/playwright' ] && [ -d '$REMOTE/playwright/node_modules/axe-core' ]; then \
    mkdir -p '$STAGE/playwright' && cp -a '$REMOTE/playwright/node_modules' '$STAGE/playwright/'; fi"
  ssh "$HOST" "docker run --rm --name '$PLAYWRIGHT_CONTAINER' --cgroup-parent=docker-batch.slice --memory=8g --memory-swap=8g ${LABELS[*]} --ipc=host \
    -v '$STAGE/playwright:/pw' -v '$STAGE:/src' -w /pw $PLAYWRIGHT_IMAGE \
    sh -c '[ -d node_modules/playwright ] && [ -d node_modules/axe-core ] || npm install --no-save --no-audit --no-fund $PLAYWRIGHT_NPM $AXE_NPM >/dev/null; \
           PLAYWRIGHT_DIR=/pw node /src/sim/web/test/screenshot.mjs /src/sim/web/www /src/sim/web/build/screenshots; \
           s=\$?; PLAYWRIGHT_DIR=/pw node /src/sim/web/test/files.mjs /src/sim/web/www /src/sim/web/build/screenshots \
             || s=1; BROWSER=chromium PLAYWRIGHT_DIR=/pw node /src/sim/web/test/info-dialogs.mjs /src/sim/web/www /src/sim/web/build/screenshots \
             || s=1; PLAYWRIGHT_DIR=/pw node /src/sim/web/test/editor.mjs /src/sim/web/www /src/sim/web/build/screenshots 30 \
             || s=1; PLAYWRIGHT_DIR=/pw node /src/sim/web/test/editor-ui.mjs /src/sim/web/www /src/sim/web/build/screenshots \
             || s=1; PLAYWRIGHT_DIR=/pw node /src/sim/web/test/editor-reach.mjs /src/sim/web/www /src/sim/web/build/screenshots \
             || s=1; PLAYWRIGHT_DIR=/pw node /src/sim/web/test/editor-map.mjs /src/sim/web/www /src/sim/web/build/screenshots \
             || s=1; PLAYWRIGHT_DIR=/pw node /src/sim/web/test/editor-v1.mjs /src/sim/web/www /src/sim/web/build/screenshots \
             || s=1; if [ $README_SHOTS = 1 ] && [ \$s = 0 ]; then \
             PLAYWRIGHT_DIR=/pw node /src/sim/web/test/readme-screenshots.mjs /src/sim/web/www \
               /src/sim/web/build/readme-screenshots /src/sim/web/build/parity; s=\$?; fi; \
           chown -R \$(stat -c %u:%g /src) /src /pw; exit \$s'"
fi

echo "== fetching results"
# A build of another ref's engines is a trial: its module and every result go
# to build/ref-<ref>/, so www/fm1.wasm always matches this working tree and
# build/ keeps this tree's parity and screenshots.
# A module with the other DX7 sine than engines/Makefile's default is a trial
# too: www/ keeps the default sine's module. The claim above owns both paths.
mkdir -p "$FETCH"
scp -q "$HOST:$STAGE/sim/web/www/fm1.wasm" "$HOST:$STAGE/sim/web/www/fm1.wasm.json" \
  "$HOST:$STAGE/sim/web/www/meta.json" "$FETCH/"
scp -q "$HOST:$STAGE/sim/web/build/parity.json" "$FETCH/"
if [ "$SCREENSHOT" = 1 ]; then              # replaced only by a new set
  scp -q -r "$HOST:$STAGE/sim/web/build/screenshots" "$FETCH/"
fi
if [ "$README_SHOTS" = 1 ]; then
  scp -q -r "$HOST:$STAGE/sim/web/build/readme-screenshots" "$FETCH/"
fi
mkdir -p "$DEST" "$RESULTS"
for name in fm1.wasm fm1.wasm.json meta.json; do mv -f "$FETCH/$name" "$DEST/$name"; done
mv -f "$FETCH/parity.json" "$RESULTS/parity.json"
if [ "$SCREENSHOT" = 1 ]; then
  rm -rf -- "$RESULTS/screenshots"
  mv "$FETCH/screenshots" "$RESULTS/screenshots"
fi
if [ "$README_SHOTS" = 1 ]; then
  rm -rf -- "$RESULTS/readme-screenshots"
  mv "$FETCH/readme-screenshots" "$RESULTS/readme-screenshots"
fi
python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print(sys.argv[1], r['wasm_bytes'], 'bytes; parity', r['parity'], '; GPL switch', r['gpl_mods'], '; DX7 sine', r['dx7_sine'], [m['id'] for m in r['licences'] if 'GPL' in m['licence']])" \
  "$DEST/fm1.wasm.json"
