# tinf native wavetable decoder

https://github.com/jibsen/tinf at
`57ffa1f1d5e3dde19011b2127bd26d01689b694b`, zlib licence.
Unmodified tinflate.c/tinf.h and LICENSE, pinned in inventory.json.
Selected after the sixteen-profile evaluation in
notes/2026-10-12-native-engine-link.md. Used only for startup decompression
into fixed, bounded RAM; no audio-interrupt or render-time decoding.
Hostile capacity tests passed in the evaluation. Full application integration,
stack usage, startup timing and device rendering remain unverified.
