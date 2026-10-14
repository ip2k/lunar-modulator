# Event Horizon full-song proposal preselection

The installer chooser now starts with the `Event Horizon Showcase` replacement candidate selected as the proposed full-song default. This changes a reversible private chooser preference only. It does not set `default_candidate`, approve musical acceptance, or mark a catalogue or package installable.

Before: the catalogue recorded Event Horizon as a 108.8-second host-rendered replacement candidate, while the installer selection started empty. A user could not see the proposed full-song default in the chooser without manually selecting it.

After: when the catalogue marks the full-song default `pending`, the chooser preselects the matching replacement showcase candidate and its startup radio option. It labels the status as pending, explains that the choice is reversible and not acceptance/admission, and preserves the separate pending packed-dependency and musical review gates. The duration label remains an estimate from project metadata; the status callout distinguishes the 108.8-second offline host render. Legacy examples remain selectable with the current host startup dispositions shown: Afterglow Relay and Packet Bloom passed their host diagnostic; Event Horizon and Neon Transit were refused allocation (report 5). None is advertised as hardware-playable or release-approved.

The browser acceptance script mounted the production installer page against a loopback server in isolated Playwright 1.63.0 / Chromium 153, using image digest `sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27`. At desktop 1440×1000 and mobile 375×812, the proposal and startup option were selected, the pending/admission language was visible, and there was no horizontal overflow or console/network error. The desktop scenario added Packet Bloom, selected it as startup, and downloaded JSON preserving Event Horizon then Packet Bloom with `startup_index: 1`; the export stated that no build/install was performed and contained no acceptance flags. Receipt records:

- Browser report: `notes/2026-10-14-event-horizon-default-browser-review/installer-default-browser-report.json` (SHA-256 `eb01d1894c187df62f1f53690a4a92993833127d490ca1cbf5d0ecda18b09149`).
- Desktop screenshot: `notes/2026-10-14-event-horizon-default-browser-review/installer-desktop.png` (SHA-256 `5079ff53a722784f10a4ea47c9105e97732648e74e70effd8540e0135dff00f3`).
- Mobile screenshot: `notes/2026-10-14-event-horizon-default-browser-review/installer-mobile.png` (SHA-256 `0ce93307620cd63e6e4039663f11243926df4e201412238f94b1ca0ce7989cc9`).
- Downloaded request: `notes/2026-10-14-event-horizon-default-browser-review/installer-request.json`.

Focused selection, installer, and build-client tests passed (24 tests total after adding client cleanup cases). The client now fires stream cancellation without awaiting it on oversize or abort and releases the reader lock in `finally`, so a stalled stream cleanup cannot defeat the bounded request timeout. Two tests cover stalled-cancel oversized and abort streams.

This evidence is browser behavior and host-render evidence only. It does not validate the packed module dependencies, target playback, save/reload on hardware, owner musical approval, or release admission. All catalogue admission flags remain false/pending.
