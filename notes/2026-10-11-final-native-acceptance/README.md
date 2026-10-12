# Final native acceptance receipt [verified]

Test-only stage on Hera: `/home/claude/mvave-fm1/final-native-acceptance-f163c1`.
Branch `feature/2026-10-11@midi-sequencer-workspace`; input checkpoint `1141e12b5ea585d6be2dcbd71484d281e7d5e3b2` (parent verified pushed). Finish HEAD `d4e0b64019faa668a6eeae685777fe5587881e2f`. No source edits, commits, pushes, device access, or native rebuilds by this subtask.

Exact local and Hera final-e module SHA256 `f163c1b5799bb6109718993600df4c3f7884ffca055a2e4df558cc8007e65219`; metadata `fbd3d320`; telemetry v3, 1464 floats, append-only levels offset1454/mask119. Exact module-exported metadata equals staged static meta.json and agrees with existing final-e native metadata except expected pointer-width RAM fields. Metadata-query audio identity and zero import calls passed.

Node v22.23.3, Docker node:22-bookworm-slim, batch cgroup, 2 CPU / 2 GiB RAM / 2 GiB swap limit. Suites sequential; no redundant whole native builds. Scripts, exact test inputs, source-hash manifest, logs and metadata are retained in ignored `scratch/final-native-acceptance/stage/` in the managed worktree and in the Hera stage above. This tracked receipt preserves the measured results; reproduction uses the repository test scripts and the unchanged committed module.

- MIDI/parser/model:27 pass,0 fail/skip; includes hostile bounds, capacities, sustain, repeated notes, complete-tag and actual native model round trips.
- Export:WAV PCM16/24 and extensible8-channel bounds, backpressure/cancellation; exact-Wasm deterministic37598-frame fixture, native mix locks with stem gating, exact stem/interleave samples, track duration/isolation, MIDI-follow clock, external-route silence, oversized refusal, actual FM6/inserts/master/MIDI arp.
- Fresh exact-Wasm meter smoke:2048frames; enabled/disabled output bit-identical, unplayed sound rows zero, empty insert/master slots identity, post-fader level50% matches taps, final MASTER0.5 peak/RMS matches rendered samples with0.25 gain. Genuine sample measurements; no inferred track audio meters.
- Four catalog projects, extracted from commit `621490b9553b17f23add077f8dd79c01b5c15db8`: all hashes match prior accepted catalog candidates; all loaded cleanly, zero left_out/skipped/repaired, no import calls.

| Project | Chain RAM bytes | Native reported headroom | Headroom after additional60B meter debit |
| --- | ---: | ---: | ---: |
| afterglow-relay-showcase.lunar | 264184 | 123740 | 123680 |
| event-horizon-showcase.lunar | 158324 | 229600 | 229540 |
| packet-bloom-showcase.lunar | 294876 | 93048 | 92988 |
| satellite-hearts.lunar | 361260 | 26664 | 26604 |

Native chain budget387924B. These are exact `fm1w_ram` figures for the final module. `fm1_app_ram` counts DSP/sequencer/mod/MFX allocation and excludes attached edit-layer telemetry counters; therefore meter state does not change its displayed chain figure. The independent60B debit explicitly accounts for the appended five peak/sum/count counters and keeps all four within this chain bound. This does not establish a complete physical firmware SRAM layout, pi32v2 ABI, device latency, or hardware acceptance.

No browser interaction/listening or physical FM-1 test performed here; owner listening remains pending. Parent owns final browser/UI checks, CI, integration/merge and verified backup. Next step:parent review `receipt.json`, incorporate the results in its durable integration receipt, and continue required gates. If shared test JS changes again, rerun affected tests; unchanged module SHA remains the exact native target.

Reproduction in stage (inside bounded Node container):

```sh
node --experimental-default-type=module test/midi-import.mjs www
node --experimental-default-type=module test/audio-export.mjs --wasm /work/www/fm1.wasm
node --experimental-default-type=module test/meta.mjs --wasm www/fm1.wasm --native meta-native.json --out module-meta.json --summary meta-summary.json
node --experimental-default-type=module budget.mjs
node --experimental-default-type=module meter-check.mjs
```
