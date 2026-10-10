#!/usr/bin/env bash
# Regenerate Movy oracle traces on aeon (docs/13 stage M3).
#
#   tools/movy-oracle/run-on-aeon.sh [--frames block|tick] [--movy1] IN_DIR OUT_DIR
#   tools/movy-oracle/run-on-aeon.sh --clean
#
# Syncs driver/ to aeon, makes sure Movy (schwung-movy, MIT, megadake) is
# checked out there at the pinned commit, builds the driver against its
# seq-core in a Rust container, runs every IN_DIR/*.verbs (with any
# <stem>.in.movy1 beside it) and copies back OUT_DIR/<stem>.jsonl, plus
# <stem>.out.movy1 with --movy1, and summary.jsonl (one line per script).
# Movy's code is only ever built and run inside the container, never here.
# --clean deletes the whole remote work directory.
#
# Environment: MOVY_ORACLE_HOST (required: user@host of a Linux machine with Docker), MOVY_ORACLE_REMOTE
# (/home/claude/mvave-fm1/oracle), MOVY_ORACLE_IMAGE (rust:1.98.1-bookworm),
# MOVY_ORACLE_SESSION (the session label on the containers).
set -euo pipefail

HOST="${MOVY_ORACLE_HOST:?set MOVY_ORACLE_HOST=user@host (a Linux machine with Docker)}"
REMOTE="${MOVY_ORACLE_REMOTE:-/home/claude/mvave-fm1/oracle}"
IMAGE="${MOVY_ORACLE_IMAGE:-rust:1.98.1-bookworm}"
SESSION="${MOVY_ORACLE_SESSION:-movy-oracle-or-virtual-fm1}"
# These values enter remote shell programs and volume/label arguments.
[[ "$REMOTE" =~ ^/([A-Za-z0-9_-][A-Za-z0-9._-]*/){2,}[A-Za-z0-9_-][A-Za-z0-9._-]*$ ]] || {
    echo "MOVY_ORACLE_REMOTE: use an absolute work path with at least three components" >&2; exit 2; }
[[ "$SESSION" =~ ^[A-Za-z0-9._-]+$ && "$IMAGE" =~ ^[A-Za-z0-9._/:@-]+$ ]] || {
    echo "invalid oracle session or image" >&2; exit 2; }
MOVY_URL="https://github.com/DimaDake/schwung-movy.git"
MOVY_SHA="9190e79a2f461e71d2bf0a9fa77042011945021e"

here="$(cd "$(dirname "$0")" && pwd)"

remote() { ssh -o BatchMode=yes "$HOST" "$@"; }

# in_container NETWORK 'shell command': one throwaway container, run as the
# remote user, with the work directory at /work.
in_container() {
    remote "docker run --rm --network $1 \
        --label project=mvave-fm1-firmware --label session=$SESSION \
        -u \$(id -u):\$(id -g) -e HOME=/work -e CARGO_HOME=/work/.cargo-home \
        -v $REMOTE:/work -w /work $IMAGE sh -c $(printf %q "$2")"
}

flags=()
while [ $# -gt 0 ]; do
    case "$1" in
        --frames)
            case "${2:-}" in block|tick) flags+=(--frames "$2");;
                *) echo "--frames requires block or tick" >&2; exit 2;; esac
            shift 2 ;;
        --movy1) flags+=(--movy1); shift ;;
        --clean)
            remote "rm -rf $REMOTE"
            echo "removed $HOST:$REMOTE"
            exit 0 ;;
        -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
        -*) echo "unknown option $1" >&2; exit 2 ;;
        *) break ;;
    esac
done
if [ $# -ne 2 ]; then
    echo "usage: $0 [--frames block|tick] [--movy1] IN_DIR OUT_DIR" >&2
    exit 2
fi
in_dir="$1"
out_dir="$2"
[ -d "$in_dir" ] || { echo "$in_dir: not a directory" >&2; exit 2; }
job="job-$(date +%Y%m%d-%H%M%S)-$$"

remote "mkdir -p $REMOTE/$job/in $REMOTE/$job/out"
trap 'remote "rm -rf $REMOTE/$job" || true' EXIT

rsync -a --delete --exclude target/ "$here/driver/" "$HOST:$REMOTE/driver/"
rsync -a --include '*.verbs' --include '*.in.movy1' --exclude '*' \
    "$in_dir/" "$HOST:$REMOTE/$job/in/"

# Movy at the pinned commit, cloned inside a container; refuse a dirty tree.
in_container bridge "set -e
    if [ ! -d schwung-movy/.git ]; then git clone -q $MOVY_URL schwung-movy; fi
    cd schwung-movy
    git cat-file -e $MOVY_SHA^{commit} 2>/dev/null || git fetch -q origin
    git checkout -q --detach $MOVY_SHA
    test \"\$(git rev-parse HEAD)\" = $MOVY_SHA
    test -z \"\$(git status --porcelain)\""

# Build and run without a network: seq-core and the driver have no
# dependencies, and Cargo.lock is committed. A script that fails is named in
# errors.txt and the others still run.
in_container none "set -e
    cd driver
    cargo build -q --release --locked --offline
    status=0
    find /work/$job/in -name '*.verbs' | sort \
        | xargs -r -P \$(nproc) -n 64 ./target/release/movy-oracle files \
            /work/$job/out ${flags[*]+${flags[*]}} \
        > /work/$job/out/unsorted 2> /work/$job/out/errors.txt || status=\$?
    sort /work/$job/out/unsorted > /work/$job/out/summary.jsonl
    rm /work/$job/out/unsorted
    echo \$status > /work/$job/out/status"

mkdir -p "$out_dir"
rsync -a "$HOST:$REMOTE/$job/out/" "$out_dir/"
status="$(cat "$out_dir/status")"
rm -f "$out_dir/status"
if [ -s "$out_dir/errors.txt" ]; then
    cat "$out_dir/errors.txt" >&2
else
    rm -f "$out_dir/errors.txt"
fi
n=$(grep -c . "$out_dir/summary.jsonl" || true)
echo "movy-oracle: $n script(s) run -> $out_dir (exit $status)"
exit "$status"
