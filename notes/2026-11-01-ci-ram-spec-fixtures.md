# CI RAM fixture and sequencer specification correction

Personal, non-commercial Lunar work, based on
`6ece5032bb4a2e7f3856350c89015725f727a473`.

[verified] Mac CI run 41331077051, job 124921216033, exposed two app-state
fixture failures and a stale manual specification. `test_each_kind_loads_into_its_target`
attempted to import the complete Deep Bass sound (Shapes + Filter + its LFO
and cable) into Sound 2 beside the Macro/Plate starter. The application correctly
refused it at 101% RAM. The full-rack case in
`test_every_refusal_changes_nothing` used the same combination, so RAM
preflight refused before the intended `NO_ROOM` rack check. The source checks
RAM before modulation merge capacity; this priority is unchanged.

[verified] The successful import and full-rack fixtures now use explicit
Macro/Room instead of the starter's Macro/Plate. Metadata reports Plate as
65,728 bytes and Room as 41,184 bytes: 24,544 bytes are removed from an unrelated
master effect while preserving the incoming sound, insert parameters, LFO,
cable target remap, full eight-position rack, refusal-state byte comparison,
and `--without` behavior. The original starter/Deep Bass combination is now
also checked explicitly for a transactional RAM refusal. No budget, preflight
priority, sound example or engine implementation changes.

[verified] The manual test was correct. The sequence allocation changed from
36,864 to 45,056 bytes when immutable event targets were added (`a75cdef3`),
while chapter 13 retained 10% (36 KB). The chapter now gives 12% (44 KB), using
the existing metadata budget of 387,924 bytes and upward meter rounding. The
specification test remains unchanged. This says nothing about hardware RAM fit
or the separate eight-voice release acceptance target.

[verified] Local specification test reproduced the missing `12 % (44 KB)`
failure before the edit and passes after it. The remaining manual tests that
do not build an engine: 15 passed, 7 skipped because Markdown is absent,
1 deselected (`test_full_build`). An initial broad manual selection accidentally
reached the renderer fixture; it was interrupted and its 2 MB partial build
was removed. Native app verification then completed on the bounded LAN lane below.

[verified] Rarefaction status/orient/scope and Serena initial/config/find_symbol
agreed on the representative test body in the shared main checkout. Their root
is `/Users/likwid/Developer/mvave-fm1-firmware`, outside this isolated worktree;
no shared activation/restart occurred. Exact base source reads and bounded
searches in this checkout are authoritative for this change. No graph was built.

No device traffic, firmware/vendor processing or protected-target work occurred.
The lane's ignored evidence lives under `scratch/ci-ram-spec-fixtures/`; the
coordinator's durable copy is
`scratch/devkit-20261023/audit-20261101/ci-ram-spec-fixtures/` in the performance
worktree. Its `HANDOFF.md`, `native-complete.log`, `ram-causal.log`, image/source
identities and setup logs remain. Built-in drive free space: 1,114 GiB.


## Completed native verification

[verified] The exact pushed source
`efbb6f258951b16043b447f4a46ceba72e20406f` was exported with `git archive`
(SHA-256 `138e253eb05df6d90bce253491d542461828a4119fdbabcd4d5b52bdd07bafa0`).
The Aeon run used existing image
`sha256:54edd6544fdc41ef5573ae26f7aa8e7d1f594e5e4b9b54e2ad2f427f33e392a1`,
CPU 4–7, four CPUs, 6 GiB memory and 6 GiB memory-plus-swap,
`docker-batch.slice`, `--rm`, no network and read-only source/dependency inputs.
The container used explicit Clang compiler settings and project/session labels.
Its own writable staging was
`/home/likwid/datasets/lunar/ci-ram-spec-fixtures-20261101/`.

[verified] Final command:

```sh
python3 -m pytest tests/test_app_state.py \
  tests/test_manual.py::test_the_specifications_give_the_builds_shares_and_sizes \
  -o addopts= -q -ra --basetemp=/work/test-tmp
```

**13 passed, zero skipped, exit 0**. This ran the full app-state file, including
Sound 2 import/remapping, the full-rack `NO_ROOM` transactional refusal,
`--without` semantics and the original starter/Deep Bass RAM refusal, plus the
actual specification check. Direct harness probes report Macro/Room plus Deep
Bass at 365,528 bytes (95%), and the original starter plus Deep Bass refusing
at 390,056 bytes (101%). No further source changes were needed.

[verified] Setup attempts and their limits are retained: the image lacks `g++`,
so GNU make's default failed for the full-renderer fixture until Clang was
selected explicitly. The image also lacks the declared `jsonschema` test
dependency and pip; read-only offline wheels unpacked into task-local dependencies
restored schema coverage. A first dependency attempt missed Python 3.12's
`typing_extensions` dependency because the download resolver ran on Mac Python
3.15; supplying that wheel yielded the final complete pass. No container used
the network. These were test environment corrections, with no source changes.

[verified] No matching container remained after the run. The owned Aeon source
stage, binaries, test outputs and dependencies, and the downloaded local wheels
were removed. Small evidence remains; CPU 4–7 and the metadata claim were
released. The clean source worktree is retained until the coordinator confirms
the documentation update is integrated. Root reported the source correction
integrated blob-identically as `0cca920294374b504b147b36e2bc145e50a23963`;
required integration CI remains the coordinator's gate. No hardware acceptance
is implied.
