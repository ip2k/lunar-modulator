#!/usr/bin/env bash
# engines/third_party/airwindows/oracle/run-on-aeon.sh -- the reference
# renders for Squash and the Limiter's Round mode, made on a Docker host:
#
#   FM1_SIM_HOST=user@host engines/third_party/airwindows/oracle/run-on-aeon.sh
#
# Writes the reference signals and the cases with this machine's
# fm1-squash-test (our own code: make -C engines first), copies them and
# airwindows_oracle.cc (the Airwindows loops in double) to the host, builds
# and runs the oracle in the gcc:12 container there, brings the renders back
# to engines/build/airwindows-oracle/ and writes
# tests/fixtures/squash-oracle.json from them (make_fixture.py, every 61st
# frame). The oracle never runs on this machine. Environment: FM1_SIM_HOST
# (required), FM1_REMOTE_DIR (default ~/mvave-fm1/airwindows-oracle there).
# MIT licence, like the rest of this repository; airwindows_oracle.cc carries
# Airwindows' notice.
set -euo pipefail
export COPYFILE_DISABLE=1

IMAGE=gcc:12
HOST="${FM1_SIM_HOST:?set FM1_SIM_HOST=user@host (a Linux machine with Docker)}"
REMOTE=${FM1_REMOTE_DIR:-$(ssh "$HOST" 'printf %s "$HOME"')/mvave-fm1/airwindows-oracle}
ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
HERE=$ROOT/engines/third_party/airwindows/oracle
OUT=$ROOT/engines/build/airwindows-oracle

rm -rf "$OUT" && mkdir -p "$OUT"
"$ROOT/engines/build/fm1-squash-test" --dump "$OUT"

echo "== staging on $HOST:$REMOTE"
ssh "$HOST" "rm -rf '$REMOTE' && mkdir -p '$REMOTE'"
tar -C "$OUT" --no-xattrs -cf - sig0.f32 sig1.f32 sig2.f32 cases.txt | ssh "$HOST" "tar -x -C '$REMOTE'"
tar -C "$HERE" --no-xattrs -cf - airwindows_oracle.cc | ssh "$HOST" "tar -x -C '$REMOTE'"

DIGEST=$(ssh "$HOST" "docker image inspect --format '{{index .RepoDigests 0}}' $IMAGE 2>/dev/null || docker pull -q $IMAGE")
echo "== $DIGEST"
ssh "$HOST" "docker run --rm --label project=mvave-fm1-firmware --label session=airwindows-oracle \
  -v '$REMOTE':/w -w /w $IMAGE sh -c '
    g++ -O2 -std=c++11 -ffp-contract=off -o oracle airwindows_oracle.cc &&
    while read name kind sig a b c d e f g h; do
      ./oracle \$kind \$a \$b \$c \$d \$e \$f \$g \$h < sig\$sig.f32 > \$name.oracle.f32 || exit 1
    done < cases.txt'"
ssh "$HOST" "cd '$REMOTE' && tar -cf - *.oracle.f32" | tar -x -C "$OUT"
echo "$DIGEST" > "$OUT/image.txt"
python3 "$HERE/make_fixture.py" "$OUT" "$ROOT/tests/fixtures/squash-oracle.json"
