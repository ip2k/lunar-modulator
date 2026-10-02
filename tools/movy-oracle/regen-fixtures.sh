#!/usr/bin/env bash
# Regenerate tests/fixtures/movy from its scripts with the Movy oracle on aeon.
#
#   tools/movy-oracle/regen-fixtures.sh
#
# For every <stem>.verbs: <stem>.jsonl (Movy's events, block-start frames)
# and <stem>.out.movy1 (Movy's export after the run). For scripts carrying a
# "# D1 trace:" comment, also <stem>.d1.jsonl (each tick at its own frame).
# oracle-summary.jsonl lists each run's length and any panic Movy caught.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
fx="$(cd "$here/../../tests/fixtures/movy" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

"$here/run-on-aeon.sh" --movy1 "$fx" "$tmp/block"
"$here/run-on-aeon.sh" --frames tick "$fx" "$tmp/tick"

for script in "$fx"/*.verbs; do
    stem="$(basename "$script" .verbs)"
    cp "$tmp/block/$stem.jsonl" "$tmp/block/$stem.out.movy1" "$fx/"
    if grep -q '^# D1 trace:' "$script"; then
        cp "$tmp/tick/$stem.jsonl" "$fx/$stem.d1.jsonl"
    else
        rm -f "$fx/$stem.d1.jsonl"
    fi
done
cp "$tmp/block/summary.jsonl" "$fx/oracle-summary.jsonl"
echo "regenerated $(ls "$fx"/*.verbs | wc -l | tr -d ' ') fixtures in $fx"
