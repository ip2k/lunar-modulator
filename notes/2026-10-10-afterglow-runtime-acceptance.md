# Afterglow owner revision: runtime acceptance

This receipt covers the lower-footprint VA+Filter Macro candidate generated
from commit `25383aed0e22283a772e21029cd53661982672a4`. The Wasm and native
artifacts are the already-built combined four-song runtime, not a new engine
build. Their source identity is recorded separately from the changed project
assets.

## Results

- The actual Wasm module loaded all four generated projects without repair,
  skipped content or budget refusal. Afterglow used 54% of the simulated FM-1
  budget; the other projects used 67%, 54% and 67% respectively. Every song
  rendered its declared duration, stopped within 8 ms of its expected end,
  produced finite audio, and dropped zero sequencer events. The native renderer
  also loaded and completed all four; Afterglow used 233,384 bytes (61% in its
  native report) and dropped zero events.
- Chromium `153.0.8010.12` loaded each preloaded example, began playback,
  downloaded Save output, and reopened it in a fresh browser context with
  structurally identical project state. The report has no page errors.
- These are runtime, budget and file-workflow checks. They do not establish
  owner approval, resemblance to either target recording, hardware fit or
  listening quality. Owner re-listening remains the acceptance gate.

## Exact inputs and receipts

The Wasm SHA-256 was
`4667498f919529ba0f1059f127ea02e60c2c2a76ee5bc16983cfeabbb96b76ec`; the
native renderer SHA-256 was
`a17a9a3255dc80a88a528f4ba24ecf85d14852fb310cb8fc831314285ce4dda2`. The
browser checks used startup-repair source `5805ea9c` and pinned Playwright
image `eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27`,
under a 2-CPU/2-GiB `docker-batch.slice` limit.

Afterglow source and browser project SHA-256:
`493a2f77873cf830919a76afea7ad427fac78e283d563bfc699493b83f81523e`. Event
Horizon, Packet Bloom and Neon Transit retain their frozen Round 5 hashes
`5b92ad3d8e6448855b9cde032a935437331620819becbb206212f32845414897`,
`7d755fd777f1b0534c2518717e4bded475872db57f9596fe410d75606765e349`, and
`e19152d0747d6d2a69cc61eaabeed6d083f89fbecdfa7e1d85ba7f9911f6e251`.

The machine-readable native/Wasm report is
[`native-wasm.json`](evidence/afterglow-owner-revision/native-wasm.json),
SHA-256 `05b2595daa60725614a0279293b148492f1917cd4c42ff651e3d71242451ca1f`.
The browser Save/Open report is
[`chromium-save-open.json`](evidence/afterglow-owner-revision/chromium-save-open.json),
SHA-256 `e1e5b59df70a4e6c1568ea2172d8d52f8f2cec92f339db6316fc23427e9fd086`.
The captured Afterglow browser screenshot SHA-256 is
`8b3722310bd5aaaebdba8f3607358e2c1f7f013138cb320888cb39aa4661811f`.

Raw audio and screenshot files remain in the isolated aeon scratch directory
`/home/claude/mvave-fm1/afterglow-owner-2dd7186/output/`: native and Wasm WAVs
are `native-v2/afterglow-relay.wav` and `wasm-v2/afterglow-relay-wasm.wav`,
and the browser capture is `browser-v2/afterglow-relay.lunar.png`. Audio SHA-256
values are `6339692cfdd45c982f0c7622952b2dcc1eda91b00dc1d27f241845ef98168576`
and `6ddcda895f9f20912b52060a9c9d2a7356af9d6efa356717c17aeea8b725cbf7`.

The rejected intermediate Shapes candidate is retained in the preceding
owner-revision note: its actual Wasm load requested 394,696 bytes against the
387,924-byte budget (102%). The current Macro model stays under budget; this
does not prove target-device SRAM or CPU fit.
