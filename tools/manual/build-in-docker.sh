#!/usr/bin/env bash
# build-in-docker.sh -- build the manual, PDF included, in the same Ubuntu
# 24.04 environment as the Pages workflow (.github/workflows/pages.yml), for a
# machine without Pango (macOS without Homebrew's pango, for one).
#
#   tools/manual/build-in-docker.sh                 # -> _site/ (simulator, manual, PDF)
#   tools/manual/build-in-docker.sh /tmp/site       # somewhere else
#   tools/manual/build-in-docker.sh _site --only-manual
#
# Needs Docker. The tree is copied into the container, so the engines build
# there and nothing in the repository changes but the output directory. MIT
# licence.
set -euo pipefail

repo=$(cd "$(dirname "$0")/../.." && pwd)
out=${1:-$repo/_site}
[ $# -gt 0 ] && shift
mkdir -p "$out"
out=$(cd "$out" && pwd)
image=lunar-modulator-manual:ubuntu-24.04
commit=$(git -C "$repo" rev-parse HEAD 2>/dev/null || echo unknown)

# The image: the workflow's apt packages and manual/requirements.txt.
if ! log=$(docker build -q -t "$image" -f - "$repo/manual" 2>&1 <<'EOF'
FROM ubuntu:24.04
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3 python3-venv make g++ gcc libpango-1.0-0 libpangoft2-1.0-0 \
      libharfbuzz-subset0 fonts-ibm-plex rsync ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/manual && /opt/manual/bin/pip install -q -r /tmp/requirements.txt
EOF
); then
  echo "$log" >&2
  exit 1
fi

# The tree goes in and the site comes out as tar streams, so this works
# whatever directories Docker can mount (colima shares only $HOME).
tar_flags=()
if tar --version 2>/dev/null | grep -q bsdtar; then
  tar_flags=(--no-xattrs --no-mac-metadata)
fi
COPYFILE_DISABLE=1 tar -C "$repo" "${tar_flags[@]}" --exclude .git --exclude _site \
    --exclude 'engines/build*' --exclude scratch --exclude .venv --exclude reference -cf - . |
  docker run --rm -i -e MANUAL_COMMIT="$commit" "$image" bash -c '
    set -euo pipefail
    mkdir -p /tmp/work /tmp/out
    tar -xf - -C /tmp/work
    cd /tmp/work
    make -C engines -j"$(nproc)" >/dev/null
    /opt/manual/bin/python tools/manual/build.py --site /tmp/out --pdf --strict --no-make "$@" >&2
    tar -C /tmp/out -cf - .
  ' bash "$@" | tar -xf - -C "$out"
echo "manual: built into $out (open $out/manual/index.html)"
