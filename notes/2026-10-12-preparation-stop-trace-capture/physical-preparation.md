# Physical file-only preparation, 2026-10-12

[verified: passive host evidence] The FM-1 remains bus1/device10, 4c4a:8057
WL80UBOOT1.00. No power cycle, USB request, SG open, capture process, loader
upload, flash operation or reset was performed in this preparation.

`prepare-file-only-v1.py` was syntax checked and executed once as nonoptimized
Linux root on bench01. It copied the previously modeled capture sources, checked
their original 292-member manifest, replayed genuine V7 preparation-stop proof,
compared passive sysfs USB/SG mapping to the unchanged historical snapshot,
prepared the real canonical five-read factory and checked the bound wrapper's
297-member packet inventory. It never invoked either execution entry point.

Private stage: `/home/claude/fm1-stop-trace-capture-v1-20261012`.
Observed at 1791846277.3010914; witness expired at 1791846397.3010914.
**This packet is expired. Do not execute it, refresh its witness in place, or
replay the consumed original automatic chain.** A later attempt needs its own
reviewed new packet and separate fresh unchanged connection observation.

Pins [verified]:

- Historical snapshot: `9afba13c12303476e2d6a9744eb43991ce81781437c45fdfcad5b9054f2b9b8d`
- Bound native: `87fc67951e564a7ba6d551044812bc89b67e4fc3978e7555988e6f53ebaa0cb8`
- Campaign: `fe163a6aae7195d5eeb8388942f3b491ab46fa614d1504955cc146d77372654c`
- Stop envelope: `9abc4264bbb20a7392495ea8aa63919e03e2ccb3d89e06dc169b9c75c2324a3d`
- Wrapper: `1df3f98f1afccfbaec12090411aad70d68a12a09625524aa8c9f03cf95b04288`
- Child: `68b9a50e1971a5f040fdea1fddda5f4e14a2269319f0b0662388eaed8c580215`
- Packet inventory: `65d15f2e0c553d044a3880d70eb6dfec260df1fff7fe0834fe7ce648cbafd26f`

Local preflight retained at
`build/preparation-stop-trace-physical-v1-20261012/capture-preflight.json`.
Only the concrete PROOF_SOURCE_SHA literal changed in the copied native reader;
tracked production activation remains closed. Historical V7 evidence was not
changed. macOS tar metadata generated ignored extended-header warnings; exact
file hashes, not archive metadata, were the acceptance check.

[verified: current tool results] Cynthion r1.4 serial2a4950df30c460de is detected,
but cynthcap cannot claim its interface (exclusive-access error0xe00002c5).
Computer-use getApp still returns Mac locked/automatic unlock unsuccessful;
there is no Packetry window or click verification. Owner was told no physical
cycle is needed and normal Packetry capture stop/quit should release access.
Do not force-kill or power-toggle the device to resolve capture ownership.

CI38319820698 for08f43679 remains pending behind38318696095 (10 successful jobs,
Linux/macOS tests and sanitizer job still running). Prior38319511427 was
cancelled, not green. Capture models passed56 checks in16 Hera chunks earlier;
neither those models nor this file-only preparation prove actual RAM replies,
diagnostic boot/display, full current stock restoration or Cynthion capture.

Next: source CI/review and capture access; prepare a distinct fresh packet and
perform one bounded trace preservation before the overlapping RAM loader.
The loader-backup guard requires explicit post-read successor admission;
never bypass that by removing the consumed marker. Continue recovery and
physical boot/display acceptance before completing the installable-image goal.
