# 2026-11-08: the `.fwsc` builder and the flasher's admission check (M12, offline)

docs/18 milestone M12 asks for a builder that makes an installable package
from the user's own stock V15 and passes `package_guard.py`. This note records
what was built, what was checked and what is still open. **Everything here is
offline. No package was sent to any FM-1, Pico or dev kit, and no MIDI or
SysEx was sent.** Device acceptance of a Lunar package is untested.

## What exists

- `tools/jieli/build_fwsc.py` (MIT) has four commands:
  - `install`: your stock V15 plus a Lunar `app.bin` makes `<out>.fwsc` and `<out>.fwsc.manifest.json`;
  - `rollback`: your V15, verified, copied byte for byte, plus its manifest;
  - `verify`: checks a package (and optionally its manifest) by the same rules the browser uses;
  - `profile`: prints the profile computed from a stock package, so the pin can be reviewed.
- `sim/web/www/lunar-package-admission.js` (MIT, self-contained, no imports
  and no URLs) exports `verifyNativePackage(bytes, {manifest})`.
  - It returns the record `native-ota-adapter.js` expects:
    `format: 'lunar-native-package-admission-v1'`, kind, product, model,
    version, `logicalImage`, `logicalImageSha256` and the manifest.
  - Otherwise it rejects with `package admission blocked: <reason>`.
  - It recomputes the manifest from the bytes. A manifest supplied with the
    package must equal it canonically.
- `tools/jieli/inspect_stock_flash.py` gains `extract_stock_components(raw)`.
  It returns the decoded SPL, `isd_config.ini`, `cfg`, `app.bin`,
  `cfg_tool.bin`, `eq_cfg_hw.bin` and `ota.bin` after the full strict parse
  and the no-op rebuild check.

## The rules (both implementations)

1. **The input is pinned.** The stock package must have SHA-256
   `db1642b2…7edb8a` (699,956 B, identity `FM-1_015`). The M-VAVE CDN copy and
   Baud Girl's saved V15 are the same file [verified: both hashed]. Any other
   input is refused, including a Lunar package offered as "stock".
   - The pinned profile records hashes of every part that must stay unchanged.
     So the browser checks a package without holding any vendor bytes.
   - Building also recomputes the profile from the input and requires it to
     equal the pin [verified: real V15].
2. **The stock gates run on the input.**
   - `package_guard.check_package` must pass, with SPL `730e54f0…`, 14,384 B.
   - `inspect_nested` checks every nested CRC and a byte-exact no-op rebuild.
   - `--stock-unpack` adds an optional cross-check against an independent
     `fwunpack_newfw.py` output.
