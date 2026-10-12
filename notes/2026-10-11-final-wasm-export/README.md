# Final Wasm exporter and showcase RAM receipt

[verified] Exact final module SHA256:
`b98e8e3295dba072a65d2d49bd5e1b3d57afc63ce2b2aa33027202e1d7c8c258`.
Independently matched the shared DAW worktree and isolated Hera copy.

On Hera (`claude@192.168.1.48`), isolated stage
`/home/claude/mvave-fm1/audio-export-final-b98e`, two sequential
`node:22-bookworm-slim` Docker jobs used `docker-batch.slice`, 2 CPU,
2 GiB RAM/swap ceiling each. No services, infrastructure or live audition
assets were changed. Node invoked with `--experimental-default-type=module`.

Commands inside the stage:
```
node test/audio-export.mjs --wasm /work/www/fm1.wasm
node budget.mjs
```

[verified] Export regressions passed: PCM16/24 WAV encoding, bounds,
clipping, multichannel extensible header/discrete channel interleave,
stream backpressure, worker cancellation/cleanup, deterministic actual-Wasm
finite song (37,598 frames), unused sound silence, sound contribution gate
under mix automation, track isolation and matching transport lengths,
saved MIDI-follow clock preference, FM6/inserts/MIDI arp/modulation/master
effects, and master volume behavior. Full assertions are in
`sim/web/test/audio-export.mjs`; raw result is `export.log`.

[verified] Fresh final-Wasm instances loaded all four exact merged catalog
projects without repair, omission or unsupported import. Strict native RAM
budget is 387,924 B:

| Project | RAM B | Headroom B |
| --- | ---: | ---: |
| Afterglow Relay | 264,184 | 123,740 |
| Event Horizon | 158,324 | 229,600 |
| Packet Bloom | 294,876 | 93,048 |
| Satellite Hearts | 361,260 | 26,664 |

`budget.log` records each exact asset SHA256 and complete native load report;
`budget.mjs` is the reproducible assertion. These are project-load/RAM checks,
not new complete-song renders on the final module.

Receipt SHA256:
```
b0816bb018d1747e875e5b84c4024e5dd4ed011a18ba93057cb382a795ed166b export.log
0e7c558497c034795327ead3a7c5a7d7c30d4e2e575da4296a6f6bd1cbcde7b8 budget.log
3538ed1185b688cef5f9d7d2aff71b9a934da9f69e3ef0495cae9a9c4559425a budget.mjs
6d1815a2bf97a455c1e8d00ce370b7d86c251e09b5104a19d9a745fb3cd2e486 test/audio-export.mjs
1078b0765f80d69672f3070e096b697c939508030e369a7400a9ba6d69893131 www/editor/render.worker.js
227649638b3b12a70bc89440504b1b92d0ffedd4f83d81b57daa10b9bdda3e97 www/editor/sequence-model.js
```

Catalog integration: PR #145 merged after all 13 exact-head PR CI jobs
(38195484726) and Pages build (38195484727) passed at
`fb92cc0d4c312bbc77866c915d6fb8f159f5f92d`.
Merge `621490b9553b17f23add077f8dd79c01b5c15db8` verified equal remote main;
source branch remains backed up. Parent owns DAW receipt checkpoint/push,
browser validation, required CI, merge and deployment.

Acceptance limits: all four showcase projects remain pending owner listening
approval. No reference audio listening or hardware acceptance is claimed.
The separate Acid amplitude sustain/release feature remains unresolved.
