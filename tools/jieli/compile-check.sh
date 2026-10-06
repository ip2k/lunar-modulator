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
# On the build host, under FM1_JIELI_DIR (default ~/mvave-fm1/sdk-v1213):
#   dl/          the toolchain archive (SHA-256 pinned)
#   toolchain/   the archive unpacked; mounted read-only at /opt/jieli
#   sdk/         AC79 SDK (Apache-2.0) at the pinned V1.2.13 commit, blobless,
#                with only the headers (libc++ and newlib), demo_hello's wl82
#                Makefile and the libraries it links checked out (for symbols).
#                Its V1.2.13 libc++ (version 12) ships math.h, so no shim is
#                needed. No uboot.boot, wl82loader.bin or ota.bin is fetched.
#   src/         the staged tree: engines/, sim/web/, firmware/, tools/jieli/
#   out/         results; copied back to engines/build-jieli/ here. Includes
#                out/audit_link.json: tools/jieli/audit_link.py run over the
#                compiled objects and our sources (the compile-time half of the
#                key-check safeguards; the link-time checks run on the real
#                link later), and out/boot-bridge/: the boot_info bridge
#                compiled for pi32v2, which must call nothing but
#                __real_boot_info_init.
#
# Environment: FM1_JIELI_HOST (required: user@host of a Linux x86-64 machine
# with Docker), FM1_JIELI_DIR, FM1_SESSION (container label, default
# jieli-compile), FM1_JIELI_TOOLCHAIN_SHA256 (to accept a different archive
# when JieLi's link moves; the report records which one ran), FM1_GPL_MODS
# (the GPL switch, engines/Makefile: 1, the default, compiles the GPL modules
# too; 0 checks the MIT/BSD build; record.json says which ran), FM1_MODULES
# (the module list, engines/modules/catalogue.mk: `all`, the default, or a
# list such as `default`; the report gives flash by module and the list's
# total against the budget; record.json says which ran).
# MIT licence, like the rest of this repository.
set -euo pipefail
export COPYFILE_DISABLE=1   # no AppleDouble files in the staged tree

HOST="${FM1_JIELI_HOST:?set FM1_JIELI_HOST=user@host (a Linux x86-64 machine with Docker)}"
SESSION=${FM1_SESSION:-jieli-compile}
GPL_MODS=${FM1_GPL_MODS:-1}
case "$GPL_MODS" in 0|1) ;; *) echo "FM1_GPL_MODS is 0 or 1, not $GPL_MODS" >&2; exit 2 ;; esac
MODULES=${FM1_MODULES:-all}
case "$MODULES" in *[!A-Za-z0-9._,-]*) echo "FM1_MODULES: ids, commas and a list name only" >&2; exit 2 ;; esac
LABELS="--label project=lunar-modulator --label session=$SESSION"

# Pins. JieLi's short link redirects to the newest archive; the pin makes a
# silent change of toolchain fail loudly.
#
# The SDK pin is V1.2.13 (owner's decision, 2026-10-05;
# notes/2026-10-05-softkey-efuse.md §4): branch release/AC79NN_SDK_V1.2.0 at
# e30b1ee, which is tag AC79NN_SDK_V1.2.13_2026-04-20 plus a README change.
# Only the closed libraries, headers and flags are used. Its uboot.boot,
# wl82loader.bin and ota.bin are never taken into an FM-1 package (trap 11);
# tools/jieli/audit_link.py gates the eventual link, packaging asserts the
# stock SPL hash. This check is compile-only: no loader binary is fetched.
TOOLCHAIN_URL=https://pkgman.jieliapp.com/s/linux-toolchain
TOOLCHAIN_ARCHIVE=jieli-linux-toolchains-20250805.1.tar.xz
TOOLCHAIN_SHA256=${FM1_JIELI_TOOLCHAIN_SHA256:-f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958}
SDK_REPO=https://gitee.com/Jieli-Tech/fw-AC79_AIoT_SDK.git
SDK_TAG=AC79NN_SDK_V1.2.13_2026-04-20
SDK_BRANCH=release/AC79NN_SDK_V1.2.0
SDK_COMMIT=e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d
CURL_IMAGE=curlimages/curl:8.16.0
GIT_IMAGE=alpine/git:v2.49.1
BASE_IMAGE=debian:bookworm-slim
IMAGE=lunar-jieli-check:bookworm

ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
# V1.2.13 lands in its own work dir, apart from the V1.1.9 tree under
# ~/mvave-fm1/jieli; override with FM1_JIELI_DIR.
REMOTE=${FM1_JIELI_DIR:-$(ssh "$HOST" 'printf %s "$HOME"')/mvave-fm1/sdk-v1213}
LOCAL_OUT=$ROOT/engines/build-jieli

