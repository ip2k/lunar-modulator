# Native app-space reclamation plan — 2026-10-14

## Decision

[verified] No existing evidence identifies a feature-preserving, low-risk
optimization that recovers the roughly 96 KiB needed for two 48 KiB native
SAVE extents, much less those extents plus the required full-song default
preload. The retained all13 SAVE-scheduler link is already built with the
pi32v2 compiler at `-Oz -flto`, function/data sections and linker section
garbage collection. It occupies 863,380 bytes in an 868,836-byte application
budget, leaving 5,456 bytes of app-tail margin. Its arena headroom is 2,320
bytes. The 96 KiB figure is a requested physical-storage amount, not current
free or owned flash.

[inferred] The one justified next measurement is a matched all13 target-link
A/B of `-Oz -flto` against `-Os -flto`, with identical sources, link roots,
full-song preload bytes and target toolchain. This can find a compiler codegen
win at low implementation risk; there is no current basis to expect an
approximately 93 KiB improvement, so it must not be treated as the storage
plan or as permission to change capacity. If that A/B does not produce a
large, verified reduction, pursue the exact storage-ownership/migration
dependency documented below rather than removing supported engines or
assuming stock banks are reclaimable.

## Quantified space requirement

[verified] A current source-derived native SAVE collector bound is 43,130
bytes for the full container; a maximal Drums fixture emitted 35,176 bytes.
The collector bound does not constrain generic imported project files, whose
format ceiling remains 98,304 bytes. A 49,152-byte slot has enough room for
the 43,130-byte container plus the 32-byte transactional store header, so two
48 KiB slots are a plausible native-SAVE-only capacity direction. They are
not a proven physical allocation, nor a guarantee that every generic
98,304-byte import can later be persisted. The product must decide and
enforce the native-save/import distinction before using this smaller slot.

[verified] Recovering 98,304 bytes of app-tail space from the current expanded
application profile would require shrinking the linked app by at least
92,848 bytes beyond its present 5,456-byte margin, before accounting for
alignment, headers, or a content preload. The four existing full-song source
projects are 36,111–38,787 bytes each in their `.lunar` source form. If one
were embedded at roughly its source size, the required app reduction would
rise to roughly 128,959–131,635 bytes from the current retained link; the
exact packed asset and linked increment must be measured by preparing and
linking the selected profile. Source size is only a planning proxy: it is not
the packed payload size or the final XIP image delta.

[verified] The expanded-profile arithmetic currently puts the app/config
image end at `0xD7AB0`, leaving 5,456 erased bytes through `0xD9000`, of which
only `[0xD8000, 0xD9000)` is a whole erased 4 KiB sector. The areas beyond
`0xD9000` are named VM, BTIF, USR, opaque gap and protected key bank. The
expanded candidate preserves those contents; no project extents there are
admitted. A smaller app only increases the app-tail candidate. It does not
create ownership over those banks or prove the tail is safe for SAVE without
the raw-layout, migration, recovery and physical gates.

## Existing evidence and candidate assessment

| Candidate | Retained evidence | Assessment |
| --- | --- | --- |
| Change `-Oz` to `-Os` | The application probe and retained integration link use pi32v2 `-Oz -flto`; catalogue tooling accepts `-Os` or `-Oz` and can emit LTO objects. Separate native codec/loader measurements compile both optimization levels, but they are not a full application link comparison. | **One useful bounded experiment.** Same compiler target and ABI, but size and execution behavior must be checked on the actual linked app. No measured result yet; expect an incremental result, not 93–132 KiB. |
| Add LTO, function/data sections, or section GC | All are already present in the retained link. It also explicitly roots project collection, validator, SAVE service, sequencer and runtime entry points. | No uncollected or unoptimized build path established as a saving. Removing link roots would remove required behavior. |
| Compress large Plaits/Braids tables | Prior 16-profile raw-DEFLATE work reports best gross savings of 27,024 B including indexes, or 25,583 B after an isolated 1,441 B decoder estimate. | Still much smaller than the target before full-app costs. Direct-pointer users need 83,712 B expansion RAM or a new cache/API. Only 2,320 B of linked arena headroom is measured. No drop-in fit. |
| Compress drum samples | Prior offline profiles report 8,976 B net after isolated decoder cost for three cymbal arrays. | Cannot close the gap; whole-array access would need about 110 KiB expansion RAM, while a block cache and bounded timing are not implemented. |
| Deduplicate generated x0x exponent rows | Bytewise check finds 19 distinct 128-float rows in the 9,728-byte table. | Exact deduplication saves zero. Runtime regeneration is a behavioral/code-size/timing change and is unmeasured on pi32v2. |
| Replace MSFA/effect tables or alter DSP | The retained image has 20,484 B of named MSFA sine, exp2 and fixed-rate frequency tables; the 13-engine requirement and reference audio are preserved. | No lossless replacement or safe omission has been measured. Approximation is a feature/behavior change, not a safe storage optimization. |
| Compress full-song preload in the app | Four source candidates are 36–39 KiB each; existing link includes only a 2,784-byte `lunar_content_00` symbol. | Need the prepared packed bytes, link-map delta, and measured decompressor/runtime RAM before crediting any reduction. Keep at least one full-length default song as required; selectable content alone does not meet the default-image requirement. |
| Reuse/migrate VM, USR or unnamed gap | The audited expanded layout preserves these exact bytes; the current verifier reports storage ownership, backup provenance, semantic migration and hardware admission false. | Not an available optimization. A future allocation requires exported and understood contents, owner-approved migration/rollback, raw-layout proof, and a scatter-capable store if extents remain noncontiguous. |

