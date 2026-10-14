# Demo scene-label compatibility adaptation

This bounded compatibility change shortens four replacement-project scene labels that exceeded the native importer's six-character limit. It changes display metadata only; the test reverses the edits and proves exact original bytes and all non-label song data are preserved.

## Scope and provenance

The worktree is `feature/2026-10-14@demo-scene-label-adaptation`, based on exact source commit `f3779b78082cceec74852120306efcaca15abcf4` in an isolated Hera checkout. The two source assets retain their original `source_provenance` commit/path (`fb92cc0d…` origin) and now carry `original_sha256`, `adaptation_kind: scene-label-compatibility`, and the explicit old/new scene-label map. The current catalogue `source_sha256` pins the adapted bytes.

| Project | Scene labels adapted | Original SHA-256 | Adapted SHA-256 |
|---|---|---|---|
| Event Horizon Showcase | `sn 4 Suspense` → `sn 4 Tense`; `sn 5 OpenSky` → `sn 5 Sky` | `0d5d871bd31db1e628efbf291fd306671b81c93bef254a950291bf95f5413d1c` | `22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f` |
| Packet Bloom Showcase | `sn 1 Packets` → `sn 1 Packet`; `sn 4 Dissolve` → `sn 4 Fade` | `eb55a36129ef3db02136b2ed0859fafcad94e3b2cbc3fa42761383d380249731` | `853be1d05bd206d9fce928e5d36944d932491a9b9c69cf79d96e6f78392700e7` |

## Verification

Ran in Hera's pinned offline container image `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`, with network disabled, `docker-batch.slice`, 4 CPUs, 4 GiB memory/swap, and `/tmp/check-venv/bin/python`:

```sh
python -m pytest -q -p no:cacheprovider \
  tests/test_native_image_catalogue.py \
  tests/test_native_demo_scene_label_adaptation.py
```

Result: all tests passed. The adaptation test reverses each label substitution and verifies the exact original SHA, checks only the `set` labels differ, preserves all other source fields and SET lines, and verifies scene labels are at most six characters. It also builds `fm1-state` with the 55 production modules, packs each edited asset, and sends the packed bytes through the native project-sequence stage. Both imports match a direct Movy1 import canonically, retain nonzero bars/song entries/tracks, and report zero refused commands, dropped events, evicted gates, and Movy faults.

`git diff --check` passed. The only edited paths are the two named assets, `tools/native/export_image_catalogue.py`, `tests/test_native_image_catalogue.py`, and `tests/test_native_demo_scene_label_adaptation.py` plus this note.

## Limits and next dependency

This proves source-byte reversibility, catalogue hash metadata, and native packed sequence staging for these two edits. It does not establish full application startup RAM, target/device behavior, musical or listening approval, shipped/default status, or a product acceptance decision. The owner keeps musical approval and default promotion pending. No hardware command was run.

Serena's active project was the shared Mac checkout, so it was not redirected; this isolated Hera work used bounded direct source inspection and the pinned native build/test path. Rarefaction was not selected in this Hera session. The coordinating root must review and back up the returned Hera branch; Hera has no GitHub write credential.