3. **Only the app changes.**
   - `app.bin` goes into V15's slot at flash `0x4120`. The slot is 581,564 B
     and ends where `cfg_tool.bin` starts, at `0x920DC` [verified: V15
     directory].
   - The rest of the slot is decoded `0xFF`.
   - These CRCs are recomputed: the app record (size, data CRC, header CRC),
     the `app_area_head` record, the outer `flash.bin` CRC, the entry-list CRC
     and the UFW header CRC.
   - On real V15, every flash byte that changed lies inside `[0x4000, 0x920DC)`
     [verified: the builder's own changed-range check plus a test].
4. **The head and VM are untouched.**
   - Flash `[0, 0x4000)` must equal stock. Its hash is `d9f43191…d9bd67`, the
     same as Baud Girl's installer constant [verified].
   - `flash.bin` is exactly `0x93000` B, so the package holds nothing at or
     above VM.
   - The VM, PRCT, BTIF, USR and key_mac descriptors are covered by the masked
     area hash.
   - The manifest states `write_range [0x4000, 0x93000)` and the four mutable
     ranges inside it.
5. **The app must fit.** `fm1_budget.measure` must pass with the profile's
   slot. With `--elf` it also checks SRAM and cache RAM.
   - The eight-voice soak image is refused: 597,916 B in a 581,564 B slot, a
     margin of −16,352 B [verified: `build_fwsc.py install` on the real V15
     with `clk320-soak30/cap8-trunc12/app.bin`, re-run 2026-11-09, refused
     with exactly those figures]. This matches `notes/2026-11-08-fit-tables.md`.
6. **Identity.**
   - The package identity must be `FM-1_5xx`. It cannot be the stock identity.
   - The app must contain that identity exactly once as `FM-1_5xx\0`, and no
     other `FM-1_nnn\0` literal.
   - Why a new version should install: stock step 1 refuses only the running
     version [reported: Baud Girl FM-1_078 ↔ 079; Echomatter FM-1_016; docs/03 §5].
     Baud Girl's FM-1_092 renamed the app literal in place [verified:
     `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §3].
   - The range `FM-1_5xx` is the plan in DEVELOPERS.md and is not yet an
     owner decision.
7. **Rollback** is your V15 byte for byte. The builder refuses when
   `--running` is `FM-1_015`, because step 1 refuses the same version. It
   works only while the running Lunar app answers the stock update protocol
   [inferred: the stock updater needs a running update service, trap 2].

## Evidence

All of this was run on 2026-11-08. Pytest ran in a `python:3.12-bookworm`
container on a LAN build host, because the workstation was overloaded. The node
binary came from `node:22-bookworm-slim`.

- `tests/test_build_fwsc.py`: 32 tests; 31 synthetic, plus 1 opt-in on real V15.
  - Synthetic packages use V15's full flash geometry with a 0x200-byte slot,
    and no vendor bytes.
  - They cover:
    - a byte-identical rebuild of stock through `assemble`;
    - install and rollback;
    - nine refusals of apps and identities;
    - an input that is not pinned, and a Lunar package offered as input;
    - the unpack cross-check;
    - ten content tamper cases with repaired CRCs (head, fill, cfg/reserved,
      VM descriptor, unreferenced tail, slot overflow, app record CRC, app
      placement, entries after flash.bin, bytes before flash.bin);
    - CRC damage and identity relabelling;
    - the browser module's profile equals Python's;
    - every package the builder makes is admitted by node, and every tamper
      case is rejected.
  - Opt-in (`FM1_STOCK_FWSC`, `FM1_STOCK_UNPACK`) on the real V15:
    - the computed profile equals the pin;
    - the no-op rebuild is byte-identical;
    - a 100,000 B app builds and passes package_guard, with changes inside
      `[0x4000, 0x920DC)`;
    - rollback equals the input;
    - node admits both packages with manifests that equal Python's;
    - a 581,565 B app is refused.
- With the real V15 set, the related suites passed: 114 passed, 1 skipped.
  - The suites: `test_build_fwsc`, `test_inspect_stock_flash`,
    `test_model_app_replacement`, `test_inspect_version_contract`,
    `test_package_guard`, `test_fm1_budget`, `test_inspect_fwsc`.
  - The skip is `test_model_app_replacement`'s linked-diagnostic case.
- `sim/web/test/lunar-package-admission.test.mjs` (node:test, in CI): 10 tests.
  - It builds a synthetic package in JavaScript.
  - It covers:
    - admitting an install, a full slot and the rollback;
    - manifest forms and mismatches;
    - twelve tamper cases with repaired CRCs;
    - CRC damage, wrong identities, a duplicate, foreign literals and wrong sizes;
    - the pinned profile admitting nothing synthetic;
    - a check that the module has no URLs, imports or device APIs.
  - The opt-in `LUNAR_PRIVATE_FWSC` admitted the real V15 as the rollback.

## Review, 2026-11-09

An adversarial review of PR #182 re-ran the evidence and fixed four problems
in new commits on the same branch:

- **One SFC key.** `build_fwsc` always decoded the app area with
  `STOCK_CHIP_KEY`, while the browser decoded with `profile.sfc_key`. Both
  were right for the one pinned profile, but a second profile with another
  key would have made them disagree silently. Both now refuse a profile whose
  key is not `0x980f`, and whose `flash.bin` does not end at VM; tests cover
  both sides.
- **Outputs together or not at all.** `install` and `rollback` wrote the
  package, then refused on a stale `<out>.manifest.json`, leaving a package
  with no manifest. Both paths are now checked first, and the package is
  removed if writing the manifest fails.
- **The builder's own range check is now tested.** Nothing showed that
  `verify_install`'s changed-byte walk ever fires (`describe_package`'s
  hashes refuse every tampered package first). A test now narrows the
  declared ranges so the real assembled package's `app_area_head` CRC falls
  outside them, and another declares a range below `0x4000`; both refuse and
  write nothing.
- **Small:** `profile` on a short file is a refusal rather than a traceback;
  the `stock bytes with a foreign identity` branch is unreachable while the
  pin is honest (the SHA covers the identity markers) and is kept as a
  documented defence, with the test's regex tightened to the branch that
  really fires.

Re-run evidence, 2026-11-09, `python:3.12-bookworm` on a LAN build host with
node 22 [verified]:

- `tests/test_build_fwsc.py` on synthetic packages: 34 passed, 1 skipped
  (the real-V15 opt-in).
- With the real V15 (`FM1_STOCK_FWSC`, and `FM1_STOCK_UNPACK` pointing at a
  `fwunpack_newfw.py` tree with `files/eq_cfg_hw.bin` and `ota.bin` staged at
  the paths `inspect_nested` reads): the seven suites listed below, 117
  passed, 1 skipped. With the bare `fwunpack_newfw.py` tree, the two
  pre-existing real-file tests in `test_inspect_stock_flash` and
  `test_inspect_version_contract` fail on the missing files; that is the
  unpack layout, not this branch.
- node `lunar-package-admission.test.mjs` with `LUNAR_PRIVATE_FWSC` set to
  the real V15: 12 of 12 passed.
- CLI on the real V15: `rollback --running FM-1_501 --stock-unpack …` wrote a
  file `cmp`-identical to the input, `verify --manifest` accepted it, and the
  soak `app.bin` was refused as above.
- The two local V15 copies (M-VAVE CDN and Baud Girl's) both hash to
  `db1642b2…7edb8a` [verified 2026-11-09].

## Not done, not tested

- **No device test.** It is unknown whether stock step 1 and the OTA loader
  accept a Lunar package [inferred from the reports above]. This is M8/M12
  hardware work and needs §4 approval.
- **No real Lunar app fits yet.** The soak image is 16,352 B over the slot.
  A real Lunar `app.bin` must also embed the `FM-1_5xx\0` literal, and
  nothing in the firmware build does that yet.
- **The flasher is not wired up.** The web flasher code
  (`native-package-admission.js`, `native-ota-adapter.js`) is on
  `feature/2026-11-01@milestone-integration` (PR #161), not on main. Wiring
  means re-exporting this module's `verifyNativePackage` there and checking
  that the flow's rollback (product `FM-1_015`) takes a `stock-rollback`
  admission.
- **The head is rewritten even though it is unchanged.** The stock OTA
  loader rewrites the second-stage bootloader from the package [reported:
  Baud Girl FINDINGS 5.4, docs/07 risk table]. The builder keeps the head
  byte-identical, so its content cannot change, but a power cut while the
  loader erases and rewrites `[0, 0x4000)` would still damage the boot area,
  which docs/17 cannot recover [inferred]. Whether the loader skips identical
  sectors is unknown. M12's power-cut case must cover that window, on the
  dev kit first.
- **One stock version only.** Only V15 is pinned. Any other stock version
  needs its own reviewed profile.
- **No code copied.** No code came from Felucca, SLOOP, Echomatter or other
  branches. The builder reuses this repository's MIT unpackers
  (`inspect_fwsc`, `inspect_stock_flash`, `model_app_replacement`).
