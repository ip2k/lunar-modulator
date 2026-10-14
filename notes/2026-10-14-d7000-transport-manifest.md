# D7000 offline transport-profile support — 2026-10-14

## Change and evidence

[verified] `tools/native/expanded_transport_manifest.py` now accepts an explicit `flash_layout`, retaining `expanded-d9000` as its backwards-compatible default. It derives the named profile and application budget from the requested layout, revalidates the raw image geometry against that layout, and constrains changed sectors and the protected suffix to its end address. The returned manifest records both the profile and `flash_layout`; admission, installability, SAVE, hardware, recovery, and device-I/O values remain false.

[verified] `tools/native/expanded_ram_stream_model.py` can consume an explicitly named D7000 manifest and serves only changed 4 KiB sectors below `0xD7000` in bounded 512-byte pulls. The model verifies the full raw baseline and target, canonical manifest hash, changed-sector list, directory-last order, and identical protected suffix. It still has no device, transport, or flash writer. For compatibility, an older schema-1 D9000 manifest may omit `flash_layout`; D7000 manifests must provide it and match their profile.

[verified] The focused tests cover D7000 candidate/receipt geometry, rejecting a layout mismatch and changed protected-tail byte, serving the final D7000 application sector, and rejecting a D7000 manifest without explicit layout. The D9000 default and its existing tests remain in the same focused suite.

## Validation and limits

[verified] In a network-disabled `python:3.12-slim` container pinned by image digest `sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`, with 1 CPU, 2 GiB memory, 4 GiB memory-plus-swap, 128 PIDs, `docker-batch.slice`, and the read-only checkout and pytest dependency mount, the two focused files collected 40 tests and exited zero. Pytest warned that its cache could not be written to the read-only source mount; that warning did not affect the test result. `py_compile` and `git diff --check` also passed.

[verified] The exact footer app in `notes/2026-10-14-realtime-event120-target.md` is 846,000 bytes and is below the D7000 app budget of 860,644 bytes. That app evidence is not itself a matching raw expanded-image candidate receipt. No concrete D7000 raw candidate or transport manifest was constructed in this task: the available D9000-specific candidate/transport receipts cannot be reused for it. No package, installation admission, rollback proof, hardware approval, or physical validation is established here.

[inferred] The smallest next offline step is to construct and independently validate a D7000 raw candidate from the exact matching baseline, footer app, ELF, prepared selection, and linked-image receipt, then feed those corresponding receipts to this manifest builder and stream model. The parent/coordinator must review that exact output before considering any separate live campaign; this code does not create a device connection binding or authorize one.
