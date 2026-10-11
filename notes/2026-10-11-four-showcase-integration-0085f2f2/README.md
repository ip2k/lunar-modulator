# Exact four-showcase integration receipt

Tested source commit `0085f2f24efa3beb1af81e1a9519f4471b87c537` on `chore/2026-10-10@demo-song-acceptance`. Isolated stage on both hosts: `/home/claude/mvave-fm1/four-integration-0085f2f2`. The live owner audition server and its Satellite asset were untouched.

- aeon `192.168.1.25`: current aggregate manifest passed full four-song Wasm and native acceptance (`aeon-runtime.json`).
- Hera `192.168.1.48`: actual independent Docker four-song Wasm acceptance passed (`hera-runtime.json`), node:22-bookworm-slim, `--cgroup-parent=docker-batch.slice --cpus=2 --memory=2g --memory-swap=2g`, UID 1001. No infrastructure modifications.
- aeon Chromium 153.0.8010.12 / Playwright v1.63.0-noble: current permanent catalog passed listing, playback-start, download, and fresh-context reopening for all four (`browser.json`). No browser errors. Satellite screenshot inspected: loaded name and RAM 92% visible, no clipped/overlapping labels observed.

Both runtime receipts identify aggregate manifest SHA256 `e073c6bdb4a8bf4f49525a49b1f63dfdc611cc41d40ded5d6c364ab92219294f` and cached module SHA256 `4667498f919529ba0f1059f127ea02e60c2c2a76ee5bc16983cfeabbb96b76ec`. Native renderer reused from worklet-ready-final-c44a808 (SHA256 `a17a9a3255dc80a88a528f4ba24ecf85d14852fb310cb8fc831314285ce4dda2`); no engine changes or new engine-build claim. Native and Wasm output assertions passed; all four show zero dropped events and successful serialization round trips. Full-song durations: Afterglow 101.54s, Event 108.80s, Packet 117.07s, Satellite 116.13s. Exact asset hashes are in runtime receipts and composition plans.

Local `showcase_songs.py --check`, legacy `demo_songs.py --check`, and catalog/harness node syntax checks passed. GitHub workflow dispatched for source HEAD: https://github.com/ip2k/lunar-modulator/actions/runs/38161344693 (completion tracked separately). These checks do not establish reference listening, owner musical acceptance, FM-1 hardware behavior, or new Acid amplitude sustain/release functionality.
