# SET receipt integration regression

[verified] At base `3807f3de8d0e1d1ef9b659678a1b15607835bc5c`, the controller test fixture created ordered project content but omitted the now-required `selected_content`. The production path at `tools/native/prepare_demo_selection.py` constructs project identity rows followed by SET identity rows, carrying each SET's `parent_project_id`; `build_demo_image.checked_link_receipt` refuses missing or drifted identities before linking.

[verified] Updated the controller fixtures to follow that schema and added a SET-bearing receipt case plus mutation cases for changed project identity/order, SET identity/order, SET parent, and startup-parent selection. While making the formerly blocked explicit-identity case reachable, tests exposed a variable shadowing defect: `checked_link_receipt` overwrote the firmware identity local with the content identity list, so the returned receipt's `firmware_identity` was wrong. Renamed the content local and asserted both the firmware identity and ordered content receipt. Validation remains unchanged.

## Validation

[verified] Fresh FM1 state codec built from this worktree inside `lunar-preload-tests:20261014`, image SHA-256 `1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`. Test container used network none, `docker-batch.slice`, 2 CPUs, 3 GiB memory/swap, 256 pids, exact checkout mounted at `/work`, and pytest dependencies mounted read-only at `/pytest-deps`.

[verified] The final command configured `FM1_STATE_TOOL=/work/engines/build/fm1-state` and `PYTHONPATH=/pytest-deps`, then ran:

```sh
python3 -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_native_demo_image_controller.py \
  tests/test_native_demo_selection.py \
  tests/test_native_content_set.py \
  tests/test_native_content_embedding.py \
  tests/test_sim_server.py
```

Result: 269 passed, 18 skipped in 45.97s. The skips are retained target-toolchain-only cases; no device or hardware acceptance was tested. `git diff --check` also passed before commit.

[reported] Serena and Rarefaction were available but selected/configured for the Mac checkout, not this isolated Hera worktree. To avoid changing a shared semantic-project selection, this small patch used direct source and test inspection instead.

## Handoff

[verified] Branch: `codex/2026-10-14-set-receipt-regression`, based on `3807f3de8d0e1d1ef9b659678a1b15607835bc5c`. Commit: 9eac541e7a475463e0dde65f5b1bbb042f79b679; verified Hera bare branch ref matches this SHA. GitHub backup remains pending coordinator fetch and verification.
