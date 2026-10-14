# Native application licence transition — 2026-10-14

## Change

The root `LICENSE` now contains the exact unmodified GPL-3.0-only text already present at `firmware/third_party/dinghy/LICENSE`. The original root MIT text was preserved byte-for-byte as `LICENSE-MIT`. `LICENSING.md`, the README license paragraph and the Developers' licence section distinguish the combined native application from the reusable MIT core and retain component-specific notices.

## Why the split is bounded

The repository's native release inventory records that the native diagnostic link integrates Dinghy's GPL-3.0-only platform along with separately licensed engine objects. The owner direction explicitly says the combined native firmware is GPLv3 while the reusable MIT core can remain MIT. The previous root MIT grant is preserved; this change does not claim to revoke it. The explicitly scoped reusable code is the first-party sequencer (`engines/seq/` and its public header) and state implementation (`engines/state/`), plus files whose existing headers explicitly say MIT. `firmware/native/` is mixed: its MIT headers remain MIT and its GPL headers remain GPL. No blanket MIT grant is made for the whole native directory.

The sequencer is documented as a C rewrite of MIT Movy, and the state codec calls itself MIT; their existing Movy provenance/license remains intact. The GPL text was copied without changes from the included Dinghy license, not constructed. The source inventory is not exhaustive, and per-file/upstream notices control.

## Validation and acceptance boundary

Validated with byte-for-byte comparisons: root `LICENSE` matches `firmware/third_party/dinghy/LICENSE` (SHA-256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`), and `LICENSE-MIT` matches the original root license at base commit `a0d46a9c9611a2240610df5df5d47117b93c1c34` (SHA-256 `f9c22c9ab390336c5a2cb311a8765de4a24ff4ba3328fd68aa373607677d5205`). `git diff --check` passed. The changed text was inspected before commit. This is documentation/licence-text work: no firmware build or release-image source manifest is produced. The existing native diagnostic link receipt remains non-release evidence, not a license clearance or release approval. A final release still needs an exact retained input manifest and corresponding source/build bundle for the specific image.
