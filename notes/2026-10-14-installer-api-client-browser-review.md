# Installer API client browser review

The installer can now accept an explicitly injected same-origin diagnostic-build client. With no client configured, the page keeps the existing offline JSON-export workflow. The client posts the selected version-1 request to `/api/v1/builds`, validates the opaque same-origin status route, polls within a bounded deadline, and accepts only a bounded receipt with a valid SHA-256, byte count, `installable: false`, and `hardware_tested: false`. It does not fetch or offer artifact bytes. “Stop waiting” cancels this browser's active fetch/polling; the service has no job-cancellation endpoint, so the server may continue the job.

Before any network call, requests must be plain objects with the exact version-1 keys, 1–8 ordered project IDs, valid unique selections, a nonempty engine list, and a UTF-8 JSON body no larger than 64 KiB. JSON responses are consumed through a streamed reader with a 64 KiB cap; the overall timeout includes the body read. This avoids unbounded `response.json()` fallback behavior.

## Checks

- `node --test sim/web/test/installer-build-client.test.mjs sim/web/test/installer-page.test.mjs`: 13 tests passed. Coverage includes request ordering, malformed/remote status URLs, failure responses, receipt overclaims, request schema/size, response stream size, timeout during a stalled response body, and cancellation.
- `git diff --check`: passed.
- Browser run used pinned `mcr.microsoft.com/playwright:v1.63.0-noble`, immutable digest `sha256:eff16c30e6f3f4af0a3fa4b706120d5e9b0891c344a27d64559aff5900a4a27`, with 2 CPUs, 3 GiB memory and swap cap, no network, read-only root and task labels. A loopback static server and Playwright stub exercised explicit submission, queued/running/succeeded states, cancellation, and 422 rejection. The selected module and project order reached the API stub; Event Horizon was selected as startup, the deselected `plate` effect was omitted, the UI showed the diagnostic-only receipt, and no artifact download was attempted.
- Desktop 1440×1000 and mobile 375×812 screenshots show no horizontal overflow or visible label collisions; the full-song default remains pending. Both were inspected after rendering.

Browser report and screenshot artifacts are in `notes/2026-10-14-installer-browser-review-v2/`. Report SHA-256: `dff2498fe72497de4518d5c893df8d000befaaff0ac0b68f3e2dd8e948018eaa`. Desktop screenshot SHA-256: `45b17fbd553bb58eaafa93c29ec189b8d497a0c31370a161512c3008e2690560`. Mobile screenshot SHA-256: `85dcb8ae668123e0454892e38e176a91a49b265aceb3293ed95bf3bf15b78217`.

This is browser/client integration evidence against a local response stub. It does not verify a deployed service, run the actual image builder, validate packed dependencies, admit any project as a release default, or establish device playback, save/reload, installation, or musical acceptance. Full-song default status remains pending, and server job cancellation remains unsupported.
