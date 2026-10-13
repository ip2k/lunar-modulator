# Frozen bench capture lifecycle sources

These are exact reviewed source copies for the FM-1 diagnostic campaign. The
source hashes in `source-pins.json` are the same bytes exercised on Hera. The
install/boot and entry/backup programs own usbmon capture processes, preserve
partial child output with fsync, and reject uncertain cleanup.

The wrappers are campaign-specific bench programs with literal absolute paths
and one-shot gates. Their presence here does not authorize another hardware
run. A new campaign needs a separately reviewed source closure, exact private
assets, current device/backup evidence and the recorded recovery plan. Do not
invoke the wrappers directly from a development checkout.

The two tests are device-free control-flow models. On Linux, run:

```sh
python -m pytest -q tools/bench_capture/lifecycle-v1/test_outer_lifecycle.py tools/bench_capture/lifecycle-v1/test_sequence_cli_failure.py
```

They cover 61 cases, including timeout/output durability, exact original
leader/reader identity, changed or escaped processes, ambiguous stop, replay
rejection and stopping a real harmless sequence child. `/proc`, transport,
time and process operations are modeled where documented in the tests. The
install/boot capture-body test excludes the real factory prelude. Successful
model results are not physical cleanup, flashing, CPU recovery or display
acceptance. The frozen sequence has four closed activation hashes and cannot
launch its children as supplied.

Retained Hera evidence and the independent replay are described in
`notes/2026-10-12-owned-capture-lifecycle.md`.

The sequence now routes returned admission to the lineage retained by the
native-read worker. `owned-admitted-backup-restore-once.py` is a source copy of
the admitted backup/restore wrapper with its passive SG comparison corrected
for tuple identities serialized as JSON lists. Its historical factory pins
remain unchanged; it must be rebound and reviewed for a new concrete campaign
before use. No consumed deployed source or old failed receipt was changed.
`test_admitted_passive_binding.py` covers equivalent representations and rejects
changed stat identities, numeric types and extra fields. The three lifecycle
test files passed 84 cases in 16 isolated Hera containers on 2026-10-12.

The historical `historical-install-7d2.py` source is retained solely to verify
old capture receipts against their actual program bytes. The recovery adapter
accepts that hash and the reviewed successor hash; it rejects caller-selected
hashes and any change after selecting a version. `test_install_capture_allowlist.py`
contains the 24 focused Hera cases, with modeled lifecycle receipts and no
factory authority. CI supplies the exact adapter and both source paths through
its three `LUNAR_PARTIAL_*` environment variables. This source gate does not
prove the complete interrupted-write recovery or a physical recovery.
