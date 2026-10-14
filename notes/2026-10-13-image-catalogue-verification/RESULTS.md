# Production image catalogue verification

## Production catalogue export (2026-10-13) [verified]

`python3 tools/native/export_image_catalogue.py` emits JSON for browser builder
choices and a version-1 default profile accepted by the existing profile format.
It resolves the canonical Make catalogue twice: once to enumerate all available
modules, then to generate the production default header. Test-prefixed module
IDs remain available for developer builds but are excluded from these choices.
The current export contains thirteen sound engines, 24 audio effects, two MIDI
modules and sixteen modulation modules. Content starts empty; songs/sets are
added through profile preparation. Output records the catalogue and default
header SHA256, and leaves installation/link/RAM/hardware acceptance false.

Thirty independent Hera containers passed the full-default request and 29 mixed
requests through the real catalogue. Terminal exit states were zero, with no OOM.
The six source hashes recorded on Hera match the current worktree. CLI output
from Hera matches local output byte-for-byte. Source was mounted read-only,
network disabled, and containers ran as UID 1001 in docker-batch.slice with one
CPU and 256 MiB each. Campaign/source/export receipts and the launcher are in
`notes/2026-10-13-image-catalogue-verification/`; detailed logs remain on Hera at
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/image-catalogue-v1/`.

This completes the catalogue export backend part of implementation step 1,
not the browser UI or a build service. It does not assess source-revision
admission, component licensing, selected image footprint, content semantics,
native timing or physical recovery. Next connect the export to browser profile
selection, then retain existing prepared-input integrity and per-image gates.
