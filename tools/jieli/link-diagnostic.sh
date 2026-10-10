#!/usr/bin/env bash
# MIT. Link on an existing LAN Docker host using its pinned cached toolchain.
set -euo pipefail
if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "usage: $0 SSH_HOST ABS_TOOLCHAIN_DIR ABS_REMOTE_WORK_DIR [inert|handover|panel-protocol]" >&2
    exit 2
fi
HOST=$1
TOOLCHAIN=$2
REMOTE=$3
PROFILE=${4:-inert}
if [[ $PROFILE != inert && $PROFILE != handover && $PROFILE != panel-protocol ]]; then
    echo "unknown diagnostic profile" >&2
    exit 2
fi
for path in "$TOOLCHAIN" "$REMOTE"; do
    if [[ ! $path =~ ^/[a-zA-Z0-9_./-]+$ ]] || [[ $path == *..* ]]; then
        echo "remote directories must be absolute simple paths without .." >&2
        exit 2
    fi
done
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT="$ROOT/build/jieli-diagnostic"
if [[ $PROFILE == handover ]]; then OUT="$ROOT/build/jieli-handover"; fi
if [[ $PROFILE == panel-protocol ]]; then OUT="$ROOT/build/jieli-panel-protocol"; fi
ARCHIVE=$(mktemp -t lunar-diag.XXXXXX)
trap 'rm -f "$ARCHIVE"' EXIT
cd "$ROOT"
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$ARCHIVE" firmware/diagnostic firmware/handover firmware/display \
    tools/jieli/audit_link.py tools/jieli/diagnostic_report.py \
    tools/jieli/diagnostic_flat.py tools/jieli/link-diagnostic-in-container.sh
ssh -o BatchMode=yes "$HOST" "mkdir -p '$REMOTE/src' '$REMOTE/out'"
scp "$ARCHIVE" "$HOST:$REMOTE/source.tar.gz"
ssh -o BatchMode=yes "$HOST" "tar -xzf '$REMOTE/source.tar.gz' -C '$REMOTE/src' && docker run --rm --cgroup-parent=docker-batch.slice --cpus=4 --memory=4g --memory-swap=4g --env PROFILE='$PROFILE' --label lan.project=lunar-modulator --label lan.session=board-diagnostic -v '$REMOTE/src:/src:ro' -v '$REMOTE/out:/out' -v '$TOOLCHAIN:/opt/jieli:ro' lunar-jieli-check:bookworm bash /src/tools/jieli/link-diagnostic-in-container.sh"
mkdir -p "$OUT"
scp -r "$HOST:$REMOTE/out/." "$OUT/"
echo "diagnostic artifacts: $OUT"
