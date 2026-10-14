# Native demo-selection request adapter

This change adds a pure browser-side adapter between the exported demo catalogue and the existing module-selection validator. It validates selected project IDs and startup ordering, then creates the exact version-1 request shape consumed by `tools/native/prepare_demo_selection.py`: `version`, `engines`, `effects`, `midi`, `modulation`, `project_ids`, and `startup_index`.

The adapter passes no source paths, source hashes, packed hashes, or dependencies. The browser catalogue reports source choices and current disposition only; `prepare_demo_selection.py` remains responsible for trusted-source staging, hashing, packing, and dependency validation. An empty project list is refused because the native request contract requires at least one project. Arrays and the resulting request are frozen snapshots so later caller changes cannot silently alter a submitted selection.

`describeNativeDemoCatalogue` exposes the current project title/category/nominal duration/disposition and required full-song-default status for a future chooser. The restored choices remain categorized as legacy examples with `default_candidate: false`; `fullSongDefault.status` remains `pending`. This adapter does not approve a composition, choose a default, wire a browser UI, build or link firmware, or claim installability or device acceptance.

Validation run on the Mac checkout at `e435edadad48641e9e08c0023b71b80b5692cd44`:

```sh
node --test sim/web/test/native-demo-selection.test.mjs sim/web/test/native-build-selection.test.mjs
```

All 10 tests passed. New cases cover exact request keys, chosen order and startup index, unknown/duplicate/empty choices, invalid startup indices, legacy/default-pending disposition, and immutability/path/hash/dependency exclusion. No heavy build or hardware operation was run.

Serena's active project and Rarefaction's detected TypeScript root both remain `/Users/likwid/Developer/mvave-fm1-firmware`, not this isolated checkout. The shared semantic root was not changed; bounded file inspection and the focused Node tests were used instead. The adapter remains unconnected to a UI/build service; the next dependent step is a separately reviewed UI integration that submits these requests to the already-defined backend preparation contract while preserving independent packed dependency, exact-content, native-link, target-RAM, musical, and hardware gates.
