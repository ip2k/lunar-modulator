# Event Horizon Showcase musical-default approval

Owner approval on 2026-10-14 makes Event Horizon Showcase Lunar's default full-song choice. The production preload catalogue identifies that choice and the chooser preselects it as startup. Approval covers the composition choice only.

The catalogue keeps default_candidate false, production default_profile.content empty, and image-installability, native-link, RAM, hardware-test, and project-admission gates unchanged. Exact packed-content/module validation and native target playback plus save/reload acceptance remain blockers. Existing memory reservations are unchanged: Event Horizon and Afterglow Relay report allocator fit with device playback unverified; Packet Bloom and Satellite Hearts remain rejected under the current profile. The 108.8-second render remains offline diagnostic evidence only.

The private Chromium review exercises the selected Event Horizon default, adds the other allocator-fit showcase (Afterglow Relay), changes startup order, and exports JSON without admission flags. Packet Bloom was not used for that interaction because the current reservation rejects it and the UI disables it. Review report: /home/claude/mvave-fm1/event120-default-approval-browser-20261014/artifacts/installer-default-browser-report.json SHA-256 9a079119590a271f4d7cca5b89e6ac3693ab3da42466ed4e3d3aaf5d46a53eee; desktop/mobile screenshots SHA-256 5a3ae36a5b1a9dc5ddf84d255405960d5c7b98999df1d2d68a04101f593ad7ad and 7f78af0bda0255b07ae405cb08ca7bd66e5a51aa23b0aad593d8ee606a0e04e5. Browser result: no console/page/network errors, no horizontal overflow, request has no acceptance flags, catalogue remains non-installable, and default_candidate remains false. The review used a loopback static site in a bounded offline container, not the live build service.

Checks on the isolated Hera branch:
- Python catalogue tests: 33 passed in pinned lunar-preload-tests:20261014 with mounted pytest dependencies and read-only bare-repository mount.
- Focused chooser/page JavaScript tests: 9 passed in bounded node:22-bookworm-slim.
- Chromium browser review: passed in pinned lunar-playwright-audio:1.63.0; desktop/mobile screenshots visually inspected.
- Python py_compile and git diff --check: passed.

No device, publication, or install operation was performed. Serena and Rarefaction remained selected to the coordinator Mac checkout, not this isolated Hera worktree; no shared/global project retargeting was attempted.
