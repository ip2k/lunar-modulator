# Simulator artifact refresh (2026-10-14)

Rebuilt the committed browser simulator artifact from the exact CI source base 064a2c075c881ca687791c89f63d0a3f539aaf96 in an isolated Hera worktree. This is an offline generated-artifact refresh; it changes no simulator or engine source and is not device/hardware acceptance.

## Inputs and reproducibility

- Checkout: /home/claude/.local/share/codex-worktrees/lunar-sim-artifact-refresh, branch codex/2026-10-14-sim-web-artifact-refresh.
- Source hashes from python3 sim/web/tools/source_hash.py: engines 19c442539b63717c76d364c3635f6fe3ecbb5b9db85771584243c369c6e08c58; simulator 1308136e6689a2c25c654f719d609ccb3950b1b44d7e5aeed433af47b502c746.
- Emscripten image: emscripten/emsdk:6.0.10, immutable digest sha256:e077d54e2b8970575ebc4f185ac1de0b95c05f2b266134d4ba27449af7aebf65.
- Musl image: alpine:3.22, immutable digest sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8.
- Both containers ran under docker-batch.slice with --cpus=4 --memory=8g --memory-swap=10g for builds; pytest used 2 CPU / 2 GiB memory / 3 GiB memory+swap. Each had project/session labels. The pinned digest pair recorded in fm1.wasm.json is the complete recipe input.
- Recipe: existing musl targets from sim/web/mk/sim.mk with EXTRA=-static, then bash sim/web/build.sh, with FM1_GPL_MODS=1 and ENGINES_REF=064a2c075c881ca687791c89f63d0a3f539aaf96. Build log: /tmp/lunar-sim-artifact-refresh-build.log on Hera.

## Results

- sim/web/www/fm1.wasm: 1,570,238 bytes; SHA-256 a214fe84ee2f88454da634e27f5a400e5ead0559d1279ed9c44fc78c03f994fa.
- sim/web/www/fm1.wasm.json: SHA-256 1f44b0f42b7c8337f2ce299677c2356383bf636741053bdf05c8d52659fcf080.
- sim/web/www/meta.json: SHA-256 9f6695ffcd0bf8741de0dbde9334c1249e0e746fa0dfe272cc9571418cb5e5fe.
- sim/web/build/parity.json: SHA-256 b433f64904f1aadc45b0bf32f5f77b88186e641d333dbf133a9a39194a3cf7be (generated evidence, not committed).
- Wasm parity: 108 passed, 0 failed; identical to JS and musl for all 108 scenarios, identical to glibc for 105 of 108 (the existing three libm-sensitive scenarios are intentionally excluded from exact glibc parity); zero imports.
- DX7 SysEx checks: 18 passed, 0 failed. Metadata identity/export checks passed. Edit-layer parity passed; 30-second edit storm: 10,341 quanta, 0 late, 0 resync, 0 fails.
- Focused test in the pinned Emscripten container with ephemeral pytest install: python3 -m pytest -q tests/test_sim_web.py -k committed_wasm_matches_its_build_record => 1 passed. The checkout was mounted read-only; pytest emitted only a cache-path warning because it could not write .pytest_cache.

The artifact record was produced by the repository's generator after all checks, not edited to force the source hash. No browser screenshots were captured; UI review is outside this refresh. No hardware, USB, MIDI, flash, power, or reboot operations occurred.
