# Installer flash usage verification — 2026-10-14

## Result

[verified] Exact checkout source base `fe68943929494ea781075dbd40d53de693983a96` was browser-tested on isolated Hera branch `codex/2026-10-14-flash-usage-browser-review`. This task changed only the browser-review test helper and this note. The build-review helper now explicitly deselects the proposed Event Horizon before selecting Packet Bloom then Event Horizon, so the tested request order and startup index are deliberate. The separate default-browser-review helper still verifies Event Horizon remains proposed and selected by default.

The installer accounting rendered identically at desktop (1440x1000) and mobile (375x812): `Diagnostic build checks passed. Application flash: 785,312 / 868,836 bytes used; 83,524 bytes free. No installable firmware file is available.` Neither viewport overflowed. This is a synthetic successful diagnostic API response in browser tests, not a fresh controller build or firmware admission.

The installer service test suite passed in the pre-existing Hera task venv: 46 passed, 1 skipped (opt-in retained-build case; `LUNAR_RETAINED_BUILD` unset). Runtime versions recorded for that environment: FastAPI 0.143.0, Pydantic 2.14.1, HTTPX 0.28.1 and pytest 8.4.2; Starlette emitted a deprecation notice for its TestClient integration.

## Browser runs and artifacts

Both scripts used Playwright 1.63.0 from `/home/claude/mvave-fm1/ci-sync-review-069333/pw/node_modules` and pinned image `mcr.microsoft.com/playwright:v1.63.0-noble`, digest `sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27`. Docker was run inside the user `docker-batch.slice` with `--network=none`, 4 CPUs, 4 GiB memory and swap, 256 PIDs, and label `codex.task=lunar-flash-usage-browser-review`.

The input site was staged read-only from `sim/web/www` at the tested checkout. Its catalogue fixture was reused from `/home/claude/mvave-fm1/installer-api-review-v2-20261014/site/demo-image-catalogue.json`, SHA-256 `908ed8bc7be25507b297f8cdd7ceb99213a5a37a2b8c6b04f34d85440cb1dd60`. It is an older generated fixture, not regenerated from this checkout. Browser API requests were stubbed; neither browser test establishes service deployment, a real build, linker budget, or firmware installability.

The committed build-review helper has SHA-256 `f9ac403f01a9c4157aa9b6e111e0adb0128d911ddda21db2d826d5a741da6cd7`; exact committed script completed desktop/mobile success, cancel-wait and request-rejected scenarios with zero browser errors. Both success requests ordered Packet Bloom then Event Horizon, startup index 1, excluded the plate effect, and had no artifact download. Report SHA-256: `4df4558a117edb32fee6210eaebb0003df269a48e026bb4de6a407c0ea802a30`.

The separate committed default-review helper SHA-256 is `7f172c942c20e673e21ee0d24fc4ccabf1e69ffb5888a3facb52f0f376862d5b`; it confirmed the candidate remains proposed, full-song status pending, catalogue non-installable, and download request preserves the startup choice. Desktop/mobile had no horizontal overflow. Report SHA-256: `eb01d1894c187df62f1f53690a4a92993833127d490ca1cbf5d0ecda18b09149`.

Private retained browser outputs are under `/home/claude/mvave-fm1/flash-usage-browser-review-fe689439-v2/`:

- Build review JSON: `out-build/installer-build-browser-report.json` (SHA-256 `4df4558a117edb32fee6210eaebb0003df269a48e026bb4de6a407c0ea802a30`)
- Build review screenshots: `out-build/installer-desktop.png` (SHA-256 `490087e609e511051ec5a06efa9ab9a6ec6eb1d95be4d3d09b76bfd91cf64e10`); `out-build/installer-mobile.png` (SHA-256 `16ea11132b78a8ca900615eea76af1a93a3fa631afac63be0d7dd3203cf1a11c`)
- Default review JSON: `out-default/installer-default-browser-report.json` (SHA-256 `eb01d1894c187df62f1f53690a4a92993833127d490ca1cbf5d0ecda18b09149`)
- Default review screenshots: `out-default/installer-desktop.png` (SHA-256 `5079ff53a722784f10a4ea47c9105e97732648e74e70effd8540e0135dff00f3`); `out-default/installer-mobile.png` (SHA-256 `0ce93307620cd63e6e4039663f11243926df4e201412238f94b1ca0ce7989cc9`)

## Limits and next step

The screenshots and report record UI behavior against a stubbed example response; the 785,312-byte app size and 868,836-byte budget do not prove fresh build measurements. The generated catalogue fixture predates the tested source. There was no public listener, deployment, hardware, network service or firmware install.

Coordinator should inspect the four retained screenshots before accepting visual review, then back up the returned branch commit to GitHub. Parent's next follow-up is separate research/planning for selectable embedded preloads on the native device; investigate cold reinitialization, audio quiescence and rollback safety before changing production code.
