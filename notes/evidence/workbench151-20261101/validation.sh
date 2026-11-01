#!/bin/sh
set -eu
cd /work
mkdir -p scratch/pause151 /pw
cd /pw
npm install --no-save --no-audit --no-fund playwright@1.63.0 >/dev/null
cd /work
apt-get update -qq
apt-get install -y -qq pulseaudio pulseaudio-utils >/dev/null
pulseaudio --system -n --disallow-exit --exit-idle-time=-1 --load='module-null-sink sink_name=lunar rate=48000 channels=2 norewinds=1' --load='module-native-protocol-unix auth-anonymous=1 socket=/tmp/pa.sock' -D
export PULSE_SERVER=unix:/tmp/pa.sock PULSE_SOURCE=lunar.monitor BROWSER=webkit PLAYWRIGHT_DIR=/pw

cp baseline-sequencer.js sim/web/www/editor/sequencer.js
if node sim/web/test/sequencer-ui.mjs sim/web/www scratch/pause151/red > scratch/pause151/red.log 2>&1; then
 echo 'ERROR: regression unexpectedly passed old source'; exit 1
fi
grep 'Immediate transport actions disabled or blocked one another' scratch/pause151/red.log
cp fixed-sequencer.js sim/web/www/editor/sequencer.js
for BROWSER in webkit chromium firefox; do
 export BROWSER
 node sim/web/test/sequencer-ui.mjs sim/web/www scratch/pause151/green-$BROWSER
 node sim/web/test/compact-toolbar-check.mjs sim/web/www scratch/pause151/toolbar-$BROWSER
done
node --test sim/web/test/sequencer-host.test.mjs sim/web/test/song-shortcuts.test.mjs