The earlier installed-footprint receipt used an older 845,916-byte image and
found 40,329 B gross savings from whole-symbol zlib of the top 30 constants.
That excludes decoder code, runtime workspace and access penalties; its
256-byte block experiment saved only 2,884 B aggregate. It is not the current
863,380-byte baseline and does not demonstrate a deployable compression
scheme. The current all13 symbol ranking likewise attributes bytes rather
than identifying removable content: largest are Plaits integrated waves
(50,688 B), ride/crash/hat samples (110,549 B combined), packed Braids
(24,159 B), x0x exponent table (9,728 B), and MSFA sine/exp2 tables
(8,192 B each). These are live engine resources, not dead link baggage.

## Exact next build experiment (not run here)

Run one matched two-profile application link on Hera using the pinned JieLi
pi32v2 toolchain, the same full thirteen-engine source manifest, feature/root
set, layout and selected full-song asset bytes. Recompile the complete native
catalogue for both profiles; do not mix cached `-Oz` bitcode with `-Os`
objects. Use `-Oz -flto` as control and change only the compiler size flag to
`-Os -flto` in the treatment. Preserve freestanding/no-builtin,
function/data sections, `--gc-sections`, LTO plugin target settings, defines,
generated tables, and all thirteen production engines. Prepare the exact
full-song profile first and bind both links to its packed payload SHA-256.

Record for each link: toolchain identity/hash, source/object manifest, command
hash, ELF and flat app SHA-256, app bytes and budget margin, section totals,
largest symbols, pool end/guard and headroom, undefined symbols, and linker
root coverage. Reject the treatment if it changes supported modules,
serialized output, symbol/ABI gates, project SAVE roots, or required app
behavior. Compare known render/oracle outputs and native project collector,
validator, pack/load and SAVE unit suites for both linked profiles; a size
improvement is useful only if behavior remains identical and runtime timing
remains within the existing target gate. Do not use a target-speed claim from
host execution. This task intentionally performs no build.

**Interpretation threshold:** report the measured byte delta plainly. A result
below 92,848 B does not create room for 96 KiB of storage from the current app
tail; any bundled song increases that threshold by its actual linked payload.
Even a larger result only creates candidate geometry until the exact expanded
raw-layout and preservation verifiers accept it and a separate owner-reviewed
migration/recovery plan establishes physical ownership. It does not authorize
flash writes.

## Evidence pointers and reproducibility

- Current link: `notes/2026-10-14-save-scheduler-verification/RESULTS.md`,
  `link-receipt.json` (SHA-256
  `7d8775421160143d278abbb47dfb4c099220ac866d69f7f65d131c3af1919db1`),
  `sections.txt`, and the retained ELF/map/symbol artifacts under
  `build/native-save-scheduler-20261014/save-scheduler-link-v1/`. The receipt
  pins app bytes 863,380, margin 5,456 and arena headroom 2,320.
- Link flags and implementation: `measure.py` in that verification directory;
  `tools/native/build_application_probe.py`; `tools/native/compile_catalogue.py`
  (the latter exposes both `-Os` and `-Oz` and optional LTO).
- Current symbol attribution: `python3 tests/native/size_savings_audit.py
  --limit 35`; read-only result against the retained `symbols.txt`.
- Existing savings summary: `notes/2026-10-14-native-size-savings.md` (SHA-256
  `6c1cdac84fcd04383b120a91d9bbf5c0e28396cbd3487755d31c67e95cc910e5`).
- Older zlib receipt: `notes/2026-10-13-native-footprint/RESULTS.md` (SHA-256
  `c3d8c73ccaf8a1697b1bb01f167eec754c72991f167a845d0a531d185969e4c5`);
  historical image only.
- Physical extent/ownership bounds:
  `notes/2026-10-14-expanded-storage-ownership-review.md` (SHA-256
  `9b6f2b50d82384dc6ca6ca444ac7cd4a2edfc879d6af336d26dba8a20b25cc97`).
- Current native accepted-state measurement and limitations:
  `notes/2026-10-14-project-capacity-measurement.md`; latest dense fixture is
  32,924 B, while 98,304 B remains the generic format ceiling and maximum
  joint app-reachable state under generic imports is unproved.
- Source-derived native collector maximum and rerun evidence:
  `notes/2026-10-14-collector-total-bound.md` (43,130 B full container) and
  `notes/2026-10-14-collector-max-validation.md` (49,152-byte simulator slots;
  host-side transactional tests only; the smaller-slot run did not inject
  torn/partially programmed writes).
- Existing full-song source sizes were reproduced read-only with
  `find engines/state/examples -maxdepth 1 -type f -name '*.lunar' -print0 |
  xargs -0 wc -c`; exact packed payload sizes and link deltas remain to be
  measured for the actual default selection.

This research added no source/build change and ran no firmware build or device
operation. The shared branch contains concurrent workers' dirty files; none
were changed here. No physical capacity, app-installability, SAVE-bank fit,
song acceptance or device behavior is claimed.