echo "== fetching what is missing on $HOST:$REMOTE"
# ssh joins its arguments into one remote command line: quote each for it.
ARGS=$(printf '%q ' "$REMOTE" "$LABELS" "$TOOLCHAIN_URL" "$TOOLCHAIN_ARCHIVE" "$TOOLCHAIN_SHA256" \
  "$SDK_REPO" "$SDK_TAG" "$SDK_BRANCH" "$SDK_COMMIT" "$CURL_IMAGE" "$GIT_IMAGE")
ssh "$HOST" "bash -s -- $ARGS" <<'REMOTE'
set -euo pipefail
R=$1 LABELS=$2 TC_URL=$3 TC_AR=$4 TC_SHA=$5 SDK_REPO=$6 SDK_TAG=$7 SDK_BRANCH=$8 SDK_COMMIT=$9
CURL=${10} GIT=${11}
U="$(id -u):$(id -g)"
mkdir -p "$R/dl" "$R/toolchain"
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
# Gitee's SSL is flaky and its promisor drops connections mid-transfer, so a
# per-path `checkout -- <path>` (one lazy fetch each) fails. Instead keep a
# persistent blobless BARE mirror and drive one sparse worktree from it: the
# sparse `checkout` is a single batched blob fetch, and the mirror keeps the
# blobs that did arrive, so retrying resumes rather than restarts. Each network
# step is retried hard (the mirror makes progress every attempt).
retry() { local max=$1; shift; local n=0
  until "$@"; do n=$((n+1)); [ "$n" -ge "$max" ] && return 1
    echo "   retry $n/$max: $*" >&2; sleep 5; done; }
GENV="-e GIT_HTTP_LOW_SPEED_LIMIT=1000 -e GIT_HTTP_LOW_SPEED_TIME=60"
gitq() { docker run --rm $LABELS -u "$U" $GENV -v "$R:/w" -w /w "$GIT" "$@"; }

# 1. The bare blobless mirror of the branch that holds the pinned commit.
if [ ! -d "$R/sdk.git/HEAD" ] && [ ! -f "$R/sdk.git/HEAD" ]; then
  rm -rf "$R/sdk.git"
  retry 20 gitq clone -q --bare --filter=blob:none --branch "$SDK_BRANCH" "$SDK_REPO" sdk.git
fi
docker run --rm $LABELS -u "$U" -v "$R/sdk.git:/g" -w /g "$GIT" cat-file -e "$SDK_COMMIT^{commit}" 2>/dev/null \
  || retry 20 docker run --rm $LABELS -u "$U" $GENV -v "$R/sdk.git:/g" -w /g "$GIT" \
       fetch -q --filter=blob:none origin "$SDK_COMMIT"

# 2. A sparse worktree of the mirror at the pinned commit. The compile check
#    needs the SDK header tree (include_lib: C++, driver, system, which the
#    V1.2.13 libc++ threading headers reach) and the libraries demo_hello links
#    (for their symbol tables); the broader source checkout is a separate,
#    human concern (tools/jieli/ac79-sdk-sparse.txt). include_lib also carries
#    the libc++ and newlib .a files. A single sparse `checkout` fetches all the
#    in-cone blobs in one batch, retried until Gitee lets it finish. The
#    worktree's .git is a gitfile with the mirror's absolute path, so the
#    mirror is mounted at that same path in each container that touches it.
SPARSE_SET="/include_lib/
/cpu/wl82/liba/cpu.a /cpu/wl82/liba/event.a /cpu/wl82/liba/system.a
/cpu/wl82/liba/cfg_tool.a /cpu/wl82/liba/fs.a /cpu/wl82/liba/common_lib.a
/cpu/wl82/liba/update.a"
M="-v $R/sdk:/sdk -v $R/sdk.git:$R/sdk.git"
rm -rf "$R/sdk"
# Mount the mirror at its real host path so the worktree's recorded gitdir
# resolves in the later containers (which mount it at the same path).
docker run --rm $LABELS -u "$U" -v "$R/sdk.git:$R/sdk.git" -w "$R/sdk.git" "$GIT" worktree prune || true
docker run --rm $LABELS -u "$U" -v "$R/sdk.git:$R/sdk.git" -v "$R:/w" -w "$R/sdk.git" "$GIT" \
  worktree add -q --no-checkout --detach /w/sdk "$SDK_COMMIT"
