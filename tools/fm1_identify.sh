#!/usr/bin/env bash
# Read-only identity query for an M-VAVE FM-1 over ALSA raw MIDI (Linux).
#
# Sends the ten-byte query the official updater uses and prints the reply.
# Nothing else is sent. Verified on hardware 2026-10-26 (stock V15, FM-1_015;
# docs/17 §7). The byte sequences come from aroum/fm1-custom-fw and
# AL-255/FM-1-RE, which captured them from the official updater.
#
# Expected reply (41 bytes): F0 00 32 45 58 01 00 00 23 4D 5A 44 ... F7; the
# tail varies by version (FM-1_015 ends 00 20 06 F7). The identity is the
# plain MODEL_NNN field; decode a saved reply with
# `fm1_identify.py --decode-file`.
#
# Raw MIDI is unavailable while PipeWire/JACK/aseq clients hold the port. If
# amidi reports "Device or resource busy", stop them for the session or use
# AL-255's sequencer-based client:  python3 FM-1-RE/tools/fm1_ota.py scan
#
# Usage: tools/fm1_identify.sh [hw:X,0,0]
set -euo pipefail

QUERY='F0 00 32 45 00 00 00 40 7F F7'

if ! command -v amidi >/dev/null; then
  echo "amidi not found (install alsa-utils)"; exit 1
fi

PORT="${1:-}"
if [ -z "$PORT" ]; then
  PORT=$(amidi -l | awk 'tolower($0) ~ /fm-1/ {print $2; exit}')
fi
if [ -z "$PORT" ]; then
  echo "No FM-1 MIDI port found. Ports:"; amidi -l; exit 1
fi

echo "port: $PORT"
echo "sending: $QUERY"
# -S sends the hex bytes, -d dumps incoming bytes, -t stops after N seconds of silence.
amidi -p "$PORT" -S "$QUERY" -d -t 3
