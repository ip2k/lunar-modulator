# Browser selection for the Event Horizon companion set

The installer browser can now include the trusted Event Horizon companion SET alongside its required parent project. Event Horizon remains the default startup project. The browser exports the companion only when the user checks it, and the backend request requires the parent to be selected and remain the startup project. Empty set selection preserves the legacy request shape by omitting `set_ids` entirely.

The UI trusts only the catalogue entry `replacement-showcase-event-horizon-companion-set`, whose parent is `replacement-showcase-candidate-event-horizon`. Catalogue metadata is treated as untrusted: duplicate IDs, unknown IDs, malformed rows, missing parents, and any set metadata that indicates a scan or dependency uncertainty are rejected. The checkbox is accessible by its visible label, disabled until the parent is selected as startup, and cleared if that condition stops holding. The normal page explains that the accompanying set is optional and that build/install has not happened.

## Verification

- Focused Node tests: 31 passed across `native-demo-selection`, `native-demo-selection-view`, and `installer-build-client` tests in the bounded Hera Playwright container (Playwright image `sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27`; 4 CPUs, 4 GiB memory and swap, network disabled).
- Browser review: desktop 1440x1000 and mobile 375x812 passed with Chromium 153 / Playwright 1.63.0; no page or console errors, no horizontal overflow, and fonts loaded. Labels and controls remained separated in both layouts.
- Review used a fresh catalogue produced by `tools/native/export_image_catalogue.py`, SHA-256 `5737dd5b5ff5dd27e7c6545c242b94b05667d169f85764c99e9f253b8c4bda5c` (14,616 bytes). The captured request SHA-256 is `ef4ce3b330162abe9d4487c5b81bd170defa2c30cf0f00bca21f143f62da55f0`: it includes 13 engines, 23 selected effects (Plate deliberately deselected in the review), startup index 0, Event Horizon as its only project, and the trusted companion ID in `set_ids`.
- Browser report SHA-256 `94a36de5e168b36bcdd0484eb827c1fc4f93f37ffb75d425bfd83725736a621a`; desktop screenshot SHA-256 `54c6472f4968caa3555ecd93edd50f20ae8dcb58ba5636486dbcc79e611abc3e`; mobile screenshot SHA-256 `4d98de28889b450b1b0ed47db74a82854197bf1b38b7ca662c0174c66a0115ed`.

## Limits

This change only adds browser selection and request validation for a catalogue-known companion set. The browser review used a local mock and exported a request; it did not invoke the real build service or demonstrate runtime set activation. It does not change native chooser behavior, physical admission, hardware acceptance, or installability. The backend binds the SET to its parent and enforces startup selection; standalone SET startup remains unsupported.