printf '%s\n' $SPARSE_SET | \
  docker run --rm -i $LABELS -u "$U" $M -w /sdk "$GIT" sparse-checkout set --no-cone --stdin
retry 20 docker run --rm $LABELS -u "$U" $GENV $M -w /sdk "$GIT" checkout
got=$(docker run --rm $LABELS -u "$U" $M -w /sdk "$GIT" rev-parse HEAD)
[ "$got" = "$SDK_COMMIT" ] || { echo "SDK at $got, expected $SDK_COMMIT" >&2; exit 1; }
# The SDK libc++ (version 12) ships its own math.h, so no shim is needed.
[ -f "$R/sdk/include_lib/c++/include/math.h" ] || {
  echo "SDK libc++ has no math.h; a shim would be needed (see git history)" >&2; exit 1; }
# Refuse a checkout that dragged in any boot/loader binary (defence in depth;
# none is referenced by this script).
bad=$(find "$R/sdk" -path "$R/sdk/.git" -prune -o -type f \
  \( -name '*.boot' -o -name 'wl82loader*.bin' -o -name 'ota.bin' \) -print)
[ -z "$bad" ] || { echo "refusing: loader/boot binaries present in checkout:" >&2; echo "$bad" >&2; exit 1; }
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
    --exclude='.DS_Store' --exclude='__pycache__' -cf - engines sim/web firmware tools/jieli \
  | ssh "$HOST" "tar -x -C '$REMOTE/src'"

echo "== compiling in $IMAGE"
ssh "$HOST" "rm -rf '$REMOTE/out' && mkdir -p '$REMOTE/out' && docker run --rm $LABELS \
  -u \$(id -u):\$(id -g) -e FM1_GPL_MODS=$GPL_MODS -e FM1_MODULES=$MODULES \
  -v '$REMOTE/toolchain/current:/opt/jieli:ro' -v '$REMOTE/sdk:/sdk:ro' \
  -v '$REMOTE/src:/src' -v '$REMOTE/out:/out' $IMAGE bash /src/tools/jieli/in-container.sh"

echo "== record"
COMMIT=$(git -C "$ROOT" rev-parse HEAD)
DIRTY=$(git -C "$ROOT" status --porcelain -- engines sim/web/src tools/jieli | wc -l | tr -d ' ')
ssh "$HOST" "cat > '$REMOTE/out/record.json'" <<EOF
{"tree": "$COMMIT", "uncommitted_files": $DIRTY, "gpl_mods": $GPL_MODS, "modules": "$MODULES",
 "toolchain_archive": "$TOOLCHAIN_ARCHIVE", "toolchain_sha256": "$TOOLCHAIN_SHA256",
 "sdk": "$SDK_TAG", "sdk_commit": "$SDK_COMMIT",
 "image": "$IMAGE", "image_id": "$DIGEST",
 "ran": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF

echo "== fetching results to $LOCAL_OUT"
rm -rf "$LOCAL_OUT" && mkdir -p "$LOCAL_OUT"
# Reports, logs, size tables and the link-audit report only; the objects stay
# on the build host.
ssh "$HOST" "cd '$REMOTE/out' && tar -cf - report.json report.md record.json sizes/*.json \
  \$(find . -name '*.log' -o -name '*.rc' -o -name 'objects.txt' -o -name 'modules.txt' -o -name 'opt.txt' -o -name 'extra.txt' -o -name 'audit_link.json' | sed 's|^\./||')" \
  | tar -x -C "$LOCAL_OUT"
echo "report: $LOCAL_OUT/report.md"
