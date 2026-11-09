#!/usr/bin/env bash
# MIT. Link on an existing LAN Docker host using its pinned cached toolchain.
set -euo pipefail
if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "usage: $0 SSH_HOST ABS_TOOLCHAIN_DIR ABS_REMOTE_WORK_DIR [inert|handover|panel-protocol|m5-test-pattern|ramtest]" >&2
    exit 2
fi
HOST=$1
TOOLCHAIN=$2
REMOTE=$3
PROFILE=${4:-inert}
if [[ $PROFILE != inert && $PROFILE != handover && $PROFILE != panel-protocol &&
      $PROFILE != m5-test-pattern && $PROFILE != ramtest ]]; then
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
if [[ $PROFILE == m5-test-pattern ]]; then OUT="$ROOT/build/jieli-m5"; fi
if [[ $PROFILE == ramtest ]]; then OUT="$ROOT/build/jieli-ramtest"; fi
# Shown on the M5 panel and kept in its status block: [A-Za-z0-9 .:-], 1-19 chars.
BUILD_ID=${LUNAR_BUILD_ID:-$(git -C "$ROOT" rev-parse --short=8 HEAD 2>/dev/null || echo unknown) $(date -u +%Y-%m-%d)}
if [[ ! $BUILD_ID =~ ^[A-Za-z0-9\ .:-]{1,19}$ ]]; then
    echo "build id must be 1-19 characters of [A-Za-z0-9 .:-]" >&2
    exit 2
fi
SESSION=${LUNAR_SESSION:-board-diagnostic}
if [[ ! $SESSION =~ ^[a-z0-9-]{1,48}$ ]]; then
    echo "session label must be [a-z0-9-]" >&2
    exit 2
fi
ARCHIVE=$(mktemp -t lunar-diag.XXXXXX)
trap 'rm -f "$ARCHIVE"' EXIT
cd "$ROOT"
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$ARCHIVE" firmware/diagnostic firmware/handover firmware/display \
    firmware/board firmware/timing firmware/m5 firmware/ramtest firmware/third_party/fm1-nes \
    tools/jieli/audit_link.py tools/jieli/diagnostic_report.py \
    tools/jieli/diagnostic_flat.py tools/jieli/link-diagnostic-in-container.sh \
    tools/jieli/link-m5-in-container.sh tools/jieli/link-ramtest-in-container.sh
ssh -o BatchMode=yes "$HOST" "mkdir -p '$REMOTE/src' '$REMOTE/out'"
scp "$ARCHIVE" "$HOST:$REMOTE/source.tar.gz"
ssh -o BatchMode=yes "$HOST" "tar -xzf '$REMOTE/source.tar.gz' -C '$REMOTE/src' && docker run --rm --cgroup-parent=docker-batch.slice --cpus=4 --memory=4g --memory-swap=4g --env PROFILE='$PROFILE' --env BUILD_ID='$BUILD_ID' --label lan.project=lunar-modulator --label lan.session='$SESSION' --label project=lunar-modulator --label session='$SESSION' -v '$REMOTE/src:/src:ro' -v '$REMOTE/out:/out' -v '$TOOLCHAIN:/opt/jieli:ro' lunar-jieli-check:bookworm bash /src/tools/jieli/link-diagnostic-in-container.sh"
mkdir -p "$OUT"
scp -r "$HOST:$REMOTE/out/." "$OUT/"
echo "diagnostic artifacts: $OUT"
