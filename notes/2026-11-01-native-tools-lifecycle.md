# Native tooling temporary-data lifetimes — 2026-11-01

The release native-tools audit at `e267d7cd58efef29afb2c0c38562f4878e8106f5`
found two lifecycle gaps. This fix starts from coordinator `1fbc77af`; the
relevant source and project instructions are unchanged between those pins.

[verified] `run_trusted_continuous_build.py` previously acquired request,
catalogue and source copies before its cleanup lifetime. Setup exceptions
could leave those private siblings behind. An `ExitStack` now registers
cleanup immediately after exclusive acquisition of each path. Source and
catalogue roots are exclusively created before copying/cloning, so a collision
never confers ownership. Every registered cleanup is attempted even if a later
operation or another cleanup raises. The intentional output evidence directory
is retained. Container ownership, refusal checks, limits and receipts retain
their existing contract.

[verified] `verify_inventory.py` now puts its per-run temporary directory under
`<checkout>/scratch/workbench-inventory`, retaining context-manager cleanup on
success and failure. The empty scratch parent is kept as the known project
location; a process killed before Python cleanup can leave a per-run directory
there for explicit investigation. No global or stale-directory sweep is added.

[verified] Before editing production code, ten synthetic causal cases failed
on the old implementation: seven setup boundaries, one preexisting catalogue
collision and inventory success/failure temporary placement. The final twelve
lifecycle cases also exercise preexisting source and request collisions. The
combined focused run passed **50 tests** using:

```sh
python -m pytest tests/test_native_tools_lifecycle.py \
  tests/test_installer_trusted_policy.py tests/test_workbench_inventory.py \
  -o addopts='' -q --tb=short --basetemp=scratch/lifecycle-tests -p no:cacheprovider
```

Fake dependencies inject request-fsync, catalogue-manifest/copy, clone,
checkout, toolchain-manifest and command-construction failures. No Docker
container, native build, protected archive extraction or device operation ran.
Inventory witnesses use synthetic ZIP bytes and an injected extractor; vendor
pins remain unchanged. `git diff --check` passed. Private RED/GREEN logs and
handoff are retained under the performance audit's `release-native-tools-gap/`.
Owned pytest products and Python bytecode are removed after recording results.

Rarefaction and Serena remain on shared primary
`/Users/likwid/Developer/mvave-fm1-firmware`. Status/config were checked; both
bounded symbol/scope queries failed because these newer tooling paths are absent
there. No shared root was changed. Direct isolated source inspection and the
prior complete pinned reads supplied navigation; no semantic completeness is
claimed. Independent review and parent integration/CI remain required. This
change supplies no firmware admission, hardware, audio or product acceptance.
